from io import BytesIO
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from stt_deepgram import transcribe_audio
from openai_api import process_transcript_with_llm
from tts_google_cloud import text_to_speech
import psycopg2
from pinecone_database import store_embedding, retrieve_personality
import logging
from user_database import initialize_database

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

initialize_database()

# Connect to PostgreSQL
conn = psycopg2.connect(dbname='postgres', user='postgres', password='2003', host='127.0.0.1', port='1234')
cursor = conn.cursor()

users = {}
chat_history = {}

@app.route("/")
def index():
    return render_template("home.html")

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/profile")
def profile():
    return render_template("profile.html")

@socketio.on("connect")
def handle_connect():
    logging.debug("Client connected: %s", request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    disconnected_user = None
    for username, sid in list(users.items()):
        if sid == request.sid:
            disconnected_user = username
            break
    if disconnected_user:
        del users[disconnected_user]
        emit("user_list", list(users.keys()), broadcast=True)
        logging.debug(f"User {disconnected_user} disconnected")

@socketio.on("join")
def handle_join(data):
    username = data.get("username")
    if username:
        # Register user if not already in database
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if not cursor.fetchone():
            personality = data.get("personality", "Default personality")
            cursor.execute("INSERT INTO users (username, personality) VALUES (%s, %s)", (username, personality))
            conn.commit()
            
        users[username] = request.sid
        emit("user_list", list(users.keys()), broadcast=True)
        logging.debug(f"{username} joined with sid {request.sid}")

# ------------------------ AI-PERSONALIZED MESSAGE RESPONSE ------------------------

def generate_personalized_response(username, message):
    """ Generate AI response based on stored personality. """
    try:
        # First check PostgreSQL directly for reliability
        cursor.execute("SELECT personality FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        personality = result[0] if result else None
        
        # If not in PostgreSQL, try Pinecone
        if not personality:
            personality = retrieve_personality(username)

        if not personality:
            personality = "Default AI behavior"  # Fallback if no personality is found

        prompt = f"User's Personality: {personality}\nUser's Message: {message}\nAI Response:"
        
        response = process_transcript_with_llm(username, prompt)
        return response if response else "Sorry, I couldn't process that."
    
    except Exception as e:
        logging.error(f"Error generating response: {str(e)}")
        return "Error generating response."

@socketio.on("send_message")
def handle_send_message(data):
    sender = data.get("sender")
    receiver = data.get("receiver")
    message = data.get("message", "")

    # Generate personalized AI response
    ai_reply = generate_personalized_response(sender, message)

    payload = {"sender": sender, "receiver": receiver, "message": ai_reply}
    
    if receiver and receiver in users:
        emit("receive_message", payload, room=users[receiver])
    else:
        emit("receive_message", payload, broadcast=True)

# ------------------------ PERSONALITY STORAGE FUNCTIONALITY ------------------------

@app.route("/store_personality", methods=["POST"])
def store_personality():
    data = request.json
    username = data.get("username")
    personality = data.get("personality")
    
    if not username or not personality:
        return jsonify({"error": "Username and personality are required"}), 400

    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            # Create new user
            cursor.execute("INSERT INTO users (username, personality) VALUES (%s, %s)", 
                        (username, personality))
        else:
            # Update existing user
            cursor.execute("UPDATE users SET personality = %s WHERE username = %s", 
                        (personality, username))
        
        conn.commit()
        
        # Store personality in Pinecone
        success = store_embedding(username, personality)
        
        return jsonify({
            "message": "Personality stored successfully!",
            "pinecone_success": success
        })
    
    except Exception as e:
        logging.error(f"Error storing personality: {str(e)}")
        return jsonify({"error": "Failed to store personality"}), 500

# ------------------------ SPEECH PROCESSING FUNCTIONALITY ------------------------

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        logging.info("Received request at /transcribe")

        # Check if audio file exists
        if 'audio' not in request.files or request.files['audio'].filename == '':
            return jsonify({'error': 'No valid audio file received'}), 400

        # Get username from the headers
        username = request.headers.get('X-Username')
        if not username:
            # Try to get from form data
            username = request.form.get('username')
            
        # If still no username, return error
        if not username:
            return jsonify({'error': 'Username is required'}), 400

        # Ensure the user exists in database
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            # Create a default user if not found
            cursor.execute("INSERT INTO users (username, personality) VALUES (%s, %s)", 
                        (username, "Default personality"))
            conn.commit()

        audio_file = request.files['audio']
        audio_data = BytesIO(audio_file.read())

        # Speech-to-Text (STT)
        transcription = transcribe_audio(audio_data)
        if not transcription or transcription.startswith("Error"):
            return jsonify({'error': transcription or "Failed to transcribe audio"}), 500

        # Process transcription with LLM
        llm_response = process_transcript_with_llm(username, transcription)
        if not llm_response or llm_response.startswith("Error"):
            return jsonify({'error': llm_response or "Failed to generate AI response"}), 500

        # Convert AI response to speech (TTS)
        tts_audio = text_to_speech(llm_response)
        if not tts_audio or tts_audio.startswith("Error"):
            return jsonify({'error': tts_audio or "Failed to convert text to speech"}), 500

        return jsonify({
            'transcription': transcription,
            'llm_response': llm_response,
            'tts_audio': tts_audio
        })

    except Exception as e:

        app.logger.error(f"Transcription error: {str(e)}")
        return jsonify({"error": "Transcription failed"}), 500

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=8000, debug=True)
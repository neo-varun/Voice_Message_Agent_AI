import os
from io import BytesIO
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from stt_deepgram import transcribe_audio
from openai_api import process_transcript_with_llm
from tts_google_cloud import text_to_speech
import logging
from database_schema import db, User, Message, init_db
from pinecone_database import store_embedding, retrieve_personality
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:2003@127.0.0.1:1234/voice_agent')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)
# Optionally add a message queue for scaling: message_queue=os.getenv('REDIS_URL')
socketio = SocketIO(app, cors_allowed_origins="*")

init_db(app)
users = {}

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
    disconnected_user = next((u for u, sid in users.items() if sid == request.sid), None)
    if disconnected_user:
        del users[disconnected_user]
        emit("user_list", list(users.keys()), broadcast=True)
        logging.debug("User %s disconnected", disconnected_user)

@socketio.on("join")
def handle_join(data):
    username = data.get("username")
    personality = data.get("personality", "Default personality")
    if username:
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, personality=personality)
            db.session.add(user)
            try:
                db.session.commit()
            except Exception as e:
                logging.error("DB commit error: %s", e)
        else:
            setattr(user, '_login_update', True)
            db.session.commit()
        users[username] = request.sid
        emit("user_list", list(users.keys()), broadcast=True)
        logging.debug("%s joined with sid %s", username, request.sid)

@socketio.on("send_message")
def handle_send_message(data):
    try:
        sender = data.get("sender")
        receiver = data.get("receiver")
        message_content = data.get("message", "")

        # Get user records
        sender_user = User.query.filter_by(username=sender).first()
        receiver_user = User.query.filter_by(username=receiver).first()
        sender_id = sender_user.id if sender_user else None
        receiver_id = receiver_user.id if receiver_user else None

        # Store the sender's message (non-AI)
        user_message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            sender=sender,
            receiver=receiver,
            content=message_content,
            is_ai_response=False
        )
        db.session.add(user_message)
        db.session.commit()

        # Create a payload with the original message
        payload = {"sender": sender, "receiver": receiver, "message": message_content}

        # Emit the message to the receiver's socket (if connected)
        if receiver in users:
            emit("receive_message", payload, room=users[receiver])
    
    except Exception as e:
        logging.error(f"Error in send_message: {str(e)}")
        emit("error", {"message": "Failed to process message"}, room=request.sid)

@app.route('/get_chat_history', methods=['POST'])
def get_chat_history():
    try:
        data = request.json
        user1 = data.get('user1')
        user2 = data.get('user2')
        if not user1 or not user2:
            return jsonify({"error": "Both users required"}), 400
        messages = Message.query.filter(
            ((Message.sender == user1) & (Message.receiver == user2)) |
            ((Message.sender == user2) & (Message.receiver == user1))
        ).order_by(Message.timestamp).all()
        for msg in messages:
            if msg.receiver == user1 and not msg.is_read:
                msg.is_read = True
        db.session.commit()
        return jsonify([msg.to_dict() for msg in messages])
    except Exception as e:
        logging.error("Error getting chat history: %s", e)
        return jsonify({"error": "Failed to retrieve chat history"}), 500

@app.route("/store_personality", methods=["POST"])
def store_personality():
    data = request.json
    username = data.get("username")
    personality = data.get("personality")
    
    # Trim whitespace
    if username:
        username = username.strip()
    if personality:
        personality = personality.strip()
    
    if not username or not personality:
        return jsonify({"error": "Username and personality are required"}), 400
    
    try:
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, personality=personality)
            db.session.add(user)
        else:
            user.personality = personality
        db.session.commit()
        
        # Store the personality embedding in Pinecone
        success = store_embedding(username, personality)
        
        logging.debug(f"Stored personality for {username}: {personality}")
        return jsonify({"message": "Personality stored successfully!", "pinecone_success": success})
    except Exception as e:
        logging.error("Error storing personality: %s", e)
        return jsonify({"error": "Failed to store personality"}), 500

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        logging.info("Received request at /transcribe")
        if 'audio' not in request.files or request.files['audio'].filename == '':
            return jsonify({'error': 'No valid audio file received'}), 400
        username = request.headers.get('X-Username') or request.form.get('username')
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, personality="Default personality")
            db.session.add(user)
            db.session.commit()
        audio_file = request.files['audio']
        audio_data = BytesIO(audio_file.read())
        transcription = transcribe_audio(audio_data)
        if not transcription or transcription.startswith("Error"):
            return jsonify({'error': transcription or "Failed to transcribe audio"}), 500
        llm_response = process_transcript_with_llm(username, transcription)
        if not llm_response or llm_response.startswith("Error"):
            return jsonify({'error': llm_response or "Failed to generate AI response"}), 500
        tts_audio = text_to_speech(llm_response)
        if not tts_audio or tts_audio.startswith("Error"):
            return jsonify({'error': tts_audio or "Failed to convert text to speech"}), 500
        return jsonify({'transcription': transcription, 'llm_response': llm_response, 'tts_audio': tts_audio})
    except Exception as e:
        app.logger.error("Transcription error: %s", e)
        return jsonify({"error": f"Transcription failed: {str(e)}"}), 500

@app.errorhandler(500)
def internal_error(error):
    app.logger.error("500 error: %s", error)
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=8000, debug=True)
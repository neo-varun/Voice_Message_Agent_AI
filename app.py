import os
import time
import re
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from database_schema import db, init_db, User, Message
from pinecone_database import PineconeDatabase, store_conversation_context, update_conversation_context
from openai_api import transcribe_audio as openai_transcribe_audio, process_message, detect_contact_from_transcript, conversational_interaction, update_conversation_recipient, reset_conversation
from sqlalchemy import func
from tts_google_cloud import text_to_speech

load_dotenv()  # Load environment variables

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:2003@127.0.0.1:1234/voice_agent')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')

CORS(app)
# Optionally add a message queue for scaling: message_queue=os.getenv('REDIS_URL')
socketio = SocketIO(app, cors_allowed_origins="*")

init_db(app)
users = {}  # Maps username to session ID of active users

# Initialize database
database = PineconeDatabase()

@app.route("/")
def index():
    return redirect("/login")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route('/get_all_users', methods=['GET'])
def get_all_users():
    """Return a list of all registered users from the database."""
    try:
        all_users = User.query.all()
        user_list = [user.to_dict() for user in all_users]
        
        # Add online status to each user
        for user in user_list:
            user['is_online'] = user['username'] in users
            
        return jsonify(user_list)
    except Exception as e:
        logging.error(f"Error getting users: {str(e)}")
        return jsonify({"error": "Failed to retrieve users"}), 500

@socketio.on("connect")
def handle_connect():
    logging.debug("Client connected: %s", request.sid)

@socketio.on("disconnect")
def handle_disconnect():
    disconnected_user = next((u for u, sid in users.items() if sid == request.sid), None)
    if disconnected_user:
        del users[disconnected_user]
        # Emit updated active users to everyone
        emit_user_status()
        logging.debug("User %s disconnected", disconnected_user)

def emit_user_status():
    """Emit both active users and all users to all connected clients."""
    try:
        # Get all users from database
        all_users = User.query.all()
        user_list = [user.to_dict() for user in all_users]
        
        # Add online status to each user
        for user in user_list:
            user['is_online'] = user['username'] in users
        
        # Emit to all connected clients
        emit("user_status_update", {
            "active_users": list(users.keys()),
            "all_users": user_list
        }, broadcast=True)
    except Exception as e:
        logging.error(f"Error emitting user status: {str(e)}")

@socketio.on("join")
def handle_join(data):
    username = data.get("username")
    if username:
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username)
            db.session.add(user)
            try:
                db.session.commit()
            except Exception as e:
                logging.error("DB commit error: %s", e)
        else:
            setattr(user, '_login_update', True)
            db.session.commit()
        
        # Store the user's socket ID
        users[username] = request.sid
        
        # Emit updated user status to all clients
        emit_user_status()
        
        logging.debug("%s joined with sid %s", username, request.sid)

@socketio.on("send_message")
def handle_send_message(data):
    try:
        sender = data.get("sender")
        receiver = data.get("receiver")
        message_content = data.get("message", "")
        is_voice_message = data.get("is_voice_message", False)

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
            is_ai_response=False,
            is_voice_message=is_voice_message
        )
        db.session.add(user_message)
        db.session.commit()

        # Create a payload with the original message
        payload = {
            "sender": sender, 
            "receiver": receiver, 
            "message": message_content,
            "is_voice_message": is_voice_message
        }

        # Emit the message to the receiver's socket (if connected)
        if receiver in users:
            emit("receive_message", payload, room=users[receiver])
            
        # Also emit the message back to the sender so they can see their own messages
        if sender in users:
            emit("receive_message", payload, room=users[sender])
            
        # Store conversation context in Pinecone
        # Create a unique conversation ID using sorted usernames to ensure consistency
        participants = sorted([sender, receiver])
        conversation_id = f"{participants[0]}_{participants[1]}"
        
        # Format the message with sender info for context
        formatted_message = f"{sender}: {message_content}"
        
        # Update the conversation context in Pinecone
        update_conversation_context(
            conversation_id=conversation_id,
            new_message=formatted_message,
            participants=participants
        )
        logging.debug(f"Updated conversation context for {conversation_id}")
    
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

@app.route("/transcribe", methods=["POST"])
def handle_transcription():
    username = request.headers.get("X-Username")
    if not username:
        return jsonify({"error": "Username is required"}), 400

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    # Check if this is continuing a conversation or starting a new one
    is_continuing = request.form.get('is_continuing', 'false').lower() == 'true'
    use_name_detection = request.form.get('use_name_detection', 'false').lower() == 'true'
    
    logging.info(f"Transcription requested by {username}, use_name_detection: {use_name_detection}, is_continuing: {is_continuing}")
    
    # Create a temporary file to save the uploaded audio
    temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{username}_{time.time()}.wav")
    os.makedirs(os.path.dirname(temp_filepath), exist_ok=True)
    file.save(temp_filepath)
    logging.info(f"Audio saved to {temp_filepath}")
    
    try:
        # Transcribe the audio using OpenAI Whisper
        transcript = openai_transcribe_audio(temp_filepath)
        logging.info(f"Transcript: {transcript}")
        
        detected_receiver = None
        detection_method = "none"
        
        # Get all available contacts for this user
        all_users = User.query.all()
        available_contacts = [user.username for user in all_users if user.username != username]
        
        # Check if we already have a detected recipient from a previous interaction
        if is_continuing:
            # Get the previously detected recipient from the conversation state
            from openai_api import user_conversations
            if username in user_conversations and user_conversations[username].get("detected_recipient"):
                detected_receiver = user_conversations[username]["detected_recipient"]
                detection_method = "previous"
                logging.info(f"Using previously detected contact: {detected_receiver}")
        
        # Try to detect contact if we don't have one yet or if explicitly requested
        if (not detected_receiver and use_name_detection) or not is_continuing:
            # Try to detect the contact using OpenAI
            try:
                ai_detected_contact = detect_contact_from_transcript(
                    transcript, 
                    username, 
                    available_contacts
                )
                
                if ai_detected_contact:
                    detected_receiver = ai_detected_contact
                    detection_method = "ai"
                    logging.info(f"OpenAI detected contact: {detected_receiver}")
                    # Store the detected recipient in the conversation state
                    update_conversation_recipient(username, detected_receiver)
                else:
                    # Fallback to pattern-based detection
                    detected_receiver = detect_recipient_from_transcript(transcript, available_contacts)
                    if detected_receiver:
                        detection_method = "pattern"
                        logging.info(f"Pattern-based detection found: {detected_receiver}")
                        # Store the detected recipient in the conversation state
                        update_conversation_recipient(username, detected_receiver)
            except Exception as e:
                logging.error(f"Error in contact detection: {str(e)}")
                # Fallback to pattern-based detection
                detected_receiver = detect_recipient_from_transcript(transcript, available_contacts)
                if detected_receiver:
                    detection_method = "pattern"
                    logging.info(f"Fallback pattern-based detection found: {detected_receiver}")
                    # Store the detected recipient in the conversation state
                    update_conversation_recipient(username, detected_receiver)
        
        # Always log the detected receiver status
        logging.info(f"Final detected receiver: {detected_receiver} (method: {detection_method})")
        
        # Process the transcript with conversational AI - pass available contacts
        convo_response = conversational_interaction(username, transcript, available_contacts=available_contacts)
        
        # Delete the temporary file
        os.remove(temp_filepath)
        
        # Convert the response to speech using Google TTS
        voice_gender = request.form.get('voice_gender', 'FEMALE')
        
        # Return the result - different response based on whether the conversation is ready
        if convo_response["ready_to_send"]:
            response_message = "Your message is ready to send."
            is_final = True
            
            # Use the stored recipient from the conversation if available
            if convo_response["detected_recipient"] and not detected_receiver:
                detected_receiver = convo_response["detected_recipient"]
                logging.info(f"Using conversation recipient: {detected_receiver}")
            
            # If we still don't have a recipient, we need to alert the user
            if not detected_receiver:
                logging.warning("No recipient detected for message that's ready to send")
            
            # Generate speech for the final state
            audio_response = text_to_speech(response_message, voice_gender=voice_gender)
            
            # Reset the conversation for this user
            reset_conversation(username)
        else:
            # If not ready, send a follow-up question
            response_message = convo_response["response"]
            is_final = False
            
            # Generate speech for the response
            audio_response = text_to_speech(response_message, voice_gender=voice_gender)
            
            # Always prefer the detected recipient from the conversation response
            if convo_response["detected_recipient"]:
                detected_receiver = convo_response["detected_recipient"]
                logging.info(f"Updated recipient from conversation: {detected_receiver}")
        
        # Construct and return the response
        response_data = {
            "transcript": transcript,
            "response": response_message,
            "audio_response": audio_response,
            "detected_receiver": detected_receiver,
            "detection_method": detection_method,
            "is_final": is_final
        }
        
        # Add final_message to the response data if available
        if is_final and convo_response["final_message"]:
            response_data["final_message"] = convo_response["final_message"]
        
        logging.info(f"Returning transcription response with audio")
        return jsonify(response_data)
    
    except Exception as e:
        logging.error(f"Error in transcription: {str(e)}")
        # Ensure we clean up the temp file
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        return jsonify({"error": str(e)}), 500

def detect_recipient_from_transcript(transcript, available_contacts):
    """
    Use a pattern-based approach to detect a recipient from the transcript.
    
    Args:
        transcript (str): The transcribed text
        available_contacts (list): List of available contacts
        
    Returns:
        str or None: The detected recipient username, or None if no recipient was detected
    """
    if not transcript:
        return None
        
    # Convert to lowercase for case-insensitive matching
    transcript_lower = transcript.lower()
    
    # Common patterns for detecting recipients in relay messages
    patterns = [
        r"tell\s+(\w+)",
        r"ask\s+(\w+)",
        r"let\s+(\w+)\s+know",
        r"inform\s+(\w+)",
        r"message\s+(\w+)",
        r"send\s+to\s+(\w+)",
        r"contact\s+(\w+)",
        r"check\s+with\s+(\w+)",
        r"relay\s+to\s+(\w+)",
        r"forward\s+to\s+(\w+)",
        r"pass\s+to\s+(\w+)",
        r"communicate\s+to\s+(\w+)",
        r"for\s+(\w+)[\s:,]"
    ]
    
    # Try each pattern
    for pattern in patterns:
        matches = re.findall(pattern, transcript_lower)
        if matches:
            candidate = matches[0]
            # Check if candidate is in available contacts (case-insensitive)
            for contact in available_contacts:
                if contact.lower() == candidate.lower():
                    return contact
    
    return None

@app.route('/get_tts', methods=['POST'])
def get_tts():
    """Convert text to speech using Google Cloud TTS and return as base64"""
    try:
        data = request.json
        text = data.get('text')
        voice_gender = data.get('voice_gender', 'FEMALE')
        
        if not text:
            return jsonify({"error": "No text provided"}), 400
            
        # Use the Google Cloud TTS function to convert text to speech
        audio_base64 = text_to_speech(text, voice_gender=voice_gender)
        
        return jsonify({"audio": audio_base64})
    except Exception as e:
        logging.error(f"Error in TTS conversion: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(500)
def internal_error(error):
    app.logger.error("500 error: %s", error)
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=8000, debug=True)
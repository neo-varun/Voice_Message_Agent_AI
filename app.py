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
from openai_api import transcribe_audio as openai_transcribe_audio, process_message, detect_contact_from_transcript
from sqlalchemy import func

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
    
    use_name_detection = request.form.get('use_name_detection', 'false').lower() == 'true'
    logging.info(f"Transcription requested by {username}, use_name_detection: {use_name_detection}")
    
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
        
        # Use the selected method for detecting the recipient
        if use_name_detection:
            # Get all available contacts for this user from the database
            all_users = User.query.all()
            available_contacts = [user.username for user in all_users if user.username != username]
            
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
                else:
                    # Fallback to pattern-based detection
                    detected_receiver = detect_recipient_from_transcript(transcript, available_contacts)
                    if detected_receiver:
                        detection_method = "pattern"
                        logging.info(f"Pattern-based detection found: {detected_receiver}")
            except Exception as e:
                logging.error(f"Error in contact detection: {str(e)}")
                # Fallback to pattern-based detection
                detected_receiver = detect_recipient_from_transcript(transcript, available_contacts)
                if detected_receiver:
                    detection_method = "pattern"
                    logging.info(f"Fallback pattern-based detection found: {detected_receiver}")
        
        # Process the transcript with OpenAI
        response = process_message(
            transcript, 
            username, 
            detected_receiver if detected_receiver else None
        )
        
        # Delete the temporary file
        os.remove(temp_filepath)
        
        # Return the result
        return jsonify({
            "transcript": transcript,
            "response": response,
            "detected_receiver": detected_receiver,
            "detection_method": detection_method
        })
    
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

@app.errorhandler(500)
def internal_error(error):
    app.logger.error("500 error: %s", error)
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found"}), 404

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=8000, debug=True)
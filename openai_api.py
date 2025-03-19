import os
import logging
from openai import OpenAI
from pinecone_database import retrieve_relevant_contexts
from database_schema import User
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def validate_contact(detected_name, available_contacts):
    """
    Validate a detected contact name against the list of available contacts.
    Performs case-insensitive matching and returns the correctly-cased contact name.
    
    Args:
        detected_name (str): The detected contact name
        available_contacts (list): List of available contact names
        
    Returns:
        str or None: The validated contact name with correct casing, or None if no match
    """
    if not detected_name or not available_contacts:
        return None
        
    # Normalize the detected name (lowercase, strip whitespace)
    normalized_name = detected_name.lower().strip()
    
    # Check for exact match first (case insensitive)
    for contact in available_contacts:
        if contact.lower().strip() == normalized_name:
            return contact  # Return the correctly cased version
    
    # No exact match found
    return None

def detect_contact_from_transcript(transcript, sender_username, available_contacts):
    """
    Use OpenAI to detect a contact name from a transcript.
    
    Args:
        transcript (str): The voice message transcript
        sender_username (str): Username of the sender
        available_contacts (list): List of available contact usernames
        
    Returns:
        str or None: Detected contact name, or None if no contact detected
    """
    if not transcript or transcript.strip() == "":
        logging.warning("Empty transcript provided for contact detection")
        return None
        
    if not available_contacts or len(available_contacts) == 0:
        logging.warning("No available contacts provided for detection")
        return None
    
    logging.info(f"Detecting contact from transcript: '{transcript}'")
    logging.info(f"Available contacts: {available_contacts}")
    
    try:
        # Format available contacts as a comma-separated list
        contacts_str = ", ".join(available_contacts)
        
        # Create a prompt for OpenAI to detect a contact name
        prompt = f"""
        Analyze this message: "{transcript}"
        
        Determine if the message is intended for a specific contact from this list: {contacts_str}
        
        Rules:
        1. If a contact name is clearly mentioned (e.g., "Tell John..." or "Ask Sarah...", "Hey Mike,..."), extract ONLY that name.
        2. Look specifically for relay patterns like "tell X", "ask X", "let X know", "check with X", etc.
        3. Return ONLY the exact name from the provided list that matches.
        4. If multiple contacts are mentioned, return the primary recipient only.
        5. If no contact is clearly identified as the intended recipient or you're uncertain, return "NONE".
        
        Return ONLY the contact name or "NONE" with no additional text.
        """
        
        # Call OpenAI API to analyze the transcript
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You extract contact names from messages. Return ONLY the name or NONE."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.0
        )
        
        # Extract the detected contact name
        detected_name = response.choices[0].message.content.strip()
        logging.info(f"OpenAI detected: '{detected_name}'")
        
        # If OpenAI says "NONE", return None
        if detected_name.upper() == "NONE":
            return None
            
        # Validate the detected name against available contacts
        validated_contact = validate_contact(detected_name, available_contacts)
        
        if validated_contact:
            logging.info(f"Validated contact: '{validated_contact}'")
            return validated_contact
        else:
            logging.warning(f"Detected name '{detected_name}' didn't match any available contacts")
            return None
            
    except Exception as e:
        logging.error(f"Error in contact detection: {str(e)}")
        return None

def generate_response(username, message, receiver=None):
    """Generate an AI response with conversation context"""
    # Get conversation context if available
    conversation_context = ""
    if receiver:
        # Retrieve context
        contexts = retrieve_relevant_contexts(
            query_text=message,
            user1=username,
            user2=receiver,
            top_k=1
        )
        if contexts:
            conversation_context = contexts[0]['text']
    
    # Build simplified prompt
    if conversation_context:
        prompt = f"Context: {conversation_context}\n{username}'s message: {message}\nRespond as {username} to {receiver}: "
    else:
        prompt = f"{username}'s message: {message}\nRespond as {username}: "
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": f"You are {username}'s assistant. Be concise and friendly."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI API Error: {str(e)}")
        return "I'm having trouble understanding right now."

def process_transcript_with_llm(username, transcript, receiver=None):
    """Process a transcript using the LLM"""
    try:
        return generate_response(username, transcript, receiver)
    except Exception as e:
        logging.error(f"Error processing transcript: {str(e)}")
        return "Sorry, I encountered an issue processing your request."

def transcribe_audio(audio_file_path):
    """
    Transcribe an audio file using OpenAI's Whisper model.
    
    Args:
        audio_file_path (str): Path to the audio file
        
    Returns:
        str: The transcribed text
    """
    try:
        logging.info(f"Transcribing audio file: {audio_file_path}")
        
        # Open the audio file
        with open(audio_file_path, "rb") as audio_file:
            # Call the OpenAI API to transcribe the audio
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            
        # Return the transcribed text
        logging.info(f"Transcription completed: {transcript.text[:50]}...")
        return transcript.text
        
    except Exception as e:
        logging.error(f"Error transcribing audio: {str(e)}")
        raise

def process_message(transcript, sender_username, receiver_username=None):
    """
    Process a message with OpenAI to generate a response.
    
    Args:
        transcript (str): The message transcript
        sender_username (str): Username of the sender
        receiver_username (str, optional): Username of the receiver
        
    Returns:
        str: The generated response
    """
    try:
        # Check if this seems like a relay message
        relay_patterns = [
            "tell", "ask", "let", "inform", "message", 
            "send to", "contact", "check with", "relay to",
            "pass", "communicate", "for"
        ]
        
        is_likely_relay = False
        lower_transcript = transcript.lower()
        
        for pattern in relay_patterns:
            if pattern in lower_transcript and receiver_username:
                is_likely_relay = True
                break
        
        # Create appropriate prompt based on message type
        if is_likely_relay:
            prompt = f"""
            You are an assistant helping relay messages between users.

            User {sender_username} has sent a message that appears to be intended for {receiver_username}.
            
            Original message: "{transcript}"
            
            Reformulate this as a relay message from {sender_username} to {receiver_username}.
            
            ALWAYS start with "Hey, {sender_username}" and then rewrite the message as a relay.
            For example:
            - If original is "Tell John I'll be at Vesapur on Monday", respond with "Hey, [sender] wanted me to let you know they'll be at Vesapur on Monday"
            - If original is "Ask Sarah if she has the documents", respond with "Hey, [sender] wants to know if you have the documents"
            
            Keep your response conversational, concise, and natural. Don't add any AI-related text.
            """
        else:
            prompt = f"""
            You are an assistant helping with a voice messaging app.

            User {sender_username} has sent a direct message to {receiver_username if receiver_username else "someone"}.
            
            Original message: "{transcript}"
            
            Convert this into a natural-sounding message. You should keep the same meaning but make it sound more polished.
            Do not add any AI-related phrases or mentions of being an assistant.
            
            Examples:
            - Original: "tell her I'll meet at 5" → "I'll meet you at 5"
            - Original: "going to the store need anything" → "I'm going to the store. Do you need anything?"
            
            Keep your response concise and conversational.
            """
        
        # Call OpenAI API to generate a response
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that relays messages between users in a natural way."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        # Extract the generated response
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")
        return f"Error processing message: {str(e)}"
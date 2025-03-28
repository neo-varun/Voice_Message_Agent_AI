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

# Conversational system prompt
SYSTEM_PROMPT = 'Voice assistant speaking fluent English. IMPORTANT: Outputs will be spoken aloud, so never use asterisks (*,-) or any text formatting. Use natural words, be warm, ask follow-up questions, reference previous exchanges. ALWAYS respond in English only, regardless of the input language.'

# Dictionary to store conversation state for users
user_conversations = {}

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
    """Detect a contact name from a transcript using AI."""
    if not transcript or not available_contacts:
        return None
    
    logging.info(f"Detecting contact from transcript: '{transcript}'")
    
    try:
        prompt = f"Message: \"{transcript}\"\nAvailable contacts: {', '.join(available_contacts)}\nExtract ONLY the recipient name from the list of contacts or respond with NONE."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": "Extract the recipient name mentioned in the message. Only respond with a name from the provided contacts list or NONE. ALWAYS respond in English only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=20,
            temperature=0.0
        )
        
        detected_name = response.choices[0].message.content.strip()
        logging.info(f"AI detected contact: '{detected_name}'")
        
        if detected_name.upper() == "NONE":
            return None
        
        # Match against available contacts (case-insensitive)
        for contact in available_contacts:
            if contact.lower() == detected_name.lower():
                return contact
                
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
    """Transcribe an audio file using OpenAI's Whisper model."""
    try:
        logging.info(f"Transcribing audio file: {audio_file_path}")
        
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            
        logging.info(f"Transcription completed: {transcript.text[:50]}...")
        return transcript.text
        
    except Exception as e:
        logging.error(f"Error transcribing audio: {str(e)}")
        raise

def process_message(transcript, sender_username, receiver_username=None):
    """Process a message with OpenAI to generate a response."""
    try:
        # All messages will now be formatted in the relay style
        # Format: "Hey [recipient]!, [sender] wants to inform u that..."
        prompt = f"Message from {sender_username} to {receiver_username}: \"{transcript}\"\nRewrite as: \"Hey {receiver_username}!, {sender_username} wants to inform u that...\""
        
        # Call OpenAI API to generate a response
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Format messages as: Hey [recipient]!, [sender] wants to inform u that..."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")
        return f"Hey {receiver_username}!, {sender_username} wants to inform u that {transcript}"

def conversational_interaction(user_id, user_message, available_contacts=None):
    """Process a message in a conversational manner, with follow-up questions and contact detection."""
    # Initialize or retrieve conversation state
    if user_id not in user_conversations:
        user_conversations[user_id] = {
            "history": [],
            "ready_to_send": False,
            "detected_recipient": None,
            "final_message": None,
            "turns": 0
        }
    
    conversation = user_conversations[user_id]
    
    # Add the user's message to history
    conversation["history"].append({"role": "user", "content": user_message})
    conversation["turns"] += 1
    
    # Check for contacts if none detected yet
    if not conversation["detected_recipient"] and available_contacts:
        detected_contact = detect_contact_from_transcript(
            user_message,
            user_id,
            available_contacts
        )
        if detected_contact:
            logging.info(f"Contact detected: {detected_contact}")
            conversation["detected_recipient"] = detected_contact
    
    # Check if this is a "send now" message
    send_keywords = ["send", "send it", "that's it", "done", "go ahead"]
    if any(keyword in user_message.lower() for keyword in send_keywords) and conversation["turns"] > 2:
        conversation["ready_to_send"] = True
        final_message = generate_final_message(conversation["history"], user_id, conversation["detected_recipient"])
        conversation["final_message"] = final_message
        
        return {
            "response": "Sending your message now.",
            "ready_to_send": True,
            "final_message": final_message,
            "detected_recipient": conversation["detected_recipient"]
        }
    
    # Determine appropriate system prompt based on conversation stage
    recipient_info = f" to {conversation['detected_recipient']}" if conversation["detected_recipient"] else ""
    
    if conversation["turns"] <= 2:
        # Initial stages - ask for details
        system_content = f"You are helping compose a voice message{recipient_info}. Ask a specific follow-up question to gather more details for the message. ALWAYS respond in English only."
    elif conversation["turns"] == 3:
        # Middle stage - gather final details
        system_content = f"You are helping compose a voice message{recipient_info}. Ask ONE more specific question about details like time, place, or context. ALWAYS respond in English only."
    else:
        # Final stage - ask for confirmation
        system_content = f"You are helping compose a voice message{recipient_info}. Ask the user if they're ready to send or want to add anything else. ALWAYS respond in English only."
    
    # Create messages for API call
    messages = [
        {"role": "system", "content": system_content}
    ]
    messages.extend(conversation["history"])
    
    try:
        # Call OpenAI API for a response
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        
        # Add assistant response to conversation history
        assistant_message = response.choices[0].message.content.strip()
        conversation["history"].append({"role": "assistant", "content": assistant_message})
        
        # Check if max turns reached
        if conversation["turns"] >= 5:
            conversation["ready_to_send"] = True
            final_message = generate_final_message(conversation["history"], user_id, conversation["detected_recipient"])
            conversation["final_message"] = final_message
        
        return {
            "response": assistant_message,
            "ready_to_send": conversation["ready_to_send"],
            "final_message": conversation["final_message"],
            "detected_recipient": conversation["detected_recipient"]
        }
    
    except Exception as e:
        logging.error(f"Error in conversation: {str(e)}")
        return {
            "response": "I'm having trouble processing your request.",
            "ready_to_send": False,
            "final_message": None,
            "detected_recipient": conversation["detected_recipient"]
        }

def generate_final_message(conversation_history, user_id, recipient=None):
    """Generate a final message from conversation history."""
    try:
        # Extract user messages
        user_inputs = [msg["content"] for msg in conversation_history if msg["role"] == "user"]
        
        # Filter out confirmation phrases from the last message only if it appears to be just a confirmation
        send_phrases = ["send", "send it", "send now", "confirm", "yes", "that's it", 
                        "yeah that's it", "yeah send it", "that's good", "looks good", 
                        "yes, send the message", "yes send the message", "send the message"]
        
        # Check if the last message is just a confirmation
        if user_inputs and len(user_inputs) > 1:
            last_message = user_inputs[-1].lower()
            is_short = len(last_message.split()) <= 5
            has_confirmation = any(phrase in last_message for phrase in send_phrases)
            
            if is_short and has_confirmation:
                # Remove the last message if it's just a confirmation
                user_inputs = user_inputs[:-1]
        
        # Combine all remaining user messages
        combined_input = " ".join(user_inputs)
        
        # Create prompt based on whether recipient is known
        if recipient:
            prompt = f"""
You are creating a concise, well-formatted message based on the user's conversation history.

User conversation history: {combined_input}

Your task:
1. Create a message from {user_id} to {recipient} using EXACTLY this format: "Hey {recipient}!, {user_id} wants to inform u that..."
2. Include all important details from the conversation
3. Summarize the message coherently and conversationally
4. Retain the original intent and core information
5. Keep the message natural and fluent
6. DO NOT include any phrases like "send it", "that's it", or any confirmation phrases
7. IMPORTANT: ALWAYS respond in English only, regardless of input language

FORMAT REQUIRED: "Hey {recipient}!, {user_id} wants to inform u that [coherent message about what {user_id} wants to communicate]"
"""
        else:
            prompt = f"""
You are creating a concise, well-formatted message based on the user's conversation history.

User conversation history: {combined_input}

Your task:
1. Create a clear first-person message summarizing what the user wants to say
2. Include all important details from the conversation
3. Make the message coherent and conversational 
4. Remove any AI assistant questions
5. Keep the message natural and fluent
6. DO NOT include any phrases like "send it", "that's it", or any confirmation phrases
7. IMPORTANT: ALWAYS respond in English only, regardless of input language
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": "You are a helpful message formatting assistant that creates coherent summaries from conversations. ALWAYS write in English only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        message = response.choices[0].message.content.strip()
        
        # Ensure proper format if recipient is specified
        if recipient and not message.startswith(f"Hey {recipient}!"):
            # Try to extract any useful information from the AI response
            content_part = message
            if "wants to inform" in message:
                content_part = message.split("wants to inform")[1].strip()
                if content_part.startswith("u that "):
                    content_part = content_part[7:].strip()
                elif content_part.startswith("you that "):
                    content_part = content_part[10:].strip()
            
            # If we couldn't extract useful info, fall back to the combined input
            if not content_part or content_part == message:
                content_part = combined_input
                
            message = f"Hey {recipient}!, {user_id} wants to inform u that {content_part}"
        
        logging.info(f"Generated message: {message[:100]}...")
        return message
    
    except Exception as e:
        logging.error(f"Error generating final message: {str(e)}")
        # Fallback to the last user message
        if recipient:
            return f"Hey {recipient}!, {user_id} wants to inform u that I need to speak with you."
        
        return user_inputs[-1] if user_inputs else "I wanted to send you a message."

def update_conversation_recipient(user_id, recipient):
    """Update the detected recipient for a user's conversation"""
    if user_id in user_conversations:
        user_conversations[user_id]["detected_recipient"] = recipient
    else:
        user_conversations[user_id] = {
            "history": [],
            "ready_to_send": False,
            "detected_recipient": recipient,
            "final_message": None,
            "turns": 0
        }

def reset_conversation(user_id):
    """Reset a user's conversation state"""
    if user_id in user_conversations:
        del user_conversations[user_id]
import logging
import psycopg2
from psycopg2 import sql
from openai import OpenAI

# OpenAI client
client = OpenAI()

logging.basicConfig(level=logging.ERROR)

def get_db_connection():
    """Securely create and return a database connection."""
    return psycopg2.connect(dbname='postgres', user='postgres', password='2003', host='127.0.0.1',port='1234')

def get_user_personality(username):
    """Retrieve stored personality traits for a user securely."""
    if not username.isalnum():  # Basic sanitization
        return None

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql.SQL("SELECT personality FROM users WHERE username = %s"), (username,))
            result = cursor.fetchone()
            return result[0] if result else None

def generate_personalized_response(username, message):
    """Generate AI response tailored to user's personality."""
    user_personality = get_user_personality(username)

    if not user_personality:
        return "I don't know much about you yet. Tell me about yourself!"

    full_context = f"User's Personality: {user_personality}\nUser's Message: {message}\nAI Response:"

    try:
        ai_response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": "Respond in the user's style."},
                {"role": "user", "content": full_context}
            ],
            temperature=0.6,
            max_tokens=min(500, len(message) * 3)
        )
        return ai_response.choices[0].message.content.strip()
    
    except Exception as e:
        logging.error(f"OpenAI API Error: {str(e)}")
        return "I'm having trouble understanding right now. Try again later."

def process_transcript_with_llm(username: str, transcript: str) -> str:
    """Process a user's transcript using OpenAI with personalized context."""
    try:
        return generate_personalized_response(username, transcript)
    
    except Exception as e:
        logging.error(f"Error processing transcript: {str(e)}")
        return "Sorry, I encountered an issue processing your request."
import logging
import psycopg2
from psycopg2 import sql
import re
from openai import OpenAI

# Create an instance of the OpenAI client.
client = OpenAI()

logging.basicConfig(level=logging.DEBUG)

def get_db_connection():
    """
    Securely create and return a database connection.
    Here, the database name is 'voice_agent' (ensure it exists).
    """
    return psycopg2.connect(
        dbname='voice_agent',
        user='postgres',
        password='2003',
        host='127.0.0.1',
        port='1234'
    )

def is_valid_username(username):
    """
    Validate the username.
    This allows letters, numbers, underscores, hyphens, and periods.
    """
    return re.match(r'^[\w\.-]+$', username) is not None

def get_user_personality(username):
    """
    Retrieve the stored personality for a user securely from the 'users' table.
    Logs the username being retrieved and returns the personality value if found.
    """
    logging.debug(f"Retrieving personality for username: '{username}'")
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            query = sql.SQL("SELECT personality FROM users WHERE username = %s")
            cursor.execute(query, (username,))
            result = cursor.fetchone()
            if result:
                logging.debug(f"Retrieved personality for {username}: {result[0]}")
                return result[0]
            else:
                logging.debug(f"No personality found for user: {username}")
            return None

def generate_personalized_response(username, message):
    """
    Generate an AI response tailored to the user's personality and conversation context.
    
    The assistant is instructed to rephrase the user's message into a direct, friendly query
    on behalf of the user. The expected output should begin with a greeting like:
      "Hey [Recipient], [username] wants to know if ..."
    
    In this version, the user's message is inserted without surrounding double quotes.
    """
    # Retrieve the user's personality from the database.
    user_personality = get_user_personality(username)
    if not user_personality:
        return "I don't know much about you yet. Tell me about yourself!"
    
    # Construct a clear and concise prompt without double quotes around the message.
    full_context = (
        f"You are {username}'s assistant. {username}'s personality is: {user_personality}.\n"
        f"{username} says: {message}\n"
        "Rephrase this message into a direct, friendly query addressed to the recipient. "
        "The output should start with 'Hey [Recipient], {username} wants to know if ...'."
    )
    
    try:
        ai_response = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": f"You are a friendly and clear voice assistant representing {username}."},
                {"role": "user", "content": full_context}
            ],
            temperature=0.6,
            max_tokens=150
        )
        return ai_response.choices[0].message.content.strip()
    
    except Exception as e:
        logging.error(f"OpenAI API Error: {str(e)}")
        return "I'm having trouble understanding right now. Try again later."

def process_transcript_with_llm(username: str, transcript: str) -> str:
    """
    Process a user's transcript using OpenAI with personalized context.
    Delegates processing to generate_personalized_response.
    """
    try:
        return generate_personalized_response(username, transcript)
    except Exception as e:
        logging.error(f"Error processing transcript: {str(e)}")
        return "Sorry, I encountered an issue processing your request."
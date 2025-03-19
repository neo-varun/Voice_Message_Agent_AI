import os
from pinecone import Pinecone, ServerlessSpec
import logging

# Initialize Pinecone instance
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Define a valid Pinecone index name
INDEX_NAME = "conversation-contexts"  # Must be lowercase and use hyphens

# Ensure the index exists
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

pinecone_index = pc.Index(INDEX_NAME)

def get_embedding(text):
    """Convert text to embedding vector using OpenAI."""
    from openai import OpenAI
    client = OpenAI()
    response = client.embeddings.create(model="text-embedding-ada-002", input=text)
    return response.data[0].embedding

def store_conversation_context(conversation_id, context_text, metadata=None):
    """
    Store conversation context in Pinecone to improve AI response relevance.
    
    Args:
        conversation_id: A unique identifier for the conversation (e.g., "user1_user2")
        context_text: The conversation text to embed and store
        metadata: Additional information about the conversation
    
    Returns:
        Boolean indicating success
    """
    try:
        # Generate embedding for the conversation context
        vector = get_embedding(context_text)
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        metadata["text"] = context_text
        metadata["timestamp"] = str(metadata.get("timestamp", ""))
        metadata["participants"] = metadata.get("participants", [])
        
        print(f"Storing conversation context for {conversation_id}")
        
        # Include metadata as a separate parameter
        pinecone_index.upsert(
            vectors=[(conversation_id, vector)],
            metadata={conversation_id: metadata}
        )
        return True
    except Exception as e:
        print(f"Error storing conversation context: {e}")
        return False

def retrieve_relevant_contexts(query_text, user1=None, user2=None, top_k=3):
    """
    Retrieve relevant conversation contexts based on semantic similarity.
    
    Args:
        query_text: The current message or conversation to find relevant contexts for
        user1, user2: Optional filter for conversation participants
        top_k: Number of relevant contexts to retrieve
    
    Returns:
        List of relevant context texts
    """
    try:
        # Generate embedding for the query
        query_vector = get_embedding(query_text)
        
        # Query Pinecone for similar conversation contexts
        query_response = pinecone_index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True
        )
        
        relevant_contexts = []
        
        if hasattr(query_response, 'matches') and query_response.matches:
            for match in query_response.matches:
                if hasattr(match, 'metadata') and match.metadata:
                    # Filter by participants if specified
                    if user1 and user2:
                        participants = match.metadata.get('participants', [])
                        if user1 not in participants or user2 not in participants:
                            continue
                    
                    # Add the context text to the list
                    if 'text' in match.metadata:
                        relevant_contexts.append({
                            'text': match.metadata['text'],
                            'score': match.score
                        })
        
        return relevant_contexts
    
    except Exception as e:
        print(f"Error retrieving conversation contexts: {e}")
        return []

def update_conversation_context(conversation_id, new_message, participants):
    """
    Update an existing conversation context with a new message
    
    Args:
        conversation_id: The unique conversation identifier
        new_message: The new message to add to the context
        participants: List of participants in the conversation
    
    Returns:
        Boolean indicating success
    """
    try:
        # First try to fetch the existing context
        fetch_response = pinecone_index.fetch(ids=[conversation_id])
        
        existing_context = ""
        if hasattr(fetch_response, 'vectors') and conversation_id in fetch_response.vectors:
            if hasattr(fetch_response.vectors[conversation_id], 'metadata'):
                metadata = fetch_response.vectors[conversation_id].metadata
                if metadata is not None:
                    existing_context = metadata.get('text', '')
        
        # Append the new message to the existing context
        updated_context = f"{existing_context}\n{new_message}".strip()
        
        # Store the updated context
        return store_conversation_context(
            conversation_id=conversation_id,
            context_text=updated_context,
            metadata={
                "participants": participants,
                "timestamp": str(import_datetime().utcnow())
            }
        )
    
    except Exception as e:
        print(f"Error updating conversation context: {str(e)}")
        return False

def import_datetime():
    """Helper to import datetime"""
    from datetime import datetime
    return datetime

class PineconeDatabase:
    def __init__(self):
        # Initialize Pinecone connection
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "voice-agent-index")
        
    def get_all_users(self):
        """
        Get all users from the database
        
        Returns:
            list: List of user dictionaries with username field
        """
        try:
            # In a real implementation, this would query Pinecone or another database
            # For demonstration, we'll query the SQLAlchemy database
            from database_schema import User
            users = User.query.all()
            return [{"username": user.username} for user in users]
        except Exception as e:
            logging.error(f"Error getting users: {str(e)}")
            return []
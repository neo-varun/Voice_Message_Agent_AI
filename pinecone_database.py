import os
from pinecone import Pinecone, ServerlessSpec

# Initialize Pinecone instance
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Define a valid Pinecone index name
INDEX_NAME = "user-profiles"  # Must be lowercase and use hyphens

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

def store_embedding(username, personality):
    """Store user personality in Pinecone."""
    try:
        vector = get_embedding(personality)
        
        # Store with explicit metadata
        metadata = {"text": personality}
        print(f"Storing embedding for {username} with metadata: {metadata}")
        
        # Include metadata as a separate parameter
        pinecone_index.upsert(
            vectors=[(username, vector)],
            metadata={username: metadata}
        )
        return True
    except Exception as e:
        print(f"Error storing embedding: {e}")
        return False

def retrieve_personality(username):
    """Retrieve user personality traits from Pinecone."""
    try:
        # First try direct fetch by ID
        fetch_response = pinecone_index.fetch(ids=[username])
        print(f"Fetch response for {username}: {fetch_response}")
        
        if hasattr(fetch_response, 'vectors') and username in fetch_response.vectors:
            print(f"Found vector for {username}")
            vector_data = fetch_response.vectors[username]
            
            if hasattr(vector_data, 'metadata') and vector_data.metadata:
                print(f"Found metadata: {vector_data.metadata}")
                if 'text' in vector_data.metadata:
                    return vector_data.metadata['text']
            
            # Fallback to a query if metadata format is different
            embedding = get_embedding(username)
            query_response = pinecone_index.query(
                vector=embedding,
                top_k=1,
                include_metadata=True
            )
            
            print(f"Query response: {query_response}")
            
            if hasattr(query_response, 'matches') and query_response.matches:
                match = query_response.matches[0]
                if hasattr(match, 'metadata') and 'text' in match.metadata:
                    return match.metadata['text']
        
        # If all fails, check database
        import psycopg2
        conn = psycopg2.connect(dbname='postgres', user='postgres', password='2003', host='127.0.0.1',port='1234')
        cursor = conn.cursor()
        cursor.execute("SELECT personality FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result[0] if result else "Default personality"
    
    except Exception as e:
        print(f"Error retrieving personality: {e}")
        return "Default personality"
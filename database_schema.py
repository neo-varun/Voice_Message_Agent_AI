from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Index, event
import psycopg2

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender_user', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver_user', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    sender = db.Column(db.String(100), nullable=False)
    receiver = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_ai_response = db.Column(db.Boolean, default=False)
    is_voice_message = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender,
            'receiver': self.receiver,
            'content': self.content,
            'is_ai_response': self.is_ai_response,
            'is_voice_message': self.is_voice_message,
            'is_read': self.is_read,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }

# Create indexes for performance
Index('idx_message_participants', Message.sender_id, Message.receiver_id)
Index('idx_message_timestamp', Message.timestamp)
Index('idx_username', User.username)

def init_db(app):
    """Initialize database with SQLAlchemy through Flask app context"""
    db.init_app(app)
    with app.app_context():
        try:
            db.create_all()
            print("Database initialized successfully.")
        except Exception as e:
            print("Error initializing database:", e)

def initialize_raw_database(dbname='voice_agent', user='postgres', password='2003', host='127.0.0.1', port='1234'):
    """
    Initialize or reset the database using direct PostgreSQL connection.
    WARNING: This will reset database tables and delete existing data.
    Only use during development or initial setup.
    """
    # Connect to postgres to create our application database
    conn = psycopg2.connect(dbname='postgres', user=user, password=password, host=host, port=port)
    conn.autocommit = True
    cursor = conn.cursor()

    # Create database if not exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'")
    if not cursor.fetchone():
        cursor.execute(f"CREATE DATABASE {dbname}")
        print(f"Database '{dbname}' created.")
    
    cursor.close()
    conn.close()

    # Connect to our application database
    conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Drop tables to reset (DANGEROUS in production!)
    print("WARNING: Dropping all tables and resetting data.")
    cursor.execute("DROP TABLE IF EXISTS messages")
    cursor.execute("DROP TABLE IF EXISTS users")
    
    # Create tables (simple schema, SQLAlchemy will manage the details)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            name VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            sender_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            receiver_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            sender VARCHAR(100) NOT NULL,
            receiver VARCHAR(100) NOT NULL,
            content TEXT NOT NULL,
            is_ai_response BOOLEAN DEFAULT FALSE,
            is_voice_message BOOLEAN DEFAULT FALSE,
            is_read BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_participants ON messages(sender_id, receiver_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_timestamp ON messages(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_username ON users(username)")
    
    # Reset sequences
    cursor.execute("ALTER SEQUENCE users_id_seq RESTART WITH 1")
    cursor.execute("ALTER SEQUENCE messages_id_seq RESTART WITH 1")
    
    conn.commit()
    cursor.close()
    conn.close()

    print("Database and tables initialized with reset state.")

@event.listens_for(User, 'before_update')
def before_update(mapper, connection, target):
    if getattr(target, '_login_update', False):
        target.last_login = datetime.utcnow()
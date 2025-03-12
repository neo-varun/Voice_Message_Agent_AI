from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Index, event

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    personality = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender_user', lazy='dynamic')
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver_user', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'personality': self.personality,
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
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender,
            'receiver': self.receiver,
            'content': self.content,
            'is_ai_response': self.is_ai_response,
            'is_read': self.is_read,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }

# Create indexes for performance
Index('idx_message_participants', Message.sender_id, Message.receiver_id)
Index('idx_message_timestamp', Message.timestamp)
Index('idx_username', User.username)

def init_db(app):
    db.init_app(app)
    with app.app_context():
        try:
            db.create_all()
            print("Database initialized successfully.")
        except Exception as e:
            print("Error initializing database:", e)

@event.listens_for(User, 'before_update')
def before_update(mapper, connection, target):
    if getattr(target, '_login_update', False):
        target.last_login = datetime.utcnow()
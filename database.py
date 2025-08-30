import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logger = logging.getLogger(__name__)

# Database setup: use a local SQLite DB file (no env vars required)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "maveli.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False allows usage across threads (e.g., TeleBot handlers)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True)  # Telegram user ID
    username = Column(String(50), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    message_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, index=True)  # Telegram user ID
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    audio_generated = Column(Boolean, default=False)
    language_detected = Column(String(10), nullable=True)

class BotStats(Base):
    __tablename__ = "bot_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    total_messages = Column(Integer, default=0)
    successful_responses = Column(Integer, default=0)
    failed_responses = Column(Integer, default=0)
    audio_generations = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)

# Create tables
Base.metadata.create_all(bind=engine)

class DatabaseManager:
    def __init__(self):
        self.engine = engine
        
    def get_session(self):
        return SessionLocal()
    
    def create_or_update_user(self, user_id: int, username: str = None, 
                            first_name: str = None, last_name: str = None) -> bool:
        """Create or update user information"""
        try:
            session = self.get_session()
            
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                # Update existing user
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.last_seen = datetime.utcnow()
                user.message_count += 1
            else:
                # Create new user
                user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    message_count=1
                )
                session.add(user)
            
            session.commit()
            session.close()
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error creating/updating user: {e}")
            if 'session' in locals():
                session.rollback()
                session.close()
            return False
    
    def save_conversation(self, user_id: int, user_message: str, bot_response: str,
                         response_time_ms: int = None, audio_generated: bool = False,
                         language_detected: str = None) -> bool:
        """Save a conversation to the database"""
        try:
            session = self.get_session()
            
            conversation = Conversation(
                user_id=user_id,
                user_message=user_message,
                bot_response=bot_response,
                response_time_ms=response_time_ms,
                audio_generated=audio_generated,
                language_detected=language_detected
            )
            
            session.add(conversation)
            session.commit()
            session.close()
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error saving conversation: {e}")
            if 'session' in locals():
                session.rollback()
                session.close()
            return False
    
    def get_user_conversation_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history for a user"""
        try:
            session = self.get_session()
            
            conversations = session.query(Conversation)\
                .filter(Conversation.user_id == user_id)\
                .order_by(Conversation.timestamp.desc())\
                .limit(limit)\
                .all()
            
            history = []
            for conv in conversations:
                history.append({
                    'user_message': conv.user_message,
                    'bot_response': conv.bot_response,
                    'timestamp': conv.timestamp,
                    'audio_generated': conv.audio_generated
                })
            
            session.close()
            return list(reversed(history))  # Return in chronological order
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting conversation history: {e}")
            if 'session' in locals():
                session.close()
            return []
    
    def get_conversation_context(self, user_id: int, limit: int = 5) -> str:
        """Get formatted conversation context for AI prompt"""
        history = self.get_user_conversation_history(user_id, limit)
        
        if not history:
            return ""
        
        context = "\n\nഞങ്ങളുടെ പഴയ സംഭാഷണം:\n"
        for conv in history:
            context += f"ഉപയോക്താവ്: {conv['user_message']}\n"
            context += f"മാവേലി: {conv['bot_response']}\n\n"
        
        return context
    
    def get_recent_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent conversations across all users for dashboard"""
        try:
            session = self.get_session()
            
            conversations = session.query(Conversation)\
                .order_by(Conversation.timestamp.desc())\
                .limit(limit)\
                .all()
            
            result = []
            for conv in conversations:
                # Get user info
                user = session.query(User).filter(User.id == conv.user_id).first()
                user_name = user.first_name if user else "Unknown"
                
                result.append({
                    'timestamp': conv.timestamp,
                    'user_id': conv.user_id,
                    'user_name': user_name,
                    'message': conv.user_message,
                    'response': conv.bot_response,
                    'audio_generated': conv.audio_generated
                })
            
            session.close()
            return result
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting recent conversations: {e}")
            if 'session' in locals():
                session.close()
            return []
    
    def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics for dashboard"""
        try:
            session = self.get_session()
            
            total_users = session.query(User).count()
            active_users = session.query(User).filter(User.is_active == True).count()
            total_conversations = session.query(Conversation).count()
            total_audio = session.query(Conversation).filter(Conversation.audio_generated == True).count()
            
            session.close()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_conversations': total_conversations,
                'total_audio_messages': total_audio
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting user stats: {e}")
            if 'session' in locals():
                session.close()
            return {
                'total_users': 0,
                'active_users': 0,
                'total_conversations': 0,
                'total_audio_messages': 0
            }

# Global database manager instance
db_manager = DatabaseManager()
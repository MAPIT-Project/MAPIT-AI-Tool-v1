from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
from .models import ChatSession, Message, UserPreferences
import asyncio
from concurrent.futures import ThreadPoolExecutor

class ChatService:
    def __init__(self, db: Session):
        self.db = db
        # Thread pool for running sync database operations asynchronously
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def _run_in_executor(self, func, *args, **kwargs):
        """Run synchronous database operations in a thread pool executor"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args, **kwargs)
    
    def _create_chat_session_sync(self, user_id: str, title: str = "New Chat") -> ChatSession:
        """Synchronous version of create_chat_session"""
        session = ChatSession(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            title_set=False
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    async def create_chat_session(self, user_id: str, title: str = "New Chat") -> ChatSession:
        """Create a new chat session for a specific user (async)"""
        return await self._run_in_executor(self._create_chat_session_sync, user_id, title)
    
    def _get_chat_session_sync(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """Synchronous version of get_chat_session"""
        try:
            session_uuid = uuid.UUID(session_id)
            return self.db.query(ChatSession).filter(
                ChatSession.id == session_uuid,
                ChatSession.user_id == user_id
            ).first()
        except ValueError:
            return None
    
    async def get_chat_session(self, session_id: str, user_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID for a specific user (async)"""
        return await self._run_in_executor(self._get_chat_session_sync, session_id, user_id)
    
    def _get_all_chat_sessions_sync(self, user_id: str) -> List[ChatSession]:
        """Synchronous version of get_all_chat_sessions"""
        return self.db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(desc(ChatSession.created_at)).all()
    
    async def get_all_chat_sessions(self, user_id: str) -> List[ChatSession]:
        """Get all chat sessions for a specific user ordered by creation date (newest first) (async)"""
        return await self._run_in_executor(self._get_all_chat_sessions_sync, user_id)
    
    async def get_session_info(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all session information including timestamps for a specific user, ordered by creation date (newest first) (async)"""
        sessions = await self.get_all_chat_sessions(user_id)
        session_info = []
        
        for session in sessions:
            # Get the latest message timestamp for this session
            latest_message = await self._run_in_executor(
                lambda: self.db.query(Message).filter(
                    Message.session_id == session.id,
                    Message.user_id == user_id
                ).order_by(desc(Message.timestamp)).first()
            )
            
            message_count = await self._run_in_executor(
                lambda: self.db.query(Message).filter(
                    Message.session_id == session.id,
                    Message.user_id == user_id
                ).count()
            )
            
            session_data = {
                "id": str(session.id),
                "title": session.title,
                "title_set": session.title_set,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "last_message_at": latest_message.timestamp.isoformat() if latest_message else None,
                "message_count": message_count
            }
            session_info.append(session_data)
        
        # Ensure sessions are ordered by creation date (newest first)
        session_info.sort(key=lambda x: x['created_at'] or '', reverse=True)
        
        return session_info
    
    def _update_chat_title_sync(self, session_id: str, user_id: str, title: str) -> Optional[ChatSession]:
        """Synchronous version of update_chat_title"""
        try:
            session_uuid = uuid.UUID(session_id)
            session = self.db.query(ChatSession).filter(
                ChatSession.id == session_uuid,
                ChatSession.user_id == user_id
            ).first()
            if session:
                session.title = title
                session.title_set = True
                self.db.commit()
                self.db.refresh(session)
            return session
        except ValueError:
            return None
    
    async def update_chat_title(self, session_id: str, user_id: str, title: str) -> Optional[ChatSession]:
        """Update chat session title for a specific user (async)"""
        return await self._run_in_executor(self._update_chat_title_sync, session_id, user_id, title)
    
    def _delete_chat_session_sync(self, session_id: str, user_id: str) -> bool:
        """Synchronous version of delete_chat_session"""
        try:
            session_uuid = uuid.UUID(session_id)
            session = self.db.query(ChatSession).filter(
                ChatSession.id == session_uuid,
                ChatSession.user_id == user_id
            ).first()
            if session:
                self.db.delete(session)
                self.db.commit()
                return True
            return False
        except ValueError:
            return False
    
    async def delete_chat_session(self, session_id: str, user_id: str) -> bool:
        """Delete a chat session and all its messages for a specific user (async)"""
        return await self._run_in_executor(self._delete_chat_session_sync, session_id, user_id)
    
    def _add_message_sync(self, session_id: str, user_id: str, role: str, content: str, 
                         context_used: Optional[Dict] = None, 
                         context_data: Optional[Dict] = None,
                         context_sources: Optional[Dict] = None,
                         elapsed_time: Optional[float] = None,
                         confidence: Optional[Dict] = None,
                         token_counts: Optional[Dict] = None,
                         lucene_query: Optional[str] = None) -> Optional[Message]:
        """Synchronous version of add_message"""
        try:
            session_uuid = uuid.UUID(session_id)
            # Verify the session belongs to the user
            session = self.db.query(ChatSession).filter(
                ChatSession.id == session_uuid,
                ChatSession.user_id == user_id
            ).first()
            if not session:
                return None
            
            message = Message(
                id=uuid.uuid4(),
                session_id=session_uuid,
                user_id=user_id,
                role=role,
                content=content,
                context_used=context_used,
                context_data=context_data,
                context_sources=context_sources,
                elapsed_time=elapsed_time,
                confidence=confidence,
                token_counts=token_counts,
                lucene_query=lucene_query,
                timestamp=datetime.utcnow()
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)
            return message
        except ValueError:
            return None
    
    async def add_message(self, session_id: str, user_id: str, role: str, content: str, 
                         context_used: Optional[Dict] = None, 
                         context_data: Optional[Dict] = None,
                         context_sources: Optional[Dict] = None,
                         elapsed_time: Optional[float] = None,
                         confidence: Optional[Dict] = None,
                         token_counts: Optional[Dict] = None,
                         lucene_query: Optional[str] = None) -> Optional[Message]:
        """Add a message to a chat session for a specific user (async)"""
        return await self._run_in_executor(
            self._add_message_sync, session_id, user_id, role, content, 
            context_used, context_data, context_sources, elapsed_time, confidence, token_counts, lucene_query
        )
    
    def _get_messages_sync(self, session_id: str, user_id: str, limit: Optional[int] = None) -> List[Message]:
        """Synchronous version of get_messages"""
        try:
            session_uuid = uuid.UUID(session_id)
            query = self.db.query(Message).filter(
                Message.session_id == session_uuid,
                Message.user_id == user_id
            ).order_by(Message.timestamp)
            if limit:
                query = query.limit(limit)
            return query.all()
        except ValueError:
            return []
    
    async def get_messages(self, session_id: str, user_id: str, limit: Optional[int] = None) -> List[Message]:
        """Get messages for a chat session for a specific user (async)"""
        return await self._run_in_executor(self._get_messages_sync, session_id, user_id, limit)
    
    def _delete_message_sync(self, message_id: str, user_id: str) -> bool:
        """Synchronous version of delete_message"""
        try:
            message_uuid = uuid.UUID(message_id)
            message = self.db.query(Message).filter(
                Message.id == message_uuid,
                Message.user_id == user_id
            ).first()
            if message:
                self.db.delete(message)
                self.db.commit()
                return True
            return False
        except ValueError:
            return False
    
    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """Delete a specific message for a specific user (async)"""
        return await self._run_in_executor(self._delete_message_sync, message_id, user_id)
    
    async def get_chat_history_text(self, session_id: str, user_id: str, max_history: int = 5) -> str:
        """Get formatted chat history as text for LLM context for a specific user (async)"""
        messages = await self.get_messages(session_id, user_id, limit=max_history)
        if not messages:
            return ""
        
        formatted_history = "Previous conversation:\n"
        for msg in messages:
            formatted_history += f"{msg.role}: {msg.content}\n"
        return formatted_history
    
    async def get_session_titles(self, user_id: str) -> Dict[str, str]:
        """Get all session titles for a specific user (legacy method for backward compatibility) (async)"""
        sessions = await self.get_all_chat_sessions(user_id)
        return {str(session.id): session.title for session in sessions}
    
    async def ensure_default_session(self, user_id: str) -> ChatSession:
        """Ensure there's at least one default session for a specific user (async)"""
        sessions = await self.get_all_chat_sessions(user_id)
        if not sessions:
            return await self.create_chat_session(user_id, "Chat 1")
        return sessions[0]
    
    # User Preferences Methods
    def _get_user_preferences_sync(self, user_id: str) -> Dict[str, bool]:
        """Synchronous version of get_user_preferences"""
        preferences = self.db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        
        if not preferences:
            # Create default preferences if they don't exist
            preferences = UserPreferences(
                id=uuid.uuid4(),
                user_id=user_id,
                neo4j_enabled=True,
                qdrant_enabled=True,
                elasticsearch_enabled=True
            )
            self.db.add(preferences)
            self.db.commit()
            self.db.refresh(preferences)
        
        return {
            "neo4j_enabled": preferences.neo4j_enabled,
            "qdrant_enabled": preferences.qdrant_enabled,
            "elasticsearch_enabled": preferences.elasticsearch_enabled
        }
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, bool]:
        """Get user preferences for data sources (async)"""
        return await self._run_in_executor(self._get_user_preferences_sync, user_id)
    
    def _update_user_preferences_sync(self, user_id: str, preferences: Dict[str, bool]) -> Dict[str, bool]:
        """Synchronous version of update_user_preferences"""
        user_prefs = self.db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        
        if not user_prefs:
            # Create new preferences if they don't exist
            user_prefs = UserPreferences(
                id=uuid.uuid4(),
                user_id=user_id,
                neo4j_enabled=preferences.get("neo4j_enabled", True),
                qdrant_enabled=preferences.get("qdrant_enabled", True),
                elasticsearch_enabled=preferences.get("elasticsearch_enabled", True)
            )
            self.db.add(user_prefs)
        else:
            # Update existing preferences
            user_prefs.neo4j_enabled = preferences.get("neo4j_enabled", user_prefs.neo4j_enabled)
            user_prefs.qdrant_enabled = preferences.get("qdrant_enabled", user_prefs.qdrant_enabled)
            user_prefs.elasticsearch_enabled = preferences.get("elasticsearch_enabled", user_prefs.elasticsearch_enabled)
        
        self.db.commit()
        self.db.refresh(user_prefs)
        
        return {
            "neo4j_enabled": user_prefs.neo4j_enabled,
            "qdrant_enabled": user_prefs.qdrant_enabled,
            "elasticsearch_enabled": user_prefs.elasticsearch_enabled
        }
    
    async def update_user_preferences(self, user_id: str, preferences: Dict[str, bool]) -> Dict[str, bool]:
        """Update user preferences for data sources (async)"""
        return await self._run_in_executor(self._update_user_preferences_sync, user_id, preferences) 
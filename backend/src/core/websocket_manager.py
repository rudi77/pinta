import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Store active connections per user
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Store connection metadata
        self.connection_metadata: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int, connection_type: str = "chat"):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        # Initialize user connections if not exists
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        # Add connection
        self.active_connections[user_id].add(websocket)
        
        # Store metadata
        self.connection_metadata[websocket] = {
            "user_id": user_id,
            "connection_type": connection_type,
            "connected_at": asyncio.get_event_loop().time()
        }
        
        logger.info(f"WebSocket connected for user {user_id}, type: {connection_type}")
        
        # Send connection confirmation
        await self.send_personal_message({
            "type": "connection_established",
            "message": "WebSocket connection established",
            "user_id": user_id
        }, websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.connection_metadata:
            metadata = self.connection_metadata[websocket]
            user_id = metadata["user_id"]
            
            # Remove from user connections
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                
                # Remove user entry if no connections left
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            # Remove metadata
            del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """Send message to a specific WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def send_to_user(self, message: Dict, user_id: int):
        """Send message to all connections of a specific user"""
        if user_id not in self.active_connections:
            logger.debug(f"No active connections for user {user_id}")
            return
        
        # Create a copy of connections to avoid modification during iteration
        connections = list(self.active_connections[user_id])
        
        for websocket in connections:
            try:
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                self.disconnect(websocket)
    
    async def send_streaming_response(self, user_id: int, stream_generator, task_id: str = None):
        """Send streaming AI response to user"""
        if user_id not in self.active_connections:
            return
        
        try:
            # Send stream start notification
            await self.send_to_user({
                "type": "stream_start",
                "task_id": task_id,
                "message": "AI response streaming started"
            }, user_id)
            
            # Stream content
            async for chunk in stream_generator:
                if chunk.get("type") == "content":
                    await self.send_to_user({
                        "type": "stream_content",
                        "task_id": task_id,
                        "content": chunk["content"]
                    }, user_id)
                elif chunk.get("type") == "done":
                    await self.send_to_user({
                        "type": "stream_complete",
                        "task_id": task_id,
                        "message": "Streaming completed"
                    }, user_id)
                elif chunk.get("type") == "error":
                    await self.send_to_user({
                        "type": "stream_error",
                        "task_id": task_id,
                        "error": chunk["error"]
                    }, user_id)
                    break
                
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            await self.send_to_user({
                "type": "stream_error",
                "task_id": task_id,
                "error": str(e)
            }, user_id)
    
    async def send_task_update(self, user_id: int, task_id: str, status: str, data: Dict = None):
        """Send background task status update to user"""
        message = {
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "timestamp": asyncio.get_event_loop().time(),
            **(data or {})
        }
        
        await self.send_to_user(message, user_id)
    
    async def send_quote_generated(self, user_id: int, quote_data: Dict):
        """Send quote generation completion notification"""
        message = {
            "type": "quote_generated",
            "quote": quote_data,
            "message": "Ihr Kostenvoranschlag wurde erfolgreich erstellt!"
        }
        
        await self.send_to_user(message, user_id)
    
    async def broadcast_to_all(self, message: Dict):
        """Broadcast message to all connected users"""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(message, user_id)
    
    def get_user_connection_count(self, user_id: int) -> int:
        """Get number of active connections for a user"""
        return len(self.active_connections.get(user_id, set()))
    
    def get_total_connections(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_connected_users(self) -> List[int]:
        """Get list of currently connected user IDs"""
        return list(self.active_connections.keys())
    
    async def ping_all_connections(self):
        """Send ping to all connections to keep them alive"""
        ping_message = {
            "type": "ping",
            "timestamp": asyncio.get_event_loop().time()
        }
        
        all_connections = []
        for connections in self.active_connections.values():
            all_connections.extend(connections)
        
        for websocket in all_connections:
            try:
                await websocket.send_text(json.dumps(ping_message))
            except Exception as e:
                logger.debug(f"Ping failed, disconnecting: {e}")
                self.disconnect(websocket)

# Global WebSocket manager
websocket_manager = ConnectionManager()

# Background task to keep connections alive
async def keep_connections_alive():
    """Background task to ping connections every 30 seconds"""
    while True:
        await asyncio.sleep(30)
        await websocket_manager.ping_all_connections()
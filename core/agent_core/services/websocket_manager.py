import asyncio
from fastapi import WebSocket
from typing import Dict, List, Any

class ConnectionManager:
    """
    Manages active WebSocket connections for different projects.
    """
    def __init__(self):
        # Dictionary to hold active connections, mapping project_id to a list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        """Accepts a new WebSocket connection and adds it to the list for a project."""
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
        print(f"Client connected to project {project_id}. Total clients: {len(self.active_connections[project_id])}")


    def disconnect(self, websocket: WebSocket, project_id: str):
        """Removes a WebSocket connection from the list."""
        if project_id in self.active_connections:
            self.active_connections[project_id].remove(websocket)
            print(f"Client disconnected from project {project_id}. Remaining clients: {len(self.active_connections[project_id])}")
            # If no connections are left for this project, clean up the entry
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def broadcast(self, message: Dict[str, Any], project_id: str):
        """Broadcasts a message to all connected clients for a specific project."""
        if project_id in self.active_connections:
            # Create a list of tasks for sending messages concurrently
            tasks = [
                connection.send_json(message)
                for connection in self.active_connections[project_id]
            ]
            await asyncio.gather(*tasks)

# Create a single global instance of the manager
manager = ConnectionManager()
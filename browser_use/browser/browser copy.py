import asyncio
import websockets
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class BrowserContext:
    """Represents a user's browser session managed via an extension."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.tabs = {}

    def update_tabs(self, tabs_data: Dict[str, Any]):
        """Update stored tab information from the browser extension."""
        self.tabs = tabs_data
        logger.info(f"Updated tabs for user {self.user_id}: {self.tabs}")

class CustomBrowser:
    """
    Custom browser manager that communicates with a browser extension.
    This does not open new browser instances but listens for data from the extension.
    """

    def __init__(self, port: int = 8080):
        self.port = port
        self.contexts: Dict[str, BrowserContext] = {}

    async def handle_browser_message(self, websocket, path):
        """Handles incoming messages from the browser extension."""
        try:
            async for message in websocket:
                data = json.loads(message)
                user_id = data.get("user_id", "unknown")
                
                if user_id not in self.contexts:
                    self.contexts[user_id] = BrowserContext(user_id)
                
                # Process tab updates
                if "tabs" in data:
                    self.contexts[user_id].update_tabs(data["tabs"])
                
                # Send a response to the extension (if needed)
                await websocket.send(json.dumps({"status": "received", "user_id": user_id}))

        except Exception as e:
            logger.error(f"Error in WebSocket communication: {e}")

    async def start_server(self):
        """Start a WebSocket server to receive messages from the browser extension."""
        server = await websockets.serve(self.handle_browser_message, "0.0.0.0", self.port)
        logger.info(f"WebSocket server started on port {self.port}")
        await server.wait_closed()

    def run(self):
        """Run the WebSocket server indefinitely."""
        asyncio.run(self.start_server())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    browser = CustomBrowser()
    browser.run()

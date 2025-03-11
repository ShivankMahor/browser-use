import asyncio
import websockets
import json

connected_extensions = set()

async def handle_browser(websocket, path):
    """Handles incoming WebSocket connections from the extension."""
    print("Browser extension connected")
    connected_extensions.add(websocket)

    try:
        async for message in websocket:
            data = json.loads(message)
            print("Received from extension:", data)

            if data.get("action") == "htmlResponse":
                print("Extracted HTML:", data.get("html"))
    
    except websockets.exceptions.ConnectionClosed:
        print("Browser extension disconnected")
    finally:
        connected_extensions.remove(websocket)

async def send_command(action, data):
    """Sends a command to the extension."""
    if connected_extensions:
        message = json.dumps({ "action": action, **data })
        for websocket in connected_extensions:
            await websocket.send(message)
            print(f"Sent: {message}")
    else:
        print("No connected extensions!")

async def main():
    """Starts the WebSocket server."""
    port = 8081
    server = await websockets.serve(handle_browser, "0.0.0.0", port)
    print("WebSocket Server running on ws://localhost:",port)
    await server.wait_closed()

# Windows-specific event loop fix
if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

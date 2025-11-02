import asyncio
import json
import logging
import websockets
import sys
from pathlib import Path

# Ensure project root is on sys.path so local packages (platforms, api, ...) can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ✅ 添加 # noqa: E402 来忽略这一行的 flake8 检查
from api.ws_platform import AsyncWebSocketsClient  # noqa: E402

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("ws_integration_test")

# Use port 0 to allow OS to pick a free port and avoid "address already in use" errors
PORT = 0
URI = None

async def server_handler(websocket, path):
    try:
        raw = await websocket.recv()
        logger.info(f"Server received raw: {raw}")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw

        # If request contains request_id, reply with matching request_id
        if isinstance(data, dict) and "request_id" in data:
            response = {
                "request_id": data["request_id"],
                "message": f"Reply to: {data.get('message', '')}"
            }
            await websocket.send(json.dumps(response))
            logger.info(f"Server sent response: {response}")
        else:
            await websocket.send("ok")
    except Exception as e:
        logger.exception(f"Server handler error: {e}")

async def main():
    # Start local websocket server (bind to port 0 to get a free port)
    server = await websockets.serve(server_handler, 'localhost', PORT)
    # Determine the actual port assigned by the OS
    sock = next(iter(server.sockets))
    assigned_port = sock.getsockname()[1]
    URI = f"ws://localhost:{assigned_port}"
    logger.info(f"Test WebSocket server running at {URI}")

    # Start client with the actual URI
    client = AsyncWebSocketsClient(uri=URI)
    await client.start()

    # Give a short moment for client to connect
    await asyncio.sleep(0.5)

    # Send a chat and wait for response
    result = await client.chat("tester", "hello world", system_prompt="", timeout=5)
    print("CHAT RESULT:", result)

    # Cleanup
    await client.close()
    server.close()
    await server.wait_closed()
    logger.info("Server closed")

if __name__ == '__main__':
    asyncio.run(main())

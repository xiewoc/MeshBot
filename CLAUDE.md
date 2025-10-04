# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MeshBot** is an AI assistant that runs on Meshtastic mesh networks, enabling offline AI interactions in remote areas without cellular or internet connectivity. It receives private messages over LoRa mesh networks, processes them using local or remote AI services, and replies back through the same mesh network.

### Core Functionality
- Receives point-to-point messages via Meshtastic serial interface
- Processes messages using pluggable AI backends (Ollama, OpenAI, DeepSeek, OpenRouter, WebSocket)
- Sends AI-generated responses back through the mesh network
- Maintains conversation history for context-aware responses
- Supports position tracking and signal quality logging (RSSI/SNR)

### Tech Stack
- **Language**: Python 3.7+ with asyncio
- **Mesh Communication**: Meshtastic Python library with pypubsub
- **AI Backends**: Ollama (local), OpenAI API, DeepSeek API, OpenRouter API, WebSocket integration
- **Networking**: aiohttp (HTTP), websockets (WebSocket client)
- **Configuration**: JSON-based dynamic client loading with .env support

## Project Structure

```
MeshBot/
├── main.py                     # Main entry point - unified bot implementation
├── config.json                 # AI client and system configuration
├── .env                        # Environment variables (API keys, model configs)
├── .env.example                # Environment variables template
├── requirements.txt            # Python dependencies
├── api/                        # AI client implementations
│   ├── ollama_api.py          # Ollama local AI client
│   ├── openai_api.py          # OpenAI API client
│   ├── deepseek_api.py        # DeepSeek API client
│   └── openrouter_api.py      # OpenRouter API client (supports .env)
├── platforms/
│   └── ws_platform.py         # WebSocket client for external integrations
└── scripts/
    └── ws_integration_test.py # WebSocket integration tests
```

## Commands

### Running the Bot

#### Basic Usage (Ollama Only - Legacy)
```bash
# Start Ollama service first
ollama serve

# Pull a model (if not already done)
ollama pull qwen2.5:7b

# Run the bot
python mesh_bot.py
```

#### Modern Usage (Config-based)
```bash
# 1. Copy .env.example to .env and fill in your API keys
cp .env.example .env
# Edit .env and add your OpenRouter/OpenAI/DeepSeek API keys

# 2. Edit config.json to select your AI backend
# Set "platform": "ollama" | "openai" | "deepseek" | "openrouter" | "websocket"

# 3. Run the unified bot
python main.py
```

### Configuration

#### Environment Variables (.env)
The recommended way to configure API keys and models is via `.env` file:
```bash
# OpenRouter (recommended for free models)
OPENROUTER_API_KEY=your-api-key-here
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

# OpenAI (optional)
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo

# DeepSeek (optional)
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_MODEL=deepseek-chat
```

See `.env.example` for full configuration options.

#### config.json
Edit `config.json` to configure:
- `system.platform`: Default AI backend (`ollama`, `openai`, `deepseek`, `openrouter`, `websocket`)
- `system.system_prompt`: AI system prompt (keep responses under 200 chars for mesh transmission)
- `system.max_response_length`: Maximum response length (default: 200)
- `clients.<platform>.kwargs`: Platform-specific configuration (overrides .env values if provided)

### Dependencies

```bash
pip install -r requirements.txt
```

Dependencies:
- `meshtastic` - Meshtastic device interface
- `pypubsub` - Event pub/sub for Meshtastic events
- `aiohttp` - Async HTTP client (for Ollama/OpenAI/DeepSeek/OpenRouter)
- `websockets` - WebSocket client (for AstrBot integration)
- `python-dotenv` - Load environment variables from .env file
- `asyncio` - Built-in async framework

## Architecture

### Message Flow

1. **Meshtastic Event** → `pub.subscribe("meshtastic.receive")` callback (`_on_receive`)
2. **Packet Analysis** → `_analyze_packet()` validates and extracts message data
3. **Queue** → Message added to async queue via `_queue_message()`
4. **Processing** → `_process_message_queue()` dequeues and calls `_handle_incoming_message()`
5. **AI Client** → `client.chat()` sends message to configured AI backend
6. **Response** → `interface.sendText()` sends reply back through mesh network

### Key Components

#### MeshAIBot (main.py:87)
- **Initialization**: Sets up Meshtastic interface, AI client, and event handlers
- **Message Queue**: Async queue with lock-protected processing
- **Signal Handling**: Graceful shutdown on SIGINT/SIGTERM
- **Event Loop Management**: Thread-safe async scheduling from sync callbacks

#### AI Client Interface
All AI clients implement:
- `async init()` - Initialize connection/session
- `async close()` - Clean up resources
- `async chat(user_name: str, message: str, system_prompt: str) -> Dict[str, Any]`
  - Returns: `{"success": bool, "response": str, "error": str}`
- `async get_models()` - List available models (optional)

#### Dynamic Client Loading (main.py:49)
```python
def create_ai_client(platform: str):
    config = AI_CLIENT_CONFIG.get(platform)
    module = importlib.import_module(config["module"])
    client_class = getattr(module, config["class"])
    return client_class(**config["kwargs"])
```

### Async Patterns

#### Thread-Safe Event Loop Scheduling
Meshtastic callbacks run in sync threads, so we use:
```python
asyncio.run_coroutine_threadsafe(
    self._queue_message(message_data, interface),
    self._loop  # Event loop saved during initialization
)
```

#### Lock-Protected AI Calls
```python
async with self._lock:
    await self.client.chat(...)
```

### Conversation History Management

- Each AI client maintains its own conversation history
- Limited to last 20 messages (10 exchanges) to avoid token overflow
- Format: `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]`
- User messages prefixed with sender name: `"NodeName:message"`

## Development Guidelines

### Adding a New AI Client

1. Create file in `api/` (e.g., `api/my_service_api.py`)
2. Implement class with required methods:
   ```python
   class AsyncMyServiceClient:
       async def init(self): ...
       async def close(self): ...
       async def chat(self, user_name: str, message: str,
                      system_prompt: str) -> Dict[str, Any]: ...
   ```
3. (Optional) Add .env support using `python-dotenv`:
   ```python
   from dotenv import load_dotenv
   import os

   load_dotenv()
   api_key = os.getenv("MYSERVICE_API_KEY")
   model = os.getenv("MYSERVICE_MODEL", "default-model")
   ```
4. Add configuration to `config.json`:
   ```json
   {
     "clients": {
       "myservice": {
         "module": "api.my_service_api",
         "class": "AsyncMyServiceClient",
         "kwargs": {}
       }
     }
   }
   ```
5. Set `"platform": "myservice"` in `config.json` to use it

### OpenRouter Integration (Example)

OpenRouter provides access to 400+ AI models through a unified API, including many free models. The `openrouter_api.py` adapter demonstrates best practices:

1. **Environment Variable Priority**:
   - Reads `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` from `.env`
   - Falls back to `google/gemini-2.0-flash-exp:free` if model not specified
   - Constructor parameters override .env values

2. **Free Model Discovery**:
   ```python
   # Get top free model dynamically
   top_model = await client.get_top_free_model()
   ```

3. **Usage**:
   ```bash
   # Set in .env
   OPENROUTER_API_KEY=sk-or-v1-xxx
   OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

   # Set platform in config.json
   "platform": "openrouter"
   ```

### Message Length Constraints

Meshtastic LoRa has strict packet size limits (~200 bytes). Always:
- Keep system prompts concise
- Truncate responses: `response[:MAX_RESPONSE_LENGTH]`
- Configure `max_response_length` in `config.json`
- AI system prompt should request brief responses

### Error Handling

- AI client errors return `{"success": False, "error": "message"}`
- Bot sends error message back to user: `"❌ 处理失败: {error}"`
- Network errors trigger auto-reconnect (WebSocket) or fallback to Ollama
- All exceptions logged with emoji indicators (✅/❌/⚠️/📡/🤖)

### Testing

#### WebSocket Integration Test
```bash
# Start a WebSocket echo server on localhost:9238
# Then run:
python scripts/ws_integration_test.py
```

Tests:
- Connection establishment
- Message sending/receiving
- Chat request/response flow
- Timeout handling
- Connection status monitoring

## Hardware Integration

### Typical Setup
- **Device**: Raspberry Pi Zero/4 or similar Linux board
- **Meshtastic Hardware**: TTGO T-Beam, Heltec LoRa32, etc. (connected via USB)
- **AI Service**:
  - Local: Ollama running on same device or network
  - Remote: OpenAI/DeepSeek via internet (requires connectivity)
  - Hybrid: WebSocket bridge to another service (e.g., AstrBot)

### Serial Connection
Bot auto-detects Meshtastic device via `meshtastic.serial_interface.SerialInterface()`. Ensure:
- USB device permissions (add user to `dialout` group on Linux)
- No other programs accessing the serial port
- Meshtastic firmware configured for serial output

## Troubleshooting

### Bot Not Responding to Messages
- Check `to_id` matches bot's node ID (only responds to direct messages)
- Verify Meshtastic connection: `self._node_id` should be logged on startup
- Check AI service is running and accessible
- Review logs for `"❌"` error indicators

### Ollama Connection Failures
```bash
# Ensure Ollama is running
ollama serve

# Test endpoint
curl http://127.0.0.1:11434/api/tags

# Check model is available
ollama list
```

### WebSocket Not Connecting
- Verify `config.json` has correct `uri` (e.g., `ws://localhost:9238`)
- Check WebSocket server is running
- Review logs for reconnection attempts
- Increase `max_reconnect_attempts` if needed

### Message Queue Timeouts
- Default timeout is 1 second (`MESSAGE_QUEUE_TIMEOUT`)
- Increase if AI responses are slow
- Monitor queue depth via logs

## Code Style

- **Async/Await**: All I/O operations must use async patterns
- **Logging**: Use emoji prefixes for log levels (✅ success, ❌ error, ⚠️ warning, 📡 message, 🤖 AI)
- **Type Hints**: Use for function signatures (already present in most code)
- **Error Returns**: Return structured dicts with `success`, `error`, `response` keys
- **Resource Cleanup**: Always implement `async def close()` and call in `shutdown()`
- **Thread Safety**: Use `asyncio.run_coroutine_threadsafe()` when bridging sync→async contexts

## Future Enhancements (Per README)

- **Context Memory**: Persistent conversation history across restarts
- **YAML Configuration**: Replace JSON config with YAML
- **Multi-Node Support**: Handle group messages or multi-bot networks
- **Voice Integration**: TTS/STT for voice-based mesh interactions


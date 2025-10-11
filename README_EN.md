<div align="center">

**English** | [ **简体中文** ](README.md)

</div>

# Mesh AI Assistant

A small AI node quietly residing in the Mesh network.
You send it a message, and it replies.

Unobtrusive, offline, and serverless.
Just for those times when you're in the mountains, in the wild, or somewhere without signal, you can still ask, "What do you think?" and receive an answer.

## 🧩 What Can It Do?

- Receive private messages sent to it (peer-to-peer)
- Generate brief replies using a local AI model
- Send the response back through the same path, as if it's always online waiting for you

All processing happens locally. Your privacy is maintained, with no dependency on the cloud.

## 📡 Why Build This?

Meshtastic enables communication in areas without networks, but the messages are always human-to-human.
I wondered: could there be a node that "understands"? Not complex or overly intelligent, but capable of responding.

So, this little project was born –
It doesn't initiate conversations or participate in group chats.
It's there when you need it.

## ⚙️ Technical Implementation

- Uses Python to listen for serial port messages from the Meshtastic device
- Extracts the content when a private message for this node is received
- Calls a locally running Ollama service (or other AI interface)
- Sends the generated reply back through the same network after creation

### How to Start

1. **Start the Ollama Service**:
   ```bash
   ollama serve
   ```
   > This starts the Ollama background service, defaulting to port `11434`.

2. **(Optional) Pull a Model in Advance**:
   ```bash
   ollama pull qwen2.5:7b
   ```
   Or use other lightweight models like `phi3` or `tinyllama`.

3. **Run the AI Node Program**:
   ```bash
   python main.py
   ```

> Note: Ollama will automatically download and load the model on the first request if it hasn't been pulled beforehand. Ensure your device has sufficient storage and memory.

### Current Configuration Example

```json
{
    "system": {
      "system_prompt": "You are an assistant. Please reply concisely (less than 200 characters).",
      "platform": "websocket",
      "max_response_length": 200,
      "message_queue_timeout": 1
    },
    "clients": {
      "ollama": {
        "module": "api.ollama_api",
        "class": "AsyncOllamaChatClient",
        "kwargs": {
          "default_model": "qwen2.5:7b"
        }
      },
      "openai": {
        "module": "api.openai_api",
        "class": "AsyncOpenAIChatClient",
        "kwargs": {
          "api_key": "your-api-key",
          "default_model": "gpt-3.5-turbo"
        }
      },
      "deepseek": {
        "module": "api.deepseek_api",
        "class": "AsyncDeepSeekChatClient",
        "kwargs": {
          "api_key": "your-api-key",
          "default_model": "deepseek-chat"
        }
      },
      "websocket": {
        "module": "platforms.ws_platform",
        "class": "AsyncWebSocketsClient",
        "kwargs": {
          "uri": "ws://localhost:9238"
        }
      },
      "openrouter": {
        "module": "api.openrouter_api",
        "class": "AsyncOpenRouterChatClient",
        "kwargs": {
          "app_name": "MeshBot"
        }
      }
    }
  }
```

>[!IMPORTANT]
>Remember to replace `your-api-key` with your actual API key when using `openai` or `deepseek`.
>
>If you are using OpenRouter, please refer to [README_OPENROUTER](README_OPENROUTER.md)

It runs perfectly on a Raspberry Pi + TTGO T-Beam – chat while you walk.

## 🛠️ How to Use?

1.  Prepare a device running Python (e.g., Raspberry Pi)
2.  Connect your Meshtastic node (e.g., via USB)
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Start the Ollama service:
    ```bash
    ollama serve
    ```
5.  Run the main program:
    ```bash
    python main.py
    ```
6.  Send a private message to it from another device and wait for the reply.

>[!IMPORTANT]
>Please pay attention to the working directory when running the main program; it must be run from within the project folder.

## 🎈 Current Version

- Added APIs for `OpenAI` and `DeepSeek`, providing a `WebSockets` interface.
- Optimized project structure.
- Added support for integration with `AstrBot` using the [AstrBot Adapter](https://github.com/xiewoc/astrbot_plugin_adapter_meshbot).

## 🌱 Future Ideas

- Introduce contextual memory for more coherent conversations.
- Add a WebUI.

## 🙏 Final Words

This project isn't meant to replace anyone, nor is it trying to create a super-smart AI.
It's just about leaving a responsive voice in those quiet places.

If you like this idea, you're welcome to help improve it.

And appriciate all the contributers who contributed to this repo ,there's no way this repop thrive without your contribution.

May your Meshtastic nodes run stably in the mountains and wilds, where every reply is like a small signal light quietly turning on. 📡💡

Happy Exploring! ✨
<div align="center">

[**简体中文**](README.md) | **English**

</div>

# Mesh AI Assistant

A small AI node that quietly resides in the Mesh network.  
You send it a message, and it replies with a sentence.

Unobtrusive, offline, and serverless.  
Just for those times when you're in the mountains, in the wild, or somewhere with no signal, and you can still ask, "What do you think?" and receive an answer.

## 🧩 What Can It Do?

-   Receive private messages sent to it (peer-to-peer messages)
-   Generate short replies using a local AI model
-   Send the response back the same way, as if it's always online waiting for you

All processing is done locally, ensuring privacy and control.

## ⚙️ Technical Implementation

-   Uses Python to listen for serial port messages from Meshtastic devices
-   Extracts content when a private message for this node is received
-   Calls a locally running Ollama service (or other AI interfaces)
-   Sends the generated reply back through the same network

### How to Start

1.  **Start the Ollama Service**:
    ```bash
    ollama serve
    ```
    > This starts the Ollama background service, listening on port `11434` by default.

2.  (Optional) Download a model in advance:
    ```bash
    ollama pull qwen2.5:7b
    ```
    Or use other lightweight models like `phi3` or `tinyllama`.

3.  Run the AI node program:
    ```bash
    python main.py
    ```

> Note: Ollama will automatically download and load the model on the first request (if not pulled in advance). Ensure your device has sufficient storage and memory.

### Current Configuration Example

```json
{
  "platform": "ollama",
  "api_keys": {
    "openai": "your-openai-api-key",
    "deepseek": "your-deepseek-api-key",
    "openrouter": "your-openrouter-api-key",
    "gemini": "your-gemini-api-key",
    "claude": "your-claude-api-key",
    "siliconflow": "your-siliconflow-api-key",
    "fastapi": "your-fastapi-token"
  },
  "model_settings": {
    "ollama": "qwen2.5:7b",
    "openai": "gpt-3.5-turbo",
    "deepseek": "deepseek-chat",
    "openrouter": "openai/gpt-3.5-turbo",
    "gemini": "gemini-pro",
    "claude": "claude-3-sonnet-20240229",
    "siliconflow": "deepseek-ai/DeepSeek-V2-Chat",
    "fastapi": "fastapi-default"
  },
  "service_urls": {
    "websockets": "ws://localhost:9238",
    "fastapi": "http://127.0.0.1:8000"
  }
}
```

> [!IMPORTANT]
> Please replace `your-api-key` with your actual API key when using services like `openai`, `deepseek`, etc.
>
> If you are using OpenRouter, please refer to [README_OPENROUTER](README_OPENROUTER.md)
>
> To integrate with `AstrBot`, you can use the [AstrBot Adapter](https://github.com/xiewoc/astrbot_plugin_adapter_meshbot)

It can easily run on a Raspberry Pi + TTGO T-Beam, allowing you to chat on the go.

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
6.  Send a private message to it from another device and wait for a reply.

> [!IMPORTANT]
> Please pay attention to the runtime path when executing the main program; it must be run from within the project folder.

## 🎈 Current Version

V 1.0.3

-   Refactored the folder structure
-   Added adapters for `Gemini`, `SiliconFlow`, `Claude`, and `Fastapi`
-   Refactored `config.json`

## 🌱 Future Ideas

-   Introduce context memory for more coherent conversations
-   Add a WebUI

## 🙏 Final Words

This project isn't meant to replace anyone, nor is it about creating an overly intelligent AI.  
It's just about leaving a voice that can respond to you in those quiet places.

If you also appreciate this concept, you're welcome to help improve it.

Simultaneously, thanks to the developers who have contributed to this project; we appreciate your support and efforts.

May your Meshtastic node run stably in the mountains and wilds, where every reply is like a quietly lit signal lamp. 📡💡

Happy Exploring! ✨
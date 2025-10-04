<div align="center">

[ **简体中文** ](readme.md) |  **English** 

</div>

# Mesh AI Assistant

A quiet little AI node living inside a Mesh network.
You send it a private message, and it replies with a brief answer.

Low-key, offline, and serverless. It’s made so that even when you’re hiking or out in the wild with no cellular signal, you can still ask “What do you think?” and get a short response back.

## What it does

- Receives private (point-to-point) messages addressed to this node
- Uses a locally running AI model/service to generate a short reply
- Sends the reply back over the same mesh network

Example:

> You: “Is tomorrow good for hiking?”
> It: “Clear skies, wind level 2, good for hiking.”

All processing happens locally (or on locally reachable services), so privacy is preserved and no cloud API is required unless you choose one.

## Why this project

Meshtastic lets people communicate where there’s no internet, but messages are normally just person-to-person. I wanted a node that can “understand” a bit and respond. Not smarter than you — just helpful when you need a short answer.

This node won’t talk unless you message it, and it won’t participate in group chats — it answers direct messages to it.

## Technical overview

- Python script that listens to a Meshtastic device over serial
- When a private message to this node arrives, it extracts the content
- Sends the text to a local AI service (like Ollama) or other configured AI client
- When a reply is returned, it forwards it back through the mesh network

### Quick start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the Ollama service (if you plan to use Ollama locally):

```bash
ollama serve
```

This starts Ollama listening on port 11434 by default.

3. (Optional) Pre-download a model to avoid on-demand download delays (take qwen2.5 for instance):

```bash
ollama pull qwen2.5:7b
```

4. Run the AI node program:

```bash
python main.py
```

> Note: Ollama will download models on first use if they are missing. Make sure the host has enough disk and memory if a large model is used.

### Configuration example

This project also includes a JSON-style configuration example that mirrors the runtime options used in the code. You can adapt it to your own config file or translate it to YAML.

```json
{
		"system": {
			"system_prompt": "You are an assistant. Reply concisely (under 200 characters).",
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
			}
		}
	}
```

> [!IMPORTANT]
> When using `openai` or `deepseek`, replace `your-api-key` with your actual API key.
>
>if you are using OpenRouter for api usage ,please refer to [README_OPENROUTER](README_OPENROUTER.md)


This project is small enough to run on a Raspberry Pi connected to a TTGO T-Beam or similar devices.

## How to use

1. Prepare a machine that can run Python (e.g., Raspberry Pi)
2. Connect your Meshtastic node (e.g., via USB)
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the Ollama service (or other AI service you prefer):

```bash
ollama serve
```

5. Run the program:

```bash
python mesh_ai_bot.py
```

6. From another Meshtastic device, send a private message to this node and wait for the reply.

## Future ideas

- Add contextual memory to make conversations more coherent
- Move configuration to YAML to avoid editing code

## Final note

This project isn’t trying to be the smartest assistant — it’s a small, private responder for quiet places. If you like the idea, contributions and improvements are welcome.

Wishing your Meshtastic node steady operation in the hills and wilds — may every reply be like a quietly lit signal. 📡💡

Happy exploring! ✨


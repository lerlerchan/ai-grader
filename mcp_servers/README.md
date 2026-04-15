# Ollama MCP Server

This directory contains MCP (Model Context Protocol) servers for ai-grader, with a primary focus on Ollama integration.

## Ollama Server

A FastMCP server that wraps the Ollama API with the following tools:

### Available Tools

1. **`check_health`**
   - Verify Ollama connectivity and health
   - Returns: `{healthy: bool, host: str, error?: str}`

2. **`list_models`**
   - List all available models on the Ollama instance
   - Returns: `{models: [{name: str, size: int, modified: str}], error?: str}`

3. **`generate_text`**
   - Send a prompt to an Ollama model and get a text response
   - Parameters: `model`, `prompt`, `temperature?`, `top_k?`, `top_p?`
   - Returns: `{response: str, model: str, done: bool, error?: str}`

4. **`chat`**
   - Send a chat message with system and user context
   - Parameters: `model`, `system`, `user_message`, `temperature?`
   - Returns: `{response: str, model: str, error?: str}`

5. **`pull_model`**
   - Pull (download) a model from Ollama's registry
   - Parameters: `model`
   - Returns: `{model: str, status: str, success: bool, error?: str}`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the server in stdio mode (default):

```bash
python mcp_servers/ollama_server.py
```

The server will connect to Ollama at the host specified by the `OLLAMA_HOST` environment variable (default: `http://localhost:11434`).

## Configuration

Set the Ollama host via environment variable:

```bash
export OLLAMA_HOST=http://custom-host:11434
python mcp_servers/ollama_server.py
```

## Tool Details

All tools include:
- **Error handling**: Returns structured error messages if Ollama is unavailable
- **Type hints**: Full type annotations for parameters and return values
- **Docstrings**: Comprehensive documentation for each tool
- **Configuration**: Configurable Ollama host via environment variable

## Requirements

- Python 3.10+
- `mcp`: Model Context Protocol library
- `ollama`: Ollama Python client

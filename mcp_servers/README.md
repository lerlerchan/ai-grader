# MCP Servers for AI Grader

This directory contains two optional [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers that extend AI Grader's capabilities. These servers expose specialized tools for working with language models (Ollama) and browser automation (Playwright).

**Note**: These servers are completely optional. The core `ai-grader mark` CLI works independently and does not require them to be running.

## Overview

### Why MCP Servers?

MCP servers provide a standardized way for AI assistants (Claude, other LLMs) to interact with external services through well-defined tools. The two servers here allow you to:

1. **Ollama MCP Server** - Let Claude interact directly with local Ollama instances for text generation, chat, and model management
2. **Playwright MCP Server** - Let Claude automate browser interactions for testing, web scraping, and UI automation

### When to Use Them

- **Ollama Server**: Use when you want Claude to programmatically interact with Ollama models (list available models, generate text, run chat sessions, pull new models)
- **Playwright Server**: Use when you want Claude to test web applications, perform automated browser interactions, or extract data from websites

## Quick Start

### Prerequisites (Both Servers)

- Python 3.8+ (for Ollama server)
- Node.js 18+ (for Playwright server)
- pip package manager (for Ollama server)
- npm package manager (for Playwright server)

### Ollama Server Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Ollama** (in a separate terminal):
   ```bash
   ollama serve
   ```
   Ollama will be accessible at `http://localhost:11434` by default.

3. **Run the MCP server**:
   ```bash
   python mcp_servers/ollama_server.py
   ```

4. **Configure in Claude** (if using Claude CLI or IDE extensions):
   Add to your MCP configuration file:
   ```json
   {
     "mcpServers": {
       "ollama": {
         "command": "python",
         "args": ["path/to/mcp_servers/ollama_server.py"],
         "env": {
           "OLLAMA_HOST": "http://localhost:11434"
         }
       }
     }
   }
   ```

### Playwright Server Setup

1. **Install dependencies**:
   ```bash
   cd mcp_servers/playwright
   npm install
   ```

2. **Build the server**:
   ```bash
   npm run build
   ```

3. **Run the MCP server**:
   ```bash
   npm start
   ```

4. **Configure in Claude** (if using Claude CLI or IDE extensions):
   Add to your MCP configuration file:
   ```json
   {
     "mcpServers": {
       "playwright": {
         "command": "node",
         "args": ["path/to/mcp_servers/playwright/dist/index.js"]
       }
     }
   }
   ```

## Ollama MCP Server

### Purpose

The Ollama server wraps the [Ollama API](https://github.com/ollama/ollama) and exposes tools for interacting with local LLM instances. This is useful for:

- Querying available models
- Generating text from custom prompts
- Running multi-turn chat conversations
- Pulling new models from Ollama's registry
- Health checking Ollama connectivity

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | URL where Ollama is running |

Set the environment variable before starting the server:
```bash
export OLLAMA_HOST=http://192.168.1.100:11434
python mcp_servers/ollama_server.py
```

### Tools

#### `check_health`

Verify that Ollama is running and accessible.

**No parameters**

**Returns**:
```json
{
  "healthy": true,
  "host": "http://localhost:11434"
}
```

Or if unhealthy:
```json
{
  "healthy": false,
  "host": "http://localhost:11434",
  "error": "Connection refused"
}
```

**Example usage in Claude**:
```
Check if my Ollama instance is running using the check_health tool.
```

---

#### `list_models`

List all models currently available on the Ollama instance.

**No parameters**

**Returns**:
```json
{
  "models": [
    {
      "name": "llama2:7b",
      "size": 3826087936,
      "modified": "2024-01-15T10:30:00Z"
    },
    {
      "name": "gemma4:12b",
      "size": 7000000000,
      "modified": "2024-01-16T14:22:00Z"
    }
  ]
}
```

**Example usage in Claude**:
```
What models do I have available on Ollama? List them all.
```

---

#### `generate_text`

Send a prompt to an Ollama model and get a text response (non-streaming).

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name (e.g., `gemma4:12b`, `llama2:7b`) |
| `prompt` | string | Yes | The prompt/question to send |
| `temperature` | float | No | Sampling temperature (0.0-1.0). Higher = more creative, lower = more deterministic. Default: model's default |
| `top_k` | int | No | Number of top tokens to consider |
| `top_p` | float | No | Nucleus sampling parameter |

**Returns**:
```json
{
  "response": "The response text from the model...",
  "model": "gemma4:12b",
  "done": true
}
```

**Example usage in Claude**:
```
Use Ollama's generate_text tool to ask the gemma4:12b model: "What is machine learning?"
With temperature set to 0.7.
```

---

#### `chat`

Send a chat message with system and user context to an Ollama model (structured conversation).

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name (e.g., `gemma4:12b`, `llama2:7b`) |
| `system` | string | Yes | System prompt that defines the assistant's behavior |
| `user_message` | string | Yes | The user's message/question |
| `temperature` | float | No | Sampling temperature (0.0-1.0) |

**Returns**:
```json
{
  "response": "The assistant's response...",
  "model": "gemma4:12b"
}
```

**Example usage in Claude**:
```
Use Ollama's chat tool with:
- model: gemma4:12b
- system: "You are a helpful Python tutor"
- user_message: "How do I read a file in Python?"
- temperature: 0.8
```

---

#### `pull_model`

Download a model from Ollama's registry to the local instance. Large models may take several minutes.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name to pull (e.g., `llama2:7b`, `mistral:7b`) |

**Returns**:
```json
{
  "model": "llama2:7b",
  "status": "completed",
  "success": true
}
```

Or if it fails:
```json
{
  "model": "llama2:7b",
  "status": "failed",
  "success": false,
  "error": "Model not found in registry"
}
```

**Example usage in Claude**:
```
Pull the llama2:7b model from Ollama.
```

---

### Example Workflow in Claude

```
I want to check if Ollama is running, list available models, and then ask a question to gemma4:12b.

Here's my plan:
1. Check health
2. List models
3. Generate text using generate_text with temperature 0.5

Let's start!
```

Claude will:
1. Call `check_health` to verify Ollama is accessible
2. Call `list_models` to see what's available
3. Call `generate_text` with your prompt

## Playwright MCP Server

### Purpose

The Playwright server exposes browser automation tools for testing, web scraping, and UI automation. This is useful for:

- Testing web applications
- Filling and submitting forms programmatically
- Extracting text and data from web pages
- Taking screenshots for visual verification
- Executing custom JavaScript on pages
- Following complex user workflows

### Prerequisites

- Node.js 18 or higher
- npm package manager
- Internet connection (for downloading Playwright browsers on first run)

### Tools

#### `navigate`

Navigate to a URL and wait for the page to load.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Full URL to navigate to (e.g., `https://example.com`) |

**Returns**:
```json
{
  "success": true,
  "status": 200,
  "url": "https://example.com/",
  "title": "Example Domain"
}
```

**Example usage in Claude**:
```
Navigate to https://example.com and tell me the page title.
```

---

#### `click`

Click an element on the page by CSS selector.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `selector` | string | Yes | CSS selector for the element to click (e.g., `#submit-btn`, `.menu-item`, `button[type="submit"]`) |

**Returns**:
```json
{
  "success": true,
  "message": "Clicked element: #submit-btn"
}
```

**Example usage in Claude**:
```
Click the submit button with the selector #submit-btn.
```

---

#### `fill_form`

Fill form fields (input, textarea) with values. Supports filling multiple fields at once.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fields` | object | Yes | Object mapping CSS selectors to values (e.g., `{"#username": "john", "#password": "secret123"}`) |

**Returns**:
```json
{
  "success": true,
  "filled": {
    "#username": true,
    "#password": true,
    "#email": true
  }
}
```

Or if some fields fail:
```json
{
  "success": false,
  "filled": {
    "#username": true,
    "#password": true,
    "#email": false
  }
}
```

**Example usage in Claude**:
```
Fill the login form with:
- #username: alice
- #password: mypassword123
- #rememberMe: on
```

---

#### `screenshot`

Take a screenshot of the current page and return as a base64-encoded PNG data URL.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fullPage` | boolean | No | If true, capture the entire page. If false, capture only the visible viewport. Default: false |

**Returns**:
```json
{
  "success": true,
  "image": "data:image/png;base64,iVBORw0KGgoAAAANS...",
  "size": 45823
}
```

**Example usage in Claude**:
```
Take a screenshot of the current page (full page) and show me what you see.
```

---

#### `get_text`

Extract text content from element(s) by CSS selector.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `selector` | string | Yes | CSS selector for element(s) to extract text from (e.g., `.result`, `h1`, `p.error-message`) |

**Returns**:
```json
{
  "success": true,
  "count": 3,
  "texts": [
    "Result 1",
    "Result 2",
    "Result 3"
  ]
}
```

**Example usage in Claude**:
```
Extract all the text from elements with the class "result".
```

---

#### `evaluate`

Execute arbitrary JavaScript code in the context of the page and return the result.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `script` | string | Yes | JavaScript code to execute (e.g., `document.title`, `window.location.href`, `JSON.stringify(window.myData)`) |

**Returns**:
```json
{
  "success": true,
  "result": "Page Title or Return Value"
}
```

**Example usage in Claude**:
```
Execute this JavaScript on the page: document.querySelectorAll('input').length
to count how many input fields exist.
```

---

### Example Workflow in Claude

```
I want to test a login page at https://testapp.local/login. Here's what I need to do:
1. Navigate to the login page
2. Fill in the username and password fields
3. Click the submit button
4. Wait and take a screenshot to verify the result
```

Claude will:
1. Call `navigate` with the URL
2. Call `fill_form` with your credentials
3. Call `click` to submit
4. Call `screenshot` to show you the result

## Troubleshooting

### Ollama Server Issues

**Problem**: "Connection refused" or "Ollama not running"

**Solution**:
1. Start Ollama in a separate terminal: `ollama serve`
2. Verify it's accessible: `curl http://localhost:11434/api/tags`
3. Check `OLLAMA_HOST` environment variable is correct
4. If using a remote Ollama, ensure the host is reachable and firewall allows it

**Problem**: "Model not found" when trying to use a model

**Solution**:
1. List available models with `list_models` tool
2. Pull the desired model using `pull_model` tool
3. Wait for the download to complete (can take several minutes for large models)

**Problem**: "Permission denied" or "Port already in use"

**Solution**:
- If port 11434 is already in use, start Ollama on a different port: `OLLAMA_HOST=http://localhost:11435 ollama serve`
- Update `OLLAMA_HOST` environment variable for the MCP server to match

---

### Playwright Server Issues

**Problem**: "npm install fails" or "Cannot find module"

**Solution**:
1. Ensure Node.js 18+ is installed: `node --version`
2. Clean and reinstall: 
   ```bash
   cd mcp_servers/playwright
   rm -rf node_modules package-lock.json
   npm install
   ```
3. Build the server: `npm run build`

**Problem**: "browser.launch failed" or "Playwright browser not found"

**Solution**:
1. Install Playwright browsers:
   ```bash
   cd mcp_servers/playwright
   npx playwright install
   ```
2. Ensure your system has required dependencies (Linux):
   ```bash
   sudo apt-get install libnss3 libgconf-2-4 libatk-bridge2.0-0
   ```

**Problem**: "Element not found" or "Selector didn't match"

**Solution**:
- Verify the CSS selector is correct by opening DevTools in your browser
- Make sure the element is visible/rendered on the page
- Try using a more specific selector or wait for the page to fully load first
- Use `get_text` or `screenshot` to debug and see what's on the page

**Problem**: Server crashes or becomes unresponsive

**Solution**:
1. Ensure the page you're navigating to is valid and accessible
2. Avoid infinite loops in `evaluate` scripts
3. Use simpler JavaScript in `evaluate` - complex async operations may timeout
4. Restart the server

---

## Development

### Modifying the Ollama Server

The Ollama server is built with [FastMCP](https://github.com/modelcontextprotocol/python-sdk), a Python framework for building MCP servers.

1. **Edit tool implementations** in `mcp_servers/ollama_server.py`
2. **Add new tools**:
   ```python
   @server.tool()
   def my_new_tool(param1: str, param2: int) -> dict[str, Any]:
       """Tool description here."""
       # Implementation
       return {"result": "value"}
   ```
3. **Test locally**:
   ```bash
   python mcp_servers/ollama_server.py
   ```

### Modifying the Playwright Server

The Playwright server is built with the [MCP TypeScript SDK](https://modelcontextprotocol.io/).

1. **Edit tool implementations** in `mcp_servers/playwright/src/index.ts`
2. **Add new tools**:
   - Add to `getTools()` method
   - Add case handler in `handleToolCall()`
   - Implement the tool method
3. **Build**:
   ```bash
   cd mcp_servers/playwright
   npm run build
   ```
4. **Test**:
   ```bash
   npm start
   ```

### Building from Source

**Ollama Server**:
```bash
# No build needed - it's pure Python
# Just run: python mcp_servers/ollama_server.py
```

**Playwright Server**:
```bash
cd mcp_servers/playwright
npm install      # Install dependencies
npm run build    # Compile TypeScript to JavaScript
npm start        # Run the compiled server
```

### Testing Servers

**Test Ollama Server**:
```bash
# With Ollama running, test a tool call:
python -c "
import subprocess
import json

result = subprocess.run(
    ['python', 'mcp_servers/ollama_server.py'],
    capture_output=True,
    timeout=5
)
print('Server started successfully')
"
```

**Test Playwright Server**:
```bash
# Start the server
npm start

# In another terminal, test it with a simple page:
curl -X POST http://localhost:3000 \
  -H 'Content-Type: application/json' \
  -d '{"tool": "navigate", "url": "https://example.com"}'
```

**Automated Tests**:
- Check `mcp_servers/test_tools.py` for test examples
- Run: `python mcp_servers/test_tools.py`

### Verification

Run the verification script to check both servers are properly configured:
```bash
python mcp_servers/verify_tools.py
```

This will:
- Check that all required dependencies are installed
- Verify tool signatures match MCP schema
- Test basic connectivity (if servers are running)

## Integration with Claude

To use these servers with Claude (Claude CLI or IDE extensions):

1. **Get the full paths** to both servers:
   ```bash
   pwd  # Current directory
   # Take note of the full path to mcp_servers/
   ```

2. **Create/update MCP configuration**:
   - Claude CLI: Edit `.copilot/mcp-config.json` or use `mcp-config.json` in your project root
   - VS Code: Edit `.vscode/mcp.json`
   - Other IDEs: Refer to your IDE's documentation

3. **Example configuration** (`.copilot/mcp-config.json`):
   ```json
   {
     "mcpServers": {
       "ollama": {
         "command": "python",
         "args": ["/full/path/to/mcp_servers/ollama_server.py"],
         "disabled": false,
         "env": {
           "OLLAMA_HOST": "http://localhost:11434"
         }
       },
       "playwright": {
         "command": "node",
         "args": ["/full/path/to/mcp_servers/playwright/dist/index.js"],
         "disabled": false
       }
     }
   }
   ```

4. **Restart Claude** to apply the configuration

5. **Verify servers are connected**:
   In Claude, ask: "Are the Ollama and Playwright MCP servers available?"

---

## Additional Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Ollama GitHub](https://github.com/ollama/ollama)
- [Playwright Documentation](https://playwright.dev/)
- [Python FastMCP](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)

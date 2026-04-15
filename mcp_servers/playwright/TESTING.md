# Playwright MCP Server - Integration Testing Guide

## Quick Start

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Start the server (communicates via stdio)
node dist/index.js
```

## Tool Examples

Once the server is running and connected to an MCP client (e.g., Claude), you can use the tools:

### 1. Navigate to a website
```json
{
  "name": "navigate",
  "arguments": {
    "url": "https://example.com"
  }
}
```

### 2. Take a screenshot
```json
{
  "name": "screenshot",
  "arguments": {
    "fullPage": false
  }
}
```

### 3. Fill a form
```json
{
  "name": "fill_form",
  "arguments": {
    "fields": {
      "#username": "john_doe",
      "#password": "secret123",
      "textarea.comments": "This is a test"
    }
  }
}
```

### 4. Click an element
```json
{
  "name": "click",
  "arguments": {
    "selector": "#submit-button"
  }
}
```

### 5. Extract text
```json
{
  "name": "get_text",
  "arguments": {
    "selector": ".result-item"
  }
}
```

### 6. Execute JavaScript
```json
{
  "name": "evaluate",
  "arguments": {
    "script": "document.title"
  }
}
```

## Response Format

All tools return JSON-formatted responses:

### Success Response
```json
{
  "success": true,
  "message": "...",
  "data": "..."
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message"
}
```

## Browser Configuration

- **Browser**: Chromium (headless mode)
- **Session**: Single browser instance per server
- **Timeout**: Default Playwright timeouts
- **Headless**: Always true for automated use

## Architecture Notes

- Built with TypeScript and @modelcontextprotocol/sdk
- Uses Playwright's Chromium automation
- Single page per server instance (can be extended for page management)
- Signal handlers for graceful shutdown (SIGINT, SIGTERM)
- Source maps included for debugging

## Future Enhancements

- Multiple page/tab management
- Browser context support
- Network interception
- Cookie/storage management
- Performance profiling

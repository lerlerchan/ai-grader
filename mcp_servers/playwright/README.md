# Playwright MCP Server

A Model Context Protocol (MCP) server for browser automation using Playwright with Chromium.

## Installation

```bash
npm install
npm run build
```

## Running the Server

```bash
node dist/index.js
```

The server communicates via stdio and is designed to be integrated with MCP clients (e.g., Claude).

## Tools

### navigate
Navigate to a URL and wait for the page to load.

**Parameters:**
- `url` (string, required): The URL to navigate to

**Returns:**
- `success`: Boolean indicating if navigation succeeded (HTTP 200-299)
- `status`: HTTP status code
- `url`: Final URL after navigation
- `title`: Page title

### click
Click an element on the page by CSS selector.

**Parameters:**
- `selector` (string, required): CSS selector for the element to click

**Returns:**
- `success`: Boolean indicating if click succeeded
- `message`: Confirmation message

### fill_form
Fill form fields (input, textarea) with values.

**Parameters:**
- `fields` (object, required): Map of CSS selectors to values

**Returns:**
- `success`: Boolean (true only if all fields filled)
- `filled`: Object mapping selectors to success status

### screenshot
Take a screenshot of the current page as base64-encoded PNG.

**Parameters:**
- `fullPage` (boolean, optional): Capture full page or viewport only (default: false)

**Returns:**
- `success`: Boolean
- `image`: Data URL (data:image/png;base64,...)
- `size`: Size in bytes

### get_text
Extract text content from element(s) by CSS selector.

**Parameters:**
- `selector` (string, required): CSS selector for element(s)

**Returns:**
- `success`: Boolean
- `count`: Number of elements matched
- `texts`: Array of text strings

### evaluate
Execute JavaScript code in the page context.

**Parameters:**
- `script` (string, required): JavaScript code to execute

**Returns:**
- `success`: Boolean
- `result`: Result of the JavaScript execution

## Architecture

- **Single browser session**: One browser instance per server
- **Chromium headless**: Uses headless Chromium for automated browsing
- **Structured responses**: All tools return JSON with success/error information
- **Base64 screenshots**: Screenshots encoded as data URLs for easy integration

## Future Enhancements

- Browser pool management for concurrent sessions
- Element inspection and DOM query utilities
- Network interception and request logging
- Cookie and local storage management
- Performance metrics collection

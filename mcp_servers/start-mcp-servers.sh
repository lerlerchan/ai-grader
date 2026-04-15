#!/bin/bash

# MCP Servers startup script for Unix/macOS/Linux
# Launches both Ollama and Playwright MCP servers

set -e

echo "=========================================="
echo "MCP Servers Startup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "${YELLOW}[1/4]${NC} Checking prerequisites..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "${RED}✗ Python 3 is not installed${NC}"
    echo "  Please install Python 3.8+ from https://www.python.org/downloads/"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "${GREEN}✓ Python 3${NC} found (version $PYTHON_VERSION)"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "${RED}✗ Node.js is not installed${NC}"
    echo "  Please install Node.js from https://nodejs.org/"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "${GREEN}✓ Node.js${NC} found (version $NODE_VERSION)"

# Check npm
if ! command -v npm &> /dev/null; then
    echo "${RED}✗ npm is not installed${NC}"
    echo "  npm should be included with Node.js. Please reinstall Node.js."
    exit 1
fi
NPM_VERSION=$(npm --version)
echo "${GREEN}✓ npm${NC} found (version $NPM_VERSION)"

echo ""

# Check if Ollama is available
echo "${YELLOW}[2/4]${NC} Checking Ollama availability..."
if ! command -v python3 -m mcp &> /dev/null; then
    echo "${YELLOW}⚠ Note:${NC} MCP CLI not found. Install with: pip install mcp"
fi
echo ""

# Build Playwright if needed
echo "${YELLOW}[3/4]${NC} Building Playwright MCP server..."
PLAYWRIGHT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/playwright" && pwd)"
if [ ! -d "$PLAYWRIGHT_DIR/dist" ] || [ -z "$(ls -A "$PLAYWRIGHT_DIR/dist" 2>/dev/null)" ]; then
    echo "  Running: npm run build"
    cd "$PLAYWRIGHT_DIR"
    npm run build > /dev/null 2>&1 || {
        echo "${RED}✗ Failed to build Playwright MCP server${NC}"
        exit 1
    }
    cd - > /dev/null
fi
echo "${GREEN}✓ Playwright MCP server built${NC}"
echo ""

# Start servers
echo "${YELLOW}[4/4]${NC} Starting MCP servers..."
echo ""
echo "${GREEN}=========================================${NC}"
echo "${GREEN}Starting Ollama MCP Server${NC}"
echo "${GREEN}=========================================${NC}"
echo "  Command: python3 -m mcp run $(dirname "${BASH_SOURCE[0]}")/ollama_server.py"
echo "  Port: 8000 (default)"
echo ""

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Start Ollama server in background
python3 -m mcp run "$SCRIPT_DIR/ollama_server.py" &
OLLAMA_PID=$!
echo "  PID: $OLLAMA_PID"
echo ""

sleep 2

echo "${GREEN}=========================================${NC}"
echo "${GREEN}Starting Playwright MCP Server${NC}"
echo "${GREEN}=========================================${NC}"
echo "  Command: node dist/index.js"
echo "  Port: 8001 (default)"
echo ""

# Start Playwright server in background
cd "$PLAYWRIGHT_DIR"
node dist/index.js &
PLAYWRIGHT_PID=$!
echo "  PID: $PLAYWRIGHT_PID"
cd - > /dev/null

echo ""
echo "${GREEN}=========================================${NC}"
echo "${GREEN}Both MCP servers are now running!${NC}"
echo "${GREEN}=========================================${NC}"
echo ""
echo "Server Details:"
echo "  Ollama MCP:     PID $OLLAMA_PID"
echo "  Playwright MCP: PID $PLAYWRIGHT_PID"
echo ""
echo "To stop the servers, run:"
echo "  kill $OLLAMA_PID $PLAYWRIGHT_PID"
echo ""
echo "Or press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait $OLLAMA_PID $PLAYWRIGHT_PID

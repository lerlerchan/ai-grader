# MCP Servers startup script for Windows PowerShell
# Launches both Ollama and Playwright MCP servers

param(
    [switch]$SkipBuild = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Green
Write-Host "MCP Servers Startup" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Helper function for colored output
function Write-Check {
    param([string]$Message, [string]$Status = "OK", [string]$Color = "Green")
    Write-Host "$(($Status -eq 'OK') ? '✓' : '✗') $Message" -ForegroundColor $Color
}

function Write-Step {
    param([int]$Number, [string]$Message)
    Write-Host "[$Number/4] $Message" -ForegroundColor Yellow
}

# Check prerequisites
Write-Step 1 "Checking prerequisites..."
Write-Host ""

# Check Python
try {
    $pythonVersion = & python --version 2>&1
    if ($pythonVersion -match "Python (\d+\.\d+\.\d+)") {
        Write-Check "Python 3" "OK" "Green"
        Write-Host "  Version: $pythonVersion"
    } else {
        Write-Check "Python 3" "FAIL" "Red"
        Write-Host "  Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Check "Python 3" "FAIL" "Red"
    Write-Host "  Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

# Check Node.js
try {
    $nodeVersion = & node --version 2>&1
    Write-Check "Node.js" "OK" "Green"
    Write-Host "  Version: $nodeVersion"
} catch {
    Write-Check "Node.js" "FAIL" "Red"
    Write-Host "  Please install Node.js from https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# Check npm
try {
    $npmVersion = & npm --version 2>&1
    Write-Check "npm" "OK" "Green"
    Write-Host "  Version: $npmVersion"
} catch {
    Write-Check "npm" "FAIL" "Red"
    Write-Host "  npm should be included with Node.js. Please reinstall Node.js." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Check MCP CLI
Write-Host "Checking MCP CLI availability..."
try {
    & python -m mcp --help > $null 2>&1
    Write-Check "MCP CLI" "OK" "Green"
} catch {
    Write-Host "⚠ Warning: MCP CLI not found" -ForegroundColor Yellow
    Write-Host "  Install with: pip install mcp" -ForegroundColor Yellow
}

Write-Host ""

# Build Playwright if needed
Write-Step 3 "Building Playwright MCP server..."
$playwrightDir = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "playwright"
$distDir = Join-Path $playwrightDir "dist"

if (-not (Test-Path $distDir) -or -not (Get-ChildItem $distDir -ErrorAction SilentlyContinue)) {
    Write-Host "  Running: npm run build"
    
    Push-Location $playwrightDir
    try {
        & npm run build | Out-Null
        Write-Check "Playwright MCP server built" "OK" "Green"
    } catch {
        Write-Check "Failed to build Playwright MCP server" "FAIL" "Red"
        exit 1
    } finally {
        Pop-Location
    }
} else {
    Write-Check "Playwright MCP server already built" "OK" "Green"
}

Write-Host ""

# Start servers
Write-Step 4 "Starting MCP servers..."
Write-Host ""

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Starting Ollama MCP Server" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ollamaServerPath = Join-Path $scriptDir "ollama_server.py"

Write-Host "  Command: python -m mcp run $ollamaServerPath"
Write-Host "  Port: 8000 (default)"
Write-Host ""

# Start Ollama server
$ollamaProcess = Start-Process -FilePath "python" `
    -ArgumentList "-m", "mcp", "run", $ollamaServerPath `
    -PassThru `
    -NoNewWindow `
    -ErrorAction Continue

Write-Host "  PID: $($ollamaProcess.Id)"
Write-Host ""

Start-Sleep -Seconds 2

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Starting Playwright MCP Server" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

Write-Host "  Command: node dist/index.js"
Write-Host "  Port: 8001 (default)"
Write-Host ""

# Start Playwright server
Push-Location $playwrightDir
$playwrightProcess = Start-Process -FilePath "node" `
    -ArgumentList "dist/index.js" `
    -PassThru `
    -NoNewWindow `
    -ErrorAction Continue

Write-Host "  PID: $($playwrightProcess.Id)"
Pop-Location

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Both MCP servers are now running!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Server Details:" -ForegroundColor Cyan
Write-Host "  Ollama MCP:     PID $($ollamaProcess.Id)"
Write-Host "  Playwright MCP: PID $($playwrightProcess.Id)"
Write-Host ""

Write-Host "To stop the servers:" -ForegroundColor Cyan
Write-Host "  Stop-Process -Id $($ollamaProcess.Id), $($playwrightProcess.Id)"
Write-Host ""
Write-Host "Or close this window to terminate both servers"
Write-Host ""

# Keep the servers running
$ollamaProcess.WaitForExit()
$playwrightProcess.WaitForExit()

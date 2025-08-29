#!/bin/bash

# This script runs the Kibana MCP server directly with HTTP transport
# for real-time access to Kibana logs with AI-powered analysis capabilities
# 
# Features:
# - Real-time log searching and analysis
# - AI-powered log summarization using Neurolink
# - Sorting logs by time using the sort_by parameter
# - Multiple authentication options
#
# AUTHENTICATION OPTIONS:
# 1. Environment variable (set below or export KIBANA_AUTH_COOKIE="your-token")
# 2. Config file (auth_cookie in config.yaml)
# 3. API call: curl -X POST http://localhost:8000/api/set_auth_token -H "Content-Type: application/json" -d '{"auth_token":"your-token-here"}'

# Function to check and setup Neurolink for AI analysis
setup_neurolink() {
    echo "🧠 Checking Neurolink setup for AI-powered log analysis..."
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        echo "⚠️  Node.js not found. AI analysis will be disabled."
        echo "   To enable AI features, install Node.js: https://nodejs.org/"
        return 1
    fi
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        echo "⚠️  npm not found. AI analysis will be disabled."
        return 1
    fi
    
    # Check if Neurolink is already installed
    if npx @juspay/neurolink --version &> /dev/null; then
        echo "✅ Neurolink already installed"
        
        # Initial check for AI provider API keys in the environment.
        # The Python server will perform the definitive check, including config.yaml.
        if [ -n "$GOOGLE_AI_API_KEY" ] || [ -n "$OPENAI_API_KEY" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
            echo "👍 AI provider API key found in initial environment check."
            echo "   (Note: The server will prioritize keys from config.yaml if set there)."
        else
            echo "ℹ️  No AI provider API key found in initial environment check."
            echo "   The Python server will also check 'config.yaml' for keys under 'ai_providers' section."
            echo "   (Keys in config.yaml take precedence over environment variables)."
            echo "   To set via environment (as an alternative): export GOOGLE_AI_API_KEY='your-key'"
        fi
        echo "🧠 AI analysis will be attempted by the server using any configured keys."
        
        # Perform a quick Neurolink status check
        echo "🩺 Attempting a quick Neurolink status check..."
        if npx @juspay/neurolink status; then
            echo "✅ Neurolink status check successful. It can connect to configured providers or operate locally."
            echo "   (Note: This CLI check primarily uses environment variables for keys.)"
            echo "    The Python server will definitively use keys from config.yaml if set there.)"
        else
            echo "⚠️  Neurolink status check reported issues or could not connect to a provider."
            echo "   This might be due to missing/invalid API keys accessible to the CLI OR network issues."
            echo "   If keys are only in config.yaml, the Python server will attempt to use them."
            echo "   If AI analysis fails later, ensure your API keys are correct in config.yaml or environment."
        fi
        return 0
    fi
    
    # Install Neurolink if not present
    echo "📦 Installing Neurolink for AI analysis..."
    if npm install -g @juspay/neurolink; then
        echo "✅ Neurolink installed successfully"
        echo "   Please ensure AI provider API keys are set either in environment variables"
        echo "   or in config.yaml for the server to use for full AI features."
        
        # Perform a quick Neurolink status check after installation
        echo "🩺 Attempting a quick Neurolink status check post-installation..."
        if npx @juspay/neurolink status; then
            echo "✅ Neurolink status check successful after installation."
        else
            echo "⚠️  Neurolink status check reported issues post-installation."
            echo "   Ensure API keys are correctly set in environment or config.yaml for full functionality."
        fi
        return 0
    else
        echo "❌ Failed to install Neurolink. AI analysis will be disabled."
        return 1
    fi
}

# Load the authentication token from start_mcp_server.sh
AUTH_TOKEN=""

# Stop any running servers
echo "Stopping any running servers..."
pkill -f "kibana_mcp_server.py" || true

# Setup Neurolink for AI features (optional)

# Set environment variables
export KIBANA_AUTH_COOKIE="$AUTH_TOKEN"
export PYTHONUNBUFFERED=1


# Run the MCP server with HTTP transport

echo "paste the below content to use this tool as mcp"

echo '
  "kibana-logs": {
    "command": "'"$(pwd)/venv/bin/python"'",
    "args": [
      "'"$(pwd)/kibana_mcp_server.py"'",
      "--transport", "stdio"
    ],
    "cwd": "'"$(pwd)"'"
  }'

echo "stop the server if using the tool as mcp"

# Activate virtual environment and run the MCP server with HTTP transport
source venv/bin/activate

# Run the server
echo "Starting Kibana MCP server with HTTP transport on http://localhost:8000"
python -m src.server --transport http --host localhost --port 8000

echo ""
echo "Server exited. Check for errors above." 

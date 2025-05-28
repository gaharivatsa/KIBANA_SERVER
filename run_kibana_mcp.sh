#!/bin/bash

# This script runs the Kibana MCP server directly with HTTP transport
# for real-time access to Kibana logs
# 
# The MCP server now supports sorting logs by time using the sort_by parameter:
# - When using search_logs, you can specify sort_by='time' and sort_order='desc'/'asc'
# - When using the API directly, add "sort_by": "time" to the request
#
# AUTHENTICATION OPTIONS:
# 1. Environment variable (set below or export KIBANA_AUTH_COOKIE="your-token")
# 2. Config file (auth_cookie in config.yaml)
# 3. API call: curl -X POST http://localhost:8000/api/set_auth_token -H "Content-Type: application/json" -d '{"auth_token":"your-token-here"}'

# Load the authentication token from start_mcp_server.sh
AUTH_TOKEN=""
# Stop any running servers
echo "Stopping any running servers..."
pkill -f "kibana_mcp_server.py" || true
pkill -f "http_server.py" || true
pkill -f "simple_server.py" || true

# Set environment variables
export KIBANA_AUTH_COOKIE="$AUTH_TOKEN"
export PYTHONUNBUFFERED=1

echo "Starting Kibana MCP Server with direct HTTP transport..."
echo "This will connect directly to Kibana for real logs."
echo "You can set or update the auth token via POST to /api/set_auth_token endpoint."

# Run the MCP server with HTTP transport
python kibana_mcp_server.py --transport http --host 0.0.0.0 --port 8000

echo ""
echo "Server exited. Check for errors above." 
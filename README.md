# 🔍 Kibana MCP (Model Context Protocol) Server

[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

> A powerful server that provides seamless access to Kibana logs through a convenient API, designed to work with Machine Control Protocol (MCP) and a standard HTTP interface.

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Setup](#-setup)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Authentication](#-authentication)
- [Running the Server](#-running-the-server)
- [API Reference](#-api-reference)
  - [Endpoints](#endpoints)
  - [Parameters](#parameters)
- [Example Usage](#-example-usage)
- [Troubleshooting](#-troubleshooting)
- [Architecture](#-architecture)
- [AI Integration](#-ai-integration)
- [License](#-license)

## 🌟 Overview

This project bridges the gap between your applications and Kibana logs by providing:

1. A Kibana log access server using the MCP protocol
2. HTTP API endpoints for log search and analysis
3. Tools for debugging Kibana connection issues
4. Fallback to mock data when Kibana is unavailable

##  Features

- **Simple API**: Easy-to-use endpoints for log searching and analysis
- **Flexible Authentication**: Multiple ways to provide authentication tokens
- **Time-Based Searching**: Support for both absolute and relative time ranges
- **Pattern Analysis**: Tools to identify log patterns and extract errors
- **Real-Time Streaming**: Monitor logs as they arrive

## 🚀 Setup

### Prerequisites

- Python 3.8+
- Access to a Kibana instance
- Kibana authentication token

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/gaharivatsa/KIBANA_SERVER.git
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   
   # On macOS/Linux
   source venv/bin/activate
   
   # On Windows
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Make the start script executable:
   ```bash
   chmod +x ./run_kibana_mcp.sh
   ```

### Configuration

1. Update `config.yaml` with your Kibana connection settings
2. Obtain a Kibana authentication token (see [Authentication](#-authentication))

### Adapting for Your Organization

This Kibana MCP Server can be easily configured for use by any company or organization:

1. **Update Connection Settings**:
   - Edit `config.yaml` to point to your organization's Kibana instance:
     ```yaml
     kibana:
       url: "https://your-company-kibana.example.com"
       indices: ["your-company-logs-*"]
       timestamp_field: "@timestamp"  # Adjust if your org uses a different field name
     ```

2. **Configure Authentication**:
   - Obtain a token from your organization's Kibana instance
   - Provide it using one of the [authentication methods](#-authentication)

3. **Customize Index Patterns**:
   - Different organizations have different index naming patterns
   - Update the `indices` field in `config.yaml` to match your log indices

4. **Adjust Field Mappings**:
   - If your organization uses custom field names:
     ```yaml
     field_mappings:
       timestamp: "your_timestamp_field_name"
       message: "your_message_field_name"
       level: "your_log_level_field_name"
     ```

5. **Test Your Configuration**:
   ```bash
   python test_kibana_connection.py
   ```

Once configured, all team members can use the same setup with their individual session IDs for log tracking and analysis.

## 🔐 Authentication

The server requires a valid Kibana authentication token to access logs. You have two main options:

### Option 1: Environment Variable

Set the token as an environment variable:

```bash
export KIBANA_AUTH_COOKIE="your_token_here"
./run_kibana_mcp.sh
```

### Option 2: API Authentication (Recommended)

Set the token through the API after starting the server:

```bash
curl -X POST http://localhost:8000/api/set_auth_token \
  -H "Content-Type: application/json" \
  -d '{"auth_token":"your_token_here"}'
```

Example with a token:
```bash
curl -X POST http://localhost:8000/api/set_auth_token \
  -H "Content-Type: application/json" \
  -d '{"auth_token":"hsjddfisdfidsiufiusf"}'
```

### How to Get Your Authentication Token

To obtain the authentication token from your Kibana instance:

1. Log in to your Kibana dashboard in a web browser
2. Open browser developer tools (right-click → Inspect or press F12)
3. Navigate to the "Application" tab in developer tools
4. In the sidebar, select "Cookies" under "Storage"
5. Look for the "pomerium" cookie (or similar authentication cookie) for your Kibana domain
6. Copy the complete cookie value - this is your authentication token

### Testing Your Token

Validate your token with:

```bash
python test_kibana_connection.py
```

If successful, you should see a list of available indices and sample logs.

## 🖥️ Running the Server

Start the HTTP server (recommended):

```bash
./run_kibana_mcp.sh
```

The server will be available at http://localhost:8000

## 📡 API Reference

### Endpoints

| Endpoint | Description | Method |
|----------|-------------|--------|
| `/api/search_logs` | Search logs with a query | POST |
| `/api/get_recent_logs` | Get the most recent logs | POST |
| `/api/analyze_logs` | Analyze logs for patterns | POST |
| `/api/extract_errors` | Extract error logs | POST |
| `/api/correlate_with_code` | Correlate logs with code | POST |
| `/api/stream_logs_realtime` | Stream logs in real-time | POST |
| `/api/set_auth_token` | Set authentication token | POST |

### Parameters

#### `/api/search_logs` Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `query_text` | string | Text to search for in logs | - |
| `start_time` | string | Start time for logs (ISO format or relative like '1h') | - |
| `end_time` | string | End time for logs (ISO format) | - |
| `levels` | array | Log levels to include (e.g., ["error", "warn"]) | - |
| `include_fields` | array | Fields to include in results | - |
| `exclude_fields` | array | Fields to exclude from results | - |
| `max_results` | integer | Maximum number of results | 100 |
| `sort_by` | string | Field to sort results by | "@timestamp" |
| `sort_order` | string | Sort order ("asc" or "desc") | "desc" |

> ⚠️ **Note**: Use `start_time` and `end_time` for time-based searches, not `time_range`.

#### `/api/analyze_logs` Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `time_range` | string | Time range to analyze (e.g., "1h", "1d", "7d") | - |
| `group_by` | string | Field to group results by | "level" |

#### `/api/extract_errors` Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `hours` | integer | Number of hours to look back | 24 |
| `include_stack_traces` | boolean | Whether to include stack traces | true |
| `limit` | integer | Maximum number of errors to return | 10 |

## 📝 Example Usage

### Search for logs

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "payment error", 
    "max_results": 50
  }'
```

### Search logs with time range

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "payment", 
    "start_time": "2025-05-25T00:00:00Z", 
    "end_time": "2025-05-26T00:00:00Z"
  }'
```

### Search using relative time

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "error", 
    "start_time": "24h"
  }'
```

### Analyze logs

```bash
curl -X POST http://localhost:8000/api/analyze_logs \
  -H "Content-Type: application/json" \
  -d '{
    "time_range": "24h", 
    "group_by": "level"
  }'
```

### Get recent logs

```bash
curl -X POST http://localhost:8000/api/get_recent_logs \
  -H "Content-Type: application/json" \
  -d '{
    "count": 10, 
    "level": "ERROR"
  }'
```

### Search for specific transaction

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "verifyPaymentAttempt", 
    "max_results": 1
  }'
```

### Stream logs in real-time

```bash
curl -X POST http://localhost:8000/api/stream_logs_realtime \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "payment"
  }'
```

## 🔧 Troubleshooting

If you encounter issues:

1. **Test Kibana connectivity**:
   ```bash
   python test_kibana_connection.py
   ```

2. **Check timestamp field issues**:
   - If you see "No mapping found for [timestamp]", update the timestamp field in `config.yaml`
   - Different indices may use different field names (`@timestamp`, `timestamp`, `start_time`)
   - The server will attempt to auto-detect and retry without sorting if needed
   - When using `sort_by`, make sure the field exists in your indices

3. **Authentication problems**:
   - Ensure your token is valid and not expired
   - Check that you're using the correct auth endpoint
   - Verify the token format matches what Kibana expects

4. **HTTP client issues**:
   - The server properly handles HTTP client lifecycle
   - If you see HTTP client errors, try restarting the server

## 🏗️ Architecture

The server consists of:

- `kibana_mcp_server.py` - Main server with MCP and HTTP support
- `config.yaml` - Configuration settings
- Support scripts for testing and token management

## 🤖 AI Integration

To integrate AI tools with this Kibana MCP Server, use the provided `AI_rules_file.txt`:

### Adding to AI Tools

1. Copy the contents of `AI_rules_file.txt` to your AI editor or AI assistant's custom instructions
2. This ensures your AI tools understand:
   - How to properly format Kibana queries with session IDs
   - The appropriate API endpoints for different types of log queries
   - Required parameters and authentication methods
   - Best practices for working with the Kibana Logs Tool

### Key AI Usage Requirements

- **Always request `session_id`** from users for all queries
- **Include `session_id` in all KQL queries** using format: `"{session_id} AND additional_query"`
- **Use Kibana Query Language (KQL)** for all query formatting
- **Set auth token first** before using any other endpoint
- **Parse and present results clearly** in a structured format

For complete AI integration instructions, refer to the `AI_rules_file.txt` in the project root.

## 📜 License

This project is licensed under the Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License (CC BY-NC-ND 4.0).

[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-nd/4.0/)

This license requires that reusers:
- Give appropriate credit (Attribution)
- Do not use the material for commercial purposes (NonCommercial)
- Do not distribute modified versions (NoDerivatives)

For more information, see the [LICENSE](LICENSE) file.

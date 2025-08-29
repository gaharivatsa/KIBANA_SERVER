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
- **🧠 AI-Powered Analysis**: Intelligent log summarization using [Neurolink](https://www.npmjs.com/package/@juspay/neurolink) with 9 AI providers
- **Smart Chunking**: Automatically handles large log sets with intelligent chunking and analysis combination
- **Fallback Analysis**: Provides basic analysis even when AI services are unavailable

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

5. **Optional: Set up AI-powered log analysis**:
   ```bash
   # Install Node.js if not already installed (required for Neurolink)
   # Visit https://nodejs.org/ or use your package manager
   
   # Set your AI provider API key (recommended for full AI features).
   # You can set them as environment variables (shown below) 
   # OR directly in config.yaml under the 'ai_providers' section.
   # Keys in config.yaml will override environment variables.
   
   # Example using environment variables:
   export GOOGLE_AI_API_KEY=\"your-google-ai-api-key\" # Recommended (free tier)
   # export OPENAI_API_KEY=\"your-openai-key\"
   
   # Neurolink will be automatically set up when you start the server using ./run_kibana_mcp.sh
   # The server will log which keys it is using (from env or config.yaml).
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

| `/api/summarize_logs` | 🧠 AI-powered log analysis with Neurolink | POST |
| `/api/set_auth_token` | Set authentication token | POST |
| `/api/discover_indexes` | Discover available Elasticsearch indexes | GET |
| `/api/set_current_index` | Set the current index to use for searches | POST |

### Parameters

#### `/api/search_logs` Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `query_text` | string | Text to search for in logs | - |
| `time_filter` | string/array | **🆕 UNIFIED TIME PARAMETER** - Supports relative strings ("1h", "24h", "7d", "2w") or absolute time tuples (["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]) | - |
| `start_time` | string | ⚠️ **DEPRECATED** - Use `time_filter` instead (still supported for backward compatibility) | - |
| `end_time` | string | ⚠️ **DEPRECATED** - Use `time_filter` instead (still supported for backward compatibility) | - |
| `levels` | array | Log levels to include (e.g., ["error", "warn"]) | - |
| `include_fields` | array | Fields to include in results | - |
| `exclude_fields` | array | Fields to exclude from results | - |
| `max_results` | integer | Maximum number of results | 100 |
| `sort_by` | string | Field to sort results by | "@timestamp" |
| `sort_order` | string | Sort order ("asc" or "desc") | "desc" |

> 💡 **New**: Use the unified `time_filter` parameter for both relative time strings and absolute timestamp ranges. Legacy parameters are still supported for backward compatibility.

#### `/api/analyze_logs` Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `time_filter` | string/array | **🆕 UNIFIED TIME PARAMETER** - Supports relative strings ("1h", "24h", "7d", "2w") or absolute time tuples (["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]) | - |
| `time_range` | string | ⚠️ **DEPRECATED** - Use `time_filter` instead (still supported for backward compatibility) | - |
| `group_by` | string | Field to group results by | "level" |

#### `/api/extract_errors` Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `time_filter` | string/array | **🆕 UNIFIED TIME PARAMETER** - Supports relative strings ("1h", "24h", "7d", "2w") or absolute time tuples (["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]) | - |
| `hours` | integer | ⚠️ **DEPRECATED** - Use `time_filter` instead (still supported for backward compatibility) | 24 |
| `include_stack_traces` | boolean | Whether to include stack traces | true |
| `limit` | integer | Maximum number of errors to return | 10 |

#### `/api/summarize_logs` Parameters

🧠 **AI-Powered Log Analysis**: This endpoint uses [Neurolink](https://www.npmjs.com/package/@juspay/neurolink) to generate intelligent analysis of your logs.

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `query_text` | string | Text to search for in logs | - |
| `time_filter` | string/array | **🆕 UNIFIED TIME PARAMETER** - Supports relative strings ("1h", "24h", "7d", "2w") or absolute time tuples (["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]) | - |
| `start_time` | string | ⚠️ **DEPRECATED** - Use `time_filter` instead (still supported for backward compatibility) | - |
| `end_time` | string | ⚠️ **DEPRECATED** - Use `time_filter` instead (still supported for backward compatibility) | - |
| `levels` | array | Log levels to include (e.g., ["error", "warn"]) | - |
| `include_fields` | array | Fields to include in results | - |
| `exclude_fields` | array | Fields to exclude from results | - |
| `max_results` | integer | Maximum number of results | 100 |
| `sort_by` | string | Field to sort results by | "@timestamp" |
| `sort_order` | string | Sort order ("asc" or "desc") | "desc" |

**Response Format**: Returns structured AI analysis including:
- **Summary**: Overview of log activities and systems involved
- **Key Insights**: Important patterns, behaviors, and recurring themes
- **Errors**: All errors and exceptions with details
- **Function Calls**: Critical functions and methods identified
- **Timestamp Flow**: Chronological reconstruction of events
- **Anomalies**: Suspicious behavior and inconsistencies
- **Focus Areas**: Areas requiring developer attention
- **Recommendations**: Suggested next steps and fixes

#### `/api/discover_indexes` Parameters

This endpoint doesn't require any parameters. It returns a list of all available indexes.

#### `/api/set_current_index` Parameters

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `index_pattern` | string | The index pattern to use for searching logs | Yes |

> 💡 **Tip**: Use `discover_indexes` to find available indexes, and then use `set_current_index` to select which one to use for searches.

## 📝 Example Usage

### Search Logs

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "error",
    "time_filter": "1h",
    "max_results": 20
  }'
```

### Get Recent Logs

```bash
curl -X POST http://localhost:8000/api/get_recent_logs \
  -H "Content-Type: application/json" \
  -d '{
    "count": 10,
    "level": "error"
  }'
```

### Discover Available Indexes

```bash
curl -X GET http://localhost:8000/api/discover_indexes
```

Response:
```json
{
  "success": true,
  "message": "Found 5 index patterns. Current index: breeze-v2-*",
  "index_patterns": [
    "breeze-v2-*", 
    "estio-logs-*", 
    "istio-logs-*", 
    "envoy-edge-*", 
    "kibana-*"
  ],
  "current_index": "breeze-v2-*"
}
```

### Set Current Index

```bash
curl -X POST http://localhost:8000/api/set_current_index \
  -H "Content-Type: application/json" \
  -d '{
    "index_pattern": "estio-logs-*"
  }'
```

Response:
```json
{
  "success": true,
  "message": "Current index pattern set to: estio-logs-*"
}
```

After setting the index, all subsequent log searches will use the specified index until it's changed again.

### AI-Powered Log Analysis

```bash
curl -X POST http://localhost:8000/api/summarize_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "error", 
    "max_results": 50,
    "time_filter": "1h"
  }'
```

**Example Response**:
```json
{
  "success": true,
  "analysis": {
    "summary": "Analysis of 42 error logs showing database connection issues and payment processing failures over the last hour.",
    "key_insights": [
      "Database connection timeout occurred 15 times",
      "Payment gateway returned 503 errors for 8 transactions",
      "Retry mechanism activated in 67% of failed cases"
    ],
    "errors": [
      "ConnectionTimeout: Database connection failed after 30s",
      "PaymentGatewayError: Service temporarily unavailable (503)"
    ],
    "function_calls": [
      "processPayment()",
      "connectToDatabase()",
      "retryTransaction()"
    ],
    "timestamp_flow": "Errors started at 14:23 with database issues, escalated to payment failures by 14:45",
    "anomalies": [
      "Unusual spike in connection timeouts between 14:30-14:40",
      "Payment success rate dropped to 23% (normal: 98%)"
    ],
    "focus_areas": [
      "Database connection pool configuration",
      "Payment gateway health monitoring",
      "Retry logic optimization"
    ],
    "recommendations": [
      "Increase database connection timeout from 30s to 60s",
      "Implement circuit breaker for payment gateway",
      "Add monitoring alerts for connection pool exhaustion"
    ]
  },
  "search_metadata": {
    "total_logs": 42,
    "query": "error",
    "indices_searched": "app-logs-*"
  }
}
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

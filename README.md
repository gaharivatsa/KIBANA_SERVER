# Kibana MCP (Machine Control Protocol) Server

A server that provides access to Kibana logs through a convenient API, designed to work with Machine Control Protocol (MCP) and a standard HTTP interface.

## Overview

This project provides:

1. A Kibana log access server using the MCP protocol
2. HTTP API endpoints for log search and analysis
3. Tools for debugging Kibana connection issues
4. Fallback to mock data when Kibana is unavailable

## Setup

### Prerequisites

- Python 3.8+
- Access to a Kibana instance
- Kibana authentication token

### Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Configuration

1. Copy `.env.example` to `.env` and configure as needed
2. Update `config.yaml` with your Kibana connection settings
3. Obtain a Kibana authentication token (see below)

## Authentication Token Management

The server requires a valid Kibana authentication token to access logs. You have several options to provide this token:

### Option 1: Environment Variable (Recommended)

Set the token as an environment variable:

```bash
export KIBANA_AUTH_COOKIE="your_token_here"
./run_kibana_mcp.sh
```

### Option 2: Update .env File

Add your token to the `.env` file:

```
KIBANA_AUTH_COOKIE=your_token_here
```

### Option 3: Update config.yaml

You can also add your token to the `config.yaml` file:

```yaml
elasticsearch:
  auth_cookie: "your_token_here"
   ```

## Getting a Kibana Authentication Token

Run the helper script for instructions:

```
./get_kibana_token.sh
```

This will guide you through:
1. Getting a token from your Kibana instance
2. Checking if your current token is valid
3. Troubleshooting connection issues

### Testing Your Token

You can validate your token with:

```bash
python test_kibana_connection.py
```

If successful, you should see a list of available indices and sample logs.

## Running the Server

### Option 1: HTTP Server (Recommended)

This runs the server with HTTP API endpoints:

```
./run_kibana_mcp.sh
```

The server will be available at http://localhost:8000

### Option 2: MCP Server with stdio

For direct integration with MCP clients:

```
export KIBANA_AUTH_COOKIE="your_token_here"
python kibana_mcp_server.py --transport stdio
```

## API Endpoints

The HTTP server provides these endpoints:

- `POST /api/search_logs` - Search logs with a query
- `POST /api/get_recent_logs` - Get the most recent logs
- `POST /api/analyze_logs` - Analyze logs for patterns
- `POST /api/extract_errors` - Extract error logs
- `POST /api/correlate_with_code` - Correlate logs with code
- `POST /api/stream_logs_realtime` - Stream logs in real-time

### API Parameters

#### `/api/search_logs` Parameters:
- `query_text` (string, optional): Text to search for in logs
- `start_time` (string, optional): Start time for logs (ISO format or relative like '1h')
- `end_time` (string, optional): End time for logs (ISO format)
- `levels` (array, optional): Log levels to include (e.g., ["error", "warn"])
- `include_fields` (array, optional): Fields to include in results
- `exclude_fields` (array, optional): Fields to exclude from results
- `max_results` (integer, optional): Maximum number of results (default: 100)
- `sort_by` (string, optional): Field to sort results by (e.g., "time", "timestamp", "@timestamp")
- `sort_order` (string, optional): Sort order ("asc" or "desc", default: "desc")

⚠️ Note: Use `start_time` and `end_time` for time-based searches, not `time_range`.

#### `/api/analyze_logs` Parameters:
- `time_range` (string, optional): Time range to analyze (e.g., "1h", "1d", "7d")
- `group_by` (string, optional): Field to group results by (default: "level")

#### `/api/extract_errors` Parameters:
- `hours` (integer, optional): Number of hours to look back (default: 24)
- `include_stack_traces` (boolean, optional): Whether to include stack traces (default: true)
- `limit` (integer, optional): Maximum number of errors to return (default: 10)

## Example Usage

### Search for logs:

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{"query_text": "payment error", "max_results": 50}'
```

### Search logs with time range:

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{"query_text": "payment", "start_time": "2025-05-25T00:00:00Z", "end_time": "2025-05-26T00:00:00Z"}'
```

### Search using relative time:

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{"query_text": "error", "start_time": "24h"}'
```

### Analyze logs:

```bash
curl -X POST http://localhost:8000/api/analyze_logs \
  -H "Content-Type: application/json" \
  -d '{"time_range": "24h", "group_by": "level"}'
```

### Get recent logs:

```bash
curl -X POST http://localhost:8000/api/get_recent_logs \
  -H "Content-Type: application/json" \
  -d '{"count": 10, "level": "ERROR"}'
```

### Search for specific transaction:

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{"query_text": "verifyPaymentAttempt", "max_results": 1}'
```

### Search logs with sorting:

```bash
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{"query_text": "payment", "sort_by": "time", "sort_order": "desc"}'
```

## Troubleshooting

If you encounter issues:

1. Check your authentication token with:
   ```
   ./get_kibana_token.sh
   ```

2. Test Kibana connectivity:
   ```
   python test_kibana_connection.py
   ```

3. Check timestamp field issues:
   - If you see "No mapping found for [timestamp]", update the timestamp field in `config.yaml`
   - Different indices may use different field names (`@timestamp`, `timestamp`, `start_time`)
   - The server will attempt to auto-detect and retry without sorting if needed
   - When using `sort_by`, make sure the field exists in your indices

4. HTTP client issues:
   - The server now properly handles HTTP client lifecycle
   - If you see any HTTP client errors, try restarting the server

5. Check the logs:
   ```
   tail -f kibana_mcp_server.log
   ```

6. Run the server with debug logging:
   ```
   LOG_LEVEL=DEBUG ./run_kibana_mcp.sh
   ```

## Architecture

The server consists of:

- `kibana_mcp_server.py` - Main server with MCP and HTTP support
- `config.yaml` - Configuration settings
- Support scripts for testing and token management
- Fallback mechanisms for unreachable Kibana instances

## License

This project is proprietary and confidential.
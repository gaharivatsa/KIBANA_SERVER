# Copyright (c) 2025 [Harivatsa G A]. All rights reserved.
# This work is licensed under CC BY-NC-ND 4.0.
# https://creativecommons.org/licenses/by-nc-nd/4.0/
# Attribution required. Commercial use and modifications prohibited.

#!/usr/bin/env python3
"""
Kibana Log MCP Server

This server implements the Model Context Protocol (MCP) to provide Cursor AI 
with access to Kibana logs for debugging and issue resolution.
"""

import os
import sys
import asyncio
import json
import yaml
import time
import datetime
import httpx
from typing import Dict, List, Optional, Any, Union, Tuple
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import elasticsearch
from elasticsearch import AsyncElasticsearch
from loguru import logger
from pydantic import BaseModel, Field

from mcp.server.fastmcp import FastMCP, Context
from mcp import types
import uvicorn
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# Store the dynamic auth token
DYNAMIC_AUTH_TOKEN = None

# Load configuration
def load_config(config_path: str = "config.yaml") -> Dict:
    """Load the configuration from a YAML file."""
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

def configure_logging():
    """Configure the logger with the settings from the config file."""
    log_level = CONFIG["mcp_server"]["log_level"].upper()
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    # logger.add("kibana_mcp_server.log", rotation="10 MB", retention="30 days", level=log_level)

# Initialize the configuration
CONFIG = load_config()

# Configure logging
log_level = CONFIG["mcp_server"]["log_level"].upper()
logger.remove()
logger.add(sys.stderr, level=log_level)
# logger.add("kibana_mcp_server.log", rotation="10 MB", retention="30 days", level=log_level)

# Get authentication details
es_config = CONFIG["elasticsearch"]
kibana_host = es_config['host']
kibana_version = es_config.get("kibana_api", {}).get("version", "7.10.2")
kibana_base_path = es_config.get("kibana_api", {}).get("base_path", "/_plugin/kibana")

# Get current auth token (with dynamic token support)
def get_auth_token():
    global DYNAMIC_AUTH_TOKEN
    return DYNAMIC_AUTH_TOKEN or os.environ.get("KIBANA_AUTH_COOKIE") or es_config.get("auth_cookie", "")

# Function to get a properly configured HTTP client
def get_http_client():
    """Get an HTTP client with proper configuration."""
    return httpx.AsyncClient(
        verify=es_config.get('verify_ssl', True),
        follow_redirects=True,
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
)

# Initialize the MCP server
mcp = FastMCP(
    CONFIG["mcp_server"]["name"],
    version=CONFIG["mcp_server"]["version"],
    dependencies=["elasticsearch>=8.0.0", "httpx>=0.24.0", "pydantic>=2.0.0"]
)

# Create a FastAPI app for HTTP transport
app = FastAPI(title="Kibana MCP Server")

# Add health endpoint for Docker healthchecks
@mcp.tool()
async def health():
    """Health check endpoint for container monitoring."""
    return {"status": "ok", "version": CONFIG["mcp_server"]["version"]}

# Helper function to interact with Kibana API
async def kibana_search(index_pattern: str, query: Dict, size: int = 10, sort: List = None, aggs: Dict = None) -> Dict:
    """Execute a search query through Kibana API."""
    # Prepare the search request
    url = f"https://{kibana_host}{kibana_base_path}/internal/search/es"
    
    # Build request payload
    search_body = {
        "query": query,
        "size": size
    }
    
    # Get timestamp field from config - default to '@timestamp' which is the Elasticsearch standard
    timestamp_field = es_config.get('timestamp_field', '@timestamp')
    
    # Check the index pattern to see if we have a specific config for it
    for source in CONFIG.get('log_sources', []):
        if source.get('index_pattern') and index_pattern.startswith(source.get('index_pattern').rstrip('*')):
            if 'timestamp_field' in source:
                timestamp_field = source.get('timestamp_field')
                logger.debug(f"Using timestamp field '{timestamp_field}' for index {index_pattern}")
                break
    
    # Add sort if provided and if we know the index has the field
    if sort:
        search_body["sort"] = sort
    else:
        # Default sort by timestamp if no sort is provided
        # We'll try not to sort if we're getting errors to avoid the "no mapping found" issue
        search_body["sort"] = [{timestamp_field: {"order": "desc"}}]
    
    # Add aggregations if provided
    if aggs:
        search_body["aggs"] = aggs
    
    # Format for the data API
    payload = {
        "params": {
            "index": index_pattern,
            "body": search_body
        }
    }
    
    # Set request headers
    headers = {
        "kbn-version": kibana_version,
        "Content-Type": "application/json"
    }
    
    # Get the current auth token
    current_auth_token = get_auth_token()
    
    # Check if we have an auth token
    if not current_auth_token:
        logger.error("No authentication token available. Please set it via API, environment variable, or config.")
        return {"error": "No authentication token available"}
    
    # Set cookies
    cookies = {"_pomerium": current_auth_token} if current_auth_token else None
    
    # Debug output for development
    logger.debug(f"Kibana search request: {json.dumps(payload)}")
    
    # Execute request with retry logic
    max_retries = 3
    retry_count = 0
    last_error = None
    
    # Create a new client for this request
    async with get_http_client() as client:
        while retry_count < max_retries:
            try:
                # Make the request
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    cookies=cookies,
                    timeout=20
                )
                
                # Handle response
                status_code = response.status_code
                if status_code == 200:
                    # Parse the response JSON
                    try:
                        # Try the async way first
                        result = await response.json()
                    except (TypeError, AttributeError):
                        # Fall back to direct access if json is not async callable
                        if callable(response.json):
                            result = response.json()
                        else:
                            result = response.json
                    
                    # Ensure we have a dictionary/JSON object
                    if hasattr(result, '__call__'):
                        logger.error("Response JSON is a method, not a value")
                        result = {"error": "Invalid response format", "rawResponse": {"hits": {"hits": []}}}
                    
                    logger.debug(f"Kibana search response status: 200 OK")
                    return result
                else:
                    # Get error text - fix for httpx response.text
                    try:
                        # Try the async way first
                        error_text = await response.text()
                    except (TypeError, AttributeError):
                        # Fall back to property access if text is not callable
                        error_text = response.text
                        
                    logger.error(f"Kibana search failed: {status_code} {error_text}")
                    last_error = f"{status_code}: {error_text}"
                    
                    # If we get a 400 with "no mapping found" for timestamp, try without sorting
                    if (status_code == 400 and 
                        "No mapping found for" in error_text and 
                        "in order to sort on" in error_text):
                        
                        logger.warning(f"Timestamp field '{timestamp_field}' not found in index. Trying without sort.")
                        # Remove the sort and try again
                        if "sort" in search_body:
                            del search_body["sort"]
                            payload["params"]["body"] = search_body
                            logger.debug(f"Retrying without sort: {json.dumps(payload)}")
                            continue
                    
                    # If it's an authentication issue, let's return a clear error
                    if status_code in (401, 403):
                        logger.error(f"Authentication failed: {status_code} {error_text}")
                        last_error = "Authentication failed. Check your Kibana auth token."
            
            except Exception as e:
                logger.error(f"Error during Kibana search: {str(e)}")
                import traceback
                logger.error(f"Stack trace: {traceback.format_exc()}")
                last_error = str(e)
                
            # Increase retry counter
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Retrying Kibana search ({retry_count}/{max_retries})...")
                await asyncio.sleep(1)  # Wait before retrying
    
    # If we reached here, all retries failed
    final_error_message = f"Kibana API request failed after {max_retries} retries."
    error_details = last_error if last_error else "Unknown error after multiple retries."
    logger.error(f"{final_error_message} Last error: {error_details}")
    
    return {
        "error": final_error_message,
        "details": error_details,
        "took": 0,
        "timed_out": True,
        "_shards": {
            "total": 0, 
            "successful": 0, 
            "skipped": 0, 
            "failed": 0 
        },
        "hits": { 
            "total": {"value": 0, "relation": "eq"},
            "max_score": None,
            "hits": []
        },
        "rawResponse": { 
             "hits": {
                "total": {"value": 0, "relation": "eq"},
                "max_score": None,
                "hits": []
            }
        }
    }

# === MCP Tools ===

@mcp.tool()
async def get_recent_logs(count: int = 10, level: Optional[str] = None, ctx: Context = None) -> List[Dict]:
    """
    Retrieve the most recent Kibana logs.
    
    Args:
        count: Number of logs to retrieve (default: 10)
        level: Filter by log level (e.g., "info", "error", "warn")
        
    Returns:
        List of recent log entries
    """
    # Validate input
    max_logs = CONFIG["processing"]["max_logs"]
    if count > max_logs:
        count = max_logs
        ctx.info(f"Limited request to {max_logs} logs")
    
    # Build query
    query = {"match_all": {}}
    if level:
        query = {"match": {"level": level}}
    
    index_pattern = f"{es_config['index_prefix']}*"
    try:
        # Use Kibana API to search
        result = await kibana_search(index_pattern, query, size=count)
        
        if "error" in result:
            logger.error(f"Error retrieving recent logs: {result['error']}")
            return {"error": result["error"]}
        
        # Process results
        logs = []
        if "hits" in result and "hits" in result["hits"]:
            logs = [doc["_source"] for doc in result["hits"]["hits"]]
            
            # Normalize timestamp fields
            for log in logs:
                # Check for various timestamp field names and normalize
                timestamp = None
                for field in ["@timestamp", "timestamp", "time", "start_time", "created_at"]:
                    if field in log:
                        timestamp = log[field]
                        break
                
                # Add a normalized timestamp field if any timestamp was found
                if timestamp:
                    log["normalized_timestamp"] = timestamp
            
            logger.debug(f"Retrieved {len(logs)} recent logs")
        else:
            logger.warning(f"No hits found in search result: {result}")
            
        return logs
        
    except Exception as e:
        logger.error(f"Error retrieving recent logs: {e}")
        return {"error": str(e)}


@mcp.tool()
async def search_logs(
    query_text: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    levels: Optional[List[str]] = None,
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    max_results: int = 100,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    ctx: Context = None
) -> Dict:
    """
    Search Kibana logs with flexible criteria.
    
    Args:
        query_text: Text to search for in log messages
        start_time: Start time for logs (ISO format or relative like '1h')
        end_time: End time for logs (ISO format)
        levels: List of log levels to include (e.g., ["error", "warn"])
        include_fields: Fields to include in results
        exclude_fields: Fields to exclude from results
        max_results: Maximum number of results to return
        sort_by: Field to sort results by (default: timestamp defined in config)
        sort_order: Order to sort results ("asc" or "desc", default: "desc")
        
    Returns:
        Dictionary with search results and metadata
    """
    try:
        # Validate input
        max_logs = CONFIG["processing"]["max_logs"]
        if max_results > max_logs:
            max_results = max_logs
            if ctx:
                ctx.info(f"Limited request to {max_logs} logs")
        
        # Build query
        must_clauses = []
        
        # Add text search if provided
        if query_text:
            must_clauses.append({
                "query_string": {
                    "query": query_text
                }
            })
        
        # Add time range if provided - try multiple timestamp fields
        if start_time or end_time:
            # Define potential timestamp fields to check
            timestamp_fields = ["@timestamp", "timestamp", "time", "start_time", "created_at"]
            
            # Build time range conditions
            time_range = {}
            if start_time:
                time_range["gte"] = start_time
            if end_time:
                time_range["lte"] = end_time
            
            # Build a should clause for any of the timestamp fields
            time_should_clauses = []
            for field in timestamp_fields:
                time_should_clauses.append({
                    "range": {
                        field: time_range
                    }
                })
            
            # Add the time filter as a should clause (match any timestamp field)
            if time_should_clauses:
                must_clauses.append({
                    "bool": {
                        "should": time_should_clauses,
                        "minimum_should_match": 1
                    }
                })
        
        # Add log level filter if provided
        if levels and len(levels) > 0:
            must_clauses.append({
                "terms": {
                    "level": levels
                }
            })
        
        # Construct the final query
        query = {"match_all": {}}
        if must_clauses:
            query = {
                "bool": {
                    "must": must_clauses
                }
            }
        
        # Prepare sort parameter
        sort_param = None
        if sort_by:
            # Using explicit sort field from parameter
            sort_param = [{sort_by: {"order": sort_order}}]
            logger.debug(f"Using explicit sort: {sort_param}")
        
        # Execute search against relevant indices
        index_pattern = f"{es_config['index_prefix']}*"
        result = await kibana_search(index_pattern, query, size=max_results, sort=sort_param)
        
        # Process results
        if isinstance(result, dict):
            if "rawResponse" in result:
                # Handle Kibana API format (new style)
                raw_response = result.get("rawResponse", {})
                hits = raw_response.get("hits", {}).get("hits", [])
                
                if not hits:
                    logger.warning(f"No logs found matching query. Response: {raw_response}")
                    
                # Extract documents and normalize
                docs = []
                for hit in hits:
                    if "_source" in hit:
                        doc = hit["_source"]
                        # Add metadata from the hit
                        doc["_index"] = hit.get("_index", "")
                        doc["_score"] = hit.get("_score", 0)
                        
                        # Apply field filtering if requested
                        if include_fields:
                            doc = {k: v for k, v in doc.items() if k in include_fields}
                        elif exclude_fields:
                            doc = {k: v for k, v in doc.items() if k not in exclude_fields}
                        
                        docs.append(doc)
                
                # Return search results
                return {
                    "success": True,
                    "total": len(docs),
                    "logs": docs,
                    "query": query_text or "All logs",
                    "indices_searched": index_pattern,
                    "sort_by": sort_by or "Default timestamp field"
                }
            elif "hits" in result:
                # Handle Elasticsearch direct API format (old style)
                hits = result.get("hits", {}).get("hits", [])
                
                # Process results
                logs = []
                if "hits" in result and "hits" in result["hits"]:
                    logger.debug(f"Number of hits: {len(result['hits']['hits'])}")
                    logs = [doc["_source"] for doc in result["hits"]["hits"]]
                    
                    # Apply field filtering if specified
                    if include_fields:
                        logs = [{k: v for k, v in log.items() if k in include_fields} for log in logs]
                    elif exclude_fields:
                        logs = [{k: v for k, v in log.items() if k not in exclude_fields} for log in logs]
                        
                    # Normalize timestamp fields
                    for log in logs:
                        # Check for various timestamp field names and normalize
                        timestamp = None
                        for field in ["@timestamp", "timestamp", "time", "start_time", "created_at"]:
                            if field in log:
                                timestamp = log[field]
                                break
                        
                        # Add a normalized timestamp field if any timestamp was found
                        if timestamp:
                            log["normalized_timestamp"] = timestamp
                else:
                    logger.warning(f"No hits found in search result: {result}")
                
                # Get total count, handling both int and dict formats
                total = 0
                if "hits" in result and "total" in result["hits"]:
                    if isinstance(result["hits"]["total"], dict) and "value" in result["hits"]["total"]:
                        total = result["hits"]["total"]["value"]
                    elif isinstance(result["hits"]["total"], int):
                        total = result["hits"]["total"]
                    else:
                        logger.warning(f"Unexpected total format: {result['hits']['total']}")
                        total = len(logs)
                else:
                    total = len(logs)
                
                # Return search results
                return {
                    "success": True,
                    "total": total,
                    "logs": logs,
                    "query": query_text or "All logs",
                    "indices_searched": index_pattern,
                    "sort_by": sort_by or "Default timestamp field"
                }
            elif "error" in result:
                # Handle error case
                logger.error(f"Error searching logs: {result.get('error')}")
                return {
                    "success": False,
                    "error": result.get("error"),
                    "logs": [],
                    "query": query_text or "All logs"
                }
            else:
                # Unknown format
                logger.error(f"Unexpected result format: {result}")
                return {
                    "success": False,
                    "error": "Unexpected response format from Kibana",
                    "logs": [],
                    "query": query_text or "All logs"
                }
        else:
            logger.error(f"Non-dict result received: {type(result)}")
            return {
                "success": False,
                "error": f"Unexpected response type: {type(result)}",
                "logs": [],
                "query": query_text or "All logs"
            }
    
    except Exception as e:
        logger.error(f"Error searching logs: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Return error with mock data
        return {
            "success": False,
            "error": str(e),
            "logs": [],
            "query": query_text or "All logs"
        }


@mcp.tool()
async def analyze_logs(
    time_range: str = "1h",
    group_by: Optional[str] = "level",
    ctx: Context = None
) -> Dict:
    """
    Analyze logs to identify patterns and provide statistics.
    
    Args:
        time_range: Time range to analyze (e.g. "1h", "1d", "7d")
        group_by: Field to group results by (e.g. "level", "service", "status")
        
    Returns:
        Dict containing analysis results and aggregations
    """
    # Parse time range
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Convert time range to datetime
    unit = time_range[-1]
    value = int(time_range[:-1])
    
    if unit == 'h':
        start_time = now - datetime.timedelta(hours=value)
    elif unit == 'd':
        start_time = now - datetime.timedelta(days=value)
    elif unit == 'w':
        start_time = now - datetime.timedelta(weeks=value)
    else:
        start_time = now - datetime.timedelta(hours=1)  # Default to 1 hour
        
    # Format start time as ISO
    start_time_iso = start_time.isoformat()
    
    # Define potential timestamp fields to check
    timestamp_fields = ["@timestamp", "timestamp", "time", "start_time", "created_at"]
    
    # Build time range conditions for any timestamp field
    time_should_clauses = []
    for field in timestamp_fields:
        time_should_clauses.append({
            "range": {
                field: {
                    "gte": start_time_iso
                }
            }
        })
    
    # Build query for time range
    query = {
        "bool": {
            "should": time_should_clauses,
            "minimum_should_match": 1
        }
    }
    
    try:
        # Execute search to get logs
        index_pattern = f"{es_config['index_prefix']}*"
        result = await kibana_search(index_pattern, query, size=0)
        
        if "error" in result:
            logger.error(f"Error analyzing logs: {result['error']}")
            return {"error": result["error"]}
        
        # Since we can't do aggregations directly with the Kibana API,
        # we'll fetch a sample of logs and do the aggregation in memory
        sample_result = await kibana_search(index_pattern, query, size=1000)
        
        if "error" in sample_result:
            logger.error(f"Error fetching sample logs: {sample_result['error']}")
            return {"error": sample_result["error"]}
        
        # Process results
        logs = []
        if "hits" in sample_result and "hits" in sample_result["hits"]:
            logs = [doc["_source"] for doc in sample_result["hits"]["hits"]]
        else:
            logger.warning(f"No hits found in search result: {sample_result}")
            return {
                "total_logs": 0,
                "time_range": time_range,
                "error_rate": 0,
                "aggregations": {}
            }
            
        total_logs = len(logs)
        
        # Perform aggregation
        aggregations = {}
        if group_by:
            counts = {}
            for log in logs:
                if group_by in log:
                    key = log[group_by]
                    if key not in counts:
                        counts[key] = 0
                    counts[key] += 1
            
            aggregations[group_by] = counts
        
        # Calculate error rate
        error_count = 0
        for log in logs:
            if "level" in log and log["level"].lower() in ["error", "fatal", "critical"]:
                error_count += 1
                
        error_rate = error_count / total_logs if total_logs > 0 else 0
        
        return {
            "total_logs": total_logs,
            "time_range": time_range,
            "error_rate": error_rate,
            "aggregations": aggregations
        }
            
    except Exception as e:
        logger.error(f"Error analyzing logs: {e}")
        return {"error": str(e)}


@mcp.tool()
async def extract_errors(
    hours: int = 24,
    include_stack_traces: bool = True,
    limit: int = 10,
    ctx: Context = None
) -> Dict:
    """
    Extract error logs with optional stack traces.
    
    Args:
        hours: Number of hours to look back
        include_stack_traces: Whether to include stack traces in results
        limit: Maximum number of errors to return
        
    Returns:
        Dict containing error logs and metadata
    """
    # Calculate time range
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now - datetime.timedelta(hours=hours)
    start_time_iso = start_time.isoformat()
    
    # Define potential timestamp fields to check
    timestamp_fields = ["@timestamp", "timestamp", "time", "start_time", "created_at"]
    
    # Build time range conditions for any timestamp field
    time_should_clauses = []
    for field in timestamp_fields:
        time_should_clauses.append({
            "range": {
                field: {
                    "gte": start_time_iso
                }
            }
        })
    
    # Build query for errors within time range
    query = {
        "bool": {
            "must": [
                {
                    "terms": {
                        "level": ["error", "fatal", "critical"]
                    }
                }
            ],
            "should": time_should_clauses,
            "minimum_should_match": 1
        }
    }
    
    try:
        # Execute search
        index_pattern = f"{es_config['index_prefix']}*"
        result = await kibana_search(index_pattern, query, size=limit)
        
        if "error" in result:
            logger.error(f"Error extracting errors: {result['error']}")
            return {"error": result["error"]}
        
        # Process results
        errors = []
        if "hits" in result and "hits" in result["hits"]:
            for doc in result["hits"]["hits"]:
                error = doc["_source"]
                
                # Extract stack trace if available and requested
                stack_trace = None
                if include_stack_traces:
                    if "error" in error and "stack_trace" in error["error"]:
                        stack_trace = error["error"]["stack_trace"]
                    elif "stack_trace" in error:
                        stack_trace = error["stack_trace"]
                        
                # Find timestamp
                timestamp = None
                for field in timestamp_fields:
                    if field in error:
                        timestamp = error[field]
                        break
                
                # Add to results
                errors.append({
                    "timestamp": timestamp,
                    "level": error.get("level", "error"),
                    "message": error.get("message", ""),
                    "service": error.get("service", ""),
                    "stack_trace": stack_trace
                })
        else:
            logger.warning(f"No hits found in search result: {result}")
        
        return {
            "errors": errors,
            "total": result["hits"]["total"]["value"] if "hits" in result and "total" in result["hits"] else len(errors),
            "hours": hours
        }
            
    except Exception as e:
        logger.error(f"Error extracting errors: {e}")
        return {"error": str(e)}


@mcp.tool()
async def correlate_with_code(
    error_message: str,
    repo_path: Optional[str] = None,
    ctx: Context = None
) -> Dict:
    """
    Correlate error logs with code locations.
    
    Args:
        error_message: Error message to search for
        repo_path: Path to the code repository (optional)
        
    Returns:
        Dict containing potential code locations and context
    """
    # Build query to find logs with the error message
    query = {
        "bool": {
            "must": [
                {
                    "match_phrase": {
                        "message": error_message
                    }
                },
                {
                    "terms": {
                        "level": ["error", "fatal", "critical"]
                    }
                }
            ]
        }
    }
    
    try:
        # Execute search
        index_pattern = f"{es_config['index_prefix']}*"
        result = await kibana_search(index_pattern, query, size=10)
        
        if "error" in result:
            logger.error(f"Error correlating with code: {result['error']}")
            return {"error": result["error"]}
        
        # Process results
        logs = [doc["_source"] for doc in result["hits"]["hits"]]
        
        # Extract code locations from logs
        code_locations = []
        for log in logs:
            locations = extract_code_locations(log)
            code_locations.extend(locations)
            
        # If repo path is provided, try to find the files
        if repo_path and code_locations:
            for location in code_locations:
                if "file" in location:
                    file_path = os.path.join(repo_path, location["file"])
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r') as f:
                                lines = f.readlines()
                                
                            # Extract context around the line
                            if "line" in location:
                                line_num = location["line"]
                                start_line = max(0, line_num - 3)
                                end_line = min(len(lines), line_num + 3)
                                
                                location["context"] = "".join(lines[start_line:end_line])
                        except Exception as e:
                            logger.warning(f"Error reading file {file_path}: {e}")
        
        return {
            "code_locations": code_locations,
            "error_message": error_message,
            "matching_logs": len(logs)
        }
            
    except Exception as e:
        logger.error(f"Error correlating with code: {e}")
        return {"error": str(e)}


@mcp.tool()
async def stream_logs_realtime(
    duration_seconds: int = 60,
    filter_expression: Optional[str] = None,
    ctx: Context = None
) -> Dict:
    """
    Stream logs in real-time for monitoring.
    
    Args:
        duration_seconds: Duration to stream logs for
        filter_expression: Expression to filter logs (e.g. "level:error")
        
    Returns:
        Dict containing the streamed logs
    """
    # Build query
    query = {"match_all": {}}
    
    if filter_expression:
        query = {
            "query_string": {
                "query": filter_expression
            }
        }
    
    # Set up streaming
    max_logs = CONFIG["processing"]["max_logs"]
    poll_interval = 2  # seconds
    logs_collected = []
    seen_log_ids = set()  # Track seen logs by ID to avoid duplicates
    
    # Get the current time to use as a reference point
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = now.isoformat()
    
    # Define timestamp fields to check for time-based filtering
    timestamp_fields = ["@timestamp", "timestamp", "time", "start_time", "created_at"]
    
    ctx.info(f"Starting log stream for {duration_seconds} seconds...")
    
    # Calculate number of polls
    num_polls = duration_seconds // poll_interval
    
    try:
        for i in range(num_polls):
            # Report progress
            await ctx.report_progress(i, num_polls)
            
            try:
                # Update query to only get logs since we started
                time_should_clauses = []
                for field in timestamp_fields:
                    time_should_clauses.append({
                        "range": {
                            field: {
                                "gte": start_time
                            }
                        }
                    })
                
                # Combine with original query
                time_query = {
                    "bool": {
                        "must": [query],
                        "should": time_should_clauses,
                        "minimum_should_match": 1
                    }
                }
                
                # Execute search
                index_pattern = f"{es_config['index_prefix']}*"
                result = await kibana_search(index_pattern, time_query, size=50)
                
                if "error" in result:
                    logger.error(f"Error in poll {i}: {result['error']}")
                    # Continue polling despite errors
                    await asyncio.sleep(poll_interval)
                    continue
                
                # Process results
                if "hits" in result and "hits" in result["hits"]:
                    new_logs = [doc["_source"] for doc in result["hits"]["hits"]]
                    
                    # Add to collected logs, avoiding duplicates
                    for log in new_logs:
                        # Create a unique ID for the log
                        log_id = None
                        
                        # Try to use existing ID if available
                        if "_id" in log:
                            log_id = log["_id"]
                        else:
                            # Create hash from content
                            log_content = json.dumps(log, sort_keys=True)
                            log_id = hash(log_content)
                        
                        if log_id not in seen_log_ids:
                            seen_log_ids.add(log_id)
                            logs_collected.append(log)
                            
                            # Normalize timestamp field
                            timestamp = None
                            for field in timestamp_fields:
                                if field in log:
                                    timestamp = log[field]
                                    break
                            
                            if timestamp:
                                log["normalized_timestamp"] = timestamp
                            
                            # Limit the number of logs
                            if len(logs_collected) >= max_logs:
                                ctx.info(f"Reached maximum log limit of {max_logs}")
                                break
                
                # Break if we've collected enough logs
                if len(logs_collected) >= max_logs:
                    break
            except Exception as e:
                logger.error(f"Error during poll {i}: {e}")
                # Continue polling despite errors
                
            # Wait for next poll
            await asyncio.sleep(poll_interval)
            
        return {
            "logs": logs_collected,
            "duration_seconds": duration_seconds,
            "filter": filter_expression,
            "log_count": len(logs_collected)
        }
            
    except Exception as e:
        logger.error(f"Error streaming logs: {e}")
        # Return any logs collected so far along with the error
        return {
            "error": str(e),
            "logs": logs_collected,
            "duration_seconds": duration_seconds,
            "filter": filter_expression,
            "log_count": len(logs_collected)
        }

# === Helper Functions ===

def extract_code_locations(log: Dict) -> List[Dict]:
    """Extract code locations from a log entry."""
    locations = []
    
    # Check for stack trace
    if "error" in log and "stack_trace" in log["error"]:
        stack_trace = log["error"]["stack_trace"]
        locations.extend(extract_file_info_from_stack_trace(stack_trace))
    elif "stack_trace" in log:
        stack_trace = log["stack_trace"]
        locations.extend(extract_file_info_from_stack_trace(stack_trace))
        
    # Check for context fields
    if "context" in log:
        context = log["context"]
        if isinstance(context, dict):
            if "file" in context:
                file_path = context["file"]
                line_num = context.get("line")
                
                locations.append({
                    "file": file_path,
                    "line": line_num
                })
    
    return locations

def extract_file_info_from_stack_trace(stack_trace: str) -> List[Dict]:
    """Extract file information from a stack trace."""
    locations = []
    
    if not stack_trace or not isinstance(stack_trace, str):
        return locations
        
    # Split into lines
    lines = stack_trace.split("\n")
    
    for line in lines:
        info = extract_file_info_from_line(line)
        if info:
            locations.append(info)
            
    return locations

def extract_file_info_from_line(line: str) -> Optional[Dict]:
    """Extract file information from a stack trace line."""
    if not line:
        return None
        
    # Common patterns in stack traces
    patterns = [
        r'at\s+[\w$.]+\s+\((.+):(\d+):\d+\)',  # JavaScript/Node.js
        r'at\s+(.+):(\d+):\d+',                # JavaScript/Node.js simplified
        r'File "(.+)", line (\d+)',            # Python
        r'at\s+[\w$.]+\((.+):(\d+)\)',         # Java/Kotlin
        r'at\s+(.+):(\d+)',                    # Generic
    ]
    
    import re
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            return {
                "file": match.group(1),
                "line": int(match.group(2))
            }
            
    return None

# New MCP tool to set auth token
@mcp.tool()
async def set_auth_token(auth_token: str, ctx: Context = None) -> Dict:
    """
    Set the Kibana authentication token for the current session.
    
    Args:
        auth_token: The authentication token to use for Kibana requests
        
    Returns:
        Dict with status information
    """
    global DYNAMIC_AUTH_TOKEN
    
    try:
        # Validate the token is not empty
        if not auth_token or auth_token.strip() == "":
            return {
                "success": False,
                "message": "Authentication token cannot be empty"
            }
        
        # Set the dynamic auth token
        old_token = DYNAMIC_AUTH_TOKEN
        DYNAMIC_AUTH_TOKEN = auth_token
        
        # Log the token change (masked for security)
        if old_token:
            logger.info("Authentication token updated")
        else:
            logger.info("Authentication token set")
        
        return {
            "success": True,
            "message": "Authentication token updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error setting authentication token: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

# Start the server if run directly
if __name__ == "__main__":
    # Get auth cookie from environment variable - no longer strictly required
    auth_cookie = os.environ.get('KIBANA_AUTH_COOKIE')
    if not auth_cookie:
        logger.warning("No authentication cookie provided in environment. You can set it via API or config.")
    
    # Configure logging
    # configure_logging() # This line might re-add it if not removed from the function itself.
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Kibana Log MCP Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--transport', choices=['http', 'stdio'], default='http', 
                      help='Transport to use for MCP')
    args = parser.parse_args()
    
    # Initialize and run MCP server
    transport = args.transport
    host = args.host
    port = args.port
    
    logger.info(f"Starting Kibana Log MCP Server on {host}:{port} using {transport} transport")
    
    if transport == 'http':
        # For HTTP transport, add routes to the FastAPI app
        @app.get("/")
        async def root(request: Request, format: Optional[str] = None):
            # If format=sse or accept header is text/event-stream, use SSE
            accept_header = request.headers.get("accept", "")
            if format == "sse" or "text/event-stream" in accept_header:
                # Use the existing SSE implementation
                return await stream_logs_sse(request)
            
            # Otherwise return regular JSON response
            return {"message": "Kibana MCP Server", "version": CONFIG["mcp_server"]["version"]}
        
        # Add MCP endpoints required by Smithery with lazy loading support
        @app.get("/mcp")
        async def mcp_get(request: Request):
            # Implement lazy loading for tool listing - don't check authentication here
            try:
                # Get request ID from query parameters
                request_id = request.query_params.get("id", "1")
                
                # Get the JSON-RPC method from query parameters
                method = request.query_params.get("method", "")
                
                # Only handle list_tools method
                if method == "list_tools":
                    # Define tool schemas manually without authentication
                    tools = [
                        {
                            "name": "health",
                            "description": "Health check endpoint for container monitoring.",
                            "parameters": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        },
                        {
                            "name": "set_auth_token",
                            "description": "Set the Kibana authentication token for the current session.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "auth_token": {
                                        "type": "string",
                                        "description": "The authentication token to use for Kibana requests"
                                    }
                                },
                                "required": ["auth_token"]
                            }
                        },
                        {
                            "name": "search_logs",
                            "description": "Search Kibana logs with flexible criteria.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query_text": {
                                        "type": "string",
                                        "description": "Text to search for in log messages"
                                    },
                                    "start_time": {
                                        "type": "string",
                                        "description": "Start time for logs (ISO format or relative like '1h')"
                                    },
                                    "end_time": {
                                        "type": "string",
                                        "description": "End time for logs (ISO format)"
                                    },
                                    "levels": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "List of log levels to include (e.g., [\"error\", \"warn\"])"
                                    },
                                    "include_fields": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Fields to include in results"
                                    },
                                    "exclude_fields": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Fields to exclude from results"
                                    },
                                    "max_results": {
                                        "type": "integer",
                                        "description": "Maximum number of results to return"
                                    },
                                    "sort_by": {
                                        "type": "string",
                                        "description": "Field to sort results by"
                                    },
                                    "sort_order": {
                                        "type": "string",
                                        "description": "Order to sort results (\"asc\" or \"desc\")"
                                    }
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "get_recent_logs",
                            "description": "Retrieve the most recent Kibana logs.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "count": {
                                        "type": "integer",
                                        "description": "Number of logs to retrieve"
                                    },
                                    "level": {
                                        "type": "string",
                                        "description": "Filter by log level (e.g., \"info\", \"error\", \"warn\")"
                                    }
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "analyze_logs",
                            "description": "Analyze logs to identify patterns and provide statistics.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "time_range": {
                                        "type": "string",
                                        "description": "Time range to analyze (e.g. \"1h\", \"1d\", \"7d\")"
                                    },
                                    "group_by": {
                                        "type": "string",
                                        "description": "Field to group results by (e.g. \"level\", \"service\", \"status\")"
                                    }
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "extract_errors",
                            "description": "Extract error logs with optional stack traces.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "hours": {
                                        "type": "integer",
                                        "description": "Number of hours to look back"
                                    },
                                    "include_stack_traces": {
                                        "type": "boolean",
                                        "description": "Whether to include stack traces in results"
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum number of errors to return"
                                    }
                                },
                                "required": []
                            }
                        },
                        {
                            "name": "correlate_with_code",
                            "description": "Correlate error logs with code locations.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "error_message": {
                                        "type": "string",
                                        "description": "Error message to search for"
                                    },
                                    "repo_path": {
                                        "type": "string",
                                        "description": "Path to the code repository (optional)"
                                    }
                                },
                                "required": ["error_message"]
                            }
                        },
                        {
                            "name": "stream_logs_realtime",
                            "description": "Stream logs in real-time for monitoring.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "duration_seconds": {
                                        "type": "integer",
                                        "description": "Duration to stream logs for"
                                    },
                                    "filter_expression": {
                                        "type": "string",
                                        "description": "Expression to filter logs (e.g. \"level:error\")"
                                    }
                                },
                                "required": []
                            }
                        }
                    ]
                    
                    # Return JSON-RPC response
                    return {
                        "jsonrpc": "2.0",
                        "result": tools,
                        "id": request_id
                    }
                else:
                    # For other methods, return error
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": f"Method '{method}' not found or not supported via GET"
                        },
                        "id": request_id
                    }
            except Exception as e:
                logger.error(f"Error handling MCP GET request: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Return JSON-RPC error
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    },
                    "id": request.query_params.get("id", "1")
                }
            
        @app.post("/mcp")
        async def mcp_post(request: Request):
            # Handle MCP POST requests (tool invocation)
            try:
                # Parse request body
                body = await request.json()
                
                # Get request ID and method
                request_id = body.get("id", "1")
                method = body.get("method", "")
                params = body.get("params", {})
                
                # Log the request
                logger.debug(f"MCP POST request: {method} with params {params}")
                
                # Special handling for health check
                if method == "health":
                    # Return health status directly
                    return {
                        "jsonrpc": "2.0",
                        "result": {"status": "ok", "version": CONFIG["mcp_server"]["version"]},
                        "id": request_id
                    }
                # Special handling for set_auth_token
                elif method == "set_auth_token":
                    # Set auth token
                    auth_token = params.get("auth_token", "")
                    if not auth_token:
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32602,
                                "message": "Invalid params: auth_token is required"
                            },
                            "id": request_id
                        }
                    
                    # Call the set_auth_token function
                    result = await set_auth_token(auth_token)
                    
                    # Return result
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                # Handle other tool calls
                elif method == "get_recent_logs":
                    result = await get_recent_logs(**params)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                elif method == "search_logs":
                    result = await search_logs(**params)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                elif method == "analyze_logs":
                    result = await analyze_logs(**params)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                elif method == "extract_errors":
                    result = await extract_errors(**params)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                elif method == "correlate_with_code":
                    result = await correlate_with_code(**params)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                elif method == "stream_logs_realtime":
                    result = await stream_logs_realtime(**params)
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": request_id
                    }
                else:
                    # Method not found
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32601,
                            "message": f"Method '{method}' not found"
                        },
                        "id": request_id
                    }
            except Exception as e:
                logger.error(f"Error handling MCP POST request: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Return JSON-RPC error
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    },
                    "id": body.get("id", "1") if isinstance(body, dict) else "1"
                }
            
        @app.delete("/mcp")
        async def mcp_delete(request: Request):
            # Handle MCP DELETE requests (session cleanup)
            return await mcp.handle_http_transport(request)
        
        # Add new endpoint for setting auth token via HTTP
        @app.post("/api/set_auth_token")
        async def api_set_auth_token(request_data: dict):
            if "auth_token" not in request_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="auth_token is required in the request body"
                )
            
            auth_token = request_data["auth_token"]
            
            # Set the token
            global DYNAMIC_AUTH_TOKEN
            old_token = DYNAMIC_AUTH_TOKEN
            DYNAMIC_AUTH_TOKEN = auth_token
            
            # Log the token change (masked for security)
            if old_token:
                logger.info("Authentication token updated via API")
            else:
                logger.info("Authentication token set via API")
            
            return {
                "success": True,
                "message": "Authentication token updated successfully"
            }
        
        # Register MCP tools as FastAPI endpoints
        @app.post("/api/search_logs")
        async def api_search_logs(request_data: dict):
            return await search_logs(**request_data)
            
        @app.post("/api/get_recent_logs")
        async def api_get_recent_logs(request_data: dict):
            return await get_recent_logs(**request_data)
            
        @app.post("/api/analyze_logs")
        async def api_analyze_logs(request_data: dict):
            return await analyze_logs(**request_data)
            
        @app.post("/api/extract_errors")
        async def api_extract_errors(request_data: dict):
            return await extract_errors(**request_data)
            
        @app.post("/api/correlate_with_code")
        async def api_correlate_with_code(request_data: dict):
            return await correlate_with_code(**request_data)
            
        @app.post("/api/stream_logs_realtime")
        async def api_stream_logs_realtime(request_data: dict):
            return await stream_logs_realtime(**request_data)
            
        @app.get("/tools")
        async def api_tools():
            return {
                "tools": [
                    {
                        "name": "set_auth_token",
                        "description": "Set the Kibana authentication token for the current session"
                    },
                    {
                        "name": "search_logs",
                        "description": "Search Kibana logs with flexible criteria"
                    },
                    {
                        "name": "get_recent_logs",
                        "description": "Retrieve the most recent Kibana logs"
                    },
                    {
                        "name": "analyze_logs",
                        "description": "Analyze logs to identify patterns and provide statistics"
                    },
                    {
                        "name": "extract_errors",
                        "description": "Extract error logs with optional stack traces"
                    },
                    {
                        "name": "correlate_with_code",
                        "description": "Correlate error logs with code locations"
                    },
                    {
                        "name": "stream_logs_realtime",
                        "description": "Stream logs in real-time for monitoring"
                    }
                ]
            }
        
        # SSE endpoint for realtime log streaming
        @app.get("/stream")
        async def stream_logs_sse(request: Request, duration: int = 60, filter: Optional[str] = None):
            """Stream logs in real-time using Server-Sent Events."""
            async def event_generator():
                """Generate events for SSE streaming."""
                # Set up streaming
                max_logs = CONFIG["processing"]["max_logs"]
                poll_interval = 2  # seconds
                seen_log_ids = set()  # Track seen logs by ID to avoid duplicates
                
                # Get the current time to use as a reference point
                now = datetime.datetime.now(datetime.timezone.utc)
                start_time = now.isoformat()
                
                # Define timestamp fields to check for time-based filtering
                timestamp_fields = ["@timestamp", "timestamp", "time", "start_time", "created_at"]
                
                # Build query
                query = {"match_all": {}}
                
                if filter:
                    query = {
                        "query_string": {
                            "query": filter
                        }
                    }
                
                # Send initial connection event
                yield {"event": "connected", "data": {"status": "connected", "server": "Kibana MCP"}}
                
                # Calculate number of polls
                num_polls = duration // poll_interval
                
                try:
                    for i in range(num_polls):
                        if await request.is_disconnected():
                            logger.info("Client disconnected from SSE stream")
                            break
                            
                        try:
                            # Update query to only get logs since we started
                            time_should_clauses = []
                            for field in timestamp_fields:
                                time_should_clauses.append({
                                    "range": {
                                        field: {
                                            "gte": start_time
                                        }
                                    }
                                })
                            
                            # Combine with original query
                            time_query = {
                                "bool": {
                                    "must": [query],
                                    "should": time_should_clauses,
                                    "minimum_should_match": 1
                                }
                            }
                            
                            # Execute search
                            index_pattern = f"{es_config['index_prefix']}*"
                            result = await kibana_search(index_pattern, time_query, size=50)
                            
                            if "error" in result:
                                logger.error(f"Error in poll {i}: {result['error']}")
                                yield {"event": "error", "data": {"error": result['error']}}
                                # Continue polling despite errors
                                await asyncio.sleep(poll_interval)
                                continue
                            
                            # Process results
                            new_logs = []
                            if "hits" in result and "hits" in result["hits"]:
                                for doc in result["hits"]["hits"]:
                                    log = doc["_source"]
                                    
                                    # Create a unique ID for the log
                                    log_id = doc.get("_id", hash(json.dumps(log, sort_keys=True)))
                                    
                                    if log_id not in seen_log_ids:
                                        seen_log_ids.add(log_id)
                                        
                                        # Normalize timestamp field
                                        for field in timestamp_fields:
                                            if field in log:
                                                log["normalized_timestamp"] = log[field]
                                                break
                                                
                                        new_logs.append(log)
                            
                            # Send any new logs as events
                            if new_logs:
                                yield {"event": "logs", "data": {"logs": new_logs, "count": len(new_logs)}}
                                
                        except Exception as e:
                            logger.error(f"Error during SSE poll {i}: {e}")
                            yield {"event": "error", "data": {"error": str(e)}}
                            
                        # Send a ping event to keep the connection alive
                        yield {"event": "ping", "data": {"time": time.time()}}
                        
                        # Wait for next poll
                        await asyncio.sleep(poll_interval)
                        
                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    yield {"event": "error", "data": {"error": str(e)}}
                    
                # Final message before closing
                yield {"event": "complete", "data": {"message": "Stream completed"}}
                
            return EventSourceResponse(event_generator())
        
        # Start the FastAPI app
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport=transport) 
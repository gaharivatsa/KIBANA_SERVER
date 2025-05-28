#!/usr/bin/env python3
"""
Test script to validate connection to Kibana instance
and verify log retrieval functionality.
"""

import sys
import asyncio
import yaml
import os
import httpx
import json
import traceback
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import AuthenticationException
from loguru import logger

# Setup logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Set the authentication token for testing
KIBANA_AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiYXV0aGVudGljYXRlLm11bS5icmVlemUuanVzcGF5Lm5ldCIsImtpYmFuYS5zc28ubXVtLmJyZWV6ZS5qdXNwYXkubmV0Il0sImRhdGFicm9rZXJfcmVjb3JkX3ZlcnNpb24iOjE5NTg5Nzk1LCJkYXRhYnJva2VyX3NlcnZlcl92ZXJzaW9uIjoyNzcxMDU3MzQwODg2MzY3NzQ0LCJpYXQiOjE3NDgxOTc2ODUsImlkcF9pZCI6IkRFUm9ucmc4dkgyM3dtTTNDWGRXNFN1QTY4ZUpTWWtUeEtFWG82R1Rvd2NVIiwiaXNzIjoiYXV0aGVudGljYXRlLm11bS5icmVlemUuanVzcGF5Lm5ldCIsImp0aSI6IjNiZDcyODYzLTQ1MDEtNGJjNi05MmRlLWVhM2QyMDNjOTlmYSIsInN1YiI6IjExNDcxMDI0MTg3OTI2NTU3MDI1MiJ9.gk5HK0NiaeuT_bKROq5a3OmClZ89G0Ndt6Jlkayikxg"

async def test_connection(config_path="config.yaml"):
    """Test connection to Elasticsearch and retrieve some logs."""
    try:
        # Load configuration
        with open(config_path, 'r') as file:
            config = json.load(file) if config_path.endswith('.json') else yaml.safe_load(file)
            
        # Get configuration values
        es_config = config.get("elasticsearch", {})
        kibana_host = es_config.get("host", "kibana.sso.mum.breeze.juspay.net")
        
        logger.info(f"Testing connection to Kibana at {kibana_host}")
        
        # Get authentication details
        # Use our predefined token first, fall back to environment or config
        auth_cookie = KIBANA_AUTH_TOKEN or os.environ.get("KIBANA_AUTH_COOKIE") or es_config.get("auth_cookie", "")
        
        if not auth_cookie:
            logger.error("No authentication cookie provided. Set KIBANA_AUTH_COOKIE environment variable.")
            return False
            
        logger.info(f"Using auth cookie: {auth_cookie[:20]}...")
        
        # Create HTTP client
        cookies = {"_pomerium": auth_cookie}
        
        # First, try to access Kibana API directly using httpx
        logger.info("Creating HTTP client with SSL verification disabled and 60s timeout")
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            # Test access to index patterns API
            url = f"https://{kibana_host}/_plugin/kibana/api/saved_objects/_find?type=index-pattern"
            headers = {
                "kbn-version": "7.10.2",
                "Content-Type": "application/json"
            }
            
            logger.info(f"Testing Kibana API access: {url}")
            try:
                response = await client.get(url, headers=headers, cookies=cookies)
                
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    logger.info("Successfully connected to Kibana API!")
                    patterns = response.json()
                    if "saved_objects" in patterns:
                        logger.info(f"Found {len(patterns['saved_objects'])} index patterns")
                        
                        # Display available index patterns
                        for pattern in patterns["saved_objects"]:
                            if "attributes" in pattern and "title" in pattern["attributes"]:
                                logger.info(f"  - {pattern['attributes']['title']}")
                else:
                    logger.error(f"Failed to connect to Kibana API: {response.status_code}")
                    logger.error(f"Response body: {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Exception during Kibana API request: {e}")
                logger.error(traceback.format_exc())
                return False
        
            # Now test direct Elasticsearch access (if available)
            try:
                # Try to access ES directly with the same cookie
                url = f"https://{kibana_host}:9200/_cat/indices?format=json"
                logger.info(f"Testing direct Elasticsearch access: {url}")
                response = await client.get(url, cookies=cookies)
                
                if response.status_code == 200:
                    logger.info("Successfully connected to Elasticsearch API!")
                    indices = response.json()
                    for index in indices:
                        if "kibana" in index.get("index", ""):
                            logger.info(f"  - {index.get('index')}: {index.get('docs.count')} docs")
                else:
                    logger.warning(f"Could not access Elasticsearch directly: {response.status_code}")
                    logger.warning(f"Response body: {response.text}")
                    logger.info("Will continue working through Kibana API only")
            except Exception as e:
                logger.warning(f"Direct Elasticsearch access failed: {e}")
                logger.info("Will continue working through Kibana API only")
            
            # Try to retrieve logs through Kibana API
            logger.info("Retrieving logs through Kibana API...")
            
            # Get a list of available indices
            logger.info("Fetching available indices...")
            url = f"https://{kibana_host}/_plugin/kibana/api/index_patterns/_fields_for_wildcard"
            params = {
                "pattern": "*",
                "meta_fields": ["_source", "_id", "_type", "_index", "_score"]
            }
            
            try:
                response = await client.get(url, params=params, headers=headers, cookies=cookies)
                logger.info(f"Index fields response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    if "fields" in result:
                        logger.info(f"Found {len(result['fields'])} fields")
                        
                        # Display some common fields
                        timestamp_fields = []
                        level_fields = []
                        message_fields = []
                        
                        for field in result["fields"]:
                            name = field.get("name", "")
                            if any(ts in name.lower() for ts in ["timestamp", "time", "date"]):
                                timestamp_fields.append(name)
                            elif "level" in name.lower() or "severity" in name.lower():
                                level_fields.append(name)
                            elif "message" in name.lower() or "msg" in name.lower():
                                message_fields.append(name)
                        
                        if timestamp_fields:
                            logger.info(f"Found timestamp fields: {', '.join(timestamp_fields[:5])}")
                        if level_fields:
                            logger.info(f"Found log level fields: {', '.join(level_fields[:5])}")
                        if message_fields:
                            logger.info(f"Found message fields: {', '.join(message_fields[:5])}")
                else:
                    logger.warning(f"Failed to get index fields: {response.status_code}")
            except Exception as e:
                logger.warning(f"Exception during index fields retrieval: {e}")
            
            # Try using the Kibana Data API
            logger.info("Using Kibana Data API...")
            
            # Try different index patterns
            index_patterns = ["istio-logs-v2*", "breeze-v2*", "envoy-edge*"]
            success = False
            
            for index_pattern in index_patterns:
                logger.info(f"Trying index pattern: {index_pattern}")
                
                # Use the Kibana Data API
                url = f"https://{kibana_host}/_plugin/kibana/internal/search/es"
                headers = {
                    "kbn-version": "7.10.2",
                    "Content-Type": "application/json"
                }
                
                # Format for the data API - without timestamp sorting
                payload = {
                    "params": {
                        "index": index_pattern,
                        "body": {
                            "query": {"match_all": {}},
                            "size": 5
                            # No sorting by timestamp
                        }
                    }
                }
                
                try:
                    response = await client.post(url, json=payload, headers=headers, cookies=cookies)
                    
                    logger.info(f"Search response status for {index_pattern}: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        if "rawResponse" in result and "hits" in result["rawResponse"] and "hits" in result["rawResponse"]["hits"]:
                            hits = result["rawResponse"]["hits"]["hits"]
                            logger.info(f"Retrieved {len(hits)} logs successfully from {index_pattern}!")
                            # Display a sample log
                            if hits:
                                logger.info(f"Sample log from {index_pattern}: {json.dumps(hits[0]['_source'], indent=2)}")
                                # Found logs, no need to try other patterns
                                success = True
                                break
                        else:
                            logger.warning(f"No logs found in indices matching {index_pattern}")
                    else:
                        logger.warning(f"Failed to retrieve logs from {index_pattern}: {response.status_code}")
                        logger.warning(f"Response body: {response.text}")
                except Exception as e:
                    logger.warning(f"Exception during log retrieval from {index_pattern}: {e}")
            
            if not success:
                logger.error("Could not retrieve logs from any of the attempted index patterns.")
                return False
            
        logger.info("Test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1) 
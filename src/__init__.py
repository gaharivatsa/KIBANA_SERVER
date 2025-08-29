"""
Kibana MCP Server - Model Context Protocol server for Kibana log analysis.

This package provides tools for searching, analyzing, and summarizing logs
through Kibana's API with AI-powered insights.
"""

__version__ = "1.0.0"
__author__ = "Harivatsa G A"

from .server import app, mcp
from .utils import TimeFilter, TimeRange, parse_time_filter

__all__ = [
    "mcp",
    "app",
    "TimeFilter",
    "TimeRange",
    "parse_time_filter",
]

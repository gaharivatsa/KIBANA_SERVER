# Unified Time Parameter System - Implementation Guide

## Overview

The Kibana MCP Server now supports a unified time parameter system that provides a consistent interface across all time-related tools. This system replaces the inconsistent time parameter handling with a single `time_filter` parameter that supports both relative time strings and absolute timestamp tuples.

## New TimeFilter Parameter

### Supported Formats

#### 1. Relative Time Strings
Format: `{number}{unit}` where unit is `h` (hours), `d` (days), or `w` (weeks)

**Examples:**
- `"1h"` - Last 1 hour
- `"24h"` - Last 24 hours
- `"7d"` - Last 7 days
- `"2w"` - Last 2 weeks

#### 2. Absolute Time Tuples
Format: `["start_time_iso", "end_time_iso"]` - JSON array with exactly 2 ISO timestamp strings

**Examples:**
- `["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]` - January 1-2, 2024
- `["2024-01-01T12:00:00Z", "2024-01-01T18:00:00Z"]` - January 1, 2024, 12:00-18:00 UTC

### Supported Timezone Formats
- UTC: `2024-01-01T00:00:00Z`
- UTC with offset: `2024-01-01T00:00:00+00:00`
- Other timezones: `2024-01-01T00:00:00-05:00`

## Updated Tool Signatures

### search_logs
```python
async def search_logs(
    query_text: Optional[str] = None,
    time_filter: Optional[TimeFilter] = None,  # NEW UNIFIED PARAMETER
    start_time: Optional[str] = None,          # DEPRECATED
    end_time: Optional[str] = None,            # DEPRECATED
    levels: Optional[List[str]] = None,
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    max_results: int = 100,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc"
) -> Dict
```

### analyze_logs
```python
async def analyze_logs(
    time_filter: Optional[TimeFilter] = None,  # NEW UNIFIED PARAMETER
    time_range: Optional[str] = None,          # DEPRECATED
    group_by: Optional[str] = "level"
) -> Dict
```

### extract_errors
```python
async def extract_errors(
    time_filter: Optional[TimeFilter] = None,  # NEW UNIFIED PARAMETER
    hours: Optional[int] = None,               # DEPRECATED
    include_stack_traces: bool = True,
    limit: int = 10
) -> Dict
```

### summarize_logs
```python
async def summarize_logs(
    query_text: Optional[str] = None,
    time_filter: Optional[TimeFilter] = None,  # NEW UNIFIED PARAMETER
    start_time: Optional[str] = None,          # DEPRECATED
    end_time: Optional[str] = None,            # DEPRECATED
    levels: Optional[List[str]] = None,
    include_fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    max_results: int = 100,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc"
) -> Dict
```

## Usage Examples

### 1. Using Relative Time Filters

```bash
# Search logs from the last hour
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "error AND payment",
    "time_filter": "1h"
  }'

# Analyze logs from the last 24 hours
curl -X POST http://localhost:8000/api/analyze_logs \
  -H "Content-Type: application/json" \
  -d '{
    "time_filter": "24h",
    "group_by": "level"
  }'

# Extract errors from the last 7 days
curl -X POST http://localhost:8000/api/extract_errors \
  -H "Content-Type: application/json" \
  -d '{
    "time_filter": "7d",
    "limit": 20
  }'
```

### 2. Using Absolute Time Filters

```bash
# Search logs for a specific time range
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "session_id AND callStartPayment",
    "time_filter": ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]
  }'

# Analyze logs for a specific day
curl -X POST http://localhost:8000/api/analyze_logs \
  -H "Content-Type: application/json" \
  -d '{
    "time_filter": ["2024-01-01T00:00:00Z", "2024-01-01T23:59:59Z"],
    "group_by": "service"
  }'
```

### 3. Function-Based Mode with Time Filters

```bash
# Search function calls with time filter
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "session_id AND (\"FunctionCallResult\" OR \"FunctionCalled\")",
    "time_filter": "2h",
    "sort_by": "timestamp",
    "sort_order": "asc"
  }'
```

## Backward Compatibility

The system maintains full backward compatibility with existing parameters:

### Legacy Parameter Support

```bash
# These still work but are deprecated
curl -X POST http://localhost:8000/api/search_logs \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "error",
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-02T00:00:00Z"
  }'

curl -X POST http://localhost:8000/api/extract_errors \
  -H "Content-Type: application/json" \
  -d '{
    "hours": 24
  }'
```

### Parameter Priority

When both new and legacy parameters are provided:
1. `time_filter` takes highest priority
2. `start_time` + `end_time` combination
3. `time_range` parameter
4. `hours` parameter
5. Default range (typically "1d")

## Error Handling

### Invalid Time Filter Examples

```bash
# Invalid relative format
{
  "time_filter": "invalid_format"
}
# Error: "Invalid relative time format: 'invalid_format'. Expected format: number + unit (h/d/w)"

# Invalid absolute format - wrong number of elements
{
  "time_filter": ["2024-01-01T00:00:00Z"]
}
# Error: "Time filter list must have exactly 2 elements (start, end), got 1"

# Invalid timestamps
{
  "time_filter": ["invalid", "timestamps"]
}
# Error: "Invalid ISO timestamp for start_time: 'invalid'"

# End time before start time
{
  "time_filter": ["2024-01-02T00:00:00Z", "2024-01-01T00:00:00Z"]
}
# Error: "Start time must be before end time"
```

## Best Practices

### 1. Use Relative Time for Recent Data
```bash
# Good for monitoring and debugging recent issues
"time_filter": "1h"   # Last hour
"time_filter": "24h"  # Last day
"time_filter": "7d"   # Last week
```

### 2. Use Absolute Time for Historical Analysis
```bash
# Good for specific incident investigation
"time_filter": ["2024-01-15T10:00:00Z", "2024-01-15T14:00:00Z"]
```

### 3. Function-Based Analysis
```bash
# For function call tracing, use ascending order
{
  "query_text": "session_id AND (\"FunctionCallResult\" OR \"FunctionCalled\")",
  "time_filter": "1h",
  "sort_by": "timestamp",
  "sort_order": "asc"
}
```

### 4. Error Investigation
```bash
# Start with recent errors, then expand time range if needed
{
  "time_filter": "1h",
  "levels": ["error", "fatal"]
}
```

## Migration Guide

### Updating Existing Code

**Before (deprecated):**
```bash
{
  "start_time": "2024-01-01T00:00:00Z",
  "end_time": "2024-01-02T00:00:00Z"
}
```

**After (recommended):**
```bash
{
  "time_filter": ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]
}
```

**Before (deprecated):**
```bash
{
  "time_range": "24h"
}
```

**After (recommended):**
```bash
{
  "time_filter": "24h"
}
```

**Before (deprecated):**
```bash
{
  "hours": 12
}
```

**After (recommended):**
```bash
{
  "time_filter": "12h"
}
```

## Technical Implementation

### Type Definition
```python
TimeFilter = Union[str, List[str]]
```

### Validation
- Relative strings: Must match pattern `^\d+[hdw]$`
- Absolute tuples: Must be exactly 2 valid ISO timestamps
- Start time must be before end time
- All timestamps must be valid ISO 8601 format

### Default Behavior
- If no time parameter is provided, defaults to "1d" (last day)
- Legacy parameters are automatically converted to the new format
- All tools now use the unified time processing logic

## Testing

A comprehensive test suite is available in `tests/test_utils.py` that validates:
- Relative time parsing
- ISO timestamp validation
- Time filter parsing
- Legacy parameter conversion
- Error handling
- Edge cases

Run tests with:
```bash
python tests/test_utils.py
```

## Support

For issues or questions about the new time parameter system:
1. Check this documentation first
2. Review the test cases in `tests/test_utils.py`
3. Examine the implementation in `src/utils.py`
4. Test with the examples provided above

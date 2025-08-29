#!/usr/bin/env python3
# Copyright (c) 2025 [Harivatsa G A]. All rights reserved.
# This work is licensed under CC BY-NC-ND 4.0.
# https://creativecommons.org/licenses/by-nc-nd/4.0/
# Attribution required. Commercial use and modifications prohibited.
"""
Time Utilities for Kibana MCP Server

Provides unified time parameter handling with support for both relative time strings
and absolute timestamp tuples.
"""

import datetime
import re
from typing import Any, List, Optional, Tuple, Union
from loguru import logger
from pydantic import BaseModel, Field

# Define the unified time filter type
TimeFilter = Union[str, List[str]]


class TimeRange(BaseModel):
    """Represents a time range with start and end times."""

    start_time: str = Field(..., description="Start time in ISO format")
    end_time: str = Field(..., description="End time in ISO format")

    class Config:
        schema_extra = {
            "example": {
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-02T00:00:00Z",
            }
        }


class RelativeTimeInfo(BaseModel):
    """Information about a relative time string."""

    value: int = Field(..., description="Numeric value")
    unit: str = Field(..., description="Time unit (h, d, w)")
    total_hours: int = Field(..., description="Total hours represented")


def validate_iso_timestamp(timestamp: str) -> bool:
    """
    Validate that a string is a valid ISO timestamp.

    Args:
        timestamp: String to validate

    Returns:
        True if valid ISO timestamp, False otherwise
    """
    try:
        # Try to parse as ISO format
        datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return True
    except (ValueError, AttributeError):
        return False


def parse_relative_time(time_str: str) -> Optional[RelativeTimeInfo]:
    """
    Parse a relative time string like '1h', '24h', '7d', '2w'.

    Args:
        time_str: Relative time string

    Returns:
        RelativeTimeInfo object or None if invalid
    """
    try:
        # Match pattern: number followed by unit (h, d, w)
        pattern = r"^(\d+)([hdw])$"
        match = re.match(pattern, time_str.lower().strip())

        if not match:
            return None

        value = int(match.group(1))
        unit = match.group(2)

        # Calculate total hours
        unit_multipliers = {
            "h": 1,  # hours
            "d": 24,  # days to hours
            "w": 168,  # weeks to hours (7 * 24)
        }

        if unit not in unit_multipliers:
            return None

        total_hours = value * unit_multipliers[unit]

        return RelativeTimeInfo(value=value, unit=unit, total_hours=total_hours)

    except (ValueError, AttributeError) as e:
        logger.debug(f"Failed to parse relative time '{time_str}': {e}")
        return None


def relative_time_to_absolute(
    time_str: str, reference_time: Optional[datetime.datetime] = None
) -> Optional[TimeRange]:
    """
    Convert a relative time string to absolute start and end times.

    Args:
        time_str: Relative time string like '1h', '24h', '7d'
        reference_time: Reference time (defaults to now UTC)

    Returns:
        TimeRange object or None if invalid
    """
    try:
        rel_info = parse_relative_time(time_str)
        if not rel_info:
            return None

        # Use provided reference time or current UTC time
        if reference_time is None:
            reference_time = datetime.datetime.now(datetime.timezone.utc)
        elif reference_time.tzinfo is None:
            # Assume UTC if no timezone info
            reference_time = reference_time.replace(tzinfo=datetime.timezone.utc)

        # Calculate start time by subtracting the relative time
        start_time = reference_time - datetime.timedelta(hours=rel_info.total_hours)
        end_time = reference_time

        return TimeRange(
            start_time=start_time.isoformat(), end_time=end_time.isoformat()
        )

    except Exception as e:
        logger.error(f"Failed to convert relative time '{time_str}' to absolute: {e}")
        return None


def parse_time_filter(time_filter: TimeFilter) -> Optional[TimeRange]:
    """
    Parse a time filter parameter into a TimeRange object.

    Args:
        time_filter: Either a relative time string or list of two ISO timestamps

    Returns:
        TimeRange object or None if invalid
    """
    try:
        if isinstance(time_filter, str):
            # Handle relative time string
            logger.debug(f"Parsing relative time filter: {time_filter}")
            return relative_time_to_absolute(time_filter)

        elif isinstance(time_filter, list):
            # Handle absolute time tuple
            if len(time_filter) != 2:
                logger.error(
                    f"Time filter list must have exactly 2 elements, got {len(time_filter)}"
                )
                return None

            start_time, end_time = time_filter

            # Validate both timestamps
            if not isinstance(start_time, str) or not isinstance(end_time, str):
                logger.error("Time filter list elements must be strings")
                return None

            if not validate_iso_timestamp(start_time) or not validate_iso_timestamp(
                end_time
            ):
                logger.error(
                    f"Invalid ISO timestamps in time filter: [{start_time}, {end_time}]"
                )
                return None

            # Ensure start is before end
            try:
                start_dt = datetime.datetime.fromisoformat(
                    start_time.replace("Z", "+00:00")
                )
                end_dt = datetime.datetime.fromisoformat(
                    end_time.replace("Z", "+00:00")
                )

                if start_dt >= end_dt:
                    logger.error(
                        f"Start time must be before end time: {start_time} >= {end_time}"
                    )
                    return None

            except ValueError as e:
                logger.error(f"Failed to parse timestamps for comparison: {e}")
                return None

            logger.debug(f"Parsing absolute time filter: [{start_time}, {end_time}]")
            return TimeRange(start_time=start_time, end_time=end_time)

        else:
            logger.error(f"Invalid time filter type: {type(time_filter)}")
            return None

    except Exception as e:
        logger.error(f"Failed to parse time filter {time_filter}: {e}")
        return None


def convert_legacy_parameters(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    time_range: Optional[str] = None,
    hours: Optional[int] = None,
) -> Optional[TimeFilter]:
    """
    Convert legacy time parameters to the new unified time_filter format.

    Args:
        start_time: Legacy start time parameter
        end_time: Legacy end time parameter
        time_range: Legacy time range parameter
        hours: Legacy hours parameter

    Returns:
        TimeFilter object or None if no valid parameters
    """
    try:
        # Priority order: start_time+end_time > time_range > hours

        if start_time and end_time:
            # Convert start_time + end_time to absolute tuple
            logger.debug(
                f"Converting legacy start_time/end_time: {start_time}, {end_time}"
            )
            return [start_time, end_time]

        elif time_range:
            # time_range is already in the correct relative format
            logger.debug(f"Converting legacy time_range: {time_range}")
            return time_range

        elif hours is not None:
            # Convert hours to relative string
            logger.debug(f"Converting legacy hours: {hours}")
            return f"{hours}h"

        else:
            return None

    except Exception as e:
        logger.error(f"Failed to convert legacy parameters: {e}")
        return None


def get_time_range_for_query(
    time_filter: Optional[TimeFilter] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    time_range: Optional[str] = None,
    hours: Optional[int] = None,
    default_range: str = "1d",
) -> Optional[TimeRange]:
    """
    Get a TimeRange object for querying, with backward compatibility support.

    Args:
        time_filter: New unified time filter parameter
        start_time: Legacy start time parameter
        end_time: Legacy end time parameter
        time_range: Legacy time range parameter
        hours: Legacy hours parameter
        default_range: Default relative time range if none specified

    Returns:
        TimeRange object or None if invalid
    """
    try:
        # If time_filter is provided, use it directly
        if time_filter is not None:
            logger.debug(f"Using time_filter parameter: {time_filter}")
            return parse_time_filter(time_filter)

        # Otherwise, try to convert legacy parameters
        legacy_filter = convert_legacy_parameters(
            start_time, end_time, time_range, hours
        )
        if legacy_filter is not None:
            logger.debug(f"Using converted legacy parameters: {legacy_filter}")
            return parse_time_filter(legacy_filter)

        # Fall back to default range
        logger.debug(f"Using default range: {default_range}")
        return parse_time_filter(default_range)

    except Exception as e:
        logger.error(f"Failed to get time range for query: {e}")
        return None


def validate_time_filter_input(time_filter: Any) -> Tuple[bool, str]:
    """
    Validate time_filter input and return validation result.

    Args:
        time_filter: Input to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if time_filter is None:
            return True, ""  # None is acceptable (will use default)

        if isinstance(time_filter, str):
            # Validate relative time string
            rel_info = parse_relative_time(time_filter)
            if rel_info is None:
                return (
                    False,
                    f"Invalid relative time format: '{time_filter}'. Expected format: number + unit (h/d/w), e.g., '1h', '24h', '7d', '2w'",
                )
            return True, ""

        elif isinstance(time_filter, list):
            # Validate absolute time tuple
            if len(time_filter) != 2:
                return (
                    False,
                    f"Time filter list must have exactly 2 elements (start, end), got {len(time_filter)}",
                )

            start_time, end_time = time_filter

            if not isinstance(start_time, str) or not isinstance(end_time, str):
                return (
                    False,
                    "Time filter list elements must be strings (ISO timestamps)",
                )

            if not validate_iso_timestamp(start_time):
                return False, f"Invalid ISO timestamp for start_time: '{start_time}'"

            if not validate_iso_timestamp(end_time):
                return False, f"Invalid ISO timestamp for end_time: '{end_time}'"

            # Check chronological order
            try:
                start_dt = datetime.datetime.fromisoformat(
                    start_time.replace("Z", "+00:00")
                )
                end_dt = datetime.datetime.fromisoformat(
                    end_time.replace("Z", "+00:00")
                )

                if start_dt >= end_dt:
                    return (
                        False,
                        f"Start time must be before end time: '{start_time}' >= '{end_time}'",
                    )

            except ValueError as e:
                return False, f"Failed to parse timestamps: {e}"

            return True, ""

        else:
            return (
                False,
                f"Invalid time_filter type: {type(time_filter)}. Expected string (relative) or list of 2 strings (absolute timestamps)",
            )

    except Exception as e:
        return False, f"Validation error: {e}"


# Example usage and testing functions
def example_usage():
    """
    Example usage of the time utilities.
    """
    print("=== Time Utils Example Usage ===")

    # Test relative time parsing
    rel_examples = ["1h", "24h", "7d", "2w", "invalid"]
    print("\nRelative time parsing:")
    for rel_time in rel_examples:
        result = parse_relative_time(rel_time)
        print(f"  {rel_time} -> {result}")

    # Test time filter parsing
    filter_examples = [
        "1h",
        "24h",
        "7d",
        ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
        ["invalid", "timestamps"],
        "invalid_format",
    ]
    print("\nTime filter parsing:")
    for time_filter in filter_examples:
        result = parse_time_filter(time_filter)
        print(f"  {time_filter} -> {result}")

    # Test validation
    print("\nValidation results:")
    for time_filter in filter_examples:
        is_valid, error = validate_time_filter_input(time_filter)
        print(f"  {time_filter} -> Valid: {is_valid}, Error: {error}")


if __name__ == "__main__":
    example_usage()

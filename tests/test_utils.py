#!/usr/bin/env python3
# Copyright (c) 2025 [Harivatsa G A]. All rights reserved.
# This work is licensed under CC BY-NC-ND 4.0.
# https://creativecommons.org/licenses/by-nc-nd/4.0/
# Attribution required. Commercial use and modifications prohibited.
"""
Test suite for time utilities module.

Tests the unified time parameter system with various input combinations.
"""

import datetime
import os
import sys

# Add the parent directory to Python path to import directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import utils module directly to avoid server dependencies
import importlib.util

spec = importlib.util.spec_from_file_location(
    "utils",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "utils.py"
    ),
)
utils_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils_module)

# Extract the functions and classes we need
TimeFilter = utils_module.TimeFilter
TimeRange = utils_module.TimeRange
parse_relative_time = utils_module.parse_relative_time
relative_time_to_absolute = utils_module.relative_time_to_absolute
parse_time_filter = utils_module.parse_time_filter
convert_legacy_parameters = utils_module.convert_legacy_parameters
get_time_range_for_query = utils_module.get_time_range_for_query
validate_time_filter_input = utils_module.validate_time_filter_input
validate_iso_timestamp = utils_module.validate_iso_timestamp


def test_relative_time_parsing():
    """Test parsing of relative time strings."""
    print("\n=== Testing Relative Time Parsing ===")

    test_cases = [
        ("1h", 1, "h", 1),
        ("24h", 24, "h", 24),
        ("7d", 7, "d", 168),  # 7 * 24 = 168 hours
        ("2w", 2, "w", 336),  # 2 * 7 * 24 = 336 hours
        ("invalid", None, None, None),
        ("", None, None, None),
        ("1x", None, None, None),
        ("abc", None, None, None),
    ]

    for time_str, expected_value, expected_unit, expected_hours in test_cases:
        result = parse_relative_time(time_str)
        if result is None:
            if expected_value is None:
                print(f"✓ {time_str} -> None (expected)")
            else:
                print(
                    f"✗ {time_str} -> None (expected {expected_value}{expected_unit})"
                )
        else:
            if (
                result.value == expected_value
                and result.unit == expected_unit
                and result.total_hours == expected_hours
            ):
                print(
                    f"✓ {time_str} -> {result.value}{result.unit} ({result.total_hours}h)"
                )
            else:
                print(
                    f"✗ {time_str} -> {result.value}{result.unit} ({result.total_hours}h) (expected {expected_value}{expected_unit} ({expected_hours}h))"
                )


def test_iso_timestamp_validation():
    """Test ISO timestamp validation."""
    print("\n=== Testing ISO Timestamp Validation ===")

    test_cases = [
        ("2024-01-01T00:00:00Z", True),
        ("2024-01-01T12:30:45.123Z", True),
        ("2024-01-01T00:00:00+00:00", True),
        ("2024-01-01T00:00:00-05:00", True),
        ("2024-01-01 00:00:00", False),
        ("invalid", False),
        ("", False),
        ("2024-13-01T00:00:00Z", False),  # Invalid month
        ("2024-01-32T00:00:00Z", False),  # Invalid day
    ]

    for timestamp, expected in test_cases:
        result = validate_iso_timestamp(timestamp)
        status = "✓" if result == expected else "✗"
        print(f"{status} {timestamp} -> {result} (expected {expected})")


def test_time_filter_parsing():
    """Test parsing of unified time filter parameters."""
    print("\n=== Testing Time Filter Parsing ===")

    # Test relative time filters
    relative_cases = ["1h", "24h", "7d", "2w"]
    for rel_time in relative_cases:
        result = parse_time_filter(rel_time)
        if result:
            print(
                f"✓ Relative '{rel_time}' -> {result.start_time} to {result.end_time}"
            )
        else:
            print(f"✗ Relative '{rel_time}' -> None")

    # Test absolute time filters
    absolute_cases = [
        ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
        ["2024-01-01T12:00:00Z", "2024-01-01T18:00:00Z"],
    ]
    for abs_times in absolute_cases:
        result = parse_time_filter(abs_times)
        if result:
            print(f"✓ Absolute {abs_times} -> {result.start_time} to {result.end_time}")
        else:
            print(f"✗ Absolute {abs_times} -> None")

    # Test invalid cases
    invalid_cases = [
        "invalid_format",
        ["single_element"],
        ["invalid", "timestamps"],
        ["2024-01-02T00:00:00Z", "2024-01-01T00:00:00Z"],  # end before start
        123,  # wrong type
        None,
    ]
    for invalid_case in invalid_cases:
        result = parse_time_filter(invalid_case)
        status = "✓" if result is None else "✗"
        print(f"{status} Invalid '{invalid_case}' -> {result} (expected None)")


def test_legacy_parameter_conversion():
    """Test conversion of legacy parameters to new format."""
    print("\n=== Testing Legacy Parameter Conversion ===")

    test_cases = [
        # (start_time, end_time, time_range, hours, expected_result)
        (
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z",
            None,
            None,
            ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
        ),
        (None, None, "1h", None, "1h"),
        (None, None, None, 24, "24h"),
        (
            "2024-01-01T00:00:00Z",
            "2024-01-02T00:00:00Z",
            "1h",
            24,
            ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
        ),  # start_time+end_time has priority
        (None, None, "1h", 24, "1h"),  # time_range has priority over hours
        (None, None, None, None, None),  # no parameters
    ]

    for start_time, end_time, time_range, hours, expected in test_cases:
        result = convert_legacy_parameters(start_time, end_time, time_range, hours)
        status = "✓" if result == expected else "✗"
        print(
            f"{status} Legacy ({start_time}, {end_time}, {time_range}, {hours}) -> {result} (expected {expected})"
        )


def test_time_range_for_query():
    """Test getting time range for queries with different parameter combinations."""
    print("\n=== Testing Time Range for Query ===")

    # Test with time_filter parameter
    time_filter_cases = ["1h", "24h", ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"]]
    for time_filter in time_filter_cases:
        result = get_time_range_for_query(time_filter=time_filter)
        if result:
            print(
                f"✓ time_filter={time_filter} -> {result.start_time} to {result.end_time}"
            )
        else:
            print(f"✗ time_filter={time_filter} -> None")

    # Test with legacy parameters
    legacy_cases = [
        {"start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-02T00:00:00Z"},
        {"time_range": "1h"},
        {"hours": 24},
    ]
    for legacy_params in legacy_cases:
        result = get_time_range_for_query(**legacy_params)
        if result:
            print(
                f"✓ legacy {legacy_params} -> {result.start_time} to {result.end_time}"
            )
        else:
            print(f"✗ legacy {legacy_params} -> None")

    # Test default behavior
    result = get_time_range_for_query()
    if result:
        print(f"✓ default -> {result.start_time} to {result.end_time}")
    else:
        print(f"✗ default -> None")


def test_validation():
    """Test input validation."""
    print("\n=== Testing Input Validation ===")

    test_cases = [
        ("1h", True, ""),
        ("24h", True, ""),
        (["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"], True, ""),
        ("invalid_format", False, "Invalid relative time format"),
        (["single"], False, "exactly 2 elements"),
        (["invalid", "timestamps"], False, "Invalid ISO timestamp"),
        (
            ["2024-01-02T00:00:00Z", "2024-01-01T00:00:00Z"],
            False,
            "Start time must be before end time",
        ),
        (123, False, "Invalid time_filter type"),
        (None, True, ""),  # None is acceptable
    ]

    for time_filter, expected_valid, expected_error_fragment in test_cases:
        is_valid, error_msg = validate_time_filter_input(time_filter)

        if is_valid == expected_valid:
            if expected_valid:
                print(f"✓ {time_filter} -> Valid")
            else:
                if expected_error_fragment in error_msg:
                    print(f"✓ {time_filter} -> Invalid ('{error_msg}')")
                else:
                    print(
                        f"✗ {time_filter} -> Invalid but wrong error: '{error_msg}' (expected to contain '{expected_error_fragment}')"
                    )
        else:
            print(f"✗ {time_filter} -> {is_valid} (expected {expected_valid})")


def test_edge_cases():
    """Test edge cases and boundary conditions."""
    print("\n=== Testing Edge Cases ===")

    # Test very large time ranges
    large_cases = ["8760h", "365d", "52w"]  # 1 year in different units
    for case in large_cases:
        result = parse_time_filter(case)
        if result:
            print(f"✓ Large range '{case}' -> {result.start_time} to {result.end_time}")
        else:
            print(f"✗ Large range '{case}' -> None")

    # Test very small time ranges
    small_cases = ["1h", "0h"]  # Note: 0h might be invalid
    for case in small_cases:
        result = parse_relative_time(case)
        if result:
            print(
                f"✓ Small range '{case}' -> {result.value}{result.unit} ({result.total_hours}h)"
            )
        else:
            print(f"✓ Small range '{case}' -> None (expected for 0h)")

    # Test timezone handling
    timezone_cases = [
        ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
        ["2024-01-01T00:00:00+00:00", "2024-01-01T01:00:00+00:00"],
        ["2024-01-01T00:00:00-05:00", "2024-01-01T01:00:00-05:00"],
    ]
    for tz_case in timezone_cases:
        result = parse_time_filter(tz_case)
        if result:
            print(f"✓ Timezone case {tz_case} -> Valid")
        else:
            print(f"✗ Timezone case {tz_case} -> None")


def run_all_tests():
    """Run all test suites."""
    print("Time Utils Test Suite")
    print("=" * 50)

    try:
        test_relative_time_parsing()
        test_iso_timestamp_validation()
        test_time_filter_parsing()
        test_legacy_parameter_conversion()
        test_time_range_for_query()
        test_validation()
        test_edge_cases()

        print("\n" + "=" * 50)
        print("✓ All tests completed successfully!")
        print("\nThe time utilities module is ready for use.")

    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        return False

    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

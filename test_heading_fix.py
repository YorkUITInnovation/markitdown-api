#!/usr/bin/env python3

from classes.services import _enhance_heading_detection
import re

def test_heading_detection():
    """Test the fixed heading detection with problematic text"""

    # Sample text that was being incorrectly converted to headers
    test_content = """# HUMA 1740

The Roots of Modern Canada

Prof. Dr. Donald Ipperciel

Course Information

Course Director: Prof. Dr. Donald Ipperciel

Email: donald.ipperciel@yorku.ca

Semester: Fall 2024 and Winter 2025 (September 2024 to April 2025)

Lecture time & day: Thursdays, 4:30 PM to 6:15 PM

Zoom (Lecture): https://yorku.zoom.us/j/99781365712

Course Description

This course explores the ideas and events that shaped Canada and the modes of expression that embodied them over the centuries.

Learning Outcomes

To better understand current Canadian issues and debates"""

    print("TESTING HEADING DETECTION FIX")
    print("=" * 50)

    print("\nORIGINAL CONTENT:")
    print("-" * 20)
    print(test_content)

    print("\nDEBUGGING LINE BY LINE:")
    print("-" * 20)
    lines = test_content.split('\n')
    for i, line in enumerate(lines):
        if line.strip() in ["Course Information", "Course Description", "Learning Outcomes"]:
            prev_line = lines[i-1].strip() if i > 0 else ""
            next_line = lines[i+1].strip() if i < len(lines)-1 else ""
            print(f"Line {i}: '{line.strip()}'")
            print(f"  Prev: '{prev_line}'")
            print(f"  Next: '{next_line}'")
            print(f"  Prev empty: {prev_line == ''}")

            # Test different regex patterns
            old_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$'
            new_pattern = r'^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*$'
            simple_pattern = r'^[A-Z][a-zA-Z\s]+$'

            print(f"  Old pattern match: {bool(re.match(old_pattern, line.strip()))}")
            print(f"  New pattern match: {bool(re.match(new_pattern, line.strip()))}")
            print(f"  Simple pattern match: {bool(re.match(simple_pattern, line.strip()))}")
            print(f"  In academic list: {line.strip().lower() in ['course information', 'course description', 'learning outcomes']}")

            # Test exclusion patterns
            exclusion_patterns = [
                r'^(Prof\.?|Dr\.?|Mr\.?|Ms\.?|Mrs\.?)\s+',
                r'.*@.*\..*',
                r'.*(https?://|www\.|\.com|\.org|\.net)',
                r'^(Phone|Tel|Email|Fax|Address|Office):?\s*',
                r'^(Course|Class|Section|Semester|Room|Time|Day|Location):?\s*',
                r'^[^:]{1,30}:\s*',
                r'.*(phone|email|office|room|building|semester|lecture|tutorial|lab).*',
                r'.*(zoom|meeting|conference).*',
                r'^[A-Z][a-z]+\s+\d{4}',
                r'^\d+:\d+\s*(AM|PM)',
                r'^[A-Z][a-z]+,\s*\d',
            ]

            excluded_by = []
            for j, pattern in enumerate(exclusion_patterns):
                if re.search(pattern, line.strip(), re.IGNORECASE):
                    excluded_by.append(f"Pattern {j+1}: {pattern}")

            if excluded_by:
                print(f"  ❌ EXCLUDED BY: {excluded_by}")
            else:
                print(f"  ✅ NOT EXCLUDED")

            print()

    print("\nPROCESSED CONTENT:")
    print("-" * 20)
    result = _enhance_heading_detection(test_content)
    print(result)

    print("\nANALYSIS:")
    print("-" * 20)

    # Check specific items that should NOT be headers
    should_not_be_headers = [
        "Prof. Dr. Donald Ipperciel",
        "Course Director: Prof. Dr. Donald Ipperciel",
        "Email: donald.ipperciel@yorku.ca",
        "Zoom (Lecture):"
    ]

    for item in should_not_be_headers:
        if f"# {item}" in result:
            print(f"❌ PROBLEM: '{item}' is still being treated as a header")
        else:
            print(f"✅ FIXED: '{item}' is correctly NOT a header")

    # Check items that SHOULD be headers
    should_be_headers = [
        "Course Information",
        "Course Description",
        "Learning Outcomes"
    ]

    for item in should_be_headers:
        if f"# {item}" in result:
            print(f"✅ CORRECT: '{item}' is properly detected as a header")
        else:
            print(f"❌ ISSUE: '{item}' should be a header but isn't")

if __name__ == "__main__":
    test_heading_detection()

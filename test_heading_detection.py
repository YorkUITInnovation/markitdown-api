#!/usr/bin/env python3
"""
Test script to debug heading detection functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from classes.services import _enhance_heading_detection

def test_heading_detection():
    """Test various heading patterns"""

    # Test cases for different heading types
    test_cases = [
        # Case 1: Simple title
        ("Document Title\n\nThis is some content.", "Word document title"),

        # Case 2: ALL CAPS title
        ("INTRODUCTION\n\nThis chapter covers...", "All caps title"),

        # Case 3: Title Case
        ("Chapter One Overview\n\nContent follows here.", "Title case"),

        # Case 4: Numbered section
        ("1. Getting Started\n\nFirst, you need to...", "Numbered section"),

        # Case 5: Bold title
        ("**Important Section**\n\nThis section is crucial.", "Bold title"),

        # Case 6: Underlined title
        ("Main Topic\n=========\n\nContent here.", "Underlined title"),

        # Case 7: Real Word document example
        ("Executive Summary\n\nThis document outlines the key findings from our research.", "Real example"),

        # Case 8: Multiple lines
        ("First Title\n\nSome content here.\n\nSecond Title\n\nMore content.", "Multiple titles"),
    ]

    print("Testing heading detection patterns...")
    print("=" * 50)

    for i, (content, description) in enumerate(test_cases, 1):
        print(f"\nTest {i}: {description}")
        print(f"Input:\n{repr(content)}")

        result = _enhance_heading_detection(content)
        print(f"Output:\n{repr(result)}")

        # Check if any headings were detected
        if result.count('# ') > content.count('# '):
            print("✅ Heading detected!")
        else:
            print("❌ No heading detected")
        print("-" * 30)

if __name__ == "__main__":
    test_heading_detection()

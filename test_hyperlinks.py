#!/usr/bin/env python3
"""
Test script to verify hyperlink conversion functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from classes.services import _convert_hyperlinks_to_markdown

def test_hyperlink_conversions():
    """Test various hyperlink conversion scenarios"""

    print("Testing hyperlink conversion functionality...")
    print("=" * 50)

    # Test 1: HTML anchor tags
    html_content = '''
    Here's a link to our website: <a href="https://example.com">Example Website</a>
    And another one: <a href="https://docs.example.com/api">API Documentation</a>
    '''

    print("Test 1: HTML anchor tags")
    print("Input:", html_content.strip())
    result1 = _convert_hyperlinks_to_markdown(html_content)
    print("Output:", result1.strip())
    print()

    # Test 2: Bare URLs
    url_content = '''
    Visit our website at https://example.com for more information.
    You can also check out www.github.com/microsoft/markitdown
    '''

    print("Test 2: Bare URLs")
    print("Input:", url_content.strip())
    result2 = _convert_hyperlinks_to_markdown(url_content)
    print("Output:", result2.strip())
    print()

    # Test 3: Email addresses
    email_content = '''
    Contact us at support@example.com or info@company.org
    '''

    print("Test 3: Email addresses")
    print("Input:", email_content.strip())
    result3 = _convert_hyperlinks_to_markdown(email_content)
    print("Output:", result3.strip())
    print()

    # Test 4: Mixed content
    mixed_content = '''
    # Document Title
    
    For more information, visit <a href="https://docs.example.com">our documentation</a>.
    
    You can also:
    - Check our website: https://example.com
    - Email us at contact@example.com
    - Visit our GitHub: www.github.com/example/project
    '''

    print("Test 4: Mixed content")
    print("Input:", mixed_content.strip())
    result4 = _convert_hyperlinks_to_markdown(mixed_content)
    print("Output:", result4.strip())
    print()

    print("All tests completed!")

if __name__ == "__main__":
    test_hyperlink_conversions()

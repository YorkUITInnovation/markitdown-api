#!/usr/bin/env python3
"""
Test script to debug PDF hyperlink conversion
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from markitdown import MarkItDown
from classes.services import _convert_hyperlinks_to_markdown

def test_pdf_conversion():
    """Test what content is extracted from test.pdf"""

    pdf_path = "test.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print("Testing PDF conversion...")
    print("=" * 50)

    # Initialize MarkItDown
    md = MarkItDown()

    try:
        # Convert PDF to markdown
        result = md.convert(pdf_path)
        content = result.text_content

        print("Raw content extracted from PDF:")
        print("-" * 30)
        print(content[:1000] + "..." if len(content) > 1000 else content)
        print("-" * 30)

        # Check if content contains any URLs or hyperlinks
        import re

        # Look for URLs
        url_pattern = r'https?://[\w\-._~:/?#[\]@!$&\'()*+,;=]+'
        urls = re.findall(url_pattern, content)
        print(f"Found URLs: {urls}")

        # Look for HTML anchor tags
        html_pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        html_links = re.findall(html_pattern, content, re.IGNORECASE)
        print(f"Found HTML links: {html_links}")

        # Look for www. patterns
        www_pattern = r'www\.[\w\-._~:/?#[\]@!$&\'()*+,;=]+'
        www_links = re.findall(www_pattern, content)
        print(f"Found www links: {www_links}")

        # Look for email addresses
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, content)
        print(f"Found emails: {emails}")

        print("\nApplying hyperlink conversion...")
        converted_content = _convert_hyperlinks_to_markdown(content)

        print("Converted content:")
        print("-" * 30)
        print(converted_content[:1000] + "..." if len(converted_content) > 1000 else converted_content)
        print("-" * 30)

        if content == converted_content:
            print("⚠️  No changes made during hyperlink conversion")
        else:
            print("✅ Hyperlinks were converted!")

    except Exception as e:
        print(f"Error converting PDF: {e}")

if __name__ == "__main__":
    test_pdf_conversion()

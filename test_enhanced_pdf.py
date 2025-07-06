#!/usr/bin/env python3
"""
Test the enhanced PDF hyperlink extraction
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from classes.services import _extract_pdf_hyperlinks, _integrate_pdf_hyperlinks

def test_enhanced_pdf_extraction():
    """Test the new PDF hyperlink extraction functionality"""

    pdf_path = "test.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print("Testing enhanced PDF hyperlink extraction...")
    print("=" * 60)

    # Extract hyperlinks from PDF
    print("Step 1: Extracting hyperlinks from PDF...")
    hyperlinks = _extract_pdf_hyperlinks(pdf_path)

    if hyperlinks:
        print(f"✅ Found {len(hyperlinks)} hyperlinks in PDF:")
        for url, data in hyperlinks.items():
            print(f"  → {url}")
            print(f"    Page: {data.get('page', 'unknown')}")
            if 'rect' in data:
                print(f"    Position: {data['rect']}")
    else:
        print("⚠️  No hyperlinks found in PDF")

    # Test with sample content
    print("\nStep 2: Testing hyperlink integration...")
    sample_content = """
    When King Pyrrhus invaded Italy, having viewed and considered the order of the army.
    
    In that part of it where Villegaignon landed, which he called Antarctic France.
    """

    print("Original content:")
    print(sample_content)

    integrated_content = _integrate_pdf_hyperlinks(sample_content, hyperlinks)

    print("\nIntegrated content:")
    print(integrated_content)

    if sample_content != integrated_content:
        print("✅ Successfully integrated hyperlinks!")
    else:
        print("⚠️  No changes made - hyperlinks may not have been matched")

if __name__ == "__main__":
    test_enhanced_pdf_extraction()

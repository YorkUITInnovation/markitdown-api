#!/usr/bin/env python3
"""
Test the actual API conversion to debug the hyperlink issue
"""

import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from classes.services import convert_file

async def test_api_conversion():
    """Test the actual API conversion process"""

    pdf_path = "test.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print("Testing full API conversion process...")
    print("=" * 60)

    try:
        # Use the actual convert_file function
        result = await convert_file(pdf_path)

        print("Conversion successful!")
        print(f"Filename: {result.filename}")
        print(f"Content length: {len(result.content)} characters")
        print(f"Images found: {len(result.images)}")

        # Look for hyperlinks in the converted content
        content = result.content

        # Check for Pyrrhus
        if "[Pyrrhus]" in content:
            print("✅ Found Pyrrhus as a hyperlink!")
            # Extract the line containing Pyrrhus
            lines = content.split('\n')
            for line in lines:
                if "Pyrrhus" in line:
                    print(f"  → {line.strip()}")
                    break
        else:
            print("❌ Pyrrhus not found as hyperlink")
            if "Pyrrhus" in content:
                print("  → Found as plain text")

        # Check for Villegaignon
        if "[Villegaignon]" in content:
            print("✅ Found Villegaignon as a hyperlink!")
            # Extract the line containing Villegaignon
            lines = content.split('\n')
            for line in lines:
                if "Villegaignon" in line:
                    print(f"  → {line.strip()}")
                    break
        else:
            print("❌ Villegaignon not found as hyperlink")
            if "Villegaignon" in content:
                print("  → Found as plain text")

        # Show first few lines of content
        print("\nFirst 500 characters of converted content:")
        print("-" * 40)
        print(content[:500])
        print("-" * 40)

    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_conversion())

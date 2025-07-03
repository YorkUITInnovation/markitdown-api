#!/usr/bin/env python3

from markitdown import MarkItDown
import tempfile
import os

# Test CSV conversion
def test_csv_conversion():
    md = MarkItDown()

    # Create a test CSV file
    csv_content = """Name,Age,City
John,30,New York
Jane,25,Los Angeles
Bob,35,Chicago"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        temp_path = f.name

    try:
        result = md.convert(temp_path)
        print("✅ CSV conversion successful!")
        print("Converted content:")
        print(result.text_content)
        return True
    except Exception as e:
        print(f"❌ CSV conversion failed: {e}")
        return False
    finally:
        os.unlink(temp_path)

if __name__ == "__main__":
    test_csv_conversion()

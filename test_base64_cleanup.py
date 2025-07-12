import asyncio
import os
from classes.services import convert_file

async def test_base64_cleanup():
    """Test base64 cleanup with syllabus.docx"""
    file_path = "syllabus.docx"

    if not os.path.exists(file_path):
        print(f"ERROR: File {file_path} not found")
        return

    print(f"Testing base64 cleanup with {file_path}")

    try:
        result = await convert_file(file_path, create_pages=False)

        print(f"Conversion completed. Content length: {len(result.content)}")
        print(f"Number of images extracted: {len(result.images)}")

        # Check for base64 in the content
        if 'base64' in result.content.lower():
            print("❌ FAILED: base64 still found in content!")

            # Find and show the lines containing base64
            lines = result.content.split('\n')
            for i, line in enumerate(lines):
                if 'base64' in line.lower():
                    print(f"Line {i+1}: {line[:150]}...")
        else:
            print("✅ SUCCESS: No base64 found in content!")

        # Also check for data:image
        if 'data:image' in result.content.lower():
            print("❌ FAILED: data:image still found in content!")

            # Find and show the lines containing data:image
            lines = result.content.split('\n')
            for i, line in enumerate(lines):
                if 'data:image' in line.lower():
                    print(f"Line {i+1}: {line[:150]}...")
        else:
            print("✅ SUCCESS: No data:image found in content!")

        # Save content to file for inspection
        with open('test_output.md', 'w', encoding='utf-8') as f:
            f.write(result.content)
        print("Content saved to test_output.md for inspection")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_base64_cleanup())

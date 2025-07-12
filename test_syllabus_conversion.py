#!/usr/bin/env python3

import asyncio
from classes.services import convert_file

async def test_syllabus_conversion():
    """Convert syllabus.docx and save results to test_output_docx.md"""
    try:
        print("Converting syllabus.docx...")
        result = await convert_file('syllabus.docx', create_pages=True)

        print("CONVERSION SUCCESSFUL!")

        # Save the markdown content to test_output_docx.md
        output_file = 'test_output_docx.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result.content)

        print(f"Markdown content saved to: {output_file}")
        print("=" * 80)
        print("MARKDOWN CONTENT:")
        print("=" * 80)
        print(result.content)
        print("=" * 80)
        print(f"Total images extracted: {len(result.images)}")

        if result.images:
            print("\nExtracted images:")
            for img in result.images:
                print(f"  - {img.filename}: {img.url}")

        print(f"\nConversion completed successfully!")
        print(f"Output saved to: {output_file}")

    except Exception as e:
        print(f"ERROR during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_syllabus_conversion())

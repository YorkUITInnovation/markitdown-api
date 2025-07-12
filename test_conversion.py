#!/usr/bin/env python3
"""
Test script to verify the enhanced image positioning system
"""
import asyncio
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from classes.services import convert_file

async def test_conversion():
    try:
        print("Starting test conversion...")

        # Test with the DOCX file
        result = await convert_file('syllabus.docx', create_pages=False)

        print(f'Conversion completed successfully!')
        print(f'Filename: {result.filename}')
        print(f'Content length: {len(result.content)} characters')
        print(f'Number of images extracted: {len(result.images)}')

        if result.images:
            print('\nExtracted images:')
            for i, img in enumerate(result.images, 1):
                print(f'  {i}. {img.filename}')
                print(f'     Page: {img.page_number}')
                print(f'     Position: ({img.position_x}, {img.position_y})')
                print(f'     URL: {img.url}')
                if img.content_context:
                    print(f'     Context: {img.content_context[:100]}...')
                print()

        # Write the result to test_output_docx.md
        with open('test_output_docx.md', 'w', encoding='utf-8') as f:
            f.write(result.content)

        print('Output saved to test_output_docx.md')

        # Show a preview of the content
        lines = result.content.split('\n')
        print(f'\nContent preview (first 30 lines):')
        for i, line in enumerate(lines[:30], 1):
            print(f'{i:2d}: {line}')

        if len(lines) > 30:
            print(f'... ({len(lines) - 30} more lines)')

    except Exception as e:
        print(f'Error during conversion: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_conversion())

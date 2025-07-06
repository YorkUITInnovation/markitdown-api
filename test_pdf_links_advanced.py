#!/usr/bin/env python3
"""
Advanced PDF hyperlink extraction test
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from markitdown import MarkItDown
from classes.services import _convert_hyperlinks_to_markdown

def test_pdf_with_links():
    """Test PDF with embedded hyperlinks"""

    pdf_path = "test.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print("Testing PDF with embedded hyperlinks...")
    print("=" * 60)

    # Initialize MarkItDown
    md = MarkItDown()

    try:
        # Convert PDF to markdown
        result = md.convert(pdf_path)
        content = result.text_content

        print("Raw content extracted from PDF:")
        print("-" * 40)
        print(content)
        print("-" * 40)

        # Look for the specific words that should have hyperlinks
        test_words = ["Pyrrhus", "Villegaignon"]

        for word in test_words:
            if word in content:
                print(f"✅ Found '{word}' in content")

                # Check if it's already a link
                if f"[{word}]" in content or f"({word})" in content:
                    print(f"   → '{word}' appears to be already formatted as a link")
                else:
                    print(f"   → '{word}' is plain text (hyperlink not extracted)")
            else:
                print(f"❌ '{word}' not found in content")

        print("\nApplying hyperlink conversion...")
        converted_content = _convert_hyperlinks_to_markdown(content)

        print("Converted content:")
        print("-" * 40)
        print(converted_content)
        print("-" * 40)

        if content == converted_content:
            print("⚠️  No changes made during hyperlink conversion")
            print("    This suggests the hyperlinks are not being extracted as text URLs")
        else:
            print("✅ Hyperlinks were converted!")

    except Exception as e:
        print(f"Error converting PDF: {e}")
        import traceback
        traceback.print_exc()

def test_with_pyPDF2():
    """Try extracting hyperlinks using PyPDF2"""
    try:
        import PyPDF2

        print("\nTesting with PyPDF2 for hyperlink extraction...")
        print("-" * 50)

        with open("test.pdf", "rb") as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            for page_num, page in enumerate(pdf_reader.pages):
                print(f"\nPage {page_num + 1}:")

                # Extract text
                text = page.extract_text()

                # Check for annotations (hyperlinks)
                if "/Annots" in page:
                    annotations = page["/Annots"]
                    if annotations:
                        print(f"  Found {len(annotations)} annotations")
                        for annotation in annotations:
                            annotation_obj = annotation.get_object()
                            if "/A" in annotation_obj:
                                action = annotation_obj["/A"]
                                if "/URI" in action:
                                    uri = action["/URI"]
                                    print(f"  → Found hyperlink: {uri}")

                                    # Try to find the associated text
                                    if "/Rect" in annotation_obj:
                                        rect = annotation_obj["/Rect"]
                                        print(f"    Position: {rect}")
                    else:
                        print("  No annotations found")
                else:
                    print("  No /Annots key found")

    except ImportError:
        print("PyPDF2 not installed. Installing...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "PyPDF2"])
        test_with_pyPDF2()
    except Exception as e:
        print(f"Error with PyPDF2: {e}")

def test_with_pdfplumber():
    """Try extracting hyperlinks using pdfplumber"""
    try:
        import pdfplumber

        print("\nTesting with pdfplumber for hyperlink extraction...")
        print("-" * 50)

        with pdfplumber.open("test.pdf") as pdf:
            for page_num, page in enumerate(pdf.pages):
                print(f"\nPage {page_num + 1}:")

                # Extract hyperlinks
                if hasattr(page, 'hyperlinks'):
                    hyperlinks = page.hyperlinks
                    if hyperlinks:
                        print(f"  Found {len(hyperlinks)} hyperlinks")
                        for link in hyperlinks:
                            print(f"  → {link}")
                    else:
                        print("  No hyperlinks found")

                # Extract annotations
                if hasattr(page, 'annots'):
                    annotations = page.annots
                    if annotations:
                        print(f"  Found {len(annotations)} annotations")
                        for annot in annotations:
                            print(f"  → {annot}")
                    else:
                        print("  No annotations found")

    except ImportError:
        print("pdfplumber not installed. Installing...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "pdfplumber"])
        test_with_pdfplumber()
    except Exception as e:
        print(f"Error with pdfplumber: {e}")

if __name__ == "__main__":
    test_pdf_with_links()
    test_with_pyPDF2()
    test_with_pdfplumber()

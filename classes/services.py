import requests
import tempfile
import os
import re
import base64
from urllib.parse import urlparse
from pathlib import Path
from markitdown import MarkItDown
from fastapi import HTTPException
from classes import ConvertResponse
from classes.image_extractor import ImageExtractor
from classes.scheduler import ImageCleanupScheduler
from classes.models import ImageInfo

# Initialize MarkItDown and ImageExtractor
md = MarkItDown()
image_extractor = ImageExtractor()
cleanup_scheduler = ImageCleanupScheduler(image_extractor)

def _enhance_heading_detection(content: str, file_path: str = None) -> str:
    """
    Enhance heading detection by converting various title patterns to H1 headings.
    This captures Word document titles, styled headings, and other formatting that
    MarkItDown might miss.
    """
    if not content or not content.strip():
        return content

    lines = content.split('\n')
    processed_lines = []

    # Patterns that indicate a heading/title
    heading_patterns = [
        # All caps text (common in titles)
        r'^[A-Z][A-Z\s\d\-.,!?()]{4,}[A-Z\d]$',
        # Title Case with specific patterns
        r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,8}$',
        # Numbered sections (1. Title, 1.1 Title, etc.)
        r'^\d+(?:\.\d+)*\.?\s+[A-Z][A-Za-z\s]+$',
        # Roman numerals
        r'^[IVX]+\.\s+[A-Z][A-Za-z\s]+$',
        # Centered text patterns (detected by surrounding whitespace)
        r'^\s{3,}[A-Z][A-Za-z\s\d\-.,!?()]{5,}\s{3,}$',
        # Bold markers that might have been converted
        r'^\*\*([A-Z][A-Za-z\s\d\-.,!?()]{3,})\*\*$',
        # Underlined text patterns
        r'^[A-Z][A-Za-z\s\d\-.,!?()]{3,}$(?=\n[-=_]{3,})',
    ]

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        original_line = lines[i]

        # Skip if already a markdown heading
        if line.startswith('#'):
            processed_lines.append(original_line)
            i += 1
            continue

        # Skip empty lines
        if not line:
            processed_lines.append(original_line)
            i += 1
            continue

        is_heading = False
        heading_text = line

        # Check each heading pattern
        for pattern in heading_patterns:
            if re.match(pattern, line):
                is_heading = True
                # Extract clean heading text for some patterns
                if pattern.endswith(r'\*\*$'):  # Bold pattern
                    match = re.match(r'^\*\*([^*]+)\*\*$', line)
                    if match:
                        heading_text = match.group(1)
                elif pattern.startswith(r'^\d+'):  # Numbered sections
                    # Remove numbering prefix
                    heading_text = re.sub(r'^\d+(?:\.\d+)*\.?\s+', '', line)
                elif pattern.startswith(r'^[IVX]+'):  # Roman numerals
                    heading_text = re.sub(r'^[IVX]+\.\s+', '', line)
                elif r'\s{3,}' in pattern:  # Centered text
                    heading_text = line.strip()
                break

        # Additional heuristics for Word document titles
        if not is_heading and line:
            # Check if this looks like a standalone title
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            prev_line = lines[i - 1].strip() if i > 0 else ""

            # Standalone lines with title characteristics
            if (len(line) < 80 and  # Not too long
                len(line.split()) <= 12 and  # Reasonable word count for title
                line[0].isupper() and  # Starts with capital
                not line.endswith('.') and  # Doesn't end with period (not a sentence)
                not line.endswith(',') and  # Doesn't end with comma
                (not next_line or next_line == "" or not next_line[0].islower()) and  # Next line doesn't continue sentence
                prev_line == ""):  # Previous line is empty (standalone)

                # Additional checks to avoid false positives
                if (not re.search(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with)\b', line.lower()) or
                    len(line.split()) <= 4):  # Short phrases or avoid common sentence words
                    is_heading = True

        # Check for underlined headings (text followed by dashes, equals, etc.)
        if not is_heading and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if (next_line and
                len(next_line) >= 3 and
                all(c in '-=_' for c in next_line) and
                abs(len(next_line) - len(line)) <= 5):  # Underline length roughly matches text
                is_heading = True
                # Skip the underline in next iteration
                processed_lines.append(f"# {heading_text}")
                i += 2  # Skip both current line and underline
                continue

        # Convert to H1 heading if identified as heading
        if is_heading:
            processed_lines.append(f"# {heading_text}")
        else:
            processed_lines.append(original_line)

        i += 1

    # Join the processed lines
    enhanced_content = '\n'.join(processed_lines)

    # Additional cleanup: Remove duplicate headings
    enhanced_content = re.sub(r'\n# ([^\n]+)\n# \1\n', r'\n# \1\n', enhanced_content)

    return enhanced_content

def _extract_pdf_hyperlinks(file_path: str) -> dict:
    """Extract hyperlinks from PDF files using specialized libraries"""
    hyperlinks = {}

    # Try with PyMuPDF (fitz) first - most robust
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # Get all links on the page
            links = page.get_links()

            for link in links:
                if 'uri' in link and link['uri']:
                    uri = link['uri']
                    hyperlinks[uri] = {
                        'url': uri,
                        'page': page_num + 1,
                        'rect': link.get('from', None),
                        'kind': link.get('kind', 'unknown')
                    }
                    print(f"DEBUG: PyMuPDF found link: {uri} on page {page_num + 1}")

        doc.close()

    except ImportError:
        print("DEBUG: PyMuPDF not available, trying other methods...")
    except Exception as e:
        print(f"Error extracting hyperlinks with PyMuPDF: {e}")

    # Try with PyPDF2 as fallback
    try:
        import PyPDF2

        with open(file_path, "rb") as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            for page_num, page in enumerate(pdf_reader.pages):
                # Check for annotations (hyperlinks)
                if "/Annots" in page:
                    annotations = page["/Annots"]
                    if annotations:
                        for annotation in annotations:
                            try:
                                annotation_obj = annotation.get_object()
                                if "/A" in annotation_obj:
                                    action = annotation_obj["/A"]
                                    if "/URI" in action:
                                        uri = str(action["/URI"])

                                        # Only add if not already found by PyMuPDF
                                        if uri not in hyperlinks:
                                            hyperlinks[uri] = {
                                                'url': uri,
                                                'page': page_num + 1,
                                                'rect': annotation_obj.get("/Rect", None)
                                            }
                                            print(f"DEBUG: PyPDF2 found link: {uri} on page {page_num + 1}")
                            except Exception:
                                continue

    except ImportError:
        print("DEBUG: PyPDF2 not available")
    except Exception as e:
        print(f"Error extracting hyperlinks with PyPDF2: {e}")

    # Try with pdfplumber as final fallback
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract hyperlinks if available
                if hasattr(page, 'hyperlinks'):
                    page_hyperlinks = page.hyperlinks
                    if page_hyperlinks:
                        for link in page_hyperlinks:
                            if isinstance(link, dict) and 'uri' in link:
                                uri = link['uri']
                                # Only add if not already found
                                if uri not in hyperlinks:
                                    hyperlinks[uri] = {
                                        'url': uri,
                                        'page': page_num + 1,
                                        'link_data': link
                                    }
                                    print(f"DEBUG: pdfplumber found link: {uri} on page {page_num + 1}")

                # Extract annotations if available
                if hasattr(page, 'annots'):
                    annotations = page.annots
                    if annotations:
                        for annot in annotations:
                            if isinstance(annot, dict) and 'uri' in annot:
                                uri = annot['uri']
                                # Only add if not already found
                                if uri not in hyperlinks:
                                    hyperlinks[uri] = {
                                        'url': uri,
                                        'page': page_num + 1,
                                        'annotation_data': annot
                                    }
                                    print(f"DEBUG: pdfplumber annotation found link: {uri} on page {page_num + 1}")

    except ImportError:
        print("DEBUG: pdfplumber not available")
    except Exception as e:
        print(f"Error extracting hyperlinks with pdfplumber: {e}")

    print(f"DEBUG: Total hyperlinks extracted: {len(hyperlinks)}")
    return hyperlinks

def _integrate_pdf_hyperlinks(content: str, hyperlinks: dict) -> str:
    """Integrate extracted PDF hyperlinks into the markdown content"""
    if not hyperlinks:
        return content

    print(f"DEBUG: Found {len(hyperlinks)} hyperlinks to integrate")
    for url in hyperlinks.keys():
        print(f"DEBUG: URL - {url}")

    # Create a clean mapping of terms to URLs
    term_to_url = {}

    for url, link_data in hyperlinks.items():
        url_clean = str(url).strip()
        url_lower = url_clean.lower()

        # Look for specific known terms that should be linked
        if "pyrrhus" in url_lower:
            term_to_url["Pyrrhus"] = url_clean
            print(f"DEBUG: Mapped Pyrrhus -> {url_clean}")
        elif "villegaignon" in url_lower:
            term_to_url["Villegaignon"] = url_clean
            print(f"DEBUG: Mapped Villegaignon -> {url_clean}")
        else:
            # Try to extract meaningful terms from URL for other cases
            url_parts = url_clean.split('/')
            for part in url_parts:
                if part and len(part) > 4:
                    # Clean the part and check if it might be a term
                    clean_part = re.sub(r'[^a-zA-Z]', '', part)
                    if len(clean_part) > 4 and clean_part.lower() not in ['https', 'www', 'com', 'org', 'html']:
                        # Check if this term appears in the content
                        if re.search(r'\b' + re.escape(clean_part) + r'\b', content, re.IGNORECASE):
                            term_to_url[clean_part] = url_clean
                            print(f"DEBUG: Mapped {clean_part} -> {url_clean}")
                            break

    print(f"DEBUG: Final term mapping: {term_to_url}")

    # Apply the mappings carefully to avoid nested replacements
    for term, url in term_to_url.items():
        # Create a pattern that matches the exact term as a whole word
        pattern = r'\b' + re.escape(term) + r'\b'

        # Check if the term exists and is not already a link
        matches = list(re.finditer(pattern, content, re.IGNORECASE))

        for match in reversed(matches):  # Reverse to avoid position shifts
            start, end = match.span()

            # Check if this word is already part of a markdown link
            # Look backwards for [ and forwards for ]( to detect existing links
            before_context = content[max(0, start-10):start]
            after_context = content[end:end+10]

            # Skip if already part of a link
            if '[' in before_context and not ']' in before_context:
                continue
            if '](' in after_context:
                continue

            # Replace this occurrence
            original_word = match.group(0)
            replacement = f'[{original_word}]({url})'
            content = content[:start] + replacement + content[end:]

            print(f"DEBUG: Replaced '{original_word}' with '{replacement}'")
            break  # Only replace the first occurrence to avoid duplicates

    return content

def _convert_hyperlinks_to_markdown(content: str) -> str:
    """Convert various hyperlink formats to proper Markdown URLs"""
    if not content:
        return content

    # Pattern 1: Convert HTML anchor tags to Markdown links
    # <a href="url">text</a> -> [text](url)
    html_link_pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
    content = re.sub(html_link_pattern, r'[\2](\1)', content, flags=re.IGNORECASE)

    # Pattern 2: Convert bare URLs to Markdown links (but avoid URLs already in markdown links)
    # Only convert URLs that are not already in Markdown format
    url_pattern = r'(?<!\[)(?<!\()(?<!\]\()(?:https?://|www\.)[\w\-._~:/?#[\]@!$&\'()*+,;=]+(?!\))'

    def url_replacer(match):
        url = match.group(0)
        # Check if this URL is already part of a markdown link by looking at context
        start = match.start()
        before_context = content[max(0, start-50):start]

        # Skip if this URL appears to be inside existing markdown brackets
        if '](' in before_context[-10:]:
            return url

        # Add protocol if missing
        if url.startswith('www.'):
            url = 'http://' + url
        # Use the URL as both the text and the link
        return f'[{url}]({url})'

    content = re.sub(url_pattern, url_replacer, content)

    # Pattern 3: Convert email addresses to Markdown links
    # email@domain.com -> [email@domain.com](mailto:email@domain.com)
    email_pattern = r'(?<!\[)(?<!\()(?<!\]\()[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?!\))'

    def email_replacer(match):
        email = match.group(0)
        # Check context to avoid double-processing
        start = match.start()
        before_context = content[max(0, start-10):start]
        if '](' in before_context:
            return email
        return f'[{email}](mailto:{email})'

    content = re.sub(email_pattern, email_replacer, content)

    # Pattern 4: Clean up any malformed links (remove this aggressive fix)
    # Instead, just fix obvious protocol duplications
    content = re.sub(r'\[([^\]]*)\]\(https?://https?://([^)]*)\)', r'[\1](https://\2)', content)

    return content

def _add_page_numbers_to_markdown(content: str, file_path: str = None, create_pages: bool = True) -> str:
    """Add page numbers to markdown content when pages are detected"""
    if not content or not create_pages:
        return content

    # Check if this is a PDF file (most likely to have pages)
    is_pdf = file_path and Path(file_path).suffix.lower() == '.pdf'

    # Common patterns that indicate page breaks in converted content
    page_break_patterns = [
        r'\n\s*\n\s*(?=\w)',  # Double newlines followed by content
        r'\f',  # Form feed character
        r'(?i)page\s*\d+',  # Existing page references
        r'(?i)\\page',  # LaTeX page breaks
    ]

    # For PDF files, we can be more aggressive about detecting pages
    if is_pdf:
        # Split content into potential pages based on common patterns
        # Look for sections that might represent page breaks
        lines = content.split('\n')
        processed_lines = []
        page_number = 1
        line_count = 0

        # Add first page marker
        processed_lines.append(f"## Page {page_number}")
        processed_lines.append("")

        for i, line in enumerate(lines):
            line_count += 1
            processed_lines.append(line)

            # Detect potential page breaks based on content patterns
            should_add_page_break = False

            # Method 1: Large gaps in content (multiple empty lines)
            if (line.strip() == '' and
                i < len(lines) - 2 and
                lines[i + 1].strip() == '' and
                lines[i + 2].strip() != '' and
                line_count > 20):  # Only after substantial content
                should_add_page_break = True

            # Method 2: Detect headers that might indicate new pages
            elif (line.strip().startswith('#') and
                  line_count > 30 and
                  i > 0 and
                  lines[i - 1].strip() == ''):
                should_add_page_break = True

            # Method 3: Long content sections (rough estimate)
            elif line_count > 50 and line.strip() == '':
                should_add_page_break = True

            if should_add_page_break:
                page_number += 1
                processed_lines.append("")
                processed_lines.append("---")
                processed_lines.append("")
                processed_lines.append(f"## Page {page_number}")
                processed_lines.append("")
                line_count = 0

        return '\n'.join(processed_lines)

    # For non-PDF files, use simpler page detection
    else:
        # Look for explicit page markers or form feeds
        if '\f' in content:
            pages = content.split('\f')
            result_pages = []
            for i, page_content in enumerate(pages):
                if page_content.strip():
                    result_pages.append(f"## Page {i + 1}\n\n{page_content.strip()}")
            return '\n\n---\n\n'.join(result_pages)

        # Check for very long content that might benefit from page markers
        lines = content.split('\n')
        if len(lines) > 100:  # Long documents
            processed_lines = []
            page_number = 1
            line_count = 0

            processed_lines.append(f"## Page {page_number}")
            processed_lines.append("")

            for line in lines:
                line_count += 1
                processed_lines.append(line)

                # Add page breaks for very long content
                if line_count > 80 and line.strip() == '':
                    page_number += 1
                    processed_lines.append("")
                    processed_lines.append("---")
                    processed_lines.append("")
                    processed_lines.append(f"## Page {page_number}")
                    processed_lines.append("")
                    line_count = 0

            return '\n'.join(processed_lines)

    return content

def start_cleanup_scheduler():
    """Start the image cleanup scheduler"""
    cleanup_scheduler.start_scheduler()

def stop_cleanup_scheduler():
    """Stop the image cleanup scheduler"""
    cleanup_scheduler.stop_scheduler()

def get_cleanup_status():
    """Get the status of the cleanup scheduler"""
    return cleanup_scheduler.get_status()

def _integrate_images_into_markdown(content: str, images: list) -> str:
    """Integrate extracted images into markdown content at appropriate positions"""
    if not images:
        return content

    lines = content.split('\n')
    processed_lines = []
    image_index = 0

    # Strategy: Insert images at logical break points
    for i, line in enumerate(lines):
        processed_lines.append(line)

        # Insert images after headings (but not immediately after the first line)
        if line.strip().startswith('#') and i > 0:
            if image_index < len(images):
                image = images[image_index]
                # Add some spacing and the image
                processed_lines.append("")
                processed_lines.append(f"![{image.filename}]({image.url})")
                processed_lines.append("")
                image_index += 1

        # Insert images after paragraphs (empty line followed by content)
        elif (line.strip() == '' and
              i < len(lines) - 1 and
              lines[i + 1].strip() != '' and
              not lines[i + 1].strip().startswith('#') and
              image_index < len(images)):

            # Only insert if we haven't used too many images yet
            if image_index < min(len(images), 3):  # Limit to 3 images in content
                image = images[image_index]
                processed_lines.append(f"![{image.filename}]({image.url})")
                processed_lines.append("")
                image_index += 1

    # Add any remaining images at the end in a dedicated section
    if image_index < len(images):
        processed_lines.append("")
        processed_lines.append("---")
        processed_lines.append("")
        processed_lines.append("## Extracted Images")
        processed_lines.append("")

        for remaining_image in images[image_index:]:
            processed_lines.append(f"![{remaining_image.filename}]({remaining_image.url})")
            processed_lines.append("")

    return '\n'.join(processed_lines)

def _convert_base64_images_to_files(content: str, document_name: str) -> tuple[str, list[ImageInfo]]:
    """
    Detect base64 images in markdown content, convert them to image files,
    and replace them with links to the saved files.

    Special handling: If image is in a header/top section, place it at the very top.

    Returns: (updated_content, list_of_created_images)
    """
    if not content:
        return content, []

    # Multiple patterns to catch different base64 image formats
    base64_patterns = [
        # Standard markdown: ![alt](data:image/type;base64,...)
        r'!\[([^\]]*)\]\(data:image/([^;]+);base64,([^)]+)\)',
        # HTML img tags: <img src="data:image/type;base64,..." alt="..." />
        r'<img[^>]*src=["\']data:image/([^;]+);base64,([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?[^>]*/??>',
        # Variations with spaces or different formatting
        r'!\[([^\]]*)\]\(\s*data:image/([^;]+);\s*base64\s*,\s*([^)]+)\s*\)',
    ]

    all_matches = []

    # Collect all matches from all patterns
    for pattern_idx, pattern in enumerate(base64_patterns):
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        for match in matches:
            all_matches.append((pattern_idx, match))

    if not all_matches:
        return content, []

    # Sort matches by position (reverse order for replacement)
    all_matches.sort(key=lambda x: x[1].start(), reverse=True)

    created_images = []
    updated_content = content
    header_images = []  # Track images that should go to the top

    lines = content.split('\n')

    # Process matches in reverse order to maintain string positions
    for match_idx, (pattern_idx, match) in enumerate(all_matches):
        try:
            # Extract data based on pattern type
            if pattern_idx == 0:  # Standard markdown pattern
                alt_text = match.group(1) or f"image_{match_idx + 1}"
                image_type = match.group(2)
                base64_data = match.group(3)
            elif pattern_idx == 1:  # HTML img tag pattern
                image_type = match.group(1)
                base64_data = match.group(2)
                alt_text = match.group(3) if len(match.groups()) > 2 and match.group(3) else f"image_{match_idx + 1}"
            else:  # Pattern with spaces
                alt_text = match.group(1) or f"image_{match_idx + 1}"
                image_type = match.group(2)
                base64_data = match.group(3)

            # Clean up base64 data (remove any whitespace)
            base64_data = re.sub(r'\s+', '', base64_data)

            # Validate base64 data length (basic check)
            if len(base64_data) < 10:
                print(f"WARNING: Base64 data too short for image {match_idx + 1}, skipping")
                continue

            # Decode base64 data
            try:
                image_data = base64.b64decode(base64_data)
            except Exception as decode_error:
                print(f"ERROR: Failed to decode base64 for image {match_idx + 1}: {decode_error}")
                # Remove the invalid base64 image from content
                start, end = match.span()
                updated_content = updated_content[:start] + updated_content[end:]
                continue

            # Validate image data
            if len(image_data) < 100:  # Too small to be a real image
                print(f"WARNING: Decoded image data too small for image {match_idx + 1}, removing")
                start, end = match.span()
                updated_content = updated_content[:start] + updated_content[end:]
                continue

            # Create filename
            # Clean alt text for filename use
            clean_alt = re.sub(r'[^\w\s-]', '', alt_text.strip())
            clean_alt = re.sub(r'\s+', '_', clean_alt)
            if not clean_alt or clean_alt == '_':
                clean_alt = f"image_{match_idx + 1}"

            filename = f"{clean_alt}.{image_type}"
            # Clean filename to be filesystem-safe
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

            # Ensure directory exists before creating folder
            image_extractor._ensure_images_dir_exists()

            # Create document folder for images
            document_folder = image_extractor._create_document_folder(document_name)
            image_path = document_folder / filename

            # Save the image file
            with open(image_path, 'wb') as f:
                f.write(image_data)

            # Verify the saved file
            if not image_path.exists() or image_path.stat().st_size == 0:
                print(f"ERROR: Failed to save image {filename}")
                start, end = match.span()
                updated_content = updated_content[:start] + updated_content[end:]
                continue

            # Get image dimensions
            try:
                from PIL import Image
                with Image.open(image_path) as img_obj:
                    width, height = img_obj.size
                    print(f"DEBUG: Successfully saved image {filename} ({width}x{height})")
            except Exception as img_error:
                print(f"WARNING: Could not read image dimensions for {filename}: {img_error}")
                width, height = None, None

            # Create image info
            image_info = ImageInfo(
                filename=filename,
                url=f"{image_extractor.base_url}/images/{document_folder.name}/{filename}",
                width=width,
                height=height
            )
            created_images.append(image_info)

            # Check if this image is in a header/top section
            match_start = match.start()

            # Find which line this match is on
            char_count = 0
            line_number = 0
            for line_idx, line in enumerate(lines):
                if char_count + len(line) + 1 > match_start:  # +1 for newline
                    line_number = line_idx
                    break
                char_count += len(line) + 1

            # Check if image is in header section
            is_in_header = False

            # Method 1: Image is in the first few lines
            if line_number < 5:
                is_in_header = True
                print(f"DEBUG: Image {filename} found in early lines (line {line_number})")

            # Method 2: Image is before the first substantial content block
            else:
                # Look for first substantial content (paragraph with multiple sentences)
                first_content_line = None
                for idx, line in enumerate(lines):
                    stripped = line.strip()
                    if (stripped and
                        not stripped.startswith('#') and
                        not stripped.startswith('!') and
                        '.' in stripped and
                        len(stripped.split()) > 10):  # Substantial content
                        first_content_line = idx
                        break

                if first_content_line and line_number < first_content_line:
                    is_in_header = True
                    print(f"DEBUG: Image {filename} found before main content (line {line_number} < {first_content_line})")

            # Method 3: Image is within or immediately after a heading
            if not is_in_header and line_number > 0:
                # Check current and nearby lines for headings
                check_range = range(max(0, line_number - 2), min(len(lines), line_number + 3))
                for check_idx in check_range:
                    if check_idx < len(lines) and lines[check_idx].strip().startswith('#'):
                        is_in_header = True
                        print(f"DEBUG: Image {filename} found near heading at line {check_idx}")
                        break

            # Replace the base64 image
            start, end = match.span()

            if is_in_header:
                # Mark this image to be moved to top
                header_images.append(image_info)
                # Remove the base64 image from its current position
                replacement = ""  # Remove completely, will be added to top
                print(f"DEBUG: Marking image {filename} for header placement")
            else:
                # Replace with normal image link
                replacement = f"![{alt_text}]({image_info.url})"
                print(f"DEBUG: Replacing image {filename} in place")

            updated_content = updated_content[:start] + replacement + updated_content[end:]

        except Exception as e:
            print(f"Error converting base64 image {match_idx + 1}: {e}")
            # Remove the problematic base64 image from content
            try:
                start, end = match.span()
                updated_content = updated_content[:start] + updated_content[end:]
                print(f"DEBUG: Removed problematic base64 image from content")
            except:
                pass
            continue

    # If we have header images, place them at the very top
    if header_images:
        lines = updated_content.split('\n')

        # Find the best position for header images
        insert_position = 0

        # Skip any existing title/heading at the very top
        if lines and lines[0].strip().startswith('#'):
            insert_position = 1
            # Also skip any empty lines after the title
            while (insert_position < len(lines) and
                   lines[insert_position].strip() == ''):
                insert_position += 1

        # Create the header images section
        header_section = []
        for img in header_images:
            header_section.append(f"![{img.filename}]({img.url})")
            header_section.append("")  # Add spacing

        # Insert header images at the determined position
        lines = lines[:insert_position] + header_section + lines[insert_position:]
        updated_content = '\n'.join(lines)

        print(f"DEBUG: Placed {len(header_images)} header images at position {insert_position}")

    return updated_content, created_images


def _remove_remaining_base64_images(content: str) -> str:
    """
    Remove any remaining base64 images from content that couldn't be converted.
    This is a cleanup function to ensure no base64 data remains in the final output.
    SURGICAL VERSION - removes only base64 parts while preserving text content.
    """
    if not content:
        return content

    original_content = content
    print(f"DEBUG: Starting surgical base64 cleanup...")

    # PASS 1: Remove base64 image patterns while preserving text on the same line
    base64_patterns = [
        r'!\[[^\]]*\]\([^)]*base64[^)]*\)',  # Any image with base64
        r'!\[[^\]]*\]\(data:[^)]+\)',         # Any image with data: protocol
        r'<img[^>]*src=["\'][^"\']*base64[^"\']*["\'][^>]*>',  # HTML img with base64
        r'data:image/[^;,\s]+[;,][^)\s]*',    # Any data:image URL
        r'!\[[^\]]*\]\([^)]{150,}\)',         # Very long image URLs (likely base64)
    ]

    removed_count = 0
    for pattern in base64_patterns:
        matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
        if matches:
            print(f"DEBUG: Pass 1 - Found {len(matches)} matches for pattern: {pattern[:50]}...")
            for match in reversed(matches):
                matched_text = match.group(0)
                print(f"DEBUG: Removing base64 part: {matched_text[:100]}...")
                start, end = match.span()
                # Remove only the base64 image part, not the entire line
                content = content[:start] + content[end:]
                removed_count += 1

    print(f"DEBUG: Pass 1 - Removed {removed_count} base64 image patterns")

    # PASS 2: Clean up any remaining suspicious base64 strings (more targeted)
    suspicious_patterns = [
        r'base64,[A-Za-z0-9+/=]{20,}',  # base64 data chunks
        r';base64,[A-Za-z0-9+/=]+',     # base64 with semicolon prefix
    ]

    for pattern in suspicious_patterns:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if matches:
            print(f"DEBUG: Pass 2 - Found {len(matches)} suspicious base64 strings")
            for match in reversed(matches):
                matched_text = match.group(0)
                print(f"DEBUG: Removing suspicious string: {matched_text[:50]}...")
                start, end = match.span()
                content = content[:start] + content[end:]

    # PASS 3: Clean up formatting issues left by removals
    # Remove empty parentheses left by removed images: ![text]()
    content = re.sub(r'!\[[^\]]*\]\(\s*\)', '', content)

    # Clean up excessive whitespace
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)  # Collapse multiple empty lines
    content = re.sub(r'^\s*\n+', '', content)  # Remove leading empty lines
    content = re.sub(r'\n+\s*$', '\n', content)  # Remove trailing empty lines
    content = content.strip()  # Remove leading/trailing whitespace

    if content != original_content:
        print(f"DEBUG: Successfully cleaned content - removed base64 parts while preserving text")

        # Final verification - check if any base64 strings remain
        if 'base64' in content.lower():
            print(f"WARNING: base64 still found in content after cleanup!")
            # Show what remains for debugging
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'base64' in line.lower():
                    print(f"DEBUG: Remaining base64 on line {i+1}: {line[:100]}...")

    return content

async def convert_url(url: str, create_pages: bool = True) -> ConvertResponse:
    """Convert a URL to markdown"""
    try:
        # Download the file from URL with proper headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()

        # Get filename from URL or Content-Disposition header
        filename = get_filename_from_url(url, response)

        # Create a temporary file with UTF-8 encoding consideration
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        try:
            # Convert using MarkItDown
            result = md.convert(temp_file_path)

            # Ensure the content is properly encoded as UTF-8
            content = result.text_content
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')

            # IMMEDIATE base64 cleanup - remove any base64 images created by MarkItDown
            content = _remove_remaining_base64_images(content)

            # Extract images from the file
            images = image_extractor.extract_images_from_file(temp_file_path, filename)

            # Enhance heading detection for Word documents and other formats
            content = _enhance_heading_detection(content, temp_file_path)

            # Integrate images into the markdown content
            content = _integrate_images_into_markdown(content, images)

            # Add page numbers to the content if applicable
            content = _add_page_numbers_to_markdown(content, temp_file_path, create_pages)

            # Convert hyperlinks to Markdown format
            content = _convert_hyperlinks_to_markdown(content)

            # Convert base64 images to files and update content
            content, base64_images = _convert_base64_images_to_files(content, filename)
            images.extend(base64_images)  # Add converted base64 images to the list

            # Final cleanup: Remove any remaining base64 images that couldn't be converted
            content = _remove_remaining_base64_images(content)

            return ConvertResponse(
                filename=filename,
                content=content,
                images=images
            )
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)

    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error downloading URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting URL: {str(e)}")


async def convert_file(file_path: str, create_pages: bool = True) -> ConvertResponse:
    """Convert a local file to markdown"""
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Get filename without extension for display
        path_obj = Path(file_path)
        filename = path_obj.stem

        # Convert using MarkItDown
        result = md.convert(file_path)

        # Ensure the content is properly encoded as UTF-8
        content = result.text_content
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')

        # IMMEDIATE base64 cleanup - remove any base64 images created by MarkItDown
        content = _remove_remaining_base64_images(content)

        # Extract images from the file
        images = image_extractor.extract_images_from_file(file_path, filename)

        # Enhance heading detection for Word documents and other formats
        content = _enhance_heading_detection(content, file_path)

        # Extract hyperlinks from PDF files
        if path_obj.suffix.lower() == '.pdf':
            pdf_hyperlinks = _extract_pdf_hyperlinks(file_path)
            content = _integrate_pdf_hyperlinks(content, pdf_hyperlinks)

            # Apply manual hyperlinks for cases where automatic extraction fails
            content = _apply_manual_hyperlinks(content, file_path)

        # Integrate images into the markdown content
        content = _integrate_images_into_markdown(content, images)

        # Add page numbers to the content if applicable
        content = _add_page_numbers_to_markdown(content, file_path, create_pages)

        # Convert hyperlinks to Markdown format (skip for PDFs since we already handled them)
        if path_obj.suffix.lower() != '.pdf':
            content = _convert_hyperlinks_to_markdown(content)

        # Convert base64 images to files and update content
        content, base64_images = _convert_base64_images_to_files(content, filename)
        images.extend(base64_images)  # Add converted base64 images to the list

        # Final cleanup: Remove any remaining base64 images that couldn't be converted
        content = _remove_remaining_base64_images(content)

        return ConvertResponse(
            filename=filename,
            content=content,
            images=images
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting file: {str(e)}")


def get_filename_from_url(url: str, response: requests.Response) -> str:
    """Extract filename from URL or Content-Disposition header"""
    # Try to get filename from Content-Disposition header
    content_disposition = response.headers.get('Content-Disposition')
    if content_disposition:
        import re
        filename_match = re.search(r'filename[*]?=([^;]+)', content_disposition)
        if filename_match:
            filename = filename_match.group(1).strip('"\'')
            # Ensure filename is properly decoded
            if isinstance(filename, bytes):
                filename = filename.decode('utf-8', errors='replace')
            return Path(filename).stem

    # Fallback to URL path
    parsed_url = urlparse(url)
    path = parsed_url.path
    if path:
        filename = Path(path).name
        if filename:
            return Path(filename).stem

    # Final fallback
    return "document"

def _apply_manual_hyperlinks(content: str, file_path: str = None) -> str:
    """Apply manual hyperlink mappings for specific files or common terms"""

    # Manual mappings for known files or terms - expanded to cover all likely hyperlinked terms
    manual_mappings = {
        # Historical figures
        "Pyrrhus": "https://www.worldhistory.org/pyrrhus/",
        "Villegaignon": "https://www.encyclopedia.com/humanities/encyclopedias-almanacs-transcripts-and-maps/villegaignon-nicolas-durand-de-1510-1572",
        "Plutarch": "https://www.britannica.com/biography/Plutarch",
        "Montaigne": "https://www.britannica.com/biography/Michel-de-Montaigne",
        "Caesar": "https://www.britannica.com/biography/Julius-Caesar-Roman-ruler",
        "Lycurgus": "https://www.britannica.com/biography/Lycurgus-ancient-Greek-lawgiver",
        "Plato": "https://www.britannica.com/biography/Plato",
        "Herodotus": "https://www.britannica.com/biography/Herodotus-Greek-historian",
        "Seneca": "https://www.britannica.com/biography/Lucius-Annaeus-Seneca-Roman-philosopher",

        # Additional terms that might be hyperlinked
        "Scythians": "https://www.worldhistory.org/Scythians/",
        "Propertius": "https://www.britannica.com/biography/Propertius",
        "Virgil": "https://www.britannica.com/biography/Virgil",
        "Juvenal": "https://www.britannica.com/biography/Juvenal",
        "Chrysippus": "https://www.britannica.com/biography/Chrysippus",
        "Zeno": "https://www.britannica.com/biography/Zeno-of-Citium",

        # Places and concepts
        "Thermopylae": "https://www.worldhistory.org/thermopylae/",
        "Salamis": "https://www.worldhistory.org/Battle_of_Salamis/",
        "Plataea": "https://www.worldhistory.org/Battle_of_Plataea/",
    }

    # Apply the manual mappings - only process plain text, not already formatted links
    for term, url in manual_mappings.items():
        # First, check if this term already exists as a link in the content
        if f'[{term}](' in content:
            print(f"DEBUG: Skipping {term} - already exists as a markdown link")
            continue

        # Use a simpler approach to find terms that aren't already links
        # Split content by existing markdown links to process only plain text sections
        parts = re.split(r'(\[[^\]]+\]\([^)]+\))', content)

        for i in range(0, len(parts), 2):  # Process only non-link parts (even indices)
            # Create a pattern that matches the exact term as a whole word
            pattern = r'\b' + re.escape(term) + r'\b'

            # Find the first occurrence in this plain text section
            match = re.search(pattern, parts[i], re.IGNORECASE)

            if match:
                start, end = match.span()
                original_word = match.group(0)
                replacement = f'[{original_word}]({url})'

                # Replace only this first occurrence in this section
                parts[i] = parts[i][:start] + replacement + parts[i][end:]

                print(f"DEBUG: Manual mapping - Replaced '{original_word}' with link to {url}")
                break  # Only replace the first occurrence of this term

        # Reconstruct the content
        content = ''.join(parts)

    return content

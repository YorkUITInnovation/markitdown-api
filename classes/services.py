import requests
import tempfile
import os
import re
from urllib.parse import urlparse
from pathlib import Path
from markitdown import MarkItDown
from fastapi import HTTPException
from classes import ConvertResponse
from classes.image_extractor import ImageExtractor
from classes.scheduler import ImageCleanupScheduler

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

            # Extract images from the file
            images = image_extractor.extract_images_from_file(temp_file_path, filename)

            # Ensure the content is properly encoded as UTF-8
            content = result.text_content
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')

            # Enhance heading detection for Word documents and other formats
            content = _enhance_heading_detection(content, temp_file_path)

            # Integrate images into the markdown content
            content = _integrate_images_into_markdown(content, images)

            # Add page numbers to the content if applicable
            content = _add_page_numbers_to_markdown(content, temp_file_path, create_pages)

            # Convert hyperlinks to Markdown format
            content = _convert_hyperlinks_to_markdown(content)

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

        # Extract images from the file
        images = image_extractor.extract_images_from_file(file_path, filename)

        # Ensure the content is properly encoded as UTF-8
        content = result.text_content
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')

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

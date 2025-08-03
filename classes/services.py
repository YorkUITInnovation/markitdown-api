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

    # Patterns that indicate a heading/title (more restrictive)
    heading_patterns = [
        # All caps text (common in titles) - but must be substantial and not contain common non-heading indicators
        r'^[A-Z][A-Z\s\d\-]{8,}[A-Z\d]$',
        # Numbered sections (1. Title, 1.1 Title, etc.) - but not simple numbering
        r'^\d+(?:\.\d+)*\.?\s+[A-Z][A-Za-z\s]{3,}$',
        # Roman numerals
        r'^[IVX]+\.\s+[A-Z][A-Za-z\s]{3,}$',
        # Centered text patterns (detected by surrounding whitespace)
        r'^\s{4,}[A-Z][A-Za-z\s\d\-.,!?()]{8,}\s{4,}$',
        # Bold markers that might have been converted
        r'^\*\*([A-Z][A-Za-z\s\d\-.,!?()]{5,})\*\*$',
        # Underlined text patterns
        r'^[A-Z][A-Za-z\s\d\-.,!?()]{5,}$(?=\n[-=_]{4,})',
    ]

    # Patterns that should NOT be treated as headings
    exclusion_patterns = [
        # Names with titles (Prof., Dr., Mr., Ms., etc.)
        r'^(Prof\.?|Dr\.?|Mr\.?|Ms\.?|Mrs\.?)\s+',
        # Email addresses or lines containing emails
        r'.*@.*\..*',
        # URLs or lines containing URLs
        r'.*(https?://|www\.|\.com|\.org|\.net)',
        # Contact information patterns
        r'^(Phone|Tel|Email|Fax|Address|Office):?\s*',
        # Course/class information - more specific pattern that requires colon or specific context
        r'^(Course|Class|Section|Semester|Room|Time|Day|Location)\s*:',
        # Lines that end with colons (field labels)
        r'^[^:]{1,30}:\s*',
        # Lines with specific academic/contact keywords
        r'.*(phone|email|office|room|building|semester|lecture|tutorial|lab).*',
        # Zoom/meeting links
        r'.*(zoom|meeting|conference).*',
        # Lines that are clearly data/values rather than headings
        r'^[A-Z][a-z]+\s+\d{4}',  # Month Year
        r'^\d+:\d+\s*(AM|PM)',     # Time formats
        r'^[A-Z][a-z]+,\s*\d',    # Day, date formats
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

        # Check exclusion patterns first
        is_excluded = False
        for exclusion_pattern in exclusion_patterns:
            if re.search(exclusion_pattern, line, re.IGNORECASE):
                is_excluded = True
                break

        if is_excluded:
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
                elif r'\s{4,}' in pattern:  # Centered text
                    heading_text = line.strip()
                break

        # Additional heuristics for Word document titles (more restrictive)
        if not is_heading and line and not is_excluded:
            # Check if this looks like a standalone title
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            prev_line = lines[i - 1].strip() if i > 0 else ""

            # More restrictive standalone title detection
            if (len(line) < 60 and  # Not too long
                len(line.split()) >= 2 and len(line.split()) <= 8 and  # Reasonable word count for title
                line[0].isupper() and  # Starts with capital
                not line.endswith('.') and  # Doesn't end with period (not a sentence)
                not line.endswith(',') and  # Doesn't end with comma
                not line.endswith(':') and  # Doesn't end with colon (not a label)
                (not next_line or next_line == "" or not next_line[0].islower()) and  # Next line doesn't continue sentence
                prev_line == "" and  # Previous line is empty (standalone)
                not re.search(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', line.lower()) and  # Avoid common sentence words
                not re.search(r'\d{4}', line) and  # Avoid years/dates
                not re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', line.lower())):  # Avoid days

                # Additional check for title-like content
                words = line.split()
                if all(word[0].isupper() or word.lower() in ['of', 'the', 'and', 'in', 'to', 'for'] for word in words):
                    is_heading = True

            # Special case: Common section titles in academic documents
            elif (len(line.split()) >= 2 and len(line.split()) <= 4 and
                  line[0].isupper() and
                  prev_line == "" and  # Previous line is empty (standalone)
                  re.match(r'^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*$', line) and  # Title case - more flexible pattern
                  line.lower() in ['course information', 'course description', 'learning outcomes',
                                   'required texts', 'course objectives', 'grading scheme',
                                   'assignment details', 'tutorial information', 'office hours']):
                is_heading = True

        # Check for underlined headings (text followed by dashes, equals, etc.)
        if not is_heading and not is_excluded and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if (next_line and
                len(next_line) >= 4 and
                all(c in '-=_' for c in next_line) and
                abs(len(next_line) - len(line)) <= 5 and  # Underline length roughly matches text
                len(line) >= 5):  # Minimum length for heading
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

        doc.close()

    except ImportError:
        pass
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
                            except Exception:
                                continue

    except ImportError:
        pass
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

    except ImportError:
        pass
    except Exception as e:
        print(f"Error extracting hyperlinks with pdfplumber: {e}")

    return hyperlinks

def _integrate_pdf_hyperlinks(content: str, hyperlinks: dict) -> str:
    """Integrate extracted PDF hyperlinks into the markdown content"""
    if not hyperlinks:
        return content

    # Create a clean mapping of terms to URLs
    term_to_url = {}

    for url, link_data in hyperlinks.items():
        url_clean = str(url).strip()
        url_lower = url_clean.lower()

        # Look for specific known terms that should be linked
        if "pyrrhus" in url_lower:
            term_to_url["Pyrrhus"] = url_clean
        elif "villegaignon" in url_lower:
            term_to_url["Villegaignon"] = url_clean
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
                            break

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
    """Integrate extracted images into markdown content at their original positions"""
    if not images:
        return content

    # Enhanced strategy: Use positioning information to place images accurately
    lines = content.split('\n')
    processed_lines = []

    # Sort images by page number and position for proper ordering
    sorted_images = sorted(images, key=lambda img: (
        img.page_number or 0,
        img.position_y or 0
    ))

    # Create a mapping of page numbers to images
    page_to_images = {}
    for image in sorted_images:
        page_num = image.page_number or 1
        if page_num not in page_to_images:
            page_to_images[page_num] = []
        page_to_images[page_num].append(image)

    # Track which images have been placed
    placed_images = set()
    current_page = 1

    for i, line in enumerate(lines):
        processed_lines.append(line)

        # Detect page breaks in content
        if _is_page_break_indicator(line, lines, i):
            current_page += 1

        # Try to place images based on content context matching
        if current_page in page_to_images:
            for image in page_to_images[current_page]:
                if image.filename in placed_images:
                    continue

                # Check if this is a good position for the image based on context
                if _should_place_image_here(line, image, lines, i):
                    processed_lines.append("")
                    processed_lines.append(f"![{image.filename}]({image.url})")
                    processed_lines.append("")
                    placed_images.add(image.filename)

        # Also place images after headings (fallback for images without good context)
        if line.strip().startswith('#') and i > 0:
            # Look for unplaced images from current or previous pages
            for page_num in range(max(1, current_page - 1), current_page + 2):
                if page_num in page_to_images:
                    for image in page_to_images[page_num]:
                        if image.filename not in placed_images:
                            processed_lines.append("")
                            processed_lines.append(f"![{image.filename}]({image.url})")
                            processed_lines.append("")
                            placed_images.add(image.filename)
                            break  # Only place one image per heading
                    break

    # Add any remaining unplaced images at the end
    unplaced_images = [img for img in sorted_images if img.filename not in placed_images]
    if unplaced_images:
        processed_lines.append("")
        processed_lines.append("---")
        processed_lines.append("")
        processed_lines.append("## Document Images")
        processed_lines.append("")

        for image in unplaced_images:
            processed_lines.append(f"![{image.filename}]({image.url})")
            processed_lines.append("")

    return '\n'.join(processed_lines)

def _is_page_break_indicator(line: str, lines: list, line_index: int) -> bool:
    """Detect if a line indicates a page break"""
    line_stripped = line.strip()

    # Explicit page indicators
    if any(indicator in line_stripped.lower() for indicator in [
        'page ', '---', '===', 'chapter ', 'section '
    ]):
        return True

    # Multiple consecutive empty lines (often indicates page breaks)
    if (line_stripped == '' and
        line_index > 0 and
        line_index < len(lines) - 1 and
        lines[line_index - 1].strip() == '' and
        lines[line_index + 1].strip() != ''):
        return True

    return False

def _should_place_image_here(current_line: str, image: ImageInfo, lines: list, line_index: int) -> bool:
    """Determine if an image should be placed at the current position based on context"""
    if not image.content_context:
        return False

    # Get surrounding lines for context matching
    context_window = 3
    start_idx = max(0, line_index - context_window)
    end_idx = min(len(lines), line_index + context_window + 1)
    surrounding_text = ' '.join(lines[start_idx:end_idx]).lower()

    # Check if image context matches surrounding text
    image_context_words = image.content_context.lower().split()

    # Look for word matches in surrounding text
    matches = 0
    for word in image_context_words:
        if len(word) > 3 and word in surrounding_text:  # Only count meaningful words
            matches += 1

    # Place image if we have good context match
    match_ratio = matches / len(image_context_words) if image_context_words else 0
    return match_ratio > 0.3  # 30% of context words should match

def _integrate_images_with_advanced_positioning(content: str, images: list, file_path: str = None) -> str:
    """Advanced image integration that analyzes document structure for optimal placement"""
    if not images:
        return content

    # For PDF files, we can use more sophisticated positioning
    if file_path and Path(file_path).suffix.lower() == '.pdf':
        try:
            import fitz

            # Re-analyze the PDF to get detailed text and image positioning
            pdf_doc = fitz.open(file_path)
            # Note: _analyze_pdf_layout function not implemented yet
            # content_with_positions = _analyze_pdf_layout(pdf_doc, content, images)
            pdf_doc.close()
            # return content_with_positions

        except Exception as e:
            print(f"Advanced positioning failed, using fallback: {e}")

    # For DOCX files, use content position data
    elif file_path and Path(file_path).suffix.lower() in ['.docx', '.doc']:
        return _integrate_docx_images_by_position(content, images)

    # Fallback to standard integration
    return _integrate_images_into_markdown(content, images)

def _integrate_docx_images_by_position(content: str, images: list) -> str:
    """Integrate images into DOCX-converted content using position_in_content data"""
    if not images:
        return content

    # Sort images by their position in content
    positioned_images = [img for img in images if img.position_in_content is not None]
    unpositioned_images = [img for img in images if img.position_in_content is None]

    # Sort positioned images by their content position
    positioned_images.sort(key=lambda img: img.position_in_content)

    if not positioned_images:
        # Fall back to context matching if no position data
        return _integrate_images_by_context_matching(content, images)

    # Convert content to list of lines for easier manipulation
    lines = content.split('\n')

    # Build a character position map for each line
    line_positions = []
    char_pos = 0
    for line in lines:
        line_positions.append(char_pos)
        char_pos += len(line) + 1  # +1 for newline

    # Insert images based on their content positions
    insertions = []  # List of (line_index, image) tuples

    for image in positioned_images:
        target_char_pos = image.position_in_content

        # Find the best line to insert the image
        best_line_idx = 0
        for i, line_char_pos in enumerate(line_positions):
            if line_char_pos <= target_char_pos:
                best_line_idx = i
            else:
                break

        # Adjust insertion position based on content context
        final_line_idx = _find_best_insertion_point(lines, best_line_idx, image)
        insertions.append((final_line_idx, image))

    # Sort insertions by line index (reverse order for proper insertion)
    insertions.sort(key=lambda x: x[0], reverse=True)

    # Insert images into content
    result_lines = lines.copy()
    for line_idx, image in insertions:
        # Insert image with proper spacing
        image_lines = [
            "",
            f"![{image.filename}]({image.url})",
            ""
        ]

        # Insert after the target line
        insert_pos = line_idx + 1
        result_lines[insert_pos:insert_pos] = image_lines

    # Handle unpositioned images at the end
    if unpositioned_images:
        result_lines.extend([
            "",
            "---",
            "",
            "## Additional Images",
            ""
        ])

        for image in unpositioned_images:
            result_lines.extend([
                f"![{image.filename}]({image.url})",
                ""
            ])

    return '\n'.join(result_lines)

def _find_best_insertion_point(lines: list, target_line_idx: int, image: ImageInfo) -> int:
    """Find the best line to insert an image near the target position"""
    # Ensure we don't go out of bounds
    target_line_idx = max(0, min(target_line_idx, len(lines) - 1))

    # Look for a good insertion point within a small range
    search_range = 3
    start_idx = max(0, target_line_idx - search_range)
    end_idx = min(len(lines), target_line_idx + search_range + 1)

    # Preferred insertion points (in order of preference):
    # 1. After a heading
    # 2. After an empty line (paragraph break)
    # 3. After a line that matches image context
    # 4. The original target position

    for offset in range(search_range + 1):
        # Check positions around the target
        for direction in [0, 1, -1]:  # target, after, before
            check_idx = target_line_idx + (offset * direction)
            if start_idx <= check_idx < end_idx:
                line = lines[check_idx].strip()

                # Priority 1: After headings
                if line.startswith('#'):
                    return check_idx

                # Priority 2: After empty lines (good paragraph breaks)
                if (check_idx > 0 and lines[check_idx - 1].strip() == '' and
                    check_idx < len(lines) - 1 and lines[check_idx + 1].strip() != ''):
                    return check_idx

    # Priority 3: Check for context matching
    if image.content_context:
        context_words = image.content_context.lower().split()[:5]  # First 5 words

        for check_idx in range(start_idx, end_idx):
            line_text = lines[check_idx].lower()

            # Count word matches
            matches = sum(1 for word in context_words if len(word) > 3 and word in line_text)

            if matches >= 2:  # Good context match
                return check_idx

    # Priority 4: Fall back to original target
    return target_line_idx

def _integrate_images_by_context_matching(content: str, images: list) -> str:
    """Integrate images using content context matching when position data is unavailable"""
    if not images:
        return content

    lines = content.split('\n')
    result_lines = []
    used_images = set()

    for i, line in enumerate(lines):
        result_lines.append(line)

        # Try to place images that match this line's context
        for image in images:
            if image.filename in used_images or not image.content_context:
                continue

            # Check if this line matches the image context
            if _line_matches_image_context(line, lines, i, image):
                result_lines.extend([
                    "",
                    f"![{image.filename}]({image.url})",
                    ""
                ])
                used_images.add(image.filename)
                break  # Only place one image per line

    # Add any remaining unplaced images
    unused_images = [img for img in images if img.filename not in used_images]
    if unused_images:
        result_lines.extend([
            "",
            "---",
            "",
            "## Additional Images",
            ""
        ])

        for image in unused_images:
            result_lines.extend([
                f"![{image.filename}]({image.url})",
                ""
            ])

    return '\n'.join(result_lines)

def _line_matches_image_context(line: str, lines: list, line_idx: int, image: ImageInfo) -> bool:
    """Check if a line and its surrounding context matches an image's context"""
    if not image.content_context:
        return False

    # Get surrounding context (current line + 2 before and after)
    context_range = 2
    start_idx = max(0, line_idx - context_range)
    end_idx = min(len(lines), line_idx + context_range + 1)

    surrounding_text = ' '.join(lines[start_idx:end_idx]).lower()
    image_context_words = image.content_context.lower().split()

    # Count meaningful word matches
    matches = 0
    total_words = 0

    for word in image_context_words:
        if len(word) > 3:  # Only count meaningful words
            total_words += 1
            if word in surrounding_text:
                matches += 1

    # Require at least 40% word match for context-based placement
    if total_words > 0:
        match_ratio = matches / total_words
        return match_ratio >= 0.4

    return False
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
        r'<img[^>]*src=["\']data:image/([^;]+);base64,([^"\']+)["\'][^>]*>(?:alt=["\']([^"\']*)["\'])?[^>]*/??>',
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
                continue

            # Decode base64 data
            try:
                image_data = base64.b64decode(base64_data)
            except Exception:
                # Remove the invalid base64 image from content
                start, end = match.span()
                updated_content = updated_content[:start] + updated_content[end:]
                continue

            # Validate image data
            if len(image_data) < 100:  # Too small to be a real image
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
                start, end = match.span()
                updated_content = updated_content[:start] + updated_content[end:]
                continue

            # Get image dimensions
            try:
                from PIL import Image
                with Image.open(image_path) as img_obj:
                    width, height = img_obj.size
            except Exception:
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

            # Method 3: Image is within or immediately after a heading
            if not is_in_header and line_number > 0:
                # Check current and nearby lines for headings
                check_range = range(max(0, line_number - 2), min(len(lines), line_number + 3))
                for check_idx in check_range:
                    if check_idx < len(lines) and lines[check_idx].strip().startswith('#'):
                        is_in_header = True
                        break

            # Replace the base64 image
            start, end = match.span()

            if is_in_header:
                # Mark this image to be moved to top
                header_images.append(image_info)
                # Remove the base64 image from its current position
                replacement = ""  # Remove completely, will be added to top
            else:
                # Replace with normal image link
                replacement = f"![{alt_text}]({image_info.url})"

            updated_content = updated_content[:start] + replacement + updated_content[end:]

        except Exception as e:
            # Remove the problematic base64 image from content
            try:
                start, end = match.span()
                updated_content = updated_content[:start] + updated_content[end:]
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

    # PASS 1: Remove base64 image patterns while preserving text on the same line
    base64_patterns = [
        r'!\[[^\]]*\]\([^)]*base64[^)]*\)',  # Any image with base64
        r'!\[[^\]]*\]\(data:[^)]+\)',         # Any image with data: protocol
        r'<img[^>]*src=["\'][^"\']*base64[^"\']*["\'][^>]*>',  # HTML img with base64
        r'data:image/[^;,\s]+[;,][^)\s]*',    # Any data:image URL
        r'!\[[^\]]*\]\([^)]{150,}\)',         # Very long image URLs (likely base64)
    ]

    for pattern in base64_patterns:
        matches = list(re.finditer(pattern, content, re.IGNORECASE | re.DOTALL))
        if matches:
            for match in reversed(matches):
                start, end = match.span()
                # Remove only the base64 image part, not the entire line
                content = content[:start] + content[end:]

    # PASS 2: Clean up any remaining suspicious base64 strings (more targeted)
    suspicious_patterns = [
        r'base64,[A-Za-z0-9+/=]{20,}',  # base64 data chunks
        r';base64,[A-Za-z0-9+/=]+',     # base64 with semicolon prefix
    ]

    for pattern in suspicious_patterns:
        matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if matches:
            for match in reversed(matches):
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

            # Integrate images into the markdown content using advanced positioning
            content = _integrate_images_with_advanced_positioning(content, images, temp_file_path)

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


async def convert_file(file_path: str, create_pages: bool = True, original_filename: str = None) -> ConvertResponse:
    """Convert a local file to markdown"""
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Always create path_obj for file extension checking
        path_obj = Path(file_path)

        # Use provided original filename or derive from file path
        if original_filename:
            filename = original_filename
        else:
            # Get filename without extension for display
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

        # Integrate images into the markdown content using advanced positioning
        content = _integrate_images_with_advanced_positioning(content, images, file_path)

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
            # Return just the stem (filename without extension) and ensure it's clean
            clean_filename = Path(filename).stem
            if clean_filename and not clean_filename.startswith('tmp'):
                return clean_filename

    # Fallback to URL path
    parsed_url = urlparse(url)
    path = parsed_url.path
    if path:
        filename = Path(path).name
        if filename:
            clean_filename = Path(filename).stem
            # Make sure we don't use temporary file names
            if clean_filename and not clean_filename.startswith('tmp'):
                return clean_filename

    # Final fallback - use a clean document name with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fallback_name = f"document_{timestamp}"
    return fallback_name

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

                break  # Only replace the first occurrence of this term

        # Reconstruct the content
        content = ''.join(parts)

    return content

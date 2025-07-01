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

async def convert_url(url: str) -> ConvertResponse:
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

            # Integrate images into the markdown content
            content = _integrate_images_into_markdown(content, images)

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


async def convert_file(file_path: str) -> ConvertResponse:
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

        # Integrate images into the markdown content
        content = _integrate_images_into_markdown(content, images)

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

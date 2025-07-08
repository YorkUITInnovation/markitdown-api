import os
import shutil
import uuid
import zipfile
import tempfile
import time
import datetime
from pathlib import Path
from typing import List, Dict, Any
from PIL import Image
import fitz  # PyMuPDF for PDF image extraction
from docx import Document
from docx.image.exceptions import UnrecognizedImageError
import xml.etree.ElementTree as ET
from classes.models import ImageInfo
from classes import config

class ImageExtractor:
    """Extract images from various document types and save them to accessible folders"""

    def __init__(self, base_url: str = "http://localhost:8000", images_dir: str = None):
        self.base_url = base_url.rstrip('/')
        # Use config.IMAGES_DIR if no specific directory is provided
        self.images_dir = Path(images_dir or config.IMAGES_DIR)
        # Don't create directory immediately - do it lazily when first needed

    def _ensure_images_dir_exists(self):
        """Ensure the images directory exists, create if necessary"""
        try:
            self.images_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        except PermissionError:
            # If we can't create the directory, try to use a temporary location
            # This should align with the fallback used in main.py
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "markitdown_static" / "images"
            temp_dir.mkdir(parents=True, exist_ok=True, mode=0o755)

            # Update the base_url to reflect the temporary directory
            old_images_dir = self.images_dir
            self.images_dir = temp_dir
            print(f"Warning: Could not create {old_images_dir}, using temporary directory: {temp_dir}")
            print(f"Images will be served from temporary location")

    def extract_images_from_file(self, file_path: str, document_name: str) -> List[ImageInfo]:
        """Extract images from a file based on its extension"""
        # Ensure directory exists before extraction
        self._ensure_images_dir_exists()

        file_path = Path(file_path)
        document_folder = self._create_document_folder(document_name)

        if file_path.suffix.lower() == '.pdf':
            return self._extract_from_pdf(file_path, document_folder)
        elif file_path.suffix.lower() in ['.docx', '.doc']:
            return self._extract_from_docx(file_path, document_folder)
        elif file_path.suffix.lower() in ['.pptx', '.ppt']:
            return self._extract_from_pptx(file_path, document_folder)
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            return self._extract_from_excel(file_path, document_folder)
        elif file_path.suffix.lower() in ['.odt', '.ods', '.odp']:
            return self._extract_from_odf(file_path, document_folder)
        elif file_path.suffix.lower() in ['.html', '.htm', '.xml']:
            return self._extract_from_html_xml(file_path, document_folder)
        elif file_path.suffix.lower() in ['.zip', '.rar', '.7z']:
            return self._extract_from_archive(file_path, document_folder)
        else:
            return []

    def _create_document_folder(self, document_name: str) -> Path:
        """Create a unique folder for the document's images"""
        safe_name = "".join(c for c in document_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        # Convert to lowercase and replace spaces and hyphens with underscores
        safe_name = safe_name.lower().replace(' ', '_').replace('-', '_')
        unique_id = str(uuid.uuid4())[:8]
        folder_name = f"{safe_name}_{unique_id}"
        document_folder = self.images_dir / folder_name
        document_folder.mkdir(parents=True, exist_ok=True)
        return document_folder

    def _extract_from_pdf(self, file_path: Path, output_folder: Path) -> List[ImageInfo]:
        """Extract images from PDF files"""
        images = []
        try:
            pdf_document = fitz.open(file_path)

            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(pdf_document, xref)

                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        filename = f"page_{page_num + 1}_img_{img_index + 1}.png"
                        image_path = output_folder / filename
                        pix.save(str(image_path))

                        # Get image dimensions
                        with Image.open(image_path) as img_obj:
                            width, height = img_obj.size

                        images.append(ImageInfo(
                            filename=filename,
                            url=f"{self.base_url}/images/{output_folder.name}/{filename}",
                            width=width,
                            height=height
                        ))

                    pix = None

            pdf_document.close()
        except Exception as e:
            print(f"Error extracting images from PDF: {e}")

        return images

    def _extract_from_docx(self, file_path: Path, output_folder: Path) -> List[ImageInfo]:
        """Extract images from DOCX files"""
        images = []
        try:
            doc = Document(file_path)

            # Extract from document relationships
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    try:
                        image_data = rel.target_part.blob
                        filename = f"image_{len(images) + 1}.{rel.target_ref.split('.')[-1]}"
                        image_path = output_folder / filename

                        with open(image_path, 'wb') as f:
                            f.write(image_data)

                        # Get image dimensions
                        try:
                            with Image.open(image_path) as img_obj:
                                width, height = img_obj.size
                        except:
                            width, height = None, None

                        images.append(ImageInfo(
                            filename=filename,
                            url=f"{self.base_url}/images/{output_folder.name}/{filename}",
                            width=width,
                            height=height
                        ))
                    except Exception as e:
                        print(f"Error extracting image from DOCX: {e}")

        except Exception as e:
            print(f"Error processing DOCX file: {e}")

        return images

    def _extract_from_pptx(self, file_path: Path, output_folder: Path) -> List[ImageInfo]:
        """Extract images from PPTX files"""
        images = []
        try:
            # PPTX files are ZIP archives
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if file_info.filename.startswith('ppt/media/'):
                        filename = Path(file_info.filename).name
                        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                            image_data = zip_ref.read(file_info.filename)
                            image_path = output_folder / filename

                            with open(image_path, 'wb') as f:
                                f.write(image_data)

                            # Get image dimensions
                            try:
                                with Image.open(image_path) as img_obj:
                                    width, height = img_obj.size
                            except:
                                width, height = None, None

                            images.append(ImageInfo(
                                filename=filename,
                                url=f"{self.base_url}/images/{output_folder.name}/{filename}",
                                width=width,
                                height=height
                            ))
        except Exception as e:
            print(f"Error extracting images from PPTX: {e}")

        return images

    def _extract_from_excel(self, file_path: Path, output_folder: Path) -> List[ImageInfo]:
        """Extract images from Excel files"""
        images = []
        try:
            # Excel files are ZIP archives
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if file_info.filename.startswith('xl/media/'):
                        filename = Path(file_info.filename).name
                        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                            image_data = zip_ref.read(file_info.filename)
                            image_path = output_folder / filename

                            with open(image_path, 'wb') as f:
                                f.write(image_data)

                            # Get image dimensions
                            try:
                                with Image.open(image_path) as img_obj:
                                    width, height = img_obj.size
                            except:
                                width, height = None, None

                            images.append(ImageInfo(
                                filename=filename,
                                url=f"{self.base_url}/images/{output_folder.name}/{filename}",
                                width=width,
                                height=height
                            ))
        except Exception as e:
            print(f"Error extracting images from Excel: {e}")

        return images

    def _extract_from_odf(self, file_path: Path, output_folder: Path) -> List[ImageInfo]:
        """Extract images from ODF files (OpenDocument Format)"""
        images = []
        try:
            # ODF files are ZIP archives
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if file_info.filename.startswith('Pictures/'):
                        filename = Path(file_info.filename).name
                        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')):
                            image_data = zip_ref.read(file_info.filename)
                            image_path = output_folder / filename

                            with open(image_path, 'wb') as f:
                                f.write(image_data)

                            # Get image dimensions
                            try:
                                with Image.open(image_path) as img_obj:
                                    width, height = img_obj.size
                            except:
                                width, height = None, None

                            images.append(ImageInfo(
                                filename=filename,
                                url=f"{self.base_url}/images/{output_folder.name}/{filename}",
                                width=width,
                                height=height
                            ))
        except Exception as e:
            print(f"Error extracting images from ODF: {e}")

        return images

    def _extract_from_html_xml(self, file_path: Path, output_folder: Path) -> List[ImageInfo]:
        """Extract images referenced in HTML/XML files"""
        images = []
        try:
            # For HTML/XML, we would need to parse and download referenced images
            # This is a basic implementation that looks for embedded base64 images
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Look for base64 embedded images
            import re
            import base64

            pattern = r'data:image/([^;]+);base64,([^"]+)'
            matches = re.findall(pattern, content)

            for i, (image_type, base64_data) in enumerate(matches):
                try:
                    image_data = base64.b64decode(base64_data)
                    filename = f"embedded_image_{i + 1}.{image_type}"
                    image_path = output_folder / filename

                    with open(image_path, 'wb') as f:
                        f.write(image_data)

                    # Get image dimensions
                    try:
                        with Image.open(image_path) as img_obj:
                            width, height = img_obj.size
                    except:
                        width, height = None, None

                    images.append(ImageInfo(
                        filename=filename,
                        url=f"{self.base_url}/images/{output_folder.name}/{filename}",
                        width=width,
                        height=height
                    ))
                except Exception as e:
                    print(f"Error extracting embedded image: {e}")

        except Exception as e:
            print(f"Error processing HTML/XML file: {e}")

        return images

    def _extract_from_archive(self, file_path: Path, output_folder: Path) -> List[ImageInfo]:
        """Extract images from archive files"""
        images = []
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    filename = Path(file_info.filename).name
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg')):
                        try:
                            image_data = zip_ref.read(file_info.filename)
                            safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                            image_path = output_folder / safe_filename

                            with open(image_path, 'wb') as f:
                                f.write(image_data)

                            # Get image dimensions (skip for SVG)
                            width, height = None, None
                            if not filename.lower().endswith('.svg'):
                                try:
                                    with Image.open(image_path) as img_obj:
                                        width, height = img_obj.size
                                except:
                                    pass

                            images.append(ImageInfo(
                                filename=safe_filename,
                                url=f"{self.base_url}/images/{output_folder.name}/{safe_filename}",
                                width=width,
                                height=height
                            ))
                        except Exception as e:
                            print(f"Error extracting image from archive: {e}")
        except Exception as e:
            print(f"Error processing archive file: {e}")

        return images

    def cleanup_old_images(self, days_old: int) -> Dict[str, Any]:
        """
        Delete image folders that are older than the specified number of days.

        Args:
            days_old: Number of days after which image folders should be deleted

        Returns:
            Dictionary with cleanup statistics
        """
        if not self.images_dir.exists():
            return {
                "status": "skipped",
                "reason": "Images directory does not exist",
                "deleted_folders": 0,
                "freed_space_mb": 0
            }

        cutoff_time = time.time() - (days_old * 24 * 60 * 60)  # Convert days to seconds
        deleted_folders = 0
        freed_space_bytes = 0
        deleted_folder_names = []

        try:
            for folder_path in self.images_dir.iterdir():
                if folder_path.is_dir():
                    # Get folder creation time
                    folder_stat = folder_path.stat()
                    folder_creation_time = folder_stat.st_ctime

                    if folder_creation_time < cutoff_time:
                        # Calculate folder size before deletion
                        folder_size = self._get_folder_size(folder_path)

                        try:
                            # Delete the folder and all its contents
                            shutil.rmtree(folder_path)
                            deleted_folders += 1
                            freed_space_bytes += folder_size
                            deleted_folder_names.append(folder_path.name)
                            print(f"Deleted old image folder: {folder_path.name}")
                        except Exception as e:
                            print(f"Error deleting folder {folder_path.name}: {e}")

            return {
                "status": "completed",
                "deleted_folders": deleted_folders,
                "freed_space_mb": round(freed_space_bytes / (1024 * 1024), 2),
                "deleted_folder_names": deleted_folder_names,
                "cleanup_time": datetime.datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "deleted_folders": deleted_folders,
                "freed_space_mb": round(freed_space_bytes / (1024 * 1024), 2)
            }

    def _get_folder_size(self, folder_path: Path) -> int:
        """Calculate the total size of a folder in bytes"""
        total_size = 0
        try:
            for file_path in folder_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            print(f"Error calculating size for {folder_path}: {e}")
        return total_size

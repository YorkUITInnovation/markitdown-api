from pydantic import BaseModel
from typing import List, Optional


class ImageInfo(BaseModel):
    filename: str
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    # New positioning fields
    page_number: Optional[int] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    position_in_content: Optional[int] = None  # Character position in extracted text
    content_context: Optional[str] = None  # Surrounding text for positioning


class ConvertRequest(BaseModel):
    source: str  # Can be a file path or URL
    create_pages: Optional[bool] = True  # New optional parameter to control page creation


class ConvertResponse(BaseModel):
    filename: str
    content: str
    images: List[ImageInfo] = []


class UploadResponse(BaseModel):
    filename: str
    content: str
    file_size: int
    images: List[ImageInfo] = []


class VersionResponse(BaseModel):
    version: str

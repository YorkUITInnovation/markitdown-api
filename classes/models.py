from pydantic import BaseModel
from typing import List, Optional


class ImageInfo(BaseModel):
    filename: str
    url: str
    width: Optional[int] = None
    height: Optional[int] = None


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

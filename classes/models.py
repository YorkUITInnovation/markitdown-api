from pydantic import BaseModel


class ConvertRequest(BaseModel):
    source: str  # Can be a file path or URL


class ConvertResponse(BaseModel):
    filename: str
    content: str


class UploadResponse(BaseModel):
    filename: str
    content: str
    file_size: int


class VersionResponse(BaseModel):
    version: str

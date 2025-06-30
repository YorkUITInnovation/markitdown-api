from fastapi import FastAPI, HTTPException, Depends, Security, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from markitdown import MarkItDown
import requests
import tempfile
import os
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Application version
API_VERSION = "1.1.1"

# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
DISABLE_DOCS = os.getenv("DISABLE_DOCS", "false").lower() == "true"

# File upload configuration
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))  # Default 100MB

# Determine if docs should be enabled
# Disable docs in production or when explicitly disabled
docs_enabled = ENVIRONMENT != "production" and not DISABLE_DOCS

app = FastAPI(
    title="MarkItDown API",
    description="Convert files and URLs to Markdown using Microsoft MarkItDown",
    version=API_VERSION,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None
)

# Initialize MarkItDown
md = MarkItDown()

# Security - HTTPBearer for API key authentication
security = HTTPBearer()

# Load API keys from environment
def get_valid_api_keys():
    api_keys_str = os.getenv("API_KEYS", "")
    if not api_keys_str:
        raise ValueError("No API keys configured. Please set API_KEYS in .env file")
    return [key.strip() for key in api_keys_str.split(",") if key.strip()]

VALID_API_KEYS = get_valid_api_keys()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify the API key from the Authorization header"""
    if credentials.credentials not in VALID_API_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

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

@app.get("/version",
         summary="Get API version",
         description="Returns the current version of the MarkItDown API",
         response_model=VersionResponse)
async def get_version():
    """Get the current API version"""
    return VersionResponse(version=API_VERSION)

@app.post("/convert",
          summary="Convert local file or URL to Markdown",
          description="Convert a file or URL to markdown using Microsoft MarkItDown. Requires valid API key.",
          dependencies=[Depends(verify_api_key)],
          responses={
              200: {"description": "Successfully converted to markdown"},
              401: {"description": "Invalid or missing API key"},
              404: {"description": "File not found"},
              400: {"description": "Error downloading URL"},
              500: {"description": "Conversion error"}
          })
async def convert(request: ConvertRequest, api_key: str = Depends(verify_api_key)):
    """
    Convert a file or URL to markdown using Microsoft MarkItDown.
    Accepts either a local file path or an HTTP/HTTPS URL.
    Requires valid API key in Authorization header: Bearer <your-api-key>
    """
    source = request.source.strip()

    # Check if it's a URL
    parsed_url = urlparse(source)
    if parsed_url.scheme in ['http', 'https']:
        return await convert_url(source)
    else:
        return await convert_file(source)

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

            # Ensure the content is properly encoded as UTF-8
            content = result.text_content
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')

            return ConvertResponse(
                filename=filename,
                content=content
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

        # Ensure the content is properly encoded as UTF-8
        content = result.text_content
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')

        return ConvertResponse(
            filename=filename,
            content=content
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting file: {str(e)}")

@app.post("/upload",
          summary="Upload and convert file to Markdown",
          description="Upload a file and convert it to markdown using Microsoft MarkItDown. Requires valid API key.",
          dependencies=[Depends(verify_api_key)],
          response_model=UploadResponse,
          responses={
              200: {"description": "Successfully uploaded and converted to markdown"},
              401: {"description": "Invalid or missing API key"},
              413: {"description": "File too large"},
              422: {"description": "Invalid file type"},
              500: {"description": "Conversion error"}
          })
async def upload_file(file: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    """
    Upload a file and convert it to markdown using Microsoft MarkItDown.
    Accepts various file types supported by MarkItDown (PDF, DOCX, images, etc.).
    Requires valid API key in Authorization header: Bearer <your-api-key>
    """

    # Check file size (limit to 100MB)
    MAX_FILE_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert MB to bytes

    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB"
            )

        # Get filename without extension for display
        filename = Path(file.filename or "uploaded_file").stem

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "").suffix) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            # Convert using MarkItDown
            result = md.convert(temp_file_path)

            # Ensure the content is properly encoded as UTF-8
            content = result.text_content
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')

            return UploadResponse(
                filename=filename,
                content=content,
                file_size=file_size
            )

        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing uploaded file: {str(e)}")

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

# Custom OpenAPI schema to ensure security is properly documented
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="MarkItDown API",
        version=API_VERSION,
        description="Convert files and URLs to Markdown using Microsoft MarkItDown",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API Key",
            "description": "Enter your API key (without 'Bearer' prefix)"
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

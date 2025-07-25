from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
import tempfile
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional
from classes import (
    ConvertRequest, ConvertResponse, UploadResponse, VersionResponse,
    verify_api_key, API_VERSION, MAX_UPLOAD_SIZE_MB, docs_enabled, services, config
)

app = FastAPI(
    title="MarkItDown API",
    description="Convert files and URLs to Markdown using Microsoft MarkItDown",
    version=API_VERSION,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None
)

# Mount static files for serving extracted images
# Use configurable directory from environment variable
static_dir = Path(config.IMAGES_DIR).parent
images_dir = Path(config.IMAGES_DIR)

# Create directories with proper error handling
try:
    static_dir.mkdir(mode=0o755, exist_ok=True)
    images_dir.mkdir(mode=0o755, exist_ok=True)
    print(f"Using static directory: {static_dir}")
except PermissionError:
    # If we can't create in the root directory, fall back to /tmp
    import tempfile
    temp_static = Path(tempfile.gettempdir()) / "markitdown_static"
    temp_images = temp_static / "images"
    temp_static.mkdir(mode=0o755, exist_ok=True)
    temp_images.mkdir(mode=0o755, exist_ok=True)
    print(f"Warning: Using temporary directory for static files: {temp_static}")
    app.mount("/images", StaticFiles(directory=str(temp_images)), name="images")
else:
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")

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
    Optional create_pages parameter (default: true) controls whether pages are created in the markdown.
    """
    source = request.source.strip()
    create_pages = request.create_pages

    # Check if it's a URL
    parsed_url = urlparse(source)
    if parsed_url.scheme in ['http', 'https']:
        return await services.convert_url(source, create_pages)
    else:
        return await services.convert_file(source, create_pages)

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
async def upload_file(
    file: UploadFile = File(...),
    create_pages: Optional[bool] = Form(True),
    api_key: str = Depends(verify_api_key)
):
    """
    Upload a file and convert it to markdown using Microsoft MarkItDown.
    Accepts various file types supported by MarkItDown (PDF, DOCX, images, etc.).
    Requires valid API key in Authorization header: Bearer <your-api-key>
    Optional create_pages parameter (default: true) controls whether pages are created in the markdown.
    """

    # Check file size (limit to configured MB)
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
            # Convert using the updated conversion function that includes base64 cleanup
            convert_result = await services.convert_file(temp_file_path, create_pages)

            return UploadResponse(
                filename=filename,
                content=convert_result.content,
                file_size=file_size,
                images=convert_result.images
            )

        finally:
            # Clean up temporary file
            import os
            os.unlink(temp_file_path)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing uploaded file: {str(e)}")

# Start the image cleanup scheduler on application startup
@app.on_event("startup")
async def startup_event():
    """Initialize services and start the image cleanup scheduler"""
    print("Starting MarkItDown API server...")
    print("Initializing image cleanup scheduler...")
    services.start_cleanup_scheduler()
    print("Image cleanup scheduler started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on application shutdown"""
    print("Shutting down MarkItDown API server...")
    services.stop_cleanup_scheduler()
    print("Image cleanup scheduler stopped")

@app.get("/cleanup-status",
         summary="Get image cleanup status",
         description="Returns the current status of the image cleanup scheduler",
         dependencies=[Depends(verify_api_key)])
async def get_cleanup_status(api_key: str = Depends(verify_api_key)):
    """Get the current status of the image cleanup scheduler"""
    return services.get_cleanup_status()

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

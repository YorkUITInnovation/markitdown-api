# MarkItDown API

A FastAPI-based web service that converts files and URLs to Markdown using Microsoft's MarkItDown library.

## Features

- **File Upload & Conversion**: Upload files directly and convert them to Markdown
- **URL Conversion**: Convert web pages and online documents to Markdown
- **Multiple File Formats**: Supports PDF, Word documents, PowerPoint, Excel, images, and more
- **Intelligent Hyperlink Conversion**: Automatically converts embedded hyperlinks to proper Markdown format
- **PDF Hyperlink Extraction**: Extracts clickable links from PDF files using specialized libraries
- **Smart Link Detection**: Avoids double-processing and nested bracket issues
- **Advanced Image Processing**: Automatically extracts and integrates images from documents
- **Smart Image Placement**: Intelligently places extracted images within the markdown content
- **Image URL Generation**: Serves extracted images through accessible URLs
- **Automated Image Cleanup**: Scheduled daily cleanup of old image folders to manage disk space
- **Configurable Retention**: Customizable image retention period via environment variables
- **Cleanup Monitoring**: Real-time status monitoring of cleanup operations
- **Secure API**: API key authentication for all conversion endpoints
- **Production Security**: Automatic documentation disabling in production environments
- **Auto-reload**: Development server with automatic reloading
- **Interactive Documentation**: Built-in Swagger UI and ReDoc documentation (development only)

### Hyperlink Conversion Features

The API includes sophisticated hyperlink conversion capabilities:

- **Automatic PDF Link Extraction**: Uses PyMuPDF, PyPDF2, and pdfplumber to extract embedded hyperlinks from PDF files
- **Manual Link Mapping**: Comprehensive database of 18+ historical figures, classical authors, and famous battles
- **Smart Text Processing**: Converts plain text references to clickable Markdown links
- **Multi-format Support**: Works with PDFs, Word documents, HTML files, and more
- **Link Quality Assurance**: Prevents nested brackets and malformed links

## Installation

1. Clone the repository:
```bash
git clone git@github.com:YorkUITInnovation/markitdown-api.git
cd markitdown-api
```

2. Create a virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install -r requirements.txt

# For PDF support (required for PDF files):
pip install markitdown[pdf]

# Or install all optional dependencies:
pip install markitdown[all]
```

4. Create a `.env` file with your API keys:
```env
# Required: API keys for authentication
API_KEYS=your-api-key-1,your-api-key-2,your-api-key-3

# Optional: Environment configuration (default: development)
ENVIRONMENT=development

# Optional: Force disable docs regardless of environment (default: false)
DISABLE_DOCS=false

# Optional: Maximum upload file size in MB (default: 100MB)
MAX_UPLOAD_SIZE_MB=100

# Image cleanup configuration
# Number of days after which image folders should be deleted (default: 7)
IMAGE_CLEANUP_DAYS=7

# Daily cleanup time in 24-hour format HH:MM (default: 02:00)
IMAGE_CLEANUP_TIME=02:00

# Optional: Directory where extracted images will be stored
IMAGES_DIR=/script/images

# Base URL for image downloads (without trailing slash)
# Change this when deploying to a server (default: http://localhost:8000)
IMAGE_BASE_URL=http://localhost:8000
```

## Environment Configuration

The API supports different environment modes for enhanced security:

### Development Mode (Default)
- API documentation available at `/docs` and `/redoc`
- OpenAPI schema accessible at `/openapi.json`
- Ideal for development and testing

```env
ENVIRONMENT=development  # or omit this line
API_KEYS=your-api-keys-here
```

### Production Mode
- **Security Enhanced**: API documentation endpoints are automatically disabled
- No access to `/docs`, `/redoc`, or `/openapi.json`
- Reduces attack surface and prevents schema exposure

```env
ENVIRONMENT=production
API_KEYS=your-api-keys-here
```

### Manual Documentation Control
Force disable documentation regardless of environment:

```env
DISABLE_DOCS=true
API_KEYS=your-api-keys-here
```

## File Upload Configuration

The API supports configurable file upload limits to accommodate different use cases and server capacities.

### Default Upload Limit
By default, the maximum file upload size is set to **100MB**. This provides a good balance between functionality and server resource usage.

### Custom Upload Limits
You can configure the maximum upload size using the `MAX_UPLOAD_SIZE_MB` environment variable:

```env
# Examples of different upload limits
MAX_UPLOAD_SIZE_MB=50    # 50MB - for smaller deployments
MAX_UPLOAD_SIZE_MB=200   # 200MB - for medium files
MAX_UPLOAD_SIZE_MB=500   # 500MB - for large documents
MAX_UPLOAD_SIZE_MB=1000  # 1GB - for enterprise use
```

### Environment-Specific Configuration

#### Development Environment
```env
ENVIRONMENT=development
MAX_UPLOAD_SIZE_MB=200
API_KEYS=your-api-keys-here
```

#### Production Environment
```env
ENVIRONMENT=production
MAX_UPLOAD_SIZE_MB=100
API_KEYS=your-api-keys-here
```

#### Docker Configuration
Add to your `docker_apikeys.env` file:
```env
MAX_UPLOAD_SIZE_MB=500
ENVIRONMENT=production
API_KEYS=your-api-keys-here
```

### Upload Limit Considerations

- **Server Resources**: Larger limits require more RAM and disk space
- **Processing Time**: Bigger files take longer to process
- **Network Bandwidth**: Consider your network capacity for large uploads
- **Use Case**: Match the limit to your typical file sizes

When a file exceeds the configured limit, the API returns a `413 Payload Too Large` error with the current size limit.

## Image Cleanup System

The API includes an intelligent image cleanup system that automatically manages disk space by removing old extracted images. This prevents unlimited storage growth while maintaining recent images for accessibility.

### How It Works

1. **Automatic Scheduling**: The cleanup runs daily at a specified time
2. **Age-Based Deletion**: Only removes image folders older than the configured number of days
3. **Background Operation**: Runs silently without affecting API performance
4. **Detailed Logging**: Provides comprehensive cleanup statistics and logs

### Configuration

Configure the cleanup system using environment variables:

```env
# Delete image folders older than 7 days (default)
IMAGE_CLEANUP_DAYS=7

# Run cleanup daily at 2:00 AM (default)
IMAGE_CLEANUP_TIME=02:00

# Optional: Directory where extracted images will be stored
IMAGES_DIR=/script/images

# Base URL for image downloads (without trailing slash)
# Change this when deploying to a server (default: http://localhost:8000)
IMAGE_BASE_URL=http://localhost:8000
```

#### Common Configuration Examples

**Conservative Cleanup (14 days)**
```env
IMAGE_CLEANUP_DAYS=14
IMAGE_CLEANUP_TIME=03:00
```

**Aggressive Cleanup (3 days)**
```env
IMAGE_CLEANUP_DAYS=3
IMAGE_CLEANUP_TIME=01:30
```

**Production Settings**
```env
IMAGE_CLEANUP_DAYS=7
IMAGE_CLEANUP_TIME=02:00
ENVIRONMENT=production
```

### Cleanup Process

The cleanup system follows these steps:

1. **Scan**: Examines all folders in the images directory
2. **Evaluate**: Checks creation time against the configured retention period
3. **Calculate**: Determines folder sizes before deletion
4. **Delete**: Removes folders and all contained files
5. **Report**: Logs detailed statistics about the cleanup operation

### Monitoring Cleanup Status

Use the `/cleanup-status` endpoint to monitor the cleanup system:

**GET** `/cleanup-status`

**Headers:**
- `Authorization: Bearer YOUR_API_KEY`

**Example:**
```bash
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8000/cleanup-status
```

**Response:**
```json
{
  "running": true,
  "cleanup_days": 7,
  "cleanup_time": "02:00",
  "next_cleanup": "2025-07-02 02:00:00",
  "images_directory": "/static/images"
}
```

### Cleanup Logs

The system provides detailed logging of cleanup operations:

```
[INFO] Starting image cleanup task (deleting folders older than 7 days)
[INFO] Cleanup completed successfully:
[INFO]   - Deleted folders: 3
[INFO]   - Freed space: 15.7 MB
[INFO]   - Deleted folder names: document_abc123, presentation_def456, spreadsheet_ghi789
```

### Benefits

- **Automatic Disk Management**: Prevents storage bloat without manual intervention
- **Configurable Retention**: Adjust retention period based on your needs
- **Production Ready**: Reliable background operation suitable for production environments
- **Resource Efficiency**: Scheduled during low-traffic hours to minimize impact
- **Detailed Monitoring**: Complete visibility into cleanup operations

## Running the Server

Start the development server:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base URL**: http://localhost:8000
- **Interactive Documentation**: http://localhost:8000/docs
- **Alternative Documentation**: http://localhost:8000/redoc

## API Endpoints

### 1. Get API Version
**GET** `/version`

Returns the current API version.

**Example:**
```bash
curl http://localhost:8000/version
```

**Response:**
```json
{
  "version": "1.0.0"
}
```

### 2. Convert URL to Markdown
**POST** `/convert`

Convert a web page or online document to Markdown format.

**Headers:**
- `Authorization: Bearer YOUR_API_KEY`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "url": "https://example.com/document.pdf"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/convert" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/page"}'
```

**Response:**
```json
{
  "markdown": "# Page Title\n\nContent converted to markdown...",
  "url": "https://example.com/page"
}
```

### 3. Upload and Convert File
**POST** `/upload`

Upload a file and convert it to Markdown format.

**Headers:**
- `Authorization: Bearer YOUR_API_KEY`

**Form Data:**
- `file`: The file to upload and convert

**Supported File Types:**
- PDF files (`.pdf`)
- Microsoft Word documents (`.docx`, `.doc`)
- Microsoft PowerPoint presentations (`.pptx`, `.ppt`)
- Microsoft Excel spreadsheets (`.xlsx`, `.xls`)
- Images with text (`.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`)
- HTML files (`.html`, `.htm`)
- Text files (`.txt`, `.md`)
- And many more formats supported by MarkItDown

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/upload" \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@document.pdf"
```

**Example using JavaScript:**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8000/upload', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer your-api-key'
  },
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

**Response:**
```json
{
  "markdown": "# Document Title\n\nConverted content in markdown format...",
  "filename": "document.pdf",
  "file_size": 1024576
}
```

## Image Processing

The API now includes advanced image processing capabilities that enhance the markdown conversion experience:

### Automatic Image Extraction

The service automatically extracts images from various document types:

- **PDF Files**: Extracts embedded images from all pages
- **Word Documents (.docx)**: Retrieves images from document relationships
- **PowerPoint Presentations (.pptx)**: Extracts images from slides
- **Excel Spreadsheets (.xlsx)**: Retrieves embedded images
- **OpenDocument Formats (.odt, .odp, .ods)**: Supports ODF image extraction
- **Archive Files (.zip, .rar, .7z)**: Finds images within compressed files
- **HTML/XML Files**: Extracts referenced images

### Smart Image Integration

Instead of just listing images separately, the API now intelligently integrates them into the markdown content:

#### Strategic Placement
- **After Headings**: Images are placed after section headings for logical organization
- **Paragraph Breaks**: Images appear at natural content breaks
- **Content Flow**: Maintains document structure and readability

#### Intelligent Distribution
- **In-Content Images**: Up to 3 images are strategically placed within the content
- **Dedicated Section**: Remaining images are organized in an "Extracted Images" section
- **Proper Formatting**: Images include alt text and proper spacing

### Image URL Structure

Extracted images are served through accessible URLs with the following structure:
```
http://localhost:8000/images/{document_folder}/{filename}
```

Where:
- `document_folder`: Unique folder based on document name and UUID
- `filename`: Original or generated filename with appropriate extension

### Image Metadata

Each extracted image includes comprehensive metadata:

```json
{
  "filename": "image1.png",
  "url": "http://localhost:8000/images/document_abc123/image1.png",
  "width": 800,
  "height": 600
}
```

### Example Output

When processing a document with images, the markdown output now includes integrated images:

```markdown
# Document Title

This is the document content...

![image1.png](http://localhost:8000/images/document_abc123/image1.png)

## Section Heading

More content here...

![image2.png](http://localhost:8000/images/document_abc123/image2.png)

---

## Extracted Images

![image3.png](http://localhost:8000/images/document_abc123/image3.png)

![image4.png](http://localhost:8000/images/document_abc123/image4.png)
```

### Static File Serving

The API automatically serves extracted images through the `/images/` endpoint:
- **Direct Access**: Images can be accessed directly via their URLs
- **Browser Viewing**: Images display properly in web browsers
- **Markdown Rendering**: Images render correctly in markdown viewers

## Error Responses

All endpoints may return these error responses:

### 401 Unauthorized
```json
{
  "detail": "Invalid API key"
}
```

### 400 Bad Request
```json
{
  "detail": "Error message describing the issue"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "field"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Docker Support

### Using Docker Compose (Recommended)

1. Create your API keys file:
```bash
cp docker_apikeys.env.example docker_apikeys.env
# Edit docker_apikeys.env with your API keys
```

2. Create the required directories and set permissions:
```bash
# Create directories for persistent storage
mkdir -p markitdown/images markitdown/uploads

# Set proper ownership (999 is the container's appuser UID)
sudo chown -R 999:999 markitdown

# Set proper permissions
sudo chmod -R 775 markitdown
```

3. Run with Docker Compose:
```bash
docker-compose up -d
```

**Docker Compose Configuration:**
The `docker-compose.yml` file includes the proper volume mapping:
```yaml
volumes:
  - ./markitdown/images:/static/images  # Persist extracted images
  - ./markitdown/uploads:/app/uploads   # Optional: persist uploads
```

### Using Docker directly

```bash
# Build the image
docker build -t markitdown-api .

# Create directories and set permissions
mkdir -p markitdown/images markitdown/uploads
sudo chown -R 999:999 markitdown
sudo chmod -R 775 markitdown

# Run the container with proper volume mounting
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/markitdown/images:/static/images \
  -v $(pwd)/markitdown/uploads:/app/uploads \
  --env-file docker_apikeys.env \
  --name markitdown-api \
  --restart unless-stopped \
  markitdown-api
```

### Important Notes for Docker Deployment

- **Volume Mounting**: The `/static/images` directory inside the container must be mounted to persist extracted images
- **Permissions**: The container runs as user ID 999 (`appuser`), so host directories must be owned by this user
- **Directory Structure**: Use `./markitdown/images` and `./markitdown/uploads` on the host for organization
- **Health Checks**: The container includes built-in health monitoring via the `/version` endpoint

## Development

### Project Structure
```
markitdown-api/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables (create this)
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile            # Docker image configuration
├── docker_apikeys.env    # Docker environment file
├── test_main.http        # HTTP test requests
└── README.md            # This file
```

### Testing

Use the provided `test_main.http` file with your HTTP client, or test directly in the browser using the interactive documentation at http://localhost:8000/docs.

## Dependencies

- **FastAPI**: Modern, fast web framework for building APIs
- **MarkItDown**: Microsoft's library for converting various file formats to Markdown
- **Uvicorn**: ASGI server for running the FastAPI application
- **python-dotenv**: For loading environment variables
- **aiofiles**: For async file operations
- **pdfminer-six**: For PDF processing support
- **cryptography**: Required for PDF processing

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
1. Check the interactive documentation at `/docs`
2. Review the error messages for troubleshooting
3. Ensure all required dependencies are installed
4. Verify your API keys are correctly configured

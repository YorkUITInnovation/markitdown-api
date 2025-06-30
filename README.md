# MarkItDown API

A FastAPI-based web service that converts files and URLs to Markdown using Microsoft's MarkItDown library.

## Features

- **File Upload & Conversion**: Upload files directly and convert them to Markdown
- **URL Conversion**: Convert web pages and online documents to Markdown
- **Multiple File Formats**: Supports PDF, Word documents, PowerPoint, Excel, images, and more
- **Secure API**: API key authentication for all conversion endpoints
- **Production Security**: Automatic documentation disabling in production environments
- **Auto-reload**: Development server with automatic reloading
- **Interactive Documentation**: Built-in Swagger UI and ReDoc documentation (development only)

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

### Using Docker Compose

1. Create your API keys file:
```bash
cp docker_apikeys.env.example docker_apikeys.env
# Edit docker_apikeys.env with your API keys
```

2. Run with Docker Compose:
```bash
docker-compose up -d
```

### Using Docker directly

```bash
# Build the image
docker build -t markitdown-api .

# Run the container
docker run -d -p 8000:8000 --env-file docker_apikeys.env markitdown-api
```

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

# MarkItDown API

A FastAPI-based service that converts files and URLs to Markdown using Microsoft's MarkItDown library. This API provides a secure endpoint for converting various document formats to Markdown with API key authentication and version management.

**Author:** Patrick Thibaudeau (thibaud@yorku.ca)  
**Built by:** UIT IT Innovation & Academic Technologies, York University

## Features

- 🔄 **Universal File Conversion**: Convert documents, presentations, spreadsheets, PDFs, images, audio files, and more to Markdown
- 🌐 **URL Support**: Download and convert files directly from HTTP/HTTPS URLs
- 🔐 **API Key Authentication**: Secure access with Bearer token authentication
- 🌍 **UTF-8 Encoding**: Proper handling of international characters and various encodings
- 📚 **Interactive Documentation**: Built-in Swagger UI for easy testing
- ⚡ **Fast Processing**: Efficient conversion using Microsoft MarkItDown with full dependency support
- 🏷️ **Version Management**: Built-in version endpoint for API version tracking
- 🎵 **Audio Processing**: Speech-to-text conversion for audio files
- 📊 **Advanced Analytics**: Enhanced Excel and data file processing with pandas
- 🎥 **YouTube Support**: Extract and convert YouTube video transcripts
- ☁️ **Azure Integration**: Support for Azure Document Intelligence

## Supported File Types

This API supports an extensive range of file types through Microsoft MarkItDown with full dependencies:

### Documents & Office Files
- **Microsoft Office**: DOCX, PPTX, XLSX (with advanced formatting preservation)
- **PDFs**: Enhanced PDF processing with pdfminer-six
- **Legacy Office**: XLS files with xlrd support

### Web & Markup
- **Web Content**: HTML, XML with advanced parsing
- **YouTube**: Video transcript extraction

### Images & Media
- **Images**: PNG, JPG, GIF (with OCR capabilities via Pillow)
- **Audio Files**: WAV, MP3, etc. (with speech recognition)

### Data & Text
- **Data Files**: CSV, Excel with pandas integration
- **Text Files**: TXT, MD, and various text formats

### Cloud & Enterprise
- **Azure Documents**: Integration with Azure Document Intelligence
- **SharePoint**: Enhanced support for enterprise document systems

## Installation

### Prerequisites

- Python 3.11 or higher (recommended)
- pip package manager

### Option 1: Local Installation

1. **Clone or download the project**
   ```bash
   git clone <your-repo-url>
   cd markitdown-api
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   # source .venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies with full capabilities**
   ```bash
   pip install -r requirements.txt
   ```
   
   This installs `markitdown[all]` which includes all optional dependencies for maximum functionality.

4. **Configure API keys**
   
   Create a `.env` file in the project root:
   ```env
   # API Keys for MarkItDown API
   # Add your API keys here, separated by commas
   API_KEYS=your-secret-api-key-1,your-secret-api-key-2,another-api-key-here
   ```

5. **Start the server**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Option 2: Docker Installation (Recommended)

#### Prerequisites
- Docker
- Docker Compose (optional but recommended)

#### Quick Start with Docker Compose

1. **Clone the project**
   ```bash
   git clone <your-repo-url>
   cd markitdown-api
   ```

2. **Configure API keys for Docker**
   
   Edit the `docker_apikeys.env` file:
   ```env
   API_KEYS=your-secret-api-key-1,your-secret-api-key-2,another-api-key-here
   ```

3. **Start the service**
   ```bash
   docker-compose up -d
   ```

4. **Check the logs**
   ```bash
   docker-compose logs -f
   ```

#### Manual Docker Build

1. **Build the image**
   ```bash
   docker build -t markitdown-api .
   ```

2. **Run the container with volume-mounted API keys**
   ```bash
   docker run -d \
     --name markitdown-api \
     -p 8000:8000 \
     -v ./markitdown/env/docker_apikeys.env:/app/.env:ro \
     -v ./markitdown/uploads:/app/uploads:rw \
     markitdown-api
   ```

#### Docker API Keys Configuration

The Docker setup uses a volume-mounted configuration file instead of environment variables for better security:

- **Local development**: Use `.env` file
- **Docker deployment**: Use `docker_apikeys.env` file (volume-mounted as read-only)

This approach ensures:
- API keys are not baked into the Docker image
- Keys can be updated without rebuilding the container
- Separate configuration for different deployment environments

### Docker Management Commands

```bash
# View running containers
docker ps

# View logs
docker logs markitdown-api

# Stop the container
docker stop markitdown-api

# Remove the container
docker rm markitdown-api

# Using docker-compose
docker-compose up -d      # Start in background
docker-compose down       # Stop and remove
docker-compose logs -f    # Follow logs
docker-compose restart    # Restart services
```

The API will be available at `http://localhost:8000`

## Usage

### Authentication

All API requests require a valid API key in the Authorization header:

```
Authorization: Bearer your-api-key-here
```

### API Endpoints

#### GET `/version`

Get the current API version (no authentication required).

**Response:**
```json
{
  "version": "1.0.0"
}
```

#### POST `/convert`

Convert a file or URL to Markdown format.

#### Request Body

```json
{
  "source": "path/to/file.pdf"
}
```

or

```json
{
  "source": "https://example.com/document.docx"
}
```

#### Response

```json
{
  "filename": "document",
  "content": "# Converted Markdown Content\n\nYour document content here..."
}
```

### Example Requests

#### Using curl with local file:
```bash
curl -X POST "http://localhost:8000/convert" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer your-api-key" \
     -d '{"source": "/path/to/document.pdf"}'
```

#### Using curl with URL:
```bash
curl -X POST "http://localhost:8000/convert" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer your-api-key" \
     -d '{"source": "https://example.com/presentation.pptx"}'
```

#### Using Python requests:
```python
import requests

url = "http://localhost:8000/convert"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your-api-key"
}
data = {
    "source": "https://example.com/document.pdf"
}

response = requests.post(url, json=data, headers=headers)
result = response.json()

print(f"Filename: {result['filename']}")
print(f"Content: {result['content']}")
```

## Interactive Documentation

Visit `http://localhost:8000/docs` to access the interactive Swagger UI documentation where you can:

1. Click the **"Authorize"** button
2. Enter your API key
3. Test the `/convert` endpoint directly in your browser

## API Response Codes

- **200**: Successful conversion
- **400**: Bad request (invalid URL, download error)
- **401**: Unauthorized (invalid or missing API key)
- **404**: File not found
- **500**: Internal server error (conversion failure)

## Security

### API Key Management

- Store API keys securely in the `.env` file
- Never commit the `.env` file to version control
- Use strong, unique API keys
- Restart the server after changing API keys

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `API_KEYS` | Comma-separated list of valid API keys | `key1,key2,key3` |

### Server Configuration

You can customize the server startup:

```bash
# Custom port
uvicorn main:app --reload --port 8080

# Custom host (for external access)
uvicorn main:app --reload --host 0.0.0.0

# Production mode (no auto-reload)
uvicorn main:app --host 0.0.0.0 --port 8000
```

## File Structure

```
markitdown-api/
├── main.py              # Main FastAPI application
├── .env                 # Environment variables for local development
├── docker_apikeys.env   # API keys for Docker deployment
├── README.md           # This file
├── requirements.txt    # Python dependencies with markitdown[all]
├── Dockerfile          # Docker image configuration
├── docker-compose.yml  # Docker Compose configuration
├── build.sh            # Build script
├── sample.txt          # Sample file for testing
├── test_main.http      # HTTP test file
└── __pycache__/        # Python cache directory
```

## Dependencies

### Core Dependencies
- **FastAPI**: Modern web framework for building APIs
- **MarkItDown[all]**: Microsoft's document-to-markdown converter with all optional dependencies
- **Requests**: HTTP library for downloading URLs
- **python-dotenv**: Environment variable management
- **Uvicorn[standard]**: ASGI server for running FastAPI with enhanced features

### Enhanced Capabilities (included with markitdown[all])
- **openpyxl**: Excel file processing (.xlsx)
- **xlrd**: Legacy Excel file support (.xls)
- **pandas**: Advanced data analysis and CSV processing
- **mammoth**: Enhanced Word document conversion (.docx)
- **python-pptx**: PowerPoint presentation processing
- **pdfminer-six**: Advanced PDF text extraction
- **Pillow**: Image processing and OCR capabilities
- **pydub**: Audio file processing
- **speechrecognition**: Speech-to-text conversion
- **lxml**: Enhanced XML/HTML parsing
- **youtube-transcript-api**: YouTube video transcript extraction
- **azure-ai-documentintelligence**: Azure Document Intelligence integration
- **azure-identity**: Azure authentication support

### Additional Dependencies
- **beautifulsoup4**: Web content parsing
- **defusedxml**: Secure XML processing
- **magika**: File type detection
- **markdownify**: HTML to Markdown conversion

## Troubleshooting

### Common Issues

1. **"No API keys configured" error**
   - Ensure your `.env` file exists and contains `API_KEYS=...`
   - Restart the server after creating/modifying `.env`

2. **401 Unauthorized responses**
   - Check that your API key is correct
   - Ensure the Authorization header format: `Bearer your-key`

3. **File not found errors**
   - Use absolute file paths for local files
   - Ensure the file exists and is readable

4. **URL download failures**
   - Check that the URL is accessible
   - Some servers may block requests; the API includes a User-Agent header

5. **"MissingDependencyException" errors**
   - Ensure you installed with `pip install -r requirements.txt`
   - The requirements.txt includes `markitdown[all]` for full functionality
   - If issues persist, try: `pip uninstall markitdown` then `pip install "markitdown[all]"`

6. **Audio processing issues**
   - Ensure your system has the necessary audio codecs
   - Some audio formats may require additional system-level dependencies

### Development

To run in development mode with detailed logging:

```bash
uvicorn main:app --reload --log-level debug
```

## License

This project uses Microsoft MarkItDown library. Please refer to the [MarkItDown repository](https://github.com/microsoft/markitdown) for licensing information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues related to:
- **Document conversion**: Check the [MarkItDown documentation](https://github.com/microsoft/markitdown)
- **API functionality**: Create an issue in this repository
- **FastAPI usage**: Refer to [FastAPI documentation](https://fastapi.tiangolo.com/)

## Docker Hub Deployment

### Prerequisites for Docker Hub
- Docker Hub account (create one at [hub.docker.com](https://hub.docker.com))
- Docker Desktop installed and running

### Option 1: Automated Build & Push (Recommended)

#### For Linux/macOS:
```bash
# 1. Edit build.sh and replace YOUR_DOCKERHUB_USERNAME with your actual username
# 2. Make the script executable
chmod +x build.sh

# 3. Login to Docker Hub
docker login

# 4. Build and push to Docker Hub
./build.sh build-push
```

#### For Windows (PowerShell):
```powershell
# 1. Edit build.ps1 and replace YOUR_DOCKERHUB_USERNAME with your actual username
# 2. Login to Docker Hub
docker login

# 3. Build and push to Docker Hub
.\build.ps1 build-push
```

### Option 2: Manual Docker Hub Deployment

1. **Login to Docker Hub**
   ```bash
   docker login
   ```

2. **Build and tag your image**
   ```bash
   # Replace 'yourusername' with your Docker Hub username
   docker build -t yourusername/markitdown-api:latest .
   docker tag yourusername/markitdown-api:latest yourusername/markitdown-api:v1.0.0
   ```

3. **Push to Docker Hub**
   ```bash
   docker push yourusername/markitdown-api:latest
   docker push yourusername/markitdown-api:v1.0.0
   ```

### Using Your Published Image

Once published, others can use your image:

```bash
# Pull and run your published image
docker run -d \
  --name markitdown-api \
  -p 8000:8000 \
  -v ./markitdown/env/docker_apikeys.env:/app/.env:ro \
    -v ./markitdown/uploads:/app/uploads:rw \
  yourusername/markitdown-api:latest
```

Or update docker-compose.yml to use your published image:
```yaml
services:
  markitdown-api:
    image: yourusername/markitdown-api:latest  # Use published image instead of build
    ports:
      - "8000:8000"
    volumes:
      - ./markitdown/env/docker_apikeys.env:/app/.env:ro
      - ./markitdown/uploads:/app/uploads:rw
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/docs"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Build Script Commands

| Command | Description |
|---------|-------------|
| `build` | Build Docker image locally |
| `push` | Push existing image to Docker Hub |
| `build-push` | Build and push to Docker Hub |
| `run` | Run container locally |
| `stop` | Stop running container |
| `clean` | Remove image and containers |



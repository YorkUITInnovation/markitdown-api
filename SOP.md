# Standard Operating Procedures (SOP)
## MarkItDown API Project

---

## 1. Authorship

- **Author**: Patrick Thibaudeau, Director IT Innovation & Academic Technologies, York University
- **Created**: July 6, 2025
- **Last Updated**: July 6, 2025

---

## 2. Version Record

| Version | Date | Changes |
|---------|------|---------|
| 1.0     | July 6, 2025 | Initial SOP creation |
| 1.2.3    | July 6, 2025 | Added page numbering functionality |

---

## 3. Glossary

- **MarkItDown API**: A FastAPI-based web service that converts various file formats (PDF, DOCX, images, etc.) to Markdown using Microsoft's MarkItDown library
- **FastAPI**: A modern, fast web framework for building APIs with Python
- **Docker**: Containerization platform used for deployment
- **Uvicorn**: ASGI server for running the FastAPI application
- **API Key**: Authentication token required to access protected endpoints
---

## 4. Introduction

The MarkItDown API is a REST API service that provides document-to-markdown conversion capabilities. It accepts various file formats including PDF, DOCX, images, and other document types, converting them to clean, structured Markdown format. The API includes features for image extraction, page numbering, and automated cleanup processes.

This SOP is intended for developers, system administrators, and DevOps engineers who need to deploy, maintain, or troubleshoot the MarkItDown API service.

---

## 5. Purpose

The MarkItDown API serves to:
- Convert various document formats to Markdown
- Extract and serve images from documents
- Provide page numbering for multi-page documents
- Offer both file upload and URL-based conversion
- Maintain security through API key authentication
- Provide automated image cleanup and maintenance

---

## 6. System Requirements

### Development Environment
- **Python**: 3.11 or higher
- **Operating System**: Windows, Linux, or macOS
- **Memory**: Minimum 2GB RAM (4GB recommended)
- **Storage**: 1GB available disk space

### Dependencies
- FastAPI >= 0.104.1
- uvicorn >= 0.24.0
- markitdown >= 0.1.2
- PyMuPDF >= 1.23.0
- Pillow >= 10.0.0
- requests >= 2.31.0

### Docker Environment
- Docker Engine 20.10+
- Docker Compose 2.0+

---

## 7. Roles and Responsibilities

### System Administrator
- Install and configure the MarkItDown API service
- Manage API keys and authentication
- Monitor system performance and logs
- Perform regular maintenance and updates

### Developer
- Implement new features and bug fixes
- Write and maintain unit tests
- Update documentation
- Review and merge code changes

### DevOps Engineer
- Deploy the application using Docker
- Configure CI/CD pipelines
- Monitor application health and performance
- Manage production environments

---

## 8. Installation Procedures

### 8.1. Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/YorkUITInnovation/markitdown-api
   cd markitdown-api
   ```

2. **Create virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/macOS
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - Set required environment variables:
     - `API_KEY`: Your API authentication key
     - `MAX_UPLOAD_SIZE_MB`: Maximum file upload size (default: 50)
     - `DOCS_ENABLED`: Enable/disable API documentation (default: true)

5. **Start the development server**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### 8.2. Docker Deployment

1. **Build Docker image**
   ```bash
   docker build -t markitdown-api .
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Alternative: Run Docker container directly**
   ```bash
   docker run -d -p 8000:8000 --env-file docker_apikeys.env markitdown-api
   ```

---

## 9. Configuration

### 9.1. Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `API_KEY` | Authentication key for API access | None | Yes |
| `MAX_UPLOAD_SIZE_MB` | Maximum file upload size in MB | 50 | No |
| `DOCS_ENABLED` | Enable API documentation | true | No |
| `CLEANUP_INTERVAL_HOURS` | Image cleanup interval | 24 | No |

### 9.2. API Key Management

1. **Generate API Key**
   - Use a secure random string generator
   - Minimum 32 characters recommended
   - Store securely in environment variables

2. **Configure Authentication**
   - Set `API_KEY` environment variable
   - Clients must include `Authorization: Bearer <api-key>` header

### 9.3. File Upload Configuration

- Maximum file size: Configurable via `MAX_UPLOAD_SIZE_MB`
- Supported formats: PDF, DOCX, XLSX, PPTX, images, text files
- Temporary file storage: System temp directory
- Automatic cleanup: Enabled by default

---

## 10. Operational Procedures

### 10.1. Starting the Service

#### Development Mode
```bash
cd markitdown-api
.venv\Scripts\activate  # Windows
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Production Mode
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Docker Mode
```bash
docker-compose up -d
```

### 10.2. Stopping the Service

#### Development Mode
- Press `Ctrl+C` in terminal
- Or use: `taskkill /f /im python.exe` (Windows)

#### Docker Mode
```bash
docker-compose down
```

### 10.3. Health Monitoring

1. **Check API Health**
   ```bash
   curl http://localhost:8000/version
   ```

2. **Check Cleanup Status**
   ```bash
   curl -H "Authorization: Bearer <api-key>" http://localhost:8000/cleanup-status
   ```

3. **Monitor Logs**
   ```bash
   docker-compose logs -f  # Docker
   # Or check application logs directly
   ```

---

## 11. API Usage

### 11.1. Authentication

All API endpoints require authentication via Bearer token:
```bash
Authorization: Bearer <your-api-key>
```

### 11.2. Available Endpoints

#### Convert File
- **POST** `/convert`
- **Body**: `{"source": "path/to/file.pdf"}`
- **Response**: Markdown content with metadata

#### Upload and Convert
- **POST** `/upload`
- **Body**: Multipart form data with file
- **Response**: Markdown content with extracted images

#### Get Version
- **GET** `/version`
- **Response**: API version information

#### Cleanup Status
- **GET** `/cleanup-status`
- **Response**: Image cleanup scheduler status

### 11.3. Example Usage

```bash
# Convert file by path
curl -X POST "http://localhost:8000/convert" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"source": "/path/to/document.pdf"}'

# Upload and convert file
curl -X POST "http://localhost:8000/upload" \
  -H "Authorization: Bearer your-api-key" \
  -F "file=@document.pdf"
```

---

## 12. Features and Functionality

### 12.1. Page Numbering

The API automatically detects and adds page numbers to converted documents:
- **PDF files**: Intelligent page break detection
- **Long documents**: Automatic pagination based on content length
- **Format**: `## Page 1`, `## Page 2`, etc.
- **Separators**: Horizontal rules (`---`) between pages

### 12.2. Image Extraction

- Automatically extracts images from documents
- Saves images to static directory
- Serves images via HTTP endpoints
- Integrates image references into Markdown

### 12.3. Automatic Cleanup

- Scheduled cleanup of extracted images
- Configurable cleanup interval
- Prevents disk space accumulation
- Maintains system performance

---

## 13. Troubleshooting

### 13.1. Common Issues

#### Service Won't Start
- **Check**: Python version compatibility
- **Check**: All dependencies installed
- **Check**: Port availability (8000)
- **Check**: Environment variables set

#### Authentication Errors
- **Check**: API key configuration
- **Check**: Authorization header format
- **Check**: Environment variable loading

#### File Upload Failures
- **Check**: File size limits
- **Check**: Supported file formats
- **Check**: Disk space availability
- **Check**: Temporary directory permissions

#### Docker Issues
- **Check**: Docker daemon running
- **Check**: Image build completed
- **Check**: Port mapping configuration
- **Check**: Environment file exists

### 13.2. Log Analysis

#### Application Logs
- Check FastAPI/Uvicorn logs for errors
- Monitor conversion process logs
- Review image extraction logs

#### Docker Logs
```bash
docker-compose logs markitdown-api
```

#### System Logs
- Check system resource usage
- Monitor disk space
- Review network connectivity

---

## 14. Maintenance Procedures

### 14.1. Regular Maintenance

#### Daily
- Monitor service health
- Check disk space usage
- Review error logs

#### Weekly
- Review cleanup scheduler status
- Check API key usage
- Monitor performance metrics

#### Monthly
- Update dependencies
- Review security settings
- Backup configuration

### 14.2. Updates and Patches

1. **Backup current configuration**
2. **Test updates in development environment**
3. **Deploy updates with zero downtime**
4. **Verify functionality post-update**
5. **Monitor for issues**

### 14.3. Security Maintenance

- Regular API key rotation
- Dependency security updates
- Access log monitoring
- Vulnerability scanning

---

## 15. Backup and Recovery

### 15.1. Backup Procedures

#### Configuration Backup
- Environment files
- Docker compose files
- API key configuration

#### Data Backup
- Static image directory
- Application logs
- Configuration files

### 15.2. Recovery Procedures

1. **Service Recovery**
   - Restart failed services
   - Restore from backup if needed
   - Verify functionality

2. **Data Recovery**
   - Restore static files
   - Reconfigure environment
   - Test conversion functionality

---

## 16. Performance Optimization

### 16.1. Scaling Considerations

- **Horizontal scaling**: Multiple container instances
- **Load balancing**: Distribute requests
- **Resource limits**: Set appropriate CPU/memory limits
- **Database caching**: Consider Redis for session management

### 16.2. Performance Monitoring

- Response time monitoring
- Resource usage tracking
- Error rate monitoring
- Throughput measurement

---

## 17. Security Considerations

### 17.1. Authentication Security

- Use strong API keys (minimum 32 characters)
- Implement rate limiting
- Log authentication attempts
- Regular key rotation

### 17.2. File Security

- Validate file types and sizes
- Scan uploaded files for malware
- Implement secure file handling
- Clean up temporary files

### 17.3. Network Security

- Use HTTPS in production
- Implement CORS properly
- Secure Docker networking
- Monitor network traffic

---

## 18. Compliance and Documentation

### 18.1. API Documentation

- Automatically generated OpenAPI/Swagger docs
- Available at `/docs` endpoint
- Interactive testing interface
- Complete endpoint documentation

### 18.2. Code Documentation

- Inline code comments
- Function docstrings
- README files
- Architecture documentation

---

## 19. Support and Contact

### 19.1. Technical Support

- **Primary Contact**: Patrick Thibaudeau
- **Email**: [Contact information]
- **Documentation**: Available at `/docs` endpoint
- **Issue Tracking**: GitHub issues

### 19.2. Emergency Procedures

1. **Service Outage**
   - Check service status
   - Review logs for errors
   - Restart services if needed
   - Escalate if unresolved

2. **Security Incident**
   - Disable affected services
   - Review access logs
   - Rotate API keys
   - Document incident

---

## 20. Appendices

### Appendix A: Environment File Template

```bash
# API Configuration
API_KEY=your-secure-api-key-here
MAX_UPLOAD_SIZE_MB=50
DOCS_ENABLED=true

# Cleanup Configuration
CLEANUP_INTERVAL_HOURS=24

# Development Settings
DEBUG=false
LOG_LEVEL=INFO
```

### Appendix B: Docker Compose Example

```yaml
version: '3.8'
services:
  markitdown-api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - docker_apikeys.env
    volumes:
      - ./markitdown/images:/static/images  # Persist extracted images
      - ./markitdown/uploads:/app/uploads
    restart: unless-stopped
```

### Appendix C: Build Script Usage

```bash
# Build Docker image
./build.sh build

# Push to registry
./build.sh push

# Deploy container
./build.sh deploy
```

---

**Document Status**: Active  
**Review Date**: July 6, 2026  
**Next Review**: Annual

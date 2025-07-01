# Use Python 3.11 slim image for better performance and security
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for image processing and PDF handling
RUN apt-get update && apt-get install -y \
    # For PDF processing and image handling
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # For image processing libraries
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    # For archive handling
    unzip \
    p7zip-full \
    # For general file processing
    libffi-dev \
    libssl-dev \
    # Add curl for health checks
    curl \
    # Add ffmpeg for audio/video processing
    ffmpeg \
    # Add cron for potential scheduling (though we use Python scheduler)
    cron \
    # Clean up to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN useradd --create-home --shell /bin/bash appuser

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies including new scheduler dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    # Install additional dependencies for full functionality
    pip install --no-cache-dir markitdown[all] && \
    # Install additional image processing libraries
    pip install --no-cache-dir Pillow PyMuPDF python-docx && \
    # Ensure scheduling dependencies are installed
    pip install --no-cache-dir schedule python-dotenv

# Copy application code
COPY . .

# Create directories for static files and uploads with proper ownership
# Updated to use root-level /static directory for image cleanup system
RUN mkdir -p /static/images && \
    mkdir -p /app/uploads && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /static && \
    chmod -R 755 /app && \
    chmod -R 755 /static && \
    # Ensure appuser can write to images directory for cleanup operations
    chmod -R 775 /static/images

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check to ensure the application is running properly
# Updated to include cleanup status monitoring
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/version || exit 1

# Set environment variables for optimal container operation
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
# Default cleanup configuration (can be overridden)
ENV IMAGE_CLEANUP_DAYS=7
ENV IMAGE_CLEANUP_TIME=02:00

# Run the application with image cleanup scheduler
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

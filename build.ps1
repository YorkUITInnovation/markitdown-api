# MarkItDown API - Docker Build Script (PowerShell)
# This script builds and manages the Docker image for the MarkItDown API

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

# Configuration
$DOCKER_HUB_USERNAME = "YOUR_DOCKERHUB_USERNAME"  # Replace with your Docker Hub username
$IMAGE_NAME = "markitdown-api"
$IMAGE_TAG = "latest"
$ADDITIONAL_TAGS = @("v1.0.0", "stable")
$CONTAINER_NAME = "markitdown-api-container"
$PORT = "8000"

# Full image name for Docker Hub
$DOCKER_HUB_IMAGE = "${DOCKER_HUB_USERNAME}/${IMAGE_NAME}"

# Function to print colored output
function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Blue
}

function Write-Success($message) {
    Write-Host "[SUCCESS] $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor Yellow
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

# Function to check if Docker is installed and running
function Test-Docker {
    Write-Info "Checking Docker installation..."

    if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is not installed. Please install Docker Desktop first."
        exit 1
    }

    try {
        docker info | Out-Null
        Write-Success "Docker is installed and running"
    }
    catch {
        Write-Error "Docker daemon is not running. Please start Docker Desktop."
        exit 1
    }
}

# Function to build Docker image
function Build-Image {
    Write-Info "Building Docker image: ${DOCKER_HUB_IMAGE}:${IMAGE_TAG}"

    # Build the image
    docker build -t "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}" .

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker image built successfully!"

        # Tag additional versions
        foreach ($tag in $ADDITIONAL_TAGS) {
            Write-Info "Tagging image as: ${DOCKER_HUB_IMAGE}:${tag}"
            docker tag "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}" "${DOCKER_HUB_IMAGE}:${tag}"
        }
    }
    else {
        Write-Error "Failed to build Docker image"
        exit 1
    }
}

# Function to push to Docker Hub
function Push-ToHub {
    Write-Info "Pushing to Docker Hub..."

    # Check if logged in (simplified check)
    try {
        $loginCheck = docker info 2>$null | Select-String "Username:"
        if (!$loginCheck) {
            Write-Warning "Not logged in to Docker Hub. Please run: docker login"
            docker login
        }
    }
    catch {
        Write-Info "Attempting to login to Docker Hub..."
        docker login
    }

    # Push main image
    Write-Info "Pushing ${DOCKER_HUB_IMAGE}:${IMAGE_TAG}"
    docker push "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}"

    # Push additional tags
    foreach ($tag in $ADDITIONAL_TAGS) {
        Write-Info "Pushing ${DOCKER_HUB_IMAGE}:${tag}"
        docker push "${DOCKER_HUB_IMAGE}:${tag}"
    }

    Write-Success "Successfully pushed to Docker Hub!"
    Write-Info "Your image is available at: https://hub.docker.com/r/${DOCKER_HUB_USERNAME}/${IMAGE_NAME}"
}

# Function to run container
function Start-Container {
    Write-Info "Starting container: ${CONTAINER_NAME}"

    # Stop and remove existing container if it exists
    $existingContainer = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $CONTAINER_NAME }
    if ($existingContainer) {
        Write-Info "Stopping existing container..."
        docker stop $CONTAINER_NAME
        docker rm $CONTAINER_NAME
    }

    # Run new container with volume-mounted API keys
    docker run -d `
        --name $CONTAINER_NAME `
        -p "${PORT}:8000" `
        -v "${PWD}/docker_apikeys.env:/app/.env:ro" `
        --restart unless-stopped `
        "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}"

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Container started successfully"
        Write-Info "API is available at: http://localhost:${PORT}"
        Write-Info "Documentation at: http://localhost:${PORT}/docs"
    }
    else {
        Write-Error "Failed to start container"
        exit 1
    }
}

# Function to show help
function Show-Help {
    Write-Host "MarkItDown API - Docker Build Script (PowerShell)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\build.ps1 [COMMAND]" -ForegroundColor White
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor White
    Write-Host "  build          Build Docker image" -ForegroundColor Gray
    Write-Host "  push           Push image to Docker Hub" -ForegroundColor Gray
    Write-Host "  build-push     Build and push to Docker Hub" -ForegroundColor Gray
    Write-Host "  run            Run container locally" -ForegroundColor Gray
    Write-Host "  stop           Stop running container" -ForegroundColor Gray
    Write-Host "  clean          Remove image and containers" -ForegroundColor Gray
    Write-Host "  help           Show this help message" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor White
    Write-Host "  .\build.ps1 build-push     # Build and upload to Docker Hub" -ForegroundColor Gray
    Write-Host "  .\build.ps1 build         # Just build locally" -ForegroundColor Gray
    Write-Host "  .\build.ps1 push          # Push existing image to Docker Hub" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Before first use:" -ForegroundColor Yellow
    Write-Host "1. Edit this script and replace YOUR_DOCKERHUB_USERNAME with your actual Docker Hub username" -ForegroundColor Gray
    Write-Host "2. Edit docker_apikeys.env with your API keys" -ForegroundColor Gray
    Write-Host "3. Run: docker login" -ForegroundColor Gray
}

# Main script logic
switch ($Command.ToLower()) {
    "build" {
        Test-Docker
        Build-Image
    }
    "push" {
        Test-Docker
        Push-ToHub
    }
    "build-push" {
        Test-Docker
        Build-Image
        Push-ToHub
    }
    "run" {
        Test-Docker
        Start-Container
    }
    "stop" {
        Test-Docker
        docker stop $CONTAINER_NAME
        Write-Success "Container stopped"
    }
    "clean" {
        Test-Docker
        docker stop $CONTAINER_NAME 2>$null
        docker rm $CONTAINER_NAME 2>$null
        docker rmi "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}" 2>$null
        Write-Success "Cleanup completed"
    }
    default {
        Show-Help
    }
}

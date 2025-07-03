#!/bin/bash

# MarkItDown API - Docker Build Script
# This script builds and manages the Docker image for the MarkItDown API

set -e  # Exit on any error

# Configuration
DOCKER_HUB_USERNAME="YOUR_DOCKERHUB_USERNAME"  # Replace with your Docker Hub username
IMAGE_NAME="markitdown-api"
IMAGE_TAG="latest"
# Additional tags (space-separated)
ADDITIONAL_TAGS="v1.0.0 Stable"
CONTAINER_NAME="markitdown-api-container"
PORT="8000"

# Full image name for Docker Hub
DOCKER_HUB_IMAGE="${DOCKER_HUB_USERNAME}/${IMAGE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is installed and running
check_docker() {
    print_info "Checking Docker installation..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    print_success "Docker is installed and running"
}

# Function to check if .env file exists
check_env_file() {
    if [ ! -f ".env" ]; then
        print_warning ".env file not found!"
        print_info "Creating a sample .env file..."
        cat > .env << EOF
# API Keys for MarkItDown API
# Replace these with your actual API keys
API_KEYS=sk-markitdown-12345,sk-markitdown-67890,my-custom-key-abc123
EOF
        print_success "Sample .env file created. Please edit it with your actual API keys."
    else
        print_success ".env file found"
    fi
}

# Function to build the Docker image
build_image() {
    print_info "Building Docker image: ${DOCKER_HUB_IMAGE}:${IMAGE_TAG}"

    # Build the main image
    if docker build -t "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}" .; then
        print_success "Docker image built successfully with tag: ${IMAGE_TAG}"

        # Apply additional tags if specified
        if [ -n "$ADDITIONAL_TAGS" ]; then
            print_info "Applying additional tags..."
            for tag in $ADDITIONAL_TAGS; do
                if docker tag "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}" "${DOCKER_HUB_IMAGE}:${tag}"; then
                    print_success "Tagged image as: ${DOCKER_HUB_IMAGE}:${tag}"
                else
                    print_warning "Failed to apply tag: ${tag}"
                fi
            done
        fi

        print_info "Available image tags:"
        docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Function to push to Docker Hub
push_to_hub() {
    print_info "Pushing to Docker Hub..."

    # Check if logged in to Docker Hub
    if ! docker info | grep -q "Username:"; then
        print_warning "Not logged in to Docker Hub. Please run: docker login"
        print_info "Attempting to login..."
        docker login
    fi

    # Push main image
    print_info "Pushing ${DOCKER_HUB_IMAGE}:${IMAGE_TAG}"
    docker push "${DOCKER_HUB_IMAGE}:${IMAGE_TAG}"

    # Push additional tags
    for tag in $ADDITIONAL_TAGS; do
        print_info "Pushing ${DOCKER_HUB_IMAGE}:${tag}"
        docker push "${DOCKER_HUB_IMAGE}:${tag}"
    done

    print_success "Successfully pushed to Docker Hub!"
    print_info "Your image is available at: https://hub.docker.com/r/${DOCKER_HUB_USERNAME}/${IMAGE_NAME}"
}

# Function to run the container
run_container() {
    print_info "Starting container: ${CONTAINER_NAME}"

    # Stop and remove existing container if it exists
    if docker ps -a --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_info "Stopping existing container..."
        docker stop "${CONTAINER_NAME}" || true
        docker rm "${CONTAINER_NAME}" || true
    fi

    # Run new container
    if docker run -d \
        --name "${CONTAINER_NAME}" \
        -p "${PORT}:8000" \
        --env-file .env \
        --restart unless-stopped \
        "${IMAGE_NAME}:${IMAGE_TAG}"; then
        print_success "Container started successfully"
        print_info "API is available at: http://localhost:${PORT}"
        print_info "Documentation at: http://localhost:${PORT}/docs"
    else
        print_error "Failed to start container"
        exit 1
    fi
}

# Function to stop the container
stop_container() {
    print_info "Stopping container: ${CONTAINER_NAME}"

    if docker stop "${CONTAINER_NAME}" 2>/dev/null; then
        print_success "Container stopped successfully"
    else
        print_warning "Container was not running or does not exist"
    fi
}

# Function to remove the container
remove_container() {
    print_info "Removing container: ${CONTAINER_NAME}"

    if docker rm "${CONTAINER_NAME}" 2>/dev/null; then
        print_success "Container removed successfully"
    else
        print_warning "Container does not exist"
    fi
}

# Function to show container logs
show_logs() {
    print_info "Showing logs for container: ${CONTAINER_NAME}"
    docker logs -f "${CONTAINER_NAME}"
}

# Function to show container status
show_status() {
    print_info "Container status:"
    docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Function to clean up (remove container and image)
cleanup() {
    print_info "Cleaning up..."

    # Stop and remove container
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true

    # Remove image
    if docker rmi "${IMAGE_NAME}:${IMAGE_TAG}" 2>/dev/null; then
        print_success "Cleanup completed"
    else
        print_warning "Image may not exist or is being used by other containers"
    fi
}

# Function to show help
show_help() {
    echo "MarkItDown API - Docker Build Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build          Build Docker image"
    echo "  push           Push image to Docker Hub"
    echo "  build-push     Build and push to Docker Hub"
    echo "  run            Run container locally"
    echo "  stop           Stop running container"
    echo "  clean          Remove image and containers"
    echo "  help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build-push     # Build and upload to Docker Hub"
    echo "  $0 build         # Just build locally"
    echo "  $0 push          # Push existing image to Docker Hub"
}

# Main script logic
case "${1:-help}" in
    build)
        check_docker
        check_env_file
        build_image
        ;;
    push)
        push_to_hub
        ;;
    build-push)
        check_docker
        check_env_file
        build_image
        push_to_hub
        ;;
    run)
        check_docker
        check_env_file
        build_image
        run_container
        ;;
    stop)
        check_docker
        stop_container
        ;;
    restart)
        check_docker
        stop_container
        sleep 2
        if docker start "${CONTAINER_NAME}" 2>/dev/null; then
            print_success "Container restarted"
        else
            print_error "Failed to restart container"
        fi
        ;;
    logs)
        check_docker
        show_logs
        ;;
    status)
        check_docker
        show_status
        ;;
    cleanup)
        check_docker
        cleanup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

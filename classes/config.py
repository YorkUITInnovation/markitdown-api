import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the main project directory
# Get the parent directory of the classes folder (which is the main project directory)
main_dir = Path(__file__).parent.parent
env_path = main_dir / ".env"
load_dotenv(env_path)

# Application version
API_VERSION = "1.2.1"

# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
DISABLE_DOCS = os.getenv("DISABLE_DOCS", "false").lower() == "true"

# File upload configuration
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))  # Default 100MB

# Image cleanup configuration
IMAGE_CLEANUP_DAYS = int(os.getenv("IMAGE_CLEANUP_DAYS", "7"))  # Default 7 days
IMAGE_CLEANUP_TIME = os.getenv("IMAGE_CLEANUP_TIME", "02:00")  # Default 2:00 AM (24-hour format HH:MM)

# Determine if docs should be enabled
# Disable docs in production or when explicitly disabled
docs_enabled = ENVIRONMENT != "production" and not DISABLE_DOCS

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Load environment variables from the main project directory
# Get the parent directory of the classes folder (which is the main project directory)
main_dir = Path(__file__).parent.parent
env_path = main_dir / ".env"
load_dotenv(env_path)

# Security - HTTPBearer for API key authentication
security = HTTPBearer()

def get_valid_api_keys():
    """Load API keys from environment variables"""
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

#!/usr/bin/env python3
"""
Test script to demonstrate the new create_pages parameter functionality
"""
import requests
import json

# API configuration
BASE_URL = "http://localhost:8000"
API_KEY = "your-api-key-here"  # Replace with your actual API key

def test_convert_with_pages():
    """Test the /convert endpoint with create_pages=True (default)"""
    url = f"{BASE_URL}/convert"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "source": "test.pdf",  # Replace with actual file path
        "create_pages": True
    }

    print("Testing /convert with create_pages=True...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success! Pages created in markdown: {'## Page' in result['content']}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def test_convert_without_pages():
    """Test the /convert endpoint with create_pages=False"""
    url = f"{BASE_URL}/convert"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "source": "test.pdf",  # Replace with actual file path
        "create_pages": False
    }

    print("Testing /convert with create_pages=False...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success! No pages created: {'## Page' not in result['content']}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def test_upload_with_pages():
    """Test the /upload endpoint with create_pages=True (default)"""
    url = f"{BASE_URL}/upload"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    # Use a sample file for testing
    files = {"file": ("test.pdf", open("test.pdf", "rb"), "application/pdf")}
    data = {"create_pages": "true"}

    print("Testing /upload with create_pages=True...")
    response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success! Pages created in markdown: {'## Page' in result['content']}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def test_upload_without_pages():
    """Test the /upload endpoint with create_pages=False"""
    url = f"{BASE_URL}/upload"
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    # Use a sample file for testing
    files = {"file": ("test.pdf", open("test.pdf", "rb"), "application/pdf")}
    data = {"create_pages": "false"}

    print("Testing /upload with create_pages=False...")
    response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Success! No pages created: {'## Page' not in result['content']}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    print("Testing create_pages parameter functionality...\n")

    # Test convert endpoint
    test_convert_with_pages()
    test_convert_without_pages()

    print()

    # Test upload endpoint
    test_upload_with_pages()
    test_upload_without_pages()

    print("\nTesting complete!")

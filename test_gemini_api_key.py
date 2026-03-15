"""
Test if the Google API key is valid and check available models.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ GOOGLE_API_KEY not found")
    exit(1)

print(f"🔑 API Key found: {api_key[:20]}...")

try:
    # Configure the API
    genai.configure(api_key=api_key)
    
    print("\n📋 Listing available models...")
    
    # List all available models
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"  ✅ {model.name}")
            print(f"     Display Name: {model.display_name}")
            print(f"     Description: {model.description[:80]}...")
            print()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print(f"\nFull error: {str(e)}")

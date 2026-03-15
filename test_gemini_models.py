"""
Test script to verify which Gemini models are actually available.
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Test models - using actual available models from Google API
TEST_MODELS = [
    # Stable Gemini 2.5 series (recommended)
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    
    # Stable Gemini 2.0 series
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    
    # Latest aliases
    "gemini-flash-latest",
    "gemini-pro-latest",
    
    # Preview models (Gemini 3.x)
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite-preview",
]

async def test_model(model_name: str, api_key: str) -> tuple[str, bool, str]:
    """Test if a model works."""
    try:
        llm = ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model_name,
            temperature=0.1,
            convert_system_message_to_human=True,
        )
        
        # Simple test message
        messages = [HumanMessage(content="Say 'OK' if you can read this.")]
        response = await llm.ainvoke(messages)
        
        return (model_name, True, str(response.content)[:50])
    except Exception as e:
        error_msg = str(e)
        # Extract the key part of the error
        if "INVALID_ARGUMENT" in error_msg:
            return (model_name, False, "Model does not exist (400 INVALID_ARGUMENT)")
        elif "404" in error_msg:
            return (model_name, False, "Model not found (404)")
        else:
            return (model_name, False, f"Error: {error_msg[:100]}")

async def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment")
        return
    
    print("🧪 Testing Gemini Models...")
    print("=" * 80)
    
    results = []
    for model in TEST_MODELS:
        print(f"\nTesting: {model}...", end=" ")
        result = await test_model(model, api_key)
        results.append(result)
        
        if result[1]:
            print(f"✅ WORKS - Response: {result[2]}")
        else:
            print(f"❌ FAILED - {result[2]}")
    
    print("\n" + "=" * 80)
    print("\n📊 SUMMARY:")
    print("\nWorking Models:")
    working = [r for r in results if r[1]]
    if working:
        for model, _, response in working:
            print(f"  ✅ {model}")
    else:
        print("  None found")
    
    print("\nFailed Models:")
    failed = [r for r in results if not r[1]]
    if failed:
        for model, _, error in failed:
            print(f"  ❌ {model} - {error}")
    else:
        print("  None")
    
    print("\n" + "=" * 80)
    print(f"\n✅ Working: {len(working)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")

if __name__ == "__main__":
    asyncio.run(main())

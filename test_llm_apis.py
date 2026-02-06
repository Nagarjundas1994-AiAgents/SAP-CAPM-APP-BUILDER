"""
LLM API Test Script
Tests OpenAI, Google Gemini, and DeepSeek APIs
"""
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_openai():
    """Test OpenAI API"""
    print("\n" + "="*50)
    print("🧪 Testing OpenAI API...")
    print("="*50)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return False
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using cheaper model for testing
            messages=[{"role": "user", "content": "Say 'Hello, I am working!' in one line."}],
            max_tokens=20
        )
        
        result = response.choices[0].message.content
        print(f"✅ OpenAI Response: {result}")
        return True
    except Exception as e:
        print(f"❌ OpenAI Error: {e}")
        return False


async def test_gemini():
    """Test Google Gemini API"""
    print("\n" + "="*50)
    print("🧪 Testing Google Gemini API...")
    print("="*50)
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not set")
        return False
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Say 'Hello, I am working!' in one line.")
        
        result = response.text
        print(f"✅ Gemini Response: {result}")
        return True
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return False


async def test_deepseek():
    """Test DeepSeek API"""
    print("\n" + "="*50)
    print("🧪 Testing DeepSeek API...")
    print("="*50)
    
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not set")
        return False
    
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Say 'Hello, I am working!' in one line."}],
            max_tokens=20
        )
        
        result = response.choices[0].message.content
        print(f"✅ DeepSeek Response: {result}")
        return True
    except Exception as e:
        print(f"❌ DeepSeek Error: {e}")
        return False


async def main():
    print("\n" + "🔥"*25)
    print("   LLM API CONNECTIVITY TEST")
    print("🔥"*25)
    
    results = {}
    
    # Test each provider
    results["OpenAI"] = await test_openai()
    results["Gemini"] = await test_gemini()
    results["DeepSeek"] = await test_deepseek()
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    for provider, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {provider}: {status}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\n  Total: {passed}/{total} providers working")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())

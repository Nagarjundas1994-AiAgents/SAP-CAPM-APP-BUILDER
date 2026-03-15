"""
Final test to verify Gemini 2.5 Flash works end-to-end.
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

async def test_gemini_2_5_flash():
    """Test Gemini 2.5 Flash with a simple SAP CAP code generation task."""
    
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("❌ GOOGLE_API_KEY not found")
        return False
    
    print("🧪 Testing Gemini 2.5 Flash for SAP CAP code generation...")
    print("=" * 80)
    
    try:
        # Initialize the model
        llm = ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model="gemini-2.5-flash",
            temperature=0.1,
            convert_system_message_to_human=True,
        )
        
        # Test with a simple SAP CAP task
        system_prompt = "You are an expert SAP CAP developer. Generate valid CDS code."
        user_prompt = """Generate a simple CDS entity for a Product with fields: ID, name, price.
Return ONLY the CDS code, no explanation."""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        print("\n📤 Sending request to Gemini 2.5 Flash...")
        response = await llm.ainvoke(messages)
        
        print("\n✅ SUCCESS! Gemini 2.5 Flash is working!")
        print("\n📥 Response:")
        print("-" * 80)
        print(response.content)
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return False

async def main():
    success = await test_gemini_2_5_flash()
    
    print("\n" + "=" * 80)
    if success:
        print("\n🎉 Gemini 2.5 Flash is ready to use!")
        print("\nYou can now:")
        print("  1. Restart your backend server")
        print("  2. Select 'Gemini 2.5 Flash' in the frontend")
        print("  3. Generate SAP CAP applications with Google Gemini")
    else:
        print("\n⚠️ There was an issue. Check the error above.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

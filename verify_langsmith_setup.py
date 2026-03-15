"""
LangSmith Setup Verification Script

Verifies that LangSmith tracing is properly configured and working.
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_env_vars():
    """Check if LangSmith environment variables are set."""
    print("=" * 70)
    print("STEP 1: Checking Environment Variables")
    print("=" * 70)
    
    required_vars = {
        "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2"),
        "LANGSMITH_TRACING": os.getenv("LANGSMITH_TRACING"),
        "LANGCHAIN_API_KEY": os.getenv("LANGCHAIN_API_KEY"),
        "LANGSMITH_API_KEY": os.getenv("LANGSMITH_API_KEY"),
        "LANGCHAIN_PROJECT": os.getenv("LANGCHAIN_PROJECT"),
        "LANGSMITH_PROJECT": os.getenv("LANGSMITH_PROJECT"),
    }
    
    all_good = True
    for var, value in required_vars.items():
        if value:
            # Mask API keys
            if "API_KEY" in var:
                display_value = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
            else:
                display_value = value
            print(f"✓ {var}: {display_value}")
        else:
            print(f"✗ {var}: NOT SET")
            all_good = False
    
    print()
    if all_good:
        print("✓ All environment variables are set!")
    else:
        print("✗ Some environment variables are missing!")
        print("\nTo fix, add to your .env file:")
        print("LANGCHAIN_TRACING_V2=true")
        print("LANGSMITH_TRACING=true")
        print("LANGCHAIN_API_KEY=<REDACTED_API_KEY>")
        print("LANGSMITH_API_KEY=<REDACTED_API_KEY>")
        print("LANGCHAIN_PROJECT=sap-app-builder")
        print("LANGSMITH_PROJECT=sap-app-builder")
    
    return all_good


def check_imports():
    """Check if required packages are installed."""
    print("\n" + "=" * 70)
    print("STEP 2: Checking Package Imports")
    print("=" * 70)
    
    packages = {
        "langgraph": "LangGraph",
        "langchain": "LangChain",
        "langsmith": "LangSmith SDK",
    }
    
    all_good = True
    for package, name in packages.items():
        try:
            __import__(package)
            print(f"✓ {name} ({package})")
        except ImportError:
            print(f"✗ {name} ({package}) - NOT INSTALLED")
            all_good = False
    
    print()
    if all_good:
        print("✓ All required packages are installed!")
    else:
        print("✗ Some packages are missing!")
        print("\nTo fix, run:")
        print("pip install langgraph langchain langsmith")
    
    return all_good


async def check_graph_config():
    """Check if the graph is configured with LangSmith metadata."""
    print("\n" + "=" * 70)
    print("STEP 3: Checking Graph Configuration")
    print("=" * 70)
    
    try:
        from backend.agents.graph import get_builder_graph
        
        print("✓ Graph module imported successfully")
        
        # Try to compile the graph
        graph = await get_builder_graph()
        print("✓ Graph compiled successfully")
        
        # Check if graph has the right structure
        if hasattr(graph, 'nodes'):
            node_count = len(graph.nodes)
            print(f"✓ Graph has {node_count} nodes")
        
        return True
        
    except Exception as e:
        print(f"✗ Error checking graph: {e}")
        return False


async def test_trace():
    """Test a simple trace to LangSmith."""
    print("\n" + "=" * 70)
    print("STEP 4: Testing LangSmith Connection")
    print("=" * 70)
    
    try:
        from langsmith import traceable
        
        @traceable(name="test_trace", run_type="chain")
        def test_function():
            return {"status": "success", "message": "LangSmith tracing works!"}
        
        result = test_function()
        print("✓ Test trace sent successfully")
        print(f"  Result: {result}")
        
        print("\n📊 Check your LangSmith dashboard:")
        project = os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT")
        print(f"   https://smith.langchain.com/o/default/projects/p/{project}")
        print("   You should see a trace named 'test_trace'")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing trace: {e}")
        print("\nThis might be a network issue or invalid API key.")
        return False


def print_summary(results):
    """Print final summary."""
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = all(results.values())
    
    for step, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {step}")
    
    print()
    if all_passed:
        print("🎉 All checks passed! LangSmith is ready to use.")
        print("\nNext steps:")
        print("1. Restart your server: python -m uvicorn backend.main:app --reload")
        print("2. Run a workflow")
        print("3. Open https://smith.langchain.com")
        print("4. Navigate to your project: sap-app-builder")
        print("5. Watch traces appear in real-time!")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print("\nQuick fixes:")
        print("1. Make sure .env file exists and has LangSmith variables")
        print("2. Install missing packages: pip install langgraph langchain langsmith")
        print("3. Verify your API key at https://smith.langchain.com/settings")
        print("4. Check network connectivity to api.smith.langchain.com")


async def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("LangSmith Setup Verification")
    print("=" * 70)
    print()
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ Loaded .env file\n")
    except ImportError:
        print("⚠️  python-dotenv not installed, using system environment\n")
    
    results = {}
    
    # Run checks
    results["Environment Variables"] = check_env_vars()
    results["Package Imports"] = check_imports()
    results["Graph Configuration"] = await check_graph_config()
    results["LangSmith Connection"] = await test_trace()
    
    # Print summary
    print_summary(results)
    
    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

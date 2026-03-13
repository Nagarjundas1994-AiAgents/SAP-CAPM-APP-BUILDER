import asyncio
import os
import sys
from pprint import pprint

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.requirements import requirements_agent
from backend.agents.state import create_initial_state

async def test_agent():
    state = create_initial_state("test-session", "Logistics App", "com.logistics", "Test description")
    state["domain"] = "Logistics"
    state["template"] = "logistics"
    state["llm_provider"] = "xai"
    state["llm_model"] = "grok-4-1-fast-reasoning"
    
    print("Running requirements agent...")
    try:
        result = await requirements_agent(state)
        print("Success! Entities:")
        pprint(result.get("entities", []))
    except Exception as e:
        print("AGENT FAILED TO RUN!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())

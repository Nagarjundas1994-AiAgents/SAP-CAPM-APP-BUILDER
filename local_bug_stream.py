import asyncio
import traceback
from backend.agents.graph import get_builder_graph
from backend.agents.state import create_initial_state

async def main():
    state = create_initial_state(
        session_id="test-session-123",
        project_name="Ecommerce Test",
        project_description="An ecommerce platform",
    )
    
    state["domain_type"] = "ecommerce"
    state["entities"] = [
        {"name": "Product", "fields": [{"name": "ID", "type": "UUID"}]},
        {"name": "Category", "fields": [{"name": "ID", "type": "UUID"}]},
    ]
    state["llm_provider"] = "gemini"
    state["relationships"] = []
    state["business_rules"] = []
    
    graph = get_builder_graph()
    
    try:
        print("Running graph.astream locally...")
        async for event in graph.astream(state):
            print("Received event:", list(event.keys()))
        print("Success!")
    except Exception:
        print("Crash caught! Here is the clean traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

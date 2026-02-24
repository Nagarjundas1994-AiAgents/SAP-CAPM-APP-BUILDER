import asyncio
import traceback
from backend.agents.requirements import requirements_agent
from backend.agents.state import create_initial_state

async def main():
    state = create_initial_state(
        session_id="test",
        project_name="Ecommerce Test",
        project_description="An ecommerce platform",
    )
    
    # Configure state like the frontend does when approving plan
    state["domain_type"] = "ecommerce"
    state["entities"] = [
        {"name": "Product", "fields": [{"name": "ID", "type": "UUID"}]},
        {"name": "Category", "fields": [{"name": "ID", "type": "UUID"}]},
    ]
    state["llm_provider"] = "gemini"
    
    # Intentionally empty relationships (like the bug condition)
    state["relationships"] = []
    state["business_rules"] = []
    
    try:
        print("Running requirements_agent locally...")
        result = await requirements_agent(state)
        print("Success! Entities returned:", len(result["entities"]))
    except Exception as e:
        print("Crash caught! Here is the clean traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

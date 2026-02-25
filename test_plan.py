import asyncio
import logging
from backend.agents.requirements import requirements_agent
from backend.agents.state import create_initial_state

logging.basicConfig(level=logging.DEBUG)

async def test():
    entities = [
        {"name": "PurchaseOrder"},
        {"name": "PurchaseOrderItem"},
        {"name": "Vendor"},
        {"name": "ApprovalWorkflow"},
        {"name": "Budget"},
        {"name": "CostCenter"},
        {"name": "Contract"},
        {"name": "GoodsReceipt"},
        {"name": "Invoice"},
        {"name": "AuditLog"}
    ]
    initial_state = create_initial_state(
        session_id="test-123",
        project_name="Procurement Hub",
        project_namespace="com.enterprise.procurement",
        project_description="Enterprise procurement management with multi-level approval workflows, budget tracking, vendor management, and purchase order lifecycle automation",
    )
    initial_state["entities"] = entities
    initial_state["complexity_level"] = "full_stack"
    initial_state["llm_provider"] = "deepseek" # Using DeepSeek
    
    print("Testing requirements agent directly with OpenAI...")
    try:
        plan_state = await requirements_agent(initial_state)
        print("Success! Entities returned:", len(plan_state.get("entities", [])))
        print("Business Rules:", len(plan_state.get("business_rules", [])))
    except Exception as e:
        print(f"FAILED with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test())

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from backend.agents.llm_providers import get_llm_manager
from backend.agents.requirements import DOMAIN_ANALYSIS_PROMPT, REQUIREMENTS_SYSTEM_PROMPT, _parse_llm_json

async def debug_llm():
    llm = get_llm_manager()
    prompt = DOMAIN_ANALYSIS_PROMPT.format(
        project_name="Global Supply Chain System",
        description="An enterprise system to track warehouses, inventory levels across regions, supplier orders, and shipments. Must include entities for Warehouse, Product, Supplier, Order, OrderItem, and Shipment.",
        domain_type="Supply Chain",
        entity_context="No entities specified — you must identify the right entities for this domain.",
        additional_context="Generate 4-8 entities that form a complete, realistic business application. Think about what entities a real enterprise would need — not a basic tutorial. Include transactional entities, master data, and line-item entities.",
    )
    
    print("Sending prompt to OpenAI...")
    try:
        response = await llm.generate(
            prompt=prompt,
            system_prompt=REQUIREMENTS_SYSTEM_PROMPT,
            provider="deepseek",
            temperature=0.1
        )
        print("--- RAW RESPONSE ---")
        print(response)
        print("--- PARSED JSON ---")
        parsed = _parse_llm_json(response)
        print("Success!" if parsed else "Failed to parse JSON")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_llm())

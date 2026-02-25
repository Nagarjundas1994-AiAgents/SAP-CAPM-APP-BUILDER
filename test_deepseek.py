import asyncio
from backend.agents.llm_providers import get_llm_manager
from backend.agents.requirements import DOMAIN_ANALYSIS_PROMPT, REQUIREMENTS_SYSTEM_PROMPT

async def get():
    llm = get_llm_manager()
    prompt = DOMAIN_ANALYSIS_PROMPT.format(
        project_name="Global Supply Chain System",
        description="An enterprise system to track warehouses, inventory levels across regions, supplier orders, and shipments. Must include entities for Warehouse, Product, Supplier, Order, OrderItem, and Shipment.",
        domain_type="Supply Chain",
        entity_context="No entities specified — you must identify the right entities for this domain.",
        additional_context="Generate 4-8 entities that form a complete, realistic business application. Think about what entities a real enterprise would need — not a basic tutorial. Include transactional entities, master data, and line-item entities.",
    )
    
    res = await llm.generate(
        prompt=prompt,
        system_prompt=REQUIREMENTS_SYSTEM_PROMPT,
        provider="deepseek",
        temperature=0.1
    )
    with open("raw_deepseek.txt", "w", encoding="utf-8") as f:
        f.write(res)
    print("Done writing to raw_deepseek.txt")

if __name__ == "__main__":
    asyncio.run(get())

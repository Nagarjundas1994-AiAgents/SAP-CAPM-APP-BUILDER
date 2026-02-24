import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Create session
        print("Creating session...")
        res = await client.post("http://localhost:8000/api/sessions", json={
            "project_name": "Ecommerce Test",
            "project_description": "An ecommerce platform"
        })
        res.raise_for_status()
        session_id = res.json()["id"]
        print(f"Session: {session_id}")

        # Step 2: Configure session like frontend step 5
        print("PUT config...")
        config = {
            "configuration": {
                "domain": "ecommerce",
                "entities": [{"name": e, "fields": []} for e in ["Product", "Category", "Order", "OrderItem", "Customer", "Review"]],
                "llm_provider": "gemini",
                "fiori_theme": "sap_horizon",
                "auth_type": "mock",
                "fiori_main_entity": "Product"
            }
        }
        res = await client.put(f"http://localhost:8000/api/sessions/{session_id}/config", json=config)
        res.raise_for_status()

        # Step 3: Generate Plan
        print("Generating plan... (waiting for LLM)")
        res = await client.post(f"http://localhost:8000/api/builder/{session_id}/plan")
        if res.status_code != 200:
            print("Failed to generate plan:", res.text)
            return
        print("Plan generated successfully!")
        
        # Add print to see EXACTLY what was generated!
        plan_data = res.json()
        print("GENERATED ENTITIES:", json.dumps(plan_data["entities"], indent=2))

        # Step 4: Approve Plan
        print("Approving plan...")
        res = await client.post(f"http://localhost:8000/api/builder/{session_id}/plan/approve")
        res.raise_for_status()

        # Step 5: Start Stream
        print(f"Triggering generation for {session_id}...")
        try:
            async with client.stream("GET", f"http://localhost:8000/api/builder/{session_id}/generate/stream") as response:
                async for chunk in response.aiter_text():
                    print(chunk, end="")
        except Exception as e:
            print("Caught exception in stream!:", e)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # Create session
        res = await client.post("http://localhost:8000/api/sessions", json={
            "project_name": "Test Error App"
        })
        session_id = res.json()["id"]

        # Update session with entities (simulate UI "Review Plan" output)
        config = {
            "configuration": {
                "entities": [
                    {"name": "Customer", "fields": [{"name": "ID", "type": "UUID", "key": True}]},
                    {"name": "Order", "fields": [{"name": "ID", "type": "UUID", "key": True}]}
                ],
                "llm_provider": "gemini"
            }
        }
        await client.put(f"http://localhost:8000/api/sessions/{session_id}/config", json=config)

        # Trigger generation stream
        print(f"Triggering generation for {session_id}...")
        async with client.stream("GET", f"http://localhost:8000/api/builder/{session_id}/generate/stream") as response:
            async for chunk in response.aiter_text():
                print(chunk, end="")

if __name__ == "__main__":
    asyncio.run(main())

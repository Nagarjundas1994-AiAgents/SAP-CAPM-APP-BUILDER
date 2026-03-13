import httpx
import json
import asyncio
import os

API_BASE = "http://localhost:8000/api"

async def main():
    print("Testing E2E App Generation Pipeline...")
    
    session_payload = {
        "project_name": "E2E Procurement Test",
        "project_namespace": "com.enterprise.e2e",
        "project_description": "Complex procurement system for E2E testing.",
        "configuration": {
            "domain": "custom",
            "entities": [
                {"name": "Supplier", "fields": []},
                {"name": "PurchaseOrder", "fields": []},
                {"name": "OrderItem", "fields": []},
                {"name": "Invoice", "fields": []}
            ],
            "llm_provider": "xai",
            "llm_model": "grok-4-1-fast-reasoning",
            "complexity_level": "standard"
        }
    }
    
    report_lines = ["# E2E Test Report\n"]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create session
        print("Creating session...")
        res = await client.post(f"{API_BASE}/sessions", json=session_payload)
        res.raise_for_status()
        session_id = res.json()["id"]
        print(f"Session Created: {session_id}")
        report_lines.append(f"- **Session ID:** `{session_id}`")
        
        print("Triggering generation via SSE stream...")
        report_lines.append("- **Generation Triggered via SSE Stream**\n")
        report_lines.append("## Events Log\n")
        
        # Listen to stream
        print("Listening to SSE stream...")
        async with client.stream("GET", f"{API_BASE}/builder/{session_id}/generate/stream", timeout=600.0) as stream:
            async for line in stream.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                    event_type = data.get("type")
                    if event_type == "agent_start":
                        msg = f"- 🔄 **Agent Started:** {data.get('agent')}"
                        print(msg)
                        report_lines.append(msg)
                    elif event_type == "agent_log":
                        # Only log some to avoid clutter
                        pass
                    elif event_type == "agent_complete":
                        msg = f"- ✅ **Agent Complete:** {data.get('agent')}"
                        print(msg)
                        report_lines.append(msg)
                    elif event_type == "workflow_complete":
                        msg = "\n🎉 **Workflow Complete!** All agents successfully ran."
                        print(msg)
                        report_lines.append(msg)
                        break
                    elif event_type in ("error", "workflow_error"):
                        msg = f"\n❌ **Error Encountered:** {data.get('error', data.get('message', 'Unknown'))}"
                        print(msg)
                        report_lines.append(msg)
                        break
                except Exception as e:
                    print(f"Error parsing line: {line} - {e}")

    with open("test_e2e_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print("Done. Report saved to test_e2e_report.md")

if __name__ == "__main__":
    asyncio.run(main())

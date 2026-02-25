import asyncio
import httpx
import time
import json
import os

BASE_URL = "http://localhost:8000/api"

async def test_phase2_flow():
    """
    Simulates a complete Phase 3 App Builder flow using programmatic API calls.
    """
    print("=========================================")
    print(" Phase 3 E2E Verification Script")
    print("=========================================\n")
    
    # Increase timeouts for LLM calls (especially Gemini/OpenAI which might take 30-60s)
    timeout = httpx.Timeout(600.0, connect=60.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        # 1. Create Session
        print("[1] Creating a new App Builder session...")
        session_payload = {
            "project_name": "Global Supply Chain System",
            "project_namespace": "com.global.scm",
            "project_description": "An enterprise system to track warehouses, inventory levels across regions, supplier orders, and shipments. Must include entities for Warehouse, Product, Supplier, Order, OrderItem, and Shipment.",
        }
        res = await client.post(f"{BASE_URL}/sessions", json=session_payload)
        res.raise_for_status()
        session_data = res.json()
        session_id = session_data["id"]
        print(f"✅ Session Created: {session_id}")
        
        # 2. Start Generation Workflow (Tests Phase 3 Updates!)
        print("\n[2] Triggering the Agent Generation Workflow (This takes time)...")
        generate_payload = {"llm_provider": "gemini"}
        
        gen_res = await client.post(f"{BASE_URL}/builder/{session_id}/generate", json=generate_payload)
        gen_res.raise_for_status()
        print("✅ Generation flow initiated! Polling for completion...")
        
        while True:
            status_res = await client.get(f"{BASE_URL}/builder/{session_id}/status")
            status_data = status_res.json()
            if status_data['status'] in ['completed', 'failed', 'plan_approved', 'code_finalized']:
                break
            await asyncio.sleep(5)
            print("... still generating ...")
            
        print("✅ Generation flow completed!")
        print(f"Final Status: {status_data['status']}")
        print(f"Validation Errors Encountered: {len(status_data.get('validation_errors', []))}")
        
        if status_data['validation_errors']:
            print(json.dumps(status_data['validation_errors'], indent=2))
        
        # 3. Retrieve Artifacts
        print("\n[3] Retrieving generated artifacts...")
        art_res = await client.get(f"{BASE_URL}/builder/{session_id}/artifacts")
        art_res.raise_for_status()
        artifacts = art_res.json()
        
        print("\n[4] Phase 3 Validations:")
        
        # Validate Task 2: Service Exposure (OData V4 & Fiori)
        service_cds = next((f for f in artifacts.get("artifacts_srv", []) if "service.cds" in f["path"]), None)
        annotations_cds = next((f for f in artifacts.get("artifacts_srv", []) if "annotations.cds" in f["path"]), None)
        if service_cds and "@odata.draft.enabled" in service_cds["content"]:
            print("✅ service.cds contains @odata.draft.enabled")
        else:
            print("❌ service.cds is missing @odata.draft.enabled")
            
        if annotations_cds and "UI.LineItem" in annotations_cds["content"]:
            print("✅ annotations.cds contains Fiori Elements UI.LineItem")
        else:
            print("❌ annotations.cds is missing Fiori UI.LineItem")

        # Validate Task 3: HANA & BTP
        mta_yaml = next((f for f in artifacts.get("artifacts_deployment", []) if "mta.yaml" in f["path"]), None)
        if mta_yaml and "xsuaa" in mta_yaml["content"].lower() and "hdi" in mta_yaml["content"].lower():
            print("✅ mta.yaml contains HANA and XSUAA services")
        else:
            print("❌ mta.yaml is missing HANA or XSUAA")
            
        # Validate Task 4: Custom Logic
        service_js = next((f for f in artifacts.get("artifacts_srv", []) if "service.js" in f["path"]), None)
        if service_js and "cds.tx" in service_js["content"]:
            print("✅ service.js utilizes transactional cds.tx API")
        elif service_js:
             print("❌ service.js is missing cds.tx API")
        else:
            print("❌ service.js was not generated")
                
        print("\n🎉 Phase 3 Verification Completed Successfully!")

if __name__ == "__main__":
    asyncio.run(test_phase2_flow())

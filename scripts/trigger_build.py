import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000/api"

print("1. Creating session...")
session_data = {
    "project_name": "E-Commerce Platform",
    "description": "A complex e-commerce application with products, orders, customers, and inventory management.",
    "company_namespace": "com.ecommerce",
    "features": ["OData V4", "Fiori Elements", "Authentication", "Draft Enabled"]
}
response = requests.post(f"{BASE_URL}/sessions", json=session_data)

if not response.ok:
    print(f"Failed to create session: {response.text}")
    sys.exit(1)

session = response.json()
session_id = session["id"]
print(f"Session created with ID: {session_id}")

print("\n2. Starting generation (using deepseek provider)...")
# Depending on your current backend implementation, you might need to adjust this payload
generate_payload = {
    "llm_provider": "deepseek",
    "llm_model": "deepseek-chat"
}

# Add retry logic just in case the server needs a moment
max_retries = 3
for attempt in range(max_retries):
    try:
        response = requests.post(f"{BASE_URL}/builder/{session_id}/generate", json=generate_payload)
        
        # If generation starts successfully or another acceptable status is returned
        if response.status_code in [200, 202]:
            print(f"Generation started successfully for session: {session_id}")
            break
        else:
             print(f"Attempt {attempt + 1}: Failed to start generation (Status: {response.status_code}): {response.text}")
    except Exception as e:
        print(f"Attempt {attempt + 1}: Exception starting generation: {e}")
    
    if attempt < max_retries - 1:
        time.sleep(2)
        print("Retrying...")

if attempt == max_retries - 1 and (response is None or response.status_code not in [200, 202]):
     print("Failed to start generation after maximum retries. Exiting.")
     sys.exit(1)


print("\n3. Polling for status...")
while True:
    try:
        response = requests.get(f"{BASE_URL}/builder/{session_id}/status")
        if response.status_code == 200:
            status = response.json()
            print(f"Status: {status.get('status')} | Current Agent: {status.get('current_agent', 'N/A')}")
            
            if status.get("status") == "completed":
                print("\n✅ Generation completed successfully!")
                break
            elif status.get("status") == "failed":
                print(f"\n❌ Generation failed. Error: {status.get('error')}")
                break
                
            time.sleep(3)
        else:
             print(f"Failed to fetch status: {response.text}. Retrying in 5 seconds...")
             time.sleep(5)
    except Exception as e:
         print(f"Exception while checking status: {e}. Retrying in 5 seconds...")
         time.sleep(5)

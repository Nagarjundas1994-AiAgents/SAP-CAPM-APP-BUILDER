import sys
sys.path.append('e:/REAL_PROJECTS/SAP CAPM APP BUILDER')

from backend.main import app
from fastapi.testclient import TestClient

def test():
    with TestClient(app) as client:
        print("Testing /api/config")
        try:
            response = client.get("/api/config")
            print(f"Status: {response.status_code}")
            print(response.json())
        except Exception as e:
            import traceback
            traceback.print_exc()
            
        print("\nTesting /api/config/models?provider=openai")
        try:
            response = client.get("/api/config/models?provider=openai")
            print(f"Status: {response.status_code}")
            if response.status_code != 200:
                print(response.json())
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test()

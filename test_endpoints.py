import urllib.request
import json
try:
    req = urllib.request.Request("http://localhost:8000/api/config/models?provider=xai")
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except urllib.error.HTTPError as e:
    print("GET models 500:")
    print(e.read().decode())

try:
    req = urllib.request.Request("http://localhost:8000/api/sessions", data=json.dumps({"project_name": "Test"}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except urllib.error.HTTPError as e:
    print("POST sessions 500:")
    print(e.read().decode())

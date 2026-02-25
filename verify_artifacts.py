import httpx

res = httpx.get('http://localhost:8000/api/builder/3044164c-1431-476b-bf26-357abcb4b4cb/artifacts')
if res.status_code == 200:
    for k, v in res.json().items():
        if v:
            print(f"✅ Generated: {k}")
        else:
            print(f"❌ Missing: {k}")
else:
    print(res.text)

import json

with open("generation_output_openai.log", "rb") as f:
    text = f.read().decode("utf-16le", errors="replace")
    
for line in text.split("\n"):
    line = line.strip()
    if line.startswith("data: {") and "workflow_error" in line:
        try:
            data = json.loads(line[6:])
            print("ERROR FOUND:")
            print(data.get("error", "No error key"))
        except Exception as e:
            print("Failed to parse JSON:", e)
            print("Raw Line:", line)

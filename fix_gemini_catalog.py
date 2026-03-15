"""
Script to fix the Gemini model catalog with working models only.
Run this to update backend/model_catalog.py
"""

import re

# Read the current file
with open("backend/model_catalog.py", "r", encoding="utf-8") as f:
    content = f.read()

# New Gemini models section (only working models)
new_gemini_section = '''    "gemini": [
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "label": "Gemini 2.5 Flash (Recommended)",
            "pricing_type": "paid",
            "price_summary": "$0.30 / $2.50 per 1M tokens",
            "created_at": None,
            "context_length": 1000000,
            "description": "Fast and efficient model for chat, agents, and production apps. Tested and working.",
            "source": "static",
            "recommended": True,
        },
        {
            "id": "gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash Lite",
            "label": "Gemini 2.5 Flash Lite (High Volume)",
            "pricing_type": "paid",
            "price_summary": "$0.10 / $0.40 per 1M tokens",
            "created_at": None,
            "context_length": 1000000,
            "description": "Ultra low-cost model for high-volume AI workloads. Tested and working.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-flash-latest",
            "name": "Gemini Flash Latest",
            "label": "Gemini Flash Latest (Auto-Updated)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": 1000000,
            "description": "Latest release of Gemini Flash - automatically updated. Tested and working.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "label": "Gemini 2.5 Pro (Most Powerful)",
            "pricing_type": "paid",
            "price_summary": "$1.25 / $10.00 per 1M tokens",
            "created_at": None,
            "context_length": 1000000,
            "description": "High capability model for reasoning, coding and long-context workloads.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-pro-latest",
            "name": "Gemini Pro Latest",
            "label": "Gemini Pro Latest (Auto-Updated)",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": 1000000,
            "description": "Latest release of Gemini Pro - automatically updated.",
            "source": "static",
            "recommended": False,
        },
        {
            "id": "gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "label": "Gemini 2.0 Flash",
            "pricing_type": "paid",
            "price_summary": None,
            "created_at": None,
            "context_length": 1000000,
            "description": "Previous generation Gemini 2.0 Flash model.",
            "source": "static",
            "recommended": False,
        },
    ],'''

# Find and replace the gemini section using regex
pattern = r'"gemini":\s*\[.*?\],\s*"deepseek"'
replacement = f'"gemini": [\n{new_gemini_section.split("[", 1)[1].rsplit("],", 1)[0]}\n    ],\n    "deepseek"'

# Use DOTALL flag to match across newlines
new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

if new_content != content:
    # Write back
    with open("backend/model_catalog.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("✅ Successfully updated backend/model_catalog.py with working Gemini models!")
    print("\nUpdated models:")
    print("  - gemini-2.5-flash (Recommended)")
    print("  - gemini-2.5-flash-lite")
    print("  - gemini-flash-latest")
    print("  - gemini-2.5-pro")
    print("  - gemini-pro-latest")
    print("  - gemini-2.0-flash")
else:
    print("❌ Could not find the gemini section to replace")
    print("Please manually update backend/model_catalog.py using GEMINI_FIX_SUMMARY.md")

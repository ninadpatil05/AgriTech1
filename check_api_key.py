"""
Run this FIRST before starting Flask:
    python check_api_key.py

It tells you exactly which Gemini models work with your API key
and how to fix the key if something is wrong.
"""
import os, sys, requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY", "")

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODELS = [
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

print("=" * 60)
print("AgriTech — Gemini API Key Diagnostic")
print("=" * 60)

if not API_KEY:
    print("❌  GEMINI_API_KEY is not set in your .env file!")
    print("    Get a key at: https://aistudio.google.com/app/apikey")
    sys.exit(1)

print(f"Key prefix: {API_KEY[:12]}...")
print()

working = []
for model in MODELS:
    url = f"{BASE}/{model}:generateContent"
    try:
        r = requests.post(
            url,
            params={"key": API_KEY},
            json={"contents": [{"parts": [{"text": "Say: ok"}]}],
                  "generationConfig": {"maxOutputTokens": 5}},
            timeout=15,
        )
        if r.status_code == 200:
            print(f"  ✅  {model}  — WORKING")
            working.append(model)
        elif r.status_code == 404:
            print(f"  ❌  {model}  — 404 (not available for your key/billing plan)")
        elif r.status_code == 403:
            body = r.text
            if "allowlist" in body.lower():
                print(f"  ❌  {model}  — 403 HOST RESTRICTION")
            else:
                print(f"  ❌  {model}  — 403 Forbidden: {body[:120]}")
        elif r.status_code == 429:
            print(f"  ⚠️   {model}  — 429 Rate limited (key works but quota hit)")
            working.append(model)
        else:
            print(f"  ❌  {model}  — {r.status_code}: {r.text[:80]}")
    except requests.exceptions.ConnectionError:
        print(f"  ❌  {model}  — Cannot connect. Check your internet.")
    except Exception as e:
        print(f"  ❌  {model}  — {e}")

print()
if working:
    print(f"✅  Your key works! Best model: {working[0]}")
    print("   You can now run:  python app.py")
else:
    print("❌  NO models are working. Most likely cause:")
    print()
    print("   Your API key has HOST or IP RESTRICTIONS set.")
    print("   Flask makes server-to-server calls (no browser referrer),")
    print("   which are blocked by restricted keys.")
    print()
    print("   FIX (takes 2 minutes):")
    print("   1. Go to: https://aistudio.google.com/app/apikey")
    print("   2. Click 'Create API key'")
    print("   3. Select your project")
    print("   4. Leave restrictions as 'None' (default)")
    print("   5. Copy the new key")
    print("   6. Open your .env file and replace:")
    print("      GEMINI_API_KEY=<paste new key here>")
    print("   7. Run this script again to confirm it works")
    print("   8. Then run: python app.py")

print("=" * 60)

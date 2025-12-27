"""
Test script to verify ScraperAPI and Gemini API keys are working
"""
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from dotenv import load_dotenv
import requests
import asyncio

# Load .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"✅ Loaded .env from: {env_path}")
else:
    load_dotenv(override=True)
    print("⚠️  No .env file found, using system environment variables")

# Check ScraperAPI
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY")
print(f"\n{'='*60}")
print("SCRAPERAPI TEST")
print(f"{'='*60}")
if SCRAPERAPI_KEY:
    masked_key = SCRAPERAPI_KEY[:4] + "..." + SCRAPERAPI_KEY[-4:] if len(SCRAPERAPI_KEY) > 8 else "***"
    print(f"✅ Key found: {masked_key}")
    # Don't print full key for security
    
    # Test ScraperAPI
    print("\n🧪 Testing ScraperAPI...")
    test_url = "https://www.amazon.in/dp/B08N5WRWNW"
    try:
        response = requests.get(
            "http://api.scraperapi.com",
            params={
                'api_key': SCRAPERAPI_KEY,
                'url': test_url,
                'render': 'false',
                'country_code': 'in',
            },
            timeout=10
        )
        if response.status_code == 200:
            print(f"✅ ScraperAPI is WORKING! Status: {response.status_code}")
            print(f"   Response length: {len(response.text)} characters")
        else:
            print(f"❌ ScraperAPI returned status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ ScraperAPI test failed: {str(e)}")
else:
    print("❌ SCRAPERAPI_KEY not found in environment!")

# Check Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print(f"\n{'='*60}")
print("GEMINI API TEST")
print(f"{'='*60}")
if GEMINI_API_KEY:
    masked_key = GEMINI_API_KEY[:4] + "..." + GEMINI_API_KEY[-4:] if len(GEMINI_API_KEY) > 8 else "***"
    print(f"✅ Key found: {masked_key}")
    # Don't print full key for security
    
    # Test Gemini API
    print("\n🧪 Testing Gemini API...")
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("Say 'Hello' if you can read this.")
        if response.text:
            print(f"✅ Gemini API is WORKING!")
            print(f"   Response: {response.text[:100]}")
        else:
            print(f"❌ Gemini API returned empty response")
    except Exception as e:
        print(f"❌ Gemini API test failed: {str(e)}")
else:
    print("❌ GEMINI_API_KEY not found in environment!")
    print("   Add it to backend/.env file: GEMINI_API_KEY=your_key_here")

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"ScraperAPI: {'✅ Working' if SCRAPERAPI_KEY else '❌ Not configured'}")
print(f"Gemini API: {'✅ Working' if GEMINI_API_KEY else '❌ Not configured'}")


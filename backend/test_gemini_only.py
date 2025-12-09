"""Test Gemini AI with simple product data"""
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")
    
genai.configure(api_key=GEMINI_API_KEY)

# Simple product data
product_data = {
    'title': 'ASUS WT300 Wireless Mouse',
    'price': '₹606',
    'specs': ['Ergonomic design', '1600 DPI', 'Wireless 2.4GHz']
}

# Very simple prompt
prompt = f"""Find 3 alternative wireless mouse products. Return ONLY JSON:

{{
  "category": "wireless mouse",
  "alternatives": [
    {{
      "id": "1",
      "brand": "Logitech",
      "model": "M185",
      "title": "Logitech M185 Wireless Mouse",
      "image_url": "",
      "price_estimate": "₹500",
      "price_raw": 500,
      "rating_estimate": 4.0,
      "rating_count_estimate": 1000,
      "specs": ["Wireless", "Compact", "Durable"],
      "connectivity": [],
      "why_pick": "Affordable and reliable",
      "tradeoffs": "Basic features",
      "search_query": "Logitech M185 wireless mouse",
      "source_site": "amazon"
    }}
  ]
}}

Return ONLY the JSON, no other text."""

print("🧪 Testing Gemini API...")
print(f"Prompt length: {len(prompt)} chars")
print("=" * 60)

try:
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(
        prompt,
        generation_config={
            'temperature': 0.2,
            'top_p': 0.8,
            'top_k': 20,
            'max_output_tokens': 1500,
        },
        safety_settings=[
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
    )
    
    print(f"\n✅ Response received!")
    print(f"Candidates: {len(response.candidates) if response.candidates else 0}")
    
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]
        finish_reason = getattr(candidate, 'finish_reason', None)
        print(f"Finish reason: {finish_reason}")
        
        if finish_reason and ('SAFETY' in str(finish_reason) or finish_reason == 2):
            print(f"❌ BLOCKED BY SAFETY FILTER")
            print(f"Safety ratings: {candidate.safety_ratings if hasattr(candidate, 'safety_ratings') else 'N/A'}")
        else:
            text = response.text
            print(f"\n✅ Got response ({len(text)} chars):")
            print(text[:500])
            
            # Try to parse JSON
            try:
                data = json.loads(text)
                print(f"\n✅ Valid JSON!")
                print(f"Alternatives: {len(data.get('alternatives', []))}")
            except Exception as e:
                print(f"\n❌ JSON parse error: {str(e)}")
    else:
        print(f"❌ No candidates in response")
        
except Exception as e:
    print(f"\n❌ Gemini API ERROR: {str(e)}")



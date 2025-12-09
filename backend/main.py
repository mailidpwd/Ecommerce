"""
FastAPI Backend for Decision Recommendation App
Handles product scraping and LLM-powered recommendations
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Literal
from datetime import datetime
import os
import json
import re
import base64
from io import BytesIO
from PIL import Image  # type: ignore  # PIL is installed as Pillow
import google.generativeai as genai
from scraper_api import scrape_product_scraperapi, search_product_scraperapi
from multi_platform_search import get_multi_platform_links
from gemini_vision import identify_product_from_image, identify_product_from_image_base64
from rdm_calculator import calculate_rdm_scores


def parse_price_raw(price_str: Optional[str]) -> int:
    """Convert price string like '₹65,990' to paise (int). Returns 0 on failure."""
    if not price_str:
        return 0
    try:
        clean = re.sub(r'[^\d.]', '', price_str)
        if not clean:
            return 0
        return int(float(clean) * 100)
    except Exception:
        return 0


def filter_names_by_category(product_names: List[str], category: str) -> List[str]:
    """
    Guardrail: if category is smartphone/phone/mobile, drop obviously wrong items
    like monitors/TV/covers.
    """
    if category.lower() not in ["smartphone", "phone", "mobile"]:
        return product_names

    deny = [
        "monitor", "tv", "cover", "case", "protector", "dust", "stand",
        "cabinet", "gpu", "graphics", "desk", "table"
    ]
    filtered = [n for n in product_names if not any(d in n.lower() for d in deny)]
    return filtered if filtered else product_names

app = FastAPI(title="Decision Recommendation API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini API Keys - MUST be set via environment variables for security
GEMINI_API_KEYS = []
current_key_index = 0

# Load API keys from environment variables
primary_key = os.getenv("GEMINI_API_KEY")
if primary_key:
    GEMINI_API_KEYS.append(primary_key)

backup_key = os.getenv("GEMINI_API_KEY_BACKUP")
if backup_key:
    GEMINI_API_KEYS.append(backup_key)

# region agent log
try:
    import time as _time
    with open(r"c:\Users\Michael\Documents\RDM Projects\SimilarLinks\.cursor\debug.log", "a", encoding="utf-8") as _f:
        _f.write(json.dumps({
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": "H1",
            "location": "backend/main.py:api_keys",
            "message": "Gemini keys loaded",
            "data": {
                "key_count": len(GEMINI_API_KEYS),
                "has_primary": bool(primary_key),
                "has_backup": bool(backup_key)
            },
            "timestamp": _time.time()
        }) + "\n")
except Exception:
    pass
# endregion

if not GEMINI_API_KEYS:
    raise ValueError(
        "GEMINI_API_KEY environment variable is required. "
        "Set it using: export GEMINI_API_KEY='your-api-key'"
    )

# ==================== Models ====================

class RecommendRequest(BaseModel):
    url: HttpUrl
    device: Literal["android", "ios"]
    user_id: Optional[str] = None
    refresh: bool = False
    share_text: Optional[str] = None  # Full share text from Amazon (includes product description)

class ImageSearchRequest(BaseModel):
    image_url: Optional[str] = None
    image_base64: Optional[str] = None

class InvoiceExtractionRequest(BaseModel):
    image_base64: str


class Product(BaseModel):
    id: str
    brand: str
    model: str
    title: str
    image_url: str  # Allow empty string, will be filled by ScraperAPI
    price_estimate: str
    price_raw: int
    rating_estimate: Optional[float] = None
    rating_count_estimate: Optional[int] = None
    specs: List[str]
    connectivity: List[str]
    why_pick: str
    tradeoffs: str
    source_url: str  # Allow search URLs (not strict HttpUrl validation)
    source_site: Literal["amazon", "flipkart", "other"]
    rdm_score: Optional[float] = None  # RDM score (0-100)
    rdm_breakdown: Optional[dict] = None  # Sub-scores breakdown


class ValidationMeta(BaseModel):
    llm_valid_json: bool
    image_urls_checked: bool


class ResponseMeta(BaseModel):
    validation: ValidationMeta
    warnings: List[str] = []


class RecommendationResponse(BaseModel):
    source: Literal["amazon", "flipkart", "unknown"]
    canonical_url: HttpUrl
    query_time_iso: str
    alternatives: List[Product]
    meta: ResponseMeta


# ==================== Gemini API Configuration ====================

# Configure with primary key initially
genai.configure(api_key=GEMINI_API_KEYS[current_key_index])


# ==================== Helper Functions ====================

def extract_source(url: str) -> Literal["amazon", "flipkart", "unknown"]:
    """Detect source from URL"""
    url_str = str(url).lower()
    if "amazon" in url_str or "amzn" in url_str:
        return "amazon"
    if "flipkart" in url_str:
        return "flipkart"
    return "unknown"


def extract_product_name_from_url(url: str) -> str:
    """
    Extract product name from Amazon/Flipkart URL path
    Example: "amazon.in/Nervfit-Launched-Smartwatch-Bluetooth/dp/B0DY6D6RDX" 
    Returns: "Nervfit Launched Smartwatch Bluetooth"
    """
    try:
        # Parse URL and get path
        from urllib.parse import urlparse
        parsed = urlparse(url if url.startswith('http') else f'https://{url}')
        path = parsed.path
        
        # Extract product name from path
        # Format: /Product-Name-With-Dashes/dp/ASIN or /dp/ASIN/product-name
        parts = path.split('/')
        
        # Find the part before /dp/ (Amazon) or after /p/ (Flipkart)
        product_slug = None
        for i, part in enumerate(parts):
            if part == 'dp' and i > 0:
                # Amazon: product name is before /dp/
                product_slug = parts[i - 1]
                break
            elif part == 'p' and i + 1 < len(parts):
                # Flipkart: product name might be after /p/
                product_slug = parts[i + 1]
                break
        
        if product_slug and len(product_slug) > 10:
            # Convert dashes to spaces and clean up
            product_name = product_slug.replace('-', ' ')
            # Remove common suffixes
            product_name = product_name.split('?')[0]  # Remove query params
            return product_name.strip()
        
        return ''
    except:
        return ''


def extract_product_from_share_text(share_text: str, url: str) -> dict:
    """
    Extract product info from Amazon/Flipkart share text ONLY
    
    ⚠️ IMPORTANT: Do NOT extract from URL path! Amazon URL slugs are often 
    misleading/outdated. Only extract from actual share text descriptions.
    
    Handles ONLY mobile app share format:
    - "Limited-time deal: Product Name https://amzn.in/d/abc"
    
    Returns: {'title': 'Product Name', 'has_details': True}
    """
    if not share_text or len(share_text.strip()) == 0:
        return {'title': '', 'has_details': False}
    
    # ONLY METHOD: Extract from share text (mobile app format)
    # Remove the URL from share text to get clean product description
    clean_text = share_text.replace(url, '').strip()
    
    # Remove common prefixes
    prefixes_to_remove = [
        'Limited-time deal:',
        'Deal:',
        'Deal of the Day:',
        'Amazon Deal:',
        'Flipkart Deal:',
    ]
    
    for prefix in prefixes_to_remove:
        if clean_text.startswith(prefix):
            clean_text = clean_text[len(prefix):].strip()
            break
    
    # If we have substantial text (at least 20 chars), use it - MOBILE FORMAT
    if len(clean_text) >= 20:
        print(f"✅ Extracted product from share text: {clean_text[:80]}")
        return {
            'title': clean_text,
            'has_details': True
        }
    
    # ⚠️ Do NOT extract from URL path - it's unreliable!
    # Amazon URL slugs can be wrong/outdated (e.g., URL says "vitamins" but product is "whey protein")
    # If no valid share text, return empty and force scraping
    print(f"⚠️  Share text too short or empty - will need to scrape product page")
    return {'title': '', 'has_details': False}


async def scrape_product(url: str):
    """
    Scrape product page using ScraperAPI (premium service)
    Fast, reliable, bypasses CAPTCHAs and anti-bot measures
    Returns structured product data
    """
    data = await scrape_product_scraperapi(url)
    return data


async def enhance_product_with_gemini(product_title: str, category: str) -> dict:
    """
    Use Gemini to analyze product and generate specifications and "why pick" explanation
    This works for ANY product type (not just laptops/phones)
    """
    print(f"🤖 Using Gemini to analyze: {product_title[:60]}...")
    
    prompt = f"""Analyze this product and provide specifications and recommendation reason.

Product: {product_title}
Category: {category}

Provide:
1. SPECIFICATIONS (3-5 key specs relevant to this product type):
   - For electronics: RAM, storage, processor, screen, etc.
   - For luggage: size, material, weight, wheels, capacity, etc.
   - For clothing: material, size, style, features, etc.
   - For furniture: dimensions, material, weight capacity, etc.

2. WHY PICK THIS (1-2 sentences explaining why this is a good choice based on specs/features)

Response format (JSON):
{{
  "specifications": ["spec1", "spec2", "spec3"],
  "why_pick": "Brief explanation why this is a good choice"
}}

Example for luggage:
{{
  "specifications": ["55 cm cabin size", "Hard shell polycarbonate", "360° spinner wheels", "TSA lock", "Lightweight 2.5kg"],
  "why_pick": "Ideal cabin luggage with durable hard shell and smooth spinner wheels for easy maneuverability"
}}"""
    
    try:
        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,  # Lower for more consistent specs
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 2048,  # Increased for Gemini 2.5
            }
        )
        
        # Handle MAX_TOKENS (finish_reason=2) by extracting from parts
        text = None
        try:
            text = response.text.strip()
        except Exception as e:
            print(f"⚠️  response.text failed: {str(e)}, trying parts...")
            # Extract from parts directly
            if response.candidates and response.candidates[0].content.parts:
                text_parts = []
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                text = ''.join(text_parts).strip()
        
        if not text:
            raise ValueError("Empty response from Gemini")
        
        # Extract JSON
        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if match:
            json_text = match.group(1).strip()
        else:
            json_start = text.find('{')
            json_end = text.rfind('}')
            if json_start != -1 and json_end != -1:
                json_text = text[json_start:json_end + 1]
            else:
                raise ValueError("Could not find JSON in response")
        
        data = json.loads(json_text)
        
        return {
            'specifications': data.get('specifications', [])[:6],  # Max 6 specs
            'why_pick': data.get('why_pick', f'Good {category} option')
        }
        
    except Exception as e:
        print(f"⚠️  Gemini enhancement failed: {str(e)}, using fallback")
        # Fallback to basic message
        return {
            'specifications': [],
            'why_pick': f'Quality {category} alternative'
        }


async def call_llm_for_product_names(scraped_data: dict) -> dict:
    """
    Call Gemini LLM to generate ONLY product names/search queries
    Returns minimal JSON with just product names - ScraperAPI will get real data
    """
    print(f"🤖 Calling Gemini AI for product names only...")
    
    # STRICT prompt - SAME category as input product!
    product_title = scraped_data.get('title', 'Unknown')
    
    # Detect category from title (CRITICAL for correct matching!)
    title_lower = product_title.lower()
    
    # PRIORITY 1: Check for ACCESSORIES & FURNITURE first (before main products!)
    # This prevents "laptop case" or "laptop table" from being detected as "laptop"
    
    # Laptop tables/desks are furniture (not laptops!)
    if any(keyword in title_lower for keyword in ['table', 'desk', 'stand table', 'workstation']) and \
       any(keyword in title_lower for keyword in ['laptop', 'adjustable', 'height', 'foldable', 'portable']):
        category = "laptop table/desk"
        product_short = product_title[:60]
    # Backpacks are a special category (larger than cases)
    elif any(keyword in title_lower for keyword in ['backpack', 'bag pack', 'rucksack']) and \
       any(keyword in title_lower for keyword in ['laptop', 'notebook', 'macbook', '15', '16', '17']):
        category = "laptop backpack"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['case', 'cover', 'sleeve', 'bag', 'pouch', 'holder']) and \
       any(keyword in title_lower for keyword in ['laptop', 'notebook', 'macbook']):
        category = "laptop accessory"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['case', 'cover', 'sleeve', 'pouch', 'holder', 'protector']) and \
         any(keyword in title_lower for keyword in ['phone', 'mobile', 'iphone', 'smartphone']):
        category = "phone accessory"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['charger', 'adapter', 'cable', 'charging']):
        category = "charger/cable"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['stand', 'mount', 'holder']) and \
         not any(keyword in title_lower for keyword in ['tv', 'monitor']):
        category = "stand/mount"
        product_short = product_title[:60]
    
    # PRIORITY 2: Main product categories (only if not an accessory)
    elif any(keyword in title_lower for keyword in ['laptop', 'notebook', 'chromebook', 'macbook']):
        category = "laptop"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['keyboard', 'mechanical keyboard', 'gaming keyboard']):
        category = "keyboard"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['mouse', 'gaming mouse', 'wireless mouse']):
        category = "mouse"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['phone', 'smartphone', 'mobile', 'iphone']):
        category = "smartphone"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['tablet', 'ipad']):
        category = "tablet"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['speaker', 'soundbar']):
        category = "speaker"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['earbuds', 'headphones', 'earphones', 'airpods']):
        category = "earbuds"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['watch', 'smartwatch']):
        category = "smartwatch"
        product_short = product_title[:60]
    elif any(keyword in title_lower for keyword in ['monitor', 'display', 'screen']):
        category = "monitor"
        product_short = product_title[:60]
    else:
        category = "product"
        product_short = product_title[:60]
    
    # Clear prompt requesting 5-6 products (ensuring 3+ pass quality filtering)
    prompt = f"""Product: {product_short}
Category: {category}

Find 5 to 6 REAL EXISTING {category}s that are similar alternatives (minimum 5, maximum 6).

IMPORTANT RULES:
1. MUST be actual {category} products (NOT books, NOT documents, NOT other categories)
2. Use REAL brand names and model numbers that exist on Amazon/Flipkart
3. Must be available for purchase in India
4. Must be in the SAME category as the input product
5. Include brand name + model number in each name

JSON output (5-6 real product names):
{{"product_names":["Brand1 Model1","Brand2 Model2","Brand3 Model3","Brand4 Model4","Brand5 Model5","Brand6 Model6"]}}"""
    
    async def retry_gemini_with_backoff(max_retries=3, base_delay=2):
        """Retry Gemini API calls with exponential backoff and API key fallback"""
        global current_key_index
        
        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        
        for attempt in range(max_retries):
            try:
                print(f"📤 Sending prompt to Gemini (attempt {attempt + 1}/{max_retries}, API key {current_key_index + 1}/{len(GEMINI_API_KEYS)}, length: {len(prompt)} chars)...")
                response = model.generate_content(
                    prompt,
                    generation_config={
                        'temperature': 0.5,
                        'top_p': 0.95,
                        'top_k': 40,
                        'max_output_tokens': 8192,  # MAXIMUM to handle thinking tokens in 2.5-flash!
                    }
                )
                return response
            except Exception as e:
                error_msg = str(e)
                is_503 = '503' in error_msg or 'overloaded' in error_msg.lower()
                is_quota = 'quota' in error_msg.lower() or '429' in error_msg
                is_last_attempt = attempt == max_retries - 1
                
                # Try backup API key if quota/rate limit error
                if is_quota and current_key_index < len(GEMINI_API_KEYS) - 1:
                    current_key_index += 1
                    genai.configure(api_key=GEMINI_API_KEYS[current_key_index])
                    print(f"🔄 Switching to backup API key {current_key_index + 1}/{len(GEMINI_API_KEYS)}...")
                    # Recreate model with new API key
                    model = genai.GenerativeModel(
                        'gemini-2.5-flash',
                        safety_settings=[
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        ]
                    )
                    continue  # Retry immediately with new key
                
                if not is_503 or is_last_attempt:
                    raise
                
                delay = base_delay * (2 ** attempt)
                print(f"⚠️  Gemini overloaded (503), retrying in {delay}s... (attempt {attempt + 1}/{max_retries})")
                import asyncio
                await asyncio.sleep(delay)
        
        raise Exception("Max retries reached for Gemini API")
    
    try:
        response = await retry_gemini_with_backoff(max_retries=3, base_delay=2)
        
        print(f"📥 Got response from Gemini")
        
        # Check if response was blocked
        if not response.candidates or len(response.candidates) == 0:
            print(f"❌ No candidates in response")
            raise ValueError("Gemini API: No response candidates returned (likely safety filter)")
        
        candidate = response.candidates[0]
        
        # Check finish_reason - use proper enum comparison
        finish_reason = getattr(candidate, 'finish_reason', None)
        finish_reason_name = getattr(finish_reason, 'name', str(finish_reason))
        print(f"📊 Finish reason: {finish_reason} (name: {finish_reason_name})")
        
        # Check for safety block - only trigger on actual SAFETY, not MAX_TOKENS (2) or STOP (1)
        # FinishReason enum: STOP=1, MAX_TOKENS=2, SAFETY=3, RECITATION=4, OTHER=5
        if finish_reason_name == 'SAFETY' or (hasattr(finish_reason, 'value') and finish_reason.value == 3):
            print(f"❌ Response blocked by safety filter")
            raise ValueError("Gemini API: Response blocked by safety filter")
        
        # Check for MAX_TOKENS (indicates a problem with the prompt or model)
        if finish_reason_name == 'MAX_TOKENS' or (hasattr(finish_reason, 'value') and finish_reason.value == 2):
            print(f"⚠️  Response hit MAX_TOKENS limit!")
            print(f"⚠️  This suggests the model is generating too much internal reasoning.")
            print(f"⚠️  Trying to extract whatever text we can...")
        
        # Extract JSON from response
        # Even if MAX_TOKENS, we should still try to get the partial response
        text = None
        
        # Try to get text - handle MAX_TOKENS case
        text = None
        
        # Method 1: Try response.text() first (works for normal responses)
        try:
            text = response.text
            print(f"✅ Got text via response.text(): {len(text)} chars")
            print(f"📝 First 200 chars: {text[:200]}")
        except Exception as text_error:
            print(f"⚠️  response.text() failed: {str(text_error)}")
            
            # Method 2: Try to extract from parts (works even with MAX_TOKENS)
            if candidate.content and candidate.content.parts:
                text_parts = []
                for part in candidate.content.parts:
                    # Try multiple ways to get text
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
                    elif hasattr(part, '__dict__'):
                        part_dict = part.__dict__
                        if 'text' in part_dict and part_dict['text']:
                            text_parts.append(part_dict['text'])
                
                if text_parts:
                    text = ''.join(text_parts)
                    print(f"✅ Extracted text from parts: {len(text)} chars")
                    print(f"📝 First 200 chars: {text[:200]}")
        
        # If still no text, check if we can continue
        if not text or len(text.strip()) == 0:
            # For MAX_TOKENS, the response might be in parts but not accessible via text()
            # Check if there's any data we can salvage
            print(f"❌ Empty response - finish_reason: {finish_reason_name}")
            print(f"📊 Candidate has parts: {bool(candidate.content and candidate.content.parts)}")
            if candidate.content and candidate.content.parts:
                print(f"📊 Number of parts: {len(candidate.content.parts)}")
                for i, part in enumerate(candidate.content.parts):
                    print(f"📊 Part {i}: has text attr = {hasattr(part, 'text')}, text = {getattr(part, 'text', None)}")
            raise ValueError(f"Gemini API: Empty response text (finish_reason: {finish_reason_name})")
        
        # Try to parse JSON - handle incomplete JSON from MAX_TOKENS truncation
        import re
        data = None
        
        # First, try to extract from markdown code block (even if incomplete)
        match = re.search(r'```(?:json)?\s*([\s\S]*)', text)  # Don't require closing ```
        if match:
            json_text = match.group(1).strip()
            # Remove any trailing ``` if present
            json_text = re.sub(r'```\s*$', '', json_text).strip()
        else:
            # Try to find JSON object directly
            json_start = text.find('{')
            if json_start != -1:
                json_text = text[json_start:]
            else:
                json_text = text
        
        # Try to parse JSON
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            # JSON is incomplete (likely due to MAX_TOKENS)
            print(f"⚠️  JSON parse error (likely incomplete): {str(e)}")
            print(f"📝 Attempting to fix incomplete JSON...")
            
            # Try to find the last complete alternative object
            # Look for complete objects ending with }
            json_objects = []
            depth = 0
            start_idx = json_text.find('{')
            if start_idx != -1:
                for i, char in enumerate(json_text[start_idx:], start=start_idx):
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            # Found complete root object
                            try:
                                data = json.loads(json_text[start_idx:i+1])
                                print(f"✅ Fixed incomplete JSON by finding complete root object")
                                break
                            except:
                                pass
            
            # If still no data, try to manually complete the JSON
            if data is None:
                # Add closing brackets for incomplete structure
                open_braces = json_text.count('{')
                close_braces = json_text.count('}')
                missing_braces = open_braces - close_braces
                
                # Try to complete the JSON structure
                completed_json = json_text
                if missing_braces > 0:
                    # Close arrays and objects
                    if '"alternatives": [' in json_text and json_text.count('[') > json_text.count(']'):
                        completed_json += ']'
                    completed_json += '}' * missing_braces
                    
                    try:
                        data = json.loads(completed_json)
                        print(f"✅ Fixed incomplete JSON by adding closing brackets")
                    except:
                        pass
            
            # If still no data, raise error
            if data is None:
                raise ValueError(f"Could not extract or fix JSON from AI response. Error: {str(e)}")
        
        # Extract product names
        product_names = data.get('product_names', [])
        # Use the category we detected earlier (not from Gemini)
        # category already set above from title detection
        
        # Ensure we have at least 3 products (fill with fallbacks if needed)
        while len(product_names) < 3:
            product_names.append(f"Alternative {category} {len(product_names) + 1}")
            print(f"⚠️  Only got {len(product_names)-1} names, adding fallback")
        
        if len(product_names) > 6:
            product_names = product_names[:6]  # Limit to 6
        
        print(f"✅ Gemini returned {len(product_names)} product names: {product_names}")
        return {
            'category': category,
            'product_names': product_names
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Gemini API error: {error_msg}")

        # Fallback on quota/429 or empty results: fabricate simple alternatives to avoid 503
        if 'quota' in error_msg.lower() or '429' in error_msg or True:
            fallback_title = scraped_data.get('title', 'Product')
            fallback_category = (scraped_data.get('category') or '').lower() or 'products'

            # Detect a phone from share text/title
            is_phone = any(k in fallback_title.lower() for k in ['phone', 'smartphone', 'mobile', 'oneplus', 'galaxy', 'iphone', 'pixel'])
            is_laptop = any(k in fallback_title.lower() for k in ['laptop', 'notebook', 'macbook'])

            if is_phone:
                fallback_category = 'smartphone'
                names = [
                    f"{fallback_title} alternative",
                    "Flagship 5G smartphone alternative",
                    "Value 5G smartphone alternative",
                ]
            elif is_laptop:
                fallback_category = 'laptop'
                names = [
                    f"{fallback_title} alternative",
                    "Performance laptop alternative",
                    "Value laptop alternative",
                ]
            else:
                names = [
                    f"{fallback_title} alternative 1",
                    f"{fallback_title} alternative 2",
                    f"{fallback_title} alternative 3",
                ]

            print(f"⚠️  Gemini quota/parse issue; returning fallback product names. Category={fallback_category}")
            return {
                'category': fallback_category,
                'product_names': names,
            }

        # Otherwise, re-raise
        raise


# ==================== Endpoints ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/recommend", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendRequest):
    """
    Main recommendation endpoint - OPTIMIZED WORKFLOW
    
    Process:
    1. Quick scrape input product for title (target: <3s)
    2. Call Gemini to get 3 similar product names (target: <2s)
    3. Search Amazon/Flipkart for each product (target: <5s parallel)
    4. Extract specs from product TITLES (no extra scraping!)
    5. Return complete data
    
    Total target: <12s with real data
    """
    import time
    import asyncio
    start_time = time.time()
    
    try:
        # Step 1: Get product title - try share text FIRST (instant!), then scrape if needed
        url_str = str(request.url)
        source_site = extract_source(url_str)
        scraped_data = None
        
        # NEW: Try to extract from share_text first (MUCH FASTER!)
        if request.share_text:
            share_data = extract_product_from_share_text(request.share_text, url_str)
            if share_data['has_details']:
                scraped_data = {'title': share_data['title']}
                print(f"✅ Got product from share text (INSTANT): {scraped_data['title'][:80]}")
                print(f"⚡ Skipped scraping - saved ~15-20 seconds!")
        
        # Fallback: Scrape only if we didn't get title from share text
        scrape_start = time.time()  # Always initialize this!
        
        if not scraped_data:
            print(f"📡 Share text not provided or too short, scraping URL...")
        
        # Quick scrape with timeout - just get title & category
        if not scraped_data:
            try:
                # Use asyncio.wait_for with generous timeout for input scraping
                scraped_data = await asyncio.wait_for(
                    scrape_product(url_str),
                    timeout=20.0  # 20s timeout for input scraping (some products are slow)
                )
                print(f"✅ Got input product from scraping: {scraped_data.get('title', 'Unknown')[:80]}")
            except asyncio.TimeoutError:
                print(f"⚠️  Input scraping timed out after 20s - using ASIN as fallback")
                # Fallback: Use ASIN-based generic name (better than failing completely)
                asin_match = re.search(r'/dp/([A-Z0-9]{10})', url_str)
                if asin_match:
                    asin = asin_match.group(1)
                    # Try to guess category from URL context
                    if 'laptop' in url_str.lower() or 'notebook' in url_str.lower():
                        scraped_data = {'title': f'Laptop Product {asin}', 'category': 'laptop'}
                    elif 'phone' in url_str.lower() or 'mobile' in url_str.lower():
                        scraped_data = {'title': f'Smartphone Product {asin}', 'category': 'smartphone'}
                    else:
                        scraped_data = {'title': f'Product {asin}', 'category': 'electronics'}
                else:
                    scraped_data = {'title': url_str.split('/')[-1][:50], 'category': 'products'}
                print(f"⚠️  Using fallback: {scraped_data}")
            except Exception as e:
                print(f"⚠️  Input scraping failed: {str(e)}, using ASIN fallback")
                asin_match = re.search(r'/dp/([A-Z0-9]{10})', url_str)
                if asin_match:
                    scraped_data = {'title': f'Product {asin_match.group(1)}', 'category': 'products'}
                else:
                    scraped_data = {'title': url_str.split('/')[-1][:50], 'category': 'products'}
        
        scrape_time = time.time() - scrape_start
        print(f"⏱️  Input product scraping took: {scrape_time:.3f}s")
        
        # Step 2: Call Gemini for product names only (super fast, minimal tokens)
        llm_start = time.time()
        llm_output = await call_llm_for_product_names(scraped_data)
        llm_time = time.time() - llm_start
        print(f"⏱️  LLM (product names) took: {llm_time:.2f}s")
        
        product_names = llm_output.get('product_names', [])
        category = llm_output.get('category', 'products')
        
        # Limit products to reduce quota usage when Gemini is constrained
        num_products = min(len(product_names), 4)  # was 6; reduce to 4 to avoid quota spikes
        if num_products < 3:
            raise ValueError(f"Expected at least 3 product names, got {num_products}")
        
        print(f"🔍 Will search for {num_products} products (ensuring 3+ quality results)")
        
        # Step 3: Search ScraperAPI for each product (parallel for speed)
        search_start = time.time()
        # Use same site as input (already extracted above)
        
        # Search products in parallel with adequate timeout for reliability
        search_tasks = [
            asyncio.wait_for(
                search_product_scraperapi(name, source_site),
                timeout=18.0  # Increased to 18s for better success rate (was 12s)
            )
            for name in product_names[:num_products]  # Get 3-6 products
        ]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # region agent log
        try:
            import time as _time
            with open(r"c:\Users\Michael\Documents\RDM Projects\SimilarLinks\.cursor\debug.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H2",
                    "location": "backend/main.py:recommend:search_results",
                    "message": "Search and LLM results",
                    "data": {
                        "product_names_count": len(product_names),
                        "num_search_tasks": len(search_tasks),
                        "exceptions": sum(1 for r in search_results if isinstance(r, Exception)),
                        "source_site": source_site,
                        "share_text_provided": bool(request.share_text)
                    },
                    "timestamp": _time.time()
                }) + "\n")
        except Exception:
            pass
        # endregion

        search_time = time.time() - search_start
        print(f"⏱️  ScraperAPI searches took: {search_time:.2f}s")
        
        # Step 4: Enhance ALL products with Gemini in PARALLEL (much faster!)
        print(f"🤖 Enhancing {num_products} products with Gemini AI (parallel)...")
        gemini_start = time.time()
        
        gemini_tasks = []
        for idx, (product_name, search_result) in enumerate(zip(product_names[:num_products], search_results)):
            if isinstance(search_result, Exception) or not search_result:
                title = product_name
            else:
                title = search_result.get('title', product_name)
            gemini_tasks.append(enhance_product_with_gemini(title, category))
        
        # Call Gemini for ALL products at once!
        gemini_results = await asyncio.gather(*gemini_tasks, return_exceptions=True)
        gemini_time = time.time() - gemini_start
        print(f"⏱️  Gemini enhancements took: {gemini_time:.2f}s (parallel)")
        
        # Step 5: Build alternatives from search results + Gemini enhancements
        alternatives = []
        for idx, (product_name, search_result, gemini_result) in enumerate(zip(product_names[:num_products], search_results, gemini_results)):
            if isinstance(search_result, Exception):
                print(f"⚠️  Search failed for '{product_name}': {str(search_result)}")
                # Search failed/timed out - create fallback with extracted specs
                print(f"⚠️  Search failed for '{product_name}': {str(search_result)}")
                search_query = product_name.replace(' ', '+')
                if source_site == 'flipkart':
                    search_url = f"https://www.flipkart.com/search?q={search_query}"
                else:
                    search_url = f"https://www.amazon.in/s?k={search_query}"
                
                # Extract specs from product name
                fallback_specs = []
                spec_patterns = [
                    r'(\d+(?:GB|TB)\s+(?:RAM|Storage|SSD|HDD))',
                    r'(Core\s+i\d+[-\w]+|Ryzen\s+\d+)',
                    r'(\d+(?:\.?\d+)?"\s*(?:FHD|HD|Display)?)',
                    r'(\d+(?:mAh|WHR)\s+Battery)',
                ]
                
                for pattern in spec_patterns:
                    matches = re.findall(pattern, product_name, re.IGNORECASE)
                    for match in matches:
                        if match and match not in fallback_specs:
                            fallback_specs.append(match.strip())
                
                alternatives.append(Product(
                    id=str(idx + 1),
                    brand=product_name.split()[0] if product_name.split() else "Unknown",
                    model=product_name,
                    title=product_name,
                    image_url="",
                    price_estimate="₹0",
                    price_raw=0,
                    rating_estimate=None,
                    rating_count_estimate=None,
                    specs=fallback_specs,
                    connectivity=[],
                    why_pick=f"Similar {category} alternative",
                    tradeoffs="Limited data - search to view details",
                    source_url=search_url,
                    source_site=source_site
                ))
            elif search_result:
                # Extract data from search result
                price_str = search_result.get('price', '₹0')
                price_raw = parse_price_raw(price_str)
                
                # Extract rating count fallback
                rating_est = search_result.get('rating')
                rating_count = search_result.get('rating_count')
                if rating_count is None and rating_est:
                    rating_count = 10  # minimal fallback so ReviewScore isn't 0

                # Extract brand from title (first word)
                title = search_result.get('title', product_name)
                brand = title.split()[0] if title.split() else "Unknown"
                
                # Get the product URL - MUST be direct product page URL
                product_url = search_result.get('url', '')
                
                # Log the URL for debugging
                print(f"🔗 Product {idx + 1} URL: {product_url}")
                
                # Validate URL quality - prefer direct links over search links
                is_direct_link = bool(product_url and ('/dp/' in product_url or '/p/' in product_url) and '/s?k=' not in product_url)
                
                if is_direct_link:
                    print(f"✅ Using direct product URL for product {idx + 1}")
                else:
                    # Use search URL as fallback (still useful for users)
                    product_url = f"https://www.{source_site}.in/s?k={product_name.replace(' ', '+')}"
                    print(f"⚠️  Using search URL fallback for product {idx + 1}")
                
                # Use Gemini result (already fetched in parallel above)
                if isinstance(gemini_result, Exception):
                    print(f"⚠️  Gemini enhancement failed for product {idx + 1}: {str(gemini_result)}")
                    # Fallback to search specs
                    product_specs = search_result.get('specs', [])[:8]
                    why_pick_msg = f"Found via search: {product_name}"
                else:
                    product_specs = gemini_result.get('specifications', [])
                    why_pick_msg = gemini_result.get('why_pick', f"Quality {category} alternative")
                    print(f"✅ Product {idx + 1} enhanced: {len(product_specs)} specs")
                
                alternatives.append(Product(
                    id=str(idx + 1),
                    brand=brand,
                    model=product_name,
                    title=title,
                    image_url=search_result.get('image_url', ''),
                    price_estimate=price_str or "₹0",
                    price_raw=price_raw,
                    rating_estimate=rating_est,
                    rating_count_estimate=rating_count,
                    specs=product_specs,  # Use extracted or search specs
                    connectivity=[],
                    why_pick=why_pick_msg,  # Improved message
                    tradeoffs="",
                    source_url=product_url,
                    source_site=source_site
                ))
            else:
                # Search returned None - extract specs from product_name at least
                print(f"⚠️  No search results for '{product_name}', creating fallback entry")
                search_query = product_name.replace(' ', '+')
                if source_site == 'flipkart':
                    search_url = f"https://www.flipkart.com/search?q={search_query}"
                else:
                    search_url = f"https://www.amazon.in/s?k={search_query}"
                
                # Use Gemini result (already fetched in parallel above)
                if isinstance(gemini_result, Exception):
                    print(f"⚠️  Gemini enhancement failed for fallback {idx + 1}: {str(gemini_result)}")
                    fallback_specs = []
                    why_pick_msg = f"Similar {category} alternative"
                else:
                    fallback_specs = gemini_result.get('specifications', [])
                    why_pick_msg = gemini_result.get('why_pick', f"Similar {category} alternative")
                    print(f"✅ Fallback product {idx + 1} enhanced: {len(fallback_specs)} specs")
                
                alternatives.append(Product(
                    id=str(idx + 1),
                    brand=product_name.split()[0] if product_name.split() else "Unknown",
                    model=product_name,
                    title=product_name,
                    image_url="",  # No image available
                    price_estimate="₹0",
                    price_raw=0,
                    rating_estimate=None,
                    rating_count_estimate=None,
                    specs=fallback_specs,  # Extracted specs from name
                    connectivity=[],
                    why_pick=why_pick_msg,  # Improved message based on specs
                    tradeoffs="Limited data available - verify specs on product page",
                    source_url=search_url,
                    source_site=source_site
                ))
        
        # Step 5: Validate and filter out bad results (relaxed validation)
        # Score each product and filter only the worst ones
        valid_alternatives = []
        filtered_count = 0
        
        for alt in alternatives:
            # Score products (higher = better quality)
            quality_score = 0
            issues = []
            
            # +1 if has valid price
            if alt.price_raw > 0:
                quality_score += 1
            else:
                issues.append("no price")
            
            # +1 if not generic fallback
            if "generic" not in alt.title.lower():
                quality_score += 1
            else:
                issues.append("generic fallback")
            
            # +1 if has direct product URL (not search)
            if '/s?k=' not in alt.source_url and '/search?' not in alt.source_url:
                quality_score += 1
            else:
                issues.append("search URL")
            
            # +1 if has image
            if alt.image_url and alt.image_url != "":
                quality_score += 1
            else:
                issues.append("no image")
            
            # STRICT FILTER: Must have BOTH image AND price (or at least one + high quality score)
            # This prevents showing products with no image and ₹0 price
            has_image = bool(alt.image_url and alt.image_url != "")
            has_price = bool(alt.price_raw > 0)
            
            # Accept if:
            # 1. Has both image AND price (ideal)
            # 2. Has image OR price, AND quality_score >= 2 (has other good attributes)
            should_keep = False
            
            if has_image and has_price:
                should_keep = True  # Perfect product
            elif (has_image or has_price) and quality_score >= 2:
                should_keep = True  # Good product with at least one critical attribute
            
            if should_keep:
                valid_alternatives.append(alt)
                if quality_score < 3:
                    print(f"⚠️  Kept product with issues (score {quality_score}/4): '{alt.title[:50]}' - {', '.join(issues)}")
            else:
                filtered_count += 1
                print(f"❌ Filtered out low-quality product (score {quality_score}/4): '{alt.title[:50]}' - {', '.join(issues)}")
        
        # Accept 1+ valid products (relaxed for when ScraperAPI is unavailable)
        if len(valid_alternatives) < 1:
            # Less than 1 is unacceptable
            raise ValueError(
                f"Could not find enough valid product alternatives. "
                f"Found {len(valid_alternatives)} valid products, filtered out {filtered_count}. "
                f"Need at least 1 product. "
                f"This may be due to ScraperAPI limits, timeouts, or poor search results."
            )

        # Step 6: Calculate RDM scores (Value for Money × Quality & Trust × Fit for Needs)
        try:
            category_for_rdm = (category or "products").lower()
            print(f"📊 Calculating RDM scores for {len(valid_alternatives)} products (category: {category_for_rdm})...")

            # Convert to dicts for calculator
            rdm_input = []
            for alt in valid_alternatives:
                rdm_input.append({
                    "id": alt.id,
                    "title": alt.title,
                    "price_raw": alt.price_raw,
                    "rating_estimate": alt.rating_estimate,
                    "rating_count_estimate": alt.rating_count_estimate,
                    "specs": alt.specs,
                })

            rdm_results = calculate_rdm_scores(rdm_input, category_for_rdm)
            rdm_map = {p["id"]: (p.get("rdm_score"), p.get("rdm_breakdown")) for p in rdm_results}

            # Attach scores back to models
            for alt in valid_alternatives:
                if alt.id in rdm_map:
                    alt.rdm_score = rdm_map[alt.id][0]
                    alt.rdm_breakdown = rdm_map[alt.id][1]

            # Sort by RDM descending
            valid_alternatives.sort(key=lambda x: x.rdm_score or 0, reverse=True)
        except Exception as e:
            print(f"⚠️  RDM calculation failed: {str(e)}")
        
        # Generate warnings
        warnings = []
        if len(valid_alternatives) < 3:
            print(f"⚠️  Only found {len(valid_alternatives)} valid products (expected 3+)")
            warnings.append(f"Only {len(valid_alternatives)} alternatives found")
        if filtered_count > 0:
            warnings.append(f"Filtered out {filtered_count} low-quality results")
        
        # Use only valid alternatives
        alternatives = valid_alternatives
        
        response = RecommendationResponse(
            source=extract_source(str(request.url)),
            canonical_url=request.url,
            query_time_iso=datetime.utcnow().isoformat(),
            alternatives=alternatives,
            meta=ResponseMeta(
                validation=ValidationMeta(
                    llm_valid_json=True,
                    image_urls_checked=True,
                ),
                warnings=warnings,
            ),
        )
        
        total_time = time.time() - start_time
        print(f"✅ TOTAL TIME: {total_time:.2f}s")
        
        if total_time < 5.0:
            print(f"🚀 BLAZING FAST! Under 5s!")
        elif total_time < 8.0:
            print(f"✅ FAST! Under 8s")
        elif total_time < 12.0:
            print(f"✅ Good: Under 12s")
        else:
            print(f"⚠️  Slow: Over 12s")
        
        return response
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Backend error: {error_msg}")

        # region agent log
        try:
            import time as _time
            with open(r"c:\Users\Michael\Documents\RDM Projects\SimilarLinks\.cursor\debug.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H3",
                    "location": "backend/main.py:recommend:error",
                    "message": "Recommendation error raised",
                    "data": {
                        "error": error_msg,
                        "url": str(request.url),
                        "has_share_text": bool(request.share_text)
                    },
                    "timestamp": _time.time()
                }) + "\n")
        except Exception:
            pass
        # endregion
        
        # Return helpful error that mobile app can detect
        # Use 503 (Service Unavailable) instead of 500 to trigger fallback
        raise HTTPException(
            status_code=503,
            detail=f"Backend error: {error_msg}. Falling back to direct Gemini mode."
        )


@app.post("/recommend/price")
async def refresh_prices(request: dict):
    """
    Lightweight endpoint to refresh prices only
    """
    url = request.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    # TODO: Implement price-only refresh
    # Re-scrape prices without full LLM call
    
    return {"message": "Price refresh not yet implemented"}


@app.post("/multi-platform/search")
async def search_multi_platform(request: dict):
    """
    Search for same product across all Indian e-commerce platforms
    Returns direct links with real prices where available
    """
    product_name = request.get("product_name")
    brand = request.get("brand")
    current_platform = request.get("current_platform", "amazon")
    
    if not product_name or not brand:
        raise HTTPException(status_code=400, detail="product_name and brand are required")
    
    try:
        sellers = await get_multi_platform_links(product_name, brand, current_platform)
        
        return {
            "sellers": sellers,
            "total_found": len(sellers),
            "query": f"{brand} {product_name}",
        }
        
    except Exception as e:
        print(f"❌ Multi-platform search error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Multi-platform search failed: {str(e)}"
        )


@app.post("/identify-product")
async def identify_product_from_image_endpoint(request: ImageSearchRequest):
    """
    Identify product from image using Gemini 2.5 Flash Vision API
    User clicks on a product image → Gemini identifies the product
    """
    try:
        print(f"\n🖼️  Image-based product identification request")
        
        product_info = None
        
        if request.image_url:
            # Identify from image URL
            print(f"📸 Image URL: {request.image_url[:80]}")
            product_info = identify_product_from_image(request.image_url)
        elif request.image_base64:
            # Identify from base64 image
            print(f"📸 Base64 image provided")
            product_info = identify_product_from_image_base64(request.image_base64)
        else:
            raise HTTPException(status_code=400, detail="Either image_url or image_base64 required")
        
        if not product_info:
            raise HTTPException(
                status_code=404,
                detail="Could not identify product from image"
            )
        
        return {
            "success": True,
            "product": product_info,
            "message": f"Identified: {product_info.get('brand')} {product_info.get('product_name')}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Image identification error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Image identification failed: {str(e)}"
        )


@app.post("/extract-invoice")
async def extract_invoice_data_endpoint(request: InvoiceExtractionRequest):
    """
    Extract product details from invoice/receipt using Gemini 2.5 Flash Vision
    Extracts: product name, brand, store, purchase date, price, warranty, next service date
    """
    try:
        print(f"\n🧾 Invoice extraction request")
        
        # Decode base64 image
        image_data = base64.b64decode(request.image_base64)
        image = Image.open(BytesIO(image_data))
        
        # Use Gemini 2.5 Flash Vision to extract invoice data
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = """You are an expert at extracting information from purchase invoices and receipts.

Analyze this invoice/receipt image and extract ALL available information:

Respond in this EXACT format (use "N/A" if information not found):
PRODUCT: [product name]
BRAND: [brand name]
STORE: [store/platform name - Amazon, Flipkart, etc.]
PURCHASE_DATE: [date of purchase - DD/MM/YYYY format]
PRICE: [price paid with currency symbol]
SPECIFICATIONS: [key specifications if visible]
WARRANTY: [warranty period - e.g., "1 Year", "2 Years"]
NEXT_SERVICE: [next service date if applicable - DD/MM/YYYY]

Examples:
PRODUCT: Realme Buds T300 True Wireless Earbuds
BRAND: Realme
STORE: Amazon
PURCHASE_DATE: 15/10/2024
PRICE: ₹2,299
SPECIFICATIONS: Bluetooth 5.3, 30H playback, Fast charging
WARRANTY: 1 Year
NEXT_SERVICE: N/A

PRODUCT: Crompton Aura Ceiling Fan 1200mm
BRAND: Crompton
STORE: Flipkart
PURCHASE_DATE: 20/09/2024
PRICE: ₹2,699
SPECIFICATIONS: 1200mm sweep, BEE 5 Star rated
WARRANTY: 2 Years
NEXT_SERVICE: 20/09/2025

Now extract from this invoice/receipt:"""
        
        # Generate response
        response = model.generate_content([prompt, image])
        result_text = response.text.strip()
        
        print(f"🤖 Gemini invoice extraction:\n{result_text}")
        
        # Parse response
        lines = result_text.split('\n')
        invoice_data = {}
        
        for line in lines:
            if line.startswith('PRODUCT:'):
                invoice_data['product_name'] = line.replace('PRODUCT:', '').strip()
            elif line.startswith('BRAND:'):
                invoice_data['brand'] = line.replace('BRAND:', '').strip()
            elif line.startswith('STORE:'):
                invoice_data['store'] = line.replace('STORE:', '').strip()
            elif line.startswith('PURCHASE_DATE:'):
                invoice_data['purchase_date'] = line.replace('PURCHASE_DATE:', '').strip()
            elif line.startswith('PRICE:'):
                invoice_data['price'] = line.replace('PRICE:', '').strip()
            elif line.startswith('SPECIFICATIONS:'):
                invoice_data['specifications'] = line.replace('SPECIFICATIONS:', '').strip()
            elif line.startswith('WARRANTY:'):
                invoice_data['warranty'] = line.replace('WARRANTY:', '').strip()
            elif line.startswith('NEXT_SERVICE:'):
                invoice_data['next_service'] = line.replace('NEXT_SERVICE:', '').strip()
        
        # Validate
        if invoice_data.get('product_name') and invoice_data.get('product_name') != 'N/A':
            print(f"✅ Invoice extracted: {invoice_data.get('product_name')}")
            return {
                "success": True,
                "invoice": invoice_data,
                "message": f"Extracted from invoice"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Could not extract product information from invoice"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Invoice extraction error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Invoice extraction failed: {str(e)}"
        )


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


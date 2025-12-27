"""
FastAPI Backend for Decision Recommendation App
Handles product scraping and LLM-powered recommendations
"""

import sys
import os

# Fix Windows console encoding for emojis (MUST be before any print statements)
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Load environment variables from .env file
from dotenv import load_dotenv

# Force reload .env file to ensure we get the latest keys (override system env vars)
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"✅ Loaded .env from: {env_path}")
else:
    load_dotenv(override=True)
    print("⚠️  No .env file found, using system environment variables")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Literal
from datetime import datetime
import json
import re
import base64
import io
from io import BytesIO
from PIL import Image  # type: ignore  # PIL is installed as Pillow
import google.generativeai as genai
from scraper_api import scrape_product_scraperapi, search_product_scraperapi, SCRAPERAPI_KEY
from multi_platform_search import get_multi_platform_links
from gemini_vision import identify_product_from_image, identify_product_from_image_base64

app = FastAPI(title="Decision Recommendation API", version="1.0.0")

# Print ScraperAPI status on startup
if SCRAPERAPI_KEY:
    masked_key = SCRAPERAPI_KEY[:4] + "..." + SCRAPERAPI_KEY[-4:] if len(SCRAPERAPI_KEY) > 8 else "***"
    print(f"✅ ScraperAPI: Key loaded ({masked_key})")
else:
    print("⚠️  ScraperAPI: No key found - using fallback mode")
    print("   Create a .env file in backend/ with: SCRAPERAPI_KEY=your_key_here")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware - MUST be after CORS middleware
@app.middleware("http")
async def log_requests(request, call_next):
    import time
    start_time = time.time()
    client_ip = request.client.host if request.client else 'Unknown'
    print(f"\n{'='*60}")
    print(f"🌐 INCOMING REQUEST: {request.method} {request.url.path}")
    print(f"   Client IP: {client_ip}")
    print(f"   Full URL: {request.url}")
    print(f"   Headers: {dict(request.headers)}")
    print(f"{'='*60}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"✅ REQUEST COMPLETED: {request.method} {request.url.path} - {process_time:.2f}s - Status: {response.status_code}")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        print(f"❌ REQUEST FAILED: {request.method} {request.url.path} - {process_time:.2f}s")
        print(f"   Error: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        raise

# Gemini API Keys - MUST be set via environment variables for security
GEMINI_API_KEYS = []
current_key_index = 0

# Load API keys from environment variables
primary_key = os.getenv("GEMINI_API_KEY")
if primary_key:
    GEMINI_API_KEYS.append(primary_key)
    print(f"✅ Loaded primary Gemini API key: {primary_key[:10]}...{primary_key[-4:]}")

backup_key = os.getenv("GEMINI_API_KEY_BACKUP")
if backup_key:
    GEMINI_API_KEYS.append(backup_key)
    print(f"✅ Loaded backup Gemini API key 1: {backup_key[:10]}...{backup_key[-4:]}")

# Load additional backup keys (GEMINI_API_KEY_BACKUP2, etc.)
backup_key2 = os.getenv("GEMINI_API_KEY_BACKUP2")
if backup_key2:
    GEMINI_API_KEYS.append(backup_key2)
    print(f"✅ Loaded backup Gemini API key 2: {backup_key2[:10]}...{backup_key2[-4:]}")

if not GEMINI_API_KEYS:
    raise ValueError(
        "GEMINI_API_KEY environment variable is required. "
        "Set it using: export GEMINI_API_KEY='your-api-key'"
    )

print(f"📋 Total Gemini API keys loaded: {len(GEMINI_API_KEYS)}")
for idx, key in enumerate(GEMINI_API_KEYS, 1):
    print(f"   Key {idx}: {key[:10]}...{key[-4:]}")

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
    file_type: Optional[str] = "image"  # "image" or "pdf"
    warranty_image_base64: Optional[str] = None  # Optional warranty slip image to merge

class WarrantyExtractionRequest(BaseModel):
    image_base64: str
    file_type: Optional[str] = "image"  # "image" or "pdf"
    invoice_data: Optional[dict] = None  # Optional invoice data to use as fallback/merge


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
        error_msg = str(e)
        is_quota = 'quota' in error_msg.lower() or '429' in error_msg or 'rate limit' in error_msg.lower()
        
        if is_quota:
            print(f"⚠️  Gemini enhancement quota exceeded, using fallback specs")
        else:
            print(f"⚠️  Gemini enhancement failed: {error_msg[:100]}, using fallback")
        
        # Fallback: Extract specs from product title
        fallback_specs = []
        spec_patterns = [
            r'(\d+(?:GB|TB)\s+(?:RAM|Storage|SSD|HDD))',
            r'(Core\s+i\d+[-\w]+|Ryzen\s+\d+)',
            r'(\d+(?:\.?\d+)?"\s*(?:FHD|HD|Display)?)',
            r'(\d+(?:mAh|WHR)\s+Battery)',
            r'(\d+(?:\.?\d+)?\s*(?:inch|cm))',
        ]
        
        for pattern in spec_patterns:
            matches = re.findall(pattern, product_title, re.IGNORECASE)
            for match in matches:
                if match and match not in fallback_specs:
                    fallback_specs.append(match.strip())
        
        return {
            'specifications': fallback_specs[:5] if fallback_specs else [f"{category} product"],
            'why_pick': f'Quality {category} alternative to consider'
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
    
    print(f"🔍 Analyzing product title: '{product_title}'")
    print(f"   Lowercase: '{title_lower}'")
    
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
    # TABLETS FIRST - before speakers (to catch "Tab" and "Pad" in model names)
    # "Pad" is a direct tablet keyword (XIAOMI Pad, Samsung Pad, etc.)
    # "Tab" needs brand context (Idea Tab, Galaxy Tab, etc.)
    elif any(keyword in title_lower for keyword in ['tablet', 'ipad', 'pad']) or \
         (any(keyword in title_lower for keyword in ['tab']) and \
          any(brand in title_lower for brand in ['idea', 'galaxy', 'mi', 'lenovo', 'samsung', 'xiaomi', 'realme', 'kamvas', 'slate', 'smartchoice'])):
        # CRITICAL: Check if it's a tablet STAND/accessory first!
        # But exclude common tablet model names
        if any(keyword in title_lower for keyword in ['stand', 'holder', 'mount']) and \
           not any(brand in title_lower for brand in ['idea tab', 'galaxy tab', 'mi tab', 'lenovo tab', 'samsung tab', 'xiaomi tab', 'realme tab', 'kamvas', 'slate', 'smartchoice', 'pad', 'xiaomi pad', 'samsung pad', 'mi pad']):
            category = "stand/mount"
            product_short = product_title[:60]
        else:
            category = "tablet"
            product_short = product_title[:60]
            if 'pad' in title_lower:
                print(f"✅ Detected TABLET category - matched 'pad' keyword")
            elif 'tab' in title_lower:
                print(f"✅ Detected TABLET category - matched 'tab' with brand keywords")
            else:
                print(f"✅ Detected TABLET category - matched 'tablet' or 'ipad'")
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
    
    # Log detected category for debugging
    print(f"📋 Detected category: '{category}' for product: '{product_short}'")
    
    # Clear prompt requesting 5-6 products (ensuring 3+ pass quality filtering)
    # CRITICAL: Make it VERY explicit to avoid accessories/stand confusion
    if category == "tablet":
        category_examples = "Samsung Galaxy Tab, Lenovo Tab, Apple iPad, Realme Pad, Xiaomi Pad"
        category_exclusion = "DO NOT return tablet stands, tablet holders, tablet cases, or tablet accessories. ONLY return actual tablet devices."
    elif category == "laptop":
        category_examples = "HP Pavilion, Dell Inspiron, Lenovo IdeaPad, ASUS VivoBook, Acer Aspire"
        category_exclusion = "DO NOT return laptop bags, laptop stands, laptop cases, or laptop accessories. ONLY return actual laptop computers."
    elif category == "smartphone":
        category_examples = "Samsung Galaxy, iPhone, OnePlus, Xiaomi Redmi, Realme"
        category_exclusion = "DO NOT return phone cases, phone covers, phone stands, or phone accessories. ONLY return actual smartphones."
    elif category == "stand/mount":
        category_examples = "Lamicall Tablet Stand, UGREEN Phone Stand, Portronics Mobile Holder"
        category_exclusion = "Return stand/mount products ONLY."
    else:
        category_examples = f"Similar {category} products"
        category_exclusion = f"MUST be actual {category} products, NOT accessories or related items."
    
    prompt = f"""Product: {product_short}
Category: {category}

Find 5 to 6 REAL EXISTING {category}s that are similar alternatives to "{product_short}" (minimum 5, maximum 6).

CRITICAL RULES:
1. {category_exclusion}
2. The input product is: "{product_short}" - return products of the SAME TYPE
3. Examples of {category}s: {category_examples}
4. Use REAL brand names and model numbers that exist on Amazon/Flipkart
5. Must be available for purchase in India
6. Include brand name + model number in each name
7. If input is a TABLET, return TABLETS (not stands/cases/accessories)
8. If input is a LAPTOP, return LAPTOPS (not bags/stands/cases/accessories)
9. If input is a PHONE, return PHONES (not cases/covers/stands/accessories)

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
                print(f"📤 Sending prompt to Gemini (attempt {attempt + 1}/{max_retries}, API key {current_key_index + 1}/{len(GEMINI_API_KEYS)}, key: {GEMINI_API_KEYS[current_key_index][:10]}...{GEMINI_API_KEYS[current_key_index][-4:]}, length: {len(prompt)} chars)...")
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
        
        # If we get here, all retries failed - raise with original error info
        raise Exception(f"Max retries reached for Gemini API. Last error: {error_msg if 'error_msg' in locals() else 'Unknown'}")
    
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
        print(f"❌ Gemini API error: {str(e)}")
        raise


# ==================== Endpoints ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    print("🏥 Health check called")
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow().isoformat(),
        "scraperapi_configured": bool(SCRAPERAPI_KEY),
        "scraperapi_key": f"{SCRAPERAPI_KEY[:4]}...{SCRAPERAPI_KEY[-4:]}" if SCRAPERAPI_KEY else "None"
    }

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify backend is receiving requests"""
    print("🧪 Test endpoint called")
    return {
        "message": "Backend is working!",
        "scraperapi_key": f"{SCRAPERAPI_KEY[:4]}...{SCRAPERAPI_KEY[-4:]}" if SCRAPERAPI_KEY else "None",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/test-scraperapi")
async def test_scraperapi():
    """Test ScraperAPI endpoint - verify it's working"""
    import time
    test_url = "https://www.amazon.in/dp/B08N5WRWNW"  # Test product URL
    
    print(f"\n🧪 TESTING SCRAPERAPI")
    print(f"   Key: {SCRAPERAPI_KEY[:4] if SCRAPERAPI_KEY else 'None'}...{SCRAPERAPI_KEY[-4:] if SCRAPERAPI_KEY and len(SCRAPERAPI_KEY) > 8 else '***'}")
    print(f"   URL: {test_url}")
    
    try:
        start = time.time()
        result = await scrape_product_scraperapi(test_url)
        elapsed = time.time() - start
        
        return {
            "success": True,
            "elapsed_time": f"{elapsed:.2f}s",
            "title": result.get('title', 'N/A'),
            "price": result.get('price', 'N/A'),
            "has_image": bool(result.get('image_url')),
            "scraperapi_key": f"{SCRAPERAPI_KEY[:4]}...{SCRAPERAPI_KEY[-4:]}" if SCRAPERAPI_KEY else "None"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "scraperapi_key": f"{SCRAPERAPI_KEY[:4]}...{SCRAPERAPI_KEY[-4:]}" if SCRAPERAPI_KEY else "None"
        }


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
    
    # Log incoming request
    print(f"\n{'='*60}")
    print(f"📥 NEW REQUEST RECEIVED")
    print(f"   URL: {request.url}")
    print(f"   Share Text: {request.share_text[:100] if request.share_text else 'None'}...")
    print(f"   ScraperAPI Key: {SCRAPERAPI_KEY[:4] if SCRAPERAPI_KEY else 'None'}...{SCRAPERAPI_KEY[-4:] if SCRAPERAPI_KEY and len(SCRAPERAPI_KEY) > 8 else '***'}")
    print(f"{'='*60}\n")
    
    try:
        # Step 1: Get product title - try share text FIRST (instant!), then scrape if needed
        print(f"🔍 Step 1: Extracting product information...")
        url_str = str(request.url)
        source_site = extract_source(url_str)
        print(f"   Detected source: {source_site}")
        scraped_data = None
        
        # NEW: Try to extract from share_text first (MUCH FASTER!)
        if request.share_text:
            print(f"   Trying to extract from share text...")
            try:
                share_data = extract_product_from_share_text(request.share_text, url_str)
                if share_data['has_details']:
                    scraped_data = {'title': share_data['title']}
                    print(f"✅ Got product from share text (INSTANT): {scraped_data['title'][:80]}")
                    print(f"⚡ Skipped scraping - saved ~15-20 seconds!")
                else:
                    print(f"⚠️  Share text didn't contain product details")
            except Exception as e:
                print(f"⚠️  Error extracting from share text: {str(e)}")
        
        # Fallback: Scrape only if we didn't get title from share text
        scrape_start = time.time()  # Always initialize this!
        
        if not scraped_data:
            print(f"📡 Share text not provided or too short, scraping URL with ScraperAPI...")
            print(f"   ScraperAPI Key available: {bool(SCRAPERAPI_KEY)}")
        
        # Quick scrape with timeout - just get title & category
        if not scraped_data:
            try:
                print(f"   Calling scrape_product_scraperapi...")
                # Use asyncio.wait_for with generous timeout for input scraping
                scraped_data = await asyncio.wait_for(
                    scrape_product(url_str),
                    timeout=20.0  # 20s timeout for input scraping (some products are slow)
                )
                print(f"✅ Got input product from scraping: {scraped_data.get('title', 'Unknown')[:80]}")
                print(f"   Price: {scraped_data.get('price', 'N/A')}")
                print(f"   Has image: {bool(scraped_data.get('image_url'))}")
            except asyncio.TimeoutError:
                print(f"❌ Input scraping timed out after 20s - ScraperAPI may be slow/down")
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
                print(f"❌ Input scraping failed: {str(e)}")
                print(f"   Error type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                asin_match = re.search(r'/dp/([A-Z0-9]{10})', url_str)
                if asin_match:
                    scraped_data = {'title': f'Product {asin_match.group(1)}', 'category': 'products'}
                else:
                    scraped_data = {'title': url_str.split('/')[-1][:50], 'category': 'products'}
        
        scrape_time = time.time() - scrape_start
        print(f"⏱️  Input product scraping took: {scrape_time:.3f}s")
        
        # Step 2: Call Gemini for product names only (super fast, minimal tokens)
        print(f"\n🔍 Step 2: Calling Gemini for product names...")
        print(f"   Input data: title={scraped_data.get('title', 'N/A')[:50]}")
        llm_start = time.time()
        try:
            llm_output = await call_llm_for_product_names(scraped_data)
            llm_time = time.time() - llm_start
            print(f"✅ LLM (product names) took: {llm_time:.2f}s")
            
            product_names = llm_output.get('product_names', [])
            category = llm_output.get('category', 'products')
            print(f"   Gemini returned {len(product_names)} product names: {product_names[:3]}...")
        except Exception as e:
            llm_time = time.time() - llm_start
            error_msg = str(e)
            error_type = type(e).__name__
            print(f"❌ Gemini API call failed: {error_msg[:200]}")
            print(f"   Error type: {error_type}")
            print(f"   Full error: {error_msg}")
            
            # Check if it's a quota/rate limit error
            is_quota = 'quota' in error_msg.lower() or '429' in error_msg or 'rate limit' in error_msg.lower()
            print(f"   Is quota error: {is_quota}")
            
            if is_quota:
                print(f"⚠️  GEMINI QUOTA EXCEEDED - Using fallback product generation")
                print(f"   The free tier allows 20 requests per day. Please wait or upgrade your plan.")
                print(f"   Billing account API key should have higher limits - check Google Cloud Console")
                
                # Generate fallback product names based on category and title
                product_title = scraped_data.get('title', 'Product')
                title_lower = product_title.lower()
                
                # Detect category for fallback
                if any(kw in title_lower for kw in ['tablet', 'ipad', 'pad']) or \
                   (any(kw in title_lower for kw in ['tab']) and any(brand in title_lower for brand in ['idea', 'galaxy', 'lenovo', 'xiaomi', 'samsung'])):
                    category = 'tablet'
                    # Generate tablet alternatives based on common brands
                    product_names = [
                        'Samsung Galaxy Tab A9',
                        'Lenovo Tab M10',
                        'Xiaomi Pad 6',
                        'Realme Pad 2',
                        'Apple iPad 10th Gen',
                        'OnePlus Pad'
                    ]
                elif any(kw in title_lower for kw in ['laptop', 'notebook']):
                    category = 'laptop'
                    product_names = [
                        'HP Pavilion 15',
                        'Dell Inspiron 15',
                        'Lenovo IdeaPad 3',
                        'ASUS VivoBook 15',
                        'Acer Aspire 5',
                        'MSI Modern 15'
                    ]
                elif any(kw in title_lower for kw in ['phone', 'smartphone', 'mobile']):
                    category = 'smartphone'
                    product_names = [
                        'Samsung Galaxy A54',
                        'OnePlus Nord 3',
                        'Xiaomi Redmi Note 13',
                        'Realme 12 Pro',
                        'Vivo V29',
                        'OPPO Reno 11'
                    ]
                elif any(kw in title_lower for kw in ['speaker', 'soundbar']):
                    category = 'speaker'
                    product_names = [
                        'JBL Flip 6',
                        'Sony SRS-XB100',
                        'boAt Stone 1200',
                        'Bose SoundLink Flex',
                        'Mivi Roam 2',
                        'Ultimate Ears WONDERBOOM 3'
                    ]
                else:
                    category = 'product'
                    # Generic fallbacks
                    product_names = [
                        f'{product_title} Alternative 1',
                        f'{product_title} Alternative 2',
                        f'{product_title} Alternative 3',
                        f'{product_title} Alternative 4',
                        f'{product_title} Alternative 5'
                    ]
                
                print(f"✅ Generated {len(product_names)} fallback products for category: {category}")
                print(f"   Products: {product_names}")
            else:
                # Other errors - use basic fallback
                print(f"⚠️  Non-quota error, using basic fallback")
                import traceback
                traceback.print_exc()
                product_title = scraped_data.get('title', 'Product')
                title_lower = product_title.lower()
                
                # Still try to detect category for better fallback
                if any(kw in title_lower for kw in ['laptop', 'notebook']):
                    category = 'laptop'
                    product_names = ['HP Pavilion 15', 'Dell Inspiron 15', 'Lenovo IdeaPad 3']
                elif any(kw in title_lower for kw in ['tablet', 'ipad', 'pad']):
                    category = 'tablet'
                    product_names = ['Samsung Galaxy Tab A9', 'Lenovo Tab M10', 'Xiaomi Pad 6']
                else:
                    category = 'product'
                    product_names = [f'{product_title} Alternative 1', f'{product_title} Alternative 2', f'{product_title} Alternative 3']
                
                print(f"⚠️  Using basic fallback product names: {product_names}")
        
        # Get 6 products to ensure 3+ pass quality filtering (minimum 3, maximum 6)
        # Increased to compensate for strict quality filtering
        num_products = min(len(product_names), 6)  # Cap at 6 for quality results
        if num_products < 3:
            print(f"⚠️  Only got {num_products} product names, adding fallbacks...")
            while len(product_names) < 3:
                product_names.append(f"Alternative {category} {len(product_names) + 1}")
        
        print(f"\n🔍 Step 3: Searching ScraperAPI for {num_products} products...")
        print(f"   ScraperAPI Key available: {bool(SCRAPERAPI_KEY)}")
        print(f"   Products to search: {product_names[:num_products]}")
        search_start = time.time()
        # Use same site as input (already extracted above)
        
        # Search products in parallel with reduced timeout for faster failure
        # If ScraperAPI is down, we want to fail fast and use fallbacks
        search_tasks = [
            asyncio.wait_for(
                search_product_scraperapi(name, source_site),
                timeout=12.0  # 12s timeout (ScraperAPI has 10s internal timeout)
            )
            for name in product_names[:num_products]  # Get 3-6 products
        ]
        print(f"   Starting {len(search_tasks)} parallel ScraperAPI searches...")
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Count successful vs failed searches and log details
        successful_searches = sum(1 for r in search_results if not isinstance(r, Exception) and r is not None)
        failed_searches = len(search_results) - successful_searches
        
        # Log detailed results
        for idx, result in enumerate(search_results):
            if isinstance(result, Exception):
                print(f"   ❌ Search {idx+1} ({product_names[idx]}) failed: {str(result)[:100]}")
            elif result:
                print(f"   ✅ Search {idx+1} ({product_names[idx]}) success: {result.get('title', 'N/A')[:50]}")
            else:
                print(f"   ⚠️  Search {idx+1} ({product_names[idx]}) returned None")
        
        if failed_searches > 0:
            print(f"⚠️  ScraperAPI: {failed_searches}/{len(search_results)} searches failed - using fallbacks")
        
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
                price_raw = 0
                if price_str:
                    # Extract numeric price
                    price_clean = re.sub(r'[^\d.]', '', price_str)
                    if price_clean:
                        try:
                            price_raw = int(float(price_clean) * 100)  # Convert to paise
                        except:
                            pass
                
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
                    rating_estimate=search_result.get('rating'),
                    rating_count_estimate=search_result.get('rating_count'),
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
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 400, 404, etc.)
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Backend error: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Check if it's a quota error - but fallback should have handled it
        is_quota = 'quota' in error_msg.lower() or '429' in error_msg or 'rate limit' in error_msg.lower()
        
        if is_quota:
            # Quota error - fallback should have worked, but if we're here, something else failed
            print(f"⚠️  Gemini API quota exceeded - fallback should have been used")
            raise HTTPException(
                status_code=503,
                detail="Gemini API quota exceeded. The system attempted to use fallback products. Please wait 24 hours or ensure billing is enabled for your API key."
            )
        else:
            # Other errors - return generic error
            raise HTTPException(
                status_code=503,
                detail=f"Backend error: {error_msg[:200]}. Please check logs for details."
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


def extract_invoice_from_pdf_plumber(file_data: bytes) -> dict:
    """
    Extract invoice using pdfplumber for better table extraction
    """
    import pdfplumber
    import re
    invoice_data = {}
    
    try:
        with pdfplumber.open(io.BytesIO(file_data)) as pdf:
            if len(pdf.pages) == 0:
                return invoice_data
            
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            
            if not text:
                return invoice_data
            
            # Extract tables
            tables = first_page.extract_tables()
            
            # Extract basic info from text
            # Order Number
            order_match = re.search(r'Order\s+Number[:\s]+([0-9-]+)', text, re.IGNORECASE)
            if not order_match:
                order_match = re.search(r'([0-9]{3}-[0-9]{7}-[0-9]{7})', text)
            if order_match:
                invoice_data['order_number'] = order_match.group(1).strip()
            
            # Order Date
            date_match = re.search(r'Order\s+Date[:\s]+(\d{2}[./]\d{2}[./]\d{4})', text, re.IGNORECASE)
            if date_match:
                invoice_data['order_date'] = date_match.group(1).replace('.', '/')
            
            # Invoice Number
            inv_match = re.search(r'Invoice\s+Number[:\s]+([A-Z0-9-]+)', text, re.IGNORECASE)
            if not inv_match:
                inv_match = re.search(r'(MKT-[0-9]+|CJB[0-9]+-[0-9]+|TN-[A-Z0-9]+-[0-9]+)', text)
            if inv_match:
                invoice_data['invoice_number'] = inv_match.group(1).strip()
            
            # Invoice Date
            inv_date_match = re.search(r'Invoice\s+Date[:\s]+(\d{2}[./]\d{2}[./]\d{4})', text, re.IGNORECASE)
            if inv_date_match:
                invoice_data['invoice_date'] = inv_date_match.group(1).replace('.', '/')
            
            # Store
            if 'amazon' in text.lower():
                invoice_data['store'] = 'Amazon'
            elif 'flipkart' in text.lower():
                invoice_data['store'] = 'Flipkart'
            
            # Extract prices from text (before table extraction, as fallback)
            # Look for various price patterns
            price_patterns = [
                r'Total\s+Amount[:\s]+₹?\s*([\d,]+\.?\d*)',
                r'Amount\s+Payable[:\s]+₹?\s*([\d,]+\.?\d*)',
                r'Grand\s+Total[:\s]+₹?\s*([\d,]+\.?\d*)',
                r'Total[:\s]+₹?\s*([\d,]+\.?\d*)',
                r'Amount\s+in\s+Words[:\s]+.*?₹?\s*([\d,]+\.?\d*)',
                r'Invoice\s+Value[:\s]+₹?\s*([\d,]+\.?\d*)',
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, text, re.IGNORECASE)
                if price_match:
                    price_value = price_match.group(1).replace(',', '')
                    if not invoice_data.get('total_amount'):
                        invoice_data['total_amount'] = f"₹{price_value}"
                    break
            
            # Extract from tables (more accurate)
            product_found = False
            marketplace_fees_count = 0
            total_items = 0
            
            for table in tables:
                if not table:
                    continue
                
                # Find header row
                header_row_idx = None
                for idx, row in enumerate(table):
                    if row and any(cell and ('Description' in str(cell) or 'Sl. No' in str(cell)) for cell in row):
                        header_row_idx = idx
                        break
                
                if header_row_idx is None:
                    continue
                
                # Extract column indices
                headers = table[header_row_idx]
                desc_idx = None
                price_idx = None
                qty_idx = None
                total_idx = None
                
                for i, header in enumerate(headers):
                    if not header:
                        continue
                    header_str = str(header).upper()
                    if 'DESCRIPTION' in header_str:
                        desc_idx = i
                    elif 'UNIT PRICE' in header_str or 'PRICE' in header_str:
                        price_idx = i
                    elif 'QTY' in header_str or 'QUANTITY' in header_str:
                        qty_idx = i
                    elif 'TOTAL' in header_str and 'AMOUNT' in header_str:
                        total_idx = i
                
                # Extract product rows - track what we find
                for row_idx in range(header_row_idx + 1, len(table)):
                    row = table[row_idx]
                    if not row or len(row) == 0:
                        continue
                    
                    # Get description cell
                    desc_cell = row[desc_idx] if desc_idx and desc_idx < len(row) else None
                    if not desc_cell:
                        continue
                    
                    desc_text = str(desc_cell).strip()
                    desc_upper = desc_text.upper()
                    
                    total_items += 1
                    
                    # Track Marketplace Fees items
                    if 'MARKETPLACE FEES' in desc_upper:
                        marketplace_fees_count += 1
                        continue
                    
                    # Skip other non-product items
                    if any(skip in desc_upper for skip in ['SHIPPING CHARGES', 'GIFT WRAP', 'GIFT MESSAGE', 'SERVICE FEE']):
                        continue
                    
                    # Look for ASIN first (most reliable)
                    asin_match = re.search(r'\b(B0[A-Z0-9]{9})\b', desc_text, re.IGNORECASE)
                    product_name = None
                    
                    if asin_match and not product_found:
                        invoice_data['model_sku_asin'] = asin_match.group(1).upper()
                        # Extract product name (everything before ASIN)
                        asin_pos = desc_text.upper().find(asin_match.group(1))
                        product_name = desc_text[:asin_pos].strip()
                    elif not product_found and len(desc_text) > 10:
                        # No ASIN found, but try to extract product name from description
                        # Skip if it looks like a header, total row, or other non-product text
                        if not any(skip in desc_upper for skip in ['TOTAL', 'SUBTOTAL', 'GRAND TOTAL', 'TAX', 'DISCOUNT', 'SHIPPING']):
                            # Take the description as product name if it's substantial
                            product_name = desc_text.strip()
                    
                    if product_name:
                        # Clean up product name
                        product_name = re.sub(r'\s*\([^)]*\)\s*$', '', product_name)  # Remove parentheses at end
                        product_name = re.sub(r'\s+', ' ', product_name).strip()
                        
                        # Remove common invoice suffixes/prefixes
                        product_name = re.sub(r'^(Item|Product|Description)[:\s]+', '', product_name, flags=re.IGNORECASE)
                        product_name = re.sub(r'\s*-\s*$', '', product_name)  # Remove trailing dash
                        
                        if product_name and len(product_name) > 5:
                            invoice_data['product_name'] = product_name
                            product_found = True
                            
                            # Extract brand (first capitalized word or common brand patterns)
                            brand_match = re.match(r'^([A-Z][a-zA-Z\s&]+?)(?:\s|$)', product_name)
                            if brand_match:
                                brand = brand_match.group(1).strip()
                                # Common brand names (1-3 words)
                                if len(brand.split()) <= 3 and len(brand) > 2:
                                    invoice_data['brand'] = brand
                            
                            # HSN Code
                            hsn_match = re.search(r'HSN[:\s]+(\d{8})', desc_text, re.IGNORECASE)
                            if not hsn_match:
                                hsn_match = re.search(r'\b(\d{8})\b', desc_text)
                            if hsn_match:
                                invoice_data['hsn_code'] = hsn_match.group(1)
                            
                            # Extract prices from table cells
                            if price_idx and price_idx < len(row):
                                price_cell = str(row[price_idx]).strip()
                                price_match = re.search(r'₹?\s*([\d,]+\.?\d*)', price_cell)
                                if price_match:
                                    invoice_data['unit_price'] = f"₹{price_match.group(1)}"
                            
                            if qty_idx and qty_idx < len(row):
                                qty_cell = str(row[qty_idx]).strip()
                                qty_match = re.search(r'(\d+)', qty_cell)
                                if qty_match:
                                    invoice_data['quantity'] = qty_match.group(1)
                            
                            if total_idx and total_idx < len(row):
                                total_cell = str(row[total_idx]).strip()
                                total_match = re.search(r'₹?\s*([\d,]+\.?\d*)', total_cell)
                                if total_match:
                                    invoice_data['total_amount'] = f"₹{total_match.group(1)}"
                            
                            # Also check if there's a price in the row text itself (for invoices where price is in same cell as product)
                            if not invoice_data.get('total_amount') and not invoice_data.get('unit_price'):
                                row_text_full = ' '.join([str(cell) for cell in row if cell])
                                # Look for price patterns in the entire row
                                price_in_row = re.search(r'₹\s*([\d,]+\.?\d*)', row_text_full)
                                if price_in_row:
                                    # If it's a large amount, it's likely total_amount
                                    try:
                                        price_val = float(price_in_row.group(1).replace(',', ''))
                                        if price_val > 100:  # Likely total amount
                                            invoice_data['total_amount'] = f"₹{price_in_row.group(1)}"
                                            print(f"💰 Found price in row text: ₹{price_in_row.group(1)}")
                                        else:
                                            invoice_data['unit_price'] = f"₹{price_in_row.group(1)}"
                                    except ValueError:
                                        pass
                            
                            # Tax info from row or nearby
                            row_text = ' '.join([str(cell) for cell in row if cell])
                            tax_rate_match = re.search(r'(\d+)%', row_text)
                            if tax_rate_match:
                                invoice_data['tax_rate'] = f"{tax_rate_match.group(1)}%"
                            
                            if 'IGST' in row_text.upper():
                                invoice_data['tax_type'] = 'IGST'
                            elif 'CGST' in row_text.upper() or 'SGST' in row_text.upper():
                                invoice_data['tax_type'] = 'CGST+SGST'
                            
                            print(f"✅ Found product in table: {product_name[:60]}")
                            break
            
            # If no product found in tables, try text extraction
            if not product_found:
                lines = text.split('\n')
                for line in lines:
                    line_upper = line.upper()
                    if any(skip in line_upper for skip in ['MARKETPLACE FEES', 'SHIPPING CHARGES']):
                        continue
                    
                    asin_match = re.search(r'\b(B0[A-Z0-9]{9})\b', line, re.IGNORECASE)
                    if asin_match:
                        invoice_data['model_sku_asin'] = asin_match.group(1).upper()
                        product_name = line[:line.upper().find(asin_match.group(1))].strip()
                        product_name = re.sub(r'\s+', ' ', product_name).strip()
                        if product_name and len(product_name) > 5:
                            invoice_data['product_name'] = product_name
                            product_found = True
                            break
            
            # Check for marketplace fees - if ALL items are Marketplace Fees, it's not a product invoice
            if not product_found:
                # If we found only Marketplace Fees items in tables, mark it
                if marketplace_fees_count > 0 and total_items > 0 and marketplace_fees_count == total_items:
                    invoice_data['product_name'] = 'N/A'
                    invoice_data['is_marketplace_fees'] = True
                # Or if text contains Marketplace Fees and no products found
                elif 'MARKETPLACE FEES' in text.upper():
                    invoice_data['product_name'] = 'N/A'
                    invoice_data['is_marketplace_fees'] = True
            
    except Exception as e:
        print(f"⚠️  pdfplumber extraction error: {str(e)}")
    
    return invoice_data


def extract_invoice_from_text_fast(pdf_text: str) -> dict:
    """
    Ultra-fast invoice extraction using regex patterns (fallback method)
    """
    import re
    invoice_data = {}
    
    # Order Number
    order_match = re.search(r'Order\s+Number[:\s]+([0-9-]+)', pdf_text, re.IGNORECASE)
    if not order_match:
        order_match = re.search(r'([0-9]{3}-[0-9]{7}-[0-9]{7})', pdf_text)
    if order_match:
        invoice_data['order_number'] = order_match.group(1).strip()
    
    # Order Date
    date_match = re.search(r'Order\s+Date[:\s]+(\d{2}[./]\d{2}[./]\d{4})', pdf_text, re.IGNORECASE)
    if date_match:
        invoice_data['order_date'] = date_match.group(1).replace('.', '/')
    
    # Invoice Number
    inv_match = re.search(r'Invoice\s+Number[:\s]+([A-Z0-9-]+)', pdf_text, re.IGNORECASE)
    if not inv_match:
        inv_match = re.search(r'(MKT-[0-9]+|CJB[0-9]+-[0-9]+|TN-[A-Z0-9]+-[0-9]+)', pdf_text)
    if inv_match:
        invoice_data['invoice_number'] = inv_match.group(1).strip()
    
    # Invoice Date
    inv_date_match = re.search(r'Invoice\s+Date[:\s]+(\d{2}[./]\d{2}[./]\d{4})', pdf_text, re.IGNORECASE)
    if inv_date_match:
        invoice_data['invoice_date'] = inv_date_match.group(1).replace('.', '/')
    
    # Store
    if 'amazon' in pdf_text.lower():
        invoice_data['store'] = 'Amazon'
    elif 'flipkart' in pdf_text.lower():
        invoice_data['store'] = 'Flipkart'
    
    # Product extraction
    lines = pdf_text.split('\n')
    product_found = False
    
    for line in lines:
        line_upper = line.upper()
        if any(skip in line_upper for skip in ['MARKETPLACE FEES', 'SHIPPING CHARGES', 'GIFT WRAP']):
            continue
        
        asin_match = re.search(r'\b(B0[A-Z0-9]{9})\b', line, re.IGNORECASE)
        if asin_match and not product_found:
            invoice_data['model_sku_asin'] = asin_match.group(1).upper()
            product_name = line[:line.upper().find(asin_match.group(1))].strip()
            product_name = re.sub(r'\s+', ' ', product_name).strip()
            if product_name and len(product_name) > 5:
                invoice_data['product_name'] = product_name
                product_found = True
                
                brand_match = re.match(r'^([A-Z][a-zA-Z\s&]+?)(?:\s|$)', product_name)
                if brand_match:
                    invoice_data['brand'] = brand_match.group(1).strip()
                
                hsn_match = re.search(r'HSN[:\s]+(\d{8})', line, re.IGNORECASE)
                if not hsn_match:
                    hsn_match = re.search(r'\b(\d{8})\b', line)
                if hsn_match:
                    invoice_data['hsn_code'] = hsn_match.group(1)
                break
    
    if 'MARKETPLACE FEES' in pdf_text.upper() and not product_found:
        invoice_data['product_name'] = 'N/A'
        invoice_data['is_marketplace_fees'] = True
    
    return invoice_data


@app.post("/extract-invoice")
async def extract_invoice_data_endpoint(request: InvoiceExtractionRequest):
    """
    Extract product details from invoice/receipt PDF or image - ULTRA-FAST (<1 second)
    Uses PyMuPDF for direct text extraction (no image conversion, no API calls)
    Falls back to Gemini Vision only if direct extraction fails
    """
    try:
        import time
        total_start = time.time()
        print(f"\n[INVOICE] Invoice extraction request (file_type: {request.file_type}) - ULTRA-FAST MODE")
        
        # Decode base64 data
        file_data = base64.b64decode(request.image_base64)
        
        invoice_data = {}
        
        # FAST PATH: Extract ALL text from PDF and send to Gemini for intelligent parsing
        if request.file_type == "pdf":
            print(f"📄 Extracting full text from PDF and sending to Gemini for parsing...")
            try:
                extract_start = time.time()
                full_text = ""
                
                # Try PyMuPDF first (fastest)
                try:
                    import fitz
                    pdf_doc = fitz.open(stream=file_data, filetype="pdf")
                    
                    # Extract text from all pages (or first 3 pages max for speed)
                    max_pages = min(len(pdf_doc), 3)
                    for page_num in range(max_pages):
                        page = pdf_doc[page_num]
                        page_text = page.get_text()
                        full_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    
                    pdf_doc.close()
                    print(f"✅ Using PyMuPDF for text extraction")
                except ImportError:
                    print(f"⚠️  PyMuPDF not available, trying pdfplumber...")
                    # Fallback to pdfplumber
                    import pdfplumber
                    import io
                    with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                        max_pages = min(len(pdf.pages), 3)
                        for page_num in range(max_pages):
                            page = pdf.pages[page_num]
                            page_text = page.extract_text()
                            if page_text:
                                full_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    print(f"✅ Using pdfplumber for text extraction")
                
                extract_time = time.time() - extract_start
                print(f"⚡ Extracted {len(full_text)} characters from PDF in {extract_time:.3f}s")
                
                # Check for Marketplace Fees before processing
                if 'MARKETPLACE FEES' in full_text.upper() and 'B0' not in full_text.upper():
                    raise HTTPException(
                        status_code=400,
                        detail="This is a Marketplace Fees invoice, not a product invoice. Please upload the product invoice instead."
                    )
                
                # Send full text to Gemini for intelligent parsing
                print(f"🤖 Sending full PDF text to Gemini for accurate parsing...")
                gemini_start = time.time()
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                prompt = """Extract ALL product details from this invoice text. Be VERY careful and accurate.

Extract EXACTLY these fields from the invoice:
PRODUCT_NAME: [Full product name from the item description row in the table, NOT from headers/footers]
BRAND: [Brand name if visible in product name or separately]
MODEL_SKU_ASIN: [ASIN like B0XXXXX or model number if present]
HSN_CODE: [8-digit HSN code if present]
STORE: [Amazon or Flipkart]
ORDER_NUMBER: [Order number - format: XXX-XXXXXXX-XXXXXXX (three groups separated by hyphens)]
ORDER_DATE: [Order date in DD/MM/YYYY format]
INVOICE_NUMBER: [Invoice number like MKT-XXXXX or CJB1-XXXXX or TN-XXXXX]
INVOICE_DATE: [Invoice date in DD/MM/YYYY format]
UNIT_PRICE: [Unit price per item in ₹ format, e.g., ₹1,234.56]
QUANTITY: [Quantity purchased - just the number]
DISCOUNT: [Discount amount if any, in ₹ format]
NET_AMOUNT: [Net amount before tax, in ₹ format]
TAX_RATE: [Tax rate percentage, e.g., 18%]
TAX_TYPE: [IGST or CGST+SGST]
TAX_AMOUNT: [Tax amount in ₹ format]
TOTAL_AMOUNT: [Total amount paid - this is the final price customer paid, in ₹ format]
SPECIFICATIONS: [Key product specifications if mentioned in invoice]

CRITICAL INSTRUCTIONS:
1. PRODUCT_NAME: Extract from the item description row in the table, NOT from invoice headers or footers
2. ORDER_NUMBER: Must be in format XXX-XXXXXXX-XXXXXXX (three groups of numbers separated by hyphens)
3. TOTAL_AMOUNT: This is the final amount the customer paid - use the "Total Amount" or "Amount Payable" field
4. Dates: Use DD/MM/YYYY format exactly
5. Prices: Include ₹ symbol and format like ₹1,234.56
6. If a field is not found in the invoice, use N/A

Respond with ONLY the field names and values, one per line, like:
PRODUCT_NAME: [value]
BRAND: [value]
ORDER_NUMBER: [value]
TOTAL_AMOUNT: [value]
..."""
                
                response = model.generate_content(
                    prompt + "\n\nINVOICE TEXT:\n" + full_text,
                    generation_config={"temperature": 0.1, "max_output_tokens": 2000}
                )
                result_text = response.text.strip()
                gemini_time = time.time() - gemini_start
                print(f"🤖 Gemini parsing completed: {gemini_time:.2f}s")
        
                # Parse Gemini response
                invoice_data = {}
                lines = result_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip()
                        
                        if key == 'product_name':
                            invoice_data['product_name'] = value
                        elif key == 'brand':
                            invoice_data['brand'] = value
                        elif key == 'model_sku_asin':
                            invoice_data['model_sku_asin'] = value
                        elif key == 'hsn_code':
                            invoice_data['hsn_code'] = value
                        elif key == 'store':
                            invoice_data['store'] = value
                        elif key == 'order_number':
                            invoice_data['order_number'] = value
                        elif key == 'order_date':
                            invoice_data['order_date'] = value
                        elif key == 'invoice_number':
                            invoice_data['invoice_number'] = value
                        elif key == 'invoice_date':
                            invoice_data['invoice_date'] = value
                        elif key == 'unit_price':
                            invoice_data['unit_price'] = value
                        elif key == 'quantity':
                            invoice_data['quantity'] = value
                        elif key == 'discount':
                            invoice_data['discount'] = value
                        elif key == 'net_amount':
                            invoice_data['net_amount'] = value
                        elif key == 'tax_rate':
                            invoice_data['tax_rate'] = value
                        elif key == 'tax_type':
                            invoice_data['tax_type'] = value
                        elif key == 'tax_amount':
                            invoice_data['tax_amount'] = value
                        elif key == 'total_amount':
                            invoice_data['total_amount'] = value
                        elif key == 'specifications':
                            invoice_data['specifications'] = value
                
                # Map to legacy fields
                if 'order_date' in invoice_data:
                    invoice_data['purchase_date'] = invoice_data.get('order_date', 'N/A')
                # Map price fields
                if invoice_data.get('total_amount'):
                    invoice_data['price'] = invoice_data.get('total_amount', 'N/A')
                    invoice_data['price_paid'] = invoice_data.get('total_amount', 'N/A')
                elif invoice_data.get('unit_price'):
                    invoice_data['price'] = invoice_data.get('unit_price', 'N/A')
                    invoice_data['price_paid'] = invoice_data.get('unit_price', 'N/A')
                
                # Validate
                product_name = invoice_data.get('product_name', '')
                if product_name and product_name != 'N/A' and len(product_name.strip()) > 0:
                    total_time = time.time() - total_start
                    print(f"✅ Extraction completed in {total_time:.2f}s!")
                    print(f"📋 Product: {product_name[:60]}")
                    print(f"📋 ASIN: {invoice_data.get('model_sku_asin', 'N/A')}")
                    print(f"📋 Order: {invoice_data.get('order_number', 'N/A')}")
                    print(f"📋 Price: {invoice_data.get('total_amount', 'N/A')}")
                    
                    return {
                        "success": True,
                        "invoice": invoice_data,
                        "message": f"Extracted from PDF in {total_time:.2f}s (Gemini text parsing)"
                    }
                else:
                    print(f"⚠️  Gemini text parsing didn't find product, falling back to Gemini Vision...")
                    
            except HTTPException:
                raise
            except ImportError as e:
                print(f"⚠️  PDF libraries not installed: {str(e)}, falling back to Gemini Vision...")
            except Exception as e:
                print(f"⚠️  PDF text extraction failed: {str(e)}, falling back to Gemini Vision...")
                import traceback
                traceback.print_exc()
        
        # FALLBACK: Gemini Vision API (slower but more accurate for images/scanned PDFs)
        print(f"🖼️  File type: {request.file_type} - {'Converting PDF to image for Gemini Vision' if request.file_type == 'pdf' else 'Using Gemini Vision directly for image'}")
        images = []
        if request.file_type == "pdf":
            try:
                from pdf2image import convert_from_bytes
                import os
                
                poppler_path = None
                possible_paths = [
                    os.path.join(os.path.dirname(__file__), "poppler", "bin"),
                    os.path.join(os.getcwd(), "backend", "poppler", "bin"),
                    os.path.join(os.getcwd(), "poppler", "bin"),
                    "backend/poppler/bin",
                ]
                for path in possible_paths:
                    abs_path = os.path.abspath(path)
                    # Check if poppler executable exists
                    poppler_exe = os.path.join(abs_path, "pdftoppm.exe") if os.name == 'nt' else os.path.join(abs_path, "pdftoppm")
                    if os.path.exists(abs_path) and os.path.exists(poppler_exe):
                        poppler_path = abs_path
                        print(f"📂 Found poppler at: {poppler_path}")
                        break
                
                if not poppler_path:
                    print(f"⚠️  Poppler not found - trying system PATH (may fail if not installed)")
                
                try:
                    pdf_images = convert_from_bytes(
                        file_data,
                        dpi=150,
                        first_page=1,
                        last_page=1,
                        poppler_path=poppler_path if poppler_path else None,
                        fmt='jpeg',
                        jpegopt={'quality': 85}
                    )
                    if pdf_images:
                        images.append(pdf_images[0])
                except Exception as pdf_conv_error:
                    print(f"❌ PDF to image conversion failed: {str(pdf_conv_error)}")
                    print(f"💡 Tip: Install poppler-utils or add poppler/bin to PATH")
                    # Try using PyMuPDF to convert PDF to image as fallback
                    try:
                        import fitz
                        pdf_doc = fitz.open(stream=file_data, filetype="pdf")
                        if len(pdf_doc) > 0:
                            first_page = pdf_doc[0]
                            pix = first_page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                            img_data = pix.tobytes("jpeg")
                            image = Image.open(BytesIO(img_data))
                            images.append(image)
                            print(f"✅ Converted PDF to image using PyMuPDF (fallback)")
                        pdf_doc.close()
                    except Exception as pymupdf_error:
                        print(f"❌ PyMuPDF conversion also failed: {str(pymupdf_error)}")
                        raise Exception("Cannot convert PDF to image - poppler not available and PyMuPDF conversion failed")
            except Exception as e:
                print(f"⚠️  PDF to image conversion failed: {str(e)}")
        else:
            image = Image.open(BytesIO(file_data))
            images.append(image)
        
        if images:
            extraction_method = 'PDF→Image→Gemini' if request.file_type == 'pdf' else 'Image→Gemini'
            print(f"🤖 Using Gemini Vision API for {extraction_method} extraction...")
            model = genai.GenerativeModel('gemini-2.5-flash')
            prompt = """Extract product details from this invoice. ONLY extract from PRODUCT ROWS (ignore Marketplace Fees, Shipping, etc.).

Respond EXACTLY:
PRODUCT_NAME: [product name]
BRAND: [brand]
MODEL_SKU_ASIN: [ASIN like B0XXXXX]
HSN_CODE: [HSN code]
STORE: Amazon or Flipkart
ORDER_NUMBER: [order number]
ORDER_DATE: [DD/MM/YYYY]
INVOICE_NUMBER: [invoice number]
INVOICE_DATE: [DD/MM/YYYY]
UNIT_PRICE: ₹[amount]
QUANTITY: [number]
DISCOUNT: ₹[amount]
NET_AMOUNT: ₹[amount]
TAX_RATE: [percentage]%
TAX_TYPE: [IGST/CGST+SGST]
TAX_AMOUNT: ₹[amount]
TOTAL_AMOUNT: ₹[amount]
SPECIFICATIONS: [specs]

If Marketplace Fees invoice, return N/A for all product fields."""
            
            gemini_start = time.time()
            response = model.generate_content(
                [prompt, images[0]],
                generation_config={"temperature": 0.1, "max_output_tokens": 1000}
            )
            result_text = response.text.strip()
            gemini_time = time.time() - gemini_start
            extraction_method = 'PDF→Image→Gemini' if request.file_type == 'pdf' else 'Image→Gemini'
            print(f"🤖 Gemini Vision extraction completed: {gemini_time:.2f}s ({extraction_method})")
            
            # Parse Gemini response
            lines = result_text.split('\n')
            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace('_', '_')
                    value = value.strip()
                    if key == 'product_name':
                        invoice_data['product_name'] = value
                    elif key == 'brand':
                        invoice_data['brand'] = value
                    elif key == 'model_sku_asin':
                        invoice_data['model_sku_asin'] = value
                    elif key == 'hsn_code':
                        invoice_data['hsn_code'] = value
                    elif key == 'store':
                        invoice_data['store'] = value
                    elif key == 'order_number':
                        invoice_data['order_number'] = value
                    elif key == 'order_date':
                        invoice_data['order_date'] = value
                    elif key == 'invoice_number':
                        invoice_data['invoice_number'] = value
                    elif key == 'invoice_date':
                        invoice_data['invoice_date'] = value
                    elif key == 'unit_price':
                        invoice_data['unit_price'] = value
                    elif key == 'quantity':
                        invoice_data['quantity'] = value
                    elif key == 'discount':
                        invoice_data['discount'] = value
                    elif key == 'net_amount':
                        invoice_data['net_amount'] = value
                    elif key == 'tax_rate':
                        invoice_data['tax_rate'] = value
                    elif key == 'tax_type':
                        invoice_data['tax_type'] = value
                    elif key == 'tax_amount':
                        invoice_data['tax_amount'] = value
                    elif key == 'total_amount':
                        invoice_data['total_amount'] = value
                    elif key == 'specifications':
                        invoice_data['specifications'] = value
        
        # Validate results
        product_name = invoice_data.get('product_name', '')
        if product_name and product_name.upper() in ['MARKETPLACE FEES', 'SERVICE FEE', 'SHIPPING CHARGES']:
            raise HTTPException(
                status_code=400,
                detail="This appears to be a Marketplace Fees or Service invoice, not a product invoice."
            )
        
        if product_name and product_name != 'N/A' and len(product_name.strip()) > 0:
            total_time = time.time() - total_start
            print(f"✅ Invoice extracted: {product_name[:80]}")
            print(f"⏱️  TOTAL TIME: {total_time:.3f}s")
            
            # Map legacy fields
            if 'order_date' in invoice_data:
                invoice_data['purchase_date'] = invoice_data.get('order_date', 'N/A')
            # Map price fields - prioritize total_amount, then unit_price, then net_amount
            if invoice_data.get('total_amount'):
                invoice_data['price'] = invoice_data.get('total_amount', 'N/A')
                invoice_data['price_paid'] = invoice_data.get('total_amount', 'N/A')
            elif invoice_data.get('unit_price'):
                invoice_data['price'] = invoice_data.get('unit_price', 'N/A')
                invoice_data['price_paid'] = invoice_data.get('unit_price', 'N/A')
            elif invoice_data.get('net_amount'):
                invoice_data['price'] = invoice_data.get('net_amount', 'N/A')
                invoice_data['price_paid'] = invoice_data.get('net_amount', 'N/A')
            
            # If warranty slip is provided, extract and merge warranty data
            warranty_image_base64 = None
            if request.warranty_image_base64:
                print(f"🛡️  Warranty slip provided - extracting warranty information...")
                try:
                    # Decode warranty image
                    warranty_file_data = base64.b64decode(request.warranty_image_base64)
                    
                    # Try to detect if it's a PDF and convert to image
                    warranty_image = None
                    try:
                        # Try opening as image first
                        warranty_image = Image.open(BytesIO(warranty_file_data))
                        warranty_image_base64 = request.warranty_image_base64  # Use original if it's already an image
                    except Exception:
                        # If not an image, try as PDF
                        try:
                            import fitz
                            pdf_doc = fitz.open(stream=warranty_file_data, filetype="pdf")
                            if len(pdf_doc) > 0:
                                first_page = pdf_doc[0]
                                pix = first_page.get_pixmap(matrix=fitz.Matrix(2, 2))
                                img_data = pix.tobytes("jpeg")
                                warranty_image = Image.open(BytesIO(img_data))
                                # Convert to base64 for return
                                img_buffer = BytesIO()
                                warranty_image.save(img_buffer, format='JPEG', quality=85)
                                warranty_image_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
                                print(f"✅ Converted warranty PDF to image")
                            pdf_doc.close()
                        except Exception as pdf_error:
                            print(f"⚠️  Could not process warranty as image or PDF: {str(pdf_error)}")
                            # Fallback: use original base64
                            warranty_image_base64 = request.warranty_image_base64
                    
                    if not warranty_image:
                        raise Exception("Could not process warranty image/PDF")
                    
                    # Use Gemini Vision to extract warranty fields
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    warranty_prompt = """Extract warranty information from this warranty slip/packing slip image.

Extract ONLY these fields:
WARRANTY_PERIOD: [warranty period if mentioned - e.g., "1 year", "2 years", "12 months" - if not found, use N/A]
WARRANTY_TERMS: [warranty terms or conditions if visible - if not found, use N/A]
ORDER_NUMBER: [Order ID or Order number if visible - format: XXX-XXXXXXX-XXXXXXX]
INVOICE_NUMBER: [Invoice number if visible - format: CJB1-XXXXX or MKT-XXXXX]

Respond with ONLY the field names and values, one per line:
WARRANTY_PERIOD: [value]
WARRANTY_TERMS: [value]
..."""
                    
                    warranty_response = model.generate_content(
                        [warranty_prompt, warranty_image],
                        generation_config={"temperature": 0.1, "max_output_tokens": 500}
                    )
                    warranty_text = warranty_response.text.strip()
                    
                    # Parse warranty response
                    warranty_data = {}
                    for line in warranty_text.split('\n'):
                        line = line.strip()
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip().lower().replace(' ', '_').replace('-', '_')
                            value = value.strip()
                            if value.startswith('[') and value.endswith(']'):
                                value = value[1:-1].strip()
                            warranty_data[key] = value
                    
                    # Merge warranty fields into invoice_data
                    if warranty_data.get('warranty_period') and warranty_data.get('warranty_period') != 'N/A':
                        invoice_data['warranty_period'] = warranty_data.get('warranty_period')
                    if warranty_data.get('warranty_terms') and warranty_data.get('warranty_terms') != 'N/A':
                        invoice_data['warranty_terms'] = warranty_data.get('warranty_terms')
                    # Merge other fields if invoice doesn't have them
                    if not invoice_data.get('order_number') and warranty_data.get('order_number'):
                        invoice_data['order_number'] = warranty_data.get('order_number')
                    if not invoice_data.get('invoice_number') and warranty_data.get('invoice_number'):
                        invoice_data['invoice_number'] = warranty_data.get('invoice_number')
                    
                    print(f"✅ Extracted and merged warranty data into invoice")
                    
                    # warranty_image_base64 already set during conversion above
                except Exception as warranty_error:
                    print(f"⚠️  Warranty extraction failed (continuing with invoice only): {str(warranty_error)}")
                    # Continue with invoice data only, but still include the image (use converted if available, otherwise original)
                    if not warranty_image_base64:
                        warranty_image_base64 = request.warranty_image_base64
            
            response_data = {
                "success": True,
                "invoice": invoice_data,
                "message": f"Extracted from {'PDF' if request.file_type == 'pdf' else 'image'} in {total_time:.3f}s"
            }
            
            # Include warranty image if provided
            if warranty_image_base64:
                response_data["warranty_image_base64"] = warranty_image_base64
            
            return response_data
        else:
            raise HTTPException(
                status_code=404,
                detail="Could not extract product information from invoice."
            )
        
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Invoice extraction error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Invoice extraction failed: {str(e)}"
        )


@app.post("/extract-warranty")
async def extract_warranty_data_endpoint(request: WarrantyExtractionRequest):
    """
    Extract product warranty details from warranty slip/packing slip PDF or image using Gemini 2.5 Flash Vision
    Extracts detailed warranty information including:
    - Product name, brand, model/SKU/ASIN
    - Order number, order date, invoice number, packing slip date
    - Seller information, product specifications
    - Warranty period and terms
    """
    try:
        print(f"\n🛡️  Warranty slip extraction request (file_type: {request.file_type})")
        
        # Decode base64 data
        file_data = base64.b64decode(request.image_base64)
        
        # Store original file (PDF or image) as base64 for return - let frontend handle display/download
        warranty_file_base64 = request.image_base64  # Always return original file
        warranty_file_type = request.file_type  # Store file type for frontend
        warranty_image_for_processing = None
        
        if request.file_type == "pdf":
            # For PDFs, we'll extract text but return original PDF for download/view
            print(f"📄 Processing PDF - will return original PDF for download/view")
            # Try to open PDF for text extraction (but keep original for return)
            try:
                import fitz
                pdf_doc = fitz.open(stream=file_data, filetype="pdf")
                pdf_doc.close()
                print(f"✅ PDF is valid, returning original PDF base64 (length: {len(warranty_file_base64)} chars)")
            except Exception as pdf_error:
                print(f"⚠️  PDF validation failed: {str(pdf_error)}")
        else:
            # For images, use as-is for processing
            warranty_image_for_processing = Image.open(BytesIO(file_data))
            print(f"✅ Using image as-is (base64 length: {len(warranty_file_base64)} chars)")
        
        # Start with invoice data as base (if provided)
        warranty_data = {}
        invoice_data = getattr(request, 'invoice_data', None) or (request.dict().get('invoice_data') if hasattr(request, 'dict') else None)
        if invoice_data and isinstance(invoice_data, dict):
            print(f"📋 Using invoice data as base: {list(invoice_data.keys())}")
            # Map invoice fields to warranty fields
            warranty_data = {
                'product_name': invoice_data.get('product_name', ''),
                'brand': invoice_data.get('brand', ''),
                'model_sku_asin': invoice_data.get('model_sku_asin', ''),
                'store': invoice_data.get('store', ''),
                'order_number': invoice_data.get('order_number', ''),
                'order_date': invoice_data.get('purchase_date') or invoice_data.get('order_date', ''),
                'invoice_number': invoice_data.get('invoice_number', ''),
                'specifications': invoice_data.get('specifications', ''),
            }
            # Remove empty values
            warranty_data = {k: v for k, v in warranty_data.items() if v and v != 'N/A' and v != 'Not specified'}
            print(f"✅ Loaded {len(warranty_data)} fields from invoice data")
        
        # Handle PDF files - Extract full text and send to Gemini
        if request.file_type == "pdf":
            print(f"📄 Extracting full text from warranty PDF and sending to Gemini...")
            try:
                import time
                extract_start = time.time()
                full_text = ""
                
                # Try PyMuPDF first (fastest)
                try:
                    import fitz
                    pdf_doc = fitz.open(stream=file_data, filetype="pdf")
                    
                    # Extract text from all pages (or first 3 pages max for speed)
                    max_pages = min(len(pdf_doc), 3)
                    for page_num in range(max_pages):
                        page = pdf_doc[page_num]
                        page_text = page.get_text()
                        full_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    
                    pdf_doc.close()
                    print(f"✅ Using PyMuPDF for warranty text extraction")
                except ImportError:
                    print(f"⚠️  PyMuPDF not available, trying pdfplumber...")
                    # Fallback to pdfplumber
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                        max_pages = min(len(pdf.pages), 3)
                        for page_num in range(max_pages):
                            page = pdf.pages[page_num]
                            page_text = page.extract_text()
                            if page_text:
                                full_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                    print(f"✅ Using pdfplumber for warranty text extraction")
                
                extract_time = time.time() - extract_start
                print(f"⚡ Extracted {len(full_text)} characters from warranty PDF in {extract_time:.3f}s")
                
                # If we have invoice data and PDF text is very small or empty, skip Gemini and use invoice data
                if invoice_data and len(full_text.strip()) < 50:
                    print(f"⚠️  PDF text is too small ({len(full_text)} chars), skipping Gemini and using invoice data + basic warranty fields")
                    # Just extract warranty-specific fields from the small text if possible
                    if 'warranty' in full_text.lower() or 'guarantee' in full_text.lower():
                        warranty_match = re.search(r'(\d+)\s*(?:year|month|yr|mo)', full_text, re.IGNORECASE)
                        if warranty_match:
                            warranty_data['warranty_period'] = f"{warranty_match.group(1)} {'year' if 'year' in full_text.lower() else 'month'}"
                    # Skip to validation - we already have invoice data
                else:
                    # Send full text to Gemini for intelligent parsing
                    try:
                        print(f"🤖 Sending warranty PDF text to Gemini for parsing...")
                        gemini_start = time.time()
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        
                        prompt = """Extract ALL product warranty information from this warranty slip/packing slip text. Be VERY careful and accurate.

This is a PACKING SLIP format. Look for:
- "Packing slip for" header with date
- "Sold By" section with seller name and address
- "Invoice Number" field
- "Order ID" or "Order Number" field
- "QTY" and "DESCRIPTION" table with product details
- Product code/SKU after description

Extract EXACTLY these fields:
PRODUCT_NAME: [Full product name from DESCRIPTION field - everything in the description row, e.g., "Amazon Basics Height Adjustable Laptop Table | Adjustable Table Angle | Alloy Steel | Foldable | Black | 75 cm - H, 52.5 cm - L, 40 cm - W"]
BRAND: [Brand name - usually first part of product name, e.g., "Amazon Basics"]
MODEL_SKU_ASIN: [Product code/SKU - usually appears after description, format: B0XXXXX or BOCW1NYQ8G]
STORE: [Store/platform - Amazon, Flipkart, etc. - usually "Amazon" for Amazon packing slips]
ORDER_NUMBER: [Order ID or Order number - format: XXX-XXXXXXX-XXXXXXX, e.g., "406-4210626-4717907"]
ORDER_DATE: [Order date from "Packing slip for" header - convert to DD/MM/YYYY format, e.g., "10 November, 2025" → "10/11/2025"]
INVOICE_NUMBER: [Invoice number - format: CJB1-XXXXX or MKT-XXXXX, e.g., "CJB1-1919765"]
PACKING_SLIP_DATE: [Packing slip date from header - DD/MM/YYYY format]
SELLER_NAME: [Seller name from "Sold By" section - full company name, e.g., "RETAILEZ PRIVATE LIMITED"]
SELLER_ADDRESS: [Complete seller address from "Sold By" section - include all address lines]
QUANTITY: [Quantity from QTY column - just the number, e.g., "1"]
PRODUCT_CODE: [Product code/SKU - same as MODEL_SKU_ASIN if found]
SPECIFICATIONS: [Extract specifications from description - dimensions (H, L, W), material, color, features - e.g., "Height: 75 cm, Length: 52.5 cm, Width: 40 cm, Material: Alloy Steel, Color: Black, Features: Adjustable Table Angle, Foldable"]
WARRANTY_PERIOD: [Warranty period if mentioned - e.g., "1 year", "2 years", "12 months" - if not found, use N/A]
WARRANTY_TERMS: [Warranty terms or conditions if visible - if not found, use N/A]

CRITICAL INSTRUCTIONS:
1. PRODUCT_NAME: Extract the ENTIRE description from DESCRIPTION field, including all pipe-separated parts
2. BRAND: Extract from first part of product name (before first "|" or space)
3. ORDER_NUMBER: Look for "Order ID" or "Order Number" - format XXX-XXXXXXX-XXXXXXX
4. INVOICE_NUMBER: Look for "Invoice Number:" field
5. PACKING_SLIP_DATE: Extract from "Packing slip for" header, convert to DD/MM/YYYY
6. SELLER_NAME: Extract company name from "Sold By" section
7. SELLER_ADDRESS: Extract complete address from "Sold By" section (all lines)
8. SPECIFICATIONS: Parse dimensions and features from description (H, L, W, material, color, etc.)
9. MODEL_SKU_ASIN: Look for product code after description or in separate field
10. If a field is not found, use N/A

Example based on typical packing slip:
PRODUCT_NAME: Amazon Basics Height Adjustable Laptop Table | Adjustable Table Angle | Alloy Steel | Foldable | Black | 75 cm - H, 52.5 cm - L, 40 cm - W
BRAND: Amazon Basics
MODEL_SKU_ASIN: BOCW1NYQ8G
STORE: Amazon
ORDER_NUMBER: 406-4210626-4717907
ORDER_DATE: 10/11/2025
INVOICE_NUMBER: CJB1-1919765
PACKING_SLIP_DATE: 10/11/2025
SELLER_NAME: RETAILEZ PRIVATE LIMITED
SELLER_ADDRESS: Survey No. 153/1 153/2226/2,229/2,230/2 Chettipalayam, Oratakuppai Village, Palladam Main Road COIMBATORE - 641201 TAMIL NADU, India
QUANTITY: 1
PRODUCT_CODE: BOCW1NYQ8G
SPECIFICATIONS: Height: 75 cm, Length: 52.5 cm, Width: 40 cm, Material: Alloy Steel, Color: Black, Features: Adjustable Table Angle, Foldable
WARRANTY_PERIOD: N/A
WARRANTY_TERMS: N/A

Now extract from this warranty/packing slip:"""
                        
                        response = model.generate_content(
                            prompt + "\n\nWARRANTY SLIP TEXT:\n" + full_text,
                            generation_config={"temperature": 0.1, "max_output_tokens": 2000}
                        )
                        result_text = response.text.strip()
                        gemini_time = time.time() - gemini_start
                        print(f"🤖 Gemini warranty parsing completed: {gemini_time:.2f}s")
                        print(f"📄 Gemini response preview: {result_text[:500]}...")
                        
                        # Parse Gemini response - handle multiple formats
                        lines = result_text.split('\n')
                        for line in lines:
                            line = line.strip()
                            # Skip empty lines and markdown formatting
                            if not line or line.startswith('#') or line.startswith('*'):
                                continue
                            
                            # Handle "KEY: value" format
                            if ':' in line:
                                parts = line.split(':', 1)
                                if len(parts) == 2:
                                    key, value = parts
                                    key = key.strip().lower().replace(' ', '_').replace('-', '_')
                                    value = value.strip()
                                    
                                    # Remove common prefixes/suffixes
                                    if value.startswith('[') and value.endswith(']'):
                                        value = value[1:-1].strip()
                                    if value.startswith('(') and value.endswith(')'):
                                        value = value[1:-1].strip()
                                    
                                    if key == 'product_name':
                                        warranty_data['product_name'] = value
                                    elif key == 'brand':
                                        warranty_data['brand'] = value
                                    elif key == 'model_sku_asin':
                                        warranty_data['model_sku_asin'] = value
                                    elif key == 'store':
                                        warranty_data['store'] = value
                                    elif key == 'order_number':
                                        warranty_data['order_number'] = value
                                    elif key == 'order_date':
                                        warranty_data['order_date'] = value
                                    elif key == 'invoice_number':
                                        warranty_data['invoice_number'] = value
                                    elif key == 'packing_slip_date':
                                        warranty_data['packing_slip_date'] = value
                                    elif key == 'seller_name':
                                        warranty_data['seller_name'] = value
                                    elif key == 'seller_address':
                                        warranty_data['seller_address'] = value
                                    elif key == 'quantity':
                                        warranty_data['quantity'] = value
                                    elif key == 'product_code':
                                        warranty_data['product_code'] = value
                                    elif key == 'specifications':
                                        warranty_data['specifications'] = value
                                    elif key == 'warranty_period':
                                        warranty_data['warranty_period'] = value
                                    elif key == 'warranty_terms':
                                        warranty_data['warranty_terms'] = value
                    except Exception as gemini_error:
                        error_msg = str(gemini_error)
                        print(f"❌ Gemini warranty parsing error: {error_msg}")
                        
                        # If we have invoice data, use it as fallback instead of failing
                        if invoice_data and ('quota' in error_msg.lower() or '429' in error_msg or 'rate limit' in error_msg.lower()):
                            print(f"⚠️  Gemini quota hit, but we have invoice data - using invoice data as warranty data")
                            # Invoice data is already loaded in warranty_data, just add warranty fields as N/A
                            if 'warranty_period' not in warranty_data:
                                warranty_data['warranty_period'] = 'N/A'
                            if 'warranty_terms' not in warranty_data:
                                warranty_data['warranty_terms'] = 'N/A'
                            # Continue to validation - we have invoice data
                        elif invoice_data:
                            print(f"⚠️  Gemini parsing failed, but we have invoice data - using invoice data as warranty data")
                            # Invoice data is already loaded, just add warranty fields as N/A
                            if 'warranty_period' not in warranty_data:
                                warranty_data['warranty_period'] = 'N/A'
                            if 'warranty_terms' not in warranty_data:
                                warranty_data['warranty_terms'] = 'N/A'
                            # Continue to validation
                        else:
                            # No invoice data, re-raise the error
                            raise
                
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="PDF processing requires PyMuPDF. Install with: pip install pymupdf"
                )
            except Exception as e:
                print(f"❌ Warranty PDF extraction error: {str(e)}")
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract warranty data: {str(e)}"
                )
        else:
            # Handle image files - use Gemini Vision
            print(f"🖼️  Processing warranty image file with Gemini Vision...")
            # Use pre-processed image if available (from PDF conversion), otherwise open from file_data
            if warranty_image_for_processing:
                image = warranty_image_for_processing
            else:
                image = Image.open(BytesIO(file_data))
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            prompt = """Extract ALL product warranty information from this warranty slip/packing slip image. Be VERY careful and accurate.

This is a PACKING SLIP format. Look for:
- "Packing slip for" header with date (e.g., "Packing slip for T1NNHqSmk 10 November, 2025")
- "Sold By" section with seller name and complete address
- "Invoice Number:" field (e.g., "CJB1-1919765")
- "Order ID" or "Order Number" field (e.g., "406-4210626-4717907")
- "QTY" and "DESCRIPTION" table with product details
- Product code/SKU after description (e.g., "BOCW1NYQ8G")

Extract EXACTLY these fields:
PRODUCT_NAME: [Full product name from DESCRIPTION field - extract the ENTIRE description including all pipe-separated parts, e.g., "Amazon Basics Height Adjustable Laptop Table | Adjustable Table Angle | Alloy Steel | Foldable | Black | 75 cm - H, 52.5 cm - L, 40 cm - W"]
BRAND: [Brand name - extract from first part of product name before first "|", e.g., "Amazon Basics"]
MODEL_SKU_ASIN: [Product code/SKU - usually appears after description or in separate field, format: B0XXXXX or BOCW1NYQ8G, e.g., "BOCW1NYQ8G"]
STORE: [Store/platform - usually "Amazon" for Amazon packing slips, or "Flipkart" for Flipkart]
ORDER_NUMBER: [Order ID or Order number - format: XXX-XXXXXXX-XXXXXXX, e.g., "406-4210626-4717907"]
ORDER_DATE: [Order date from "Packing slip for" header - convert to DD/MM/YYYY format, e.g., "10 November, 2025" → "10/11/2025"]
INVOICE_NUMBER: [Invoice number from "Invoice Number:" field - format: CJB1-XXXXX or MKT-XXXXX, e.g., "CJB1-1919765"]
PACKING_SLIP_DATE: [Packing slip date from header - convert to DD/MM/YYYY format, e.g., "10 November, 2025" → "10/11/2025"]
SELLER_NAME: [Seller name from "Sold By" section - full company name, e.g., "RETAILEZ PRIVATE LIMITED"]
SELLER_ADDRESS: [Complete seller address from "Sold By" section - include ALL address lines, e.g., "Survey No. 153/1 153/2226/2,229/2,230/2 Chettipalayam, Oratakuppai Village, Palladam Main Road COIMBATORE - 641201 TAMIL NADU, India"]
QUANTITY: [Quantity from QTY column - just the number, e.g., "1"]
PRODUCT_CODE: [Product code/SKU - same as MODEL_SKU_ASIN if found, e.g., "BOCW1NYQ8G"]
SPECIFICATIONS: [Extract specifications from description - parse dimensions (H, L, W), material, color, features. Format: "Height: 75 cm, Length: 52.5 cm, Width: 40 cm, Material: Alloy Steel, Color: Black, Features: Adjustable Table Angle, Foldable"]
WARRANTY_PERIOD: [Warranty period if mentioned anywhere - e.g., "1 year", "2 years", "12 months" - if not found, use N/A]
WARRANTY_TERMS: [Warranty terms or conditions if visible - if not found, use N/A]

CRITICAL INSTRUCTIONS:
1. PRODUCT_NAME: Extract the ENTIRE description from DESCRIPTION field, including ALL pipe-separated parts (everything between QTY and product code)
2. BRAND: Extract from first part of product name (before first "|" or space)
3. ORDER_NUMBER: Look for "Order ID" or "Order Number" - must be in format XXX-XXXXXXX-XXXXXXX
4. INVOICE_NUMBER: Look for "Invoice Number:" field - format CJB1-XXXXX or MKT-XXXXX
5. PACKING_SLIP_DATE: Extract from "Packing slip for" header, convert date format to DD/MM/YYYY
6. SELLER_NAME: Extract full company name from "Sold By" section (first line)
7. SELLER_ADDRESS: Extract COMPLETE address from "Sold By" section (all address lines together)
8. SPECIFICATIONS: Parse dimensions (H, L, W), material, color, and features from description
9. MODEL_SKU_ASIN: Look for product code after description or in separate field (format: B0XXXXX or BOCW1NYQ8G)
10. If a field is not found, use N/A

Respond with ONLY the field names and values, one per line, like:
PRODUCT_NAME: [value]
BRAND: [value]
ORDER_NUMBER: [value]
..."""
            
            gemini_start = time.time()
            response = model.generate_content(
                [prompt, image],
                generation_config={"temperature": 0.1, "max_output_tokens": 2000}
            )
            result_text = response.text.strip()
            gemini_time = time.time() - gemini_start
            print(f"🤖 Gemini Vision warranty extraction completed: {gemini_time:.2f}s")
            print(f"📄 Gemini response preview: {result_text[:500]}...")
            
            # Parse Gemini response
            lines = result_text.split('\n')
            for line in lines:
                line = line.strip()
                # Skip empty lines and markdown formatting
                if not line or line.startswith('#') or line.startswith('*'):
                    continue
                
                # Handle both "KEY: value" format
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key, value = parts
                        key = key.strip().lower().replace(' ', '_').replace('-', '_')
                        value = value.strip()
                        
                        # Remove common prefixes/suffixes
                        if value.startswith('[') and value.endswith(']'):
                            value = value[1:-1].strip()
                        if value.startswith('(') and value.endswith(')'):
                            value = value[1:-1].strip()
                        
                        if key == 'product_name':
                            warranty_data['product_name'] = value
                        elif key == 'brand':
                            warranty_data['brand'] = value
                        elif key == 'model_sku_asin':
                            warranty_data['model_sku_asin'] = value
                        elif key == 'store':
                            warranty_data['store'] = value
                        elif key == 'order_number':
                            warranty_data['order_number'] = value
                        elif key == 'order_date':
                            warranty_data['order_date'] = value
                        elif key == 'invoice_number':
                            warranty_data['invoice_number'] = value
                        elif key == 'packing_slip_date':
                            warranty_data['packing_slip_date'] = value
                        elif key == 'seller_name':
                            warranty_data['seller_name'] = value
                        elif key == 'seller_address':
                            warranty_data['seller_address'] = value
                        elif key == 'quantity':
                            warranty_data['quantity'] = value
                        elif key == 'product_code':
                            warranty_data['product_code'] = value
                        elif key == 'specifications':
                            warranty_data['specifications'] = value
                        elif key == 'warranty_period':
                            warranty_data['warranty_period'] = value
                        elif key == 'warranty_terms':
                            warranty_data['warranty_terms'] = value
        
        # Map to common fields for consistency
        if 'packing_slip_date' in warranty_data:
            warranty_data['document_date'] = warranty_data.get('packing_slip_date', 'N/A')
        if 'order_date' in warranty_data and 'document_date' not in warranty_data:
            warranty_data['document_date'] = warranty_data.get('order_date', 'N/A')
        
        # Validate - be more lenient, check if we have at least product name or order number
        product_name = warranty_data.get('product_name', '').strip()
        order_number = warranty_data.get('order_number', '').strip()
        model_sku = warranty_data.get('model_sku_asin', '').strip()
        
        # Debug: Print what we extracted
        print(f"🔍 Extracted fields: product_name='{product_name}', order_number='{order_number}', model_sku='{model_sku}'")
        print(f"🔍 All extracted fields: {list(warranty_data.keys())}")
        
        # Get invoice_data again for validation
        invoice_data = getattr(request, 'invoice_data', None) or (request.dict().get('invoice_data') if hasattr(request, 'dict') else None)
        has_invoice_data = invoice_data is not None and isinstance(invoice_data, dict)
        
        # Accept if we have product_name (not N/A) OR if we have order_number and model_sku OR if we have invoice data
        if (product_name and product_name != 'N/A' and len(product_name) > 3) or \
           (order_number and order_number != 'N/A' and model_sku and model_sku != 'N/A') or \
           has_invoice_data:
            
            # If product_name is missing but we have other data, try to construct it
            if not product_name or product_name == 'N/A' or len(product_name) <= 3:
                if warranty_data.get('brand') and warranty_data.get('model_sku_asin'):
                    warranty_data['product_name'] = f"{warranty_data.get('brand')} {warranty_data.get('model_sku_asin')}"
                elif warranty_data.get('model_sku_asin'):
                    warranty_data['product_name'] = f"Product {warranty_data.get('model_sku_asin')}"
                elif has_invoice_data and invoice_data.get('product_name'):
                    warranty_data['product_name'] = invoice_data.get('product_name')
                else:
                    warranty_data['product_name'] = "Unknown Product"
            
            # Ensure brand is set
            if not warranty_data.get('brand') or warranty_data.get('brand') == 'N/A':
                if product_name and '|' in product_name:
                    warranty_data['brand'] = product_name.split('|')[0].strip()
                elif product_name:
                    warranty_data['brand'] = product_name.split()[0] if product_name.split() else 'Unknown'
                elif has_invoice_data and invoice_data.get('brand'):
                    warranty_data['brand'] = invoice_data.get('brand')
                else:
                    warranty_data['brand'] = 'Unknown'
            
            # Ensure other fields from invoice are preserved if not in warranty slip
            if has_invoice_data:
                if not warranty_data.get('order_number') and invoice_data.get('order_number'):
                    warranty_data['order_number'] = invoice_data.get('order_number')
                if not warranty_data.get('invoice_number') and invoice_data.get('invoice_number'):
                    warranty_data['invoice_number'] = invoice_data.get('invoice_number')
                if not warranty_data.get('model_sku_asin') and invoice_data.get('model_sku_asin'):
                    warranty_data['model_sku_asin'] = invoice_data.get('model_sku_asin')
                if not warranty_data.get('store') and invoice_data.get('store'):
                    warranty_data['store'] = invoice_data.get('store')
            
            print(f"✅ Warranty slip extracted: {warranty_data.get('product_name')[:80]}")
            
            # Convert warranty data to invoice format (merge into invoice structure)
            invoice_response = {
                'product_name': warranty_data.get('product_name', ''),
                'brand': warranty_data.get('brand', ''),
                'model_sku_asin': warranty_data.get('model_sku_asin', ''),
                'store': warranty_data.get('store', ''),
                'order_number': warranty_data.get('order_number', ''),
                'order_date': warranty_data.get('order_date', '') or warranty_data.get('packing_slip_date', ''),
                'invoice_number': warranty_data.get('invoice_number', ''),
                'invoice_date': warranty_data.get('packing_slip_date', '') or warranty_data.get('order_date', ''),
                'quantity': warranty_data.get('quantity', ''),
                'specifications': warranty_data.get('specifications', ''),
                'seller_name': warranty_data.get('seller_name', ''),
                'seller_address': warranty_data.get('seller_address', ''),
                'warranty_period': warranty_data.get('warranty_period', 'N/A'),
                'warranty_terms': warranty_data.get('warranty_terms', 'N/A'),
            }
            
            # Map legacy fields for consistency
            if invoice_response.get('order_date'):
                invoice_response['purchase_date'] = invoice_response.get('order_date', '')
            
            # Return invoice format with warranty file (PDF or image) for download/view
            print(f"📄 Returning warranty file: type={warranty_file_type}, base64 length={len(warranty_file_base64) if warranty_file_base64 else 0} chars")
            print(f"📦 Response structure: invoice={bool(invoice_response)}, warranty_file_base64={bool(warranty_file_base64)}")
            
            return {
                "success": True,
                "invoice": invoice_response,
                "warranty_file_base64": warranty_file_base64,  # Return original PDF or image
                "warranty_file_type": warranty_file_type,  # "pdf" or "image"
                "message": f"Extracted from {'PDF' if request.file_type == 'pdf' else 'image'} warranty slip" + (" (merged with invoice data)" if has_invoice_data else "")
            }
        else:
            # Log the full response for debugging
            print(f"❌ Validation failed - product_name: '{product_name}', order_number: '{order_number}', model_sku: '{model_sku}'")
            print(f"❌ Full warranty_data: {warranty_data}")
            # Still return the file even if extraction failed
            return {
                "success": False,
                "invoice": {},
                "warranty_file_base64": warranty_file_base64,  # Always return original file
                "warranty_file_type": warranty_file_type,
                "message": f"Could not extract product information from warranty slip. Extracted fields: {list(warranty_data.keys())}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Warranty extraction error: {str(e)}")
        import traceback
        traceback.print_exc()
        # Try to return the file even if extraction failed
        try:
            file_to_return = warranty_file_base64 if 'warranty_file_base64' in locals() and warranty_file_base64 else request.image_base64
            file_type_to_return = warranty_file_type if 'warranty_file_type' in locals() and warranty_file_type else request.file_type
            return {
                "success": False,
                "invoice": {},
                "warranty_file_base64": file_to_return,
                "warranty_file_type": file_type_to_return,
                "message": f"Extraction failed: {str(e)}"
            }
        except:
            # If we can't return file, raise the original error
            raise HTTPException(
                status_code=500,
                detail=f"Warranty extraction failed: {str(e)}"
        )


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


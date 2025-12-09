"""
Gemini Vision API integration for product identification from images
"""

import os
import google.generativeai as genai
from typing import Dict, Optional
import httpx
import base64
from io import BytesIO
from PIL import Image


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

if not GEMINI_API_KEYS:
    raise ValueError(
        "GEMINI_API_KEY environment variable is required. "
        "Set it using: export GEMINI_API_KEY='your-api-key'"
    )

# Configure Gemini with primary key
genai.configure(api_key=GEMINI_API_KEYS[current_key_index])


def identify_product_from_image(image_url: str) -> Optional[Dict]:
    """
    Identify product from image URL using Gemini Vision API
    """
    try:
        print(f"🖼️  Identifying product from image URL: {image_url[:80]}")
        
        # Download image
        response = httpx.get(image_url, timeout=10.0)
        response.raise_for_status()
        
        # Open image
        image = Image.open(BytesIO(response.content))
        
        # Use Gemini Vision
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = """Analyze this product image and identify:
1. Product name/brand
2. Model number (if visible)
3. Key features/specifications

Respond in JSON format:
{
    "brand": "Brand Name",
    "product_name": "Product Name",
    "model": "Model Number",
    "specifications": ["spec1", "spec2"]
}"""
        
        response = model.generate_content([prompt, image])
        result_text = response.text.strip()
        
        # Parse JSON from response
        import json
        import re
        
        # Extract JSON from markdown code block if present
        match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', result_text)
        if match:
            result_text = match.group(1)
        
        # Try to find JSON object
        json_start = result_text.find('{')
        if json_start != -1:
            json_text = result_text[json_start:]
            json_end = json_text.rfind('}') + 1
            if json_end > 0:
                json_text = json_text[:json_end]
                # Wrap json.loads in try-except to allow fallback dict on malformed JSON
                try:
                    product_info = json.loads(json_text)
                    return product_info
                except json.JSONDecodeError as json_error:
                    print(f"⚠️  JSON parse error: {str(json_error)}, using fallback")
                    # Fall through to fallback dict below
        
        # Fallback: return basic info
        return {
            "brand": "Unknown",
            "product_name": "Product from image",
            "model": "",
            "specifications": []
        }
        
    except Exception as e:
        print(f"❌ Error identifying product from image: {str(e)}")
        return None


def identify_product_from_image_base64(image_base64: str) -> Optional[Dict]:
    """
    Identify product from base64 encoded image using Gemini Vision API
    """
    try:
        print(f"🖼️  Identifying product from base64 image")
        
        # Decode base64 image
        image_data = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_data))
        
        # Use Gemini Vision
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = """Analyze this product image and identify:
1. Product name/brand
2. Model number (if visible)
3. Key features/specifications

Respond in JSON format:
{
    "brand": "Brand Name",
    "product_name": "Product Name",
    "model": "Model Number",
    "specifications": ["spec1", "spec2"]
}"""
        
        response = model.generate_content([prompt, image])
        result_text = response.text.strip()
        
        # Parse JSON from response
        import json
        import re
        
        # Extract JSON from markdown code block if present
        match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', result_text)
        if match:
            result_text = match.group(1)
        
        # Try to find JSON object
        json_start = result_text.find('{')
        if json_start != -1:
            json_text = result_text[json_start:]
            json_end = json_text.rfind('}') + 1
            if json_end > 0:
                json_text = json_text[:json_end]
                # Wrap json.loads in try-except to allow fallback dict on malformed JSON
                try:
                    product_info = json.loads(json_text)
                    return product_info
                except json.JSONDecodeError as json_error:
                    print(f"⚠️  JSON parse error: {str(json_error)}, using fallback")
                    # Fall through to fallback dict below
        
        # Fallback: return basic info
        return {
            "brand": "Unknown",
            "product_name": "Product from image",
            "model": "",
            "specifications": []
        }
        
    except Exception as e:
        print(f"❌ Error identifying product from base64 image: {str(e)}")
        return None


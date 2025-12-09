import { GoogleGenerativeAI, HarmCategory, HarmBlockThreshold } from '@google/generative-ai';
import type { Product, RecommendationResponse } from '../types';

// Gemini API Configuration - Read from environment variable
const GEMINI_API_KEY = process.env.EXPO_PUBLIC_GEMINI_API_KEY;

if (!GEMINI_API_KEY) {
  console.error('❌ EXPO_PUBLIC_GEMINI_API_KEY not found in environment!');
  throw new Error('Gemini API key is required. Please set EXPO_PUBLIC_GEMINI_API_KEY in .env file');
}

console.log('✅ Gemini API key loaded from environment');
let genAI = new GoogleGenerativeAI(GEMINI_API_KEY);

/**
 * Extract JSON from AI response
 */
function extractJSON(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    // Try to extract from markdown code blocks
    const match = text.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (match) {
      return JSON.parse(match[1].trim());
    }
    
    // Try to find JSON object
    const jsonStart = text.indexOf('{');
    const jsonEnd = text.lastIndexOf('}');
    if (jsonStart !== -1 && jsonEnd !== -1) {
      return JSON.parse(text.substring(jsonStart, jsonEnd + 1));
    }
    
    throw new Error('Could not extract JSON from response');
  }
}

/**
 * Detect category from URL
 */
function detectCategory(url: string): string {
  const urlLower = url.toLowerCase();
  if (urlLower.includes('laptop') || urlLower.includes('notebook')) return 'laptop';
  if (urlLower.includes('keyboard')) return 'keyboard';
  if (urlLower.includes('mouse')) return 'mouse';
  if (urlLower.includes('phone') || urlLower.includes('mobile')) return 'smartphone';
  if (urlLower.includes('tablet') || urlLower.includes('ipad')) return 'tablet';
  if (urlLower.includes('speaker') || urlLower.includes('soundbar')) return 'speaker';
  if (urlLower.includes('earbuds') || urlLower.includes('headphones') || urlLower.includes('earphones')) return 'earbuds';
  if (urlLower.includes('watch')) return 'smartwatch';
  if (urlLower.includes('monitor') || urlLower.includes('display')) return 'monitor';
  return 'product';
}

/**
 * Build prompt for Gemini with category enforcement
 */
function buildPrompt(url: string): string {
  const category = detectCategory(url);
  
  return `Find 3 similar ${category}s for: ${url}

Return ONLY JSON (must include ${category}s only):
{
  "category": "${category}",
  "alternatives": [
    {"id": "1", "brand": "Brand", "model": "Model", "title": "Title", "image_url": "", "price_estimate": "₹0", "price_raw": 0, "rating_estimate": 4.0, "rating_count_estimate": 1000, "specs": ["spec1"], "connectivity": [], "why_pick": "reason", "tradeoffs": "cons", "search_query": "brand model", "source_site": "amazon"}
  ]
}`;
}

/**
 * Retry helper with exponential backoff and API key fallback
 */
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error: any) {
      const is503 = error?.message?.includes('503') || error?.message?.includes('overloaded');
      const isQuotaError = error?.message?.includes('quota') || error?.message?.includes('429');
      const isLastAttempt = attempt === maxRetries - 1;
      
      // Try backup API key if quota/rate limit error
      if (isQuotaError && currentKeyIndex < GEMINI_API_KEYS.length - 1) {
        currentKeyIndex++;
        genAI = new GoogleGenerativeAI(GEMINI_API_KEYS[currentKeyIndex]);
        console.log(`🔄 Switching to backup API key ${currentKeyIndex + 1}/${GEMINI_API_KEYS.length}...`);
        continue; // Retry immediately with new key
      }
      
      if (!is503 || isLastAttempt) {
        throw error;
      }
      
      const delay = baseDelay * Math.pow(2, attempt);
      console.log(`⚠️ Gemini overloaded (503), retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw new Error('Max retries reached');
}

/**
 * Get product recommendations using Gemini AI
 */
export async function getRecommendationsFromGemini(
  url: string
): Promise<RecommendationResponse> {
  console.log('🤖 Calling Gemini AI...');
  const startTime = Date.now();

  try {
    const model = genAI.getGenerativeModel({
      model: 'gemini-2.5-flash',  // Only this model works!
      generationConfig: {
        temperature: 0.5,
        topP: 0.95,
        topK: 40,
        maxOutputTokens: 400000, // Higher for mobile (works better with thinking tokens)
      },
      safetySettings: [
        {
          category: HarmCategory.HARM_CATEGORY_HARASSMENT,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
        {
          category: HarmCategory.HARM_CATEGORY_HATE_SPEECH,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
        {
          category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
        {
          category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
          threshold: HarmBlockThreshold.BLOCK_NONE,
        },
      ],
    });

    const prompt = buildPrompt(url);
    console.log('📤 Sending prompt to Gemini...');
    
    // Retry with exponential backoff for 503 errors
    const result = await retryWithBackoff(
      () => model.generateContent(prompt),
      3,  // 3 retries
      2000  // 2s base delay (2s, 4s, 8s)
    );
    
    // Check if response was blocked
    if (!result.response || !result.response.candidates || result.response.candidates.length === 0) {
      console.error('❌ No candidates returned from Gemini');
      throw new Error('Gemini API: No response candidates returned (likely blocked by safety filter)');
    }
    
    const candidate = result.response.candidates[0];
    console.log('📥 Got response from Gemini, finish reason:', candidate.finishReason);
    
    // Check if blocked by safety
    if (candidate.finishReason === 'SAFETY') {
      console.error('❌ Response blocked by safety filter');
      throw new Error('Gemini API: Response blocked by safety filter');
    }
    
    // Get text content - handle MAX_TOKENS case properly
    let response: string = '';
    
    console.log('🔍 Extracting text from response...');
    console.log('📊 Finish reason:', candidate.finishReason);
    
    // Method 1: Try to get text from parts first (most reliable)
    if (candidate.content?.parts) {
      console.log('📊 Has parts:', candidate.content.parts.length);
      const textParts: string[] = [];
      for (const part of candidate.content.parts) {
        if (part.text) {
          textParts.push(part.text);
          console.log('📝 Part text length:', part.text.length);
        }
      }
      if (textParts.length > 0) {
        response = textParts.join('');
        console.log('✅ Extracted text from parts:', response.length, 'chars');
        console.log('📝 First 200 chars:', response.substring(0, 200));
      }
    }
    
    // Method 2: Fallback to response.text() if parts didn't work
    if (!response || response.trim().length === 0) {
      console.log('⚠️ No text from parts, trying response.text()...');
      try {
        response = result.response.text();
        console.log('✅ Got text via response.text():', response.length, 'chars');
        console.log('📝 First 200 chars:', response.substring(0, 200));
      } catch (textError) {
        console.error('❌ Failed to get text from response:', textError);
        console.log('📊 Error type:', typeof textError);
        console.log('📊 Error details:', JSON.stringify(textError));
        
        // Check if this is MAX_TOKENS with empty response
        if (candidate.finishReason === 'MAX_TOKENS') {
          console.error('❌ MAX_TOKENS hit with no text - this should not happen with 2000 tokens!');
          throw new Error('Gemini API: Response hit token limit with no text. Please report this issue.');
        }
        throw new Error('Gemini API: Failed to extract text from response');
      }
    }
    
    if (!response || response.trim().length === 0) {
      console.error('❌ Empty response from Gemini');
      console.log('📊 Finish reason was:', candidate.finishReason);
      console.log('📊 Has content?', !!candidate.content);
      console.log('📊 Has parts?', !!candidate.content?.parts);
      throw new Error('Gemini API: Empty response received');
    }

    const elapsedTime = ((Date.now() - startTime) / 1000).toFixed(2);
    console.log(`✅ Gemini responded in ${elapsedTime}s`);

    // Parse JSON
    console.log('🔍 Attempting to parse JSON...');
    const data = extractJSON(response);
    console.log('✅ JSON parsed successfully');
    
    // Validate we have alternatives
    if (!data.alternatives || data.alternatives.length === 0) {
      throw new Error('No alternatives found in AI response');
    }

    // Log category for validation
    if (data.category) {
      console.log(`✅ Product category: ${data.category}`);
    }

    // Build response with BROAD category search URLs that will ALWAYS work
    const category = data.category || 'products';
    
    const alternatives: Product[] = data.alternatives.map((alt: any, index: number) => {
      const brand = alt.brand || 'Unknown';
      const model = alt.model || '';
      const sourceSite = alt.source_site || 'amazon';
      
      // Use BROAD category + brand search (more reliable than specific products)
      // Example: "luggage bags Safari" instead of "Safari Pentagon Hardside 123"
      const broadSearch = `${category} ${brand}`.trim();
      
      // Construct working search URL with broad terms
      let searchUrl: string;
      if (sourceSite === 'flipkart') {
        const query = encodeURIComponent(broadSearch);
        searchUrl = `https://www.flipkart.com/search?q=${query}&sort=relevance`;
      } else {
        const query = encodeURIComponent(broadSearch);
        searchUrl = `https://www.amazon.in/s?k=${query}&sort=relevance`;
      }
      
      console.log(`🔗 ${brand}: ${searchUrl}`);
      
      const placeholderUrl = `https://via.placeholder.com/400x400/3B82F6/FFFFFF?text=${encodeURIComponent(brand)}`;
      
      return {
        id: alt.id || `alt${index + 1}`,
        brand,
        model,
        title: alt.title || 'Unknown Product',
        image_url: alt.image_url || placeholderUrl,
        price_estimate: alt.price_estimate || '₹0',
        price_raw: alt.price_raw || 0,
        rating_estimate: alt.rating_estimate,
        rating_count_estimate: alt.rating_count_estimate,
        specs: alt.specs || [],
        connectivity: alt.connectivity || [],
        why_pick: alt.why_pick || 'Good alternative product',
        tradeoffs: alt.tradeoffs || 'None specified',
        source_url: searchUrl,
        source_site: sourceSite,
      };
    });

    // Ensure exactly 3 alternatives
    const validAlternatives = alternatives.slice(0, 3);
    const warnings = validAlternatives.length < 3 
      ? [`Only ${validAlternatives.length} alternatives found`]
      : [];

    return {
      source: url.includes('amazon') ? 'amazon' : url.includes('flipkart') ? 'flipkart' : 'unknown',
      canonical_url: url,
      query_time_iso: new Date().toISOString(),
      category: data.category || 'Unknown Category',
      alternatives: validAlternatives,
      meta: {
        validation: {
          llm_valid_json: true,
          image_urls_checked: false, // Not checking URLs in direct mode
        },
        warnings,
      },
    };
  } catch (error) {
    console.error('❌ Gemini API Error:', error);
    throw new Error(
      error instanceof Error 
        ? error.message 
        : 'Failed to get recommendations from AI'
    );
  }
}


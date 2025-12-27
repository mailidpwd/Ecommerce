/**
 * API Service - Smart Mode with Auto-Fallback
 * 
 * 🚀 Tries backend first (real scraped data), falls back to direct Gemini (fast)
 * 
 * Backend must be running: py main.py (in backend/ folder)
 * Update BACKEND_URL if your IP changes
 */

import { Platform } from 'react-native';
import type { RecommendationResponse } from '../types';
import { getRecommendationsFromGemini } from './geminiService';

// ⚠️ Backend running on computer - use IP address for phone access
const BACKEND_URL = 'http://10.247.204.10:8000';
const BACKEND_TIMEOUT = 120000; // 120 seconds (2 min) - allows Gemini to enhance each product

/**
 * Fetch with timeout helper
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout: number = BACKEND_TIMEOUT
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout - backend is taking too long');
    }
    throw error;
  }
}

/**
 * Get recommendations - Smart Mode: Backend first, Gemini fallback
 * 
 * 1. Try backend (real scraped data with ScraperAPI) - BEST QUALITY
 * 2. Fallback to direct Gemini if backend fails - FAST BACKUP
 */
export async function getRecommendations(
  url: string,
  refresh: boolean = false,
  shareText?: string
): Promise<RecommendationResponse> {
  // Try backend first (real scraped data)
  try {
    console.log('🚀 Trying backend first (real scraped data)...');
    if (shareText) {
      console.log('⚡ Sending share text - backend will skip scraping!');
    }
    
    const response = await fetchWithTimeout(`${BACKEND_URL}/recommend`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url,
        device: Platform.OS === 'ios' ? 'ios' : 'android',
        refresh,
        share_text: shareText || null, // Send share text if available
      }),
    });

    if (response.ok) {
      try {
      const data = await response.json();
        
        // Validate response structure
        if (!data || !data.alternatives || !Array.isArray(data.alternatives)) {
          throw new Error('Invalid response structure from backend');
        }
        
      console.log('✅ Backend success:', data.alternatives.length, 'alternatives');
      return data;
      } catch (parseError) {
        console.error('❌ Failed to parse backend response:', parseError);
        throw new Error(`Backend returned invalid JSON: ${parseError instanceof Error ? parseError.message : 'Unknown error'}`);
      }
    } else {
      // Backend returned error (503, etc.) - fallback to Gemini
      try {
      const errorText = await response.text();
      console.log('⚠️  Backend error:', response.status, errorText);
        throw new Error(`Backend error: ${response.status} - ${errorText.substring(0, 100)}`);
      } catch (textError) {
        console.error('❌ Failed to read error text:', textError);
      throw new Error(`Backend error: ${response.status}`);
      }
    }
  } catch (error) {
    console.log('⚠️  Backend unavailable, falling back to direct Gemini...');
    console.error('Backend error:', error);
    
    // Fallback to direct Gemini
    try {
      const result = await getRecommendationsFromGemini(url);
      console.log('✅ Gemini fallback success:', result.alternatives.length, 'alternatives');
      return result;
    } catch (geminiError) {
      console.error('❌ Gemini fallback also failed:', geminiError);
      throw new Error(
        geminiError instanceof Error
          ? `Both backend and Gemini failed. Gemini error: ${geminiError.message}`
          : 'Failed to get recommendations from both backend and Gemini'
      );
    }
  }
}

/**
 * Refresh prices
 */
export async function refreshPrices(url: string): Promise<RecommendationResponse> {
  return getRecommendations(url, true);
}

/**
 * Health check - tries backend, always returns true (fallback available)
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetchWithTimeout(`${BACKEND_URL}/health`, {
      method: 'GET',
    }, 5000);
    return response.ok;
  } catch {
    // Backend not available, but we have Gemini fallback, so still "healthy"
    return true;
  }
}

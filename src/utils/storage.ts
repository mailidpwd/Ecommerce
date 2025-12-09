import AsyncStorage from '@react-native-async-storage/async-storage';
import type { CachedResult, RecommendationResponse } from '../types';

const CACHE_KEY_PREFIX = '@decision_rec_cache:';
const RECENT_URLS_KEY = '@decision_rec_recent';
const MAX_RECENT = 10;
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

/**
 * Save recommendation result to cache
 */
export async function cacheResult(
  url: string,
  data: RecommendationResponse
): Promise<void> {
  const cacheEntry: CachedResult = {
    url,
    data,
    timestamp: Date.now(),
  };

  try {
    await AsyncStorage.setItem(
      CACHE_KEY_PREFIX + url,
      JSON.stringify(cacheEntry)
    );
    await addToRecentUrls(url);
  } catch (error) {
    console.error('Failed to cache result:', error);
  }
}

/**
 * Get cached result if not expired
 */
export async function getCachedResult(
  url: string
): Promise<RecommendationResponse | null> {
  try {
    const cached = await AsyncStorage.getItem(CACHE_KEY_PREFIX + url);
    if (!cached) return null;

    const cacheEntry: CachedResult = JSON.parse(cached);
    
    // Check if expired
    if (Date.now() - cacheEntry.timestamp > CACHE_TTL) {
      return null;
    }

    return cacheEntry.data;
  } catch (error) {
    console.error('Failed to get cached result:', error);
    return null;
  }
}

/**
 * Add URL to recent searches
 */
async function addToRecentUrls(url: string): Promise<void> {
  try {
    const recentJson = await AsyncStorage.getItem(RECENT_URLS_KEY);
    const recent: string[] = recentJson ? JSON.parse(recentJson) : [];

    // Remove if already exists
    const filtered = recent.filter((u) => u !== url);
    
    // Add to beginning
    const updated = [url, ...filtered].slice(0, MAX_RECENT);

    await AsyncStorage.setItem(RECENT_URLS_KEY, JSON.stringify(updated));
  } catch (error) {
    console.error('Failed to add to recent URLs:', error);
  }
}

/**
 * Get recent URLs
 */
export async function getRecentUrls(): Promise<string[]> {
  try {
    const recentJson = await AsyncStorage.getItem(RECENT_URLS_KEY);
    return recentJson ? JSON.parse(recentJson) : [];
  } catch (error) {
    console.error('Failed to get recent URLs:', error);
    return [];
  }
}

/**
 * Clear all cached data
 */
export async function clearAllCache(): Promise<void> {
  try {
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter((key) => key.startsWith(CACHE_KEY_PREFIX));
    await AsyncStorage.multiRemove(cacheKeys);
  } catch (error) {
    console.error('Failed to clear cache:', error);
  }
}


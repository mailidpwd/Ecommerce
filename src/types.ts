// TypeScript type definitions for Decision Recommendation App

export interface Product {
  id: string;
  brand: string;
  model: string;
  title: string;
  image_url: string;
  price_estimate: string;
  price_raw: number;
  rating_estimate: number | null;
  rating_count_estimate: number | null;
  specs: string[];
  connectivity: string[];
  why_pick: string;
  tradeoffs: string;
  source_url: string; // Search URL (not direct product URL) to avoid invalid links
  source_site: 'amazon' | 'flipkart' | 'other';
  rdm_score?: number; // RDM score (0-100)
  rdm_breakdown?: {
    price_score: number;
    rating_score: number;
    review_score: number;
    feature_score: number;
    ownership_score: number;
  };
}

export interface RecommendationResponse {
  source: 'amazon' | 'flipkart' | 'unknown';
  canonical_url: string;
  query_time_iso: string;
  category?: string; // Detected product category
  alternatives: Product[];
  meta: {
    validation: {
      llm_valid_json: boolean;
      image_urls_checked: boolean;
    };
    warnings: string[];
  };
}

export interface RecommendRequest {
  url: string;
  device: 'android' | 'ios';
  user_id?: string;
  refresh?: boolean;
}

export interface CachedResult {
  url: string;
  data: RecommendationResponse;
  timestamp: number;
}


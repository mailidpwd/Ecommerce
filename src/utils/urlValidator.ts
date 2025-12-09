/**
 * URL validation utilities
 */

const AMAZON_PATTERN = /^https?:\/\/(www\.)?(amazon\.(in|com|co\.uk|com\.au)|amzn\.(in|to|com))\/.*$/i;
const FLIPKART_PATTERN = /^https?:\/\/(www\.)?flipkart\.com\/.*$/i;

export function isValidProductUrl(url: string): boolean {
  if (!url || url.trim().length === 0) {
    return false;
  }

  try {
    new URL(url);
    return AMAZON_PATTERN.test(url) || FLIPKART_PATTERN.test(url);
  } catch {
    return false;
  }
}

export function getSourceFromUrl(url: string): 'amazon' | 'flipkart' | 'unknown' {
  if (AMAZON_PATTERN.test(url)) {
    return 'amazon';
  }
  if (FLIPKART_PATTERN.test(url)) {
    return 'flipkart';
  }
  return 'unknown';
}

export function formatUrl(url: string): string {
  try {
    const urlObj = new URL(url);
    return urlObj.href;
  } catch {
    return url;
  }
}

/**
 * Extract clean URL from text that may contain product description + URL
 * Example: "Limited-time deal: Product Name https://amzn.in/d/abc123" -> "https://amzn.in/d/abc123"
 */
export function extractUrlFromText(text: string): string {
  if (!text || text.trim().length === 0) {
    return '';
  }

  // Remove extra whitespace and newlines
  const cleanText = text.trim().replace(/\s+/g, ' ');

  // Try to find a URL pattern in the text
  const urlPatterns = [
    // Match https:// or http:// URLs
    /https?:\/\/[^\s]+/i,
    // Match amazon.in or amazon.com URLs (website copy format)
    /amazon\.(in|com|co\.uk|com\.au)\/[^\s]+/i,
    // Match flipkart.com URLs
    /flipkart\.com\/[^\s]+/i,
    // Match amzn.in short links without protocol
    /amzn\.in\/[^\s]+/i,
    // Match www. URLs
    /www\.[^\s]+/i,
  ];

  for (const pattern of urlPatterns) {
    const match = cleanText.match(pattern);
    if (match) {
      let extractedUrl = match[0];
      
      // Add protocol if missing
      if (!extractedUrl.startsWith('http://') && !extractedUrl.startsWith('https://')) {
        extractedUrl = 'https://' + extractedUrl;
      }
      
      // Clean up any trailing punctuation that might have been captured
      extractedUrl = extractedUrl.replace(/[.,;:!?]+$/, '');
      
      return extractedUrl;
    }
  }

  // If no URL pattern found, check if the whole text looks like a URL
  // and add https:// if needed
  if (cleanText.includes('amazon.') || cleanText.includes('flipkart.') || cleanText.includes('amzn.')) {
    if (!cleanText.startsWith('http://') && !cleanText.startsWith('https://')) {
      return 'https://' + cleanText;
    }
  }
  
  return cleanText;
}


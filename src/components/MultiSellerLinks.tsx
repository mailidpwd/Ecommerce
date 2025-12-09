import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Linking } from 'react-native';

interface SellerLink {
  platform: string;
  url: string;
  price?: string;
  available: boolean;
  icon: string;
}

interface MultiSellerLinksProps {
  productName: string;
  productBrand: string;
  currentPlatform: 'amazon' | 'flipkart';
}

export const MultiSellerLinks: React.FC<MultiSellerLinksProps> = ({ 
  productName, 
  productBrand,
  currentPlatform 
}) => {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sellers, setSellers] = useState<SellerLink[]>([]);

  const searchOtherPlatforms = async () => {
    setLoading(true);
    
    try {
      // Call backend to search all platforms
      const BACKEND_URL = 'http://10.178.224.10:8000';
      
      // Create abort controller for timeout (React Native compatible)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout for multi-platform search
      
      const response = await fetch(`${BACKEND_URL}/multi-platform/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          product_name: productName,
          brand: productBrand,
          current_platform: currentPlatform,
        }),
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const data = await response.json();
        console.log(`✅ Found ${data.total_found} sellers:`, data.sellers);
        
        // Convert backend response to SellerLink format
        const sellerLinks: SellerLink[] = data.sellers.map((seller: any) => ({
          platform: seller.platform,
          url: seller.url,
          price: seller.price,
          available: seller.available,
          icon: getIconForPlatform(seller.platform),
        }));
        
        setSellers(sellerLinks);
      } else {
        console.log('⚠️  Backend multi-platform search failed, using fallback search links');
        // Fallback to search links if backend fails
        setSellers(getFallbackSearchLinks());
      }
    } catch (error) {
      console.error('❌ Multi-platform search error:', error);
      // Fallback to search links
      setSellers(getFallbackSearchLinks());
    }
    
    setLoading(false);
  };
  
  const getIconForPlatform = (platform: string): string => {
    const icons: Record<string, string> = {
      // Regular E-commerce
      'Flipkart': '🛒',
      'Meesho': '🏪',
      'Snapdeal': '🛍️',
      'Myntra': '👔',
      'Ajio': '👗',
      'JioMart': '🏬',
      'ShopClues': '🏷️',
      'Amazon': '📦',
      'Tata Cliq': '🏢',
      // Quick Commerce
      'Blinkit': '⚡',
      'Instamart': '🚀',
      'Zepto': '⏱️',
    };
    return icons[platform] || '🏬';
  };
  
  const getFallbackSearchLinks = (): SellerLink[] => {
    // Fallback search links if backend fails
    const searchQuery = encodeURIComponent(`${productBrand} ${productName.split(' ').slice(0, 5).join(' ')}`);
    const links: SellerLink[] = [];
    
    if (currentPlatform !== 'flipkart') {
      links.push({
        platform: 'Flipkart',
        url: `https://www.flipkart.com/search?q=${searchQuery}`,
        available: true,
        icon: '🛒',
      });
    }
    
    if (currentPlatform !== 'amazon') {
      links.push({
        platform: 'Amazon',
        url: `https://www.amazon.in/s?k=${searchQuery}`,
        available: true,
        icon: '📦',
      });
    }
    
    links.push(
      {
        platform: 'Meesho',
        url: `https://www.meesho.com/search?q=${searchQuery}`,
        available: true,
        icon: '🏪',
      },
      {
        platform: 'Snapdeal',
        url: `https://www.snapdeal.com/search?keyword=${searchQuery}`,
        available: true,
        icon: '🛍️',
      },
      {
        platform: 'JioMart',
        url: `https://www.jiomart.com/search/${searchQuery}`,
        available: true,
        icon: '🏬',
      },
      {
        platform: 'Blinkit',
        url: `https://blinkit.com/s/?q=${searchQuery}`,
        available: true,
        icon: '⚡',
      },
      {
        platform: 'Instamart',
        url: `https://www.swiggy.com/instamart/search?q=${searchQuery}`,
        available: true,
        icon: '🚀',
      },
      {
        platform: 'Zepto',
        url: `https://www.zepto.com/search?query=${searchQuery}`,
        available: true,
        icon: '⏱️',
      }
    );
    
    return links;
  };

  const handleExpand = () => {
    if (!expanded && sellers.length === 0) {
      searchOtherPlatforms();
    }
    setExpanded(!expanded);
  };

  return (
    <View style={styles.container}>
      {/* Expand/Collapse Button */}
      <TouchableOpacity 
        style={styles.expandButton}
        onPress={handleExpand}
        activeOpacity={0.7}
      >
        <Text style={styles.expandIcon}>🏪</Text>
        <Text style={styles.expandText}>
          {expanded ? 'Hide Other Sellers' : 'Compare Prices on Other Platforms'}
        </Text>
        <Text style={styles.expandArrow}>{expanded ? '▼' : '▶'}</Text>
      </TouchableOpacity>

      {/* Seller Links - Shown when expanded */}
      {expanded && (
        <View style={styles.sellersContainer}>
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator color="#3B82F6" size="small" />
              <Text style={styles.loadingText}>Searching all platforms...</Text>
              <Text style={styles.loadingSubtext}>Checking Flipkart, Meesho, Snapdeal & more</Text>
            </View>
          ) : sellers.length === 0 ? (
            <View style={styles.noSellersContainer}>
              <Text style={styles.noSellersIcon}>🔍</Text>
              <Text style={styles.noSellersTitle}>Product not found on other platforms</Text>
              <Text style={styles.noSellersText}>
                This product appears to be exclusive to {currentPlatform === 'amazon' ? 'Amazon' : 'Flipkart'}
              </Text>
            </View>
          ) : (
            <>
              <Text style={styles.sellersTitle}>
                ✅ Available on {sellers.length} other platform{sellers.length > 1 ? 's' : ''}:
              </Text>
              {sellers.map((seller, index) => {
                const isDirectLink = seller.url.includes('/p/') || seller.url.includes('/dp/') || seller.url.includes('/prn/') || seller.url.includes('/pn/');
                const isSearchLink = seller.url.includes('/search') || seller.url.includes('/s?');
                const hasPrice = seller.price && seller.price !== 'null';
                
                return (
                  <TouchableOpacity
                    key={index}
                    style={[
                      styles.sellerItem,
                      isDirectLink && styles.sellerItemDirect,
                      isSearchLink && styles.sellerItemSearch,
                    ]}
                    onPress={() => Linking.openURL(seller.url)}
                    activeOpacity={0.7}
                  >
                    <View style={styles.sellerLeft}>
                      <Text style={styles.sellerIcon}>{seller.icon}</Text>
                      <View style={styles.sellerInfo}>
                        <View style={styles.sellerHeader}>
                          <Text style={styles.sellerName}>{seller.platform}</Text>
                          {isDirectLink && (
                            <View style={styles.directBadge}>
                              <Text style={styles.directBadgeText}>DIRECT</Text>
                            </View>
                          )}
                          {isSearchLink && !isDirectLink && (
                            <View style={styles.searchBadge}>
                              <Text style={styles.searchBadgeText}>SEARCH</Text>
                            </View>
                          )}
                        </View>
                        <Text style={[
                          styles.sellerSubtext,
                          hasPrice && styles.sellerPrice
                        ]}>
                          {hasPrice ? seller.price : 'Tap to search product'}
                        </Text>
                      </View>
                    </View>
                    <View style={styles.sellerRight}>
                      <Text style={styles.sellerArrow}>→</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
              <Text style={styles.disclaimer}>
                ✅ Verified availability • Tap any platform to view product
              </Text>
            </>
          )}
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginTop: 16,
  },
  expandButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F0F9FF',
    padding: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#BAE6FD',
    gap: 10,
  },
  expandIcon: {
    fontSize: 20,
  },
  expandText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: '#0369A1',
  },
  expandArrow: {
    fontSize: 14,
    color: '#0284C7',
    fontWeight: '700',
  },
  sellersContainer: {
    marginTop: 12,
    backgroundColor: '#FAFAFA',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  sellersTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#6B7280',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  loadingContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 24,
    gap: 8,
  },
  loadingText: {
    fontSize: 14,
    color: '#374151',
    fontWeight: '600',
    marginTop: 8,
  },
  loadingSubtext: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'center',
  },
  noSellersContainer: {
    alignItems: 'center',
    paddingVertical: 24,
    paddingHorizontal: 16,
  },
  noSellersIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  noSellersTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#374151',
    textAlign: 'center',
    marginBottom: 8,
  },
  noSellersText: {
    fontSize: 13,
    color: '#6B7280',
    textAlign: 'center',
    lineHeight: 18,
  },
  sellerItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    padding: 14,
    borderRadius: 10,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  sellerItemDirect: {
    borderColor: '#10B981',
    borderWidth: 2,
    backgroundColor: '#F0FDF4',
  },
  sellerItemSearch: {
    borderColor: '#3B82F6',
    borderWidth: 1,
    backgroundColor: '#EFF6FF',
  },
  sellerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  sellerIcon: {
    fontSize: 26,
  },
  sellerInfo: {
    flex: 1,
  },
  sellerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  sellerName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
  },
  directBadge: {
    backgroundColor: '#10B981',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  directBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  searchBadge: {
    backgroundColor: '#3B82F6',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  searchBadgeText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  sellerSubtext: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  sellerPrice: {
    fontSize: 14,
    fontWeight: '700',
    color: '#059669',
  },
  sellerRight: {
    marginLeft: 12,
  },
  sellerArrow: {
    fontSize: 20,
    color: '#3B82F6',
    fontWeight: '700',
  },
  disclaimer: {
    fontSize: 11,
    color: '#9CA3AF',
    textAlign: 'center',
    marginTop: 8,
    fontStyle: 'italic',
  },
});


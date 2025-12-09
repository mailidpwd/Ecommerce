import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Linking, Image, Modal } from 'react-native';
import type { Product } from '../types';
import { MultiSellerLinks } from './MultiSellerLinks';

interface ProductCardProps {
  product: Product;
  index: number;
}

export const ProductCard: React.FC<ProductCardProps> = ({ product, index }) => {
  const [imageError, setImageError] = useState(false);
  const [showMoreSellers, setShowMoreSellers] = useState(false);
  const [showUrl, setShowUrl] = useState(false); // Hide URL by default
  const [showRdmInfo, setShowRdmInfo] = useState(false); // Show RDM breakdown
  
  // Check if URL is a direct product page (not a search page)
  const isDirectProductLink = product.source_url.includes('/dp/') || 
                               product.source_url.includes('/gp/product/') ||
                               product.source_url.includes('/p/');
  
  const handlePress = () => {
    Linking.openURL(product.source_url);
  };
  
  // Determine button text and helper text based on link type
  const getButtonText = () => {
    if (isDirectProductLink) {
      return `🛒 View ${product.brand} on ${product.source_site === 'amazon' ? 'Amazon.in' : 'Flipkart'}`;
    }
    return `🔍 Browse ${product.brand} on ${product.source_site === 'amazon' ? 'Amazon.in' : 'Flipkart'}`;
  };
  
  const getHelperText = () => {
    if (isDirectProductLink) {
      return 'Opens product page • View details & buy';
    }
    return 'Opens category search • Find similar products';
  };

  // Generate search URLs for other platforms
  const generateOtherSellerLinks = () => {
    const searchQuery = encodeURIComponent(
      `${product.brand} ${product.model || product.title.split(' ').slice(0, 5).join(' ')}`
    );
    
    return [
      {
        name: 'Flipkart',
        icon: '🛒',
        url: `https://www.flipkart.com/search?q=${searchQuery}`,
        color: '#FFD700',
      },
      {
        name: 'Meesho',
        icon: '🛍️',
        url: `https://www.meesho.com/search?q=${searchQuery}`,
        color: '#E91E63',
      },
      {
        name: 'Snapdeal',
        icon: '📦',
        url: `https://www.snapdeal.com/search?keyword=${searchQuery}`,
        color: '#FF6B6B',
      },
    ];
  };

  return (
    <View style={styles.card}>
      {/* Rank Badge */}
      <View style={styles.rankBadge}>
        <Text style={styles.rankText}>#{index + 1}</Text>
      </View>

      {/* Product Image */}
      {!imageError && product.image_url && product.image_url.length > 0 ? (
        <Image
          source={{ uri: product.image_url }}
          style={styles.image}
          resizeMode="contain"
          onError={() => setImageError(true)}
        />
      ) : (
        <View style={[styles.image, styles.imageFallback]}>
          <Text style={styles.imageFallbackEmoji}>📦</Text>
          <Text style={styles.imageFallbackBrand}>{product.brand}</Text>
          <Text style={styles.imageFallbackSubtext}>
            {product.source_site === 'amazon' ? 'Amazon.in' : 'Flipkart'}
          </Text>
        </View>
      )}

      {/* Product Info */}
      <View style={styles.content}>
        <Text style={styles.brand}>{product.brand}</Text>
        <Text style={styles.title} numberOfLines={2}>
          {product.title}
        </Text>

        {/* Price & Rating */}
        <View style={styles.priceRow}>
          <Text style={styles.price}>{product.price_estimate}</Text>
          {product.rating_estimate && (
            <View style={styles.ratingContainer}>
              <Text style={styles.rating}>
                ★ {product.rating_estimate.toFixed(1)}
              </Text>
              {product.rating_count_estimate && (
                <Text style={styles.ratingCount}>
                  ({product.rating_count_estimate})
                </Text>
              )}
            </View>
          )}
        </View>

        {/* RDM Score */}
        {product.rdm_score !== undefined && product.rdm_score !== null && (
          <View style={{ gap: 4 }}>
            <TouchableOpacity
              style={styles.rdmContainer}
              onPress={() => setShowRdmInfo(true)}
              activeOpacity={0.8}
            >
              <Text style={styles.rdmLabel}>RDM Score</Text>
              <Text style={styles.rdmValue}>{product.rdm_score.toFixed(1)}</Text>
              <Text style={styles.rdmSubtext}>Value · Trust · Fit</Text>
            </TouchableOpacity>
            <Text style={styles.rdmHint}>Tap to see how we calculated this score</Text>
          </View>
        )}

        {/* Specs - Show all available specs */}
        <View style={styles.specsContainer}>
          <Text style={styles.specsLabel}>Specifications:</Text>
          {product.specs.map((spec, i) => (
            <Text key={i} style={styles.spec}>
              • {spec}
            </Text>
          ))}
        </View>

        {/* Why Pick */}
        <View style={styles.whyPickContainer}>
          <Text style={styles.whyPickLabel}>Why pick this:</Text>
          <Text style={styles.whyPickText}>{product.why_pick}</Text>
        </View>

        {/* Tradeoffs */}
        {product.tradeoffs && (
          <View style={styles.tradeoffsContainer}>
            <Text style={styles.tradeoffsLabel}>Tradeoffs:</Text>
            <Text style={styles.tradeoffsText}>{product.tradeoffs}</Text>
          </View>
        )}

        {/* Product URL (collapsible to save space) */}
        <TouchableOpacity 
          style={styles.urlToggle}
          onPress={() => setShowUrl(!showUrl)}
          activeOpacity={0.7}
        >
          <Text style={styles.urlToggleText}>
            {showUrl ? '▼' : '▶'} {showUrl ? 'Hide' : 'Show'} Product URL
          </Text>
        </TouchableOpacity>
        
        {showUrl && (
          <View style={styles.urlContainer}>
            <Text style={styles.urlText} numberOfLines={3} selectable>
              {product.source_url}
            </Text>
          </View>
        )}

        {/* View Product Button */}
        <TouchableOpacity style={styles.button} onPress={handlePress}>
          <Text style={styles.buttonText}>
            {getButtonText()}
          </Text>
        </TouchableOpacity>
        
        {/* Helper text */}
        <Text style={styles.helperText}>
          {getHelperText()}
        </Text>

        {/* Multi-Seller Links - Lazy loaded price comparison */}
        <MultiSellerLinks 
          productName={product.title}
          productBrand={product.brand}
          currentPlatform={product.source_site}
        />

        {/* RDM Breakdown Modal */}
        <Modal
          visible={showRdmInfo}
          transparent
          animationType="fade"
          onRequestClose={() => setShowRdmInfo(false)}
        >
          <View style={styles.modalBackdrop}>
            <View style={styles.modalCard}>
              <Text style={styles.modalTitle}>RDM Score Breakdown</Text>
              <Text style={styles.modalScore}>{product.rdm_score?.toFixed(1) ?? '—'}</Text>
              <Text style={styles.modalSubtitle}>Value · Trust · Fit</Text>

              {product.rdm_breakdown ? (
                <View style={styles.breakdownList}>
                  <Text style={styles.breakdownItem}>PriceScore: {product.rdm_breakdown.price_score.toFixed(1)}</Text>
                  <Text style={styles.breakdownItem}>RatingScore: {product.rdm_breakdown.rating_score.toFixed(1)}</Text>
                  <Text style={styles.breakdownItem}>ReviewScore: {product.rdm_breakdown.review_score.toFixed(1)}</Text>
                  <Text style={styles.breakdownItem}>FeatureScore: {product.rdm_breakdown.feature_score.toFixed(1)}</Text>
                  <Text style={styles.breakdownItem}>OwnershipScore: {product.rdm_breakdown.ownership_score.toFixed(1)}</Text>
                </View>
              ) : (
                <Text style={styles.breakdownItem}>Breakdown unavailable for this item.</Text>
              )}

              <Text style={styles.modalNote}>
                RDM = 0.25 Price + 0.25 Rating + 0.20 Reviews + 0.20 Features + 0.10 Ownership
              </Text>

              <TouchableOpacity style={styles.modalButton} onPress={() => setShowRdmInfo(false)}>
                <Text style={styles.modalButtonText}>Close</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    marginHorizontal: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  rankBadge: {
    position: 'absolute',
    top: 16,
    right: 16,
    backgroundColor: '#3B82F6',
    borderRadius: 16,
    width: 32,
    height: 32,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 1,
  },
  rankText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  image: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    backgroundColor: '#F3F4F6',
    marginBottom: 12,
  },
  imageFallback: {
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#EFF6FF',
    borderWidth: 2,
    borderColor: '#BFDBFE',
    borderStyle: 'dashed',
  },
  imageFallbackEmoji: {
    fontSize: 56,
    marginBottom: 12,
  },
  imageFallbackBrand: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#1E40AF',
    marginBottom: 4,
    textAlign: 'center',
  },
  imageFallbackSubtext: {
    fontSize: 11,
    color: '#6B7280',
    fontWeight: '600',
  },
  content: {
    gap: 8,
  },
  brand: {
    fontSize: 12,
    color: '#6B7280',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  title: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#111827',
    lineHeight: 22,
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
  },
  price: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#10B981',
  },
  rdmContainer: {
    marginTop: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: '#ECFDF3',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#D1FAE5',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  rdmLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#065F46',
  },
  rdmValue: {
    fontSize: 18,
    fontWeight: '900',
    color: '#047857',
  },
  rdmSubtext: {
    fontSize: 11,
    color: '#047857',
    fontWeight: '600',
  },
  rdmHint: {
    fontSize: 11,
    color: '#6B7280',
  },
  ratingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  rating: {
    fontSize: 14,
    fontWeight: '600',
    color: '#F59E0B',
  },
  ratingCount: {
    fontSize: 12,
    color: '#6B7280',
  },
  specsContainer: {
    marginTop: 8,
    gap: 4,
  },
  specsLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  spec: {
    fontSize: 12,
    color: '#374151',
    lineHeight: 18,
  },
  whyPickContainer: {
    marginTop: 12,
    padding: 12,
    backgroundColor: '#EFF6FF',
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#3B82F6',
  },
  whyPickLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1E40AF',
    marginBottom: 4,
  },
  whyPickText: {
    fontSize: 13,
    color: '#1E3A8A',
    lineHeight: 18,
  },
  tradeoffsContainer: {
    marginTop: 8,
    padding: 12,
    backgroundColor: '#FEF3C7',
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#F59E0B',
  },
  tradeoffsLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#92400E',
    marginBottom: 4,
  },
  tradeoffsText: {
    fontSize: 13,
    color: '#78350F',
    lineHeight: 18,
  },
  urlToggle: {
    marginTop: 12,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  urlToggleText: {
    fontSize: 12,
    color: '#6B7280',
    fontWeight: '500',
  },
  urlContainer: {
    marginTop: 6,
    padding: 10,
    backgroundColor: '#F0F9FF',
    borderRadius: 6,
    borderLeftWidth: 3,
    borderLeftColor: '#3B82F6',
  },
  urlLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  urlText: {
    fontSize: 11,
    color: '#374151',
    fontFamily: 'monospace',
  },
  button: {
    marginTop: 16,
    backgroundColor: '#3B82F6',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  helperText: {
    fontSize: 11,
    color: '#9CA3AF',
    textAlign: 'center',
    marginTop: 8,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalCard: {
    width: '100%',
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    gap: 8,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#111827',
  },
  modalScore: {
    fontSize: 28,
    fontWeight: '900',
    color: '#047857',
  },
  modalSubtitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#065F46',
  },
  breakdownList: {
    marginTop: 8,
    gap: 4,
  },
  breakdownItem: {
    fontSize: 14,
    color: '#374151',
  },
  modalNote: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 6,
  },
  modalButton: {
    marginTop: 12,
    backgroundColor: '#3B82F6',
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: 'center',
  },
  modalButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
});


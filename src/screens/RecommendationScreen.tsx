import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  RefreshControl,
  FlatList,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { useQuery } from '@tanstack/react-query';
import { ProductCard } from '../components/ProductCard';
import { ComparisonTable } from '../components/ComparisonTable';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { ErrorCard } from '../components/ErrorCard';
import { getRecommendations } from '../services/api';
import { cacheResult, getCachedResult } from '../utils/storage';
import type { RootStackParamList } from '../navigation/types';

type RecommendationRouteProp = RouteProp<RootStackParamList, 'Recommendation'>;

const { width: screenWidth } = Dimensions.get('window');

export const RecommendationScreen: React.FC = () => {
  const route = useRoute<RecommendationRouteProp>();
  const navigation = useNavigation();
  const { url, shareText } = route.params;
  const [activeIndex, setActiveIndex] = useState(0);

  const {
    data,
    isLoading,
    error,
    refetch,
    isRefetching,
  } = useQuery({
    // Include shareText in cache key to prevent wrong cached results
    queryKey: ['recommendations', url, shareText || ''],
    queryFn: async () => {
      // If shareText is provided, always fetch fresh (don't use cache)
      // This ensures we get correct results for the NEW product
      if (shareText) {
        console.log('🔍 ShareText provided - fetching FRESH data (no cache)');
        console.log('⚡ Product from shareText - will skip scraping!');
        const result = await getRecommendations(url, false, shareText);
        
        // Cache the fresh result
        await cacheResult(url, result);
        
        return result;
      }

      // Only use cache if NO shareText (manual URL entry)
      const cached = await getCachedResult(url);
      if (cached) {
        console.log('✅ Using cached result (no shareText provided)');
        return cached;
      }

      // Fetch fresh data
      console.log('🔍 Fetching fresh recommendations...');
      const result = await getRecommendations(url, false);
      
      // Cache the result
      await cacheResult(url, result);
      
      return result;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: 1,
  });

  if (isLoading) {
    return <LoadingSkeleton message="Analyzing product..." />;
  }

  if (error) {
    return (
      <ErrorCard
        message={(error as Error).message || 'Failed to load recommendations'}
        onRetry={() => refetch()}
      />
    );
  }

  if (!data || data.alternatives.length === 0) {
    return (
      <ErrorCard
        message="No alternatives found for this product"
        onRetry={() => navigation.goBack()}
      />
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={isRefetching} onRefresh={() => refetch()} />
      }
    >
      {/* Header Info */}
      <View style={styles.headerCard}>
        {data.category && (
          <View style={styles.categoryBadge}>
            <Text style={styles.categoryText}>📦 {data.category}</Text>
          </View>
        )}
        <Text style={styles.sourceText}>Source: {data.source}</Text>
        <Text style={styles.urlText} numberOfLines={1}>
          {data.canonical_url}
        </Text>
        {data.meta.warnings.length > 0 && (
          <View style={styles.warningBadge}>
            <Text style={styles.warningText}>
              ⚠️ Limited data available
            </Text>
          </View>
        )}
      </View>

      {/* Success Banner */}
      <View style={styles.successBanner}>
        <Text style={styles.successIcon}>✓</Text>
        <View style={styles.successContent}>
          <Text style={styles.successTitle}>Analysis Complete</Text>
          <Text style={styles.successSubtitle}>
            Found {data.alternatives.length} verified alternatives
          </Text>
        </View>
      </View>

      {/* Carousel Section */}
      <View style={styles.carouselSection}>
        <Text style={styles.sectionTitle}>Product Alternatives</Text>
        <FlatList
          data={data.alternatives}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          keyExtractor={(item, index) => item.id || `product-${index}`}
          onMomentumScrollEnd={(event) => {
            const index = Math.round(
              event.nativeEvent.contentOffset.x / screenWidth
            );
            setActiveIndex(index);
          }}
          renderItem={({ item, index }) => (
            <View style={styles.carouselItem}>
              <ProductCard product={item} index={index} />
            </View>
          )}
          snapToInterval={screenWidth}
          decelerationRate="fast"
          style={styles.carouselList}
        />

        {/* Carousel Indicators */}
        <View style={styles.indicators}>
          {data.alternatives.map((_, index) => (
            <View
              key={index}
              style={[
                styles.indicator,
                index === activeIndex && styles.indicatorActive,
              ]}
            />
          ))}
        </View>
      </View>

      {/* Comparison Table */}
      <View style={styles.tableSection}>
        <Text style={styles.sectionTitle}>Quick Comparison</Text>
        <ComparisonTable products={data.alternatives} />
      </View>

      {/* Action Buttons */}
      <View style={styles.actionsContainer}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => refetch()}
        >
          <Text style={styles.actionButtonText}>🔄 Refresh Prices</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, styles.actionButtonSecondary]}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.actionButtonTextSecondary}>
            ← New Search
          </Text>
        </TouchableOpacity>
      </View>

      {/* Metadata Footer */}
      <View style={styles.footer}>
        <Text style={styles.footerText}>
          Last updated: {new Date(data.query_time_iso).toLocaleString()}
        </Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  headerCard: {
    backgroundColor: '#FFFFFF',
    margin: 16,
    padding: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  categoryBadge: {
    backgroundColor: '#DBEAFE',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    alignSelf: 'flex-start',
    marginBottom: 12,
  },
  categoryText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#1E40AF',
  },
  sourceText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B7280',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  urlText: {
    fontSize: 13,
    color: '#3B82F6',
  },
  warningBadge: {
    marginTop: 8,
    paddingVertical: 4,
    paddingHorizontal: 8,
    backgroundColor: '#FEF3C7',
    borderRadius: 4,
    alignSelf: 'flex-start',
  },
  warningText: {
    fontSize: 11,
    color: '#92400E',
    fontWeight: '600',
  },
  successBanner: {
    backgroundColor: '#10B981',
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 16,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  successIcon: {
    fontSize: 32,
    color: '#FFFFFF',
  },
  successContent: {
    flex: 1,
  },
  successTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFFFFF',
    marginBottom: 4,
  },
  successSubtitle: {
    fontSize: 13,
    color: '#D1FAE5',
  },
  carouselSection: {
    marginBottom: 24,
  },
  carouselList: {
    flexGrow: 0,
  },
  carouselItem: {
    width: screenWidth,
    paddingHorizontal: 0,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#111827',
    marginHorizontal: 16,
    marginBottom: 12,
  },
  indicators: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginTop: 16,
  },
  indicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#D1D5DB',
  },
  indicatorActive: {
    backgroundColor: '#3B82F6',
    width: 24,
  },
  tableSection: {
    marginBottom: 24,
    paddingHorizontal: 16,
  },
  actionsContainer: {
    marginHorizontal: 16,
    marginBottom: 16,
    gap: 12,
  },
  actionButton: {
    backgroundColor: '#3B82F6',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  actionButtonSecondary: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
  actionButtonTextSecondary: {
    color: '#374151',
    fontSize: 15,
    fontWeight: '600',
  },
  footer: {
    padding: 16,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 11,
    color: '#9CA3AF',
  },
});


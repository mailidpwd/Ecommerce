import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import type { Product } from '../types';

interface ComparisonTableProps {
  products: Product[];
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({ products }) => {
  if (products.length === 0) return null;

  // Extract ALL unique specs from all products (not just first product)
  const allSpecs = new Set<string>();
  products.forEach(p => {
    p.specs.forEach(spec => allSpecs.add(spec));
  });
  
  const specCategories = [
    'Price',
    'Rating',
    'Brand',
    'Model',
    ...Array.from(allSpecs).slice(0, 10).map((spec, i) => {
      // Use first 30 chars of spec as label
      return spec.substring(0, 30) + (spec.length > 30 ? '...' : '');
    }),
  ];

  const renderRow = (label: string, index: number) => {
    let values: string[];

    if (label === 'Price') {
      values = products.map((p) => p.price_estimate);
    } else if (label === 'Rating') {
      values = products.map((p) =>
        p.rating_estimate ? `★ ${p.rating_estimate.toFixed(1)}` : '—'
      );
    } else if (label === 'Brand') {
      values = products.map((p) => p.brand);
    } else if (label === 'Model') {
      values = products.map((p) => p.model || '—');
    } else {
      // Find if each product has this spec
      values = products.map((p) => {
        // Look for the spec in this product's specs array
        const matchingSpec = p.specs.find(s => s.startsWith(label.substring(0, 25)));
        if (matchingSpec) {
          return '✓';  // Product has this spec
        }
        // Try to find this spec in the specs array
        const specFound = p.specs.find(s => label.includes(s.substring(0, 20)) || s.includes(label.substring(0, 20)));
        return specFound || '—';
      });
    }

    return (
      <View
        key={label}
        style={[styles.row, index % 2 === 0 && styles.rowEven]}
      >
        <View style={styles.labelCell}>
          <Text style={styles.labelText} numberOfLines={2}>{label}</Text>
        </View>
        {values.map((value, i) => (
          <View key={i} style={styles.valueCell}>
            <Text style={styles.valueText} numberOfLines={3}>
              {value}
            </Text>
          </View>
        ))}
      </View>
    );
  };

  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View style={styles.table}>
        {/* Header Row */}
        <View style={styles.headerRow}>
          <View style={styles.labelCell}>
            <Text style={styles.headerText}>Feature</Text>
          </View>
          {products.map((p, i) => (
            <View key={i} style={styles.valueCell}>
              <Text style={styles.headerText}>#{i + 1}</Text>
            </View>
          ))}
        </View>

        {/* Data Rows - Show all categories */}
        {specCategories.map((category, index) =>
          renderRow(category, index)
        )}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  table: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  headerRow: {
    flexDirection: 'row',
    backgroundColor: '#3B82F6',
  },
  row: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  rowEven: {
    backgroundColor: '#F9FAFB',
  },
  labelCell: {
    width: 150,
    padding: 12,
    justifyContent: 'center',
    borderRightWidth: 1,
    borderRightColor: '#E5E7EB',
  },
  valueCell: {
    width: 120,
    padding: 10,
    justifyContent: 'center',
    borderRightWidth: 1,
    borderRightColor: '#E5E7EB',
  },
  headerText: {
    fontWeight: 'bold',
    fontSize: 13,
    color: '#FFFFFF',
  },
  labelText: {
    fontWeight: '600',
    fontSize: 13,
    color: '#374151',
  },
  valueText: {
    fontSize: 12,
    color: '#6B7280',
  },
});


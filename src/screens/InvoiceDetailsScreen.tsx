import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '../navigation/types';

type InvoiceDetailsRouteProp = RouteProp<RootStackParamList, 'InvoiceDetails'>;
type NavigationProp = StackNavigationProp<RootStackParamList, 'InvoiceDetails'>;

interface InvoiceData {
  product_name: string;
  brand: string;
  store: string;
  purchase_date: string;
  price_paid: string;
  specifications: string;
  warranty_period: string;
  next_service_date: string;
  extracted_at: string;
  image_uri?: string;
}

export const InvoiceDetailsScreen: React.FC = () => {
  const route = useRoute<InvoiceDetailsRouteProp>();
  const navigation = useNavigation<NavigationProp>();
  const { invoiceData } = route.params;

  const InfoRow = ({ label, value, icon }: { label: string; value: string; icon: string }) => (
    <View style={styles.infoRow}>
      <View style={styles.labelContainer}>
        <Text style={styles.icon}>{icon}</Text>
        <Text style={styles.label}>{label}</Text>
      </View>
      <Text style={styles.value}>{value || 'Not available'}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity 
            style={styles.backButton}
            onPress={() => navigation.goBack()}
          >
            <Text style={styles.backButtonText}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Invoice Details</Text>
          <View style={styles.placeholder} />
        </View>

        {/* Success Banner */}
        <View style={styles.successBanner}>
          <View style={styles.successIconContainer}>
            <Text style={styles.successIcon}>✓</Text>
          </View>
          <View style={styles.successTextContainer}>
            <Text style={styles.successTitle}>Invoice Extracted!</Text>
            <Text style={styles.successSubtitle}>
              All details have been successfully extracted
            </Text>
          </View>
        </View>

        {/* Product Information */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📦 Product Information</Text>
          <View style={styles.card}>
            <InfoRow 
              icon="📱" 
              label="Product Name" 
              value={invoiceData.product_name} 
            />
            <View style={styles.divider} />
            <InfoRow 
              icon="🏷️" 
              label="Brand" 
              value={invoiceData.brand} 
            />
          </View>
        </View>

        {/* Purchase Information */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🛒 Purchase Information</Text>
          <View style={styles.card}>
            <InfoRow 
              icon="🏪" 
              label="Store" 
              value={invoiceData.store} 
            />
            <View style={styles.divider} />
            <InfoRow 
              icon="📅" 
              label="Purchase Date" 
              value={invoiceData.purchase_date} 
            />
            <View style={styles.divider} />
            <InfoRow 
              icon="💰" 
              label="Price Paid" 
              value={invoiceData.price_paid} 
            />
          </View>
        </View>

        {/* Technical Specifications */}
        {invoiceData.specifications && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>⚙️ Specifications</Text>
            <View style={styles.card}>
              <Text style={styles.specsText}>{invoiceData.specifications}</Text>
            </View>
          </View>
        )}

        {/* Warranty & Service */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🛡️ Warranty & Service</Text>
          <View style={styles.card}>
            <InfoRow 
              icon="🛡️" 
              label="Warranty Period" 
              value={invoiceData.warranty_period} 
            />
            <View style={styles.divider} />
            <InfoRow 
              icon="🔧" 
              label="Next Service Date" 
              value={invoiceData.next_service_date} 
            />
          </View>
        </View>

        {/* Extraction Info */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            🤖 Extracted by Gemini 2.5 Flash Vision
          </Text>
          <Text style={styles.footerDate}>
            {new Date(invoiceData.extracted_at).toLocaleString()}
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 32,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    padding: 8,
  },
  backButtonText: {
    fontSize: 16,
    color: '#3B82F6',
    fontWeight: '600',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#111827',
  },
  placeholder: {
    width: 60,
  },
  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#D1FAE5',
    marginHorizontal: 20,
    marginTop: 20,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#86EFAC',
  },
  successIconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#10B981',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  successIcon: {
    fontSize: 24,
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  successTextContainer: {
    flex: 1,
  },
  successTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#065F46',
    marginBottom: 4,
  },
  successSubtitle: {
    fontSize: 13,
    color: '#047857',
  },
  section: {
    marginTop: 24,
    paddingHorizontal: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#374151',
    marginBottom: 12,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  infoRow: {
    paddingVertical: 12,
  },
  labelContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  icon: {
    fontSize: 16,
    marginRight: 8,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
  },
  value: {
    fontSize: 15,
    fontWeight: '600',
    color: '#111827',
    marginLeft: 24,
  },
  divider: {
    height: 1,
    backgroundColor: '#E5E7EB',
    marginVertical: 4,
  },
  specsText: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 22,
  },
  footer: {
    marginTop: 24,
    paddingHorizontal: 20,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#9CA3AF',
    marginBottom: 4,
  },
  footerDate: {
    fontSize: 11,
    color: '#D1D5DB',
  },
});


import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '../navigation/types';
import { getAllWarranties, deleteWarranty, clearAllWarranties, type WarrantyData } from '../utils/warrantyStorage';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

type NavigationProp = StackNavigationProp<RootStackParamList, 'WarrantyList'>;

export const WarrantyListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const [warranties, setWarranties] = useState<WarrantyData[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadWarranties = async () => {
    try {
      const allWarranties = await getAllWarranties();
      setWarranties(allWarranties);
    } catch (error) {
      console.error('Failed to load warranties:', error);
    }
  };

  useFocusEffect(
    useCallback(() => {
      loadWarranties();
    }, [])
  );

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadWarranties();
    setRefreshing(false);
  }, []);

  const handleWarrantyPress = (warranty: WarrantyData) => {
    if (warranty.type === 'invoice') {
      // Navigate to InvoiceDetailsScreen for invoices
      navigation.navigate('InvoiceDetails', {
        invoiceData: {
          product_name: warranty.product_name,
          brand: warranty.brand,
          store: warranty.store,
          purchase_date: warranty.purchase_date || warranty.order_date || 'Not specified',
          price_paid: warranty.price_paid || 'Not specified',
          specifications: warranty.specifications || 'Not available',
          warranty_period: warranty.warranty_period || 'Not specified',
          next_service_date: warranty.next_service_date || 'Not specified',
          extracted_at: warranty.extracted_at,
          image_uri: warranty.image_uri,
          order_number: warranty.order_number,
          invoice_number: warranty.invoice_number,
          invoice_date: warranty.invoice_date || warranty.document_date,
          net_amount: warranty.net_amount,
          tax_amount: warranty.tax_amount,
          model_sku_asin: warranty.model_sku_asin,
          hsn_code: warranty.hsn_code,
        },
      });
    } else {
      // Navigate to WarrantyDetailsScreen for warranties
    navigation.navigate('WarrantyDetails', { warrantyData: warranty });
    }
  };

  const handleDeleteWarranty = (warranty: WarrantyData) => {
    Alert.alert(
      'Delete Item',
      `Are you sure you want to delete this ${warranty.type === 'invoice' ? 'invoice' : 'warranty'} for "${warranty.product_name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await deleteWarranty(warranty.id);
              await loadWarranties();
            } catch (error) {
              Alert.alert('Error', 'Failed to delete item');
            }
          },
        },
      ]
    );
  };

  const handleClearAll = () => {
    Alert.alert(
      'Clear All Data',
      'Are you sure you want to delete ALL invoices and warranties? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear All',
          style: 'destructive',
          onPress: async () => {
            try {
              await clearAllWarranties();
              await loadWarranties();
              Alert.alert('Success', 'All invoices and warranties have been cleared');
            } catch (error) {
              Alert.alert('Error', 'Failed to clear all data');
            }
          },
        },
      ]
    );
  };

  const handleDownloadFile = async (warranty: WarrantyData) => {
    if (!warranty.image_uri) return;
    
    try {
      const isPdf = warranty.image_uri.includes('application/pdf') || warranty.image_uri.includes('.pdf');
      
      if (isPdf) {
        // Extract base64 from data URI
        const base64Data = warranty.image_uri.includes(',') 
          ? warranty.image_uri.split(',')[1] 
          : warranty.image_uri;
        
        // Save to file system
        const fileUri = `${FileSystem.documentDirectory}${warranty.type}_${warranty.id}.pdf`;
        await FileSystem.writeAsStringAsync(fileUri, base64Data, {
          encoding: FileSystem.EncodingType.Base64,
        });
        
        // Share/download
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(fileUri, {
            mimeType: 'application/pdf',
            dialogTitle: `Download ${warranty.type === 'invoice' ? 'Invoice' : 'Warranty'} PDF`,
          });
        } else {
          Alert.alert('Success', `PDF saved to: ${fileUri}`);
        }
      }
    } catch (error) {
      console.error('File download error:', error);
      Alert.alert('Error', 'Failed to download file');
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity 
          style={styles.backButton}
          onPress={() => navigation.goBack()}
        >
          <Text style={styles.backButtonText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Invoices & Warranties</Text>
        {warranties.length > 0 && (
          <TouchableOpacity 
            style={styles.clearButton}
            onPress={handleClearAll}
          >
            <Text style={styles.clearButtonText}>🗑️ Clear</Text>
          </TouchableOpacity>
        )}
        {warranties.length === 0 && <View style={styles.placeholder} />}
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {warranties.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyIcon}>📄</Text>
            <Text style={styles.emptyTitle}>No Invoices or Warranties Yet</Text>
            <Text style={styles.emptySubtitle}>
              Upload invoices to track your purchases and warranty information
            </Text>
            <TouchableOpacity
              style={styles.addButton}
              onPress={() => navigation.navigate('ProductInput')}
            >
              <Text style={styles.addButtonText}>Upload Invoice/PDF</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <>
            <View style={styles.statsContainer}>
              <Text style={styles.statsText}>
                {warranties.length} {warranties.length === 1 ? 'Item' : 'Items'} 
                {' '}({warranties.filter(w => w.type === 'invoice').length} invoices, {warranties.filter(w => w.type === 'warranty').length} warranties)
              </Text>
            </View>

            {warranties.map((warranty) => {
              const hasFile = !!warranty.image_uri;
              const isPdf = hasFile && (warranty.image_uri.includes('application/pdf') || warranty.image_uri.includes('.pdf'));
              
              return (
              <TouchableOpacity
                key={warranty.id}
                style={styles.warrantyCard}
                onPress={() => handleWarrantyPress(warranty)}
                activeOpacity={0.7}
              >
                <View style={styles.warrantyCardHeader}>
                  <View style={styles.warrantyCardContent}>
                      <View style={[
                        styles.warrantyTypeBadge,
                        { backgroundColor: warranty.type === 'invoice' ? '#DBEAFE' : '#D1FAE5' }
                      ]}>
                        <Text style={[
                          styles.warrantyTypeText,
                          { color: warranty.type === 'invoice' ? '#1E40AF' : '#065F46' }
                        ]}>
                        {warranty.type === 'invoice' ? '🧾 Invoice' : '🛡️ Warranty'}
                      </Text>
                    </View>
                    <Text style={styles.warrantyProductName} numberOfLines={2}>
                      {warranty.product_name}
                    </Text>
                    <Text style={styles.warrantyBrand}>{warranty.brand}</Text>
                  </View>
                  <TouchableOpacity
                    style={styles.deleteButton}
                    onPress={(e) => {
                      e.stopPropagation();
                      handleDeleteWarranty(warranty);
                    }}
                  >
                    <Text style={styles.deleteButtonText}>🗑️</Text>
                  </TouchableOpacity>
                </View>

                  {/* PDF/Image Preview */}
                  {hasFile && (
                    <View style={styles.filePreviewContainer}>
                      {isPdf ? (
                        <TouchableOpacity
                          style={styles.pdfPreview}
                          onPress={(e) => {
                            e.stopPropagation();
                            handleDownloadFile(warranty);
                          }}
                          activeOpacity={0.7}
                        >
                          <Text style={styles.pdfPreviewIcon}>📄</Text>
                          <Text style={styles.pdfPreviewText}>PDF Document</Text>
                          <Text style={styles.pdfPreviewSubtext}>Tap to download</Text>
                        </TouchableOpacity>
                      ) : (
                        <Image
                          source={{ uri: warranty.image_uri }}
                          style={styles.imagePreview}
                          resizeMode="cover"
                        />
                      )}
                    </View>
                  )}

                <View style={styles.warrantyCardDetails}>
                  <View style={styles.warrantyDetailRow}>
                    <Text style={styles.warrantyDetailLabel}>🏪 Store:</Text>
                    <Text style={styles.warrantyDetailValue}>{warranty.store}</Text>
                  </View>
                  {warranty.type === 'invoice' && warranty.price_paid && warranty.price_paid !== 'Not specified' && (
                    <View style={styles.warrantyDetailRow}>
                      <Text style={styles.warrantyDetailLabel}>💰 Price:</Text>
                      <Text style={styles.warrantyDetailValue}>{warranty.price_paid}</Text>
                    </View>
                  )}
                  {warranty.purchase_date && warranty.purchase_date !== 'Not specified' && (
                    <View style={styles.warrantyDetailRow}>
                      <Text style={styles.warrantyDetailLabel}>📅 Purchase Date:</Text>
                      <Text style={styles.warrantyDetailValue}>{warranty.purchase_date}</Text>
                    </View>
                  )}
                  {warranty.warranty_period && warranty.warranty_period !== 'N/A' && warranty.warranty_period !== 'Not specified' && (
                    <View style={styles.warrantyDetailRow}>
                      <Text style={styles.warrantyDetailLabel}>🛡️ Warranty:</Text>
                      <Text style={styles.warrantyDetailValue}>{warranty.warranty_period}</Text>
                    </View>
                  )}
                  {warranty.document_date && warranty.document_date !== 'N/A' && warranty.type === 'warranty' && (
                    <View style={styles.warrantyDetailRow}>
                      <Text style={styles.warrantyDetailLabel}>📅 Date:</Text>
                      <Text style={styles.warrantyDetailValue}>{warranty.document_date}</Text>
                    </View>
                  )}
                </View>

                <View style={styles.warrantyCardFooter}>
                  <Text style={styles.warrantyCardFooterText}>
                    Tap to view details
                  </Text>
                </View>
              </TouchableOpacity>
              );
            })}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
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
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 32,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 24,
    paddingHorizontal: 40,
  },
  addButton: {
    backgroundColor: '#3B82F6',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  addButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  statsContainer: {
    marginBottom: 16,
  },
  statsText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  warrantyCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  warrantyCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  warrantyCardContent: {
    flex: 1,
    marginRight: 8,
  },
  warrantyProductName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  warrantyBrand: {
    fontSize: 14,
    color: '#6B7280',
  },
  deleteButton: {
    padding: 4,
  },
  deleteButtonText: {
    fontSize: 20,
  },
  warrantyCardDetails: {
    marginBottom: 12,
  },
  warrantyDetailRow: {
    flexDirection: 'row',
    marginBottom: 6,
  },
  warrantyDetailLabel: {
    fontSize: 13,
    color: '#6B7280',
    marginRight: 8,
    width: 90,
  },
  warrantyDetailValue: {
    fontSize: 13,
    fontWeight: '600',
    color: '#111827',
    flex: 1,
  },
  warrantyCardFooter: {
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    paddingTop: 8,
  },
  warrantyCardFooterText: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'center',
  },
  clearButton: {
    padding: 8,
  },
  clearButtonText: {
    fontSize: 14,
    color: '#EF4444',
    fontWeight: '600',
  },
  filePreviewContainer: {
    marginBottom: 12,
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  pdfPreview: {
    padding: 16,
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
  },
  pdfPreviewIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  pdfPreviewText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 4,
  },
  pdfPreviewSubtext: {
    fontSize: 12,
    color: '#6B7280',
  },
  imagePreview: {
    width: '100%',
    height: 200,
    backgroundColor: '#F9FAFB',
  },
  warrantyTypeBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    marginBottom: 8,
  },
  warrantyTypeText: {
    fontSize: 12,
    fontWeight: '600',
  },
});


import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Image,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '../navigation/types';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

type WarrantyDetailsRouteProp = RouteProp<RootStackParamList, 'WarrantyDetails'>;
type NavigationProp = StackNavigationProp<RootStackParamList, 'WarrantyDetails'>;

export const WarrantyDetailsScreen: React.FC = () => {
  const route = useRoute<WarrantyDetailsRouteProp>();
  const navigation = useNavigation<NavigationProp>();
  const { warrantyData } = route.params;
  
  // Determine if this is an invoice or warranty (check type field or infer from data)
  const isInvoice = (warrantyData as any).type === 'invoice' || 
                   (!(warrantyData as any).type && warrantyData.price_paid); // Fallback: if has price_paid, likely invoice
  const isPdf = warrantyData.image_uri && (warrantyData.image_uri.includes('application/pdf') || warrantyData.image_uri.includes('.pdf'));

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
          <Text style={styles.headerTitle}>
            {isInvoice ? 'Invoice Details' : 'Warranty Details'}
          </Text>
          <View style={styles.placeholder} />
        </View>

        {/* Success Banner */}
        <View style={styles.successBanner}>
          <View style={styles.successIconContainer}>
            <Text style={styles.successIcon}>{isInvoice ? '🧾' : '🛡️'}</Text>
          </View>
          <View style={styles.successTextContainer}>
            <Text style={styles.successTitle}>
              {isInvoice ? 'Invoice Extracted!' : 'Warranty Extracted!'}
            </Text>
            <Text style={styles.successSubtitle}>
              {isInvoice 
                ? 'All invoice details have been successfully extracted'
                : 'All warranty details have been successfully extracted'}
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
              value={warrantyData.product_name} 
            />
            <View style={styles.divider} />
            <InfoRow 
              icon="🏷️" 
              label="Brand" 
              value={warrantyData.brand} 
            />
            {warrantyData.model_sku_asin && warrantyData.model_sku_asin !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="🔢" 
                  label="Model/SKU/ASIN" 
                  value={warrantyData.model_sku_asin} 
                />
              </>
            )}
            {warrantyData.product_code && warrantyData.product_code !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📋" 
                  label="Product Code" 
                  value={warrantyData.product_code} 
                />
              </>
            )}
          </View>
        </View>

        {/* Order Information */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🛒 Order Information</Text>
          <View style={styles.card}>
            <InfoRow 
              icon="🏪" 
              label="Store" 
              value={warrantyData.store} 
            />
            {warrantyData.order_number && warrantyData.order_number !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📦" 
                  label="Order Number" 
                  value={warrantyData.order_number} 
                />
              </>
            )}
            {warrantyData.order_date && warrantyData.order_date !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📅" 
                  label="Order Date" 
                  value={warrantyData.order_date} 
                />
              </>
            )}
            {warrantyData.invoice_number && warrantyData.invoice_number !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="🧾" 
                  label="Invoice Number" 
                  value={warrantyData.invoice_number} 
                />
              </>
            )}
            {warrantyData.document_date && warrantyData.document_date !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📄" 
                  label="Document Date" 
                  value={warrantyData.document_date} 
                />
              </>
            )}
            {warrantyData.quantity && warrantyData.quantity !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="🔢" 
                  label="Quantity" 
                  value={warrantyData.quantity} 
                />
              </>
            )}
          </View>
        </View>

        {/* Seller Information */}
        {(warrantyData.seller_name || warrantyData.seller_address) && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>🏢 Seller Information</Text>
            <View style={styles.card}>
              {warrantyData.seller_name && warrantyData.seller_name !== 'N/A' && (
                <>
                  <InfoRow 
                    icon="🏢" 
                    label="Seller Name" 
                    value={warrantyData.seller_name} 
                  />
                  {warrantyData.seller_address && warrantyData.seller_address !== 'N/A' && (
                    <>
                      <View style={styles.divider} />
                      <InfoRow 
                        icon="📍" 
                        label="Seller Address" 
                        value={warrantyData.seller_address} 
                      />
                    </>
                  )}
                </>
              )}
            </View>
          </View>
        )}

        {/* Technical Specifications */}
        {warrantyData.specifications && warrantyData.specifications !== 'N/A' && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>⚙️ Specifications</Text>
            <View style={styles.card}>
              <Text style={styles.specsText}>{warrantyData.specifications}</Text>
            </View>
          </View>
        )}

        {/* Warranty Information - Only show for warranties, not invoices */}
        {!isInvoice && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>🛡️ Warranty Information</Text>
            <View style={styles.card}>
              {warrantyData.warranty_period && warrantyData.warranty_period !== 'N/A' && warrantyData.warranty_period !== 'Not specified' && (
                <>
                  <InfoRow 
                    icon="🛡️" 
                    label="Warranty Period" 
                    value={warrantyData.warranty_period} 
                  />
                  {warrantyData.warranty_terms && warrantyData.warranty_terms !== 'N/A' && (
                    <>
                      <View style={styles.divider} />
                      <InfoRow 
                        icon="📜" 
                        label="Warranty Terms" 
                        value={warrantyData.warranty_terms} 
                      />
                    </>
                  )}
                </>
              )}
              {(!warrantyData.warranty_period || warrantyData.warranty_period === 'N/A' || warrantyData.warranty_period === 'Not specified') && (
                <Text style={styles.noWarrantyText}>
                  Warranty information not found on this document
                </Text>
              )}
            </View>
          </View>
        )}

        {/* Document File Display (PDF or Image) */}
        {warrantyData.image_uri && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>
              {isPdf ? '📄 Document PDF' : '📷 Document Image'}
            </Text>
            <View style={styles.fileSection}>
              {isPdf ? (
                // PDF: Show download button
                <View style={styles.pdfContainer}>
                  <View style={styles.pdfIconContainer}>
                    <Text style={styles.pdfIcon}>📄</Text>
                    <Text style={styles.pdfText}>PDF Document</Text>
                    <Text style={styles.pdfSubtext}>Tap to download and view</Text>
                  </View>
                  <TouchableOpacity
                    style={styles.downloadButton}
                    onPress={async () => {
                      try {
                        if (!warrantyData.image_uri) return;
                        
                        // Extract base64 from data URI
                        const base64Data = warrantyData.image_uri.includes(',') 
                          ? warrantyData.image_uri.split(',')[1] 
                          : warrantyData.image_uri;
                        
                        // Save to file system
                        const fileUri = `${FileSystem.documentDirectory}${warrantyData.type || 'document'}_${warrantyData.id}.pdf`;
                        await FileSystem.writeAsStringAsync(fileUri, base64Data, {
                          encoding: FileSystem.EncodingType.Base64,
                        });
                        
                        // Share/download
                        if (await Sharing.isAvailableAsync()) {
                          await Sharing.shareAsync(fileUri, {
                            mimeType: 'application/pdf',
                            dialogTitle: `Download ${warrantyData.type === 'invoice' ? 'Invoice' : 'Warranty'} PDF`,
                          });
                        } else {
                          Alert.alert('Success', `PDF saved to: ${fileUri}`);
                        }
                      } catch (error) {
                        console.error('PDF download error:', error);
                        Alert.alert('Error', 'Failed to download PDF');
                      }
                    }}
                    activeOpacity={0.7}
                  >
                    <Text style={styles.downloadButtonText}>📥 Download PDF</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                // Image: Display normally
                <>
                  <TouchableOpacity
                    style={styles.imageContainer}
                    onPress={() => {
                      Alert.alert(
                        'Document Image',
                        'This is the extracted document image. You can view it here or take a screenshot to save it.',
                        [{ text: 'OK' }]
                      );
                    }}
                    activeOpacity={0.9}
                  >
                    <Image
                      source={{ uri: warrantyData.image_uri }}
                      style={styles.documentImage}
                      resizeMode="contain"
                    />
                  </TouchableOpacity>
                  <Text style={styles.imageHint}>
                    Tap image to view full size
                  </Text>
                </>
              )}
            </View>
          </View>
        )}

        {/* Extraction Info */}
        <View style={styles.footer}>
          <Text style={styles.footerText}>
            🤖 Extracted by Gemini 2.5 Flash Vision
          </Text>
          <Text style={styles.footerDate}>
            {new Date(warrantyData.extracted_at).toLocaleString()}
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
    backgroundColor: '#DBEAFE',
    marginHorizontal: 20,
    marginTop: 20,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#93C5FD',
  },
  successIconContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#3B82F6',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  successIcon: {
    fontSize: 24,
  },
  successTextContainer: {
    flex: 1,
  },
  successTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1E40AF',
    marginBottom: 4,
  },
  successSubtitle: {
    fontSize: 13,
    color: '#1E3A8A',
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
  noWarrantyText: {
    fontSize: 14,
    color: '#9CA3AF',
    fontStyle: 'italic',
    textAlign: 'center',
    paddingVertical: 8,
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
  fileSection: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  pdfContainer: {
    padding: 20,
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#E5E7EB',
    borderStyle: 'dashed',
    alignItems: 'center',
  },
  pdfIconContainer: {
    alignItems: 'center',
    marginBottom: 16,
  },
  pdfIcon: {
    fontSize: 48,
    marginBottom: 8,
  },
  pdfText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 4,
  },
  pdfSubtext: {
    fontSize: 13,
    color: '#6B7280',
  },
  downloadButton: {
    backgroundColor: '#3B82F6',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2563EB',
  },
  downloadButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  imageContainer: {
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  documentImage: {
    width: '100%',
    height: 400,
    backgroundColor: '#F9FAFB',
  },
  imageHint: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
    marginTop: 8,
    fontStyle: 'italic',
  },
});




import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRoute, useNavigation } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import type { RootStackParamList } from '../navigation/types';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { saveWarranty, generateWarrantyId, getAllWarranties } from '../utils/warrantyStorage';

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
  order_number?: string;
  invoice_number?: string;
  invoice_date?: string;
  net_amount?: string;
  tax_amount?: string;
  model_sku_asin?: string;
  hsn_code?: string;
}

export const InvoiceDetailsScreen: React.FC = () => {
  const route = useRoute<InvoiceDetailsRouteProp>();
  const navigation = useNavigation<NavigationProp>();
  const { invoiceData } = route.params;
  
  const [warrantyData, setWarrantyData] = useState<{
    warranty_period?: string;
    next_service_date?: string;
    warranty_terms?: string;
    extracted_at?: string;
  }>({
    warranty_period: invoiceData.warranty_period || 'Not specified',
    next_service_date: invoiceData.next_service_date || 'Not specified',
  });
  const [uploadingWarranty, setUploadingWarranty] = useState(false);
  const [warrantyImageUri, setWarrantyImageUri] = useState<string | null>(null);
  const [warrantyFileType, setWarrantyFileType] = useState<string | null>(null);

  // DO NOT load warranty images on mount - only show after user uploads a warranty slip
  // This ensures warranty section is empty until user explicitly uploads a warranty

  const InfoRow = ({ label, value, icon }: { label: string; value: string; icon: string }) => (
    <View style={styles.infoRow}>
      <View style={styles.labelContainer}>
        <Text style={styles.icon}>{icon}</Text>
        <Text style={styles.label}>{label}</Text>
      </View>
      <Text style={styles.value}>{value || 'Not available'}</Text>
    </View>
  );

  const handleUploadWarranty = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['application/pdf', 'image/*'],
        copyToCacheDirectory: true,
      });

      if (result.assets && result.assets[0]) {
        const file = result.assets[0];
        const isPdf = file.mimeType === 'application/pdf';
        
        setUploadingWarranty(true);
        
        const BACKEND_URL = 'http://10.41.62.10:8000';
        
        // Convert file to base64 AND data URI for immediate display
        let fileDataUri: string | null = null;
        const fileBase64 = await fetch(file.uri)
          .then(res => res.blob())
          .then(blob => {
            return new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onloadend = () => {
                const base64 = reader.result as string;
                // Store full data URI for immediate display
                fileDataUri = base64;
                // Extract just base64 data for backend
                const base64Data = base64.includes(',') ? base64.split(',')[1] : base64;
                resolve(base64Data);
              };
              reader.onerror = reject;
              reader.readAsDataURL(blob);
            });
          });
        
        // Display uploaded file immediately (before backend response)
        if (fileDataUri) {
          console.log(`📷 Setting uploaded file as warranty file immediately (type: ${isPdf ? 'pdf' : 'image'}, URI length: ${fileDataUri.length})`);
          setWarrantyImageUri(fileDataUri);
          setWarrantyFileType(isPdf ? 'pdf' : 'image');
          console.log(`✅ State updated - warrantyImageUri: ${!!fileDataUri}, warrantyFileType: ${isPdf ? 'pdf' : 'image'}`);
        } else {
          console.error('❌ fileDataUri is null - cannot display file');
        }
        
        // Add timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);
        
        const response = await fetch(`${BACKEND_URL}/extract-warranty`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            image_base64: fileBase64,
            file_type: isPdf ? 'pdf' : 'image',
            invoice_data: {
              product_name: invoiceData.product_name,
              brand: invoiceData.brand,
              store: invoiceData.store,
              order_number: invoiceData.order_number,
              purchase_date: invoiceData.purchase_date,
              invoice_number: invoiceData.invoice_number,
              model_sku_asin: invoiceData.model_sku_asin,
              specifications: invoiceData.specifications,
            },
          }),
          signal: controller.signal,
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
          const data = await response.json();
          console.log('📥 Warranty extraction response:', {
            hasInvoice: !!data.invoice,
            hasWarranty: !!data.warranty,
            hasWarrantyFile: !!data.warranty_file_base64,
            hasWarrantyImage: !!data.warranty_image_base64, // Old format support
            warrantyFileLength: data.warranty_file_base64?.length || 0,
            warrantyFileType: data.warranty_file_type,
            responseKeys: Object.keys(data),
          });
          
          // Handle both old format (warranty) and new format (invoice)
          const warranty = data.warranty || {};
          const invoice = data.invoice || warranty; // Fallback to warranty for backward compatibility
          
          // Extract warranty file (PDF or image) - prefer backend file, fallback to uploaded file
          let responseFileDataUri: string | null = null;
          let responseFileType: string = isPdf ? 'pdf' : 'image';
          
          if (data.warranty_file_base64) {
            // New format: backend returns original file
            responseFileType = data.warranty_file_type || responseFileType;
            if (responseFileType === 'pdf') {
              responseFileDataUri = `data:application/pdf;base64,${data.warranty_file_base64}`;
            } else {
              responseFileDataUri = `data:image/jpeg;base64,${data.warranty_file_base64}`;
            }
            console.log(`✅ Setting warranty file from backend: type=${responseFileType}, length=${responseFileDataUri.length}`);
            setWarrantyImageUri(responseFileDataUri);
            setWarrantyFileType(responseFileType);
          } else if (data.warranty_image_base64) {
            // Old format: backend returns converted image
            responseFileDataUri = `data:image/jpeg;base64,${data.warranty_image_base64}`;
            console.log('✅ Setting warranty image from backend (old format)');
            setWarrantyImageUri(responseFileDataUri);
            setWarrantyFileType('image');
          } else {
            // Fallback to uploaded file (already set immediately, but ensure file type is set)
            console.warn('⚠️ No warranty file in response - keeping uploaded file that was set immediately');
            // fileDataUri and fileType are already set from immediate display above
            // Just ensure file type is set correctly
            if (!warrantyFileType) {
              setWarrantyFileType(responseFileType);
            }
          }
          
          // Update warranty data from invoice/warranty response
          setWarrantyData({
            warranty_period: invoice.warranty_period || warranty.warranty_period || warrantyData.warranty_period || invoiceData.warranty_period || 'Not specified',
            next_service_date: invoice.next_service_date || warranty.next_service_date || warrantyData.next_service_date || invoiceData.next_service_date || 'Not specified',
            warranty_terms: invoice.warranty_terms || warranty.warranty_terms || warrantyData.warranty_terms,
            extracted_at: new Date().toISOString(),
          });
          
          // Save warranty to storage - use the file URI that was set (from response or uploaded file)
          const warrantyId = generateWarrantyId();
          // Use response file if available, otherwise use the uploaded file data URI
          // CRITICAL: NEVER use invoiceData.image_uri - this must be the WARRANTY file only
          const savedFileUri = responseFileDataUri || fileDataUri || file.uri;
          const savedFileType = responseFileType || (isPdf ? 'pdf' : 'image');
          
          // Safety check: Ensure we're not accidentally using invoice image_uri
          if (!savedFileUri) {
            console.error('❌ CRITICAL: No warranty file URI to save!');
            Alert.alert('Error', 'No warranty file to save. Please try uploading again.');
            return;
          }
          
          // Double-check: Ensure savedFileUri is NOT the invoice image_uri
          if (invoiceData.image_uri && savedFileUri === invoiceData.image_uri) {
            console.error('❌ CRITICAL: Warranty file URI matches invoice URI! This should never happen!');
            Alert.alert('Error', 'Warranty file cannot be the same as invoice file. Please upload a different warranty slip.');
            return;
          }
          
          console.log('💾 Saving warranty with file URI:', savedFileUri ? `Yes (type: ${savedFileType}, length: ${savedFileUri.length})` : 'No');
          console.log('💾 Warranty type: warranty (not invoice) - this is a WARRANTY upload');
          console.log('💾 Invoice image_uri exists:', !!invoiceData.image_uri);
          console.log('💾 Warranty file URI is different from invoice:', savedFileUri !== invoiceData.image_uri);
          
          await saveWarranty({
            id: warrantyId,
            type: 'warranty', // CRITICAL: Must be 'warranty', not 'invoice' - this is a WARRANTY slip upload
            product_name: invoice.product_name || warranty.product_name || invoiceData.product_name,
            brand: invoice.brand || warranty.brand || invoiceData.brand,
            store: invoice.store || warranty.store || invoiceData.store,
            order_number: invoice.order_number || warranty.order_number || invoiceData.order_number,
            order_date: invoice.order_date || invoice.purchase_date || warranty.order_date || invoiceData.purchase_date,
            invoice_number: invoice.invoice_number || warranty.invoice_number || invoiceData.invoice_number,
            model_sku_asin: invoice.model_sku_asin || warranty.model_sku_asin || invoiceData.model_sku_asin,
            specifications: invoice.specifications || warranty.specifications || invoiceData.specifications,
            warranty_period: invoice.warranty_period || warranty.warranty_period || warrantyData.warranty_period,
            warranty_terms: invoice.warranty_terms || warranty.warranty_terms,
            extracted_at: new Date().toISOString(),
            image_uri: savedFileUri, // Save the warranty file (PDF or image) - this is from WARRANTY upload, not invoice
          });
          
          Alert.alert('Success', 'Warranty details extracted and saved successfully!');
        } else {
          const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
          Alert.alert('Error', errorData.detail || 'Could not extract warranty data');
        }
      }
    } catch (error) {
      console.error('Warranty upload error:', error);
      let errorMessage = 'Failed to extract warranty data';
      
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          errorMessage = 'Request timeout - extraction took too long';
        } else if (error.message.includes('Network request failed')) {
          errorMessage = 'Network error - cannot connect to server';
        } else {
          errorMessage = error.message;
        }
      }
      
      Alert.alert('Error', errorMessage);
    } finally {
      setUploadingWarranty(false);
    }
  };

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
            {invoiceData.model_sku_asin && invoiceData.model_sku_asin !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="🔢" 
                  label="Model/SKU/ASIN" 
                  value={invoiceData.model_sku_asin} 
                />
              </>
            )}
            {invoiceData.hsn_code && invoiceData.hsn_code !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📋" 
                  label="HSN Code" 
                  value={invoiceData.hsn_code} 
                />
              </>
            )}
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
            {invoiceData.order_number && invoiceData.order_number !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📦" 
                  label="Order Number" 
                  value={invoiceData.order_number} 
                />
              </>
            )}
            {invoiceData.invoice_number && invoiceData.invoice_number !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="🧾" 
                  label="Invoice Number" 
                  value={invoiceData.invoice_number} 
                />
              </>
            )}
            <View style={styles.divider} />
            <InfoRow 
              icon="📅" 
              label="Purchase Date" 
              value={invoiceData.purchase_date} 
            />
            {invoiceData.invoice_date && invoiceData.invoice_date !== 'N/A' && invoiceData.invoice_date !== invoiceData.purchase_date && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📄" 
                  label="Invoice Date" 
                  value={invoiceData.invoice_date} 
                />
              </>
            )}
            <View style={styles.divider} />
            <InfoRow 
              icon="💰" 
              label="Price Paid" 
              value={invoiceData.price_paid} 
            />
            {invoiceData.net_amount && invoiceData.net_amount !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="💵" 
                  label="Net Amount" 
                  value={invoiceData.net_amount} 
                />
              </>
            )}
            {invoiceData.tax_amount && invoiceData.tax_amount !== 'N/A' && (
              <>
                <View style={styles.divider} />
                <InfoRow 
                  icon="📊" 
                  label="Tax Amount" 
                  value={invoiceData.tax_amount} 
                />
              </>
            )}
          </View>
        </View>

        {/* Invoice File Display (PDF or Image) */}
        {invoiceData.image_uri && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>
              {invoiceData.image_uri.includes('application/pdf') || invoiceData.image_uri.includes('.pdf') 
                ? '📄 Invoice PDF' 
                : '📷 Invoice Image'}
            </Text>
            <View style={styles.fileSection}>
              {invoiceData.image_uri.includes('application/pdf') || invoiceData.image_uri.includes('.pdf') ? (
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
                        if (!invoiceData.image_uri) return;
                        
                        // Extract base64 from data URI
                        const base64Data = invoiceData.image_uri.includes(',') 
                          ? invoiceData.image_uri.split(',')[1] 
                          : invoiceData.image_uri;
                        
                        // Save to file system
                        const fileUri = `${FileSystem.documentDirectory}invoice_${invoiceData.invoice_number || Date.now()}.pdf`;
                        await FileSystem.writeAsStringAsync(fileUri, base64Data, {
                          encoding: FileSystem.EncodingType.Base64,
                        });
                        
                        // Share/download
                        if (await Sharing.isAvailableAsync()) {
                          await Sharing.shareAsync(fileUri, {
                            mimeType: 'application/pdf',
                            dialogTitle: 'Download Invoice PDF',
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
                        'Invoice Image',
                        'This is the extracted invoice image. You can view it here or take a screenshot to save it.',
                        [{ text: 'OK' }]
                      );
                    }}
                    activeOpacity={0.9}
                  >
                    <Image
                      source={{ uri: invoiceData.image_uri }}
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
              value={warrantyData.warranty_period || invoiceData.warranty_period || 'Not specified'} 
            />
            <View style={styles.divider} />
            <InfoRow 
              icon="🔧" 
              label="Next Service Date" 
              value={warrantyData.next_service_date || invoiceData.next_service_date || 'Not specified'} 
            />
            {warrantyData.warranty_terms && (
              <>
                <View style={styles.divider} />
                <View style={styles.warrantyTermsContainer}>
                  <Text style={styles.warrantyTermsLabel}>Warranty Terms:</Text>
                  <Text style={styles.warrantyTermsText}>{warrantyData.warranty_terms}</Text>
                </View>
              </>
            )}
          </View>
          
          {/* Warranty File Display (PDF or Image) */}
          {warrantyImageUri && (
            <View style={styles.warrantyImageSection}>
              <Text style={styles.warrantyImageTitle}>
                {(warrantyFileType === 'pdf' || warrantyImageUri.includes('application/pdf')) ? '📄 Warranty Slip PDF' : '📷 Warranty Slip Image'}
              </Text>
              
              {(warrantyFileType === 'pdf' || warrantyImageUri.includes('application/pdf')) ? (
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
                        if (!warrantyImageUri) return;
                        
                        // Extract base64 from data URI
                        const base64Data = warrantyImageUri.includes(',') 
                          ? warrantyImageUri.split(',')[1] 
                          : warrantyImageUri;
                        
                        // Save to file system
                        const fileUri = `${FileSystem.documentDirectory}warranty_slip_${Date.now()}.pdf`;
                        await FileSystem.writeAsStringAsync(fileUri, base64Data, {
                          encoding: FileSystem.EncodingType.Base64,
                        });
                        
                        // Share/download
                        if (await Sharing.isAvailableAsync()) {
                          await Sharing.shareAsync(fileUri, {
                            mimeType: 'application/pdf',
                            dialogTitle: 'Download Warranty Slip PDF',
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
                    style={styles.warrantyImageContainer}
                    onPress={() => {
                      Alert.alert(
                        'Warranty Slip Image',
                        'This is the extracted warranty slip image. You can view it here or take a screenshot to save it.',
                        [{ text: 'OK' }]
                      );
                    }}
                    activeOpacity={0.9}
                  >
                    <Image
                      source={{ uri: warrantyImageUri }}
                      style={styles.warrantyImage}
                      resizeMode="contain"
                    />
                  </TouchableOpacity>
                  <Text style={styles.warrantyImageHint}>
                    Tap image to view full size
                  </Text>
                </>
              )}
            </View>
          )}
          
          {/* Upload Warranty Proof Section */}
          <View style={styles.uploadSection}>
            <Text style={styles.uploadSectionTitle}>📄 Upload Warranty Proof</Text>
            <Text style={styles.uploadSectionSubtitle}>
              Upload warranty slip or packing slip to extract warranty details
            </Text>
            <TouchableOpacity
              style={[styles.uploadButton, uploadingWarranty && styles.uploadButtonDisabled]}
              onPress={handleUploadWarranty}
              disabled={uploadingWarranty}
              activeOpacity={0.7}
            >
              {uploadingWarranty ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <>
                  <Text style={styles.uploadButtonIcon}>🛡️</Text>
                  <Text style={styles.uploadButtonText}>Choose Warranty Slip/PDF</Text>
                </>
              )}
            </TouchableOpacity>
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
  uploadSection: {
    marginTop: 16,
    padding: 16,
    backgroundColor: '#F0FDF4',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#BBF7D0',
    borderStyle: 'dashed',
  },
  uploadSectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#166534',
    marginBottom: 4,
  },
  uploadSectionSubtitle: {
    fontSize: 13,
    color: '#15803D',
    marginBottom: 12,
  },
  uploadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#10B981',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#059669',
  },
  uploadButtonDisabled: {
    opacity: 0.6,
  },
  uploadButtonIcon: {
    fontSize: 20,
    marginRight: 8,
  },
  uploadButtonText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  warrantyTermsContainer: {
    marginTop: 8,
  },
  warrantyTermsLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 6,
  },
  warrantyTermsText: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
  },
  warrantyImageSection: {
    marginTop: 16,
    padding: 16,
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  warrantyImageTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#374151',
    marginBottom: 12,
  },
  warrantyImageContainer: {
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  warrantyImage: {
    width: '100%',
    height: 400,
    backgroundColor: '#F9FAFB',
  },
  warrantyImageHint: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
    marginTop: 8,
    fontStyle: 'italic',
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


import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Image,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { StackNavigationProp } from '@react-navigation/stack';
import { isValidProductUrl, extractUrlFromText } from '../utils/urlValidator';
import { getRecentUrls } from '../utils/storage';
import type { RootStackParamList } from '../navigation/types';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';

type NavigationProp = StackNavigationProp<RootStackParamList, 'ProductInput'>;

export const ProductInputScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const [url, setUrl] = useState('');
  const [shareText, setShareText] = useState(''); // Store original share text
  const [recentUrls, setRecentUrls] = useState<string[]>([]);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [identifyingProduct, setIdentifyingProduct] = useState(false);  // For image search
  const [extractingInvoice, setExtractingInvoice] = useState(false);    // For invoice extraction
  const [productText, setProductText] = useState(''); // Direct text input
  const [searchMode, setSearchMode] = useState<'url' | 'text'>('url'); // Switch between URL and text mode
  const [showExtractedDetails, setShowExtractedDetails] = useState(false); // Toggle for viewing extracted details

  useEffect(() => {
    loadRecentUrls();
  }, []);

  const loadRecentUrls = async () => {
    const recent = await getRecentUrls();
    setRecentUrls(recent);
  };

  const handleUrlChange = (text: string) => {
    // Store original text (contains product details!)
    setShareText(text);
    
    // Extract clean URL from text that might contain product description
    // Example: "Limited-time deal: Product Name https://amzn.in/d/abc123" -> "https://amzn.in/d/abc123"
    const extractedUrl = extractUrlFromText(text);
    setUrl(extractedUrl);
  };

  const handleSubmit = () => {
    if (searchMode === 'url' && isValidProductUrl(url)) {
      // URL-based search
      navigation.navigate('Recommendation', { url, shareText });
    } else if (searchMode === 'text' && productText.trim().length > 0) {
      // Text-based search - create a search URL
      const searchUrl = `https://www.amazon.in/s?k=${encodeURIComponent(productText)}`;
      navigation.navigate('Recommendation', { 
        url: searchUrl, 
        shareText: productText 
      });
    }
  };
  
  const handleProductTextChange = (text: string) => {
    setProductText(text);
  };

  const handleSelectRecent = (recentUrl: string) => {
    setUrl(recentUrl);
    setShareText(''); // No share text for recent URLs
  };

  const identifyProductFromImage = async (imageUri: string) => {
    setIdentifyingProduct(true);
    
    try {
      // Call backend to identify product using Gemini 2.5 Flash Vision
      const BACKEND_URL = 'http://10.255.84.10:8000';
      
      // Convert local image to base64 for backend
      const imageBase64 = await fetch(imageUri)
        .then(res => res.blob())
        .then(blob => {
          return new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
              const base64 = reader.result as string;
              // Remove data:image/jpeg;base64, prefix
              const base64Data = base64.split(',')[1];
              resolve(base64Data);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
        });
      
      const response = await fetch(`${BACKEND_URL}/identify-product`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_base64: imageBase64,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const { product } = data;
        
        // Show success message
        Alert.alert(
          '✅ Product Identified!',
          `${product.brand} ${product.product_name}\n\nSearching for alternatives...`,
          [{ text: 'OK' }]
        );
        
        // Navigate to recommendations with identified product
        navigation.navigate('Recommendation', { 
          url: `https://www.amazon.in/s?k=${encodeURIComponent(product.brand + ' ' + product.product_name)}`,
          shareText: `${product.brand} ${product.product_name}`
        });
      } else {
        Alert.alert('Error', 'Could not identify product from image');
      }
    } catch (error) {
      console.error('Image identification error:', error);
      Alert.alert('Error', 'Failed to identify product');
    } finally {
      setIdentifyingProduct(false);
      setSelectedImage(null);
    }
  };

  const pickImageFromGallery = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please allow access to your photos');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      setSelectedImage(result.assets[0].uri);
      await identifyProductFromImage(result.assets[0].uri);
    }
  };

  const takePhoto = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please allow camera access');
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      setSelectedImage(result.assets[0].uri);
      await identifyProductFromImage(result.assets[0].uri);
    }
  };

  const showImageOptions = () => {
    Alert.alert(
      '📸 Search by Image',
      'How would you like to add a product image?',
      [
        { text: 'Take Photo', onPress: takePhoto },
        { text: 'Choose from Gallery', onPress: pickImageFromGallery },
        { text: 'Cancel', style: 'cancel' }
      ]
    );
  };

  const uploadInvoice = async () => {
    try {
      // Use DocumentPicker to select PDF or image files
      const result = await DocumentPicker.getDocumentAsync({
        type: ['application/pdf', 'image/*'],  // Allow PDFs and images
        copyToCacheDirectory: true,
      });

      if (result.assets && result.assets[0]) {
        const file = result.assets[0];
        
        // Check file type
        if (file.mimeType === 'application/pdf') {
          Alert.alert(
            'PDF Support Coming Soon',
            'PDF extraction is under development. Please use image invoices (JPEG/PNG) for now.',
            [{ text: 'OK' }]
          );
          return;
        }
        
        // For images, proceed with extraction
        setSelectedImage(file.uri);
        await extractInvoiceData(file.uri);
      }
    } catch (error) {
      console.error('Document picker error:', error);
      Alert.alert('Error', 'Failed to select document');
    }
  };

  const extractInvoiceData = async (imageUri: string) => {
    setExtractingInvoice(true);
    
    try {
      const BACKEND_URL = 'http://10.255.84.10:8000';
      
      // Convert image to base64
      const imageBase64 = await fetch(imageUri)
        .then(res => res.blob())
        .then(blob => {
          return new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
              const base64 = reader.result as string;
              const base64Data = base64.split(',')[1];
              resolve(base64Data);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
        });
      
      const response = await fetch(`${BACKEND_URL}/extract-invoice`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_base64: imageBase64,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const invoice = data.invoice;
        
        // Navigate to Invoice Details screen (NO product search)
        navigation.navigate('InvoiceDetails', {
          invoiceData: {
            product_name: invoice.product_name || 'Unknown',
            brand: invoice.brand || 'Unknown',
            store: invoice.store || 'Unknown',
            purchase_date: invoice.purchase_date || 'Not specified',
            price_paid: invoice.price || 'Not specified',
            specifications: invoice.specifications || 'Not available',
            warranty_period: invoice.warranty || 'Not specified',
            next_service_date: invoice.next_service || 'Not specified',
            extracted_at: new Date().toISOString(),
            image_uri: imageUri,
          },
        });
      } else {
        Alert.alert('Error', 'Could not extract data from invoice');
      }
    } catch (error) {
      console.error('Invoice extraction error:', error);
      Alert.alert('Error', 'Failed to extract invoice data');
    } finally {
      setExtractingInvoice(false);
      setSelectedImage(null);
    }
  };

  const isValid = searchMode === 'url' ? isValidProductUrl(url) : productText.trim().length > 0;

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView 
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.title}>Decision Recommendation</Text>
            <Text style={styles.subtitle}>
              Get AI-powered product alternatives with verified pricing
            </Text>
          </View>

        {/* Mode Toggle */}
        <View style={styles.modeToggleContainer}>
          <TouchableOpacity
            style={[styles.modeButton, searchMode === 'url' && styles.modeButtonActive]}
            onPress={() => setSearchMode('url')}
            activeOpacity={0.7}
          >
            <Text style={[styles.modeButtonText, searchMode === 'url' && styles.modeButtonTextActive]}>
              🔗 URL
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeButton, searchMode === 'text' && styles.modeButtonActive]}
            onPress={() => setSearchMode('text')}
            activeOpacity={0.7}
          >
            <Text style={[styles.modeButtonText, searchMode === 'text' && styles.modeButtonTextActive]}>
              ✏️ Text
            </Text>
          </TouchableOpacity>
        </View>

        {/* URL Input (shown when searchMode === 'url') */}
        {searchMode === 'url' && (
        <View style={styles.inputContainer}>
          <View style={styles.labelRow}>
            <Text style={styles.label}>Product URL</Text>
            {/* Smart badge indicator */}
            {shareText && shareText.length > url.length + 20 && (
              <View style={styles.smartBadge}>
                <Text style={styles.smartBadgeText}>⚡ Smart</Text>
              </View>
            )}
          </View>
          
          <TextInput
            style={styles.input}
            placeholder="Paste Amazon/Flipkart product link or share text"
            value={url}
            onChangeText={handleUrlChange}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            returnKeyType="go"
            onSubmitEditing={handleSubmit}
            multiline={false}
          />
          
          <Text style={styles.helperText}>
            Paste directly from Amazon app - Product details auto-extracted
          </Text>

          {/* Validation Indicator */}
          {url.length > 0 && (
            <View style={styles.validationContainer}>
              {isValid ? (
                <View style={styles.validRow}>
                  <Text style={styles.validText}>✓ Valid URL</Text>
                  {/* Show if product details were extracted */}
                  {shareText && shareText.length > url.length + 20 && (
                    <Text style={styles.detailsExtracted}>
                      • Details captured
                    </Text>
                  )}
                </View>
              ) : (
                <Text style={styles.invalidText}>✗ Invalid URL format</Text>
              )}
            </View>
          )}

          {/* Expandable product details (optional) */}
          {shareText && shareText.length > url.length + 20 && (
            <>
              <TouchableOpacity 
                style={styles.detailsToggle}
                onPress={() => setShowExtractedDetails(!showExtractedDetails)}
                activeOpacity={0.7}
              >
                <Text style={styles.detailsToggleText}>
                  {showExtractedDetails ? '▼' : '▶'} View extracted product details
                </Text>
              </TouchableOpacity>
              
              {showExtractedDetails && (
                <View style={styles.extractedDetailsBox}>
                  <Text style={styles.extractedDetailsLabel}>
                    📋 Product Information (used for smart search):
                  </Text>
                  <Text style={styles.extractedDetailsText}>
                    {shareText.replace(url, '').replace(/^Limited-time deal:\s*/, '').replace(/^Deal:\s*/, '').replace(/^Deal of the Day:\s*/, '').trim()}
                  </Text>
                  <Text style={styles.extractedDetailsNote}>
                    💡 Using this info to find similar products - no need to scrape!
                  </Text>
                </View>
              )}
            </>
          )}
        </View>
        )}

        {/* Text Input (shown when searchMode === 'text') */}
        {searchMode === 'text' && (
          <View style={styles.inputContainer}>
            <Text style={styles.label}>Product Name</Text>
            <TextInput
              style={styles.input}
              placeholder="E.g., Realme Buds T300, Nike Revolution 6 Shoes"
              value={productText}
              onChangeText={handleProductTextChange}
              autoCapitalize="words"
              autoCorrect={true}
              returnKeyType="search"
              onSubmitEditing={handleSubmit}
              multiline={false}
            />
            <Text style={styles.helperText}>
              Type the product name you want to find alternatives for
            </Text>

            {/* Validation Indicator */}
            {productText.length > 0 && (
              <View style={styles.validationContainer}>
                <Text style={styles.validText}>✓ Ready to search</Text>
              </View>
            )}
          </View>
        )}

        {/* Get Recommendations Button */}
        <TouchableOpacity
          style={[styles.button, !isValid && styles.buttonDisabled]}
          onPress={handleSubmit}
          disabled={!isValid}
        >
          <Text style={styles.buttonText}>Get Recommendations</Text>
        </TouchableOpacity>

        {/* OR Divider */}
        <View style={styles.dividerContainer}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>OR</Text>
          <View style={styles.dividerLine} />
        </View>

        {/* Image Search Section */}
        <View style={styles.imageSearchContainer}>
          <Text style={styles.imageSearchTitle}>📸 Search by Image</Text>
          <Text style={styles.imageSearchSubtitle}>
            Take a photo or upload a product image - Gemini AI will identify it
          </Text>
          
          {identifyingProduct ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#3B82F6" />
              <Text style={styles.loadingText}>🤖 Gemini AI identifying product...</Text>
            </View>
          ) : (
            <View style={styles.imageButtonsContainer}>
              <TouchableOpacity
                style={styles.imageButton}
                onPress={takePhoto}
                activeOpacity={0.7}
              >
                <Text style={styles.imageButtonIcon}>📷</Text>
                <Text style={styles.imageButtonText}>Take Photo</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={styles.imageButton}
                onPress={pickImageFromGallery}
                activeOpacity={0.7}
              >
                <Text style={styles.imageButtonIcon}>🖼️</Text>
                <Text style={styles.imageButtonText}>Choose Image</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>

        {/* Invoice/PDF Extraction Section */}
        <View style={styles.invoiceContainer}>
          <Text style={styles.invoiceTitle}>🧾 Upload Invoice/PDF</Text>
          <Text style={styles.invoiceSubtitle}>
            Upload receipt or invoice - Extract product, warranty, service dates
          </Text>
          
          {extractingInvoice ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color="#10B981" />
              <Text style={styles.loadingText}>📄 Extracting invoice data...</Text>
            </View>
          ) : (
            <TouchableOpacity
              style={styles.invoiceButton}
              onPress={uploadInvoice}
              activeOpacity={0.7}
            >
              <Text style={styles.invoiceButtonIcon}>📄</Text>
              <Text style={styles.invoiceButtonText}>Choose Invoice/PDF</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Recent Searches */}
        {recentUrls.length > 0 && (
          <View style={styles.recentContainer}>
            <Text style={styles.recentTitle}>Recent Searches</Text>
            {recentUrls.map((recentUrl, index) => (
              <TouchableOpacity
                key={index}
                style={styles.recentItem}
                onPress={() => handleSelectRecent(recentUrl)}
              >
                <Text style={styles.recentText} numberOfLines={1}>
                  {recentUrl}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  scrollContent: {
    padding: 20,
    paddingTop: 16,
  },
  header: {
    marginBottom: 24,
    alignItems: 'center',
    marginTop: 8,
  },
  modeToggleContainer: {
    flexDirection: 'row',
    backgroundColor: '#F3F4F6',
    borderRadius: 10,
    padding: 4,
    marginBottom: 20,
    gap: 8,
  },
  modeButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  modeButtonActive: {
    backgroundColor: '#3B82F6',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
  },
  modeButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6B7280',
  },
  modeButtonTextActive: {
    color: '#FFFFFF',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#111827',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
  },
  inputContainer: {
    marginBottom: 24,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 15,
    color: '#111827',
  },
  helperText: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 6,
  },
  validationContainer: {
    marginTop: 8,
  },
  validText: {
    fontSize: 13,
    color: '#10B981',
    fontWeight: '600',
  },
  invalidText: {
    fontSize: 13,
    color: '#EF4444',
    fontWeight: '600',
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  smartBadge: {
    backgroundColor: '#DBEAFE',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  smartBadgeText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#1E40AF',
  },
  validRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  detailsExtracted: {
    fontSize: 13,
    color: '#10B981',
    fontWeight: '500',
  },
  detailsToggle: {
    marginTop: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  detailsToggleText: {
    fontSize: 13,
    color: '#6B7280',
    fontWeight: '500',
  },
  extractedDetailsBox: {
    marginTop: 8,
    padding: 12,
    backgroundColor: '#F0F9FF',
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#3B82F6',
  },
  extractedDetailsLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#1E40AF',
    marginBottom: 6,
  },
  extractedDetailsText: {
    fontSize: 13,
    lineHeight: 20,
    color: '#374151',
    marginBottom: 8,
  },
  extractedDetailsNote: {
    fontSize: 11,
    color: '#6B7280',
    fontStyle: 'italic',
  },
  button: {
    backgroundColor: '#3B82F6',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  buttonDisabled: {
    backgroundColor: '#9CA3AF',
    shadowOpacity: 0,
    elevation: 0,
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
  recentContainer: {
    marginTop: 32,
  },
  recentTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 12,
  },
  recentItem: {
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  recentText: {
    fontSize: 13,
    color: '#6B7280',
  },
  dividerContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 24,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: '#E5E7EB',
  },
  dividerText: {
    marginHorizontal: 16,
    fontSize: 13,
    color: '#9CA3AF',
    fontWeight: '600',
  },
  imageSearchContainer: {
    backgroundColor: '#F0F9FF',
    borderRadius: 12,
    padding: 20,
    borderWidth: 2,
    borderColor: '#BAE6FD',
    borderStyle: 'dashed',
    marginBottom: 24,
  },
  imageSearchTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0369A1',
    marginBottom: 8,
    textAlign: 'center',
  },
  imageSearchSubtitle: {
    fontSize: 13,
    color: '#0284C7',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 18,
  },
  loadingContainer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#0369A1',
    fontWeight: '600',
  },
  imageButtonsContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  imageButton: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#3B82F6',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
  },
  imageButtonIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  imageButtonText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#3B82F6',
  },
  invoiceContainer: {
    backgroundColor: '#F0FDF4',
    borderRadius: 12,
    padding: 20,
    borderWidth: 2,
    borderColor: '#BBF7D0',
    borderStyle: 'dashed',
    marginBottom: 24,
  },
  invoiceTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#15803D',
    marginBottom: 8,
    textAlign: 'center',
  },
  invoiceSubtitle: {
    fontSize: 13,
    color: '#16A34A',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 18,
  },
  invoiceButton: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#10B981',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
    elevation: 2,
  },
  invoiceButtonIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  invoiceButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#10B981',
  },
});


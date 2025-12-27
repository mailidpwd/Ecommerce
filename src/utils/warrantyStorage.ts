import AsyncStorage from '@react-native-async-storage/async-storage';

const WARRANTY_KEY_PREFIX = '@warranty:';
const WARRANTY_LIST_KEY = '@warranty_list';
const INVOICE_KEY_PREFIX = '@invoice:';
const INVOICE_LIST_KEY = '@invoice_list';

export interface WarrantyData {
  id: string;
  type: 'invoice' | 'warranty';
  product_name: string;
  brand: string;
  store: string;
  order_number?: string;
  order_date?: string;
  invoice_number?: string;
  packing_slip_date?: string;
  document_date?: string;
  seller_name?: string;
  seller_address?: string;
  quantity?: string;
  product_code?: string;
  model_sku_asin?: string;
  specifications?: string;
  warranty_period?: string;
  warranty_terms?: string;
  extracted_at: string;
  image_uri?: string;
  // Invoice-specific fields
  purchase_date?: string;
  price_paid?: string;
  invoice_date?: string;
  net_amount?: string;
  tax_amount?: string;
  hsn_code?: string;
  next_service_date?: string;
}

/**
 * Save warranty slip data
 */
export async function saveWarranty(warranty: WarrantyData): Promise<void> {
  try {
    // Save individual warranty
    await AsyncStorage.setItem(
      WARRANTY_KEY_PREFIX + warranty.id,
      JSON.stringify(warranty)
    );
    
    // Update warranty list
    await addToWarrantyList(warranty.id);
  } catch (error) {
    console.error('Failed to save warranty:', error);
    throw error;
  }
}

/**
 * Get warranty by ID
 */
export async function getWarranty(id: string): Promise<WarrantyData | null> {
  try {
    const warrantyJson = await AsyncStorage.getItem(WARRANTY_KEY_PREFIX + id);
    if (!warrantyJson) return null;
    return JSON.parse(warrantyJson);
  } catch (error) {
    console.error('Failed to get warranty:', error);
    return null;
  }
}

/**
 * Get all warranties and invoices (unified list)
 */
export async function getAllWarranties(): Promise<WarrantyData[]> {
  try {
    const listJson = await AsyncStorage.getItem(WARRANTY_LIST_KEY);
    if (!listJson) return [];
    
    const warrantyIds: string[] = JSON.parse(listJson);
    const warranties: WarrantyData[] = [];
    
    for (const id of warrantyIds) {
      const warranty = await getWarranty(id);
      if (warranty) {
        warranties.push(warranty);
      }
    }
    
    // Sort by extraction date (newest first)
    return warranties.sort((a, b) => 
      new Date(b.extracted_at).getTime() - new Date(a.extracted_at).getTime()
    );
  } catch (error) {
    console.error('Failed to get all warranties:', error);
    return [];
  }
}

/**
 * Delete warranty
 */
export async function deleteWarranty(id: string): Promise<void> {
  try {
    // Remove from storage
    await AsyncStorage.removeItem(WARRANTY_KEY_PREFIX + id);
    
    // Remove from list
    const listJson = await AsyncStorage.getItem(WARRANTY_LIST_KEY);
    if (listJson) {
      const warrantyIds: string[] = JSON.parse(listJson);
      const updated = warrantyIds.filter(wid => wid !== id);
      await AsyncStorage.setItem(WARRANTY_LIST_KEY, JSON.stringify(updated));
    }
  } catch (error) {
    console.error('Failed to delete warranty:', error);
    throw error;
  }
}

/**
 * Add warranty ID to list
 */
async function addToWarrantyList(id: string): Promise<void> {
  try {
    const listJson = await AsyncStorage.getItem(WARRANTY_LIST_KEY);
    const warrantyIds: string[] = listJson ? JSON.parse(listJson) : [];
    
    // Remove if already exists (to avoid duplicates)
    const filtered = warrantyIds.filter(wid => wid !== id);
    
    // Add to beginning
    const updated = [id, ...filtered];
    
    await AsyncStorage.setItem(WARRANTY_LIST_KEY, JSON.stringify(updated));
  } catch (error) {
    console.error('Failed to add to warranty list:', error);
  }
}

/**
 * Generate unique warranty ID
 */
export function generateWarrantyId(): string {
  return `warranty_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate unique invoice ID
 */
export function generateInvoiceId(): string {
  return `invoice_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Save invoice data (uses same storage as warranties for unified list)
 */
export async function saveInvoice(invoice: WarrantyData): Promise<void> {
  try {
    // Ensure type is set
    if (!invoice.type) {
      invoice.type = 'invoice';
    }
    
    // Save individual invoice
    await AsyncStorage.setItem(
      WARRANTY_KEY_PREFIX + invoice.id,
      JSON.stringify(invoice)
    );
    
    // Update warranty list (now includes invoices)
    await addToWarrantyList(invoice.id);
  } catch (error) {
    console.error('Failed to save invoice:', error);
    throw error;
  }
}

/**
 * Clear all warranties
 */
export async function clearAllWarranties(): Promise<void> {
  try {
    const listJson = await AsyncStorage.getItem(WARRANTY_LIST_KEY);
    if (listJson) {
      const warrantyIds: string[] = JSON.parse(listJson);
      const keys = warrantyIds.map(id => WARRANTY_KEY_PREFIX + id);
      await AsyncStorage.multiRemove(keys);
    }
    await AsyncStorage.removeItem(WARRANTY_LIST_KEY);
  } catch (error) {
    console.error('Failed to clear all warranties:', error);
  }
}


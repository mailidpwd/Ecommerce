export type RootStackParamList = {
  ProductInput: undefined;
  Recommendation: { url: string; shareText?: string };
  InvoiceDetails: { 
    invoiceData: {
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
    }
  };
  WarrantyDetails: { 
    warrantyData: {
      id: string;
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
    }
  };
  WarrantyList: undefined;
};


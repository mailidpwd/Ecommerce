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
    }
  };
};


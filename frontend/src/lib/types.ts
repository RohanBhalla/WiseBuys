/** Mirrors FastAPI / Pydantic responses used by the UI. */

export type UserRole = "customer" | "vendor" | "admin";

export interface UserPublic {
  id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
}

export interface TagPublic {
  id: number;
  slug: string;
  label: string;
  description: string | null;
  category: string | null;
  is_active: boolean;
}

export interface CustomerProfilePublic {
  id: number;
  user_id: number;
  primary_focus: TagPublic | null;
  secondary_focuses: TagPublic[];
  rewards_preferences: Record<string, unknown> | null;
}

export type VendorApplicationStatus =
  | "draft"
  | "submitted"
  | "needs_info"
  | "approved"
  | "rejected";

export interface VendorApplicationPublic {
  id: number;
  applicant_user_id: number;
  company_legal_name: string;
  company_website: string | null;
  contact_email: string;
  country: string | null;
  narrative: string | null;
  evidence_urls: string[] | null;
  status: VendorApplicationStatus;
  admin_notes: string | null;
  requested_tags: TagPublic[];
  submitted_at: string;
  reviewed_at: string | null;
}

export interface VendorProfilePublic {
  id: number;
  user_id: number;
  company_legal_name: string;
  company_website: string | null;
  country: string | null;
  allowed_tags: TagPublic[];
}

export interface VendorProductPublic {
  id: number;
  vendor_user_id: number;
  name: string;
  sku: string | null;
  category: string | null;
  currency: string;
  price_hint: string | number | null;
  differentiator: string | null;
  key_features: string[] | null;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export interface VendorProductSummary {
  id: number;
  vendor_user_id: number;
  name: string;
  category: string | null;
  currency: string | null;
  price_hint: string | number | null;
  differentiator: string | null;
  key_features: string[] | null;
}

export interface RecommendationItem {
  product: VendorProductSummary;
  score: number;
  reasons: string[];
  evidence_line_item_ids: number[];
}

export interface SpendingInsight {
  knot_merchant_id: number;
  merchant_name: string | null;
  currency: string | null;
  purchase_count: number;
  total_spent: number;
}

export type RewardEventType =
  | "account_linked"
  | "onboarding_complete"
  | "aligned_purchase"
  | "admin_adjustment";

export interface RewardEventPublic {
  id: number;
  event_type: RewardEventType;
  points: number;
  description: string | null;
  related_purchase_id: number | null;
  related_vendor_user_id: number | null;
  extra: Record<string, unknown> | null;
  created_at: string;
}

export interface RewardSummary {
  balance: number;
  events: RewardEventPublic[];
}

export interface MerchantAccountPublic {
  id: number;
  knot_merchant_id: number;
  merchant_name: string | null;
  connection_status: string;
  last_synced_at: string | null;
  authenticated_at: string | null;
}

export interface LineItemPublic {
  id: number;
  name: string;
  description: string | null;
  quantity: number | null;
  unit_price: string | number | null;
  total: string | number | null;
  seller_name: string | null;
}

export interface PurchasePublic {
  id: number;
  knot_transaction_id: string;
  knot_merchant_id: number;
  merchant_name: string | null;
  occurred_at: string | null;
  order_status: string | null;
  currency: string | null;
  total: string | number | null;
  url: string | null;
  line_items: LineItemPublic[];
}

export interface CreateSessionResponse {
  session_id: string;
  client_id: string;
  environment: string;
  merchant_id: number;
  external_user_id: string;
}

export interface SyncResponse {
  merchant_id: number;
  pages_fetched: number;
  transactions_seen: number;
  transactions_persisted: number;
  rewards_events_granted: number;
  rewards_points_awarded: number;
}

export interface KnotMerchantLite {
  id: number;
  name: string | null;
  logo?: string | null;
  category?: string | null;
}

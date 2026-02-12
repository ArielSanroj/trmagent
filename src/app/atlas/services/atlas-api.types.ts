// ATLAS API Types
// Extracted interfaces from atlas-api.service
// Interfaces
// ============================================================================

export interface Counterparty {
  id: string;
  company_id: string;
  name: string;
  tax_id?: string;
  country: string;
  counterparty_type: string;
  category?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  default_payment_terms: number;
  default_currency: string;
  credit_limit?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Exposure {
  id: string;
  company_id: string;
  counterparty_id?: string;
  exposure_type: 'payable' | 'receivable';
  reference: string;
  description?: string;
  currency: string;
  amount: number;
  amount_hedged: number;
  original_rate?: number;
  target_rate?: number;
  budget_rate?: number;
  invoice_date?: string;
  due_date: string;
  status: 'open' | 'partially_hedged' | 'fully_hedged' | 'settled' | 'cancelled';
  hedge_percentage: number;
  tags: string[];
  source: string;
  external_id?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  amount_open?: number;
  days_to_maturity?: number;
}

export interface ExposureSummary {
  total_payables: number;
  total_receivables: number;
  total_hedged_payables: number;
  total_hedged_receivables: number;
  net_exposure: number;
  coverage_percentage: number;
  exposures_count: number;
  by_horizon: { [key: string]: HorizonSummary };
}

export interface HorizonSummary {
  total: number;
  hedged: number;
  open: number;
  count: number;
  coverage_pct: number;
}

export interface ExposureUploadResult {
  total_rows: number;
  created: number;
  updated: number;
  errors: number;
  error_details: any[];
}

export interface HedgePolicy {
  id: string;
  company_id: string;
  name: string;
  description?: string;
  exposure_type?: 'payable' | 'receivable';
  currency: string;
  counterparty_category?: string;
  coverage_rules: { [key: string]: number };
  min_amount: number;
  max_single_exposure?: number;
  rate_tolerance_up: number;
  rate_tolerance_down: number;
  auto_generate_recommendations: boolean;
  require_approval_above?: number;
  is_active: boolean;
  is_default: boolean;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface PolicySimulationResult {
  total_exposure: number;
  would_hedge: number;
  coverage_percentage: number;
  by_horizon: { [key: string]: any };
  estimated_orders: number;
}

export interface HedgeRecommendation {
  id: string;
  company_id: string;
  exposure_id?: string;
  policy_id?: string;
  action: 'hedge_now' | 'hedge_partial' | 'wait' | 'review';
  currency: string;
  amount_to_hedge: number;
  current_coverage?: number;
  target_coverage?: number;
  current_rate?: number;
  suggested_rate?: number;
  priority: number;
  urgency: 'low' | 'normal' | 'high' | 'critical';
  days_to_maturity?: number;
  reasoning?: string;
  factors?: any;
  confidence?: number;
  status: 'pending' | 'accepted' | 'rejected' | 'expired';
  valid_until?: string;
  decided_at?: string;
  decided_by?: string;
  rejection_reason?: string;
  created_at: string;
}

export interface HedgeOrder {
  id: string;
  company_id: string;
  exposure_id?: string;
  recommendation_id?: string;
  order_type: string;
  side: 'buy' | 'sell';
  currency: string;
  amount: number;
  target_rate?: number;
  limit_rate?: number;
  market_rate_at_creation?: number;
  settlement_date?: string;
  status: string;
  requires_approval: boolean;
  approved_by?: string;
  approved_at?: string;
  bank_reference?: string;
  executed_at?: string;
  notes?: string;
  internal_reference?: string;
  created_at: string;
  updated_at: string;
}

export interface Quote {
  id: string;
  order_id: string;
  provider: string;
  provider_reference?: string;
  bid_rate?: number;
  ask_rate?: number;
  mid_rate?: number;
  spread?: number;
  amount?: number;
  currency: string;
  valid_from: string;
  valid_until?: string;
  is_accepted: boolean;
  is_expired: boolean;
  created_at: string;
}

export interface Trade {
  id: string;
  company_id: string;
  order_id?: string;
  quote_id?: string;
  trade_type: string;
  side: 'buy' | 'sell';
  currency_sold: string;
  amount_sold: number;
  currency_bought: string;
  amount_bought: number;
  executed_rate: number;
  counterparty_bank?: string;
  bank_reference?: string;
  trade_date: string;
  value_date: string;
  status: string;
  confirmation_number?: string;
  notes?: string;
  created_at: string;
}

export interface CoverageReport {
  as_of_date: string;
  total_payables: number;
  total_receivables: number;
  total_hedged_payables: number;
  total_hedged_receivables: number;
  net_exposure: number;
  payables_coverage_pct: number;
  receivables_coverage_pct: number;
  overall_coverage_pct: number;
  by_currency: { [key: string]: any };
  by_counterparty: any[];
  by_maturity: { [key: string]: any };
}

export interface MaturityLadder {
  buckets: MaturityBucket[];
  total_exposure: number;
  total_hedged: number;
  coverage_by_bucket: { [key: string]: number };
}

export interface MaturityBucket {
  start_date: string;
  end_date: string;
  total: number;
  hedged: number;
  open: number;
  coverage_pct: number;
  exposure_count: number;
  payables: number;
  receivables: number;
}

export interface DashboardSummary {
  coverage: {
    total_exposure: number;
    net_exposure: number;
    overall_coverage_pct: number;
    payables_coverage_pct: number;
    receivables_coverage_pct: number;
  };
  settlements: any;
  currency: string;
  as_of: string;
}

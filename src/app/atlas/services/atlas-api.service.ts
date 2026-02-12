/**
 * ATLAS API Service
 * Service for interacting with the ATLAS Treasury Copilot backend
 */
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

// ============================================================================
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

// ============================================================================
// Service
// ============================================================================

@Injectable({
  providedIn: 'root'
})
export class AtlasApiService {
  private baseUrl = `${environment.apiUrl || 'http://localhost:8000'}/api/v1/atlas`;

  constructor(private http: HttpClient) {}

  // ==========================================================================
  // Exposures
  // ==========================================================================

  createExposure(data: Partial<Exposure>): Observable<Exposure> {
    return this.http.post<Exposure>(`${this.baseUrl}/exposures/`, data);
  }

  uploadExposures(file: File): Observable<ExposureUploadResult> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<ExposureUploadResult>(`${this.baseUrl}/exposures/upload`, formData);
  }

  getExposures(params?: {
    exposure_type?: string;
    status?: string;
    counterparty_id?: string;
    due_date_from?: string;
    due_date_to?: string;
    currency?: string;
    skip?: number;
    limit?: number;
  }): Observable<Exposure[]> {
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          httpParams = httpParams.set(key, value.toString());
        }
      });
    }
    return this.http.get<Exposure[]>(`${this.baseUrl}/exposures/`, { params: httpParams });
  }

  getExposureSummary(currency: string = 'USD'): Observable<ExposureSummary> {
    return this.http.get<ExposureSummary>(`${this.baseUrl}/exposures/summary`, {
      params: { currency }
    });
  }

  getExposuresByHorizon(horizon: string, currency: string = 'USD'): Observable<Exposure[]> {
    return this.http.get<Exposure[]>(`${this.baseUrl}/exposures/by-horizon`, {
      params: { horizon, currency }
    });
  }

  getExposure(id: string): Observable<Exposure> {
    return this.http.get<Exposure>(`${this.baseUrl}/exposures/${id}`);
  }

  updateExposure(id: string, data: Partial<Exposure>): Observable<Exposure> {
    return this.http.put<Exposure>(`${this.baseUrl}/exposures/${id}`, data);
  }

  deleteExposure(id: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/exposures/${id}`);
  }

  // Counterparties
  getCounterparties(type?: string): Observable<Counterparty[]> {
    let params = new HttpParams();
    if (type) {
      params = params.set('counterparty_type', type);
    }
    return this.http.get<Counterparty[]>(`${this.baseUrl}/exposures/counterparties/`, { params });
  }

  createCounterparty(data: Partial<Counterparty>): Observable<Counterparty> {
    return this.http.post<Counterparty>(`${this.baseUrl}/exposures/counterparties/`, data);
  }

  // ==========================================================================
  // Policies
  // ==========================================================================

  createPolicy(data: Partial<HedgePolicy>): Observable<HedgePolicy> {
    return this.http.post<HedgePolicy>(`${this.baseUrl}/policies/`, data);
  }

  getPolicies(isActive: boolean = true): Observable<HedgePolicy[]> {
    return this.http.get<HedgePolicy[]>(`${this.baseUrl}/policies/`, {
      params: { is_active: isActive.toString() }
    });
  }

  getDefaultPolicy(): Observable<HedgePolicy> {
    return this.http.get<HedgePolicy>(`${this.baseUrl}/policies/default`);
  }

  getPolicy(id: string): Observable<HedgePolicy> {
    return this.http.get<HedgePolicy>(`${this.baseUrl}/policies/${id}`);
  }

  updatePolicy(id: string, data: Partial<HedgePolicy>): Observable<HedgePolicy> {
    return this.http.put<HedgePolicy>(`${this.baseUrl}/policies/${id}`, data);
  }

  simulatePolicy(policyId: string): Observable<PolicySimulationResult> {
    return this.http.post<PolicySimulationResult>(`${this.baseUrl}/policies/${policyId}/simulate`, {});
  }

  simulateCustomRules(rules: { [key: string]: number }): Observable<PolicySimulationResult> {
    return this.http.post<PolicySimulationResult>(`${this.baseUrl}/policies/simulate`, {
      coverage_rules: rules
    });
  }

  // ==========================================================================
  // Recommendations
  // ==========================================================================

  generateRecommendations(policyId?: string, exposureIds?: string[]): Observable<HedgeRecommendation[]> {
    return this.http.post<HedgeRecommendation[]>(`${this.baseUrl}/recommendations/generate`, {
      policy_id: policyId,
      exposure_ids: exposureIds,
      include_all_open: true
    });
  }

  getRecommendations(params?: {
    status?: string;
    action?: string;
    urgency?: string;
    include_expired?: boolean;
    skip?: number;
    limit?: number;
  }): Observable<HedgeRecommendation[]> {
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          httpParams = httpParams.set(key, value.toString());
        }
      });
    }
    return this.http.get<HedgeRecommendation[]>(`${this.baseUrl}/recommendations/`, { params: httpParams });
  }

  getPendingRecommendations(): Observable<HedgeRecommendation[]> {
    return this.http.get<HedgeRecommendation[]>(`${this.baseUrl}/recommendations/pending`);
  }

  getRecommendationsCalendar(days: number = 30): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}/recommendations/calendar`, {
      params: { days: days.toString() }
    });
  }

  getRecommendationsSummary(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/recommendations/summary`);
  }

  getRecommendation(id: string): Observable<HedgeRecommendation> {
    return this.http.get<HedgeRecommendation>(`${this.baseUrl}/recommendations/${id}`);
  }

  acceptRecommendation(id: string): Observable<HedgeRecommendation> {
    return this.http.post<HedgeRecommendation>(`${this.baseUrl}/recommendations/${id}/accept`, {});
  }

  rejectRecommendation(id: string, reason?: string): Observable<HedgeRecommendation> {
    return this.http.post<HedgeRecommendation>(`${this.baseUrl}/recommendations/${id}/reject`, {
      rejection_reason: reason
    });
  }

  // ==========================================================================
  // Orders
  // ==========================================================================

  createOrder(data: Partial<HedgeOrder>): Observable<HedgeOrder> {
    return this.http.post<HedgeOrder>(`${this.baseUrl}/orders/`, data);
  }

  createOrderFromRecommendation(recommendationId: string, orderType: string = 'spot'): Observable<HedgeOrder> {
    return this.http.post<HedgeOrder>(
      `${this.baseUrl}/orders/from-recommendation/${recommendationId}`,
      null,
      { params: { order_type: orderType } }
    );
  }

  getOrders(params?: {
    status?: string;
    exposure_id?: string;
    skip?: number;
    limit?: number;
  }): Observable<HedgeOrder[]> {
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          httpParams = httpParams.set(key, value.toString());
        }
      });
    }
    return this.http.get<HedgeOrder[]>(`${this.baseUrl}/orders/`, { params: httpParams });
  }

  getOrdersSummary(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/orders/summary`);
  }

  getOrder(id: string): Observable<HedgeOrder> {
    return this.http.get<HedgeOrder>(`${this.baseUrl}/orders/${id}`);
  }

  updateOrder(id: string, data: Partial<HedgeOrder>): Observable<HedgeOrder> {
    return this.http.put<HedgeOrder>(`${this.baseUrl}/orders/${id}`, data);
  }

  approveOrder(id: string): Observable<HedgeOrder> {
    return this.http.post<HedgeOrder>(`${this.baseUrl}/orders/${id}/approve`, {});
  }

  rejectOrder(id: string, reason?: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/orders/${id}/reject`, null, {
      params: reason ? { reason } : {}
    });
  }

  cancelOrder(id: string, reason?: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/orders/${id}/cancel`, null, {
      params: reason ? { reason } : {}
    });
  }

  addQuote(orderId: string, data: Partial<Quote>): Observable<Quote> {
    return this.http.post<Quote>(`${this.baseUrl}/orders/${orderId}/quotes/`, data);
  }

  acceptQuote(orderId: string, quoteId: string): Observable<Quote> {
    return this.http.post<Quote>(`${this.baseUrl}/orders/${orderId}/quotes/${quoteId}/accept`, {});
  }

  executeOrder(orderId: string, tradeData: Partial<Trade>): Observable<Trade> {
    return this.http.post<Trade>(`${this.baseUrl}/orders/${orderId}/execute`, tradeData);
  }

  // ==========================================================================
  // Reports
  // ==========================================================================

  getCoverageReport(asOfDate?: string, currency: string = 'USD'): Observable<CoverageReport> {
    let params = new HttpParams().set('currency', currency);
    if (asOfDate) {
      params = params.set('as_of_date', asOfDate);
    }
    return this.http.get<CoverageReport>(`${this.baseUrl}/reports/coverage`, { params });
  }

  getMaturityLadder(currency: string = 'USD', bucketDays: number = 7): Observable<MaturityLadder> {
    return this.http.get<MaturityLadder>(`${this.baseUrl}/reports/maturity-ladder`, {
      params: { currency, bucket_days: bucketDays.toString() }
    });
  }

  getCostAnalysis(startDate: string, endDate: string, currency: string = 'USD'): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/reports/cost-analysis`, {
      params: { start_date: startDate, end_date: endDate, currency }
    });
  }

  getSettlementCalendar(days: number = 30): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/reports/settlement-calendar`, {
      params: { days: days.toString() }
    });
  }

  getSettlementSummary(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/reports/settlement-summary`);
  }

  getDashboard(currency: string = 'USD'): Observable<DashboardSummary> {
    return this.http.get<DashboardSummary>(`${this.baseUrl}/reports/dashboard`, {
      params: { currency }
    });
  }

  exportReport(reportType: string, format: string = 'xlsx', startDate?: string, endDate?: string): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/reports/export`, {
      report_type: reportType,
      format: format,
      start_date: startDate,
      end_date: endDate
    }, { responseType: 'blob' });
  }
}

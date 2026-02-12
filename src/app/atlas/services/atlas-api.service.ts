import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Counterparty,
  CoverageReport,
  DashboardSummary,
  Exposure,
  ExposureSummary,
  ExposureUploadResult,
  HedgeOrder,
  HedgePolicy,
  HedgeRecommendation,
  HorizonSummary,
  MaturityBucket,
  MaturityLadder,
  PolicySimulationResult,
  Quote,
  Trade
} from './atlas-api.types';

@Injectable({
  providedIn: 'root'
})
export class AtlasApiService {
  private baseUrl = `${environment.apiUrl || 'http://localhost:8000'}/api/v1/atlas`;

  constructor(private http: HttpClient) {}

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

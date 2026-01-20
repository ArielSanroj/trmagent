/**
 * API Service - Conexion con Backend Python
 */
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError, BehaviorSubject } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';

export interface TRMData {
  date: string;
  value: number;
  change_pct?: number;
  source: string;
}

export interface Prediction {
  id: string;
  target_date: string;
  predicted_value: number;
  lower_bound: number;
  upper_bound: number;
  confidence: number;
  model_type: string;
  trend: 'ALCISTA' | 'BAJISTA' | 'NEUTRAL';
}

export interface TradingSignal {
  id: string;
  action: 'BUY_USD' | 'SELL_USD' | 'HOLD';
  confidence: number;
  predicted_trm: number;
  current_trm: number;
  expected_return: number;
  risk_score: number;
  reasoning: string;
  status: string;
  approved: boolean;
}

export interface PortfolioSummary {
  total_usd: number;
  total_cop: number;
  total_value_cop: number;
  unrealized_pnl: number;
  realized_pnl: number;
  daily_pnl: number;
  open_positions: number;
}

export interface BacktestResult {
  id: string;
  strategy_name: string;
  model_type: string;
  start_date: string;
  end_date: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  final_capital?: number;
  profitable_trades?: number;
  avg_trade_return?: number;
}

export interface MarketIndicators {
  trm_current: number;
  oil_wti: number;
  oil_brent: number;
  fed_rate: number;
  banrep_rate: number;
  inflation_col: number;
  inflation_usa: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  company_id?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = environment.apiUrl || 'http://localhost:8000/api/v1';
  private tokenSubject = new BehaviorSubject<string | null>(localStorage.getItem('token'));

  constructor(private http: HttpClient) {}

  // ==================== AUTH ====================

  private getHeaders(): HttpHeaders {
    const token = this.tokenSubject.value;
    let headers = new HttpHeaders({ 'Content-Type': 'application/json' });
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }
    return headers;
  }

  login(email: string, password: string): Observable<any> {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);

    return this.http.post(`${this.baseUrl}/auth/login`, formData).pipe(
      tap((response: any) => {
        localStorage.setItem('token', response.access_token);
        this.tokenSubject.next(response.access_token);
      }),
      catchError(this.handleError)
    );
  }

  register(email: string, password: string, fullName: string): Observable<User> {
    return this.http.post<User>(`${this.baseUrl}/auth/register`, {
      email, password, full_name: fullName
    }).pipe(catchError(this.handleError));
  }

  logout(): void {
    localStorage.removeItem('token');
    this.tokenSubject.next(null);
  }

  isLoggedIn(): boolean {
    return !!this.tokenSubject.value;
  }

  getCurrentUser(): Observable<User> {
    return this.http.get<User>(`${this.baseUrl}/auth/me`, {
      headers: this.getHeaders()
    }).pipe(catchError(this.handleError));
  }

  // ==================== MARKET DATA ====================

  getCurrentTRM(): Observable<TRMData> {
    return this.http.get<TRMData>(`${this.baseUrl}/market/trm/current`).pipe(
      catchError(this.handleError)
    );
  }

  getTRMHistory(days: number = 30): Observable<{ data: TRMData[], count: number }> {
    return this.http.get<{ data: TRMData[], count: number }>(
      `${this.baseUrl}/market/trm/history?days=${days}`
    ).pipe(catchError(this.handleError));
  }

  getMarketIndicators(): Observable<MarketIndicators> {
    return this.http.get<MarketIndicators>(`${this.baseUrl}/market/indicators`).pipe(
      catchError(this.handleError)
    );
  }

  // ==================== PREDICTIONS ====================

  getCurrentPrediction(): Observable<Prediction> {
    return this.http.get<Prediction>(`${this.baseUrl}/predictions/current`).pipe(
      catchError(this.handleError)
    );
  }

  getForecast(days: number = 30): Observable<{ predictions: Prediction[], summary: any }> {
    return this.http.get<{ predictions: Prediction[], summary: any }>(
      `${this.baseUrl}/predictions/forecast?days=${days}`
    ).pipe(catchError(this.handleError));
  }

  generatePredictions(daysAhead: number = 30, modelType: string = 'ensemble'): Observable<any> {
    return this.http.post(`${this.baseUrl}/predictions/generate`, {
      days_ahead: daysAhead,
      model_type: modelType
    }, { headers: this.getHeaders() }).pipe(catchError(this.handleError));
  }

  // ==================== TRADING ====================

  getCurrentSignal(): Observable<{ signal: TradingSignal, recommendation: string }> {
    return this.http.get<{ signal: TradingSignal, recommendation: string }>(
      `${this.baseUrl}/trading/signals/current`,
      { headers: this.getHeaders() }
    ).pipe(catchError(this.handleError));
  }

  evaluateAndNotify(): Observable<any> {
    return this.http.post(`${this.baseUrl}/trading/signals/evaluate`, {}, {
      headers: this.getHeaders()
    }).pipe(catchError(this.handleError));
  }

  getSignalHistory(limit: number = 50): Observable<{ signals: TradingSignal[], count: number }> {
    return this.http.get<{ signals: TradingSignal[], count: number }>(
      `${this.baseUrl}/trading/signals/history?limit=${limit}`,
      { headers: this.getHeaders() }
    ).pipe(catchError(this.handleError));
  }

  createOrder(side: 'buy' | 'sell', amount: number, isPaperTrade: boolean = true): Observable<any> {
    return this.http.post(`${this.baseUrl}/trading/orders/create`, {
      side, amount, is_paper_trade: isPaperTrade, order_type: 'market'
    }, { headers: this.getHeaders() }).pipe(catchError(this.handleError));
  }

  getPortfolioSummary(): Observable<PortfolioSummary> {
    return this.http.get<PortfolioSummary>(
      `${this.baseUrl}/trading/portfolio/summary`,
      { headers: this.getHeaders() }
    ).pipe(catchError(this.handleError));
  }

  resetPortfolio(): Observable<any> {
    return this.http.post(`${this.baseUrl}/trading/portfolio/reset`, {}, {
      headers: this.getHeaders()
    }).pipe(catchError(this.handleError));
  }

  // ==================== BACKTESTING ====================

  runBacktest(config: {
    strategy: string;
    model_type: string;
    start_date: string;
    end_date: string;
    initial_capital?: number;
    min_confidence?: number;
  }): Observable<BacktestResult> {
    return this.http.post<BacktestResult>(`${this.baseUrl}/backtesting/run`, config, {
      headers: this.getHeaders()
    }).pipe(catchError(this.handleError));
  }

  getBacktestHistory(limit: number = 20): Observable<{ backtests: BacktestResult[], count: number }> {
    return this.http.get<{ backtests: BacktestResult[], count: number }>(
      `${this.baseUrl}/backtesting/history?limit=${limit}`,
      { headers: this.getHeaders() }
    ).pipe(catchError(this.handleError));
  }

  compareStrategies(days: number = 365): Observable<any> {
    return this.http.get<any>(
      `${this.baseUrl}/backtesting/compare?days=${days}`,
      { headers: this.getHeaders() }
    ).pipe(catchError(this.handleError));
  }

  // ==================== ERROR HANDLING ====================

  private handleError(error: HttpErrorResponse): Observable<never> {
    let errorMessage = 'Error desconocido';

    if (error.error instanceof ErrorEvent) {
      errorMessage = `Error: ${error.error.message}`;
    } else {
      errorMessage = `Error ${error.status}: ${error.error?.detail || error.message}`;
    }

    console.error('API Error:', errorMessage);
    return throwError(() => new Error(errorMessage));
  }
}

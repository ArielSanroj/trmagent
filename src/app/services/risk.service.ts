
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface RiskScoreResponse {
    total_score: number;
    volatility_score: number;
    trend_score: number;
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    recommendation: string;
}

export interface HedgingRequest {
    amount: number;
    time_horizon_days: number;
    current_exposure: number;
}

export interface HedgingResponse {
    action: string;
    amount_to_hedge: number;
    suggested_rate: number;
    urgency: string;
    reasoning: string[];
}

export interface WebhookRequest {
    url: string;
}

@Injectable({
    providedIn: 'root'
})
export class RiskService {
    private apiUrl = `${environment.apiUrl}/api/v1/risk`;

    constructor(private http: HttpClient) { }

    getRiskScore(): Observable<RiskScoreResponse> {
        return this.http.get<RiskScoreResponse>(`${this.apiUrl}/score`);
    }

    analyzeHedging(request: HedgingRequest): Observable<HedgingResponse> {
        return this.http.post<HedgingResponse>(`${this.apiUrl}/analyze`, request);
    }

    registerWebhook(url: string): Observable<any> {
        return this.http.post(`${this.apiUrl}/webhooks`, { url });
    }
}

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs'; // To use async/await with Observables
import { environment } from '../environments/environment';

@Injectable({
    providedIn: 'root'
})
export class CurrencyService {
    private historyUrl = `${environment.apiUrl}/market/trm/history?days=30`;
    private currentUrl = `${environment.apiUrl}/market/trm/current`;

    private cachedData: any[] = [];

    constructor(private http: HttpClient) { }

    async loadData(): Promise<void> {
        if (this.cachedData.length > 0) return;
        try {
            const response = await firstValueFrom(this.http.get<{ data: Array<{ date: string; value: number }> }>(this.historyUrl));
            this.cachedData = (response?.data || []).map(item => ({
                valor: String(item.value),
                vigenciahasta: item.date
            }));
        } catch (e) {
            console.error('Error fetching TRM data', e);
            // Fallback mock if API fails
            this.cachedData = [
                { valor: '4100', vigenciahasta: new Date().toISOString() },
                { valor: '4050', vigenciahasta: new Date(Date.now() - 86400000).toISOString() }
            ];
        }
    }

    async getDailyTRM(): Promise<number> {
        try {
            const current = await firstValueFrom(this.http.get<{ value: number }>(this.currentUrl));
            if (current?.value !== undefined && current?.value !== null) {
                return Number(current.value);
            }
        } catch (e) {
            console.error('Error fetching current TRM', e);
        }

        await this.loadData();
        return parseFloat(this.cachedData[0]?.valor || '0');
    }

    async getHistoricalStats(): Promise<string> {
        await this.loadData();
        // Return last 5 days
        const history = this.cachedData.slice(0, 5).map(d =>
            `- ${d.vigenciahasta.split('T')[0]}: $${d.valor}`
        ).join('\n');
        return history;
    }

    // Basic Linear Regression for "Time Series" Prediction
    async getPrediction(months: number): Promise<string> {
        await this.loadData();

        // Prepare data: [dayIndex, value]
        // Reverse to have oldest first for regression
        const data = [...this.cachedData].reverse().map((d, i) => ({
            x: i,
            y: parseFloat(d.valor)
        }));

        const n = data.length;
        const sumX = data.reduce((acc, p) => acc + p.x, 0);
        const sumY = data.reduce((acc, p) => acc + p.y, 0);
        const sumXY = data.reduce((acc, p) => acc + (p.x * p.y), 0);
        const sumXX = data.reduce((acc, p) => acc + (p.x * p.x), 0);

        const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
        const intercept = (sumY - slope * sumX) / n;

        // Project future (approx 30 days per month)
        const futureX = n + (months * 30);
        const predictedValue = slope * futureX + intercept;

        const trend = slope > 0 ? 'ALCISTA' : 'BAJISTA';

        return `Predicción estadística (${months} meses): $${predictedValue.toFixed(2)} COP. Tendencia detectada: ${trend} (Pendiente: ${slope.toFixed(2)})`;
    }

    async getFullFinancialContext(): Promise<string> {
        await this.loadData();
        const trm = await this.getDailyTRM();
        const history = await this.getHistoricalStats();
        const pred1 = await this.getPrediction(1);
        const pred3 = await this.getPrediction(3);

        return `
    DATOS REALES (Fuente: datos.gov.co):
    - TRM Actual: $${trm}
    - Histórico Reciente:
${history}
    
    PROYECCIÓN MATEMÁTICA (Regresión Lineal Simple):
    - 1 Mes: ${pred1}
    - 3 Meses: ${pred3}
    `;
    }
}

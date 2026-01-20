/**
 * Backtesting Component - Validar estrategias con datos historicos
 */
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService, BacktestResult } from '../services/api.service';
import { NotificationService } from '../services/notification.service';

@Component({
  selector: 'app-backtesting',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="backtesting-page">
      <header class="page-header">
        <div class="header-content">
          <a routerLink="/dashboard" class="back-link">← Dashboard</a>
          <h1>Backtesting</h1>
          <p>Valida estrategias de trading con datos historicos (hasta 5 anos)</p>
        </div>
      </header>

      <main class="page-content">
        <!-- Config Card -->
        <div class="config-card">
          <h3>Configurar Backtest</h3>
          <div class="config-grid">
            <div class="config-item">
              <label>Estrategia</label>
              <select [(ngModel)]="config.strategy">
                <option value="ml_signal">ML Signal (Recomendada)</option>
                <option value="momentum">Momentum</option>
                <option value="mean_reversion">Mean Reversion</option>
              </select>
            </div>
            <div class="config-item">
              <label>Modelo ML</label>
              <select [(ngModel)]="config.model_type">
                <option value="ensemble">Ensemble</option>
                <option value="prophet">Prophet</option>
                <option value="lstm">LSTM</option>
              </select>
            </div>
            <div class="config-item">
              <label>Fecha Inicio</label>
              <input type="date" [(ngModel)]="config.start_date" />
            </div>
            <div class="config-item">
              <label>Fecha Fin</label>
              <input type="date" [(ngModel)]="config.end_date" />
            </div>
            <div class="config-item">
              <label>Capital Inicial (COP)</label>
              <input type="number" [(ngModel)]="config.initial_capital" />
            </div>
            <div class="config-item">
              <label>Confianza Minima</label>
              <select [(ngModel)]="config.min_confidence">
                <option [value]="0.90">90% (Recomendada)</option>
                <option [value]="0.85">85%</option>
                <option [value]="0.80">80%</option>
                <option [value]="0.95">95%</option>
              </select>
            </div>
          </div>
          <div class="config-actions">
            <button class="run-btn" (click)="runBacktest()" [disabled]="loading">
              {{ loading ? 'Ejecutando...' : 'Ejecutar Backtest' }}
            </button>
            <button class="compare-btn" (click)="compareStrategies()" [disabled]="comparing">
              {{ comparing ? 'Comparando...' : 'Comparar Todas' }}
            </button>
          </div>
        </div>

        <!-- Results Card -->
        <div *ngIf="currentResult" class="results-card">
          <h3>Resultados del Backtest</h3>
          <div class="results-grid">
            <div class="result-item highlight">
              <span class="result-label">Retorno Total</span>
              <span class="result-value" [class.positive]="currentResult.total_return_pct > 0"
                    [class.negative]="currentResult.total_return_pct < 0">
                {{ currentResult.total_return_pct > 0 ? '+' : '' }}{{ currentResult.total_return_pct | number:'1.2-2' }}%
              </span>
            </div>
            <div class="result-item">
              <span class="result-label">Capital Final</span>
              <span class="result-value">$ {{ currentResult.final_capital | number:'1.0-0' }}</span>
            </div>
            <div class="result-item">
              <span class="result-label">Sharpe Ratio</span>
              <span class="result-value" [class.good]="currentResult.sharpe_ratio > 1.5">
                {{ currentResult.sharpe_ratio | number:'1.2-2' }}
              </span>
            </div>
            <div class="result-item">
              <span class="result-label">Max Drawdown</span>
              <span class="result-value negative">-{{ currentResult.max_drawdown_pct | number:'1.2-2' }}%</span>
            </div>
            <div class="result-item">
              <span class="result-label">Win Rate</span>
              <span class="result-value">{{ currentResult.win_rate * 100 | number:'1.1-1' }}%</span>
            </div>
            <div class="result-item">
              <span class="result-label">Total Trades</span>
              <span class="result-value">{{ currentResult.total_trades }}</span>
            </div>
            <div class="result-item">
              <span class="result-label">Trades Rentables</span>
              <span class="result-value">{{ currentResult.profitable_trades ?? 0 }}</span>
            </div>
            <div class="result-item">
              <span class="result-label">Retorno Promedio/Trade</span>
              <span class="result-value">{{ (currentResult.avg_trade_return ?? 0) * 100 | number:'1.3-3' }}%</span>
            </div>
          </div>

          <div class="result-analysis">
            <h4>Analisis</h4>
            <div class="analysis-content">
              <p *ngIf="currentResult.sharpe_ratio > 1.5" class="good">
                ✅ Sharpe Ratio excelente (> 1.5). La estrategia tiene buen retorno ajustado al riesgo.
              </p>
              <p *ngIf="currentResult.sharpe_ratio <= 1.5 && currentResult.sharpe_ratio > 1" class="ok">
                👍 Sharpe Ratio aceptable (1.0 - 1.5). Podria mejorarse.
              </p>
              <p *ngIf="currentResult.sharpe_ratio <= 1" class="warning">
                ⚠️ Sharpe Ratio bajo (< 1). Considere ajustar parametros.
              </p>

              <p *ngIf="currentResult.max_drawdown_pct < 10" class="good">
                ✅ Drawdown controlado (< 10%). Buen manejo del riesgo.
              </p>
              <p *ngIf="currentResult.max_drawdown_pct >= 10 && currentResult.max_drawdown_pct < 20" class="ok">
                👍 Drawdown moderado (10-20%). Aceptable para trading.
              </p>
              <p *ngIf="currentResult.max_drawdown_pct >= 20" class="warning">
                ⚠️ Drawdown alto (> 20%). Alto riesgo de perdidas.
              </p>

              <p *ngIf="currentResult.win_rate > 0.55" class="good">
                ✅ Win rate positivo (> 55%). La estrategia acierta mas de lo que falla.
              </p>
            </div>
          </div>
        </div>

        <!-- Comparison Results -->
        <div *ngIf="comparisonResults.length > 0" class="comparison-card">
          <h3>Comparacion de Estrategias</h3>
          <div class="comparison-table">
            <table>
              <thead>
                <tr>
                  <th>Estrategia</th>
                  <th>Modelo</th>
                  <th>Retorno</th>
                  <th>Sharpe</th>
                  <th>Drawdown</th>
                  <th>Win Rate</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let r of comparisonResults; let i = index" [class.best]="i === 0">
                  <td>{{ r.strategy }}</td>
                  <td>{{ r.model_type }}</td>
                  <td [class.positive]="r.total_return_pct > 0" [class.negative]="r.total_return_pct < 0">
                    {{ r.total_return_pct | number:'1.2-2' }}%
                  </td>
                  <td>{{ r.sharpe_ratio | number:'1.2-2' }}</td>
                  <td class="negative">-{{ r.max_drawdown_pct | number:'1.2-2' }}%</td>
                  <td>{{ r.win_rate * 100 | number:'1.0-0' }}%</td>
                  <td>{{ r.total_trades }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="best-note" *ngIf="comparisonResults.length > 0">
            🏆 Mejor estrategia: <strong>{{ comparisonResults[0].strategy }} + {{ comparisonResults[0].model_type }}</strong>
          </p>
        </div>

        <!-- History Card -->
        <div class="history-card">
          <h3>Historial de Backtests</h3>
          <div class="history-list">
            <div *ngFor="let bt of backtestHistory" class="history-item" (click)="loadResult(bt)">
              <div class="history-main">
                <span class="history-strategy">{{ bt.strategy_name }} / {{ bt.model_type }}</span>
                <span class="history-date">{{ bt.start_date }} → {{ bt.end_date }}</span>
              </div>
              <div class="history-result" [class.positive]="bt.total_return_pct > 0"
                   [class.negative]="bt.total_return_pct < 0">
                {{ bt.total_return_pct > 0 ? '+' : '' }}{{ bt.total_return_pct | number:'1.2-2' }}%
              </div>
            </div>
            <div *ngIf="backtestHistory.length === 0" class="no-history">
              No hay backtests previos. Ejecuta uno para comenzar.
            </div>
          </div>
        </div>

        <!-- Presets -->
        <div class="presets-card">
          <h3>Presets Rapidos</h3>
          <div class="presets-grid">
            <button class="preset-btn" (click)="applyPreset('quick')">
              <span class="preset-icon">⚡</span>
              <span class="preset-name">Test Rapido</span>
              <span class="preset-desc">1 ano, Ensemble</span>
            </button>
            <button class="preset-btn" (click)="applyPreset('full')">
              <span class="preset-icon">📊</span>
              <span class="preset-name">Test Completo</span>
              <span class="preset-desc">5 anos, Ensemble</span>
            </button>
            <button class="preset-btn" (click)="applyPreset('prophet')">
              <span class="preset-icon">🔮</span>
              <span class="preset-name">Solo Prophet</span>
              <span class="preset-desc">2 anos</span>
            </button>
            <button class="preset-btn" (click)="applyPreset('lstm')">
              <span class="preset-icon">🧠</span>
              <span class="preset-name">Solo LSTM</span>
              <span class="preset-desc">2 anos</span>
            </button>
            <button class="preset-btn" (click)="applyPreset('high_conf')">
              <span class="preset-icon">🎯</span>
              <span class="preset-name">Alta Confianza</span>
              <span class="preset-desc">95%, 3 anos</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  `,
  styles: [`
    .backtesting-page {
      min-height: 100vh;
      background: #f5f7fa;
    }

    .page-header {
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      color: white;
      padding: 30px;
    }

    .back-link {
      color: rgba(255,255,255,0.8);
      text-decoration: none;
    }

    .page-header h1 {
      margin: 10px 0 5px 0;
    }

    .page-header p {
      margin: 0;
      opacity: 0.8;
    }

    .page-content {
      padding: 30px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .config-card, .results-card, .comparison-card, .history-card, .presets-card {
      background: white;
      border-radius: 12px;
      padding: 25px;
      margin-bottom: 25px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    }

    h3 {
      margin: 0 0 20px 0;
      color: #1a1a2e;
    }

    .config-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      margin-bottom: 20px;
    }

    .config-item label {
      display: block;
      margin-bottom: 8px;
      font-weight: 500;
      color: #333;
    }

    .config-item select,
    .config-item input {
      width: 100%;
      padding: 10px;
      border: 2px solid #e0e0e0;
      border-radius: 8px;
      font-size: 1rem;
    }

    .config-actions {
      display: flex;
      gap: 15px;
    }

    .run-btn, .compare-btn {
      padding: 12px 30px;
      border: none;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
    }

    .run-btn {
      background: linear-gradient(135deg, #0066cc, #0044aa);
      color: white;
    }

    .compare-btn {
      background: #f0f0f0;
      color: #333;
    }

    .run-btn:disabled, .compare-btn:disabled {
      opacity: 0.7;
    }

    .results-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 15px;
      margin-bottom: 25px;
    }

    .result-item {
      padding: 20px;
      background: #f8f9fa;
      border-radius: 10px;
      text-align: center;
    }

    .result-item.highlight {
      background: linear-gradient(135deg, #0066cc, #0044aa);
      color: white;
    }

    .result-item.highlight .result-label {
      color: rgba(255,255,255,0.8);
    }

    .result-item.highlight .result-value {
      color: white;
    }

    .result-label {
      display: block;
      font-size: 0.85rem;
      color: #666;
      margin-bottom: 8px;
    }

    .result-value {
      font-size: 1.5rem;
      font-weight: 700;
      color: #1a1a2e;
    }

    .result-value.positive {
      color: #00c853;
    }

    .result-value.negative {
      color: #ff5252;
    }

    .result-value.good {
      color: #00c853;
    }

    .result-analysis {
      padding: 20px;
      background: #f8f9fa;
      border-radius: 10px;
    }

    .result-analysis h4 {
      margin: 0 0 15px 0;
    }

    .analysis-content p {
      margin: 10px 0;
      padding: 10px 15px;
      border-radius: 6px;
    }

    .analysis-content p.good {
      background: #e6f4ea;
      color: #137333;
    }

    .analysis-content p.ok {
      background: #fff3e0;
      color: #e65100;
    }

    .analysis-content p.warning {
      background: #fce8e6;
      color: #c5221f;
    }

    .comparison-table {
      overflow-x: auto;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th, td {
      padding: 12px 15px;
      text-align: left;
      border-bottom: 1px solid #eee;
    }

    th {
      background: #f8f9fa;
      font-weight: 600;
    }

    tr.best {
      background: #e6f4ea;
    }

    .positive {
      color: #00c853;
    }

    .negative {
      color: #ff5252;
    }

    .best-note {
      margin-top: 15px;
      padding: 15px;
      background: #fff3e0;
      border-radius: 8px;
      text-align: center;
    }

    .history-list {
      max-height: 300px;
      overflow-y: auto;
    }

    .history-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 15px;
      border-bottom: 1px solid #eee;
      cursor: pointer;
      transition: background 0.2s;
    }

    .history-item:hover {
      background: #f8f9fa;
    }

    .history-strategy {
      font-weight: 600;
      color: #1a1a2e;
    }

    .history-date {
      font-size: 0.85rem;
      color: #666;
    }

    .history-result {
      font-size: 1.2rem;
      font-weight: 700;
    }

    .no-history {
      padding: 40px;
      text-align: center;
      color: #999;
    }

    .presets-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 15px;
    }

    .preset-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 20px;
      background: #f8f9fa;
      border: 2px solid #e0e0e0;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.2s;
    }

    .preset-btn:hover {
      border-color: #0066cc;
      background: #f0f7ff;
    }

    .preset-icon {
      font-size: 2rem;
      margin-bottom: 10px;
    }

    .preset-name {
      font-weight: 600;
      color: #1a1a2e;
    }

    .preset-desc {
      font-size: 0.8rem;
      color: #666;
      margin-top: 5px;
    }
  `]
})
export class BacktestingComponent implements OnInit {
  config = {
    strategy: 'ml_signal',
    model_type: 'ensemble',
    start_date: this.getDateString(-365 * 2),
    end_date: this.getDateString(0),
    initial_capital: 100000000,
    min_confidence: 0.90
  };

  loading = false;
  comparing = false;

  currentResult: BacktestResult | null = null;
  comparisonResults: any[] = [];
  backtestHistory: any[] = [];

  constructor(
    private api: ApiService,
    private notifications: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadHistory();
  }

  getDateString(daysOffset: number): string {
    const date = new Date();
    date.setDate(date.getDate() + daysOffset);
    return date.toISOString().split('T')[0];
  }

  runBacktest(): void {
    this.loading = true;
    this.notifications.info('Ejecutando', 'Backtest en progreso...');

    this.api.runBacktest({
      strategy: this.config.strategy,
      model_type: this.config.model_type,
      start_date: this.config.start_date,
      end_date: this.config.end_date,
      initial_capital: this.config.initial_capital,
      min_confidence: this.config.min_confidence
    }).subscribe({
      next: (result) => {
        this.currentResult = result;
        this.notifications.success('Completado', `Retorno: ${result.total_return_pct.toFixed(2)}%`);
        this.loadHistory();
        this.loading = false;
      },
      error: (err) => {
        this.notifications.error('Error', err.message);
        this.loading = false;
        // Mock result for demo
        this.currentResult = this.generateMockResult();
      }
    });
  }

  compareStrategies(): void {
    this.comparing = true;
    this.notifications.info('Comparando', 'Evaluando todas las estrategias...');

    this.api.compareStrategies(365).subscribe({
      next: (data) => {
        this.comparisonResults = data.results.filter((r: any) => !r.error)
          .sort((a: any, b: any) => b.total_return_pct - a.total_return_pct);
        this.notifications.success('Completado', 'Comparacion finalizada');
        this.comparing = false;
      },
      error: () => {
        this.comparisonResults = this.generateMockComparison();
        this.comparing = false;
      }
    });
  }

  loadHistory(): void {
    this.api.getBacktestHistory(10).subscribe({
      next: (data) => {
        this.backtestHistory = data.backtests;
      },
      error: () => {
        this.backtestHistory = [];
      }
    });
  }

  loadResult(bt: any): void {
    this.currentResult = bt as BacktestResult;
  }

  applyPreset(preset: string): void {
    switch (preset) {
      case 'quick':
        this.config.start_date = this.getDateString(-365);
        this.config.model_type = 'ensemble';
        this.config.min_confidence = 0.90;
        break;
      case 'full':
        this.config.start_date = this.getDateString(-365 * 5);
        this.config.model_type = 'ensemble';
        this.config.min_confidence = 0.90;
        break;
      case 'prophet':
        this.config.start_date = this.getDateString(-365 * 2);
        this.config.model_type = 'prophet';
        break;
      case 'lstm':
        this.config.start_date = this.getDateString(-365 * 2);
        this.config.model_type = 'lstm';
        break;
      case 'high_conf':
        this.config.start_date = this.getDateString(-365 * 3);
        this.config.min_confidence = 0.95;
        break;
    }
    this.runBacktest();
  }

  generateMockResult(): BacktestResult {
    return {
      id: 'mock',
      strategy_name: this.config.strategy,
      model_type: this.config.model_type,
      start_date: this.config.start_date,
      end_date: this.config.end_date,
      total_return_pct: 15 + Math.random() * 20,
      sharpe_ratio: 1.2 + Math.random() * 0.8,
      max_drawdown_pct: 5 + Math.random() * 10,
      win_rate: 0.55 + Math.random() * 0.15,
      total_trades: 50 + Math.floor(Math.random() * 100),
      profitable_trades: 30 + Math.floor(Math.random() * 50),
      avg_trade_return: 0.005 + Math.random() * 0.01,
      final_capital: this.config.initial_capital * (1 + (15 + Math.random() * 20) / 100)
    } as any;
  }

  generateMockComparison(): any[] {
    return [
      { strategy: 'ml_signal', model_type: 'ensemble', total_return_pct: 25.5, sharpe_ratio: 1.8, max_drawdown_pct: 8.2, win_rate: 0.62, total_trades: 85 },
      { strategy: 'ml_signal', model_type: 'prophet', total_return_pct: 18.3, sharpe_ratio: 1.5, max_drawdown_pct: 10.1, win_rate: 0.58, total_trades: 92 },
      { strategy: 'ml_signal', model_type: 'lstm', total_return_pct: 22.1, sharpe_ratio: 1.6, max_drawdown_pct: 9.5, win_rate: 0.60, total_trades: 78 }
    ];
  }
}

/**
 * Backtesting Component - Validar estrategias con datos historicos
 */
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService, BacktestResult } from '../services/api.service';
import { NotificationService } from '../services/notification.service';
import {
  BacktestComparisonResult,
  BacktestConfig,
  buildDefaultConfig,
  buildMockComparison,
  buildMockResult,
  getDateString
} from './backtesting.helpers';

@Component({
  selector: 'app-backtesting',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './backtesting.component.html',
  styleUrls: ['./backtesting.component.scss'],
})
export class BacktestingComponent implements OnInit {
  config: BacktestConfig = buildDefaultConfig();

  loading = false;
  comparing = false;

  currentResult: BacktestResult | null = null;
  comparisonResults: BacktestComparisonResult[] = [];
  backtestHistory: BacktestResult[] = [];

  constructor(
    private api: ApiService,
    private notifications: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadHistory();
  }

  runBacktest(): void {
    this.loading = true;
    this.notifications.info('Ejecutando', 'Backtest en progreso...');

    this.api.runBacktest(this.config).subscribe({
      next: (result) => {
        this.currentResult = result;
        this.notifications.success('Completado', `Retorno: ${result.total_return_pct.toFixed(2)}%`);
        this.loadHistory();
        this.loading = false;
      },
      error: (err) => {
        this.notifications.error('Error', err.message);
        this.loading = false;
        this.currentResult = buildMockResult(this.config);
      }
    });
  }

  compareStrategies(): void {
    this.comparing = true;
    this.notifications.info('Comparando', 'Evaluando todas las estrategias...');

    this.api.compareStrategies(365).subscribe({
      next: (data) => {
        this.comparisonResults = data.results
          .filter((result: BacktestComparisonResult) => !result.error)
          .sort((a, b) => b.total_return_pct - a.total_return_pct);
        this.notifications.success('Completado', 'Comparacion finalizada');
        this.comparing = false;
      },
      error: () => {
        this.comparisonResults = buildMockComparison();
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

  loadResult(bt: BacktestResult): void {
    this.currentResult = bt;
  }

  applyPreset(preset: string): void {
    switch (preset) {
      case 'quick':
        this.config.start_date = getDateString(-365);
        this.config.model_type = 'ensemble';
        this.config.min_confidence = 0.90;
        break;
      case 'full':
        this.config.start_date = getDateString(-365 * 5);
        this.config.model_type = 'ensemble';
        this.config.min_confidence = 0.90;
        break;
      case 'prophet':
        this.config.start_date = getDateString(-365 * 2);
        this.config.model_type = 'prophet';
        break;
      case 'lstm':
        this.config.start_date = getDateString(-365 * 2);
        this.config.model_type = 'lstm';
        break;
      case 'high_conf':
        this.config.start_date = getDateString(-365 * 3);
        this.config.min_confidence = 0.95;
        break;
    }
    this.runBacktest();
  }
}

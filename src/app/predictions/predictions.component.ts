/**
 * Predictions Component - Vista de predicciones ML
 */
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService, Prediction } from '../services/api.service';
import { NotificationService } from '../services/notification.service';
import {
  buildMockPredictions,
  calculatePredictionRange,
  getChartPosition,
  MockSummary,
  PredictionRange
} from './predictions.helpers';

@Component({
  selector: 'app-predictions',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './predictions.component.html',
  styleUrls: ['./predictions.component.scss'],
})
export class PredictionsComponent implements OnInit {
  predictions: Prediction[] = [];
  summary: MockSummary | null = null;
  loading = false;
  isMockData = false;

  selectedModel = 'ensemble';
  daysAhead = 30;

  range: PredictionRange = { minValue: 4000, maxValue: 4400, midValue: 4200 };

  constructor(
    private api: ApiService,
    private notifications: NotificationService
  ) {}

  ngOnInit(): void {
    this.loadForecast();
  }

  loadForecast(): void {
    this.api.getForecast(this.daysAhead).subscribe({
      next: (data) => {
        this.predictions = data.predictions;
        this.summary = data.summary;
        this.updateRange();
        this.isMockData = false;
      },
      error: () => {
        this.generateMockData();
        this.isMockData = true;
      }
    });
  }

  generatePredictions(): void {
    this.loading = true;
    this.notifications.info('Generando', 'Entrenando modelos y generando predicciones...');

    this.api.generatePredictions(this.daysAhead, this.selectedModel).subscribe({
      next: (result) => {
        this.notifications.success('Completado', `${result.generated} predicciones generadas`);
        this.loadForecast();
        this.loading = false;
      },
      error: (err) => {
        this.notifications.error('Error', err.message);
        this.isMockData = true;
        this.loading = false;
      }
    });
  }

  getPosition(value: number): number {
    return getChartPosition(value, this.range);
  }

  private updateRange(): void {
    const range = calculatePredictionRange(this.predictions);
    if (range) this.range = range;
  }

  private generateMockData(): void {
    const mock = buildMockPredictions(this.daysAhead, this.selectedModel);
    this.predictions = mock.predictions;
    this.summary = mock.summary;
    this.updateRange();
  }
}

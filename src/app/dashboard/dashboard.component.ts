import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, TRMData, TradingSignal, Prediction } from '../services/api.service';
import { RiskService, RiskScoreResponse, HedgingResponse } from '../services/risk.service';
import { Subscription, interval } from 'rxjs';
import { buildChartPaths } from './dashboard.chart';
import {
  buildTrendAnalysis,
  updateModelPredictions,
  ModelSpec,
  TrendFactor,
  TrendSummary
} from './dashboard.analysis';
import {
  DEFAULT_DATA_SOURCES,
  DEFAULT_MODEL_METRICS,
  DEFAULT_MODELS,
  DEFAULT_TREND_SUMMARY,
  DataSource,
  ModelMetrics
} from './dashboard.defaults';
import { DashboardDataLoader } from './dashboard.loader';
import { resolveSignalState } from './dashboard.signal';
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit, OnDestroy {
  Math = Math; // Para usar en template

  isOnline = false;
  loading = false;
  isRunning = false;
  chartPeriod = 30;
  showAnalysis = false;

  currentTRM = 0;
  trmChange = 0;
  predictedTRM = 0;
  predictionConfidence = 0;
  signalClass = 'hold';
  signalIcon = '⏸️';
  signalText = 'ESPERAR';
  signalConfidence = 0;
  expectedReturn = 0;
  signalReason = 'Cargando análisis...';
  canBuy = false;
  canSell = false;
  oilWTI = 0;
  fedRate = 0;
  banrepRate = 0;
  inflationCol = 0;
  portfolioUSD = 0;
  portfolioCOP = 0;
  portfolioPnL = 0;
  historyData: TRMData[] = [];
  predictionData: Prediction[] = [];
  minValue = 4000;
  maxValue = 4400;
  midValue = 4200;
  historyLinePath = '';
  predictionLinePath = '';
  predictionAreaPath = '';
  currentPointX = 0;
  currentPointY = 0;
  toastMessage = '';
  toastType = 'info';
  models: ModelSpec[] = DEFAULT_MODELS.map((model) => ({ ...model }));
  dataSources: DataSource[] = DEFAULT_DATA_SOURCES;
  trendFactors: TrendFactor[] = [];
  trendSummary: TrendSummary = { ...DEFAULT_TREND_SUMMARY };
  modelMetrics: ModelMetrics = { ...DEFAULT_MODEL_METRICS };
  riskScore = 0;
  riskLevel = 'CALCULANDO...';
  riskLevelClass = 'MEDIUM';
  riskRecommendation = 'Analizando volatilidad de mercado...';
  hedgeAmount = 100000;
  hedgeHorizon = 30;
  hedgingResult: HedgingResponse | null = null;

  private subscriptions: Subscription[] = [];
  private dataLoader: DashboardDataLoader;

  constructor(private api: ApiService, private riskService: RiskService) {
    this.dataLoader = new DashboardDataLoader(this.api);
  }

  ngOnInit(): void {
    this.loadData(30);
    this.loadRiskData(); // Load risk initial
    this.subscriptions.push(
      interval(300000).subscribe(() => {
        this.loadData(this.chartPeriod);
        this.loadRiskData();
      })
    );
  }

  loadRiskData(): void {
    this.riskService.getRiskScore().subscribe({
      next: (data) => {
        this.riskScore = data.total_score;
        this.riskLevel = data.risk_level;
        this.riskLevelClass = data.risk_level;
        this.riskRecommendation = data.recommendation;
      },
      error: (e) => console.error('Error loading risk data', e)
    });
  }

  calculateHedging(): void {
    if (!this.hedgeAmount || this.hedgeAmount <= 0) {
      this.showToast('Ingrese un monto válido', 'error');
      return;
    }

    this.showToast('Analizando estrategia de cobertura...', 'info');

    this.riskService.analyzeHedging({
      amount: this.hedgeAmount,
      time_horizon_days: this.hedgeHorizon,
      current_exposure: 0
    }).subscribe({
      next: (res) => {
        this.hedgingResult = res;
        this.showToast('Recomendación generada', 'success');
      },
      error: (e) => {
        this.showToast('Error generando recomendación', 'error');
        console.error(e);
      }
    });
  }

  runModel(): void {
    this.isRunning = true;
    this.showToast('Ejecutando modelo ML...', 'info');

    // Simular tiempo de procesamiento del modelo
    setTimeout(() => {
      // Recargar todos los datos
      this.loadData(this.chartPeriod);

      // Generar nuevas predicciones
      this.api.generatePredictions(30, 'ensemble').subscribe({
        next: () => {
          // Evaluar señal con los nuevos datos
          this.api.evaluateAndNotify().subscribe({
            next: (result) => {
              this.updateSignal(result);
              this.updateAnalysisData();
              this.isRunning = false;
              this.showToast('Modelo ejecutado correctamente', 'success');
            },
            error: () => {
              this.updateAnalysisData();
              this.isRunning = false;
              this.showToast('Modelo ejecutado (modo offline)', 'success');
            }
          });
        },
        error: () => {
          // Modo offline - actualizar con datos mock
          this.generateMockHistory(this.chartPeriod);
          this.generateMockPredictions();
          this.updateChart();
          this.updateAnalysisData();
          this.isRunning = false;
          this.showToast('Modelo ejecutado (modo offline)', 'success');
        }
      });
    }, 1500); // Pequeño delay para UX
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(s => s.unsubscribe());
  }

  loadData(days: number): void {
    this.chartPeriod = days;
    this.dataLoader.load(
      days,
      {
        setOnline: (online) => { this.isOnline = online; },
        setCurrentTRM: (value, change) => { this.currentTRM = value; this.trmChange = change; },
        setHistoryData: (data) => { this.historyData = data; },
        getHistoryData: () => this.historyData,
        setPredictionData: (predictions, predictedTRM, confidencePct) => {
          this.predictionData = predictions;
          this.predictedTRM = predictedTRM || this.currentTRM;
          this.predictionConfidence = confidencePct;
        },
        setSignal: (signal) => { this.updateSignal(signal); },
        setIndicators: (oilWTI, fedRate, banrepRate, inflationCol) => {
          this.oilWTI = oilWTI;
          this.fedRate = fedRate;
          this.banrepRate = banrepRate;
          this.inflationCol = inflationCol;
        },
        setPortfolio: (usd, cop, pnl, canSell) => {
          this.portfolioUSD = usd;
          this.portfolioCOP = cop;
          this.portfolioPnL = pnl;
          this.canSell = canSell;
        }
      },
      () => this.updateChart()
    );
  }

  updateSignal(signal: TradingSignal | null): void {
    const state = resolveSignalState(signal);
    this.signalClass = state.signalClass;
    this.signalIcon = state.signalIcon;
    this.signalText = state.signalText;
    this.signalConfidence = state.signalConfidence;
    this.expectedReturn = state.expectedReturn;
    this.signalReason = state.signalReason;
    this.canBuy = state.canBuy;
  }

  updateChart(): void {
    const chartPaths = buildChartPaths(this.historyData, this.predictionData, this.currentTRM);
    if (!chartPaths) return;

    this.minValue = chartPaths.minValue;
    this.maxValue = chartPaths.maxValue;
    this.midValue = chartPaths.midValue;
    this.historyLinePath = chartPaths.historyLinePath;
    this.predictionLinePath = chartPaths.predictionLinePath;
    this.predictionAreaPath = chartPaths.predictionAreaPath;
    this.currentPointX = chartPaths.currentPointX;
    this.currentPointY = chartPaths.currentPointY;
  }

  evaluateMarket(): void {
    this.loading = true;
    this.showToast('Analizando mercado...', 'info');

    this.api.evaluateAndNotify().subscribe({
      next: (result) => {
        this.updateSignal(result);
        this.updateAnalysisData();
        this.showAnalysis = true;
        this.loading = false;
      },
      error: () => {
        this.updateAnalysisData();
        this.showAnalysis = true;
        this.loading = false;
      }
    });
  }

  updateAnalysisData(): void {
    // Ensure numeric values
    this.currentTRM = Number(this.currentTRM) || 0;
    this.predictedTRM = Number(this.predictedTRM) || 0;

    // Actualizar predicciones de modelos
    const basePred = this.predictedTRM || this.currentTRM;
    this.models = updateModelPredictions(this.models, basePred);

    const analysis = buildTrendAnalysis({
      oilWTI: this.oilWTI,
      banrepRate: this.banrepRate,
      fedRate: this.fedRate,
      inflationCol: this.inflationCol,
      predictedTRM: this.predictedTRM,
      currentTRM: this.currentTRM
    });

    this.trendFactors = analysis.trendFactors;
    this.trendSummary = analysis.trendSummary;
  }

  executeTrade(action: 'buy' | 'sell'): void {
    if (action === 'sell' && this.portfolioUSD <= 0) return;

    const amount = action === 'buy' ? 10000000 : this.portfolioUSD * this.currentTRM;
    const successMsg = action === 'buy' ? 'Compra ejecutada' : 'Venta ejecutada';
    const errorMsg = action === 'buy' ? 'Error en compra' : 'Error en venta';

    this.api.createOrder(action, amount, true).subscribe({
      next: () => { this.showToast(successMsg, 'success'); this.loadData(this.chartPeriod); },
      error: () => { this.showToast(errorMsg, 'error'); }
    });
  }

  showToast(message: string, type: 'success' | 'error' | 'info'): void {
    this.toastMessage = message;
    this.toastType = type;
    setTimeout(() => this.toastMessage = '', 3000);
  }

}

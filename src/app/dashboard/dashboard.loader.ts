import { ApiService, TradingSignal, TRMData, Prediction } from '../services/api.service';
import { buildMockHistory, buildMockPredictions } from './dashboard.mocks';

export interface DashboardLoadHandlers {
  setOnline: (online: boolean) => void;
  setCurrentTRM: (value: number, change: number) => void;
  setHistoryData: (data: TRMData[]) => void;
  getHistoryData: () => TRMData[];
  setPredictionData: (predictions: Prediction[], predictedTRM: number, confidencePct: number) => void;
  setSignal: (signal: TradingSignal | null) => void;
  setIndicators: (oilWTI: number, fedRate: number, banrepRate: number, inflationCol: number) => void;
  setPortfolio: (usd: number, cop: number, pnl: number, canSell: boolean) => void;
}

export class DashboardDataLoader {
  constructor(private api: ApiService) {}

  load(days: number, handlers: DashboardLoadHandlers, onChartUpdate: () => void): void {
    this.api.getCurrentTRM().subscribe({
      next: (data) => {
        handlers.setCurrentTRM(Number(data.value), data.change_pct || 0);
        handlers.setOnline(true);
      },
      error: () => {
        handlers.setCurrentTRM(4150 + Math.random() * 50, (Math.random() - 0.5) * 2);
        handlers.setOnline(false);
      }
    });

    this.api.getTRMHistory(days).subscribe({
      next: (data) => {
        handlers.setHistoryData(data.data.slice(0, days).reverse());
        onChartUpdate();
      },
      error: () => {
        handlers.setHistoryData(buildMockHistory(days));
        onChartUpdate();
      }
    });

    this.api.getForecast(30).subscribe({
      next: (data) => {
        handlers.setPredictionData(
          data.predictions.slice(0, 15),
          data.summary?.average_prediction || 0,
          Math.round((data.summary?.average_confidence || 0.85) * 100)
        );
        onChartUpdate();
      },
      error: () => {
        const mock = buildMockPredictions(handlers.getHistoryData());
        handlers.setPredictionData(mock.predictions, mock.predictedTRM, mock.predictionConfidence);
        onChartUpdate();
      }
    });

    this.api.getCurrentSignal().subscribe({
      next: (data) => { handlers.setSignal(data.signal); },
      error: () => { handlers.setSignal(null); }
    });

    this.api.getMarketIndicators().subscribe({
      next: (data) => {
        handlers.setIndicators(
          Number(data.oil_wti) || 0,
          Number(data.fed_rate) || 0,
          Number(data.banrep_rate) || 0,
          Number(data.inflation_col) || 0
        );
      },
      error: () => { handlers.setIndicators(75.5, 5.25, 9.5, 5.2); }
    });

    this.api.getPortfolioSummary().subscribe({
      next: (data) => {
        handlers.setPortfolio(data.total_usd, data.total_cop, data.realized_pnl, data.total_usd > 0);
      },
      error: () => { handlers.setPortfolio(0, 100000000, 0, false); }
    });
  }
}

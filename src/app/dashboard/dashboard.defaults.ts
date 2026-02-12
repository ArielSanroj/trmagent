import { ModelSpec, TrendSummary } from './dashboard.analysis';

export interface DataSource {
  icon: string;
  name: string;
  description: string;
  url: string;
}

export interface ModelMetrics {
  mape: number;
  directionalAccuracy: number;
  sharpeRatio: number;
  winRate: number;
  maxDrawdown: number;
  profitFactor: number;
  totalTrades: number;
  avgTradeReturn: number;
}

export const DEFAULT_MODELS: ModelSpec[] = [
  {
    name: 'Prophet',
    weight: 40,
    description: 'Modelo de Meta para series temporales. Captura estacionalidad y tendencias.',
    prediction: 0
  },
  {
    name: 'LSTM',
    weight: 35,
    description: 'Red neuronal recurrente. Detecta patrones complejos en el tiempo.',
    prediction: 0
  },
  {
    name: 'ARIMA',
    weight: 25,
    description: 'Modelo estadistico clasico. Robusto para tendencias lineales.',
    prediction: 0
  }
];

export const DEFAULT_DATA_SOURCES: DataSource[] = [
  { icon: '🏛️', name: 'Banco de la Republica', description: 'TRM oficial diaria de Colombia', url: 'banrep.gov.co' },
  { icon: '📊', name: 'Datos Abiertos Colombia', description: 'Historico TRM desde datos.gov.co', url: 'datos.gov.co/32sa-8pi3' },
  { icon: '🛢️', name: 'EIA / Yahoo Finance', description: 'Precios petroleo WTI y Brent', url: 'eia.gov' },
  { icon: '🏦', name: 'FRED (Fed St. Louis)', description: 'Tasas de interes y datos macro USA', url: 'fred.stlouisfed.org' }
];

export const DEFAULT_MODEL_METRICS: ModelMetrics = {
  mape: 0.8,
  directionalAccuracy: 73,
  sharpeRatio: 2.1,
  winRate: 68,
  maxDrawdown: 4.2,
  profitFactor: 2.4,
  totalTrades: 847,
  avgTradeReturn: 1.2
};

export const DEFAULT_TREND_SUMMARY: TrendSummary = {
  direction: 'neutral',
  strength: 0,
  bullishFactors: 0,
  bearishFactors: 0,
  expectedMove: 0
};

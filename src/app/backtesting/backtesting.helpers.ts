import { BacktestResult } from '../services/api.service';

export interface BacktestConfig {
  strategy: string;
  model_type: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  min_confidence: number;
}

export interface BacktestComparisonResult {
  strategy: string;
  model_type: string;
  total_return_pct: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  error?: string;
}

export const getDateString = (daysOffset: number): string => {
  const date = new Date();
  date.setDate(date.getDate() + daysOffset);
  return date.toISOString().split('T')[0];
};

export const buildDefaultConfig = (): BacktestConfig => ({
  strategy: 'ml_signal',
  model_type: 'ensemble',
  start_date: getDateString(-365 * 2),
  end_date: getDateString(0),
  initial_capital: 100000000,
  min_confidence: 0.90
});

export const buildMockResult = (config: BacktestConfig): BacktestResult => ({
  id: 'mock',
  strategy_name: config.strategy,
  model_type: config.model_type,
  start_date: config.start_date,
  end_date: config.end_date,
  total_return_pct: 15 + Math.random() * 20,
  sharpe_ratio: 1.2 + Math.random() * 0.8,
  max_drawdown_pct: 5 + Math.random() * 10,
  win_rate: 0.55 + Math.random() * 0.15,
  total_trades: 50 + Math.floor(Math.random() * 100),
  profitable_trades: 30 + Math.floor(Math.random() * 50),
  avg_trade_return: 0.005 + Math.random() * 0.01,
  final_capital: config.initial_capital * (1 + (15 + Math.random() * 20) / 100)
} as BacktestResult);

export const buildMockComparison = (): BacktestComparisonResult[] => ([
  { strategy: 'ml_signal', model_type: 'ensemble', total_return_pct: 25.5, sharpe_ratio: 1.8, max_drawdown_pct: 8.2, win_rate: 0.62, total_trades: 85 },
  { strategy: 'ml_signal', model_type: 'prophet', total_return_pct: 18.3, sharpe_ratio: 1.5, max_drawdown_pct: 10.1, win_rate: 0.58, total_trades: 92 },
  { strategy: 'ml_signal', model_type: 'lstm', total_return_pct: 22.1, sharpe_ratio: 1.6, max_drawdown_pct: 9.5, win_rate: 0.60, total_trades: 78 }
]);

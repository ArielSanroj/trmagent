import { Prediction, TRMData } from '../services/api.service';

export const buildMockHistory = (days: number): TRMData[] => {
  const base = 4150;
  return Array.from({ length: days }, (_, i) => ({
    date: new Date(Date.now() - (days - i) * 86400000).toISOString(),
    value: base + Math.sin(i / 5) * 50 + (Math.random() - 0.5) * 30,
    source: 'mock'
  }));
};

export const buildMockPredictions = (historyData: TRMData[]): {
  predictions: Prediction[];
  predictedTRM: number;
  predictionConfidence: number;
} => {
  const base = historyData[historyData.length - 1]?.value || 4150;
  const trend = Math.random() > 0.5 ? 1 : -1;

  const predictions = Array.from({ length: 15 }, (_, i) => ({
    id: `pred-${i}`,
    target_date: new Date(Date.now() + (i + 1) * 86400000).toISOString(),
    predicted_value: base + trend * i * 3 + (Math.random() - 0.5) * 20,
    lower_bound: base + trend * i * 3 - 40,
    upper_bound: base + trend * i * 3 + 40,
    confidence: 0.85 + Math.random() * 0.1,
    model_type: 'ensemble',
    trend: trend > 0 ? 'ALCISTA' : 'BAJISTA'
  }));

  return {
    predictions,
    predictedTRM: predictions[predictions.length - 1].predicted_value,
    predictionConfidence: 87
  };
};

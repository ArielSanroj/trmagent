import { Prediction } from '../services/api.service';

export interface PredictionRange {
  minValue: number;
  maxValue: number;
  midValue: number;
}

export interface MockSummary {
  current_trm: number;
  average_prediction: number;
  min_prediction: number;
  max_prediction: number;
  average_confidence: number;
  overall_trend: 'ALCISTA' | 'BAJISTA' | 'NEUTRAL';
}

export const calculatePredictionRange = (predictions: Prediction[]): PredictionRange | null => {
  if (predictions.length == 0) return null;

  const values = predictions.flatMap((p) => [p.lower_bound, p.upper_bound, p.predicted_value]);
  const minValue = Math.min(...values) * 0.98;
  const maxValue = Math.max(...values) * 1.02;
  return {
    minValue,
    maxValue,
    midValue: (minValue + maxValue) / 2
  };
};

export const getChartPosition = (value: number, range: PredictionRange): number =>
  ((value - range.minValue) / (range.maxValue - range.minValue)) * 100;

export const buildMockPredictions = (daysAhead: number, selectedModel: string): { predictions: Prediction[]; summary: MockSummary } => {
  const baseValue = 4150;
  const predictions = Array.from({ length: daysAhead }, (_, i) => {
    const trend = Math.random() > 0.5 ? 1 : -1;
    const predicted = baseValue + trend * (i * 2 + Math.random() * 30);
    return {
      id: `mock-${i}`,
      target_date: new Date(Date.now() + (i + 1) * 86400000).toISOString().split('T')[0],
      predicted_value: predicted,
      lower_bound: predicted - 50,
      upper_bound: predicted + 50,
      confidence: 0.85 + Math.random() * 0.1,
      model_type: selectedModel,
      trend: predicted > baseValue ? 'ALCISTA' : 'BAJISTA'
    } as Prediction;
  });

  const averagePrediction = predictions.reduce((acc, prediction) => acc + prediction.predicted_value, 0) / predictions.length;
  const minPrediction = Math.min(...predictions.map((prediction) => prediction.predicted_value));
  const maxPrediction = Math.max(...predictions.map((prediction) => prediction.predicted_value));
  const overallTrend = predictions[predictions.length - 1].predicted_value > baseValue ? 'ALCISTA' : 'BAJISTA';

  return {
    predictions,
    summary: {
      current_trm: baseValue,
      average_prediction: averagePrediction,
      min_prediction: minPrediction,
      max_prediction: maxPrediction,
      average_confidence: 90,
      overall_trend: overallTrend
    }
  };
};

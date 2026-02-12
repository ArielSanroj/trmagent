import { Prediction, TRMData } from '../services/api.service';

export interface ChartPaths {
  minValue: number;
  maxValue: number;
  midValue: number;
  historyLinePath: string;
  predictionLinePath: string;
  predictionAreaPath: string;
  currentPointX: number;
  currentPointY: number;
}

export const buildChartPaths = (
  historyData: TRMData[],
  predictionData: Prediction[],
  currentTRM: number
): ChartPaths | null => {
  if (historyData.length === 0) return null;

  const allValues = [...historyData.map((d) => d.value), ...predictionData.map((p) => p.predicted_value)];
  const minValue = Math.min(...allValues) * 0.995;
  const maxValue = Math.max(...allValues) * 1.005;
  const midValue = (minValue + maxValue) / 2;

  const totalPoints = historyData.length + predictionData.length;
  const width = 800;
  const height = 200;
  const padding = 10;

  const getX = (i: number) => padding + (i / (totalPoints - 1)) * (width - 2 * padding);
  const getY = (value: number) => height - padding - ((value - minValue) / (maxValue - minValue)) * (height - 2 * padding);

  const historyLinePath = historyData.map((d, i) => `${getX(i)},${getY(d.value)}`).join(' ');

  const lastHistoryIdx = historyData.length - 1;
  const currentPointX = getX(lastHistoryIdx);
  const currentPointY = getY(historyData[lastHistoryIdx]?.value || currentTRM);

  let predictionLinePath = '';
  let predictionAreaPath = '';

  if (predictionData.length > 0) {
    const predStart = historyData.length;
    const predPoints = predictionData.map((p, i) => `${getX(predStart + i)},${getY(p.predicted_value)}`).join(' ');
    predictionLinePath = `${currentPointX},${currentPointY} ${predPoints}`;

    const upperPath = predictionData.map((p, i) => `${getX(predStart + i)},${getY(p.upper_bound)}`);
    const lowerPath = predictionData.map((p, i) => `${getX(predStart + i)},${getY(p.lower_bound)}`).reverse();
    predictionAreaPath = `M ${currentPointX},${currentPointY} L ${upperPath.join(' L ')} L ${lowerPath.join(' L ')} Z`;
  }

  return {
    minValue,
    maxValue,
    midValue,
    historyLinePath,
    predictionLinePath,
    predictionAreaPath,
    currentPointX,
    currentPointY
  };
};

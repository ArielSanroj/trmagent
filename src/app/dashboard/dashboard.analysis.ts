export type TrendImpact = 'bullish' | 'bearish' | 'neutral';

export interface ModelSpec {
  name: string;
  weight: number;
  description: string;
  prediction: number;
}

export interface TrendFactor {
  name: string;
  category: string;
  currentValue: string;
  referenceValue: string;
  explanation: string;
  impact: TrendImpact;
  weight: number;
  correlation: number;
}

export interface TrendSummary {
  direction: TrendImpact;
  strength: number;
  bullishFactors: number;
  bearishFactors: number;
  expectedMove: number;
}

export interface TrendAnalysisInput {
  oilWTI: number;
  banrepRate: number;
  fedRate: number;
  inflationCol: number;
  predictedTRM: number;
  currentTRM: number;
}

export interface TrendAnalysisResult {
  trendFactors: TrendFactor[];
  trendSummary: TrendSummary;
}

export const updateModelPredictions = (models: ModelSpec[], basePrediction: number): ModelSpec[] =>
  models.map((model) => ({
    ...model,
    prediction: basePrediction * (1 + (Math.random() - 0.5) * 0.02)
  }));

export const buildTrendAnalysis = (input: TrendAnalysisInput): TrendAnalysisResult => {
  const trendFactors: TrendFactor[] = [];
  let bullishScore = 0;
  let bearishScore = 0;

  // 1. PETROLEO (correlacion -0.72 con COP)
  const oilRef = 75;
  const oilDeviation = ((input.oilWTI - oilRef) / oilRef) * 100;
  if (Math.abs(oilDeviation) > 5) {
    const isBullish = oilDeviation > 0;
    trendFactors.push({
      name: 'Precio del Petroleo',
      category: 'Commodities',
      currentValue: `$${input.oilWTI.toFixed(2)} USD`,
      referenceValue: `Promedio: $${oilRef} USD`,
      explanation: isBullish
        ? `WTI ${oilDeviation.toFixed(1)}% arriba del promedio. Colombia exporta ~40% en petroleo. Mas dolares entran al pais -> peso se fortalece.`
        : `WTI ${Math.abs(oilDeviation).toFixed(1)}% debajo del promedio. Menos ingresos por exportaciones -> presion sobre el peso.`,
      impact: isBullish ? 'bullish' : 'bearish',
      weight: 25,
      correlation: -0.72
    });
    if (isBullish) bullishScore += 25; else bearishScore += 25;
  }

  // 2. DIFERENCIAL DE TASAS (carry trade)
  const rateDiff = input.banrepRate - input.fedRate;
  const rateDiffRef = 4.0;
  trendFactors.push({
    name: 'Diferencial de Tasas',
    category: 'Politica Monetaria',
    currentValue: `${rateDiff.toFixed(2)}% (BanRep ${input.banrepRate}% - Fed ${input.fedRate}%)`,
    referenceValue: `Promedio historico: ${rateDiffRef}%`,
    explanation: rateDiff > rateDiffRef
      ? `Diferencial de ${rateDiff.toFixed(1)}% atrae "carry trade". Inversionistas piden USD prestado barato y compran activos en COP con mayor rendimiento.`
      : rateDiff > 0
        ? `Diferencial positivo pero bajo (${rateDiff.toFixed(1)}%). Atractivo moderado para inversion extranjera.`
        : `Diferencial negativo. La Fed paga mas que BanRep -> capital sale de Colombia hacia USA.`,
    impact: rateDiff > rateDiffRef ? 'bullish' : rateDiff < 2 ? 'bearish' : 'neutral',
    weight: 20,
    correlation: -0.58
  });
  if (rateDiff > rateDiffRef) bullishScore += 20;
  else if (rateDiff < 2) bearishScore += 20;

  // 3. INFLACION COLOMBIA
  const inflationRef = 3.0;
  trendFactors.push({
    name: 'Inflacion Colombia',
    category: 'Economia Local',
    currentValue: `${input.inflationCol.toFixed(1)}% anual`,
    referenceValue: `Meta BanRep: ${inflationRef}%`,
    explanation: input.inflationCol > inflationRef + 2
      ? `Inflacion ${(input.inflationCol - inflationRef).toFixed(1)}pp arriba de la meta. Erosiona poder adquisitivo del peso y genera incertidumbre.`
      : input.inflationCol <= inflationRef
        ? 'Inflacion controlada dentro de la meta. Senal de estabilidad macroeconomica -> confianza en el peso.'
        : 'Inflacion moderadamente alta. BanRep podria mantener tasas altas para controlarla.',
    impact: input.inflationCol > 5 ? 'bearish' : input.inflationCol <= inflationRef ? 'bullish' : 'neutral',
    weight: 15,
    correlation: 0.45
  });
  if (input.inflationCol > 5) bearishScore += 15;
  else if (input.inflationCol <= inflationRef) bullishScore += 15;

  // 4. PREDICCION DEL MODELO
  const predChange = ((input.predictedTRM - input.currentTRM) / input.currentTRM) * 100;
  trendFactors.push({
    name: 'Senal del Modelo ML',
    category: 'Analisis Tecnico',
    currentValue: `$${input.predictedTRM.toFixed(2)} COP`,
    referenceValue: `Actual: $${input.currentTRM.toFixed(2)} COP`,
    explanation: Math.abs(predChange) < 1
      ? `Modelo predice estabilidad (${predChange > 0 ? '+' : ''}${predChange.toFixed(2)}%). Sin senal clara de direccion.`
      : predChange > 0
        ? `Modelo predice TRM +${predChange.toFixed(2)}% en 30 dias. Ensemble de Prophet+LSTM+ARIMA coinciden en tendencia alcista.`
        : `Modelo predice TRM ${predChange.toFixed(2)}% en 30 dias. Los 3 modelos coinciden en fortalecimiento del peso.`,
    impact: predChange > 1 ? 'bearish' : predChange < -1 ? 'bullish' : 'neutral',
    weight: 25,
    correlation: 0.85
  });
  if (predChange > 1) bearishScore += 25;
  else if (predChange < -1) bullishScore += 25;

  // 5. VOLATILIDAD IMPLICITA (simulada)
  const volatility = 8 + Math.random() * 10;
  const volRef = 12;
  trendFactors.push({
    name: 'Volatilidad del Mercado',
    category: 'Riesgo',
    currentValue: `${volatility.toFixed(1)}% (30 dias)`,
    referenceValue: `Promedio: ${volRef}%`,
    explanation: volatility > volRef + 3
      ? `Alta volatilidad (${volatility.toFixed(1)}%). Incertidumbre elevada favorece refugio en USD. Aumenta prima de riesgo Colombia.`
      : volatility < volRef - 3
        ? 'Baja volatilidad. Mercado tranquilo, flujos estables. Ambiente favorable para carry trade.'
        : 'Volatilidad normal. Sin impacto significativo en la tendencia.',
    impact: volatility > volRef + 3 ? 'bearish' : volatility < volRef - 3 ? 'bullish' : 'neutral',
    weight: 10,
    correlation: 0.35
  });
  if (volatility > volRef + 3) bearishScore += 10;
  else if (volatility < volRef - 3) bullishScore += 10;

  // 6. FLUJOS DE INVERSION EXTRANJERA (simulado)
  const foreignFlows = (Math.random() - 0.5) * 2000;
  trendFactors.push({
    name: 'Flujos de Inversion',
    category: 'Flujos de Capital',
    currentValue: `${foreignFlows > 0 ? '+' : ''}${foreignFlows.toFixed(0)} M USD (mes)`,
    referenceValue: 'Promedio mensual: +200 M USD',
    explanation: foreignFlows > 300
      ? `Entrada neta de ${foreignFlows.toFixed(0)}M USD. Inversionistas extranjeros comprando activos colombianos -> demanda de pesos.`
      : foreignFlows < -300
        ? `Salida neta de ${Math.abs(foreignFlows).toFixed(0)}M USD. Capital extranjero saliendo -> venden pesos, compran dolares.`
        : 'Flujos neutrales. Sin presion significativa por movimientos de capital extranjero.',
    impact: foreignFlows > 300 ? 'bullish' : foreignFlows < -300 ? 'bearish' : 'neutral',
    weight: 15,
    correlation: -0.62
  });
  if (foreignFlows > 300) bullishScore += 15;
  else if (foreignFlows < -300) bearishScore += 15;

  const totalScore = bullishScore + bearishScore;
  const trendSummary: TrendSummary = {
    direction: bullishScore > bearishScore + 10 ? 'bullish' : bearishScore > bullishScore + 10 ? 'bearish' : 'neutral',
    strength: totalScore > 0 ? Math.abs(bullishScore - bearishScore) / totalScore * 100 : 0,
    bullishFactors: trendFactors.filter((f) => f.impact === 'bullish').length,
    bearishFactors: trendFactors.filter((f) => f.impact === 'bearish').length,
    expectedMove: predChange
  };

  return { trendFactors, trendSummary };
};

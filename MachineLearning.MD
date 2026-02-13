# Machine Learning — TRM Agent

> Última actualización: 2026-02-13
> Notas de referencia: docs/ml-notes/

## 1. Modelos y Técnicas

| Modelo | Propósito | Ubicación en código | Tipo |
|--------|-----------|---------------------|------|
| Prophet | Pronóstico de series temporales TRM | `backend/models/` | Series temporales (aditivo) |
| LSTM | Pronóstico deep learning TRM | `backend/models/` | Deep learning / RNN |
| Ensemble (Prophet+LSTM) | Combinación ponderada de pronósticos | `backend/models/` | Ensemble ponderado |
| Forward pricing | Cálculo de precio forward USD/COP | `backend/simulate_hedging.py` | Modelo financiero (no ML) |

### 1.1 Prophet — Series Temporales
- **Qué predice**: TRM (USD/COP) a horizonte de 1-90 días
- **Datos de entrada**: Serie histórica diaria de TRM, variables exógenas opcionales (tasas de interés, commodities)
- **Salida**: Pronóstico puntual + intervalos de confianza
- **Parámetros clave**: Changepoints automáticos, seasonality (yearly, weekly), holidays Colombia
- **Referencia**: [docs/ml-notes/resumos/validacion-tiempo-y-leakage.md](docs/ml-notes/resumos/validacion-tiempo-y-leakage.md) — CRÍTICO: split temporal obligatorio

### 1.2 LSTM — Deep Learning
- **Qué predice**: TRM a horizonte corto (1-30 días)
- **Datos de entrada**: Ventana de N días históricos (features normalizados)
- **Salida**: Pronóstico puntual
- **Parámetros clave**: Window size, hidden layers, dropout, learning rate
- **Riesgo**: Overfitting en series financieras cortas
- **Referencia**: [docs/ml-notes/resumos/bias-variance-tradeoff.md](docs/ml-notes/resumos/bias-variance-tradeoff.md) — Manejar overfitting en LSTM

### 1.3 Ensemble — Combinación Ponderada
- **Qué hace**: Combina pronósticos de Prophet y LSTM con pesos optimizados
- **Pesos**: Basados en rendimiento histórico de cada modelo (rolling validation)
- **Ventaja**: Reduce varianza del pronóstico individual
- **Referencia**: [docs/ml-notes/cursos/2019-06-27_clase3_arboles-y-ensembles.md](docs/ml-notes/cursos/2019-06-27_clase3_arboles-y-ensembles.md)

### 1.4 Forward Pricing — Modelo Financiero
- **Fórmula**: `Forward ≈ Spot × (1 + i_COP × T) / (1 + i_USD × T)`
- **No es ML**: Es un modelo financiero determinístico basado en diferencial de tasas
- **Uso**: Calcular precio justo de cobertura, no predecir mercado

## 2. Pipeline de Datos y Validación

- **Fuentes de datos**: Datos de mercado (TRM oficial BanRep, tasas de interés, commodities)
- **Estrategia de validación**:
  - **CRÍTICO — Split temporal obligatorio**: Nunca usar datos futuros para entrenar/validar
  - Ventana rolling/expanding para backtesting
  - Test ADF para verificar estacionariedad
  - Walk-forward validation: entrenar hasta T, predecir T+1...T+h, avanzar ventana
- **Riesgos de leakage**:
  - Usar precio de cierre del día actual para predecir el mismo día
  - Incluir indicadores calculados con datos futuros (ej: MA que incluye datos posteriores)
  - No considerar días no hábiles (TRM no se publica fines de semana/festivos)
- **Referencia**: [docs/ml-notes/resumos/validacion-tiempo-y-leakage.md](docs/ml-notes/resumos/validacion-tiempo-y-leakage.md)

## 3. Métricas — ML a Negocio

| Métrica ML | Métrica de Negocio | Umbral |
|------------|-------------------|--------|
| MAE (COP) | Error promedio en pronóstico TRM | < 50 COP a 7 días |
| RMSE (COP) | Penalización de errores grandes | < 80 COP a 7 días |
| Directional accuracy | % de veces que acertó dirección | > 55% |
| Impacto P&L cobertura | Ahorro/costo vs sin cobertura | Positivo neto anualizado |
| Sharpe del pronóstico | Retorno ajustado por riesgo de señales | > 0.5 |

**Referencia**: [docs/ml-notes/resumos/metricas-y-negocio.md](docs/ml-notes/resumos/metricas-y-negocio.md)

## 4. Operaciones en Producción

- **Deployment**: Docker (FastAPI backend) + Angular frontend
- **Frecuencia**: Actualización diaria de pronósticos (después de cierre de mercado)
- **Pipeline**:
  1. Fetch datos actualizados de TRM y tasas
  2. Re-entrenar/actualizar modelos (incremental o rolling)
  3. Generar pronósticos para siguiente ventana
  4. Calcular forwards actualizados
  5. Servir vía API al frontend
- **Monitoreo**:
  - MAE rolling de últimos 30 días
  - Drift en distribución de residuos
  - Alerta si error > 2σ histórico
- **Triggers de reentrenamiento**:
  - MAE rolling supera umbral
  - Cambio de régimen detectado (volatilidad > percentil 95)
  - Evento macroeconómico significativo (cambio de tasa del banco central)

**Referencia**: [docs/ml-notes/resumos/monitoreo-y-retraining.md](docs/ml-notes/resumos/monitoreo-y-retraining.md)

## 5. Checklists

### Pre-entrenamiento
- [ ] Serie temporal sin gaps (imputar o marcar días no hábiles)
- [ ] Test ADF pasado (estacionariedad o diferenciación aplicada)
- [ ] Features normalizados para LSTM
- [ ] Split temporal definido (nunca random)
- [ ] Ventana de entrenamiento suficiente (> 2 años recomendado)

### Pre-deploy
- [ ] Backtesting con walk-forward completado
- [ ] MAE y directional accuracy dentro de umbrales
- [ ] Forward pricing validado contra broker real
- [ ] API sirviendo pronósticos con latencia < 1s
- [ ] Fallback si datos de mercado no están disponibles
- [ ] Logs sin datos financieros sensibles

**Referencia**: [docs/ml-notes/cheatsheets/modeling-checklist.md](docs/ml-notes/cheatsheets/modeling-checklist.md)

## 6. Índice de Notas de Referencia

### Cheatsheets
- [Modeling Checklist](docs/ml-notes/cheatsheets/modeling-checklist.md)
- [Econometría & ML Cheatsheet](docs/ml-notes/cheatsheets/econometria-ml-cheatsheet.md)

### Resúmenes Temáticos
- [Bias-Variance Tradeoff](docs/ml-notes/resumos/bias-variance-tradeoff.md)
- [Calibración](docs/ml-notes/resumos/calibracion.md)
- [Métricas y Negocio](docs/ml-notes/resumos/metricas-y-negocio.md)
- [Validación Temporal y Leakage](docs/ml-notes/resumos/validacion-tiempo-y-leakage.md)
- [Modelos Tabulares 2026](docs/ml-notes/resumos/modelos-tabulares-2026.md)
- [Notebook a Producción](docs/ml-notes/resumos/notebook-a-produccion.md)
- [Monitoreo y Retraining](docs/ml-notes/resumos/monitoreo-y-retraining.md)

### Cursos
- [Clase 1 — Riesgo y Aprendizaje](docs/ml-notes/cursos/2019-06-25_clase1_riesgo-y-aprendizaje.md)
- [Clase 2 — Modelos Lineales y Validación](docs/ml-notes/cursos/2019-06-26_clase2_modelos-lineales-validacion.md)
- [Clase 3 — Árboles y Ensembles](docs/ml-notes/cursos/2019-06-27_clase3_arboles-y-ensembles.md)
- [Clase 5 — Validación y Checklist](docs/ml-notes/cursos/2019-07-03_clase5_validacion-y-checklist.md)

### Implementaciones
- [Árboles CMC](docs/ml-notes/implementaciones/arboles_cmc.md)
- [Pruning Cost Complexity](docs/ml-notes/implementaciones/pruning_cost_complexity.md)

### Producción
- [Árboles en Producción](docs/ml-notes/produccion/arboles_en_produccion.md)

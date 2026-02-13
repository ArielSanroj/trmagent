# Métricas de ML ↔ Métrica de negocio (lo único que importa)

## Clasificación (riesgo / fraude / churn)

### AUC / ROC-AUC
- Útil para ranking global.
- No te dice el threshold óptimo ni calibración.

**Métrica de negocio detrás (ejemplo fraude):**
\[
\text{Profit}(s) = TP(s)\cdot V_{TP} - FP(s)\cdot C_{FP} - FN(s)\cdot C_{FN}
\]
Donde `s` es el umbral.

### Precision / Recall / FPR
- Sirven si los costos son asimétricos.
- En producción, casi siempre optimizas con **constraints**, por ejemplo:
  - “maximiza recall sujeto a FPR ≤ 0.5%”
  - “maximiza profit sujeto a capacidad ≤ 10k casos/día”

### Calibration (Brier, ECE)
Si el output se interpreta como probabilidad (PD, propensión, churn), calibración es parte del producto.

## Regresión / forecasting

### RMSE / MAE
Bien como proxy, pero lo que duele es:
- **stockouts** (ventas perdidas, penalizaciones)
- **overstock** (markdown, obsolescencia, coste de capital)

Una forma común:
\[
\text{Cost} = c_o \cdot \max(0, \hat{y}-y) + c_u \cdot \max(0, y-\hat{y})
\]
(“newsvendor loss”, asimétrica)

### Cuantiles
En supply/retail:
- P90 para inventario (evitar stockout),
- P50 para plan base,
- P10 para riesgo de sobrestock.

## Recomendación / ranking

- Offline (NDCG, MAP) suele correlacionar poco con negocio si no haces experimentos.
- Online: CTR, CVR, revenue per session, watch time, etc.

**Regla dolorosa:** si no hay A/B o quasi-experiment, puedes estar “ganando” offline y perdiendo dinero.

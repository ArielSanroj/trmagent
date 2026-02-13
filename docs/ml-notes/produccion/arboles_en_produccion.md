# Árboles en producción (2025–2026): reglas duras

## 1) Árboles puros casi nunca son el “modelo final”
- Usualmente terminan como baseline interpretable o como parte de un ensemble.
- Lo más común en tabular: **LightGBM/XGBoost** con restricciones (monotonicidad, min_data_in_leaf, etc.).

## 2) Métrica offline vs métrica de negocio
Ejemplos típicos:
- Fraude: AUC puede subir y el *profit* bajar si no controlas **capacity/threshold**.
- Crédito: ranking (AUC/KS) no basta: necesitas **calibración** (PD) y *expected loss*.

## 3) Validación y leakage
- Si hay tiempo: split temporal.
- Si hay usuario/cliente: split por grupo.
- Si hay intervención/política: cuidado con variables post-tratamiento.

## 4) Monitoreo mínimo
- Drift de features (PSI/KS + alertas)
- Drift de score y tasa de positivos
- Calibración (ECE/Brier) si score se usa como probabilidad
- Calidad de datos (missing/categorías nuevas)

## 5) Explicabilidad real
- Árbol: reglas claras, pero pueden ser inestables.
- Para ensembles: SHAP (con muestreo), y explicaciones agregadas por segmento.

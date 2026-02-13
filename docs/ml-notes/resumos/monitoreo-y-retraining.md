# Monitoreo y retraining (MLOps de verdad, no “slides”)

## 1) Qué monitoreo siempre

### Datos (input)
- Missing rate por feature
- Distribuciones (PSI/KS, drift)
- Cardinalidad y “nuevos valores”
- Latencia de features / freshness

### Predicciones
- Distribución de scores
- Tasa de decisiones (accept/reject)
- Calibration drift (reliability)

### Outcome (si llega)
- Performance real (AUC/LogLoss/MAE) por cohorte
- Profit/cost real (si lo puedes medir)

## 2) Retraining: gatillos reales
- Programado (mensual/semanal)
- Trigger por drift (PSI > threshold)
- Trigger por degradación de negocio (profit cae)

## 3) Lo que falla en el mundo real
- “No tenemos labels a tiempo” → necesitas proxies y delayed labels.
- Cambios de política (ej. underwriting) → concept drift.
- Data pipelines frágiles → alertas y data contracts.

## 4) Modelo riesgo / SR 11-7 (si aplica)
- Documentación del modelo (propósito, población, features)
- Validación independiente
- Control de cambios (versionado)
- Evidencia de monitoreo y recalibración

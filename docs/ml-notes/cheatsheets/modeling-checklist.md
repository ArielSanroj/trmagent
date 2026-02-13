# Modeling checklist (cheatsheet)

## 0) Antes de modelar
- ¿Cuál es el objetivo de negocio? (profit, riesgo, fill-rate, churn)
- ¿Qué decisión se toma con el modelo? (umbral, ranking, presupuesto)
- ¿Qué horizonte temporal? (t0 predice t0+h)

## 1) Datos
- Definición de `Y` estable y auditable
- Leakage: features construidas solo con info disponible al momento de decisión
- Split correcto: tiempo / usuario / tienda / grupo
- Data quality: missing, outliers, duplicados, cambios de esquema
- Privacidad: minimización y propósito (GDPR/ley local)

## 2) Modelado
- Baselines fuertes (lineal, árbol)
- Métrica alineada a negocio (cost-sensitive)
- Calibración si necesitas probabilidades
- Interpretabilidad (SHAP / monotonic constraints si aplica)
- Fairness: disparate impact / equal opportunity (según caso)

## 3) Validación
- CV adecuada (no aleatoria si hay estructura)
- Reporte por segmentos / cohortes
- Stress tests: drift simulado, cambios de política, missing spikes
- Robustez: sensibilidad a features clave

## 4) Producción
- Latencia P95/P99 y coste por predicción
- Observabilidad: logs de features, predicción, versión de modelo
- Monitoreo drift y performance (con labels retrasados)
- Plan de retraining + rollback
- Documentación (MRM/SR 11-7 si aplica)

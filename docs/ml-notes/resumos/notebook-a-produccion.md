# De notebook a producción confiable (resumen de batalla)

## 1) Contratos entre entrenamiento y serving
- Mismo cálculo de features (ideal: feature store o librería compartida)
- Versionado de features y del pipeline de entrenamiento
- Tests unitarios y de datos (Great Expectations / pandera, etc.)

## 2) Latencia y coste
- Define SLOs: P95/P99
- Batch vs realtime
- Caching y precomputación

## 3) Observabilidad
- Logs de inputs (con privacidad), outputs, versión
- Trazabilidad: request → features → predicción → decisión

## 4) Operación
- Canary releases y rollback
- Alertas por drift y por fallos de pipeline
- Retraining con gates (no se promueve modelo sin pasar checks)

## 5) Documentación mínima
- Qué hace el modelo y para qué no sirve
- Población, features, límites
- Métrica de negocio y thresholds
- Plan de monitoreo y retraining

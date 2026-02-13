# Validación en el tiempo y leakage (imprescindible)

Esto **no** aparece explícito en el cuaderno, pero es la causa #1 de “modelos que se ven increíbles y mueren en producción”.

## 1) Tipos de leakage típicos

- **Leaking label:** usas información posterior al momento de predicción (ej. estado de pago futuro).
- **Leaking aggregation:** agregas métricas calculadas con ventana que incluye futuro.
- **Leaking split:** random split cuando hay múltiples filas por cliente/tienda → el mismo entity cae en train y test.
- **Target leakage por procesos:** features que son proxies directos de la decisión humana posterior (ej. “monto aprobado”).

## 2) Split recomendado según problema

- Series de tiempo (demanda, energía):
  - rolling / expanding window CV
  - backtesting por cortes (semanas/meses)
- Cliente/usuario con múltiples eventos:
  - split por **cliente** (GroupKFold) o por “cohorte de alta”
- Experimentos / marketing:
  - A/B test cuando puedas

## 3) En producción, valida también “operaciones”
No solo performance offline:
- latencia P95/P99
- tasa de fallos
- estabilidad por segmento
- drift (data y concept)

## 4) Código orientativo (scikit-learn)
Ver `notebooks/python/` (placeholder para ampliar).

# Bias–Variance tradeoff (versión operativa)

## 1) Definición útil (no académica)

- **Bias (sesgo):** error sistemático porque tu clase de modelos no puede representar la relación real *o* porque regularizaste demasiado.
- **Variance (varianza):** sensibilidad del modelo a pequeñas variaciones del dataset (muestras).

En la práctica, *casi siempre* lo ves como:
- Train muy bueno + Test malo → **varianza / overfitting**
- Train malo + Test malo → **sesgo / underfitting** o features pobres

## 2) Lo que realmente haces en producción

### Paso 1: fija la métrica de negocio
Ejemplos:
- Fraude: profit esperado a cierto recall mínimo, con constraint de FPR.
- Crédito: utilidad/riesgo, constraint de PD a nivel portafolio.
- Forecasting: coste de stockout + overstock (no RMSE “a secas”).

### Paso 2: curvas y diagnóstico
- Curva de aprendizaje: error vs tamaño de data.
- Gap train-test: proxy de varianza.
- Estabilidad temporal: performance por cohorte / semana / segmento.

### Paso 3: elige palancas
Para bajar varianza:
- más datos (o data augmentation en texto/imagen),
- regularización,
- early stopping,
- simplificar features,
- bagging/ensembles.

Para bajar sesgo:
- mejores features,
- modelos más expresivos,
- interacciones,
- objetivos/loss adecuados (ej. quantile loss en demanda).

## 3) Números “de vida real”
(no universales, pero recurrentes)

- En tabular de riesgo/fraude, pasar de logística a boosting suele dar:
  - +1 a +4 puntos AUC (0.01–0.04) cuando hay no-linealidad real,
  - pero también puede empeorar calibración si no calibras.

- En forecasting retail, modelos demasiado complejos sin buen data quality:
  - mejoran RMSE, pero empeoran fill-rate o margen por decisiones erróneas (sobreajuste estacional).

## 4) Anti-patterns que cuestan dinero
- Evaluar con split aleatorio cuando hay tiempo → leakage.
- Optimizar AUC y desplegar con threshold fijo sin matriz de coste.
- “Más features” sin gobernanza: se rompe un upstream → caída silenciosa.

# Econometría + ML – Cheatsheet rápido

## Conceptos
- Riesgo: \(R(f)=\mathbb{E}[L(Y,f(X))]\)
- Riesgo empírico: \(\hat{R}(f)=\frac{1}{n}\sum_i L(y_i,f(x_i))\)
- Bayes classifier (0–1): \(f^\*(x)=\mathbb{I}(P(Y=1|x)\ge 0.5)\)

## Métricas de clasificación
- TPR/Recall: \(TP/(TP+FN)\)
- FPR: \(FP/(FP+TN)\)
- Precision: \(TP/(TP+FP)\)
- ROC: TPR vs FPR al barrer umbral

## Árboles (CART)
- Modelo por regiones: \(f(x)=\sum_m c_m I(x\in R_m)\)
- Regresión: SSE
- Pruning: cost-complexity

## k-means
- Objetivo: minimizar suma de distancias a centroides

## Reglas de asociación
- Support: frecuencia de un itemset
- Confidence: probabilidad condicional de regla

## Producción (recordatorio)
- Split correcto > modelo complejo
- Métrica de negocio > AUC/RMSE
- Monitoreo + retraining > “entrené una vez y listo”

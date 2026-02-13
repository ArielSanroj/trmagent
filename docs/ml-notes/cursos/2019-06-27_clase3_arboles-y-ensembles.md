# 2019-06-27 – Árboles y ensembles (clase 3)

**Fuente:** `raw/scans/MECA MACHINE LEARNING NOTES.pdf`, páginas 15–18.

## 1) Árboles (CART) como modelo por regiones

En los apuntes:
\[
f(x)=\sum_{m=1}^M c_m\ \mathbb{I}(x\in R_m)
\]

donde `R_m` son regiones del espacio de variables generadas por splits del tipo:
\[
x_j \le s
\]

### Árbol de regresión (objetivo continuo)

Se eligen splits para minimizar SSE:

\[
\min_{\{R_m\},\{c_m\}} \sum_{m=1}^M \sum_{i:x_i\in R_m}(y_i-c_m)^2
\]
y típicamente:
\[
c_m=\text{promedio}(y\mid x\in R_m)
\]

**Producción:** árboles solitos raramente son el mejor “modelo final” porque:
- Son **alta varianza**
- Cambian mucho con pequeñas perturbaciones de datos

Pero son excelentes para:
- Interpretabilidad local
- Capturar no-linealidades básicas
- Baseline rápido

### Árbol de clasificación

Se usa una métrica de impureza / error en el nodo (en tus notas aparece el error de clasificación tipo `1 - p_{mk(m)}`).

## 2) Pruning y cost-complexity (evitar sobreajuste)

En los apuntes aparece la idea de penalizar complejidad:
\[
C_\alpha(T)=C(T)+\alpha |T|
\]
donde `|T|` es el número de hojas (o nodos terminales).

Se elige `α` con validación cruzada.

**Regla de campo:**  
> Si no controlas profundidad/min_samples_leaf, un árbol te da una demo linda y una semana después drift + varianza te lo matan.

## 3) Random Forests: por qué funcionan tan bien

Idea operativa:
- Bagging (bootstrap) + muchos árboles.
- Promedio/voto → baja varianza.

**Pros (producción):**
- Robustos, poco tuning.
- Buen rendimiento tabular.
- Manejan no-linealidades e interacciones.
- Feature importance (con cuidado).

**Contras:**
- Latencia mayor que lineales.
- Interpretabilidad limitada (aunque SHAP ayuda).
- Calibration a veces mala → suele requerir calibración si usas probabilidades.

**Lo que se usa en 2025–2026 en tabular (realista):**
- Gradient Boosting (LightGBM/CatBoost/XGBoost) suele ganar a RF en AUC/LogLoss.
- RF sigue siendo un baseline fuerte y muy estable.

En `docs/resumos-tematicos/modelos-tabulares-2026.md` dejo una comparación práctica.

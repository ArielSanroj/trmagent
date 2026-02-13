# Poda (Cost-Complexity) en árboles: lo que importa de verdad

En clase se suele mostrar el árbol creciendo “hasta que no pueda más” y luego podarlo.
En producción, lo que te interesa es controlar **varianza** y tener un modelo estable ante drift.

## Objetivo
Minimizar:

C_α(T) = Σ_{m∈hojas} N_m Q_m(T) + α |T|

- `Q_m(T)`: impureza / error en hoja `m` (Gini/entropy en clasificación, MSE en regresión)
- `|T|`: número de hojas (proxy de complejidad)
- `α`: trade-off sesgo–varianza (regularización)

## Cómo se hace bien (práctico)
1) Entrena árbol grande (con límites razonables: `min_samples_leaf`, `max_depth`).
2) Obtén la ruta de `ccp_alpha`.
3) Evalúa por CV (ideal: estratificada o por grupos) y elige α por métrica objetivo.
4) Re-entrena con ese α y congela hiperparámetros.

## Señales de overfit en árboles
- Gran brecha train vs valid (macro-F1 o logloss)
- Importancias “raras” dominadas por variables sospechosas
- Árbol muy profundo con hojas pequeñas (pocas observaciones)

## Producción (lo que te tumba)
- **Data contracts** rotos: categorías nuevas / missing patterns cambian → splits inválidos.
- **Drift**: cambia la distribución de features → cambian reglas del árbol.
- **Costo de errores**: un árbol “más exacto” puede ser menos rentable si optimiza la métrica equivocada.

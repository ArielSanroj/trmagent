# Implementación: Árboles con CMC (Contraceptive Method Choice)

Este documento acompaña el notebook `notebooks/arboles/Clase_3_Arboles.ipynb` y el dataset `raw/datasets/cmc.csv`.

## Qué debes verificar antes de “creerle” al árbol
- **Tipo de split**: si el dataset tiene dependencia temporal o por individuo, debes hacer *group split* / *time split* (evita leakage).
- **Métrica correcta**: en multiclase, accuracy suele ser engañosa. En producción casi siempre necesitas:
  - *macro-F1* (equidad entre clases raras),
  - *balanced accuracy*,
  - o una métrica de negocio (costo por clase, utilidad esperada).
- **Calibración**: si vas a usar probabilidades (p.ej. decisión por umbral o policy), calibra (isotonic / Platt) y valida ECE/Brier.

## Árbol sin poda vs podado
En `raw/model_outputs/tree_full.pdf` verás el árbol completo (típicamente sobreajusta);
en `raw/model_outputs/tree_pruned.pdf` verás el árbol podado (mejor generalización).

## Checklist mínimo (2026)
1) Split correcto (ideal: CV estratificada + seed fijo).
2) Grid/Random search sobre:
   - `max_depth`, `min_samples_leaf`, `ccp_alpha` (cost complexity pruning).
3) Reporta:
   - matriz de confusión,
   - macro-F1 / balanced accuracy,
   - curva de calibración si usas probabilidades.
4) Interpretable ≠ seguro: revisa **fairness** si las features son sensibles o proxies.

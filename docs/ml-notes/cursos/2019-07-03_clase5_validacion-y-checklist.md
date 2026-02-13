# 2019-07-03 – Validación y checklist (clase 5)

**Fuente:** `raw/scans/MECA MACHINE LEARNING NOTES.pdf`, páginas 29–30.

## 1) Matriz de confusión y métricas

En tus notas:

- **Recall / TPR**:
\[
TPR=\frac{TP}{TP+FN}
\]

- **False Positive Rate / FPR**:
\[
FPR=\frac{FP}{FP+TN}
\]

- **Precision**:
\[
Precision=\frac{TP}{TP+FP}
\]

**Conexión a negocio (lo que no se puede omitir):**
- Fraude: sube TPR pero si sube FPR demasiado, churn + costos de call center te comen vivo.
- Crédito: subir approvals (bajar FN de “buenos”) puede subir pérdidas si no controlas PD/LGD o si cambian políticas.

## 2) Out-of-sample y cross-validation

- Holdout cuando tienes suficiente data.
- Cross-validation cuando el dataset es pequeño.

**Fallo clásico:** CV aleatoria en datos con tiempo o usuarios repetidos → leakage.

Ver: `docs/resumos-tematicos/validacion-tiempo-y-leakage.md`.

## 3) Checklist de “posibles problemas” (p.30)

Los puntos del cuaderno apuntan a preguntas correctas:

- ¿Qué tan grande es el dataset?
- ¿Cómo es la calidad de la data?
- ¿Hay sesgos / selección?
- ¿Cambios en el tiempo (drift)?
- ¿Qué tan complejo es el modelo vs data?

Yo lo aterricé a un checklist de producción en:
- `docs/cheatsheets/modeling-checklist.md`

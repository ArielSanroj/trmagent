# 2019-06-26 – Modelos lineales, selección y validación (clase 2)

**Fuente:** `raw/scans/MECA MACHINE LEARNING NOTES.pdf`, páginas 8–14.

## 1) Regresión vs clasificación (lineales)

En el cuaderno se contrasta:

- **k-NN** como aproximación *localmente constante*.
- **Modelo lineal** como aproximación *globalmente lineal*.

Esta dicotomía es clave para entender por qué:
- k-NN suele tener **bajo sesgo** pero **alta varianza** si `k` es pequeño.
- lo lineal suele tener **más sesgo** pero **menos varianza**.

## 2) Selección de variables (por qué NO es solo estadística)

Motivaciones que aparecen en el cuaderno:
- Minimizar error de prueba.
- Interpretabilidad.
- Evitar multicolinealidad / inestabilidad.

**Producción (mi lectura):**
- En fintech/insurance, interpretabilidad no es “nice to have”: es un requisito (auditoría, disputas, fairness).
- En retail/forecasting, la selección de variables afecta coste de features (joins pesados, latencia, dependencia de fuentes).

### Técnicas que aparecen

- **Best subset / selección por subconjuntos**
- **Forward / backward / stepwise**
- **Shrinkage (contracción)**:
  - Ridge (penalización L2)
  - Lasso (penalización L1)

**Nota realista (2025–2026):**
- Stepwise “clásico” se usa menos en producción porque es inestable y puede overfittear selección.  
- Lo que sí veo mucho:
  - Regularización (ridge/lasso/elastic net).
  - Modelos de árboles con regularización + importance.
  - Selección guiada por coste de feature + estabilidad.

## 3) Regresión logística + umbral

En los apuntes aparece:
\[
p(x)=P(Y=1\mid X=x)=\frac{e^{\beta^\top x}}{1+e^{\beta^\top x}}
\]
y la regla de decisión:
\[
\hat{y}=\mathbb{I}(p(x) > s).
\]

**Cuidado:** en scoring/fraude, **s=0.5 casi nunca** es óptimo.  
Se elige `s` para optimizar negocio: profit, FNR bajo a cierto FPR, capacidad operativa, etc.

## 4) Validación: train/valid/test y cross-validation

En los apuntes:
- Separación de datos (holdout).
- Validación cruzada para elegir hiperparámetros.

**Regla que evita autoengaño:**
- El **test** se usa **una sola vez**, al final.
- Todo tuning se hace con train/valid o CV.

### Lo que falta (y es crítico en 2026)

- Si hay tiempo (series, cohortes, campañas): usar **time split** y no CV aleatorio.  
  Ver: `docs/resumos-tematicos/validacion-tiempo-y-leakage.md`.

## 5) Curva ROC y calibración

El cuaderno explica ROC con la idea de separar distribuciones de scores entre clases.

Recordatorio práctico:
- ROC/AUC mide *ranking* (qué tan bien ordenas), **no** calibración.
- Para decisiones con umbrales y coste, a veces importa más:
  - **PR-AUC** (si hay desbalance extremo)
  - **Expected Cost / Profit**
  - **Calibration** (Brier, ECE, reliability curve)

**Producción:** si vendes “probabilidades” (PD, churn), calibración es obligatoria. Si solo haces *ranking* (priorización de casos), puede ser secundario… hasta que alguien fije un threshold y se incendie.

## 6) Matriz de confusión y métricas

En el cuaderno:
- Accuracy / error de clasificación
- Recall/TPR
- FPR
- Precision

Yo siempre fuerzo el mapeo a negocio:

- `TP`: detectaste fraude → ahorras $.
- `FP`: bloqueaste cliente bueno → pierdes margen + churn.
- `FN`: se te cuela fraude → pérdida directa.
- `TN`: nada.

**Métrica de negocio real (ejemplo):**
\[
\text{Profit}(s)=TP(s)\cdot V_{TP} - FP(s)\cdot C_{FP} - FN(s)\cdot C_{FN}
\]

(poner números de verdad aquí cambia decisiones de modelo).

## 7) Mini-snippet (producción-friendly): evaluar ROC + calibración

> Nota: en el repo dejamos notebooks mínimos en `notebooks/python/`.

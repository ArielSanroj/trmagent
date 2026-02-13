# 2019-06-25 – Riesgo y aprendizaje estadístico (clase 1)

**Fuente:** `raw/scans/MECA MACHINE LEARNING NOTES.pdf`, páginas 1–6.

## 1) Terminología y tipos de aprendizaje

En los apuntes se separa el trabajo en:

- **Supervisado**: tienes variable objetivo `Y` y covariables `X`. Objetivo: aprender una función `f` que prediga `Y` con buen desempeño fuera de muestra.  
  Ejemplos típicos (y donde he visto dinero real): *scoring*, fraude, collections, churn, demanda.

- **No supervisado**: solo observas `X` y buscas estructura.  
  Ejemplos: segmentación, clustering, reducción de dimensión, detección de anomalías.

- **Semi-supervisado** (aparece mencionado): parte de los datos tiene etiqueta, parte no.

- **Aprendizaje por refuerzo** (mencionado): decisiones secuenciales con recompensa.

**Producción (2025–2026):**  
- Supervisado domina *pricing, riesgo, fraude, forecasting*.  
- RL se usa más en **recomendación / bidding / routing** y *supply chain* cuando hay simuladores o logs suficientes; sin eso suele quedarse en papers.

## 2) Formalización del problema de clasificación

Dataset:
\[
T=\{(x_1,y_1),\dots,(x_n,y_n)\},\quad (X,Y)\sim P(X,Y),\quad y\in\{0,1\}.
\]

Espacios:
- `X ∈ 𝒳` (en los apuntes: algo como `ℝ^p`).
- `Y ∈ {0,1}`.

Función/hipótesis:
\[
f:\mathcal{X}\to \{0,1\}.
\]

**Loss (0–1):**
\[
L(y,f(x))=\mathbb{I}(y\neq f(x)).
\]

## 3) Riesgo: lo que importa vs lo que se estima

- **Riesgo verdadero (generalización):**
\[
R(f)=\mathbb{E}[L(Y,f(X))].
\]

- **Riesgo empírico (entrenamiento):**
\[
\hat{R}_n(f)=\frac{1}{n}\sum_{i=1}^n L(y_i,f(x_i)).
\]

En producción, el “riesgo” no es abstracto: casi siempre es **pérdida económica esperada**.

Ejemplos de “riesgo = negocio”:
- Fraude: `R` ≈ coste de FP (rechazar bueno) + coste de FN (dejar pasar fraude) + fricción.
- Crédito: `R` ≈ pérdida esperada (EL = PD×LGD×EAD) + coste de capital + coste de adquisición.

> He visto modelos con +0.02 AUC que *perdían* dinero porque movían la frontera de decisión sin tener en cuenta costes asimétricos y capacidad operativa.

## 4) Clasificador óptimo de Bayes (idea central)

Para pérdida 0–1, el óptimo es:

\[
f^\*(x)=\mathbb{I}\big(P(Y=1\mid X=x)\ge 0.5\big)
\]

(misma idea que aparece en los apuntes).

**Por qué importa:** Bayes te dice que el “límite” es estimar bien la probabilidad condicional. Todo el resto son aproximaciones con sesgo/varianza.

## 5) “Caballitos de batalla” del curso

### 5.1 k-Nearest Neighbors (k-NN)

Procedimiento (en los apuntes):
1. Para un `x` nuevo, busca los `k` vecinos más cercanos (según una distancia).
2. Predice por mayoría (clasificación) o promedio (regresión).

**Producción (realista):**
- k-NN puro casi nunca entra a producción por **latencia** (búsqueda de vecinos) y **mantenimiento**.
- Sí aparece como **bloque**: recuperación de candidatos (ANN), embeddings + búsqueda aproximada, “similarity features”.

### 5.2 Modelo lineal (para clasificación/regresión)

Hipótesis lineal:
\[
f(x)=\beta^\top x.
\]

Para clasificación, se usa un umbral (en el cuaderno se menciona 0.5).

**2025–2026:** lo lineal sigue siendo brutalmente útil por:
- Interpretabilidad (auditoría / SR 11-7 / reguladores).
- Coste y latencia bajísimos.
- Buen rendimiento con buen feature engineering.

## 6) Bias vs variance (lo que te va a romper en práctica)

En el cuaderno aparece la separación:
- **Error de aproximación (sesgo)**: tu clase de modelos no puede representar la verdad.
- **Error de estimación (varianza)**: con datos finitos, estimas mal.

**Regla que pago con sangre:**  
> “Más complejo” casi siempre baja el error de train, pero **no** garantiza bajar el error fuera de muestra.

En `docs/resumos-tematicos/bias-variance-tradeoff.md` dejo una versión *operativa* (qué mirar en curvas, cuándo parar, cómo monitorear).

## 7) Checklist de producción (mínimo viable)

- ¿Qué es `Y` exactamente? (definición estable, sin leakage)
- ¿Qué ventana temporal usan las features?
- ¿Cómo se toma la decisión? (threshold/estrategia)
- ¿Cuál es el coste de FP vs FN? (matriz de costes)
- ¿Necesito probabilidades calibradas o solo ranking?
- ¿Qué latencia y coste por predicción tengo? (P95, P99)
- ¿Cómo monitoreo drift? (en `docs/resumos-tematicos/monitoreo-y-retraining.md`)

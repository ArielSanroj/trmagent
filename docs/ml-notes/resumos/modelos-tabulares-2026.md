# Modelos tabulares en 2026: qué se usa y por qué (opinión de producción)

## 1) Línea base que casi siempre debes tener
- Regresión logística / lineal (con buen feature engineering)
- Árbol + regularización

## 2) El “workhorse” de tabular
- Gradient Boosting:
  - LightGBM / XGBoost / CatBoost

**Por qué ganan:**
- Capturan interacciones no lineales bien
- Manejan missing / categóricas (CatBoost especialmente)
- Buen tradeoff rendimiento/latencia

## 3) ¿Transformers para tabular?
Controversial. Mi experiencia:
- En datasets tabulares medianos (10^5–10^6 filas, cientos de features),
  boosting suele ser igual o mejor con menos complejidad operativa.
- Transformers tabulares pueden ganar cuando:
  - hay mezcla fuerte de modalidades (texto + tabular + secuencias),
  - hay mucha data y feature learning útil,
  - tienes infraestructura y equipo para mantenerlo.

**Si no tienes evidencia sólida en tu dominio, no asumas que el transformer “va a ganar”.**

## 4) Números típicos (no promesa)
- Boosting vs logística:
  - +0.01 a +0.04 AUC en riesgo/fraude (dependiendo no-linealidad)
- Costo operacional:
  - logística: milisegundos y barato
  - boosting: ms–decenas de ms (depende)
  - deep: puede ser 10–100x más caro si no optimizas

## 5) Requisito regulatorio
Si estás en banca/seguros:
- interpretabilidad, documentación, estabilidad y bias checks pesan tanto como AUC.

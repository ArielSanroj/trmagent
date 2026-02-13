# Calibración de probabilidades (cuando el score es un producto)

En tus apuntes aparece ROC (ranking). Para riesgo real necesitas además **calibración**.

## 1) Señales de mala calibración
- Predices 0.8 y la tasa real de evento es 0.5.
- La curva de reliability se separa de la diagonal.
- El modelo “se rompe” al cambiar el mix de población.

## 2) Métodos comunes
- **Platt scaling** (logística sobre el score)
- **Isotonic regression** (no paramétrica; ojo overfit si hay poca data)
- **Beta calibration** (a veces mejor que Platt)

## 3) En producción
- Calibrar con datos recientes y representativos.
- Monitorear calibración por cohorte y segmento.
- Si cambias estrategia o políticas, recalibrar.

## 4) Métricas
- Brier score
- ECE (Expected Calibration Error)
- Log loss (sensible a calibración)

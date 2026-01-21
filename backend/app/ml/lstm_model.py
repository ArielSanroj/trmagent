"""
Modelo LSTM (Long Short-Term Memory) para prediccion de TRM
Deep Learning para capturar patrones temporales complejos
"""
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from decimal import Decimal
import logging
import pickle
import os

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    from sklearn.preprocessing import MinMaxScaler
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logging.warning("TensorFlow not installed. Install with: pip install tensorflow")

logger = logging.getLogger(__name__)


class LSTMModel:
    """
    Modelo LSTM para prediccion de TRM
    Arquitectura de red neuronal recurrente
    """

    def __init__(
        self,
        lookback: int = 60,
        n_features: int = 1,
        lstm_units: int = 50,
        dropout: float = 0.2
    ):
        self.lookback = lookback  # Dias de historia para predecir
        self.n_features = n_features
        self.lstm_units = lstm_units
        self.dropout = dropout

        self.model = None
        self.scaler = MinMaxScaler(feature_range=(0, 1)) if TF_AVAILABLE else None
        self.is_fitted = False
        self.model_version = "lstm_v1"
        self.last_trained = None

    def _build_model(self):
        """Construir arquitectura del modelo LSTM"""
        if not TF_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM model. Install with: pip install tensorflow")
        
        model = Sequential([
            # Primera capa LSTM
            LSTM(
                self.lstm_units,
                return_sequences=True,
                input_shape=(self.lookback, self.n_features)
            ),
            BatchNormalization(),
            Dropout(self.dropout),

            # Segunda capa LSTM
            LSTM(self.lstm_units, return_sequences=True),
            BatchNormalization(),
            Dropout(self.dropout),

            # Tercera capa LSTM
            LSTM(self.lstm_units, return_sequences=False),
            BatchNormalization(),
            Dropout(self.dropout),

            # Capas densas
            Dense(25, activation='relu'),
            Dense(1)
        ])

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )

        return model

    def prepare_data(
        self,
        trm_history: List[dict],
        indicators: Optional[dict] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Preparar datos para LSTM

        Args:
            trm_history: Lista de {date, value}
            indicators: Indicadores adicionales

        Returns:
            Tuple de (X, y) arrays
        """
        # Crear DataFrame
        df = pd.DataFrame(trm_history)
        df = df.sort_values("date").reset_index(drop=True)

        # Extraer valores
        values = df["value"].astype(float).values.reshape(-1, 1)

        # Normalizar
        scaled_data = self.scaler.fit_transform(values)

        # Crear secuencias
        X, y = [], []
        for i in range(self.lookback, len(scaled_data)):
            X.append(scaled_data[i - self.lookback:i, 0])
            y.append(scaled_data[i, 0])

        X = np.array(X)
        y = np.array(y)

        # Reshape para LSTM [samples, timesteps, features]
        X = np.reshape(X, (X.shape[0], X.shape[1], self.n_features))

        return X, y

    def train(
        self,
        trm_history: List[dict],
        indicators: Optional[dict] = None,
        epochs: int = 100,
        batch_size: int = 32,
        validation_split: float = 0.2,
        **kwargs
    ) -> bool:
        """
        Entrenar modelo LSTM

        Args:
            trm_history: Historico de TRM
            indicators: Indicadores macroeconomicos
            epochs: Numero de epocas
            batch_size: Tamano del batch
            validation_split: Proporcion para validacion

        Returns:
            True si entrenamiento exitoso
        """
        if not TF_AVAILABLE:
            logger.error("TensorFlow not available")
            return False

        try:
            # Verificar datos suficientes
            if len(trm_history) < self.lookback + 30:
                logger.error(f"Insufficient data. Need at least {self.lookback + 30} days")
                return False

            # Preparar datos
            X, y = self.prepare_data(trm_history, indicators)

            if len(X) == 0:
                logger.error("No training data after preprocessing")
                return False

            # Construir modelo
            self.model = self._build_model()

            # Callbacks
            early_stop = EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            )
            reduce_lr = ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=0.0001
            )

            # Entrenar
            history = self.model.fit(
                X, y,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=validation_split,
                callbacks=[early_stop, reduce_lr],
                verbose=1
            )

            self.is_fitted = True
            self.last_trained = datetime.utcnow()

            logger.info(f"LSTM model trained. Final loss: {history.history['loss'][-1]:.6f}")
            return True

        except Exception as e:
            logger.error(f"Error training LSTM model: {e}")
            return False

    def predict(
        self,
        trm_history: List[dict],
        days_ahead: int = 30,
        indicators: Optional[dict] = None
    ) -> List[dict]:
        """
        Generar predicciones

        Args:
            trm_history: Historico reciente de TRM (al menos lookback dias)
            days_ahead: Dias a predecir
            indicators: Indicadores para el futuro

        Returns:
            Lista de predicciones
        """
        if not self.is_fitted or self.model is None:
            logger.error("Model not fitted. Call train() first")
            return []

        try:
            # Preparar datos
            df = pd.DataFrame(trm_history)
            df = df.sort_values("date").reset_index(drop=True)
            values = df["value"].astype(float).values.reshape(-1, 1)

            # Normalizar con el scaler existente
            scaled_data = self.scaler.transform(values)

            # Tomar ultimos lookback valores
            input_seq = scaled_data[-self.lookback:].reshape(1, self.lookback, 1)

            predictions = []
            current_seq = input_seq.copy()
            base_date = df["date"].iloc[-1]

            for i in range(days_ahead):
                # Predecir siguiente valor
                next_pred = self.model.predict(current_seq, verbose=0)

                # Desnormalizar
                next_value = self.scaler.inverse_transform(next_pred)[0, 0]

                # Calcular fecha objetivo
                target_date = base_date + timedelta(days=i + 1)

                # Estimar intervalo de confianza (basado en volatilidad historica)
                std = np.std(values[-30:])
                lower = next_value - (1.645 * std)  # 90% CI
                upper = next_value + (1.645 * std)

                predictions.append({
                    "target_date": target_date if isinstance(target_date, date) else target_date.date(),
                    "predicted_value": Decimal(str(round(float(next_value), 2))),
                    "lower_bound": Decimal(str(round(float(lower), 2))),
                    "upper_bound": Decimal(str(round(float(upper), 2))),
                    "confidence": Decimal("0.90"),
                    "model_type": "lstm",
                    "model_version": self.model_version
                })

                # Actualizar secuencia para siguiente prediccion
                current_seq = np.roll(current_seq, -1, axis=1)
                current_seq[0, -1, 0] = next_pred[0, 0]

            return predictions

        except Exception as e:
            logger.error(f"Error generating LSTM predictions: {e}")
            return []

    def save_model(self, path: str) -> bool:
        """Guardar modelo entrenado"""
        if not self.is_fitted:
            return False

        try:
            # Guardar modelo Keras
            self.model.save(f"{path}_model.keras")

            # Guardar scaler y metadata
            with open(f"{path}_meta.pkl", "wb") as f:
                pickle.dump({
                    "scaler": self.scaler,
                    "lookback": self.lookback,
                    "n_features": self.n_features,
                    "version": self.model_version,
                    "trained_at": self.last_trained
                }, f)

            return True
        except Exception as e:
            logger.error(f"Error saving LSTM model: {e}")
            return False

    def load_model(self, path: str) -> bool:
        """Cargar modelo guardado"""
        try:
            # Cargar modelo Keras
            self.model = load_model(f"{path}_model.keras")

            # Cargar metadata
            with open(f"{path}_meta.pkl", "rb") as f:
                meta = pickle.load(f)
                self.scaler = meta["scaler"]
                self.lookback = meta["lookback"]
                self.n_features = meta["n_features"]
                self.model_version = meta["version"]
                self.last_trained = meta["trained_at"]

            self.is_fitted = True
            return True
        except Exception as e:
            logger.error(f"Error loading LSTM model: {e}")
            return False


# Instancia singleton
lstm_model = LSTMModel()

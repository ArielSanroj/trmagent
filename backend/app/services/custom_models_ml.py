"""Funciones ML para entrenamiento y prediccion."""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.core.database import SessionLocal
from app.models.database_models import TRMHistory
from .custom_models_config import ModelConfig


def train_prophet(df: pd.DataFrame, config: ModelConfig, logger) -> tuple:
    """Entrenar modelo Prophet"""
    try:
        from prophet import Prophet

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            **config.hyperparameters.get("prophet", {})
        )

        model.fit(df)

        train_size = int(len(df) * 0.8)
        train_df = df[:train_size]
        test_df = df[train_size:]

        model_cv = Prophet()
        model_cv.fit(train_df)

        future = model_cv.make_future_dataframe(periods=len(test_df))
        forecast = model_cv.predict(future)

        test_predictions = forecast.tail(len(test_df))["yhat"].values
        test_actual = test_df["y"].values
        rmse = np.sqrt(np.mean((test_predictions - test_actual) ** 2))
        mape = np.mean(np.abs((test_actual - test_predictions) / test_actual)) * 100

        return model, {"rmse": rmse, "mape": mape}

    except Exception as exc:
        logger.error(f"Prophet training error: {exc}")
        return None, {}


def train_lstm(df: pd.DataFrame, config: ModelConfig, logger) -> tuple:
    """Entrenar modelo LSTM"""
    try:
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import LSTM, Dense, Dropout
        from sklearn.preprocessing import MinMaxScaler

        scaler = MinMaxScaler()
        scaled_data = scaler.fit_transform(df[["y"]].values)

        lookback = config.hyperparameters.get("lstm", {}).get("lookback", 60)
        X, y = [], []
        for i in range(lookback, len(scaled_data)):
            X.append(scaled_data[i - lookback:i, 0])
            y.append(scaled_data[i, 0])

        X, y = np.array(X), np.array(y)
        X = X.reshape((X.shape[0], X.shape[1], 1))

        train_size = int(len(X) * 0.8)
        X_train, X_test = X[:train_size], X[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]

        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(lookback, 1)),
            Dropout(0.2),
            LSTM(50, return_sequences=False),
            Dropout(0.2),
            Dense(25),
            Dense(1)
        ])

        model.compile(optimizer="adam", loss="mean_squared_error")
        model.fit(
            X_train, y_train,
            batch_size=32,
            epochs=config.hyperparameters.get("lstm", {}).get("epochs", 50),
            validation_split=0.1,
            verbose=0
        )

        predictions = model.predict(X_test)
        predictions = scaler.inverse_transform(predictions)
        y_test_actual = scaler.inverse_transform(y_test.reshape(-1, 1))

        rmse = np.sqrt(np.mean((predictions - y_test_actual) ** 2))
        mape = np.mean(np.abs((y_test_actual - predictions) / y_test_actual)) * 100

        model_bundle = {
            "model": model,
            "scaler": scaler,
            "lookback": lookback
        }

        return model_bundle, {"rmse": float(rmse), "mape": float(mape[0])}

    except Exception as exc:
        logger.error(f"LSTM training error: {exc}")
        return None, {}


def train_arima(df: pd.DataFrame, config: ModelConfig, logger) -> tuple:
    """Entrenar modelo ARIMA"""
    try:
        from statsmodels.tsa.arima.model import ARIMA

        train_size = int(len(df) * 0.8)
        train_data = df["y"].values[:train_size]
        test_data = df["y"].values[train_size:]

        order = config.hyperparameters.get("arima", {}).get("order", (5, 1, 0))
        model = ARIMA(train_data, order=order)
        model_fit = model.fit()

        predictions = model_fit.forecast(steps=len(test_data))

        rmse = np.sqrt(np.mean((predictions - test_data) ** 2))
        mape = np.mean(np.abs((test_data - predictions) / test_data)) * 100

        final_model = ARIMA(df["y"].values, order=order)
        final_fit = final_model.fit()

        return final_fit, {"rmse": float(rmse), "mape": float(mape)}

    except Exception as exc:
        logger.error(f"ARIMA training error: {exc}")
        return None, {}


def predict_prophet(model, horizon: int, logger) -> Optional[List[float]]:
    """Predicciones con Prophet"""
    if not model:
        return None
    try:
        future = model.make_future_dataframe(periods=horizon)
        forecast = model.predict(future)
        return forecast.tail(horizon)["yhat"].tolist()
    except Exception as exc:
        logger.error(f"Prophet prediction error: {exc}")
        return None


def predict_lstm(model_bundle, horizon: int, logger) -> Optional[List[float]]:
    """Predicciones con LSTM"""
    if not model_bundle:
        return None
    try:
        model = model_bundle["model"]
        scaler = model_bundle["scaler"]
        lookback = model_bundle["lookback"]

        db = SessionLocal()
        try:
            recent_data = db.query(TRMHistory).order_by(
                TRMHistory.date.desc()
            ).limit(lookback).all()

            if len(recent_data) < lookback:
                return None

            values = [float(t.value) for t in reversed(recent_data)]
            scaled = scaler.transform(np.array(values).reshape(-1, 1))

            predictions = []
            current_batch = scaled[-lookback:].reshape(1, lookback, 1)

            for _ in range(horizon):
                pred = model.predict(current_batch, verbose=0)[0, 0]
                predictions.append(pred)
                current_batch = np.append(current_batch[:, 1:, :], [[[pred]]], axis=1)

            predictions = scaler.inverse_transform(
                np.array(predictions).reshape(-1, 1)
            ).flatten().tolist()

            return predictions

        finally:
            db.close()

    except Exception as exc:
        logger.error(f"LSTM prediction error: {exc}")
        return None


def predict_arima(model, horizon: int, logger) -> Optional[List[float]]:
    """Predicciones con ARIMA"""
    if not model:
        return None
    try:
        forecast = model.forecast(steps=horizon)
        return forecast.tolist()
    except Exception as exc:
        logger.error(f"ARIMA prediction error: {exc}")
        return None


def combine_predictions(
    horizon_days: int,
    config: ModelConfig,
    prophet_preds: Optional[List[float]],
    lstm_preds: Optional[List[float]],
    arima_preds: Optional[List[float]]
) -> List[Dict[str, Any]]:
    """Combinar predicciones con pesos"""
    predictions: List[Dict[str, Any]] = []

    for i in range(horizon_days):
        target_date = datetime.utcnow().date() + timedelta(days=i + 1)
        values = []
        weights = []

        if prophet_preds and i < len(prophet_preds):
            values.append(prophet_preds[i])
            weights.append(config.prophet_weight)

        if lstm_preds and i < len(lstm_preds):
            values.append(lstm_preds[i])
            weights.append(config.lstm_weight)

        if arima_preds and i < len(arima_preds):
            values.append(arima_preds[i])
            weights.append(config.arima_weight)

        if not values:
            continue

        total_weight = sum(weights)
        weighted_value = sum(v * w for v, w in zip(values, weights)) / total_weight

        if len(values) > 1:
            max_dev = max(values) - min(values)
            confidence = max(0.5, 1 - (max_dev / weighted_value * 10))
        else:
            confidence = 0.75

        predictions.append({
            "target_date": target_date.isoformat(),
            "predicted_value": round(weighted_value, 2),
            "confidence": round(confidence, 4),
            "model_predictions": {
                "prophet": prophet_preds[i] if prophet_preds and i < len(prophet_preds) else None,
                "lstm": lstm_preds[i] if lstm_preds and i < len(lstm_preds) else None,
                "arima": arima_preds[i] if arima_preds and i < len(arima_preds) else None
            }
        })

    return predictions

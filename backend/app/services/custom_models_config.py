"""Config y paths para modelos personalizados."""
from pathlib import Path
from typing import Optional, List, Dict

# Directorio para guardar modelos
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


class ModelConfig:
    """Configuracion de modelo personalizado"""

    def __init__(
        self,
        model_type: str = "ensemble",
        prophet_weight: float = 0.4,
        lstm_weight: float = 0.4,
        arima_weight: float = 0.2,
        lookback_days: int = 365,
        forecast_horizon: int = 7,
        confidence_threshold: float = 0.90,
        features: Optional[List[str]] = None,
        hyperparameters: Optional[Dict] = None
    ):
        self.model_type = model_type
        self.prophet_weight = prophet_weight
        self.lstm_weight = lstm_weight
        self.arima_weight = arima_weight
        self.lookback_days = lookback_days
        self.forecast_horizon = forecast_horizon
        self.confidence_threshold = confidence_threshold
        self.features = features or ["trm", "oil_price", "dxy_index"]
        self.hyperparameters = hyperparameters or {}

    def to_dict(self) -> Dict:
        return {
            "model_type": self.model_type,
            "prophet_weight": self.prophet_weight,
            "lstm_weight": self.lstm_weight,
            "arima_weight": self.arima_weight,
            "lookback_days": self.lookback_days,
            "forecast_horizon": self.forecast_horizon,
            "confidence_threshold": self.confidence_threshold,
            "features": self.features,
            "hyperparameters": self.hyperparameters
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ModelConfig":
        return cls(**data)

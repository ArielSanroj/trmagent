# Lazy imports to handle missing dependencies
import logging

logger = logging.getLogger(__name__)

# Always available
from .model_registry import MLModelRegistry

# Try to import adapters - may fail if underlying libraries not installed
try:
    from .prophet_adapter import ProphetModelAdapter
except ImportError:
    ProphetModelAdapter = None
    logger.warning("ProphetModelAdapter not available - Prophet not installed")

try:
    from .lstm_adapter import LSTMModelAdapter
except (ImportError, NameError):
    LSTMModelAdapter = None
    logger.warning("LSTMModelAdapter not available - TensorFlow not installed")

try:
    from .ensemble_adapter import EnsembleModelAdapter
except (ImportError, NameError):
    EnsembleModelAdapter = None
    logger.warning("EnsembleModelAdapter not available - dependencies missing")

__all__ = [
    "ProphetModelAdapter",
    "LSTMModelAdapter",
    "EnsembleModelAdapter",
    "MLModelRegistry"
]

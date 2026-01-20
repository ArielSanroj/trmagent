
import sys
import os
from unittest.mock import MagicMock
from decimal import Decimal

# Add backend to sys.path
sys.path.append(os.getcwd())

# Mock dependencies BEFORE importing service to avoid DB connections
sys.modules['app.core.database'] = MagicMock()
sys.modules['app.models.database_models'] = MagicMock()
sys.modules['app.services.risk_management'] = MagicMock()
sys.modules['app.services.notification_service'] = MagicMock()
sys.modules['app.services.compliance_service'] = MagicMock()

# --- FIX for DB Query Mocks ---
# Create a Mock for Prediction.target_date that accepts comparisons
config_mock = MagicMock()
config_mock.__ge__.return_value = True
config_mock.__le__.return_value = True
# Assign it to the mocked module
sys.modules['app.models.database_models'].Prediction.target_date = config_mock

# Setup SessionLocal to return a mock session that returns [] for queries
mock_session_instance = MagicMock()
mock_session_instance.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
sys.modules['app.core.database'].SessionLocal.return_value = mock_session_instance

# Mock ml model
mock_ensemble = MagicMock()
sys.modules['app.ml.ensemble_model'] = MagicMock()
sys.modules['app.ml.ensemble_model'].ensemble_model = mock_ensemble

# Import the service to test
try:
    from app.services.hedging_service import hedging_service, HedgingAction
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def simulate_scenario(scenario_name, amount, volatility, trend):
    print(f"\n{'='*60}")
    print(f"🔎 SIMULACIÓN: {scenario_name}")
    print(f"{'='*60}")
    
    # Setup mock predictions
    # We create a fake list of predictions with specific volatility
    predictions_mock = [
        {
            "predicted_value": 4200, 
            "model_volatility": volatility,
            "target_date": "2024-01-01"
        } 
    ] * 30
    
    # Mock ensemble behavior
    mock_ensemble.predict.return_value = predictions_mock
    mock_ensemble.get_trend.return_value = trend
    
    # 1. Calculate Risk Score
    risk = hedging_service.calculate_market_risk(predictions_mock)
    print(f"\n📊 ANÁLISIS DE RIESGO")
    print(f"   • Score Total:      {risk.total_score:.1f} / 100")
    print(f"   • Volatilidad (IA): {risk.volatility_score:.1f} (Discrepancia entre modelos)")
    print(f"   • Riesgo Tendencia: {risk.trend_risk:.1f} ({trend})")
    print(f"   • Nivel:            {risk.risk_level}")
    
    # 2. Get Hedging Advice
    print(f"\n🛡️ ASISTENTE DE COBERTURA")
    print(f"   INPUT: Empresa quiere proteger ${amount:,.2f} USD a 30 días")
    
    advice = hedging_service.get_hedging_recommendation(
        amount=Decimal(str(amount)),
        time_horizon_days=30,
        current_exposure=Decimal("0")
    )
    
    print(f"   RESULTADO:")
    print(f"   • Acción:           {advice.action}")
    print(f"   • Cubrir:           ${advice.amount_to_hedge:,.2f}")
    print(f"   • Urgencia:         {advice.urgency}")
    print(f"   • Razonamiento:")
    for r in advice.reasoning:
        print(f"     - {r}")

# --- EXECUTION ---

# Scenario 1: High Uncertainty (Models disagree) + Market going against us (Up)
simulate_scenario(
    scenario_name="Alta Incertidumbre + Tendencia Alcista", 
    amount=500000, 
    volatility=60, # High variance between models
    trend="ALCISTA"
)

# Scenario 2: Calm Market
simulate_scenario(
    scenario_name="Mercado Estable", 
    amount=150000, 
    volatility=10, # Low variance
    trend="NEUTRAL"
)

# Scenario 3: Favorable Market (Peso strengthening)
simulate_scenario(
    scenario_name="Tendencia Bajista (Peso Fortaleciéndose)", 
    amount=1000000, 
    volatility=15, 
    trend="BAJISTA"
)

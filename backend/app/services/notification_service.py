"""
Servicio de Notificaciones - Telegram, Slack, Email
Alerta cuando se detectan oportunidades de trading
"""
import logging
from typing import Optional
from decimal import Decimal
import httpx

from app.core.config import settings
from app.services.decision_engine import TradingDecision
from app.models.database_models import SignalAction

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Servicio de notificaciones multicanal
    Soporta: Telegram, Slack, Webhooks
    """

    def __init__(self):
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = settings.TELEGRAM_CHAT_ID
        self.slack_webhook = settings.SLACK_WEBHOOK_URL
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    # ==================== TELEGRAM ====================

    async def send_telegram(
        self,
        message: str,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Enviar mensaje por Telegram

        Args:
            message: Texto del mensaje
            chat_id: Chat ID (usa default si no se provee)

        Returns:
            True si se envio exitosamente
        """
        if not self.telegram_token:
            logger.warning("Telegram bot token not configured")
            return False

        target_chat = chat_id or self.telegram_chat_id
        if not target_chat:
            logger.warning("Telegram chat ID not configured")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": target_chat,
                "text": message,
                "parse_mode": "HTML"
            }

            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            logger.info(f"Telegram message sent to {target_chat}")
            return True

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    # ==================== SLACK ====================

    async def send_slack(
        self,
        message: str,
        webhook_url: Optional[str] = None,
        channel: Optional[str] = None
    ) -> bool:
        """
        Enviar mensaje por Slack

        Args:
            message: Texto del mensaje
            webhook_url: URL del webhook (usa default si no se provee)
            channel: Canal especifico (opcional)

        Returns:
            True si se envio exitosamente
        """
        url = webhook_url or self.slack_webhook
        if not url:
            logger.warning("Slack webhook URL not configured")
            return False

        try:
            payload = {
                "text": message,
                "mrkdwn": True
            }
            if channel:
                payload["channel"] = channel

            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            logger.info("Slack message sent")
            return True

        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
            return False

    # ==================== WEBHOOKS ====================

    async def send_webhook(
        self,
        url: str,
        data: dict,
        headers: Optional[dict] = None
    ) -> bool:
        """
        Enviar notificacion a webhook personalizado

        Args:
            url: URL del webhook
            data: Datos a enviar
            headers: Headers adicionales

        Returns:
            True si se envio exitosamente
        """
        try:
            response = await self.client.post(
                url,
                json=data,
                headers=headers or {}
            )
            response.raise_for_status()

            logger.info(f"Webhook notification sent to {url}")
            return True

        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            return False

    # ==================== TRADING ALERTS ====================

    def format_trading_alert(self, decision: TradingDecision) -> str:
        """
        Formatear alerta de trading para enviar

        Args:
            decision: Decision de trading

        Returns:
            Mensaje formateado
        """
        # Emoji segun accion
        if decision.action == SignalAction.BUY_USD:
            emoji = "🟢"
            action_text = "COMPRAR USD"
        elif decision.action == SignalAction.SELL_USD:
            emoji = "🔴"
            action_text = "VENDER USD"
        else:
            emoji = "⚪"
            action_text = "MANTENER"

        # Emoji de fuerza
        strength_emoji = {
            "strong": "💪",
            "moderate": "👌",
            "weak": "👎"
        }.get(decision.signal_strength.value, "")

        message = f"""
{emoji} <b>ALERTA TRM AGENT</b> {emoji}

<b>Senal:</b> {action_text} {strength_emoji}
<b>Confianza:</b> {decision.confidence:.1%}
<b>TRM Actual:</b> ${decision.current_trm:,.2f}
<b>TRM Predicho:</b> ${decision.predicted_trm:,.2f}
<b>Retorno Esperado:</b> {decision.expected_return:.2%}
<b>Riesgo:</b> {decision.risk_score:.2%}

<b>Analisis:</b>
{decision.reasoning}

<b>Aprobado:</b> {'✅ SI' if decision.approved else '❌ NO'}

<i>Generado: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</i>
"""
        return message.strip()

    def format_slack_trading_alert(self, decision: TradingDecision) -> str:
        """Formatear alerta de trading para Slack"""
        if decision.action == SignalAction.BUY_USD:
            emoji = ":large_green_circle:"
            action_text = "COMPRAR USD"
        elif decision.action == SignalAction.SELL_USD:
            emoji = ":red_circle:"
            action_text = "VENDER USD"
        else:
            emoji = ":white_circle:"
            action_text = "MANTENER"

        message = f"""
{emoji} *ALERTA TRM AGENT* {emoji}

*Senal:* {action_text}
*Confianza:* {decision.confidence:.1%}
*TRM Actual:* ${decision.current_trm:,.2f}
*TRM Predicho:* ${decision.predicted_trm:,.2f}
*Retorno Esperado:* {decision.expected_return:.2%}
*Riesgo:* {decision.risk_score:.2%}

> {decision.reasoning}

*Aprobado:* {'✅' if decision.approved else '❌'}
"""
        return message.strip()

    async def send_trading_alert(
        self,
        decision: TradingDecision,
        telegram_chat_id: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        custom_webhook: Optional[str] = None
    ) -> dict:
        """
        Enviar alerta de trading a todos los canales configurados

        Args:
            decision: Decision de trading
            telegram_chat_id: Chat ID especifico de Telegram
            slack_webhook: Webhook especifico de Slack
            custom_webhook: Webhook personalizado

        Returns:
            Diccionario con resultados de cada canal
        """
        results = {}

        # Solo enviar alertas para senales aprobadas o si es HOLD con razon importante
        if not decision.approved and decision.action != SignalAction.HOLD:
            logger.info("Skipping alert for non-approved signal")
            return {"skipped": True, "reason": "Signal not approved"}

        # Telegram
        if self.telegram_token and (telegram_chat_id or self.telegram_chat_id):
            telegram_msg = self.format_trading_alert(decision)
            results["telegram"] = await self.send_telegram(
                telegram_msg,
                chat_id=telegram_chat_id
            )

        # Slack
        if slack_webhook or self.slack_webhook:
            slack_msg = self.format_slack_trading_alert(decision)
            results["slack"] = await self.send_slack(
                slack_msg,
                webhook_url=slack_webhook
            )

        # Custom webhook
        if custom_webhook:
            webhook_data = {
                "action": decision.action.value,
                "confidence": float(decision.confidence),
                "current_trm": float(decision.current_trm),
                "predicted_trm": float(decision.predicted_trm),
                "expected_return": float(decision.expected_return),
                "risk_score": float(decision.risk_score),
                "reasoning": decision.reasoning,
                "approved": decision.approved,
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            }
            results["webhook"] = await self.send_webhook(custom_webhook, webhook_data)

        return results


# Instancia singleton
notification_service = NotificationService()

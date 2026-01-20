"""
Email Service - Alertas por email usando SendGrid
"""
import logging
from typing import List, Optional
from datetime import datetime

from app.core.config import settings

# Intentar importar SendGrid
try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    logging.warning("SendGrid not installed. Install with: pip install sendgrid")

logger = logging.getLogger(__name__)


class EmailService:
    """
    Servicio de envio de emails usando SendGrid
    """

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = "alerts@trmagent.com"
        self.from_name = "TRM Agent"

        if SENDGRID_AVAILABLE and self.api_key:
            self.client = SendGridAPIClient(api_key=self.api_key)
        else:
            self.client = None

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Enviar email

        Args:
            to_email: Email destino
            subject: Asunto
            html_content: Contenido HTML
            plain_content: Contenido texto plano (opcional)

        Returns:
            True si se envio exitosamente
        """
        if not self.client:
            logger.warning("SendGrid not configured, email not sent")
            return False

        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )

            if plain_content:
                message.add_content(Content("text/plain", plain_content))

            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent to {to_email}")
                return True
            else:
                logger.error(f"Email failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False

    def send_trading_alert(
        self,
        to_email: str,
        action: str,
        confidence: float,
        current_trm: float,
        predicted_trm: float,
        expected_return: float,
        reasoning: str
    ) -> bool:
        """
        Enviar alerta de trading por email
        """
        # Determinar color segun accion
        if action == "BUY_USD":
            color = "#00c853"
            emoji = "🟢"
            action_text = "COMPRAR USD"
        elif action == "SELL_USD":
            color = "#ff5252"
            emoji = "🔴"
            action_text = "VENDER USD"
        else:
            color = "#999999"
            emoji = "⚪"
            action_text = "MANTENER"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #eee; }}
                .signal-box {{ background: {color}20; border-left: 4px solid {color}; padding: 20px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
                .signal-action {{ font-size: 24px; font-weight: bold; color: {color}; }}
                .metrics {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }}
                .metric {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
                .metric-label {{ font-size: 12px; color: #666; }}
                .metric-value {{ font-size: 18px; font-weight: bold; color: #1a1a2e; }}
                .reasoning {{ background: #f0f7ff; padding: 20px; border-radius: 8px; margin-top: 20px; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>TRM Agent</h1>
                    <p>Alerta de Trading USD/COP</p>
                </div>
                <div class="content">
                    <div class="signal-box">
                        <span style="font-size: 32px;">{emoji}</span>
                        <div class="signal-action">{action_text}</div>
                        <div>Confianza: {confidence*100:.1f}%</div>
                    </div>

                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-label">TRM Actual</div>
                            <div class="metric-value">${current_trm:,.2f}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">TRM Predicho</div>
                            <div class="metric-value">${predicted_trm:,.2f}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Retorno Esperado</div>
                            <div class="metric-value" style="color: {'#00c853' if expected_return > 0 else '#ff5252'}">
                                {expected_return*100:+.2f}%
                            </div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Fecha</div>
                            <div class="metric-value">{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
                        </div>
                    </div>

                    <div class="reasoning">
                        <strong>Analisis:</strong>
                        <p>{reasoning}</p>
                    </div>
                </div>
                <div class="footer">
                    <p>Este email fue generado automaticamente por TRM Agent.</p>
                    <p>Las predicciones son estimaciones basadas en modelos ML y no garantizan resultados.</p>
                </div>
            </div>
        </body>
        </html>
        """

        subject = f"{emoji} TRM Agent: {action_text} - Confianza {confidence*100:.0f}%"

        return self.send_email(to_email, subject, html_content)

    def send_daily_report(
        self,
        to_email: str,
        trm_current: float,
        trm_change: float,
        predictions: List[dict],
        portfolio_summary: dict
    ) -> bool:
        """
        Enviar reporte diario por email
        """
        trend = "📈 ALCISTA" if predictions and predictions[0].get("trend") == "ALCISTA" else "📉 BAJISTA"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #ffffff; padding: 30px; border: 1px solid #eee; }}
                .section {{ margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
                .section-title {{ font-weight: bold; color: #1a1a2e; margin-bottom: 15px; }}
                .value-big {{ font-size: 28px; font-weight: bold; color: #1a1a2e; }}
                .change {{ font-size: 14px; color: {'#00c853' if trm_change > 0 else '#ff5252'}; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
                th {{ background: #f0f0f0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>TRM Agent</h1>
                    <p>Reporte Diario - {datetime.now().strftime('%Y-%m-%d')}</p>
                </div>
                <div class="content">
                    <div class="section">
                        <div class="section-title">TRM Actual</div>
                        <div class="value-big">${trm_current:,.2f}</div>
                        <div class="change">{'+' if trm_change > 0 else ''}{trm_change:.2f}% vs ayer</div>
                    </div>

                    <div class="section">
                        <div class="section-title">Tendencia: {trend}</div>
                        <table>
                            <tr>
                                <th>Fecha</th>
                                <th>Prediccion</th>
                                <th>Confianza</th>
                            </tr>
                            {''.join(f'''
                            <tr>
                                <td>{p.get("target_date", "")}</td>
                                <td>${p.get("predicted_value", 0):,.2f}</td>
                                <td>{p.get("confidence", 0)*100:.0f}%</td>
                            </tr>
                            ''' for p in predictions[:5])}
                        </table>
                    </div>

                    <div class="section">
                        <div class="section-title">Resumen Portafolio (Paper Trading)</div>
                        <table>
                            <tr><td>USD Balance</td><td>${portfolio_summary.get('total_usd', 0):,.2f}</td></tr>
                            <tr><td>COP Balance</td><td>${portfolio_summary.get('total_cop', 0):,.0f}</td></tr>
                            <tr><td>Valor Total</td><td>${portfolio_summary.get('total_value_cop', 0):,.0f} COP</td></tr>
                            <tr><td>PnL Realizado</td><td>${portfolio_summary.get('realized_pnl', 0):,.0f} COP</td></tr>
                        </table>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        subject = f"📊 TRM Agent: Reporte Diario - TRM ${trm_current:,.2f}"

        return self.send_email(to_email, subject, html_content)

    def send_batch_emails(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str
    ) -> dict:
        """
        Enviar emails en batch

        Returns:
            Dict con resultados por email
        """
        results = {}
        for email in to_emails:
            results[email] = self.send_email(email, subject, html_content)
        return results


# Instancia singleton
email_service = EmailService()

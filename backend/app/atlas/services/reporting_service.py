"""
ATLAS - Reporting Service
Generacion de reportes de cobertura y analisis de costos.
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID
import io

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.atlas.models.atlas_models import (
    Exposure,
    Trade,
    HedgeOrder,
    Counterparty,
    ExposureType,
    ExposureStatus,
    TradeStatus,
)
from app.atlas.models.schemas import (
    CoverageReport,
    MaturityLadder,
    CostAnalysis,
)

logger = logging.getLogger(__name__)


class ReportingService:
    """Servicio de reportes para ATLAS"""

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Coverage Report
    # =========================================================================

    def get_coverage_report(
        self,
        company_id: UUID,
        as_of_date: Optional[date] = None,
        currency: str = "USD"
    ) -> CoverageReport:
        """
        Generar reporte de cobertura.

        Muestra % cubierto por tipo, contraparte y vencimiento.
        """
        if not as_of_date:
            as_of_date = date.today()

        # Query base
        exposures = self.db.query(Exposure).filter(
            Exposure.company_id == company_id,
            Exposure.currency == currency,
            Exposure.status.in_([
                ExposureStatus.OPEN,
                ExposureStatus.PARTIALLY_HEDGED,
                ExposureStatus.FULLY_HEDGED
            ]),
            Exposure.due_date >= as_of_date
        ).all()

        # Totales por tipo
        payables = [e for e in exposures if e.exposure_type == ExposureType.PAYABLE]
        receivables = [e for e in exposures if e.exposure_type == ExposureType.RECEIVABLE]

        total_payables = sum(e.amount for e in payables)
        total_receivables = sum(e.amount for e in receivables)
        hedged_payables = sum(e.amount_hedged or Decimal("0") for e in payables)
        hedged_receivables = sum(e.amount_hedged or Decimal("0") for e in receivables)

        net_exposure = total_payables - total_receivables

        payables_coverage = (
            (hedged_payables / total_payables * 100) if total_payables > 0 else Decimal("0")
        )
        receivables_coverage = (
            (hedged_receivables / total_receivables * 100) if total_receivables > 0 else Decimal("0")
        )

        total_exposure = total_payables + total_receivables
        total_hedged = hedged_payables + hedged_receivables
        overall_coverage = (
            (total_hedged / total_exposure * 100) if total_exposure > 0 else Decimal("0")
        )

        # Por moneda (para futura expansion)
        by_currency = {
            currency: {
                "total_payables": total_payables,
                "total_receivables": total_receivables,
                "hedged_payables": hedged_payables,
                "hedged_receivables": hedged_receivables,
            }
        }

        # Por contraparte
        by_counterparty = self._get_coverage_by_counterparty(
            company_id, as_of_date, currency
        )

        # Por vencimiento
        by_maturity = self._get_coverage_by_maturity(exposures, as_of_date)

        return CoverageReport(
            as_of_date=as_of_date,
            total_payables=total_payables,
            total_receivables=total_receivables,
            total_hedged_payables=hedged_payables,
            total_hedged_receivables=hedged_receivables,
            net_exposure=net_exposure,
            payables_coverage_pct=payables_coverage.quantize(Decimal("0.01")),
            receivables_coverage_pct=receivables_coverage.quantize(Decimal("0.01")),
            overall_coverage_pct=overall_coverage.quantize(Decimal("0.01")),
            by_currency=by_currency,
            by_counterparty=by_counterparty,
            by_maturity=by_maturity,
        )

    def _get_coverage_by_counterparty(
        self,
        company_id: UUID,
        as_of_date: date,
        currency: str
    ) -> List[Dict[str, Any]]:
        """Cobertura agrupada por contraparte"""
        results = []

        counterparties = self.db.query(Counterparty).filter(
            Counterparty.company_id == company_id,
            Counterparty.is_active == True
        ).all()

        for cp in counterparties:
            exposures = self.db.query(Exposure).filter(
                Exposure.counterparty_id == cp.id,
                Exposure.currency == currency,
                Exposure.status.in_([
                    ExposureStatus.OPEN,
                    ExposureStatus.PARTIALLY_HEDGED,
                    ExposureStatus.FULLY_HEDGED
                ]),
                Exposure.due_date >= as_of_date
            ).all()

            if not exposures:
                continue

            total = sum(e.amount for e in exposures)
            hedged = sum(e.amount_hedged or Decimal("0") for e in exposures)
            coverage = (hedged / total * 100) if total > 0 else Decimal("0")

            results.append({
                "counterparty_id": str(cp.id),
                "counterparty_name": cp.name,
                "total_exposure": float(total),
                "hedged": float(hedged),
                "coverage_pct": float(coverage.quantize(Decimal("0.01"))),
                "exposure_count": len(exposures),
            })

        return sorted(results, key=lambda x: x["total_exposure"], reverse=True)

    def _get_coverage_by_maturity(
        self,
        exposures: List[Exposure],
        as_of_date: date
    ) -> Dict[str, Dict[str, Decimal]]:
        """Cobertura agrupada por horizonte de vencimiento"""
        horizons = {
            "0-30": (0, 30),
            "31-60": (31, 60),
            "61-90": (61, 90),
            "91-180": (91, 180),
            "180+": (181, 9999),
        }

        result = {}
        for horizon, (min_days, max_days) in horizons.items():
            min_date = as_of_date + timedelta(days=min_days)
            max_date = as_of_date + timedelta(days=max_days)

            bucket_exposures = [
                e for e in exposures
                if min_date <= e.due_date <= max_date
            ]

            total = sum(e.amount for e in bucket_exposures)
            hedged = sum(e.amount_hedged or Decimal("0") for e in bucket_exposures)
            coverage = (hedged / total * 100) if total > 0 else Decimal("0")

            result[horizon] = {
                "total": total,
                "hedged": hedged,
                "open": total - hedged,
                "coverage_pct": coverage.quantize(Decimal("0.01")),
            }

        return result

    # =========================================================================
    # Maturity Ladder
    # =========================================================================

    def get_maturity_ladder(
        self,
        company_id: UUID,
        currency: str = "USD",
        bucket_days: int = 7
    ) -> MaturityLadder:
        """
        Generar escalera de vencimientos.

        Muestra exposiciones por semana/periodo.
        """
        today = date.today()
        max_date = today + timedelta(days=365)

        exposures = self.db.query(Exposure).filter(
            Exposure.company_id == company_id,
            Exposure.currency == currency,
            Exposure.status.in_([
                ExposureStatus.OPEN,
                ExposureStatus.PARTIALLY_HEDGED
            ]),
            Exposure.due_date >= today,
            Exposure.due_date <= max_date
        ).order_by(Exposure.due_date).all()

        # Agrupar en buckets
        buckets = []
        current_bucket_start = today
        total_exposure = Decimal("0")
        total_hedged = Decimal("0")
        coverage_by_bucket = {}

        while current_bucket_start < max_date:
            bucket_end = current_bucket_start + timedelta(days=bucket_days - 1)

            bucket_exposures = [
                e for e in exposures
                if current_bucket_start <= e.due_date <= bucket_end
            ]

            bucket_total = sum(e.amount for e in bucket_exposures)
            bucket_hedged = sum(e.amount_hedged or Decimal("0") for e in bucket_exposures)
            bucket_open = bucket_total - bucket_hedged
            bucket_coverage = (
                (bucket_hedged / bucket_total * 100) if bucket_total > 0 else Decimal("0")
            )

            total_exposure += bucket_total
            total_hedged += bucket_hedged

            bucket_label = f"{current_bucket_start.strftime('%Y-%m-%d')}"
            coverage_by_bucket[bucket_label] = bucket_coverage

            buckets.append({
                "start_date": current_bucket_start.isoformat(),
                "end_date": bucket_end.isoformat(),
                "total": float(bucket_total),
                "hedged": float(bucket_hedged),
                "open": float(bucket_open),
                "coverage_pct": float(bucket_coverage.quantize(Decimal("0.01"))),
                "exposure_count": len(bucket_exposures),
                "payables": float(sum(
                    e.amount for e in bucket_exposures
                    if e.exposure_type == ExposureType.PAYABLE
                )),
                "receivables": float(sum(
                    e.amount for e in bucket_exposures
                    if e.exposure_type == ExposureType.RECEIVABLE
                )),
            })

            current_bucket_start = bucket_end + timedelta(days=1)

        return MaturityLadder(
            buckets=buckets,
            total_exposure=total_exposure,
            total_hedged=total_hedged,
            coverage_by_bucket={
                k: float(v.quantize(Decimal("0.01")))
                for k, v in coverage_by_bucket.items()
            },
        )

    # =========================================================================
    # Cost Analysis
    # =========================================================================

    def get_cost_analysis(
        self,
        company_id: UUID,
        start_date: date,
        end_date: date,
        currency: str = "USD"
    ) -> CostAnalysis:
        """
        Analisis de costos de cobertura.

        Compara tasas de ejecucion vs benchmark (TRM).
        """
        # Obtener trades del periodo
        trades = self.db.query(Trade).filter(
            Trade.company_id == company_id,
            Trade.trade_date >= start_date,
            Trade.trade_date <= end_date,
            Trade.status.in_([TradeStatus.CONFIRMED, TradeStatus.SETTLED])
        ).all()

        if not trades:
            return CostAnalysis(
                period_start=start_date,
                period_end=end_date,
                total_volume_traded=Decimal("0"),
                avg_rate=Decimal("0"),
                weighted_avg_rate=Decimal("0"),
                best_rate=Decimal("0"),
                worst_rate=Decimal("0"),
                benchmark_rate=Decimal("0"),
                performance_vs_benchmark=Decimal("0"),
                total_cost_savings=Decimal("0"),
                by_counterparty_bank=[],
            )

        # Calcular metricas
        rates = [t.executed_rate for t in trades]
        amounts = [t.amount_bought if t.side == "buy" else t.amount_sold for t in trades]

        total_volume = sum(amounts)
        avg_rate = sum(rates) / len(rates)

        # Tasa promedio ponderada
        weighted_sum = sum(r * a for r, a in zip(rates, amounts))
        weighted_avg = weighted_sum / total_volume if total_volume > 0 else Decimal("0")

        best_rate = min(rates)  # Para compras, menor es mejor
        worst_rate = max(rates)

        # Benchmark: TRM promedio del periodo (simplificado)
        # TODO: Obtener TRM real del periodo
        benchmark_rate = weighted_avg  # Placeholder

        performance = (
            (benchmark_rate - weighted_avg) / benchmark_rate * 100
            if benchmark_rate > 0 else Decimal("0")
        )

        # Ahorro estimado
        cost_savings = (benchmark_rate - weighted_avg) * total_volume

        # Por banco contraparte
        by_bank = self._get_cost_by_bank(trades)

        return CostAnalysis(
            period_start=start_date,
            period_end=end_date,
            total_volume_traded=total_volume,
            avg_rate=avg_rate.quantize(Decimal("0.0001")),
            weighted_avg_rate=weighted_avg.quantize(Decimal("0.0001")),
            best_rate=best_rate,
            worst_rate=worst_rate,
            benchmark_rate=benchmark_rate.quantize(Decimal("0.0001")),
            performance_vs_benchmark=performance.quantize(Decimal("0.01")),
            total_cost_savings=cost_savings.quantize(Decimal("0.01")),
            by_counterparty_bank=by_bank,
        )

    def _get_cost_by_bank(self, trades: List[Trade]) -> List[Dict[str, Any]]:
        """Analisis de costos por banco contraparte"""
        by_bank: Dict[str, Dict[str, Any]] = {}

        for trade in trades:
            bank = trade.counterparty_bank or "Unknown"
            if bank not in by_bank:
                by_bank[bank] = {
                    "bank": bank,
                    "trade_count": 0,
                    "total_volume": Decimal("0"),
                    "rates": [],
                }

            by_bank[bank]["trade_count"] += 1
            amount = trade.amount_bought if trade.side == "buy" else trade.amount_sold
            by_bank[bank]["total_volume"] += amount
            by_bank[bank]["rates"].append(trade.executed_rate)

        results = []
        for bank, data in by_bank.items():
            avg_rate = sum(data["rates"]) / len(data["rates"])
            results.append({
                "bank": bank,
                "trade_count": data["trade_count"],
                "total_volume": float(data["total_volume"]),
                "avg_rate": float(avg_rate.quantize(Decimal("0.0001"))),
                "best_rate": float(min(data["rates"])),
                "worst_rate": float(max(data["rates"])),
            })

        return sorted(results, key=lambda x: x["total_volume"], reverse=True)

    # =========================================================================
    # Export
    # =========================================================================

    def export_report(
        self,
        company_id: UUID,
        report_type: str,
        format: str = "xlsx",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> bytes:
        """
        Exportar reporte a archivo.

        Args:
            report_type: coverage, maturity, cost
            format: xlsx, csv, pdf
        """
        if report_type == "coverage":
            data = self.get_coverage_report(company_id)
        elif report_type == "maturity":
            data = self.get_maturity_ladder(company_id)
        elif report_type == "cost":
            if not start_date or not end_date:
                end_date = date.today()
                start_date = end_date - timedelta(days=30)
            data = self.get_cost_analysis(company_id, start_date, end_date)
        else:
            raise ValueError(f"Unknown report type: {report_type}")

        if format == "csv":
            return self._export_csv(data, report_type)
        elif format == "xlsx":
            return self._export_xlsx(data, report_type)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_csv(self, data: Any, report_type: str) -> bytes:
        """Exportar a CSV"""
        import csv

        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == "coverage":
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Total Payables", data.total_payables])
            writer.writerow(["Total Receivables", data.total_receivables])
            writer.writerow(["Hedged Payables", data.total_hedged_payables])
            writer.writerow(["Hedged Receivables", data.total_hedged_receivables])
            writer.writerow(["Overall Coverage %", data.overall_coverage_pct])

        elif report_type == "maturity":
            writer.writerow([
                "Period", "Total", "Hedged", "Open", "Coverage %", "Exposures"
            ])
            for bucket in data.buckets:
                writer.writerow([
                    bucket["start_date"],
                    bucket["total"],
                    bucket["hedged"],
                    bucket["open"],
                    bucket["coverage_pct"],
                    bucket["exposure_count"],
                ])

        elif report_type == "cost":
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Period", f"{data.period_start} - {data.period_end}"])
            writer.writerow(["Total Volume", data.total_volume_traded])
            writer.writerow(["Weighted Avg Rate", data.weighted_avg_rate])
            writer.writerow(["Performance vs Benchmark %", data.performance_vs_benchmark])

        return output.getvalue().encode('utf-8')

    def _export_xlsx(self, data: Any, report_type: str) -> bytes:
        """Exportar a Excel"""
        try:
            import openpyxl
            from openpyxl import Workbook
        except ImportError:
            logger.warning("openpyxl not installed, falling back to CSV")
            return self._export_csv(data, report_type)

        wb = Workbook()
        ws = wb.active
        ws.title = report_type.capitalize()

        if report_type == "coverage":
            ws.append(["Coverage Report"])
            ws.append(["As of Date", str(data.as_of_date)])
            ws.append([])
            ws.append(["Metric", "Value"])
            ws.append(["Total Payables", float(data.total_payables)])
            ws.append(["Total Receivables", float(data.total_receivables)])
            ws.append(["Hedged Payables", float(data.total_hedged_payables)])
            ws.append(["Hedged Receivables", float(data.total_hedged_receivables)])
            ws.append(["Net Exposure", float(data.net_exposure)])
            ws.append(["Payables Coverage %", float(data.payables_coverage_pct)])
            ws.append(["Receivables Coverage %", float(data.receivables_coverage_pct)])
            ws.append(["Overall Coverage %", float(data.overall_coverage_pct)])

        elif report_type == "maturity":
            ws.append(["Maturity Ladder"])
            ws.append([])
            headers = ["Period Start", "Period End", "Total", "Hedged", "Open", "Coverage %", "Exposures"]
            ws.append(headers)
            for bucket in data.buckets:
                ws.append([
                    bucket["start_date"],
                    bucket["end_date"],
                    bucket["total"],
                    bucket["hedged"],
                    bucket["open"],
                    bucket["coverage_pct"],
                    bucket["exposure_count"],
                ])

        elif report_type == "cost":
            ws.append(["Cost Analysis"])
            ws.append(["Period", f"{data.period_start} - {data.period_end}"])
            ws.append([])
            ws.append(["Metric", "Value"])
            ws.append(["Total Volume Traded", float(data.total_volume_traded)])
            ws.append(["Average Rate", float(data.avg_rate)])
            ws.append(["Weighted Average Rate", float(data.weighted_avg_rate)])
            ws.append(["Best Rate", float(data.best_rate)])
            ws.append(["Worst Rate", float(data.worst_rate)])
            ws.append(["Benchmark Rate", float(data.benchmark_rate)])
            ws.append(["Performance vs Benchmark %", float(data.performance_vs_benchmark)])
            ws.append(["Total Cost Savings", float(data.total_cost_savings)])

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

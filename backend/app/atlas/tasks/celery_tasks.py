"""
ATLAS - Celery Tasks
Tareas asincronas para generacion periodica de recomendaciones y reportes.
"""
import logging
from datetime import date
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.database_models import Company
from app.atlas.services.policy_engine import PolicyEngine
from app.atlas.services.recommendation_service import RecommendationService
from app.atlas.services.reporting_service import ReportingService

logger = logging.getLogger(__name__)


def get_db_session() -> Session:
    """Create a new database session for tasks"""
    return SessionLocal()


@shared_task(name="atlas.generate_recommendations")
def generate_recommendations_task(company_id: Optional[str] = None):
    """
    Generate hedge recommendations for companies.

    If company_id is provided, only generate for that company.
    Otherwise, generate for all active companies.

    This task is typically scheduled to run daily at market open.
    """
    db = get_db_session()
    try:
        if company_id:
            companies = [db.query(Company).filter(
                Company.id == UUID(company_id),
                Company.is_active == True
            ).first()]
            companies = [c for c in companies if c]
        else:
            companies = db.query(Company).filter(
                Company.is_active == True
            ).all()

        total_recommendations = 0

        for company in companies:
            try:
                engine = PolicyEngine(db)

                # Get default policy
                policy = engine.get_default_policy(company.id)
                if not policy:
                    logger.info(f"No default policy for company {company.id}, skipping")
                    continue

                # Check if auto-generate is enabled
                if not policy.auto_generate_recommendations:
                    logger.info(f"Auto-generate disabled for company {company.id}")
                    continue

                # Generate recommendations
                recommendations = engine.evaluate(
                    company_id=company.id,
                    policy_id=policy.id,
                )

                total_recommendations += len(recommendations)
                logger.info(
                    f"Generated {len(recommendations)} recommendations "
                    f"for company {company.id}"
                )

            except Exception as e:
                logger.error(
                    f"Error generating recommendations for company {company.id}: {e}"
                )
                continue

        return {
            "status": "success",
            "companies_processed": len(companies),
            "total_recommendations": total_recommendations,
        }

    except Exception as e:
        logger.error(f"Error in generate_recommendations_task: {e}")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


@shared_task(name="atlas.expire_recommendations")
def expire_recommendations_task():
    """
    Expire old recommendations that have passed their valid_until date.

    This task should run frequently (e.g., every hour) to keep
    the recommendations list clean.
    """
    db = get_db_session()
    try:
        companies = db.query(Company).filter(
            Company.is_active == True
        ).all()

        total_expired = 0

        for company in companies:
            try:
                service = RecommendationService(db)
                expired = service.expire_old(company.id)
                total_expired += expired

                if expired > 0:
                    logger.info(f"Expired {expired} recommendations for company {company.id}")

            except Exception as e:
                logger.error(f"Error expiring recommendations for company {company.id}: {e}")
                continue

        return {
            "status": "success",
            "total_expired": total_expired,
        }

    except Exception as e:
        logger.error(f"Error in expire_recommendations_task: {e}")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


@shared_task(name="atlas.daily_coverage_report")
def daily_coverage_report_task(company_id: Optional[str] = None):
    """
    Generate and optionally send daily coverage reports.

    This task is typically scheduled to run at end of business day.
    """
    db = get_db_session()
    try:
        if company_id:
            companies = [db.query(Company).filter(
                Company.id == UUID(company_id),
                Company.is_active == True
            ).first()]
            companies = [c for c in companies if c]
        else:
            companies = db.query(Company).filter(
                Company.is_active == True
            ).all()

        reports_generated = 0

        for company in companies:
            try:
                service = ReportingService(db)
                report = service.get_coverage_report(
                    company_id=company.id,
                    as_of_date=date.today()
                )

                # Log key metrics
                logger.info(
                    f"Company {company.id} coverage report: "
                    f"Net Exposure: {report.net_exposure}, "
                    f"Coverage: {report.overall_coverage_pct}%"
                )

                # TODO: Send report via email/notification if configured
                # This would integrate with the existing notification_service

                reports_generated += 1

            except Exception as e:
                logger.error(f"Error generating report for company {company.id}: {e}")
                continue

        return {
            "status": "success",
            "reports_generated": reports_generated,
        }

    except Exception as e:
        logger.error(f"Error in daily_coverage_report_task: {e}")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


@shared_task(name="atlas.check_pending_settlements")
def check_pending_settlements_task():
    """
    Check for pending settlements due today or overdue.

    This task should run daily in the morning to alert treasury
    about settlements that need attention.
    """
    db = get_db_session()
    try:
        from app.atlas.services.settlement_service import SettlementService

        companies = db.query(Company).filter(
            Company.is_active == True
        ).all()

        alerts = []

        for company in companies:
            try:
                service = SettlementService(db)
                summary = service.get_summary(company.id)

                if summary["pending_today_count"] > 0:
                    alerts.append({
                        "company_id": str(company.id),
                        "company_name": company.name,
                        "pending_today": summary["pending_today_count"],
                        "pending_amount": summary["pending_today_amount"],
                    })

                    logger.info(
                        f"Company {company.name}: {summary['pending_today_count']} "
                        f"settlements due today (${summary['pending_today_amount']:,.2f})"
                    )

            except Exception as e:
                logger.error(f"Error checking settlements for company {company.id}: {e}")
                continue

        return {
            "status": "success",
            "companies_with_pending": len(alerts),
            "alerts": alerts,
        }

    except Exception as e:
        logger.error(f"Error in check_pending_settlements_task: {e}")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()

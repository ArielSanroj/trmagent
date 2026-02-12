"""Add ATLAS tables for Treasury Copilot

Revision ID: 001_atlas
Revises:
Create Date: 2026-01-21

Tables:
- atlas_counterparties: Suppliers and customers
- atlas_exposures: FX exposures (payables/receivables)
- atlas_hedge_policies: Coverage policies
- atlas_hedge_recommendations: Generated recommendations
- atlas_hedge_orders: Hedge orders
- atlas_quotes: Bank quotes
- atlas_trades: Executed trades
- atlas_settlements: Trade settlements
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_atlas'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    exposure_type = postgresql.ENUM('payable', 'receivable', name='exposuretype', create_type=False)
    exposure_type.create(op.get_bind(), checkfirst=True)

    exposure_status = postgresql.ENUM('open', 'partially_hedged', 'fully_hedged', 'settled', 'cancelled', name='exposurestatus', create_type=False)
    exposure_status.create(op.get_bind(), checkfirst=True)

    hedge_action = postgresql.ENUM('hedge_now', 'hedge_partial', 'wait', 'review', name='hedgeaction', create_type=False)
    hedge_action.create(op.get_bind(), checkfirst=True)

    recommendation_status = postgresql.ENUM('pending', 'accepted', 'rejected', 'expired', name='recommendationstatus', create_type=False)
    recommendation_status.create(op.get_bind(), checkfirst=True)

    order_status = postgresql.ENUM('draft', 'pending_approval', 'approved', 'sent_to_bank', 'quoted', 'executed', 'cancelled', 'rejected', name='atlas_orderstatus', create_type=False)
    order_status.create(op.get_bind(), checkfirst=True)

    trade_status = postgresql.ENUM('confirmed', 'pending_settlement', 'settled', 'failed', name='tradestatus', create_type=False)
    trade_status.create(op.get_bind(), checkfirst=True)

    settlement_status = postgresql.ENUM('pending', 'processing', 'completed', 'failed', name='settlementstatus', create_type=False)
    settlement_status.create(op.get_bind(), checkfirst=True)

    # Create atlas_counterparties table
    op.create_table(
        'atlas_counterparties',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('tax_id', sa.String(50), nullable=True),
        sa.Column('country', sa.String(3), nullable=True, default='USA'),
        sa.Column('counterparty_type', sa.String(50), nullable=True, default='supplier'),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(50), nullable=True),
        sa.Column('default_payment_terms', sa.Integer, nullable=True, default=30),
        sa.Column('default_currency', sa.String(3), nullable=True, default='USD'),
        sa.Column('credit_limit', sa.Numeric(15, 2), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=True, default=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
    )
    op.create_index('ix_atlas_counterparties_company_id', 'atlas_counterparties', ['company_id'])
    op.create_index('ix_atlas_counterparties_company_name', 'atlas_counterparties', ['company_id', 'name'])

    # Create atlas_exposures table
    op.create_table(
        'atlas_exposures',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('counterparty_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('exposure_type', sa.Enum('payable', 'receivable', name='exposuretype'), nullable=False),
        sa.Column('reference', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('amount_hedged', sa.Numeric(15, 2), nullable=True, default=0),
        sa.Column('original_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('target_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('budget_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('invoice_date', sa.Date, nullable=True),
        sa.Column('due_date', sa.Date, nullable=False),
        sa.Column('status', sa.Enum('open', 'partially_hedged', 'fully_hedged', 'settled', 'cancelled', name='exposurestatus'), nullable=True, default='open'),
        sa.Column('hedge_percentage', sa.Numeric(5, 2), nullable=True, default=0),
        sa.Column('tags', postgresql.JSON, nullable=True),
        sa.Column('source', sa.String(50), nullable=True, default='manual'),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['counterparty_id'], ['atlas_counterparties.id']),
    )
    op.create_index('ix_atlas_exposures_company_id', 'atlas_exposures', ['company_id'])
    op.create_index('ix_atlas_exposures_counterparty_id', 'atlas_exposures', ['counterparty_id'])
    op.create_index('ix_atlas_exposures_due_date', 'atlas_exposures', ['due_date'])
    op.create_index('ix_atlas_exposures_company_due_date', 'atlas_exposures', ['company_id', 'due_date'])
    op.create_index('ix_atlas_exposures_company_status', 'atlas_exposures', ['company_id', 'status'])

    # Create atlas_hedge_policies table
    op.create_table(
        'atlas_hedge_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('exposure_type', sa.Enum('payable', 'receivable', name='exposuretype'), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, default='USD'),
        sa.Column('counterparty_category', sa.String(100), nullable=True),
        sa.Column('coverage_rules', postgresql.JSON, nullable=False),
        sa.Column('min_amount', sa.Numeric(15, 2), nullable=True, default=0),
        sa.Column('max_single_exposure', sa.Numeric(15, 2), nullable=True),
        sa.Column('rate_tolerance_up', sa.Numeric(5, 2), nullable=True, default=2.0),
        sa.Column('rate_tolerance_down', sa.Numeric(5, 2), nullable=True, default=2.0),
        sa.Column('auto_generate_recommendations', sa.Boolean, nullable=True, default=True),
        sa.Column('require_approval_above', sa.Numeric(15, 2), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=True, default=True),
        sa.Column('is_default', sa.Boolean, nullable=True, default=False),
        sa.Column('priority', sa.Integer, nullable=True, default=100),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
    )
    op.create_index('ix_atlas_hedge_policies_company_id', 'atlas_hedge_policies', ['company_id'])
    op.create_index('ix_atlas_hedge_policies_company_active', 'atlas_hedge_policies', ['company_id', 'is_active'])

    # Create atlas_hedge_recommendations table
    op.create_table(
        'atlas_hedge_recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exposure_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('policy_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.Enum('hedge_now', 'hedge_partial', 'wait', 'review', name='hedgeaction'), nullable=False),
        sa.Column('currency', sa.String(3), nullable=True, default='USD'),
        sa.Column('amount_to_hedge', sa.Numeric(15, 2), nullable=False),
        sa.Column('current_coverage', sa.Numeric(5, 2), nullable=True),
        sa.Column('target_coverage', sa.Numeric(5, 2), nullable=True),
        sa.Column('current_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('suggested_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('priority', sa.Integer, nullable=True, default=50),
        sa.Column('urgency', sa.String(20), nullable=True, default='normal'),
        sa.Column('days_to_maturity', sa.Integer, nullable=True),
        sa.Column('reasoning', sa.Text, nullable=True),
        sa.Column('factors', postgresql.JSON, nullable=True),
        sa.Column('confidence', sa.Numeric(5, 2), nullable=True),
        sa.Column('status', sa.Enum('pending', 'accepted', 'rejected', 'expired', name='recommendationstatus'), nullable=True, default='pending'),
        sa.Column('valid_until', sa.DateTime, nullable=True),
        sa.Column('decided_at', sa.DateTime, nullable=True),
        sa.Column('decided_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rejection_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['exposure_id'], ['atlas_exposures.id']),
        sa.ForeignKeyConstraint(['policy_id'], ['atlas_hedge_policies.id']),
    )
    op.create_index('ix_atlas_recommendations_company_id', 'atlas_hedge_recommendations', ['company_id'])
    op.create_index('ix_atlas_recommendations_exposure_id', 'atlas_hedge_recommendations', ['exposure_id'])
    op.create_index('ix_atlas_recommendations_company_status', 'atlas_hedge_recommendations', ['company_id', 'status'])
    op.create_index('ix_atlas_recommendations_company_created', 'atlas_hedge_recommendations', ['company_id', 'created_at'])

    # Create atlas_hedge_orders table
    op.create_table(
        'atlas_hedge_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exposure_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recommendation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('order_type', sa.String(20), nullable=True, default='spot'),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('currency', sa.String(3), nullable=True, default='USD'),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('target_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('limit_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('market_rate_at_creation', sa.Numeric(10, 4), nullable=True),
        sa.Column('settlement_date', sa.Date, nullable=True),
        sa.Column('status', sa.Enum('draft', 'pending_approval', 'approved', 'sent_to_bank', 'quoted', 'executed', 'cancelled', 'rejected', name='atlas_orderstatus'), nullable=True, default='draft'),
        sa.Column('requires_approval', sa.Boolean, nullable=True, default=False),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('bank_reference', sa.String(100), nullable=True),
        sa.Column('executed_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('internal_reference', sa.String(100), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['exposure_id'], ['atlas_exposures.id']),
        sa.ForeignKeyConstraint(['recommendation_id'], ['atlas_hedge_recommendations.id']),
    )
    op.create_index('ix_atlas_orders_company_id', 'atlas_hedge_orders', ['company_id'])
    op.create_index('ix_atlas_orders_exposure_id', 'atlas_hedge_orders', ['exposure_id'])
    op.create_index('ix_atlas_orders_company_status', 'atlas_hedge_orders', ['company_id', 'status'])

    # Create atlas_quotes table
    op.create_table(
        'atlas_quotes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(100), nullable=False),
        sa.Column('provider_reference', sa.String(100), nullable=True),
        sa.Column('bid_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('ask_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('mid_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('spread', sa.Numeric(6, 4), nullable=True),
        sa.Column('amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, default='USD'),
        sa.Column('valid_from', sa.DateTime, nullable=True),
        sa.Column('valid_until', sa.DateTime, nullable=True),
        sa.Column('is_accepted', sa.Boolean, nullable=True, default=False),
        sa.Column('is_expired', sa.Boolean, nullable=True, default=False),
        sa.Column('raw_response', postgresql.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['atlas_hedge_orders.id']),
    )
    op.create_index('ix_atlas_quotes_order_id', 'atlas_quotes', ['order_id'])

    # Create atlas_trades table
    op.create_table(
        'atlas_trades',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quote_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('trade_type', sa.String(20), nullable=True, default='spot'),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('currency_sold', sa.String(3), nullable=False),
        sa.Column('amount_sold', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency_bought', sa.String(3), nullable=False),
        sa.Column('amount_bought', sa.Numeric(15, 2), nullable=False),
        sa.Column('executed_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('counterparty_bank', sa.String(100), nullable=True),
        sa.Column('bank_reference', sa.String(100), nullable=True),
        sa.Column('trade_date', sa.Date, nullable=False),
        sa.Column('value_date', sa.Date, nullable=False),
        sa.Column('status', sa.Enum('confirmed', 'pending_settlement', 'settled', 'failed', name='tradestatus'), nullable=True, default='confirmed'),
        sa.Column('confirmation_number', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['order_id'], ['atlas_hedge_orders.id']),
        sa.ForeignKeyConstraint(['quote_id'], ['atlas_quotes.id']),
    )
    op.create_index('ix_atlas_trades_company_id', 'atlas_trades', ['company_id'])
    op.create_index('ix_atlas_trades_order_id', 'atlas_trades', ['order_id'])
    op.create_index('ix_atlas_trades_company_trade_date', 'atlas_trades', ['company_id', 'trade_date'])

    # Create atlas_settlements table
    op.create_table(
        'atlas_settlements',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trade_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('settlement_date', sa.Date, nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('from_account', sa.String(100), nullable=True),
        sa.Column('to_account', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='settlementstatus'), nullable=True, default='pending'),
        sa.Column('payment_reference', sa.String(100), nullable=True),
        sa.Column('bank_confirmation', sa.String(100), nullable=True),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('confirmed_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['trade_id'], ['atlas_trades.id']),
    )
    op.create_index('ix_atlas_settlements_trade_id', 'atlas_settlements', ['trade_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('atlas_settlements')
    op.drop_table('atlas_trades')
    op.drop_table('atlas_quotes')
    op.drop_table('atlas_hedge_orders')
    op.drop_table('atlas_hedge_recommendations')
    op.drop_table('atlas_hedge_policies')
    op.drop_table('atlas_exposures')
    op.drop_table('atlas_counterparties')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS settlementstatus')
    op.execute('DROP TYPE IF EXISTS tradestatus')
    op.execute('DROP TYPE IF EXISTS atlas_orderstatus')
    op.execute('DROP TYPE IF EXISTS recommendationstatus')
    op.execute('DROP TYPE IF EXISTS hedgeaction')
    op.execute('DROP TYPE IF EXISTS exposurestatus')
    op.execute('DROP TYPE IF EXISTS exposuretype')

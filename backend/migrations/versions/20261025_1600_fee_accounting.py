"""Complete fee accounting, idempotency, refund and concession audit records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "fee_accounting"
down_revision = "class_query_indexes"
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade():
    # Constraint creation intentionally fails on inconsistent legacy accounts;
    # never merge charges or alter paid balances to make a migration succeed.
    op.add_column("fee_ledger", sa.Column("fee_head_name", sa.String(100)))
    op.add_column("fee_ledger", sa.Column("original_amount", sa.Numeric(12, 2)))
    op.add_column("fee_ledger", sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.execute("UPDATE fee_ledger SET original_amount = amount_due")
    op.execute("UPDATE fee_ledger SET fee_head_name = fee_heads.name FROM fee_heads WHERE fee_heads.id = fee_ledger.fee_head_id")
    op.alter_column("fee_ledger", "fee_head_name", nullable=False)
    op.alter_column("fee_ledger", "original_amount", nullable=False)
    op.add_column("fee_payments", sa.Column("request_id", sa.UUID()))
    op.add_column("fee_payments", sa.Column("reference", sa.String(100)))
    op.add_column("fee_payments", sa.Column("balance_after", sa.Numeric(12, 2)))
    op.add_column("fee_payments", sa.Column("refunded_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    for column in (
        sa.Column("request_id", sa.UUID()),
        sa.Column("applied_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("applied_by", sa.UUID()), sa.Column("reversed_by", sa.UUID()),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reversal_reason", sa.String(500)),
        sa.Column("requested_ledger_ids", postgresql.JSONB()),
    ):
        op.add_column("scholarships", column)
    op.create_index("uq_fee_structure_active", "fee_structures", ["school_id", "academic_year_bs", "grade"], unique=True, postgresql_where=sa.text("is_active"))
    op.create_index("uq_fee_head_name", "fee_heads", ["fee_structure_id", sa.text("lower(name)")], unique=True)
    op.create_index("uq_fee_ledger_period", "fee_ledger", ["school_id", "student_id", "fee_head_id", "academic_year_bs", sa.text("coalesce(month_bs, '')")], unique=True)
    op.create_index("ix_fee_ledger_school_year_due", "fee_ledger", ["school_id", "academic_year_bs", "due_date_ad"])
    op.create_index("uq_fee_payment_request", "fee_payments", ["school_id", "request_id"], unique=True)
    op.create_index("uq_fee_scholarship_request", "scholarships", ["school_id", "request_id"], unique=True)
    op.create_check_constraint("ck_fee_head_amount", "fee_heads", "amount > 0")
    op.create_check_constraint("ck_fee_ledger_nonnegative", "fee_ledger", "amount_due >= 0 AND amount_paid >= 0 AND balance >= 0")
    op.create_check_constraint("ck_fee_ledger_balance", "fee_ledger", "balance = amount_due - amount_paid")
    op.create_check_constraint("ck_fee_ledger_discount", "fee_ledger", "original_amount >= amount_due AND discount_amount = original_amount - amount_due")
    op.create_check_constraint("ck_fee_payment_amount", "fee_payments", "amount > 0 AND refunded_amount >= 0 AND refunded_amount <= amount")
    op.create_table("fee_refunds", *audit_columns(),
        sa.Column("payment_id", sa.UUID(), sa.ForeignKey("fee_payments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False), sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", postgresql.ENUM("cash", "bank_transfer", "cheque", name="payment_method_enum", create_type=False), nullable=False),
        sa.Column("reference", sa.String(100)), sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("refund_number", sa.String(30), unique=True, nullable=False),
        sa.Column("refunded_date_ad", sa.Date(), nullable=False), sa.Column("refunded_date_bs", sa.String(10), nullable=False),
        sa.Column("refunded_by", sa.UUID(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_fee_refund_amount"),
    )
    op.create_index("uq_fee_refund_request", "fee_refunds", ["school_id", "request_id"], unique=True)
    op.create_index("ix_fee_refund_payment", "fee_refunds", ["school_id", "payment_id"])
    op.create_table("fee_discount_allocations", *audit_columns(),
        sa.Column("scholarship_id", sa.UUID(), sa.ForeignKey("scholarships.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ledger_id", sa.UUID(), sa.ForeignKey("fee_ledger.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_fee_discount_amount"),
    )
    op.create_index("ix_fee_discount_scholarship", "fee_discount_allocations", ["school_id", "scholarship_id"])
    for table in ("fee_refunds", "fee_discount_allocations"):
        op.create_index(f"ix_{table}_id", table, ["id"], unique=True)
        op.create_index(f"ix_{table}_school_id", table, ["school_id"])


def downgrade():
    # Financial audit records must not be silently discarded by a rollback.
    if not op.get_context().as_sql:
        records = op.get_bind().scalar(sa.text("SELECT (SELECT count(*) FROM fee_refunds) + (SELECT count(*) FROM fee_discount_allocations) + (SELECT count(*) FROM fee_payments WHERE request_id IS NOT NULL) + (SELECT count(*) FROM scholarships WHERE request_id IS NOT NULL)"))
        if records:
            raise RuntimeError("Cannot downgrade fee accounting while payment, refund or concession audit records exist")
    op.drop_table("fee_discount_allocations")
    op.drop_table("fee_refunds")
    for name, table in (
        ("uq_fee_structure_active", "fee_structures"), ("uq_fee_head_name", "fee_heads"),
        ("uq_fee_ledger_period", "fee_ledger"), ("ix_fee_ledger_school_year_due", "fee_ledger"),
        ("uq_fee_payment_request", "fee_payments"), ("uq_fee_scholarship_request", "scholarships"),
    ):
        op.drop_index(name, table_name=table)
    for name, table in (
        ("ck_fee_head_amount", "fee_heads"), ("ck_fee_ledger_nonnegative", "fee_ledger"),
        ("ck_fee_ledger_balance", "fee_ledger"), ("ck_fee_ledger_discount", "fee_ledger"),
        ("ck_fee_payment_amount", "fee_payments"),
    ):
        op.drop_constraint(name, table, type_="check")
    for table, columns in {
        "fee_ledger": ["fee_head_name", "original_amount", "discount_amount"],
        "fee_payments": ["request_id", "reference", "balance_after", "refunded_amount"],
        "scholarships": ["request_id", "applied_amount", "applied_by", "reversed_by", "reversed_at", "reversal_reason", "requested_ledger_ids"],
    }.items():
        for column in columns:
            op.drop_column(table, column)

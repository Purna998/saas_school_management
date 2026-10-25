"""Accession-level inventory, reliable circulation, school policies and audit."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "library_circulation"
down_revision = "fee_accounting"
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("school_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM books b WHERE b.total_copies < 0 OR b.available_copies < 0
            OR b.available_copies > b.total_copies OR b.total_copies - b.available_copies <>
            (SELECT count(*) FROM book_issues i WHERE i.book_id=b.id AND i.status IN ('ISSUED','OVERDUE','LOST')))
            OR EXISTS (SELECT 1 FROM book_issues i JOIN books b ON b.id=i.book_id WHERE i.school_id<>b.school_id)
        THEN RAISE EXCEPTION 'Reconcile legacy library stock/tenant inconsistencies before migration; no circulation history was changed';
        END IF;
    END $$""")
    op.add_column("books", sa.Column("is_lendable", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("books", sa.Column("language", sa.String(50)))
    op.add_column("books", sa.Column("reading_level", sa.String(50)))
    op.execute("UPDATE books SET isbn = nullif(regexp_replace(upper(isbn), '[-[:space:]]', '', 'g'), '') WHERE isbn IS NOT NULL")
    op.create_index("uq_books_school_isbn", "books", ["school_id", "isbn"], unique=True, postgresql_where=sa.text("isbn IS NOT NULL"))
    op.create_index("ix_books_school_catalog", "books", ["school_id", "is_active", "title", "id"])
    op.create_check_constraint("ck_book_stock", "books", "total_copies >= 0 AND available_copies >= 0 AND available_copies <= total_copies")
    op.create_table("book_copies", *common(),
        sa.Column("book_id", sa.UUID(), sa.ForeignKey("books.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("accession_number", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("acquired_date_ad", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.CheckConstraint("status IN ('available','issued','damaged','lost','withdrawn')", name="ck_library_copy_status"),
    )
    op.create_index("uq_library_accession", "book_copies", ["school_id", "accession_number"], unique=True)
    op.create_index("ix_library_copy_inventory", "book_copies", ["school_id", "book_id", "status"])
    op.create_table("library_policies", *common(),
        sa.Column("loan_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("student_limit", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("staff_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("renewal_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("max_renewals", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("allow_overdue_renewal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("daily_fine", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("fine_cap", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("next_accession_number", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("loan_days BETWEEN 1 AND 90 AND renewal_days BETWEEN 1 AND 90 AND max_renewals BETWEEN 0 AND 10", name="ck_library_policy_periods"),
        sa.CheckConstraint("student_limit BETWEEN 1 AND 100 AND staff_limit BETWEEN 1 AND 100 AND next_accession_number >= 1", name="ck_library_policy_limits"),
        sa.CheckConstraint("daily_fine >= 0 AND fine_cap >= 0 AND (daily_fine = 0 OR fine_cap > 0)", name="ck_library_policy_fines"),
    )
    op.create_index("uq_library_policy_school", "library_policies", ["school_id"], unique=True)
    for column in (
        sa.Column("copy_id", sa.UUID()), sa.Column("book_title", sa.String(300)),
        sa.Column("accession_number", sa.String(50)), sa.Column("borrower_name", sa.String(200)),
        sa.Column("borrower_reference", sa.String(50)), sa.Column("return_condition", sa.String(20)),
        sa.Column("notes", sa.String(1000)), sa.Column("renewal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    ):
        op.add_column("book_issues", column)
    # Legacy aggregates do not identify physical copies. Assign new accession
    # identities to unresolved loans and retain unknown copies on old returns.
    op.execute("""INSERT INTO book_copies (id, school_id, book_id, accession_number, status, acquired_date_ad)
        SELECT gen_random_uuid(), b.school_id, b.id,
            'MIG-' || replace(b.id::text,'-','') || '-' || lpad(n::text,6,'0'),
            CASE WHEN n <= (SELECT count(*) FROM book_issues i WHERE i.book_id=b.id AND i.status IN ('ISSUED','OVERDUE')) THEN 'issued'
                 WHEN n <= b.total_copies-b.available_copies THEN 'lost' ELSE 'available' END,
            b.added_date_ad FROM books b CROSS JOIN LATERAL generate_series(1,b.total_copies) n""")
    op.execute("""WITH ranked_loans AS (
            SELECT id, book_id, row_number() OVER (PARTITION BY book_id ORDER BY CASE WHEN status='LOST' THEN 1 ELSE 0 END,created_at,id) n
            FROM book_issues WHERE status IN ('ISSUED','OVERDUE','LOST')
        ), ranked_copies AS (
            SELECT id,book_id,accession_number,row_number() OVER (PARTITION BY book_id ORDER BY accession_number) n FROM book_copies
        ) UPDATE book_issues i SET copy_id=c.id, accession_number=c.accession_number
        FROM ranked_loans l JOIN ranked_copies c ON c.book_id=l.book_id AND c.n=l.n WHERE i.id=l.id""")
    op.execute("""UPDATE book_issues i SET book_title=b.title,
        borrower_name=coalesce(
            CASE WHEN i.issued_to_type='STUDENT' THEN (SELECT s.full_name_en FROM students s WHERE s.id=i.issued_to_id AND s.school_id=i.school_id) END,
            CASE WHEN i.issued_to_type='STAFF' THEN (SELECT s.full_name_en FROM staff s WHERE s.id=i.issued_to_id AND s.school_id=i.school_id) END,
            CASE WHEN i.issued_to_type='STAFF' THEN (SELECT u.full_name_en FROM users u WHERE u.id=i.issued_to_id AND u.school_id=i.school_id) END,
            'Legacy borrower'),
        policy_snapshot=jsonb_build_object('max_renewals',2,'renewal_days',14,'allow_overdue_renewal',false,'daily_fine','0.00','fine_cap','0.00','legacy',true)
        FROM books b WHERE b.id=i.book_id""")
    op.alter_column("book_issues", "book_title", nullable=False)
    op.alter_column("book_issues", "borrower_name", nullable=False)
    op.create_foreign_key("fk_library_loan_copy", "book_issues", "book_copies", ["copy_id"], ["id"], ondelete="RESTRICT")
    op.drop_constraint("book_issues_book_id_fkey", "book_issues", type_="foreignkey")
    op.create_foreign_key("book_issues_book_id_fkey", "book_issues", "books", ["book_id"], ["id"], ondelete="RESTRICT")
    op.create_index("uq_library_copy_open_loan", "book_issues", ["copy_id"], unique=True, postgresql_where=sa.text("status IN ('ISSUED','OVERDUE')"))
    op.create_index("ix_library_open_due", "book_issues", ["school_id", "due_date_ad"], postgresql_where=sa.text("status IN ('ISSUED','OVERDUE')"))
    op.create_index("ix_library_borrower", "book_issues", ["school_id", "issued_to_type", "issued_to_id", "status"])
    op.create_check_constraint("ck_library_loan_values", "book_issues", "fine_amount >= 0 AND renewal_count >= 0")
    op.create_check_constraint("ck_library_loan_dates", "book_issues", "due_date_ad >= issue_date_ad AND (return_date_ad IS NULL OR return_date_ad >= issue_date_ad)")
    op.create_check_constraint("ck_library_loan_copy", "book_issues", "status = 'RETURNED' OR copy_id IS NOT NULL")
    op.create_table("library_events", *common(),
        sa.Column("request_id", sa.UUID(), nullable=False), sa.Column("action", sa.String(30), nullable=False),
        sa.Column("book_id", sa.UUID(), sa.ForeignKey("books.id", ondelete="RESTRICT")),
        sa.Column("copy_id", sa.UUID(), sa.ForeignKey("book_copies.id", ondelete="RESTRICT")),
        sa.Column("issue_id", sa.UUID(), sa.ForeignKey("book_issues.id", ondelete="RESTRICT")),
        sa.Column("actor_id", sa.UUID(), nullable=False), sa.Column("actor_name", sa.String(200)),
        sa.Column("notes", sa.String(1000)), sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("before_values", postgresql.JSONB(), nullable=False), sa.Column("after_values", postgresql.JSONB(), nullable=False),
    )
    op.create_index("uq_library_request", "library_events", ["school_id", "request_id"], unique=True)
    op.create_index("ix_library_history", "library_events", ["school_id", "book_id", "created_at"])
    op.create_index("ix_library_loan_history", "library_events", ["school_id", "issue_id", "created_at"])
    for table in ("book_copies", "library_policies", "library_events"):
        op.create_index(f"ix_{table}_id", table, ["id"], unique=True)
        op.create_index(f"ix_{table}_school_id", table, ["school_id"])


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM library_events) THEN
            RAISE EXCEPTION 'Cannot discard library accession/circulation audit history during downgrade';
        END IF;
    END $$""")
    op.drop_table("library_events")
    for name in ("uq_library_copy_open_loan", "ix_library_open_due", "ix_library_borrower"):
        op.drop_index(name, table_name="book_issues")
    for name in ("ck_library_loan_values", "ck_library_loan_dates", "ck_library_loan_copy"):
        op.drop_constraint(name, "book_issues", type_="check")
    op.drop_constraint("fk_library_loan_copy", "book_issues", type_="foreignkey")
    op.drop_constraint("book_issues_book_id_fkey", "book_issues", type_="foreignkey")
    op.create_foreign_key("book_issues_book_id_fkey", "book_issues", "books", ["book_id"], ["id"], ondelete="CASCADE")
    for name in ("copy_id", "book_title", "accession_number", "borrower_name", "borrower_reference", "return_condition", "notes", "renewal_count", "policy_snapshot"):
        op.drop_column("book_issues", name)
    op.drop_table("book_copies")
    op.drop_table("library_policies")
    op.drop_index("uq_books_school_isbn", table_name="books")
    op.drop_index("ix_books_school_catalog", table_name="books")
    op.drop_constraint("ck_book_stock", "books", type_="check")
    for name in ("language", "reading_level", "is_lendable"):
        op.drop_column("books", name)

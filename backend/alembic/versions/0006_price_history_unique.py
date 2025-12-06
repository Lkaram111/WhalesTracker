"""add unique constraint on price_history asset+timestamp

Revision ID: 0006_price_history_unique
Revises: 0005_backtest_runs
Create Date: 2025-12-06 10:30:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0006_price_history_unique"
down_revision = "0005_backtest_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""

    # Remove duplicates before enforcing uniqueness
    if dialect == "sqlite":
        op.execute(
            """
            DELETE FROM price_history
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM price_history
                GROUP BY asset_symbol, timestamp
            )
            """
        )
    elif dialect in {"mysql"}:
        op.execute(
            """
            DELETE ph FROM price_history ph
            JOIN price_history ph2
              ON ph.asset_symbol = ph2.asset_symbol
             AND ph.timestamp = ph2.timestamp
             AND ph.id > ph2.id
            """
        )
    else:
        op.execute(
            """
            DELETE FROM price_history ph
            USING price_history ph2
            WHERE ph.asset_symbol = ph2.asset_symbol
              AND ph.timestamp = ph2.timestamp
              AND ph.id > ph2.id
            """
        )

    # Add uniqueness on asset_symbol + timestamp
    if dialect in {"postgresql", "postgres", "sqlite"}:
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_price_history_asset_ts ON price_history(asset_symbol, timestamp)"
        )
    else:
        op.create_unique_constraint(
            "uq_price_history_asset_ts", "price_history", ["asset_symbol", "timestamp"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""

    if dialect in {"postgresql", "postgres", "sqlite"}:
        op.execute("DROP INDEX IF EXISTS uq_price_history_asset_ts")
    else:
        op.drop_constraint("uq_price_history_asset_ts", "price_history", type_="unique")

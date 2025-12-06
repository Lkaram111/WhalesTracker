"""ensure trades unique per whale+tx

Revision ID: 0007_trades_unique_whale_tx
Revises: 0006_price_history_unique
Create Date: 2025-12-06 11:00:00.000000
"""

from alembic import op


revision = "0007_trades_unique_whale_tx"
down_revision = "0006_price_history_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""

    # Remove duplicates before adding uniqueness
    if dialect == "sqlite":
        op.execute(
            """
            DELETE FROM trades
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM trades
                WHERE tx_hash IS NOT NULL
                GROUP BY whale_id, tx_hash
            )
            AND tx_hash IS NOT NULL
            """
        )
    elif dialect in {"mysql"}:
        op.execute(
            """
            DELETE t FROM trades t
            JOIN trades t2
              ON t.tx_hash IS NOT NULL
             AND t.whale_id = t2.whale_id
             AND t.tx_hash = t2.tx_hash
             AND t.id > t2.id
            """
        )
    else:
        op.execute(
            """
            DELETE FROM trades t
            USING trades t2
            WHERE t.tx_hash IS NOT NULL
              AND t.whale_id = t2.whale_id
              AND t.tx_hash = t2.tx_hash
              AND t.id > t2.id
            """
        )

    # Add uniqueness
    if dialect in {"postgresql", "postgres", "sqlite"}:
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_trades_whale_tx_hash ON trades(whale_id, tx_hash) WHERE tx_hash IS NOT NULL"
        )
    else:
        op.create_unique_constraint(
            "uq_trades_whale_tx_hash", "trades", ["whale_id", "tx_hash"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind else ""

    if dialect in {"postgresql", "postgres", "sqlite"}:
        op.execute("DROP INDEX IF EXISTS uq_trades_whale_tx_hash")
    else:
        op.drop_constraint("uq_trades_whale_tx_hash", "trades", type_="unique")

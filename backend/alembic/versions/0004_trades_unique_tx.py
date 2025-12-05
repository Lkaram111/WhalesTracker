"""add unique constraint on trades tx per whale

Revision ID: 0004_trades_unique_tx
Revises: 0003_ingestion_checkpoints
Create Date: 2025-12-04 10:00:00.000000
"""

from alembic import op


revision = "0004_trades_unique_tx"
down_revision = "0003_ingestion_checkpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicates before adding unique index
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        op.execute(
            """
            DELETE FROM trades
            WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM trades
                WHERE tx_hash IS NOT NULL
                GROUP BY whale_id, tx_hash
            )
            AND tx_hash IS NOT NULL
            """
        )
    elif dialect in {"mysql"}:
        # MariaDB/MySQL syntax requires an explicit FROM target with JOIN
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
    if dialect == "sqlite":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_trades_whale_txhash ON trades(whale_id, tx_hash) WHERE tx_hash IS NOT NULL"
        )
    elif dialect in {"postgresql", "postgres"}:
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_trades_whale_txhash ON trades(whale_id, tx_hash) WHERE tx_hash IS NOT NULL"
        )
    else:
        # best-effort fallback: plain unique index (may allow multiple nulls depending on dialect)
        op.create_unique_constraint("uq_trades_whale_txhash", "trades", ["whale_id", "tx_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name in {"postgresql", "postgres", "sqlite"}:
        op.execute("DROP INDEX IF EXISTS uq_trades_whale_txhash")
    else:
        op.drop_constraint("uq_trades_whale_txhash", "trades", type_="unique")

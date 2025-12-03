<%text>
This file is part of the Alembic migration environment.
</%text>
<%!
import re
from alembic import util
%>
${up_revision}
${comment}
Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
${message}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}

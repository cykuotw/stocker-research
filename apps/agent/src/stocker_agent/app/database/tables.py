"""SQLAlchemy query mappings for the existing migration-owned runtime tables.

These mappings do not create or alter tables; immutable SQL migrations own DDL.
"""

from sqlalchemy import BigInteger, Column, DateTime, Integer, MetaData, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData(schema="runtime")
schema_migrations = Table(
    "schema_migrations",
    metadata,
    Column("version", Integer, primary_key=True),
    Column("checksum", Text),
    Column("applied_at", DateTime(timezone=True)),
)
assistants = Table(
    "assistants",
    metadata,
    Column("assistant_id", UUID(as_uuid=True), primary_key=True),
    Column("graph_id", Text),
    Column("name", Text),
    Column("config", JSONB),
    Column("created_at", DateTime(timezone=True)),
)
sessions = Table(
    "sessions",
    metadata,
    Column("session_id", UUID(as_uuid=True), primary_key=True),
    Column("assistant_id", UUID(as_uuid=True)),
    Column("graph_id", Text),
    Column("config", JSONB),
    Column("title", Text),
    Column("created_at", DateTime(timezone=True)),
)
runs = Table(
    "runs",
    metadata,
    Column("run_id", UUID(as_uuid=True), primary_key=True),
    Column("session_id", UUID(as_uuid=True)),
    Column("action", Text),
    Column("request", JSONB),
    Column("idempotency_key", Text),
    Column("status", Text),
    Column("error", JSONB(none_as_null=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)
events = Table(
    "events",
    metadata,
    Column("event_id", BigInteger, primary_key=True),
    Column("session_id", UUID(as_uuid=True)),
    Column("run_id", UUID(as_uuid=True)),
    Column("kind", Text),
    Column("payload", JSONB),
    Column("created_at", DateTime(timezone=True)),
)

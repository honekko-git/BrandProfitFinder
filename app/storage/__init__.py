"""Opportunity persistence exports."""

from app.storage.database import DEFAULT_DATABASE_PATH, connect, initialize_schema, resolve_database_path
from app.storage.models import OpportunityRecord, OpportunityStatus
from app.storage.repository import OpportunityRepository

__all__ = [
    "DEFAULT_DATABASE_PATH",
    "OpportunityRecord",
    "OpportunityRepository",
    "OpportunityStatus",
    "connect",
    "initialize_schema",
    "resolve_database_path",
]

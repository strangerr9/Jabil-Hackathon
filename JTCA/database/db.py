"""
============================================================
JTCA - Database Module (Compatibility Shim)
============================================================
This module previously used SQLite. It now delegates ALL
calls to database.postgres_db (PostgreSQL).

All existing imports like:
    from database.db import get_all_shipments
...continue to work without any changes elsewhere.
============================================================
"""

# Re-export everything from postgres_db so existing code
# using `from database.db import X` keeps working.
from database.postgres_db import (
    # Connection
    get_connection,

    # Schema
    initialize_db,

    # Shipments
    insert_shipment,
    get_all_shipments,
    get_shipment,
    delete_shipment,
    update_shipment_status,
    get_dashboard_stats,

    # Tariff Rules
    get_all_tariff_rules,
    insert_tariff_rule,
    delete_tariff_rules_by_fta,
    delete_tariff_rules_by_ids,
    clear_crawled_rules,

    # Audit Log
    insert_audit_log,
    get_audit_log,
    get_recent_audit_log,
)

# Export Mongo clear function as well
from database.mongo_db import clear_raw_crawls

__all__ = [
    "get_connection",
    "initialize_db",
    "insert_shipment",
    "get_all_shipments",
    "get_shipment",
    "delete_shipment",
    "update_shipment_status",
    "get_dashboard_stats",
    "get_all_tariff_rules",
    "insert_tariff_rule",
    "delete_tariff_rules_by_fta",
    "delete_tariff_rules_by_ids",
    "clear_crawled_rules",
    "clear_raw_crawls",
    "insert_audit_log",
    "get_audit_log",
    "get_recent_audit_log",
]

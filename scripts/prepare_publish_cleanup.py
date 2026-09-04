"""Clean-slate for publish: remove old demo users + all sample/transactional data.
Keeps config collections (role_permissions, system_settings, company_settings,
tax_masters, deduction_types, ppn_configurations, refund_policies, *_settings).
"""
import os
from pymongo import MongoClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
db = MongoClient(MONGO_URL)[DB_NAME]

OLD_DEMO_EMAILS = [
    "dedyirawan18@gmail.com", "sales@safarcrm.com",
    "salesb@safarcrm.com", "accounting@safarcrm.com",
]
r = db.users.delete_many({"email": {"$in": OLD_DEMO_EMAILS}})
print(f"Deleted old demo users: {r.deleted_count}")

# Transactional / sample business data to wipe for a clean start
CLEAR = [
    "customers", "leads", "follow_ups", "quotations", "bookings",
    "invoices", "payments", "receipts", "travelers", "documents",
    "packages", "package_costs", "package_itineraries", "departures",
    "sales_activities", "commission_items", "commission_lines",
    "commission_closings", "commission_adjustments", "commission_schemes",
    "cancellation_requests", "refund_requests", "notifications",
    "mmbc_bookings", "hotel_search_cache", "search_history",
    "n8n_api_logs", "api_logs", "whatsapp_messages", "file_downloads",
    "company_files", "idempotency_keys", "password_reset_tokens",
]
existing = set(db.list_collection_names())
for col in CLEAR:
    if col in existing:
        n = db[col].delete_many({}).deleted_count
        if n:
            print(f"  cleared {col}: {n}")

# Ensure company branding name
db.company_settings.update_one(
    {"key": "company"},
    {"$set": {"company_name": "PT Harmoni Wisata Internusa"}},
    upsert=True,
)
print("Company name set -> PT Harmoni Wisata Internusa")
print("Remaining users:", list(db.users.find({}, {"email": 1, "_id": 0})))
print("DONE")

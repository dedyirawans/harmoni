from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import logging
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Annotated, Any

import bcrypt
import jwt
import httpx
from bson import ObjectId
from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, BeforeValidator, ConfigDict

# ----------------------------------------------------------------------------
# DB / App setup
# ----------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Safar Travel CRM API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("safar-crm")

JWT_ALGORITHM = "HS256"
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Safar Travel CRM")

ROLES = ["super_admin", "sales", "accounting"]

ALL_PERMISSIONS = [
    "dashboard.view", "crm.view", "sales.view", "product.view", "product.manage",
    "booking.view", "accounting.view", "transactions.view", "hpp.view", "tax.view",
    "commission.view", "reports.view", "reports.export", "integration.view",
    "users.view", "users.manage", "settings.view", "settings.manage", "audit.view",
    "packages.view", "departures.view", "notifications.view",
    "quotation.view", "quotation.manage", "quotation.approve", "booking.manage",
    "traveler.manage", "document.manage", "invoice.view", "invoice.manage",
    "payment.view", "payment.manage", "receivable.view",
    "hpp.edit", "expense.view", "expense.manage", "refund.manage", "tax.manage", "commission.manage",
    "cancellation.request", "cancellation.review", "cancellation.approve",
    "refund.request", "refund.review", "refund.approve", "refund.process", "refund.view",
]

DEFAULT_ROLE_PERMISSIONS = {
    "super_admin": list(ALL_PERMISSIONS),
    "sales": [
        "dashboard.view", "crm.view", "sales.view", "packages.view",
        "departures.view", "commission.view", "notifications.view",
        "booking.view", "quotation.view", "quotation.manage", "booking.manage",
        "traveler.manage", "document.manage", "invoice.view", "payment.view",
        "cancellation.request", "refund.view",
    ],
    "accounting": [
        "accounting.view", "transactions.view", "hpp.view", "tax.view", "product.view",
        "commission.view", "commission.manage", "reports.view", "reports.export", "notifications.view",
        "booking.view", "quotation.view", "invoice.view", "invoice.manage",
        "payment.view", "payment.manage", "receivable.view", "document.manage",
        "expense.view", "expense.manage", "refund.manage", "tax.manage",
        "cancellation.request", "cancellation.review",
        "refund.request", "refund.review", "refund.process", "refund.view",
    ],
}

DEFAULT_LOGIN_PAGE = {
    "heading": "Run your Umrah & Travel business with clarity.",
    "subheading": "Leads, bookings, costing and commissions — unified with strict role-based access control.",
    "background_image": "https://images.unsplash.com/photo-1720549973451-018d3623b55a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwxfHxtZWNjYSUyMHVtcmFoJTIwYXJjaGl0ZWN0dXJlfGVufDB8fHx8MTc4NjQxMjMyOHww&ixlib=rb-4.1.0&q=85",
}

# ----------------------------------------------------------------------------
# Mongo model helpers
# ----------------------------------------------------------------------------
PyObjectId = Annotated[str, BeforeValidator(str)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: dict):
        if not doc:
            return None
        return cls(**doc)


# ----------------------------------------------------------------------------
# Password + JWT helpers
# ----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access",
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


# ----------------------------------------------------------------------------
# Auth dependencies
# ----------------------------------------------------------------------------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if user.get("status") == "inactive":
            raise HTTPException(status_code=403, detail="Account is inactive")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_user_permissions(user: dict) -> set:
    if user["role"] == "super_admin":
        return set(ALL_PERMISSIONS)
    rp = await db.role_permissions.find_one({"role": user["role"]})
    if rp:
        return set(rp.get("permissions", []))
    return set(DEFAULT_ROLE_PERMISSIONS.get(user["role"], []))


def require_permission(perm: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        perms = await get_user_permissions(user)
        if perm not in perms:
            raise HTTPException(status_code=403, detail="403 Forbidden: insufficient permission")
        return user
    return checker


def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="403 Forbidden: role not allowed")
        return user
    return checker


# ----------------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------------
async def log_audit(user, module, action, request: Request, record_id=None, old=None, new=None):
    doc = {
        "user_id": user.get("_id") if user else None,
        "user_name": user.get("name") if user else "system",
        "user_email": user.get("email") if user else None,
        "role": user.get("role") if user else None,
        "module": module,
        "action": action,
        "record_id": record_id,
        "old_value": old,
        "new_value": new,
        "ip": request.client.host if request and request.client else None,
        "user_agent": request.headers.get("user-agent") if request else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.audit_logs.insert_one(doc)


def serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    doc.pop("password_hash", None)
    return doc


# ----------------------------------------------------------------------------
# Pydantic request models
# ----------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = ""
    username: str
    role: str
    status: str = "active"
    branch: Optional[str] = ""
    data_scope: str = "own"
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    branch: Optional[str] = None
    data_scope: Optional[str] = None
    password: Optional[str] = None


class RolePermissionsUpdate(BaseModel):
    permissions: List[str]


class CompanySettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    logo: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    npwp: Optional[str] = None
    nib: Optional[str] = None
    bank_account: Optional[str] = None


class SystemSettingsUpdate(BaseModel):
    settings: dict


# ----------------------------------------------------------------------------
# Email helper
# ----------------------------------------------------------------------------
async def send_email(to_email: str, subject: str, html: str):
    if not EMAIL_KEY:
        logger.warning("EMERGENT_EMAIL_KEY missing; skipping email send")
        return
    payload = {"to": [to_email], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            resp = await c.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Email send error: {e}")


# ----------------------------------------------------------------------------
# AUTH ROUTES
# ----------------------------------------------------------------------------
@api_router.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    identifier = body.email.strip().lower()
    user = await db.users.find_one({"$or": [{"email": identifier}, {"username": body.email.strip()}]})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("status") == "inactive":
        raise HTTPException(status_code=403, detail="Account is inactive. Contact administrator.")
    token = create_access_token(str(user["_id"]), user["email"], user["role"])
    clean = serialize(dict(user))
    await log_audit(clean, "auth", "login", request, record_id=clean["_id"])
    return {"token": token, "user": clean}


@api_router.post("/auth/logout")
async def logout(request: Request, user: dict = Depends(get_current_user)):
    await log_audit(user, "auth", "logout", request, record_id=user["_id"])
    return {"message": "Logged out"}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    perms = await get_user_permissions(user)
    user["permissions"] = sorted(perms)
    return user


@api_router.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    # Always return success to avoid user enumeration
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token, "user_id": str(user["_id"]), "email": email, "used": False,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        link = f"{os.environ.get('FRONTEND_URL', '')}/reset-password?token={token}"
        logger.info(f"Password reset link for {email}: {link}")
        html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;background:#f1f5f9;padding:32px">
          <tr><td align="center">
            <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0">
              <tr><td style="background:#0f172a;padding:24px 32px"><span style="color:#fbbf24;font-size:20px;font-weight:700">Safar Travel CRM</span></td></tr>
              <tr><td style="padding:32px">
                <h2 style="color:#0f172a;margin:0 0 12px">Reset your password</h2>
                <p style="color:#475569;line-height:1.6">Hi {user.get('name','there')}, we received a request to reset your password. Click the button below. This link expires in 1 hour.</p>
                <p style="margin:28px 0"><a href="{link}" style="background:#d97706;color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;display:inline-block">Reset Password</a></p>
                <p style="color:#94a3b8;font-size:12px;word-break:break-all">Or paste this link: {link}</p>
                <p style="color:#94a3b8;font-size:12px">If you didn't request this, you can safely ignore this email.</p>
              </td></tr>
            </table>
          </td></tr>
        </table>"""
        await send_email(email, "Reset your Safar CRM password", html)
    return {"message": "If an account exists for this email, a reset link has been sent."}


@api_router.post("/auth/reset-password")
async def reset_password(body: ResetPasswordRequest, request: Request):
    rec = await db.password_reset_tokens.find_one({"token": body.token})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or already used reset link")
    expires = rec["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    await db.users.update_one({"_id": ObjectId(rec["user_id"])},
                              {"$set": {"password_hash": hash_password(body.new_password)}})
    await db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"message": "Password reset successful. You can now log in."}


@api_router.post("/auth/change-password")
async def change_password(body: ChangePasswordRequest, request: Request, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"_id": ObjectId(user["_id"])})
    if not verify_password(body.current_password, full["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    await db.users.update_one({"_id": ObjectId(user["_id"])},
                              {"$set": {"password_hash": hash_password(body.new_password)}})
    await log_audit(user, "auth", "change_password", request, record_id=user["_id"])
    return {"message": "Password changed successfully"}


# ----------------------------------------------------------------------------
# USER MANAGEMENT (super admin)
# ----------------------------------------------------------------------------
@api_router.get("/users")
async def list_users(user: dict = Depends(require_permission("users.view"))):
    users = await db.users.find().sort("created_at", -1).to_list(1000)
    return [serialize(u) for u in users]


@api_router.post("/users")
async def create_user(body: UserCreate, request: Request, user: dict = Depends(require_permission("users.manage"))):
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    email = body.email.strip().lower()
    if await db.users.find_one({"$or": [{"email": email}, {"username": body.username}]}):
        raise HTTPException(status_code=400, detail="Email or username already exists")
    doc = {
        "name": body.name, "email": email, "phone": body.phone, "username": body.username,
        "role": body.role, "status": body.status, "branch": body.branch,
        "data_scope": body.data_scope if body.role == "sales" else "all",
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    new = serialize(await db.users.find_one({"_id": res.inserted_id}))
    await log_audit(user, "user", "create_user", request, record_id=new["_id"], new=serialize(dict(doc)))
    return new


@api_router.put("/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, request: Request, user: dict = Depends(require_permission("users.manage"))):
    existing = await db.users.find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "password" in updates:
        updates["password_hash"] = hash_password(updates.pop("password"))
    if "email" in updates:
        updates["email"] = updates["email"].strip().lower()
    old = serialize(dict(existing))
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    new = serialize(await db.users.find_one({"_id": ObjectId(user_id)}))
    await log_audit(user, "user", "update_user", request, record_id=user_id, old=old, new=new)
    return new


@api_router.patch("/users/{user_id}/status")
async def toggle_status(user_id: str, request: Request, user: dict = Depends(require_permission("users.manage"))):
    existing = await db.users.find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    new_status = "inactive" if existing.get("status") == "active" else "active"
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"status": new_status}})
    await log_audit(user, "user", "update_status", request, record_id=user_id,
                    old={"status": existing.get("status")}, new={"status": new_status})
    return {"status": new_status}


@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request, user: dict = Depends(require_permission("users.manage"))):
    existing = await db.users.find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    if str(existing["_id"]) == user["_id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    await db.users.delete_one({"_id": ObjectId(user_id)})
    await log_audit(user, "user", "delete_user", request, record_id=user_id, old=serialize(dict(existing)))
    return {"message": "User deleted"}


# ----------------------------------------------------------------------------
# ROLES & PERMISSIONS (super admin)
# ----------------------------------------------------------------------------
@api_router.get("/roles")
async def get_roles(user: dict = Depends(require_role("super_admin"))):
    return [{"key": r, "label": r.replace("_", " ").title()} for r in ROLES]


@api_router.get("/permissions")
async def get_permissions(user: dict = Depends(require_role("super_admin"))):
    return ALL_PERMISSIONS


@api_router.get("/role-permissions")
async def get_role_permissions(user: dict = Depends(require_role("super_admin"))):
    result = {}
    for r in ROLES:
        rp = await db.role_permissions.find_one({"role": r})
        result[r] = rp.get("permissions", DEFAULT_ROLE_PERMISSIONS.get(r, [])) if rp else DEFAULT_ROLE_PERMISSIONS.get(r, [])
    return result


@api_router.put("/role-permissions/{role}")
async def update_role_permissions(role: str, body: RolePermissionsUpdate, request: Request, user: dict = Depends(require_role("super_admin"))):
    if role not in ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if role == "super_admin":
        raise HTTPException(status_code=400, detail="Super Admin permissions cannot be changed")
    valid = [p for p in body.permissions if p in ALL_PERMISSIONS]
    old = await db.role_permissions.find_one({"role": role})
    await db.role_permissions.update_one({"role": role}, {"$set": {"permissions": valid}}, upsert=True)
    await log_audit(user, "settings", "update_permissions", request, record_id=role,
                    old={"permissions": old.get("permissions") if old else None}, new={"permissions": valid})
    return {"role": role, "permissions": valid}


# ----------------------------------------------------------------------------
# AUDIT LOG
# ----------------------------------------------------------------------------
@api_router.get("/audit-logs")
async def get_audit_logs(module: Optional[str] = None, user: dict = Depends(require_permission("audit.view"))):
    query = {}
    if module and module != "all":
        query["module"] = module
    logs = await db.audit_logs.find(query).sort("timestamp", -1).to_list(500)
    return [serialize(l) for l in logs]


# ----------------------------------------------------------------------------
# COMPANY + SYSTEM SETTINGS
# ----------------------------------------------------------------------------
@api_router.get("/company-settings")
async def get_company_settings(user: dict = Depends(require_permission("settings.view"))):
    doc = await db.company_settings.find_one({"key": "company"})
    return serialize(doc) if doc else {}


@api_router.put("/company-settings")
async def update_company_settings(body: CompanySettingsUpdate, request: Request, user: dict = Depends(require_permission("settings.manage"))):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    old = await db.company_settings.find_one({"key": "company"})
    await db.company_settings.update_one({"key": "company"}, {"$set": updates}, upsert=True)
    new = await db.company_settings.find_one({"key": "company"})
    await log_audit(user, "settings", "update_company", request, record_id="company",
                    old=serialize(dict(old)) if old else None, new=serialize(dict(new)))
    return serialize(new)


@api_router.get("/system-settings")
async def get_system_settings(user: dict = Depends(require_permission("settings.view"))):
    doc = await db.system_settings.find_one({"key": "system"})
    return serialize(doc) if doc else {"settings": {}}


@api_router.put("/system-settings")
async def update_system_settings(body: SystemSettingsUpdate, request: Request, user: dict = Depends(require_permission("settings.manage"))):
    old = await db.system_settings.find_one({"key": "system"})
    await db.system_settings.update_one({"key": "system"}, {"$set": {"settings": body.settings}}, upsert=True)
    new = await db.system_settings.find_one({"key": "system"})
    await log_audit(user, "settings", "update_system", request, record_id="system",
                    old=serialize(dict(old)) if old else None, new=serialize(dict(new)))
    return serialize(new)


# ----------------------------------------------------------------------------
# HPP (restricted: super_admin + accounting only)
# ----------------------------------------------------------------------------
@api_router.get("/hpp")
async def get_hpp(user: dict = Depends(require_permission("hpp.view"))):
    # Demo costing data; Sales is blocked at the permission layer -> 403
    return {
        "packages": [
            {"name": "Umrah Reguler 9 Hari", "supplier_cost": 22500000, "selling_price": 27500000,
             "gross_profit": 5000000, "gross_margin": 18.2},
            {"name": "Umrah Plus Turki 12 Hari", "supplier_cost": 31000000, "selling_price": 38500000,
             "gross_profit": 7500000, "gross_margin": 19.5},
            {"name": "Haji Furoda 2026", "supplier_cost": 210000000, "selling_price": 245000000,
             "gross_profit": 35000000, "gross_margin": 14.3},
        ]
    }


# ----------------------------------------------------------------------------
# DASHBOARD stats (role-aware placeholder)
# ----------------------------------------------------------------------------
@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    role = user["role"]
    if role == "super_admin":
        total_users = await db.users.count_documents({})
        total_customers = await db.customers.count_documents({})
        total_leads = await db.leads.count_documents({})
        total_packages = await db.packages.count_documents({})
        return {"role": role, "cards": [
            {"label": "Total Users", "value": total_users, "hint": "across all roles"},
            {"label": "Total Customers", "value": total_customers, "hint": "registered"},
            {"label": "Total Leads", "value": total_leads, "hint": "in pipeline"},
            {"label": "Total Packages", "value": total_packages, "hint": "products"},
        ]}
    if role == "sales":
        return {"role": role, "cards": [
            {"label": "My Leads", "value": 24, "hint": "assigned to you"},
            {"label": "My Quotations", "value": 9, "hint": "pending"},
            {"label": "My Bookings", "value": 6, "hint": "this month"},
            {"label": "My Commission", "value": "Rp 12.4M", "hint": "estimated"},
        ]}
    return {"role": role, "cards": [
        {"label": "Transactions", "value": 342, "hint": "this month"},
        {"label": "Pending Tax", "value": "Rp 48.2M", "hint": "to reconcile"},
        {"label": "Commission Payable", "value": "Rp 96.7M", "hint": "to sales team"},
        {"label": "Gross Margin", "value": "17.8%", "hint": "avg across packages"},
    ]}


@api_router.get("/dashboard/charts")
async def dashboard_charts(user: dict = Depends(get_current_user)):
    role = user["role"]
    of = owner_filter(user) if role == "sales" else {}
    leads = await db.leads.find(of).to_list(5000)
    by_stage = {s: 0 for s in LEAD_STAGES + [LEAD_LOST]}
    by_source = {}
    monthly = {}
    for l in leads:
        st = l.get("status") or "NEW"
        by_stage[st] = by_stage.get(st, 0) + 1
        src = l.get("source") or "Other"
        by_source[src] = by_source.get(src, 0) + 1
        key = (l.get("created_at") or "")[:7]
        if key:
            monthly[key] = monthly.get(key, 0) + 1
    leads_by_stage = [{"name": s, "value": by_stage.get(s, 0)} for s in LEAD_STAGES + [LEAD_LOST]]
    leads_by_source = [{"name": k, "value": v} for k, v in sorted(by_source.items(), key=lambda x: -x[1])][:6]

    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    keys = []
    for i in range(5, -1, -1):
        mm, yy = m - i, y
        while mm <= 0:
            mm += 12
            yy -= 1
        keys.append(f"{yy:04d}-{mm:02d}")
    mlabel = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Ags", "Sep", "Okt", "Nov", "Des"]
    monthly_leads = [{"name": mlabel[int(k[5:7]) - 1], "value": monthly.get(k, 0)} for k in keys]

    pkgs = await db.packages.find({}).to_list(5000)
    pt = {}
    for p in pkgs:
        t = norm_type(p.get("product_type") or "TOUR")
        pt[t] = pt.get(t, 0) + 1
    tlabel = {"UMROH": "Umroh", "TOUR": "Paket Tour", "UMROH_PLUS": "Umroh Plus"}
    packages_by_type = [{"name": tlabel.get(k, k), "value": v} for k, v in pt.items()]

    return {"leads_by_stage": leads_by_stage, "leads_by_source": leads_by_source,
            "monthly_leads": monthly_leads, "packages_by_type": packages_by_type}


@api_router.get("/notifications")
async def notifications(user: dict = Depends(require_permission("notifications.view"))):
    q = {"$or": [{"user_id": user["_id"]}, {"role": user["role"]}]}
    docs = await db.notifications.find(q).sort("created_at", -1).to_list(50)
    return [{"id": str(d["_id"]), "title": d.get("title", ""), "body": d.get("body", ""),
             "link": d.get("link", ""), "read": d.get("read", False),
             "time": d.get("created_at", "")} for d in docs]


@api_router.patch("/notifications/{nid}/read")
async def mark_notification_read(nid: str, user: dict = Depends(require_permission("notifications.view"))):
    await db.notifications.update_one({"_id": ObjectId(nid)}, {"$set": {"read": True}})
    return {"ok": True}


@api_router.get("/public/login-config")
async def public_login_config():
    doc = await db.system_settings.find_one({"key": "system"})
    lp = (doc.get("settings", {}) if doc else {}).get("login_page", {})
    return {
        "heading": lp.get("heading") or DEFAULT_LOGIN_PAGE["heading"],
        "subheading": lp.get("subheading") or DEFAULT_LOGIN_PAGE["subheading"],
        "background_image": lp.get("background_image") or DEFAULT_LOGIN_PAGE["background_image"],
    }


@api_router.get("/public/branding")
async def public_branding():
    doc = await db.company_settings.find_one({"key": "company"})
    return {
        "company_name": (doc.get("company_name") if doc else None) or "Safar Travel CRM",
        "logo": (doc.get("logo") if doc else None) or "",
    }



@api_router.get("/")
async def root():
    return {"message": "Safar Travel CRM API"}


# ============================================================================
# PHASE 2 — CRM & SALES MANAGEMENT
# ============================================================================
LEAD_STAGES = ["NEW", "CONTACTED", "QUALIFIED", "QUOTATION", "NEGOTIATION", "BOOKING", "PAID", "COMPLETED"]
LEAD_LOST = "LOST"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def today_str():
    return datetime.now(timezone.utc).date().isoformat()


def owner_filter(user: dict) -> dict:
    if user["role"] == "super_admin":
        return {}
    scope = user.get("data_scope", "own")
    if scope == "all":
        return {}
    if scope == "branch":
        return {"branch": user.get("branch")}
    return {"sales_pic_id": user["_id"]}


def can_access_record(user: dict, doc: dict) -> bool:
    if user["role"] == "super_admin":
        return True
    scope = user.get("data_scope", "own")
    if scope == "all":
        return True
    if scope == "branch":
        return doc.get("branch") == user.get("branch")
    return doc.get("sales_pic_id") == user["_id"]


async def resolve_pic(user: dict, sales_pic_id: Optional[str]):
    pic_id = sales_pic_id if (user["role"] == "super_admin" and sales_pic_id) else user["_id"]
    pic = await db.users.find_one({"_id": ObjectId(pic_id)}) if pic_id else None
    name = pic["name"] if pic else user["name"]
    branch = (pic.get("branch") if pic else user.get("branch")) or ""
    return pic_id, name, branch


# ---------- Pydantic models ----------
class CustomerCreate(BaseModel):
    full_name: str
    whatsapp: Optional[str] = ""
    email: Optional[str] = ""
    gender: Optional[str] = ""
    date_of_birth: Optional[str] = ""
    nik: Optional[str] = ""
    passport_number: Optional[str] = ""
    passport_expiry: Optional[str] = ""
    address: Optional[str] = ""
    city: Optional[str] = ""
    country: Optional[str] = ""
    customer_type: Optional[str] = "Prospect"
    customer_source: Optional[str] = ""
    sales_pic_id: Optional[str] = None
    tags: Optional[List[str]] = []
    notes: Optional[str] = ""


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    nik: Optional[str] = None
    passport_number: Optional[str] = None
    passport_expiry: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    customer_type: Optional[str] = None
    customer_source: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class NoteCreate(BaseModel):
    note: str


class LeadCreate(BaseModel):
    customer_id: Optional[str] = None
    source: Optional[str] = ""
    interested_package: Optional[str] = ""
    package_id: Optional[str] = ""
    package_type: Optional[str] = ""
    package_name: Optional[str] = ""
    destination_id: Optional[str] = ""
    destination_name: Optional[str] = ""
    destination: Optional[str] = ""
    pax: Optional[int] = 0
    budget: Optional[float] = 0
    departure_date: Optional[str] = ""
    status: Optional[str] = "NEW"
    next_follow_up: Optional[str] = ""
    notes: Optional[str] = ""
    sales_pic_id: Optional[str] = None


class LeadUpdate(BaseModel):
    customer_id: Optional[str] = None
    source: Optional[str] = None
    interested_package: Optional[str] = None
    package_id: Optional[str] = None
    package_type: Optional[str] = None
    package_name: Optional[str] = None
    destination_id: Optional[str] = None
    destination_name: Optional[str] = None
    destination: Optional[str] = None
    pax: Optional[int] = None
    budget: Optional[float] = None
    departure_date: Optional[str] = None
    next_follow_up: Optional[str] = None
    notes: Optional[str] = None


class StageUpdate(BaseModel):
    stage: str


class FollowUpCreate(BaseModel):
    customer_id: Optional[str] = None
    lead_id: Optional[str] = None
    activity_type: str = "Call"
    due_date: str
    notes: Optional[str] = ""


class CommunicationCreate(BaseModel):
    customer_id: Optional[str] = None
    lead_id: Optional[str] = None
    phone: Optional[str] = ""
    direction: str = "outbound"
    message: str
    channel: str = "whatsapp"
    source: Optional[str] = "manual"


async def log_activity(customer_id, lead_id, atype, title, detail, user):
    await db.lead_activities.insert_one({
        "customer_id": customer_id, "lead_id": lead_id, "type": atype,
        "title": title, "detail": detail,
        "user_id": user["_id"] if user else None,
        "user_name": user["name"] if user else "system",
        "timestamp": now_iso(),
    })


# ---------- Customers ----------
@api_router.get("/customers")
async def list_customers(q: Optional[str] = None, customer_type: Optional[str] = None,
                         user: dict = Depends(require_permission("crm.view"))):
    query = owner_filter(user)
    if customer_type and customer_type != "all":
        query["customer_type"] = customer_type
    if q:
        query["$or"] = [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"whatsapp": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"customer_code": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.customers.find(query).sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.post("/customers")
async def create_customer(body: CustomerCreate, request: Request,
                          user: dict = Depends(require_permission("crm.view"))):
    pic_id, pic_name, branch = await resolve_pic(user, body.sales_pic_id)
    count = await db.customers.count_documents({})
    doc = body.model_dump()
    doc.pop("sales_pic_id", None)
    doc.update({
        "customer_code": f"CUST-{count + 1:05d}",
        "sales_pic_id": pic_id, "sales_pic_name": pic_name, "branch": branch,
        "created_at": now_iso(), "created_by": user["name"],
    })
    res = await db.customers.insert_one(doc)
    new = serialize(await db.customers.find_one({"_id": res.inserted_id}))
    await log_audit(user, "customer", "create_customer", request, record_id=new["_id"], new={"full_name": new["full_name"]})
    return new


@api_router.get("/customers/{cid}")
async def get_customer(cid: str, user: dict = Depends(require_permission("crm.view"))):
    doc = await db.customers.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden: not your customer")
    return serialize(doc)


@api_router.put("/customers/{cid}")
async def update_customer(cid: str, body: CustomerUpdate, request: Request,
                          user: dict = Depends(require_permission("crm.view"))):
    doc = await db.customers.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden: not your customer")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    await db.customers.update_one({"_id": ObjectId(cid)}, {"$set": updates})
    await log_audit(user, "customer", "update_customer", request, record_id=cid, new=updates)
    return serialize(await db.customers.find_one({"_id": ObjectId(cid)}))


@api_router.delete("/customers/{cid}")
async def delete_customer(cid: str, request: Request, user: dict = Depends(require_permission("crm.view"))):
    doc = await db.customers.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden: not your customer")
    await db.customers.delete_one({"_id": ObjectId(cid)})
    await log_audit(user, "customer", "delete_customer", request, record_id=cid)
    return {"message": "Customer deleted"}


@api_router.post("/customers/{cid}/notes")
async def add_note(cid: str, body: NoteCreate, user: dict = Depends(require_permission("crm.view"))):
    doc = await db.customers.find_one({"_id": ObjectId(cid)})
    if not doc or not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    rec = {"customer_id": cid, "note": body.note, "user_name": user["name"], "timestamp": now_iso()}
    await db.customer_notes.insert_one(dict(rec))
    return serialize(rec)


@api_router.get("/customers/{cid}/360")
async def customer_360(cid: str, user: dict = Depends(require_permission("crm.view"))):
    customer = await db.customers.find_one({"_id": ObjectId(cid)})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not can_access_record(user, customer):
        raise HTTPException(status_code=403, detail="403 Forbidden: not your customer")
    leads = [serialize(d) for d in await db.leads.find({"customer_id": cid}).sort("created_at", -1).to_list(500)]
    follow_ups = [serialize(d) for d in await db.follow_ups.find({"customer_id": cid}).sort("due_date", -1).to_list(500)]
    comms = [serialize(d) for d in await db.communications.find({"customer_id": cid}).sort("timestamp", -1).to_list(500)]
    notes = [serialize(d) for d in await db.customer_notes.find({"customer_id": cid}).sort("timestamp", -1).to_list(500)]
    acts = [serialize(d) for d in await db.lead_activities.find({"customer_id": cid}).sort("timestamp", -1).to_list(500)]

    timeline = []
    for a in acts:
        timeline.append({"kind": a.get("type", "activity"), "title": a.get("title", "Activity"),
                         "detail": a.get("detail", ""), "user_name": a.get("user_name"), "timestamp": a.get("timestamp")})
    for f in follow_ups:
        timeline.append({"kind": "follow_up", "title": f"Follow Up — {f.get('activity_type')}",
                         "detail": f.get("notes", ""), "user_name": f.get("sales_pic_name"), "timestamp": f.get("created_at", f.get("due_date"))})
    for c in comms:
        timeline.append({"kind": "communication", "title": f"{c.get('channel', 'msg').title()} ({c.get('direction')})",
                         "detail": c.get("message", ""), "user_name": c.get("sales_pic_name"), "timestamp": c.get("timestamp")})
    for n in notes:
        timeline.append({"kind": "note", "title": "Note", "detail": n.get("note", ""),
                         "user_name": n.get("user_name"), "timestamp": n.get("timestamp")})
    timeline.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    total_value = sum(float(l.get("budget") or 0) for l in leads if l.get("status") != "LOST")
    return {
        "customer": serialize(customer), "leads": leads, "follow_ups": follow_ups,
        "communications": comms, "notes": notes, "timeline": timeline,
        "totals": {"leads": len(leads), "follow_ups": len(follow_ups),
                   "communications": len(comms), "total_value": total_value},
    }


# ---------- Leads / Pipeline ----------
@api_router.get("/leads")
async def list_leads(status: Optional[str] = None, user: dict = Depends(require_permission("sales.view"))):
    query = owner_filter(user)
    if status and status != "all":
        query["status"] = status
    docs = await db.leads.find(query).sort("created_at", -1).to_list(2000)
    return [serialize(d) for d in docs]


@api_router.post("/leads")
async def create_lead(body: LeadCreate, request: Request, user: dict = Depends(require_permission("sales.view"))):
    pic_id, pic_name, branch = await resolve_pic(user, body.sales_pic_id)
    customer_name = ""
    if body.customer_id:
        c = await db.customers.find_one({"_id": ObjectId(body.customer_id)})
        customer_name = c.get("full_name") if c else ""
    count = await db.leads.count_documents({})
    stage = body.status if body.status in LEAD_STAGES + [LEAD_LOST] else "NEW"
    doc = body.model_dump()
    doc.pop("sales_pic_id", None)
    if body.package_id and ObjectId.is_valid(body.package_id):
        p = await db.packages.find_one({"_id": ObjectId(body.package_id)})
        if p:
            doc["package_id"] = str(p["_id"])
            doc["package_type"] = p.get("product_type", "")
            doc["package_name"] = p.get("package_name", "")
            doc["destination_id"] = str(p["_id"])
            doc["destination_name"] = p.get("destination", "")
            doc["interested_package"] = p.get("package_name", "")
            doc["destination"] = p.get("destination", "")
    doc.update({
        "lead_code": f"LEAD-{count + 1:05d}", "status": stage,
        "customer_name": customer_name, "sales_pic_id": pic_id, "sales_pic_name": pic_name,
        "branch": branch, "last_contact": now_iso(), "created_at": now_iso(),
    })
    res = await db.leads.insert_one(doc)
    lead = serialize(await db.leads.find_one({"_id": res.inserted_id}))
    await log_activity(body.customer_id, lead["_id"], "lead_created", "Lead created",
                       f"{body.interested_package or 'New lead'} — stage {stage}", user)
    await log_audit(user, "lead", "create_lead", request, record_id=lead["_id"], new={"stage": stage})
    return lead


@api_router.get("/lead-packages")
async def lead_packages(q: Optional[str] = None, user: dict = Depends(require_permission("sales.view"))):
    docs = await db.packages.find({"status": "ACTIVE"}).to_list(500)
    today = today_str()
    out = []
    for p in docs:
        deps = await db.departures.find({"package_id": str(p["_id"])}).sort("departure_date", 1).to_list(50)
        seat = 0
        nearest = ""
        for dd in deps:
            seat += max(0, int(dd.get("quota") or 0) - int(dd.get("confirmed_pax") or 0))
            if not nearest and (dd.get("departure_date", "") >= today):
                nearest = dd.get("departure_date", "")
        out.append({"id": str(p["_id"]), "package_code": p.get("package_code", ""), "package_name": p.get("package_name", ""),
                    "product_type": p.get("product_type", ""), "destination": p.get("destination", ""),
                    "duration": p.get("duration", ""), "selling_price": p.get("selling_price", 0),
                    "departure_date": nearest, "available_seat": seat})
    if q:
        ql = q.lower()
        out = [o for o in out if any(ql in (o[k] or "").lower() for k in ("package_name", "package_code", "product_type", "destination"))]
    return out


@api_router.get("/leads/{lid}")
async def get_lead(lid: str, user: dict = Depends(require_permission("sales.view"))):
    doc = await db.leads.find_one({"_id": ObjectId(lid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden: not your lead")
    return serialize(doc)


@api_router.put("/leads/{lid}")
async def update_lead(lid: str, body: LeadUpdate, request: Request, user: dict = Depends(require_permission("sales.view"))):
    doc = await db.leads.find_one({"_id": ObjectId(lid)})
    if not doc or not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if body.customer_id:
        c = await db.customers.find_one({"_id": ObjectId(body.customer_id)})
        updates["customer_name"] = c.get("full_name") if c else ""
    await db.leads.update_one({"_id": ObjectId(lid)}, {"$set": updates})
    await log_audit(user, "lead", "update_lead", request, record_id=lid, new=updates)
    return serialize(await db.leads.find_one({"_id": ObjectId(lid)}))


@api_router.patch("/leads/{lid}/stage")
async def move_stage(lid: str, body: StageUpdate, request: Request, user: dict = Depends(require_permission("sales.view"))):
    if body.stage not in LEAD_STAGES + [LEAD_LOST]:
        raise HTTPException(status_code=400, detail="Invalid pipeline stage")
    doc = await db.leads.find_one({"_id": ObjectId(lid)})
    if not doc or not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    if user["role"] != "super_admin" and doc.get("sales_pic_id") != user["_id"]:
        raise HTTPException(status_code=403, detail="403 Forbidden: only the assigned sales or super admin can move this lead")
    old_stage = doc.get("status")
    await db.leads.update_one({"_id": ObjectId(lid)}, {"$set": {"status": body.stage, "last_contact": now_iso()}})
    await db.sales_pipeline.insert_one({
        "lead_id": lid, "customer_id": doc.get("customer_id"), "from_stage": old_stage, "to_stage": body.stage,
        "user_name": user["name"], "timestamp": now_iso(),
    })
    await log_activity(doc.get("customer_id"), lid, "stage_change", f"Stage: {old_stage} → {body.stage}", "", user)
    await log_audit(user, "lead", "move_stage", request, record_id=lid, old={"stage": old_stage}, new={"stage": body.stage})
    return serialize(await db.leads.find_one({"_id": ObjectId(lid)}))


@api_router.delete("/leads/{lid}")
async def delete_lead(lid: str, request: Request, user: dict = Depends(require_permission("sales.view"))):
    doc = await db.leads.find_one({"_id": ObjectId(lid)})
    if not doc or not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    await db.leads.delete_one({"_id": ObjectId(lid)})
    await log_audit(user, "lead", "delete_lead", request, record_id=lid)
    return {"message": "Lead deleted"}


# ---------- Follow Ups ----------
@api_router.get("/follow-ups")
async def list_follow_ups(scope: Optional[str] = "all", user: dict = Depends(require_permission("sales.view"))):
    docs = await db.follow_ups.find(owner_filter(user)).sort("due_date", 1).to_list(2000)
    today = today_str()
    res = []
    for d in docs:
        d = serialize(d)
        status = d.get("status", "pending")
        due = (d.get("due_date") or "")[:10]
        if scope == "completed" and status == "completed":
            res.append(d)
        elif scope == "today" and status != "completed" and due == today:
            res.append(d)
        elif scope == "overdue" and status != "completed" and due and due < today:
            res.append(d)
        elif scope == "upcoming" and status != "completed" and due and due > today:
            res.append(d)
        elif scope in (None, "all"):
            res.append(d)
    return res


@api_router.post("/follow-ups")
async def create_follow_up(body: FollowUpCreate, request: Request, user: dict = Depends(require_permission("sales.view"))):
    pic_id, pic_name, branch = await resolve_pic(user, None)
    customer_name = ""
    if body.customer_id:
        c = await db.customers.find_one({"_id": ObjectId(body.customer_id)})
        customer_name = c.get("full_name") if c else ""
    doc = body.model_dump()
    doc.update({
        "status": "pending", "customer_name": customer_name,
        "sales_pic_id": pic_id, "sales_pic_name": pic_name, "branch": branch,
        "created_at": now_iso(),
    })
    res = await db.follow_ups.insert_one(doc)
    fu = serialize(await db.follow_ups.find_one({"_id": res.inserted_id}))
    await log_activity(body.customer_id, body.lead_id, "follow_up_created",
                       f"Follow up scheduled — {body.activity_type}", body.notes or "", user)
    return fu


@api_router.patch("/follow-ups/{fid}/complete")
async def complete_follow_up(fid: str, user: dict = Depends(require_permission("sales.view"))):
    doc = await db.follow_ups.find_one({"_id": ObjectId(fid)})
    if not doc or not can_access_record(user, doc):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    await db.follow_ups.update_one({"_id": ObjectId(fid)}, {"$set": {"status": "completed", "completed_at": now_iso()}})
    await log_activity(doc.get("customer_id"), doc.get("lead_id"), "follow_up_done",
                       f"Follow up completed — {doc.get('activity_type')}", doc.get("notes", ""), user)
    return serialize(await db.follow_ups.find_one({"_id": ObjectId(fid)}))


# ---------- Communications ----------
@api_router.get("/communications")
async def list_communications(customer_id: Optional[str] = None, user: dict = Depends(require_permission("crm.view"))):
    query = owner_filter(user)
    if customer_id:
        query["customer_id"] = customer_id
    docs = await db.communications.find(query).sort("timestamp", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.post("/communications")
async def create_communication(body: CommunicationCreate, user: dict = Depends(require_permission("crm.view"))):
    pic_id, pic_name, branch = await resolve_pic(user, None)
    doc = body.model_dump()
    doc.update({"sales_pic_id": pic_id, "sales_pic_name": pic_name, "branch": branch, "timestamp": now_iso()})
    res = await db.communications.insert_one(doc)
    return serialize(await db.communications.find_one({"_id": res.inserted_id}))


# ---------- Sales Dashboard ----------
@api_router.get("/sales/dashboard")
async def sales_dashboard(user: dict = Depends(require_permission("sales.view"))):
    of = owner_filter(user)

    def q(extra):
        return {**of, **extra}

    new_leads = await db.leads.count_documents(q({"status": "NEW"}))
    quotations = await db.leads.count_documents(q({"status": "QUOTATION"}))
    bookings = await db.leads.count_documents(q({"status": {"$in": ["BOOKING", "PAID", "COMPLETED"]}}))
    total_leads = await db.leads.count_documents(of)
    won = await db.leads.count_documents(q({"status": {"$in": ["PAID", "COMPLETED"]}}))
    active_leads = await db.leads.find(q({"status": {"$ne": "LOST"}})).to_list(3000)
    my_pax = sum(int(l.get("pax") or 0) for l in active_leads)
    estimated = sum(float(l.get("budget") or 0) for l in active_leads)
    today = today_str()
    upcoming_departure = sum(1 for l in active_leads if (l.get("departure_date") or "")[:10] >= today and l.get("departure_date"))

    fdocs = await db.follow_ups.find(of).to_list(3000)
    fu_today = sum(1 for f in fdocs if f.get("status") != "completed" and (f.get("due_date") or "")[:10] == today)
    fu_overdue = sum(1 for f in fdocs if f.get("status") != "completed" and (f.get("due_date") or "")[:10] and (f.get("due_date") or "")[:10] < today)
    customers_count = await db.customers.count_documents(of)
    conversion = round(won / total_leads * 100, 1) if total_leads else 0.0

    return {
        "new_leads": new_leads, "follow_up_today": fu_today, "overdue_follow_up": fu_overdue,
        "my_quotations": quotations, "my_bookings": bookings, "my_pax": my_pax,
        "upcoming_departure": upcoming_departure, "outstanding_customer": customers_count,
        "estimated_sales": estimated, "conversion_rate": conversion,
    }


# ---------- Global Search ----------
@api_router.get("/search")
async def global_search(q: str, user: dict = Depends(require_permission("crm.view"))):
    of = owner_filter(user)
    cust_q = {**of, "$or": [
        {"full_name": {"$regex": q, "$options": "i"}},
        {"whatsapp": {"$regex": q, "$options": "i"}},
        {"email": {"$regex": q, "$options": "i"}},
        {"customer_code": {"$regex": q, "$options": "i"}},
    ]}
    customers = [serialize(d) for d in await db.customers.find(cust_q).limit(8).to_list(8)]
    lead_q = {**of, "$or": [
        {"lead_code": {"$regex": q, "$options": "i"}},
        {"customer_name": {"$regex": q, "$options": "i"}},
        {"interested_package": {"$regex": q, "$options": "i"}},
        {"destination": {"$regex": q, "$options": "i"}},
    ]}
    leads = [serialize(d) for d in await db.leads.find(lead_q).limit(8).to_list(8)]
    return {"customers": customers, "leads": leads}


# ============================================================================
# PHASE 3 — PRODUCT / TOUR & UMRAH PACKAGE MANAGEMENT
# ============================================================================
PACKAGE_STATUSES = ["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"]
HPP_STRIP = ["hpp", "total_cost", "cost_per_pax", "gross_profit", "gross_margin", "costs", "cost_components"]
COST_COMPONENTS = ["flight", "hotel", "visa", "transport", "guide", "muthawwif", "handling", "meal", "insurance", "other"]


def require_any_permission(*perms):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        up = await get_user_permissions(user)
        if not any(p in up for p in perms):
            raise HTTPException(status_code=403, detail="403 Forbidden: insufficient permission")
        return user
    return checker


async def perms_of(user):
    return await get_user_permissions(user)


PRODUCT_TYPES3 = ["UMROH", "TOUR", "UMROH_PLUS"]
SUB_CATEGORIES = ["PRIVATE", "OPEN_TRIP", "SEAT_IN_COACH"]


def norm_type(t):
    return "UMROH" if t == "UMRAH" else t


def resolve_category_tax(pkg, settings):
    ct = (settings or {}).get("category_tax", {})
    pt = norm_type(pkg.get("product_type"))
    if pt == "TOUR":
        pct = float(ct.get("tour_percent", 0) or 0)
        base = float(pkg.get("selling_price") or 0)
    elif pt == "UMROH_PLUS":
        pct = float(ct.get("umroh_plus_percent", 0) or 0)
        base = float(pkg.get("tour_price_portion") or 0)  # only tour portion taxed
    else:  # UMROH
        pct = float(ct.get("umroh_percent", 0) or 0)
        base = 0
    return pct, round(base * pct / 100)


def strip_hpp(pkg: dict, can_hpp: bool) -> dict:
    d = serialize(dict(pkg))
    if not can_hpp:
        for k in HPP_STRIP:
            d.pop(k, None)
    return d


class PackageModel(BaseModel):
    package_name: str
    product_type: str = "TOUR"
    sub_category: Optional[str] = ""
    min_quota_pax: Optional[int] = 0
    tour_price_portion: Optional[float] = 0
    pricing_tiers: Optional[List[dict]] = []
    category: Optional[str] = ""
    destination: Optional[str] = ""
    country: Optional[str] = ""
    duration: Optional[str] = ""
    description: Optional[str] = ""
    cover_image: Optional[str] = ""
    gallery: Optional[List[str]] = []
    min_pax: Optional[int] = 1
    max_pax: Optional[int] = 40
    selling_price: Optional[float] = 0
    child_price: Optional[float] = 0
    infant_price: Optional[float] = 0
    single_supplement: Optional[float] = 0
    currency: Optional[str] = "IDR"
    tax_treatment: Optional[str] = "Non-PPN"
    commission_eligibility: Optional[bool] = True
    status: Optional[str] = "DRAFT"
    promo_text: Optional[str] = ""
    terms: Optional[str] = ""
    umrah: Optional[dict] = {}


class ItineraryModel(BaseModel):
    day: Optional[int] = 1
    date: Optional[str] = ""
    location: Optional[str] = ""
    activity: Optional[str] = ""
    hotel: Optional[str] = ""
    meal: Optional[str] = ""
    transport: Optional[str] = ""
    flight: Optional[str] = ""
    description: Optional[str] = ""
    notes: Optional[str] = ""
    images: Optional[List[str]] = []


class DepartureModel(BaseModel):
    departure_date: str
    return_date: Optional[str] = ""
    quota: Optional[int] = 0
    confirmed_pax: Optional[int] = 0
    flight: Optional[str] = ""
    hotel: Optional[str] = ""
    price: Optional[float] = 0
    status: Optional[str] = ""


class CostingModel(BaseModel):
    components: dict
    pax_basis: Optional[int] = 1


def compute_departure(dep: dict) -> dict:
    quota = int(dep.get("quota") or 0)
    confirmed = int(dep.get("confirmed_pax") or 0)
    available = max(quota - confirmed, 0)
    dep["available_seat"] = available
    forced = dep.get("status")
    if forced in ("CLOSED", "CANCELLED"):
        return dep
    if available <= 0:
        dep["status"] = "FULL"
    elif quota > 0 and available / quota <= 0.2:
        dep["status"] = "ALMOST FULL"
    else:
        dep["status"] = "OPEN"
    return dep


@api_router.get("/packages")
async def list_packages(product_type: Optional[str] = None, sub_category: Optional[str] = None, status: Optional[str] = None, q: Optional[str] = None,
                        user: dict = Depends(require_any_permission("product.view", "packages.view", "hpp.view"))):
    up = await perms_of(user)
    can_hpp = "hpp.view" in up
    can_manage = "product.manage" in up
    query = {}
    if product_type and product_type != "all":
        query["product_type"] = product_type
    if sub_category and sub_category != "all":
        query["sub_category"] = sub_category
    if q:
        query["$or"] = [{"package_name": {"$regex": q, "$options": "i"}},
                        {"destination": {"$regex": q, "$options": "i"}},
                        {"package_code": {"$regex": q, "$options": "i"}}]
    if not can_manage and not can_hpp:
        query["status"] = "ACTIVE"  # sales: only active
    elif status and status != "all":
        query["status"] = status
    docs = await db.packages.find(query).sort("created_at", -1).to_list(1000)
    sysdoc = await db.system_settings.find_one({"key": "system"})
    settings = (sysdoc or {}).get("settings", {})
    out = []
    for d in docs:
        item = strip_hpp(d, can_hpp)
        pct, amt = resolve_category_tax(d, settings)
        item["tax_percent"] = pct
        item["tax_amount"] = amt
        out.append(item)
    return out


@api_router.post("/packages")
async def create_package(body: PackageModel, request: Request, user: dict = Depends(require_permission("product.manage"))):
    if body.product_type not in PRODUCT_TYPES3:
        raise HTTPException(status_code=400, detail="Invalid product type")
    count = await db.packages.count_documents({})
    prefix = {"UMROH": "UMR", "TOUR": "TOUR", "UMROH_PLUS": "UMRPLUS"}[body.product_type]
    doc = body.model_dump()
    doc.update({"package_code": f"{prefix}-{count + 1:04d}", "version": 1,
                "created_at": now_iso(), "created_by": user["name"]})
    res = await db.packages.insert_one(doc)
    new = serialize(await db.packages.find_one({"_id": res.inserted_id}))
    await log_audit(user, "package", "create_package", request, record_id=new["_id"], new={"name": body.package_name})
    return new


@api_router.get("/packages/{pid}")
async def get_package(pid: str, user: dict = Depends(require_any_permission("product.view", "packages.view", "hpp.view"))):
    pkg = await db.packages.find_one({"_id": ObjectId(pid)})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    up = await perms_of(user)
    can_hpp = "hpp.view" in up
    can_manage = "product.manage" in up
    if not can_manage and not can_hpp and pkg.get("status") != "ACTIVE":
        raise HTTPException(status_code=403, detail="403 Forbidden: package not available")
    itins = [serialize(d) for d in await db.package_itineraries.find({"package_id": pid}).sort("day", 1).to_list(200)]
    deps = [compute_departure(serialize(d)) for d in await db.departures.find({"package_id": pid}).sort("departure_date", 1).to_list(200)]
    result = {"package": strip_hpp(pkg, can_hpp), "itineraries": itins, "departures": deps}
    sysdoc = await db.system_settings.find_one({"key": "system"})
    pct, amt = resolve_category_tax(pkg, (sysdoc or {}).get("settings", {}))
    result["package"]["tax_percent"] = pct
    result["package"]["tax_amount"] = amt
    if can_hpp:
        cost = await db.package_costs.find_one({"package_id": pid})
        result["costing"] = serialize(cost) if cost else None
    if can_manage:
        result["versions"] = [serialize(v) for v in await db.package_versions.find({"package_id": pid}).sort("version", -1).to_list(100)]
    return result


@api_router.put("/packages/{pid}")
async def update_package(pid: str, body: PackageModel, request: Request, user: dict = Depends(require_permission("product.manage"))):
    old = await db.packages.find_one({"_id": ObjectId(pid)})
    if not old:
        raise HTTPException(status_code=404, detail="Package not found")
    updates = body.model_dump()
    new_version = old.get("version", 1)
    if float(old.get("selling_price") or 0) != float(updates.get("selling_price") or 0):
        await db.package_versions.insert_one({
            "package_id": pid, "version": old.get("version", 1),
            "selling_price": old.get("selling_price"), "snapshot": serialize(dict(old)), "created_at": now_iso(),
        })
        new_version = old.get("version", 1) + 1
    updates["version"] = new_version
    await db.packages.update_one({"_id": ObjectId(pid)}, {"$set": updates})
    await log_audit(user, "package", "update_package", request, record_id=pid,
                    old={"selling_price": old.get("selling_price"), "version": old.get("version")},
                    new={"selling_price": updates.get("selling_price"), "version": new_version})
    return serialize(await db.packages.find_one({"_id": ObjectId(pid)}))


@api_router.patch("/packages/{pid}/status")
async def package_status(pid: str, body: StageUpdate, request: Request, user: dict = Depends(require_permission("product.manage"))):
    if body.stage not in PACKAGE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    old = await db.packages.find_one({"_id": ObjectId(pid)})
    if not old:
        raise HTTPException(status_code=404, detail="Package not found")
    await db.packages.update_one({"_id": ObjectId(pid)}, {"$set": {"status": body.stage}})
    await log_audit(user, "package", "update_status", request, record_id=pid,
                    old={"status": old.get("status")}, new={"status": body.stage})
    return {"status": body.stage}


@api_router.delete("/packages/{pid}")
async def archive_package(pid: str, request: Request, user: dict = Depends(require_permission("product.manage"))):
    await db.packages.update_one({"_id": ObjectId(pid)}, {"$set": {"status": "ARCHIVED"}})
    await log_audit(user, "package", "archive_package", request, record_id=pid)
    return {"message": "Package archived"}


# ---- Itineraries ----
@api_router.post("/packages/{pid}/itineraries")
async def add_itinerary(pid: str, body: ItineraryModel, user: dict = Depends(require_permission("product.manage"))):
    doc = body.model_dump()
    doc["package_id"] = pid
    doc["created_at"] = now_iso()
    res = await db.package_itineraries.insert_one(doc)
    return serialize(await db.package_itineraries.find_one({"_id": res.inserted_id}))


@api_router.put("/itineraries/{iid}")
async def update_itinerary(iid: str, body: ItineraryModel, user: dict = Depends(require_permission("product.manage"))):
    await db.package_itineraries.update_one({"_id": ObjectId(iid)}, {"$set": body.model_dump()})
    return serialize(await db.package_itineraries.find_one({"_id": ObjectId(iid)}))


@api_router.delete("/itineraries/{iid}")
async def delete_itinerary(iid: str, user: dict = Depends(require_permission("product.manage"))):
    await db.package_itineraries.delete_one({"_id": ObjectId(iid)})
    return {"message": "Deleted"}


@api_router.post("/itineraries/{iid}/duplicate")
async def duplicate_itinerary(iid: str, user: dict = Depends(require_permission("product.manage"))):
    src = await db.package_itineraries.find_one({"_id": ObjectId(iid)})
    if not src:
        raise HTTPException(status_code=404, detail="Not found")
    clone = {k: v for k, v in src.items() if k != "_id"}
    clone["day"] = int(clone.get("day") or 1) + 1
    clone["created_at"] = now_iso()
    res = await db.package_itineraries.insert_one(clone)
    return serialize(await db.package_itineraries.find_one({"_id": res.inserted_id}))


@api_router.put("/packages/{pid}/itineraries/reorder")
async def reorder_itineraries(pid: str, body: dict, user: dict = Depends(require_permission("product.manage"))):
    ids = body.get("ids", [])
    for i, iid in enumerate(ids):
        await db.package_itineraries.update_one({"_id": ObjectId(iid)}, {"$set": {"day": i + 1}})
    return {"message": "Reordered"}


# ---- Costing / HPP ----
@api_router.get("/packages/{pid}/costing")
async def get_costing(pid: str, user: dict = Depends(require_permission("hpp.view"))):
    pkg = await db.packages.find_one({"_id": ObjectId(pid)})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    cost = await db.package_costs.find_one({"package_id": pid})
    return {"package_id": pid, "selling_price": pkg.get("selling_price"),
            "costing": serialize(cost) if cost else {"components": {}, "total_cost": 0, "cost_per_pax": 0, "gross_profit": 0, "gross_margin": 0}}


@api_router.put("/packages/{pid}/costing")
async def save_costing(pid: str, body: CostingModel, request: Request, user: dict = Depends(require_permission("product.manage"))):
    pkg = await db.packages.find_one({"_id": ObjectId(pid)})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    comps = {k: float(body.components.get(k) or 0) for k in COST_COMPONENTS}
    total = sum(comps.values())
    selling = float(pkg.get("selling_price") or 0)
    gp = selling - total
    gm = round(gp / selling * 100, 2) if selling else 0
    doc = {"package_id": pid, "components": comps, "total_cost": total, "cost_per_pax": total,
           "gross_profit": gp, "gross_margin": gm, "updated_at": now_iso()}
    await db.package_costs.update_one({"package_id": pid}, {"$set": doc}, upsert=True)
    await db.packages.update_one({"_id": ObjectId(pid)}, {"$set": {"hpp": total, "total_cost": total,
                                 "cost_per_pax": total, "gross_profit": gp, "gross_margin": gm}})
    await log_audit(user, "hpp", "update_costing", request, record_id=pid, new={"total_cost": total, "gross_margin": gm})
    return serialize(doc)


# ---- Departures ----
@api_router.get("/packages/{pid}/departures")
async def package_departures(pid: str, user: dict = Depends(require_any_permission("product.view", "packages.view", "departures.view", "hpp.view"))):
    deps = [compute_departure(serialize(d)) for d in await db.departures.find({"package_id": pid}).sort("departure_date", 1).to_list(200)]
    return deps


@api_router.post("/packages/{pid}/departures")
async def add_departure(pid: str, body: DepartureModel, user: dict = Depends(require_permission("product.manage"))):
    doc = body.model_dump()
    doc["package_id"] = pid
    doc["created_at"] = now_iso()
    doc = compute_departure(doc)
    res = await db.departures.insert_one(doc)
    return compute_departure(serialize(await db.departures.find_one({"_id": res.inserted_id})))


@api_router.put("/departures/{did}")
async def update_departure(did: str, body: DepartureModel, user: dict = Depends(require_permission("product.manage"))):
    doc = body.model_dump()
    doc = compute_departure(doc)
    await db.departures.update_one({"_id": ObjectId(did)}, {"$set": doc})
    return compute_departure(serialize(await db.departures.find_one({"_id": ObjectId(did)})))


@api_router.delete("/departures/{did}")
async def delete_departure(did: str, user: dict = Depends(require_permission("product.manage"))):
    await db.departures.delete_one({"_id": ObjectId(did)})
    return {"message": "Deleted"}


@api_router.get("/departures")
async def all_departures(user: dict = Depends(require_any_permission("departures.view", "product.view", "packages.view", "hpp.view"))):
    up = await perms_of(user)
    can_manage = "product.manage" in up
    can_hpp = "hpp.view" in up
    pkg_query = {} if (can_manage or can_hpp) else {"status": "ACTIVE"}
    pkgs = {str(p["_id"]): p for p in await db.packages.find(pkg_query).to_list(1000)}
    deps = await db.departures.find({"package_id": {"$in": list(pkgs.keys())}}).sort("departure_date", 1).to_list(500)
    out = []
    for d in deps:
        d = compute_departure(serialize(d))
        p = pkgs.get(d["package_id"])
        if p:
            d["package_name"] = p.get("package_name")
            d["destination"] = p.get("destination")
            d["product_type"] = p.get("product_type")
        out.append(d)
    return out


@api_router.get("/packages/{pid}/price")
async def package_price(pid: str, pax: int = 1, hotel: Optional[str] = None,
                        user: dict = Depends(require_any_permission("product.view", "packages.view", "hpp.view"))):
    pkg = await db.packages.find_one({"_id": ObjectId(pid)})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    sub = pkg.get("sub_category")
    base = float(pkg.get("selling_price") or 0)
    if sub == "PRIVATE":
        match = None
        for t in pkg.get("pricing_tiers", []):
            hp_ok = (not hotel) or (t.get("hotel") == hotel)
            lo = int(t.get("min_pax") or 0)
            hi = int(t.get("max_pax") or 9999)
            if hp_ok and lo <= pax <= hi:
                match = t
                break
        return {"mode": "private", "pax": pax, "hotel": hotel,
                "price_per_pax": round(float(match["price"])) if match else round(base),
                "tiers": pkg.get("pricing_tiers", [])}
    if sub in ("OPEN_TRIP", "SEAT_IN_COACH"):
        minq = int(pkg.get("min_quota_pax") or 0)
        if minq and pax and pax < minq:
            eff = (minq * base) / pax
        else:
            eff = base
        return {"mode": "open_trip" if sub == "OPEN_TRIP" else "seat_in_coach", "pax": pax, "min_quota_pax": minq,
                "base_price": round(base), "price_per_pax": round(eff),
                "quota_met": (not minq) or pax >= minq}
    return {"mode": "fixed", "pax": pax, "price_per_pax": round(base)}





# ============================================================================
# PHASE 4 — QUOTATION, BOOKING, TRAVELER, DOCUMENT, INVOICE, PAYMENT
# ============================================================================
import uuid as _uuid
import requests as _requests
from fastapi import UploadFile, File, Form, Query, Header, Body
from fastapi.responses import Response, JSONResponse
import hmac as _hmac
import hashlib as _hashlib
import time as _time
from cryptography.fernet import Fernet
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

BOOKING_SOURCES = ["SALES", "AUTO SALES", "ADMIN", "AGENT", "PARTNER", "WEBSITE", "OTHER"]
DOCUMENT_TYPES = ["KTP", "PASSPORT", "PHOTO", "VISA", "MARRIAGE_BOOK", "OTHER"]
DOC_STATUSES = ["Missing", "Uploaded", "Verified", "Rejected"]

_STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
_STORAGE_URL = _STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
_EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
_APP_NAME = "safarcrm"
_storage_key = None


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = _requests.post(f"{_STORAGE_URL}/init", json={"emergent_key": _EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = _requests.put(f"{_STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = _requests.put(f"{_STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = _requests.get(f"{_STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = _requests.get(f"{_STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


async def get_settings_dict():
    doc = await db.system_settings.find_one({"key": "system"})
    return (doc or {}).get("settings", {})


# ============================================================================
# PHASE 6 — INTEGRATIONS (n8n webhooks + WhatsApp dispatched via n8n)
# ============================================================================
N8N_EVENTS = ["lead.created", "lead.updated", "quotation.created", "quotation.sent", "quotation.accepted",
              "booking.created", "booking.updated", "booking.cancelled", "invoice.created",
              "payment.created", "payment.recorded", "payment.confirmed", "payment.overdue",
              "payment.reminder", "departure.updated",
              "refund.calculated", "refund.submitted", "refund.approved", "refund.rejected",
              "refund.processing", "refund.partially_paid", "refund.completed"]

DEFAULT_WA_TEMPLATES = {
    "payment.reminder": "Assalamu'alaikum {customer_name} 🙏\n\nPengingat pembayaran untuk invoice *{invoice_number}*.\nSisa tagihan: *Rp {outstanding}*\nJatuh tempo: *{due_date}* ({stage}).\n\nMohon segera menyelesaikan pembayaran. Terima kasih.\n\n_{company_name}_",
    "booking.created": "Assalamu'alaikum {customer_name} 🙏\n\nAlhamdulillah booking Anda *{booking_number}* telah dikonfirmasi.\nTotal: *Rp {total}*.\n\nTim kami akan segera menghubungi Anda. Terima kasih.\n\n_{company_name}_",
    "payment.recorded": "Assalamu'alaikum {customer_name} 🙏\n\nPembayaran *Rp {amount}* untuk invoice *{invoice_number}* telah kami terima. Status: {invoice_status}.\nTerima kasih.\n\n_{company_name}_",
}


def _fmt_rp(v):
    try:
        return f"{int(round(float(v or 0))):,}".replace(",", ".")
    except Exception:
        return str(v)


def _render_template(tmpl, ctx):
    out = tmpl or ""
    for k, v in ctx.items():
        out = out.replace("{" + k + "}", str(v))
    return out


async def _cust_phone(customer_id):
    if not customer_id:
        return ""
    try:
        c = await db.customers.find_one({"_id": ObjectId(customer_id)})
    except Exception:
        c = None
    return (c or {}).get("whatsapp", "") if c else ""


async def _n8n_cfg():
    s = await get_settings_dict()
    return s.get("n8n", {}) or {}


async def _deliver_n8n(event, data):
    cfg = await _n8n_cfg()
    url = cfg.get("webhook_url")
    log = {"event": event, "data": data, "created_at": now_iso()}
    if not cfg.get("enabled") or not url:
        log.update({"ok": False, "skipped": True, "reason": "n8n disabled or webhook URL empty"})
        await db.n8n_logs.insert_one(log)
        return serialize(log)
    events = cfg.get("events") or {}
    if events.get(event) is False:
        log.update({"ok": False, "skipped": True, "reason": "event disabled"})
        await db.n8n_logs.insert_one(log)
        return serialize(log)
    payload = {"event": event, "timestamp": now_iso(), "data": data}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
        log.update({"ok": resp.status_code < 400, "status_code": resp.status_code, "response": resp.text[:400]})
    except Exception as e:
        log.update({"ok": False, "error": str(e)})
    await db.n8n_logs.insert_one(log)
    return serialize(log)


def trigger_n8n(event, data):
    try:
        asyncio.create_task(_deliver_n8n(event, data))
    except RuntimeError:
        pass


async def _compute_reminders(user):
    from datetime import date
    query = {} if user["role"] != "sales" else {"sales_pic_id": user["_id"]}
    invs = await db.invoices.find(query).to_list(3000)
    td = date.fromisoformat(today_str())
    out = []
    for inv in invs:
        await _recompute_invoice_status(str(inv["_id"]))
        inv = await db.invoices.find_one({"_id": inv["_id"]})
        if inv.get("status") in ("Paid",) or not inv.get("due_date"):
            continue
        try:
            dd = date.fromisoformat(inv["due_date"][:10])
        except Exception:
            continue
        days_to = (dd - td).days
        stage = None
        for h in (30, 14, 7, 3):
            if days_to == h:
                stage = f"H-{h}"
        if days_to == 0:
            stage = "DUE"
        if days_to < 0:
            stage = "OVERDUE"
        if stage:
            out.append({"invoice_id": str(inv["_id"]), "invoice_number": inv.get("invoice_number"),
                        "customer_id": inv.get("customer_id"), "customer_name": inv.get("customer_name"),
                        "due_date": inv.get("due_date"), "outstanding": inv.get("outstanding"),
                        "stage": stage, "days_to_due": days_to})
    return out



def compute_pax_price(pkg: dict, pax: int, hotel: Optional[str] = None) -> int:
    sub = pkg.get("sub_category")
    base = float(pkg.get("selling_price") or 0)
    if sub == "PRIVATE":
        for t in pkg.get("pricing_tiers", []):
            hp_ok = (not hotel) or (t.get("hotel") == hotel)
            lo = int(t.get("min_pax") or 0)
            hi = int(t.get("max_pax") or 9999)
            if hp_ok and lo <= pax <= hi:
                return round(float(t["price"]))
        return round(base)
    if sub in ("OPEN_TRIP", "SEAT_IN_COACH"):
        minq = int(pkg.get("min_quota_pax") or 0)
        if minq and pax and pax < minq:
            return round((minq * base) / pax)
        return round(base)
    return round(base)


def resolve_discount_status(pct: float, settings: dict):
    da = (settings or {}).get("discount_approval", {})
    smax = float(da.get("sales_max_percent", 5) or 0)
    amax = float(da.get("approval_max_percent", 10) or 0)
    if pct <= smax:
        return "APPROVED", "SALES"
    if pct <= amax:
        return "PENDING", "APPROVAL"
    return "PENDING", "SUPER_ADMIN"


async def next_number(prefix: str, collection, field: str) -> str:
    n = await collection.count_documents({}) + 1
    while await collection.find_one({field: f"{prefix}-{n:05d}"}):
        n += 1
    return f"{prefix}-{n:05d}"


async def user_from_token(token: str):
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if user:
            user["_id"] = str(user["_id"])
        return user
    except Exception:
        return None


# ---------- PDF helpers ----------
def _logo_flowable(company: dict):
    logo = (company or {}).get("logo") or ""
    try:
        if logo.startswith("data:"):
            import base64
            b = base64.b64decode(logo.split(",", 1)[1])
            return RLImage(BytesIO(b), width=40 * mm, height=15 * mm, kind="proportional")
        if logo.startswith("http"):
            r = _requests.get(logo, timeout=10)
            if r.status_code == 200:
                return RLImage(BytesIO(r.content), width=40 * mm, height=15 * mm, kind="proportional")
    except Exception:
        return None
    return None


def _money(v):
    try:
        return "Rp " + f"{int(round(float(v or 0))):,}".replace(",", ".")
    except Exception:
        return "Rp 0"


def build_document_pdf(kind: str, data: dict, company: dict, itineraries=None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading1"], textColor=colors.HexColor("#1d4ed8"), fontSize=18)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#475569"))
    el = []
    logo = _logo_flowable(company)
    header_left = []
    if logo:
        header_left.append(logo)
    header_left.append(Paragraph(f"<b>{company.get('company_name','Safar Travel')}</b>", styles["Normal"]))
    header_left.append(Paragraph(company.get("address", ""), small))
    header_left.append(Paragraph(f"{company.get('phone','')} · {company.get('email','')}", small))
    right = [Paragraph(f"<b>{kind}</b>", h),
             Paragraph(f"No: {data.get('number','')}", small),
             Paragraph(f"Tanggal: {(data.get('created_at') or '')[:10]}", small)]
    el.append(Table([[header_left, right]], colWidths=[95 * mm, 75 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))
    el.append(Spacer(1, 8 * mm))
    el.append(Table([[Paragraph(f"<b>Customer</b><br/>{data.get('customer_name','')}", small),
                      Paragraph(f"<b>Sales PIC</b><br/>{data.get('sales_pic_name','')}", small),
                      Paragraph(f"<b>Package</b><br/>{data.get('package_name','')} (v{data.get('package_version',1)})", small)]],
                     colWidths=[56 * mm, 56 * mm, 58 * mm]))
    el.append(Spacer(1, 6 * mm))
    rows = [["Deskripsi", "Qty", "Harga", "Jumlah"]]
    rows.append([f"{data.get('package_name','')} — {data.get('room_type','') or 'Standard'}", str(data.get("pax", 1)), _money(data.get("per_pax_price")), _money(data.get("gross"))])
    for a in (data.get("addons") or []):
        rows.append([f"Add-on: {a.get('name','')}", "1", _money(a.get("amount")), _money(a.get("amount"))])
    t = Table(rows, colWidths=[92 * mm, 18 * mm, 30 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    el.append(t)
    el.append(Spacer(1, 4 * mm))
    summ = [["Subtotal", _money(data.get("subtotal"))],
            [f"Discount ({data.get('discount_percent',0)}%)", "- " + _money(data.get("discount_amount"))],
            [f"Pajak ({data.get('tax_percent',0)}%)", _money(data.get("tax_amount"))],
            ["TOTAL", _money(data.get("total"))]]
    ts = Table(summ, colWidths=[140 * mm, 30 * mm])
    ts.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 10),
                            ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor("#1d4ed8")),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    el.append(ts)
    if itineraries:
        el.append(Spacer(1, 6 * mm))
        el.append(Paragraph("<b>Itinerary</b>", styles["Normal"]))
        for i, it in enumerate(itineraries):
            el.append(Paragraph(f"Day {it.get('day', i + 1)}: {it.get('location','')} — {it.get('activity','')}", small))
    if data.get("terms"):
        el.append(Spacer(1, 6 * mm))
        el.append(Paragraph("<b>Terms & Conditions</b>", styles["Normal"]))
        el.append(Paragraph(str(data.get("terms")), small))
    if kind == "INVOICE" and data.get("due_date"):
        el.append(Spacer(1, 4 * mm))
        el.append(Paragraph(f"<b>Jatuh Tempo:</b> {data.get('due_date')} · <b>Status:</b> {data.get('status','')}", small))
    doc.build(el)
    return buf.getvalue()


# ---------- Quotations ----------
class QuotationCreate(BaseModel):
    customer_id: str
    package_id: str
    departure_id: Optional[str] = None
    lead_id: Optional[str] = None
    pax: int = 1
    room_type: Optional[str] = ""
    addons: Optional[List[dict]] = []
    discount_type: Optional[str] = "PERCENT"
    discount_value: Optional[float] = 0
    discount_percent: Optional[float] = 0
    notes: Optional[str] = ""
    terms: Optional[str] = ""
    sales_pic_id: Optional[str] = None


async def _compute_quotation_amounts(pkg, pax, addons, discount_type, discount_value, settings):
    per_pax = compute_pax_price(pkg, pax, None)
    gross = per_pax * pax
    addon_total = sum(float(a.get("amount") or 0) for a in (addons or []))
    subtotal = gross + addon_total
    dtype = (discount_type or "PERCENT").upper()
    dval = float(discount_value or 0)
    if dtype == "AMOUNT":
        discount_amount = round(min(dval, subtotal))
        pct = round(discount_amount / subtotal * 100, 2) if subtotal else 0.0
    else:
        pct = dval
        discount_amount = round(subtotal * pct / 100)
    tax_pct, tax_unit = resolve_category_tax(pkg, settings)
    tax_amount = round(tax_unit * pax)
    total = subtotal - discount_amount + tax_amount
    return {"per_pax_price": per_pax, "base_price": float(pkg.get("selling_price") or 0), "gross": gross,
            "addon_total": addon_total, "subtotal": subtotal, "discount_type": dtype, "discount_value": dval,
            "discount_percent": pct, "discount_amount": discount_amount, "tax_percent": tax_pct,
            "tax_amount": tax_amount, "total": total}


@api_router.get("/quotations")
async def list_quotations(status: Optional[str] = None, user: dict = Depends(require_permission("quotation.view"))):
    query = owner_filter(user)
    if status and status != "all":
        query = {**query, "status": status}
    docs = await db.quotations.find(query).sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.post("/quotations")
async def create_quotation(body: QuotationCreate, request: Request, user: dict = Depends(require_permission("quotation.manage"))):
    pkg = await db.packages.find_one({"_id": ObjectId(body.package_id)})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    cust = await db.customers.find_one({"_id": ObjectId(body.customer_id)})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    settings = await get_settings_dict()
    amt = await _compute_quotation_amounts(pkg, body.pax, body.addons, body.discount_type, body.discount_value, settings)
    dstatus, dlevel = resolve_discount_status(amt["discount_percent"], settings)
    pic_id, pic_name, branch = await resolve_pic(user, body.sales_pic_id)
    number = await next_number((settings.get("numbering") or {}).get("quotation_prefix", "QT"), db.quotations, "quotation_number")
    doc = {"quotation_number": number, "customer_id": body.customer_id, "customer_name": cust["full_name"],
           "package_id": body.package_id, "package_name": pkg["package_name"], "package_version": pkg.get("version", 1),
           "departure_id": body.departure_id, "lead_id": body.lead_id, "pax": body.pax, "room_type": body.room_type,
           "addons": body.addons or [], **amt, "discount_status": dstatus, "discount_level": dlevel,
           "status": "DRAFT", "notes": body.notes, "terms": body.terms or pkg.get("terms", ""),
           "sales_pic_id": pic_id, "sales_pic_name": pic_name, "branch": branch,
           "converted_booking_id": None, "created_at": now_iso(), "created_by": user["name"]}
    res = await db.quotations.insert_one(doc)
    new = serialize(await db.quotations.find_one({"_id": res.inserted_id}))
    await log_audit(user, "quotation", "create_quotation", request, record_id=new["_id"], new={"number": number})
    trigger_n8n("quotation.created", {"id": new["_id"], "quotation_number": number,
        "customer_name": cust["full_name"], "customer_phone": cust.get("whatsapp", ""),
        "total": amt.get("total"), "sales_pic": pic_name})
    return new


@api_router.get("/quotations/{qid}")
async def get_quotation(qid: str, user: dict = Depends(require_permission("quotation.view"))):
    q = await db.quotations.find_one({"_id": ObjectId(qid)})
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if not can_access_record(user, q):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    return serialize(q)


@api_router.put("/quotations/{qid}")
async def update_quotation(qid: str, body: QuotationCreate, request: Request, user: dict = Depends(require_permission("quotation.manage"))):
    q = await db.quotations.find_one({"_id": ObjectId(qid)})
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if not can_access_record(user, q):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    if q.get("status") in ("ACCEPTED",) or q.get("converted_booking_id"):
        raise HTTPException(status_code=400, detail="Quotation already accepted/converted")
    pkg = await db.packages.find_one({"_id": ObjectId(body.package_id)})
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    settings = await get_settings_dict()
    amt = await _compute_quotation_amounts(pkg, body.pax, body.addons, body.discount_type, body.discount_value, settings)
    dstatus, dlevel = resolve_discount_status(amt["discount_percent"], settings)
    updates = {"package_id": body.package_id, "package_name": pkg["package_name"], "departure_id": body.departure_id,
               "pax": body.pax, "room_type": body.room_type, "addons": body.addons or [], **amt,
               "discount_status": dstatus, "discount_level": dlevel, "notes": body.notes, "terms": body.terms}
    await db.quotations.update_one({"_id": ObjectId(qid)}, {"$set": updates})
    await log_audit(user, "quotation", "update_quotation", request, record_id=qid)
    return serialize(await db.quotations.find_one({"_id": ObjectId(qid)}))


@api_router.patch("/quotations/{qid}/status")
async def set_quotation_status(qid: str, body: dict, request: Request, user: dict = Depends(require_permission("quotation.manage"))):
    q = await db.quotations.find_one({"_id": ObjectId(qid)})
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if not can_access_record(user, q):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    new_status = body.get("status")
    if new_status not in ("DRAFT", "SENT", "ACCEPTED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Invalid status")
    if new_status == "ACCEPTED":
        up = await perms_of(user)
        if "quotation.approve" not in up:
            raise HTTPException(status_code=403, detail="Hanya Super Admin yang dapat approve quotation")
        if q.get("discount_status") != "APPROVED":
            raise HTTPException(status_code=400, detail="Discount belum di-approve")
    await db.quotations.update_one({"_id": ObjectId(qid)}, {"$set": {"status": new_status}})
    await log_audit(user, "quotation", "status", request, record_id=qid, new={"status": new_status})
    if new_status in ("SENT", "ACCEPTED"):
        phone = await _cust_phone(q.get("customer_id"))
        trigger_n8n(f"quotation.{new_status.lower()}", {"id": qid, "quotation_number": q.get("quotation_number"),
            "customer_name": q.get("customer_name"), "customer_phone": phone, "total": q.get("total")})
    return serialize(await db.quotations.find_one({"_id": ObjectId(qid)}))


@api_router.patch("/quotations/{qid}/discount-approval")
async def approve_discount(qid: str, body: dict, request: Request, user: dict = Depends(require_permission("quotation.approve"))):
    q = await db.quotations.find_one({"_id": ObjectId(qid)})
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    action = body.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Invalid action")
    status = "APPROVED" if action == "approve" else "REJECTED"
    await db.quotations.update_one({"_id": ObjectId(qid)}, {"$set": {"discount_status": status, "discount_approved_by": user["name"]}})
    await log_audit(user, "quotation", "discount_approval", request, record_id=qid, new={"discount_status": status})
    return serialize(await db.quotations.find_one({"_id": ObjectId(qid)}))


@api_router.get("/quotations/{qid}/pdf")
async def quotation_pdf(qid: str, authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    q = await db.quotations.find_one({"_id": ObjectId(qid)})
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    company = await db.company_settings.find_one({"key": "company"}) or {}
    itins = await db.package_itineraries.find({"package_id": q.get("package_id")}).sort("day", 1).to_list(200)
    data = {**q, "number": q.get("quotation_number")}
    pdf = build_document_pdf("QUOTATION", data, company, itins)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={q.get('quotation_number')}.pdf"})


# ---------- Bookings ----------
@api_router.post("/quotations/{qid}/convert")
async def convert_to_booking(qid: str, body: dict, request: Request, user: dict = Depends(require_permission("booking.manage"))):
    q = await db.quotations.find_one({"_id": ObjectId(qid)})
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if not can_access_record(user, q):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    if q.get("status") != "ACCEPTED":
        raise HTTPException(status_code=400, detail="Quotation must be ACCEPTED first")
    if q.get("discount_status") != "APPROVED":
        raise HTTPException(status_code=400, detail="Discount belum di-approve")
    if q.get("converted_booking_id"):
        return serialize(await db.bookings.find_one({"_id": ObjectId(q["converted_booking_id"])}))
    pkg = await db.packages.find_one({"_id": ObjectId(q["package_id"])})
    settings = await get_settings_dict()
    number = await next_number((settings.get("numbering") or {}).get("booking_prefix", "BKG"), db.bookings, "booking_number")
    source = (body or {}).get("booking_source", "SALES")
    if source not in BOOKING_SOURCES:
        source = "SALES"
    booking = {"booking_number": number, "quotation_id": qid, "customer_id": q["customer_id"], "customer_name": q["customer_name"],
               "package_id": q["package_id"], "package_name": q["package_name"], "package_version": (pkg or {}).get("version", q.get("package_version", 1)),
               "departure_id": q.get("departure_id"), "pax": q["pax"], "room_type": q.get("room_type"), "addons": q.get("addons", []),
               "booking_source": source, "per_pax_price": q["per_pax_price"], "subtotal": q["subtotal"],
               "discount_percent": q["discount_percent"], "discount_amount": q["discount_amount"],
               "tax_percent": q.get("tax_percent", 0), "tax_amount": q["tax_amount"], "total": q["total"],
               "payment_schedule": [], "status": "CONFIRMED", "sales_pic_id": q["sales_pic_id"], "sales_pic_name": q["sales_pic_name"],
               "sales_type": "MANUAL", "sales_user_id": q["sales_pic_id"], "sales_name": q["sales_pic_name"],
               "branch": q.get("branch", ""), "created_at": now_iso(), "created_by": user["name"]}
    res = await db.bookings.insert_one(booking)
    bid = str(res.inserted_id)
    await db.quotations.update_one({"_id": ObjectId(qid)}, {"$set": {"converted_booking_id": bid, "status": "CONVERTED"}})
    await log_audit(user, "booking", "convert", request, record_id=bid, new={"number": number})
    phone = await _cust_phone(q.get("customer_id"))
    trigger_n8n("booking.created", {"id": bid, "booking_number": number, "customer_name": q["customer_name"],
        "customer_phone": phone, "total": q.get("total")})
    return serialize(await db.bookings.find_one({"_id": res.inserted_id}))


@api_router.get("/bookings")
async def list_bookings(status: Optional[str] = None, user: dict = Depends(require_permission("booking.view"))):
    query = owner_filter(user)
    if status and status != "all":
        query = {**query, "status": status}
    docs = await db.bookings.find(query).sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.get("/bookings/{bid}")
async def get_booking(bid: str, user: dict = Depends(require_permission("booking.view"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not can_access_record(user, b):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    travelers = [serialize(d) for d in await db.travelers.find({"booking_id": bid}).sort("created_at", 1).to_list(200)]
    tids = [t["_id"] for t in travelers]
    docs = [serialize(d) for d in await db.documents.find({"traveler_id": {"$in": tids}, "is_deleted": False}).to_list(1000)]
    invoices = [serialize(d) for d in await db.invoices.find({"booking_id": bid}).sort("created_at", -1).to_list(100)]
    return {"booking": serialize(b), "travelers": travelers, "documents": docs, "invoices": invoices}


@api_router.put("/bookings/{bid}/payment-schedule")
async def set_payment_schedule(bid: str, body: dict, request: Request, user: dict = Depends(require_permission("booking.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not can_access_record(user, b):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    schedule = body.get("schedule", [])
    await db.bookings.update_one({"_id": ObjectId(bid)}, {"$set": {"payment_schedule": schedule}})
    return serialize(await db.bookings.find_one({"_id": ObjectId(bid)}))


# ---------- Travelers ----------
class TravelerModel(BaseModel):
    full_name: str
    passport_name: Optional[str] = ""
    nik: Optional[str] = ""
    passport_number: Optional[str] = ""
    passport_expiry: Optional[str] = ""
    dob: Optional[str] = ""
    gender: Optional[str] = ""
    nationality: Optional[str] = "Indonesia"
    phone: Optional[str] = ""
    emergency_contact: Optional[str] = ""
    room_type: Optional[str] = ""
    special_request: Optional[str] = ""


@api_router.post("/bookings/{bid}/travelers")
async def add_traveler(bid: str, body: TravelerModel, request: Request, user: dict = Depends(require_permission("traveler.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not can_access_record(user, b):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    doc = {**body.model_dump(), "booking_id": bid, "created_at": now_iso(), "created_by": user["name"]}
    res = await db.travelers.insert_one(doc)
    await log_audit(user, "traveler", "add", request, record_id=str(res.inserted_id))
    return serialize(await db.travelers.find_one({"_id": res.inserted_id}))


@api_router.put("/travelers/{tid}")
async def update_traveler(tid: str, body: TravelerModel, user: dict = Depends(require_permission("traveler.manage"))):
    t = await db.travelers.find_one({"_id": ObjectId(tid)})
    if not t:
        raise HTTPException(status_code=404, detail="Traveler not found")
    await db.travelers.update_one({"_id": ObjectId(tid)}, {"$set": body.model_dump()})
    return serialize(await db.travelers.find_one({"_id": ObjectId(tid)}))


@api_router.delete("/travelers/{tid}")
async def delete_traveler(tid: str, user: dict = Depends(require_permission("traveler.manage"))):
    await db.travelers.delete_one({"_id": ObjectId(tid)})
    await db.documents.update_many({"traveler_id": tid}, {"$set": {"is_deleted": True}})
    return {"ok": True}


# ---------- Documents ----------
@api_router.post("/travelers/{tid}/documents")
async def upload_document(tid: str, doc_type: str = Form(...), file: UploadFile = File(...), user: dict = Depends(require_permission("document.manage"))):
    t = await db.travelers.find_one({"_id": ObjectId(tid)})
    if not t:
        raise HTTPException(status_code=404, detail="Traveler not found")
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    doc_id = str(_uuid.uuid4())
    path = f"{_APP_NAME}/documents/{tid}/{doc_id}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type or "application/octet-stream")
    rec = {"id": doc_id, "traveler_id": tid, "booking_id": t.get("booking_id"), "doc_type": doc_type,
           "storage_path": result["path"], "original_filename": file.filename, "content_type": file.content_type,
           "size": result.get("size", len(data)), "status": "Uploaded", "is_deleted": False,
           "uploaded_by": user["name"], "created_at": now_iso()}
    await db.documents.insert_one(rec)
    return {k: v for k, v in rec.items() if k != "_id"}


@api_router.patch("/documents/{doc_id}/status")
async def set_document_status(doc_id: str, body: dict, user: dict = Depends(require_permission("document.manage"))):
    status = body.get("status")
    if status not in DOC_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    await db.documents.update_one({"id": doc_id}, {"$set": {"status": status, "verified_by": user["name"]}})
    d = await db.documents.find_one({"id": doc_id})
    return {k: v for k, v in serialize(d).items() if k != "_id"} if d else {}


@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    d = await db.documents.find_one({"id": doc_id, "is_deleted": False})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    data, ct = get_object(d["storage_path"])
    return Response(content=data, media_type=d.get("content_type") or ct)


# ---------- Invoices ----------
async def _recompute_invoice_status(invoice_id: str):
    inv = await db.invoices.find_one({"_id": ObjectId(invoice_id)})
    if not inv:
        return None
    payments = await db.payments.find({"invoice_id": invoice_id}).to_list(500)
    paid = sum(float(p.get("amount") or 0) for p in payments)
    total = float(inv.get("total") or 0)
    today = today_str()
    if paid >= total and total > 0:
        status = "Paid"
    elif paid > 0:
        status = "Partially Paid"
    else:
        status = "Unpaid"
    if status in ("Unpaid", "Partially Paid") and inv.get("due_date") and inv["due_date"] < today:
        status = "Overdue"
    await db.invoices.update_one({"_id": ObjectId(invoice_id)}, {"$set": {"paid_amount": paid, "outstanding": max(total - paid, 0), "status": status}})
    return status


@api_router.post("/bookings/{bid}/invoice")
async def create_invoice(bid: str, body: dict, request: Request, user: dict = Depends(require_permission("invoice.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    settings = await get_settings_dict()
    number = await next_number((settings.get("numbering") or {}).get("invoice_prefix", "INV"), db.invoices, "invoice_number")
    due_date = (body or {}).get("due_date") or ""
    amount = float((body or {}).get("amount") if (body or {}).get("amount") is not None else b.get("subtotal", 0))
    doc = {"invoice_number": number, "booking_id": bid, "booking_number": b.get("booking_number"),
           "customer_id": b.get("customer_id"), "customer_name": b.get("customer_name"),
           "package_id": b.get("package_id"), "package_name": b.get("package_name"), "pax": b.get("pax"),
           "amount": amount, "discount_amount": b.get("discount_amount", 0), "discount_percent": b.get("discount_percent", 0),
           "tax_percent": b.get("tax_percent", 0), "tax_amount": b.get("tax_amount", 0), "total": b.get("total", amount),
           "paid_amount": 0, "outstanding": b.get("total", amount), "due_date": due_date, "status": "Unpaid",
           "sales_pic_id": b.get("sales_pic_id"), "sales_pic_name": b.get("sales_pic_name"), "branch": b.get("branch", ""),
           "terms": (await db.packages.find_one({"_id": ObjectId(b["package_id"])}) or {}).get("terms", ""),
           "created_at": now_iso(), "created_by": user["name"]}
    res = await db.invoices.insert_one(doc)
    await _recompute_invoice_status(str(res.inserted_id))
    await log_audit(user, "invoice", "create", request, record_id=str(res.inserted_id), new={"number": number})
    phone = await _cust_phone(b.get("customer_id"))
    trigger_n8n("invoice.created", {"id": str(res.inserted_id), "invoice_number": number,
        "customer_name": b.get("customer_name"), "customer_phone": phone,
        "total": doc.get("total"), "due_date": due_date})
    return serialize(await db.invoices.find_one({"_id": res.inserted_id}))


@api_router.get("/invoices")
async def list_invoices(status: Optional[str] = None, user: dict = Depends(require_permission("invoice.view"))):
    query = {} if user["role"] != "sales" else {"sales_pic_id": user["_id"]}
    if status and status != "all":
        query["status"] = status
    docs = await db.invoices.find(query).sort("created_at", -1).to_list(2000)
    for d in docs:
        await _recompute_invoice_status(str(d["_id"]))
    docs = await db.invoices.find(query).sort("created_at", -1).to_list(2000)
    return [serialize(d) for d in docs]


@api_router.get("/invoices/{iid}")
async def get_invoice(iid: str, user: dict = Depends(require_permission("invoice.view"))):
    await _recompute_invoice_status(iid)
    inv = await db.invoices.find_one({"_id": ObjectId(iid)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    payments = [serialize(p) for p in await db.payments.find({"invoice_id": iid}).sort("created_at", -1).to_list(500)]
    return {"invoice": serialize(inv), "payments": payments}


@api_router.get("/invoices/{iid}/pdf")
async def invoice_pdf(iid: str, authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    inv = await db.invoices.find_one({"_id": ObjectId(iid)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    company = await db.company_settings.find_one({"key": "company"}) or {}
    data = {**inv, "number": inv.get("invoice_number"), "subtotal": inv.get("amount"),
            "per_pax_price": round(float(inv.get("amount") or 0) / max(int(inv.get("pax") or 1), 1)), "gross": inv.get("amount"), "addons": []}
    pdf = build_document_pdf("INVOICE", data, company)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={inv.get('invoice_number')}.pdf"})


# ---------- Payments ----------
class PaymentCreate(BaseModel):
    payment_date: str
    amount: float
    payment_method: Optional[str] = ""
    bank: Optional[str] = ""
    reference_number: Optional[str] = ""
    notes: Optional[str] = ""
    attachment_url: Optional[str] = ""


@api_router.post("/invoices/{iid}/payments")
async def record_payment(iid: str, body: PaymentCreate, request: Request, user: dict = Depends(require_permission("payment.manage"))):
    inv = await db.invoices.find_one({"_id": ObjectId(iid)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    doc = {**body.model_dump(), "invoice_id": iid, "invoice_number": inv.get("invoice_number"),
           "booking_id": inv.get("booking_id"), "recorded_by": user["name"], "created_at": now_iso()}
    res = await db.payments.insert_one(doc)
    status = await _recompute_invoice_status(iid)
    await log_audit(user, "payment", "record", request, record_id=str(res.inserted_id), new={"amount": body.amount, "invoice_status": status})
    return serialize(await db.payments.find_one({"_id": res.inserted_id}))


# ---------- Receivable & Reminders ----------
def _aging_bucket(due_date: str, today: str):
    if not due_date:
        return "Current"
    from datetime import date
    try:
        dd = date.fromisoformat(due_date[:10])
        td = date.fromisoformat(today)
    except Exception:
        return "Current"
    days = (td - dd).days
    if days <= 0:
        return "Current"
    if days <= 30:
        return "1-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


@api_router.get("/receivables")
async def receivables(user: dict = Depends(require_permission("receivable.view"))):
    query = {} if user["role"] != "sales" else {"sales_pic_id": user["_id"]}
    invs = await db.invoices.find(query).to_list(3000)
    today = today_str()
    rows = []
    aging = {"Current": 0, "1-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    total_invoice = total_paid = 0.0
    for inv in invs:
        await _recompute_invoice_status(str(inv["_id"]))
        inv = await db.invoices.find_one({"_id": inv["_id"]})
        outstanding = float(inv.get("outstanding") or 0)
        total_invoice += float(inv.get("total") or 0)
        total_paid += float(inv.get("paid_amount") or 0)
        if outstanding > 0:
            bucket = _aging_bucket(inv.get("due_date"), today)
            aging[bucket] += outstanding
            rows.append({"invoice_number": inv.get("invoice_number"), "customer_name": inv.get("customer_name"),
                         "total": inv.get("total"), "paid_amount": inv.get("paid_amount"), "outstanding": outstanding,
                         "due_date": inv.get("due_date"), "status": inv.get("status"), "aging": bucket,
                         "invoice_id": str(inv["_id"])})
    return {"rows": rows, "aging": aging, "total_invoice": total_invoice, "total_payment": total_paid,
            "total_outstanding": max(total_invoice - total_paid, 0)}


@api_router.get("/payment-reminders")
async def payment_reminders(user: dict = Depends(require_permission("receivable.view"))):
    out = await _compute_reminders(user)
    return {"reminders": out, "generated_at": now_iso()}


@api_router.get("/booking-config")
async def booking_config(user: dict = Depends(get_current_user)):
    settings = await get_settings_dict()
    return {"booking_sources": settings.get("booking_sources", BOOKING_SOURCES),
            "document_types": DOCUMENT_TYPES, "doc_statuses": DOC_STATUSES,
            "discount_approval": settings.get("discount_approval", {"sales_max_percent": 5, "approval_max_percent": 10})}


# ============================================================================
# PHASE 5 — ACCOUNTING, HPP & TAX ENGINE
# ============================================================================
import csv as _csv
from io import StringIO
from openpyxl import Workbook

EXPENSE_CATEGORIES = ["Flight", "Hotel", "Visa", "Transport", "Guide", "Marketing", "Commission", "Operational", "Refund", "Other"]
TAX_TYPES = ["PPN", "PPh", "OTHER"]
TAX_TREATMENTS = ["NON_TAXABLE", "PPN_TERTENTU", "PPN_STANDARD", "CUSTOM_TAX", "UMRAH_MURNI", "UMRAH_PLUS"]


def _in_range(dt, frm, to):
    d = (dt or "")[:10]
    if frm and d < frm:
        return False
    if to and d > to:
        return False
    return True


# ---------- Tax Master ----------
class TaxMasterModel(BaseModel):
    tax_code: str
    tax_name: str
    tax_type: str = "PPN"
    rate: float = 0
    tax_base: Optional[str] = "SELLING_PRICE"
    effective_from: str = ""
    effective_until: Optional[str] = ""
    treatment: str = "PPN_STANDARD"
    tax_account: Optional[str] = ""
    description: Optional[str] = ""
    active: bool = True


@api_router.get("/tax-masters")
async def list_tax_masters(user: dict = Depends(require_permission("tax.view"))):
    docs = await db.tax_masters.find({}).sort("effective_from", -1).to_list(500)
    return [serialize(d) for d in docs]


@api_router.post("/tax-masters")
async def create_tax_master(body: TaxMasterModel, request: Request, user: dict = Depends(require_permission("tax.manage"))):
    doc = {**body.model_dump(), "created_at": now_iso(), "created_by": user["name"]}
    res = await db.tax_masters.insert_one(doc)
    await log_audit(user, "tax", "create_tax_master", request, record_id=str(res.inserted_id), new=body.model_dump())
    return serialize(await db.tax_masters.find_one({"_id": res.inserted_id}))


@api_router.put("/tax-masters/{tid}")
async def update_tax_master(tid: str, body: TaxMasterModel, request: Request, user: dict = Depends(require_permission("tax.manage"))):
    old = await db.tax_masters.find_one({"_id": ObjectId(tid)})
    if not old:
        raise HTTPException(status_code=404, detail="Tax master not found")
    await db.tax_masters.update_one({"_id": ObjectId(tid)}, {"$set": body.model_dump()})
    await log_audit(user, "tax", "update_tax_master", request, record_id=tid, old=serialize(old), new=body.model_dump())
    return serialize(await db.tax_masters.find_one({"_id": ObjectId(tid)}))


@api_router.delete("/tax-masters/{tid}")
async def delete_tax_master(tid: str, request: Request, user: dict = Depends(require_permission("tax.manage"))):
    await db.tax_masters.update_one({"_id": ObjectId(tid)}, {"$set": {"active": False}})
    await log_audit(user, "tax", "deactivate_tax_master", request, record_id=tid)
    return {"ok": True}


@api_router.get("/tax-config")
async def tax_config(user: dict = Depends(require_permission("tax.view"))):
    return {"tax_types": TAX_TYPES, "treatments": TAX_TREATMENTS, "tax_bases": ["SELLING_PRICE", "TOUR_PORTION", "DPP", "CUSTOM"]}


# ---------- Expense ----------
class ExpenseModel(BaseModel):
    category: str
    amount: float
    date: str = ""
    description: Optional[str] = ""
    vendor: Optional[str] = ""
    package_id: Optional[str] = None
    departure_id: Optional[str] = None
    booking_id: Optional[str] = None
    notes: Optional[str] = ""


@api_router.get("/expenses")
async def list_expenses(category: Optional[str] = None, user: dict = Depends(require_permission("expense.view"))):
    q = {} if not category or category == "all" else {"category": category}
    docs = await db.expenses.find(q).sort("date", -1).to_list(2000)
    return [serialize(d) for d in docs]


@api_router.post("/expenses")
async def create_expense(body: ExpenseModel, request: Request, user: dict = Depends(require_permission("expense.manage"))):
    doc = {**body.model_dump(), "date": body.date or today_str(), "created_at": now_iso(), "created_by": user["name"]}
    res = await db.expenses.insert_one(doc)
    await log_audit(user, "expense", "create", request, record_id=str(res.inserted_id), new={"category": body.category, "amount": body.amount})
    return serialize(await db.expenses.find_one({"_id": res.inserted_id}))


@api_router.put("/expenses/{eid}")
async def update_expense(eid: str, body: ExpenseModel, user: dict = Depends(require_permission("expense.manage"))):
    await db.expenses.update_one({"_id": ObjectId(eid)}, {"$set": body.model_dump()})
    return serialize(await db.expenses.find_one({"_id": ObjectId(eid)}))


@api_router.delete("/expenses/{eid}")
async def delete_expense(eid: str, user: dict = Depends(require_permission("expense.manage"))):
    await db.expenses.delete_one({"_id": ObjectId(eid)})
    return {"ok": True}


# ---------- Refund ----------
class RefundModel(BaseModel):
    booking_id: Optional[str] = None
    invoice_id: Optional[str] = None
    customer_name: Optional[str] = ""
    amount: float
    reason: Optional[str] = ""
    method: Optional[str] = ""
    date: str = ""
    status: Optional[str] = "PENDING"


@api_router.get("/refunds")
async def list_refunds(user: dict = Depends(require_permission("refund.manage"))):
    docs = await db.refunds.find({}).sort("date", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.post("/refunds")
async def create_refund(body: RefundModel, request: Request, user: dict = Depends(require_permission("refund.manage"))):
    doc = {**body.model_dump(), "date": body.date or today_str(), "created_at": now_iso(), "created_by": user["name"]}
    res = await db.refunds.insert_one(doc)
    await log_audit(user, "refund", "create", request, record_id=str(res.inserted_id), new={"amount": body.amount})
    return serialize(await db.refunds.find_one({"_id": res.inserted_id}))


@api_router.patch("/refunds/{rid}/status")
async def refund_status(rid: str, body: dict, request: Request, user: dict = Depends(require_permission("refund.manage"))):
    await db.refunds.update_one({"_id": ObjectId(rid)}, {"$set": {"status": body.get("status", "PENDING")}})
    return serialize(await db.refunds.find_one({"_id": ObjectId(rid)}))


# ---------- Report builders ----------
async def _invoices_in(frm, to):
    docs = await db.invoices.find({}).to_list(5000)
    for d in docs:
        await _recompute_invoice_status(str(d["_id"]))
    docs = await db.invoices.find({}).to_list(5000)
    return [d for d in docs if _in_range(d.get("created_at"), frm, to)]


async def report_revenue(frm=None, to=None):
    invs = await _invoices_in(frm, to)
    gross = sum(float(i.get("amount") or 0) for i in invs)
    discount = sum(float(i.get("discount_amount") or 0) for i in invs)
    tax = sum(float(i.get("tax_amount") or 0) for i in invs)
    net = gross - discount
    revenue = sum(float(i.get("total") or 0) for i in invs)
    exps = [e for e in await db.expenses.find({}).to_list(5000) if _in_range(e.get("date"), frm, to)]
    cost = sum(float(e.get("amount") or 0) for e in exps)
    gp = revenue - cost
    gm = round(gp / revenue * 100, 2) if revenue else 0
    return {"title": "Revenue Report", "columns": ["Metric", "Amount"],
            "rows": [["Gross Sales", gross], ["Discount", discount], ["Net Sales", net], ["Tax", tax],
                     ["Revenue", revenue], ["Cost (Expenses)", cost], ["Gross Profit", gp], ["Gross Margin %", gm]],
            "summary": {"gross_sales": gross, "discount": discount, "net_sales": net, "tax": tax,
                        "revenue": revenue, "cost": cost, "gross_profit": gp, "gross_margin": gm}}


async def report_tax(frm=None, to=None):
    invs = await _invoices_in(frm, to)
    taxable = sum(float(i.get("amount") or 0) for i in invs if float(i.get("tax_amount") or 0) > 0)
    non_taxable = sum(float(i.get("amount") or 0) for i in invs if float(i.get("tax_amount") or 0) <= 0)
    dpp = taxable
    tax_amount = sum(float(i.get("tax_amount") or 0) for i in invs)
    by_pkg = {}
    for i in invs:
        k = i.get("package_name") or "-"
        b = by_pkg.setdefault(k, {"dpp": 0, "tax": 0})
        b["dpp"] += float(i.get("amount") or 0) if float(i.get("tax_amount") or 0) > 0 else 0
        b["tax"] += float(i.get("tax_amount") or 0)
    by_period = {}
    for i in invs:
        k = (i.get("created_at") or "")[:7]
        by_period[k] = by_period.get(k, 0) + float(i.get("tax_amount") or 0)
    rows = [[i.get("invoice_number"), i.get("customer_name"), i.get("package_name"),
             float(i.get("amount") or 0), float(i.get("tax_percent") or 0), float(i.get("tax_amount") or 0)] for i in invs]
    return {"title": "Tax Report", "columns": ["Invoice", "Customer", "Package", "DPP", "Rate %", "Tax"],
            "rows": rows,
            "summary": {"taxable_sales": taxable, "non_taxable_sales": non_taxable, "dpp": dpp, "tax_amount": tax_amount},
            "by_package": [{"package": k, **v} for k, v in by_pkg.items()],
            "by_period": [{"period": k, "tax": v} for k, v in sorted(by_period.items())]}


async def report_expense(frm=None, to=None):
    exps = [e for e in await db.expenses.find({}).sort("date", -1).to_list(5000) if _in_range(e.get("date"), frm, to)]
    by_cat = {}
    for e in exps:
        by_cat[e.get("category")] = by_cat.get(e.get("category"), 0) + float(e.get("amount") or 0)
    rows = [[e.get("date"), e.get("category"), e.get("description"), e.get("vendor"), float(e.get("amount") or 0)] for e in exps]
    return {"title": "Expense Report", "columns": ["Date", "Category", "Description", "Vendor", "Amount"], "rows": rows,
            "summary": {"total_expense": sum(float(e.get("amount") or 0) for e in exps)},
            "by_category": [{"category": k, "amount": v} for k, v in by_cat.items()]}


async def report_profitability(frm=None, to=None):
    invs = await _invoices_in(frm, to)
    exps = [e for e in await db.expenses.find({}).to_list(5000) if _in_range(e.get("date"), frm, to)]
    exp_by_pkg = {}
    for e in exps:
        if e.get("package_id"):
            exp_by_pkg[e["package_id"]] = exp_by_pkg.get(e["package_id"], 0) + float(e.get("amount") or 0)
    by_pkg = {}
    for i in invs:
        pid = i.get("package_id")
        b = by_pkg.setdefault(pid, {"name": i.get("package_name"), "revenue": 0})
        b["revenue"] += float(i.get("total") or 0)
    rows = []
    for pid, b in by_pkg.items():
        cost = exp_by_pkg.get(pid, 0)
        gp = b["revenue"] - cost
        gm = round(gp / b["revenue"] * 100, 2) if b["revenue"] else 0
        rows.append([b["name"], b["revenue"], cost, gp, gm])
    return {"title": "Profitability Report", "columns": ["Package", "Revenue", "Cost", "Gross Profit", "Margin %"], "rows": rows}


async def report_sales(frm=None, to=None):
    bks = [b for b in await db.bookings.find({}).sort("created_at", -1).to_list(5000) if _in_range(b.get("created_at"), frm, to)]
    rows = [[b.get("booking_number"), b.get("customer_name"), b.get("package_name"), b.get("pax"),
             b.get("sales_pic_name"), b.get("booking_source"), float(b.get("total") or 0)] for b in bks]
    return {"title": "Sales Report", "columns": ["Booking", "Customer", "Package", "Pax", "Sales", "Source", "Total"], "rows": rows,
            "summary": {"total_bookings": len(bks), "total_value": sum(float(b.get("total") or 0) for b in bks)}}


async def report_receivable_r(frm=None, to=None):
    invs = await _invoices_in(frm, to)
    rows = []
    total_out = 0
    for i in invs:
        out = float(i.get("outstanding") or 0)
        if out > 0:
            total_out += out
            rows.append([i.get("invoice_number"), i.get("customer_name"), float(i.get("total") or 0),
                         float(i.get("paid_amount") or 0), out, i.get("due_date"), i.get("status")])
    return {"title": "Receivable Report", "columns": ["Invoice", "Customer", "Total", "Paid", "Outstanding", "Due", "Status"],
            "rows": rows, "summary": {"total_outstanding": total_out}}


async def report_hpp_r(frm=None, to=None):
    pkgs = await db.packages.find({}).to_list(2000)
    rows = []
    for p in pkgs:
        rows.append([p.get("package_name"), norm_type(p.get("product_type")), float(p.get("total_cost") or 0),
                     float(p.get("cost_per_pax") or 0), float(p.get("selling_price") or 0),
                     float(p.get("gross_profit") or 0), float(p.get("gross_margin") or 0)])
    deps = await db.departures.find({}).to_list(2000)
    dep_rows = [[d.get("departure_code") or str(d.get("_id")), d.get("package_name", ""), d.get("date", ""),
                 float(d.get("total_cost") or 0), float(d.get("cost_per_pax") or 0)] for d in deps]
    return {"title": "HPP Report", "columns": ["Package", "Type", "Total Cost", "Cost/Pax", "Selling Price", "Gross Profit", "Margin %"],
            "rows": rows, "by_departure": dep_rows}


REPORTS = {"revenue": (report_revenue, "reports.view"), "tax": (report_tax, "tax.view"),
           "expense": (report_expense, "expense.view"), "profitability": (report_profitability, "reports.view"),
           "sales": (report_sales, "reports.view"), "receivable": (report_receivable_r, "receivable.view"),
           "hpp": (report_hpp_r, "hpp.view")}


@api_router.get("/reports/{name}")
async def get_report(name: str, frm: Optional[str] = None, to: Optional[str] = None, user: dict = Depends(get_current_user)):
    if name not in REPORTS:
        raise HTTPException(status_code=404, detail="Report not found")
    fn, perm = REPORTS[name]
    up = await perms_of(user)
    if perm not in up:
        raise HTTPException(status_code=403, detail="403 Forbidden")
    return await fn(frm, to)


def _fmt_cell(v):
    return v


def export_response(fmt, title, columns, rows):
    fname = title.replace(" ", "_")
    if fmt == "csv":
        sio = StringIO()
        w = _csv.writer(sio)
        w.writerow(columns)
        for r in rows:
            w.writerow(r)
        return Response(content=sio.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={fname}.csv"})
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = title[:31]
        ws.append(columns)
        for r in rows:
            ws.append([(_fmt_cell(c)) for c in r])
        bio = BytesIO()
        wb.save(bio)
        return Response(content=bio.getvalue(),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename={fname}.xlsx"})
    # pdf
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    el = [Paragraph(f"<b>{title}</b>", styles["Heading2"]), Spacer(1, 6 * mm)]
    data = [columns] + [[str(c) for c in r] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")])]))
    el.append(t)
    doc.build(el)
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={fname}.pdf"})


@api_router.get("/reports/{name}/export")
async def export_report(name: str, format: str = "xlsx", frm: Optional[str] = None, to: Optional[str] = None,
                        authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if name not in REPORTS:
        raise HTTPException(status_code=404, detail="Report not found")
    fn, perm = REPORTS[name]
    up = await get_user_permissions(user)
    if perm not in up and "reports.export" not in up:
        raise HTTPException(status_code=403, detail="403 Forbidden")
    rep = await fn(frm, to)
    fmt = format if format in ("csv", "xlsx", "pdf") else "xlsx"
    return export_response(fmt, rep["title"], rep["columns"], rep["rows"])


# ---------- Commission & n8n settings (Accounting must be 403) ----------
@api_router.get("/commission-settings")
async def get_commission_settings(user: dict = Depends(require_permission("commission.manage"))):
    s = await get_settings_dict()
    return s.get("commission", {"default_percent": 2.5})


@api_router.put("/commission-settings")
async def put_commission_settings(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    if "default_percent" in (body or {}):
        await db.system_settings.update_one({"key": "system"}, {"$set": {"settings.commission.default_percent": body.get("default_percent")}})
    if "auto_sales_commission" in (body or {}):
        await db.system_settings.update_one({"key": "system"}, {"$set": {"settings.commission.auto_sales_commission": bool(body.get("auto_sales_commission"))}})
    await log_audit(user, "settings", "update_commission", request, new=body)
    s = await get_settings_dict()
    return s.get("commission", {})


@api_router.get("/integrations/n8n")
async def get_n8n_settings(user: dict = Depends(require_permission("settings.manage"))):
    s = await get_settings_dict()
    n = s.get("n8n", {}) or {}
    return {"webhook_url": n.get("webhook_url", ""), "enabled": bool(n.get("enabled")),
            "events": {**{e: True for e in N8N_EVENTS}, **(n.get("events") or {})},
            "whatsapp_templates": {**DEFAULT_WA_TEMPLATES, **(n.get("whatsapp_templates") or {})}}


@api_router.put("/integrations/n8n")
async def put_n8n_settings(body: dict, request: Request, user: dict = Depends(require_permission("settings.manage"))):
    await db.system_settings.update_one({"key": "system"}, {"$set": {"settings.n8n": body}})
    await log_audit(user, "settings", "update_n8n", request, new=body)
    return body


@api_router.get("/integrations/n8n/events")
async def n8n_events_catalog(user: dict = Depends(require_permission("settings.manage"))):
    return {"events": N8N_EVENTS, "default_templates": DEFAULT_WA_TEMPLATES}


@api_router.post("/integrations/n8n/test")
async def n8n_test(body: dict, request: Request, user: dict = Depends(require_permission("settings.manage"))):
    event = (body or {}).get("event") or "test.ping"
    result = await _deliver_n8n(event, {"message": "Test event dari Safar Travel CRM", "triggered_by": user["name"], "sample": True})
    await log_audit(user, "integration", "n8n_test", request, new={"event": event, "ok": result.get("ok")})
    return result


@api_router.get("/integrations/n8n/logs")
async def n8n_logs(user: dict = Depends(require_permission("settings.manage"))):
    docs = await db.n8n_logs.find().sort("created_at", -1).to_list(100)
    return [serialize(d) for d in docs]


@api_router.post("/payment-reminders/dispatch")
async def dispatch_payment_reminders(request: Request, user: dict = Depends(require_permission("receivable.view"))):
    cfg = await _n8n_cfg()
    reminders = await _compute_reminders(user)
    company = await db.company_settings.find_one({"key": "company"}) or {}
    tmpl = (cfg.get("whatsapp_templates") or {}).get("payment.reminder") or DEFAULT_WA_TEMPLATES["payment.reminder"]
    sent = 0
    for r in reminders:
        phone = await _cust_phone(r.get("customer_id"))
        ctx = {"customer_name": r.get("customer_name", ""), "invoice_number": r.get("invoice_number", ""),
               "outstanding": _fmt_rp(r.get("outstanding")), "due_date": (r.get("due_date") or "")[:10],
               "stage": r.get("stage", ""), "company_name": company.get("company_name", "Safar Travel")}
        message = _render_template(tmpl, ctx)
        res = await _deliver_n8n("payment.reminder", {**r, "customer_phone": phone, "message": message, "channel": "whatsapp"})
        if res.get("ok"):
            sent += 1
    await log_audit(user, "integration", "dispatch_reminders", request, new={"count": len(reminders), "sent": sent})
    return {"total": len(reminders), "dispatched": sent,
            "n8n_enabled": bool(cfg.get("enabled") and cfg.get("webhook_url"))}


# ============================================================================
# PHASE 6 — SALES COMMISSION & MONTHLY CLOSING
# ============================================================================
COMMISSION_BASES = ["BOOKED", "CONFIRMED", "PAID", "COMPLETED"]
CLOSING_STATUSES = ["OPEN", "CALCULATING", "REVIEW", "APPROVED", "CLOSED", "PAID"]
COMMISSION_PRODUCT_TYPES = ["ALL", "UMROH", "TOUR", "UMROH_PLUS"]


class CommissionTier(BaseModel):
    min_pax: int = 0
    max_pax: Optional[int] = None
    rate_per_pax: float = 0


class CommissionScheme(BaseModel):
    scheme_name: str
    product_type: str = "ALL"
    package_id: Optional[str] = ""
    effective_from: Optional[str] = ""
    effective_until: Optional[str] = ""
    calculation_basis: str = "PAID"
    tiers: List[dict] = []
    auto_sales: bool = False
    status: str = "ACTIVE"


def _period_bounds(period: str):
    import calendar
    y, m = int(period[:4]), int(period[5:7])
    last = calendar.monthrange(y, m)[1]
    return f"{period}-01", f"{period}-{last:02d}"


def _tier_for(tiers, pax):
    best = None
    for t in sorted(tiers or [], key=lambda x: int(x.get("min_pax", 0) or 0)):
        mn = int(t.get("min_pax", 0) or 0)
        mx = t.get("max_pax")
        mx = int(mx) if mx not in (None, "", 0, "0") else None
        if pax >= mn and (mx is None or pax <= mx):
            best = t
    if best is None:
        return 0.0, "-"
    mx = best.get("max_pax")
    label = f"{best.get('min_pax', 0)}-{mx if mx not in (None, '', 0, '0') else '∞'}"
    return float(best.get("rate_per_pax", 0) or 0), label


def _scheme_matches(s, is_auto, product_type, package_id):
    if bool(s.get("auto_sales")) != is_auto:
        return False
    pt = s.get("product_type", "ALL")
    if pt not in ("ALL", "", None) and pt != product_type:
        return False
    pkg = s.get("package_id")
    if pkg and pkg != package_id:
        return False
    return True


def _scheme_rank(s):
    r = 0
    if s.get("package_id"):
        r += 2
    if s.get("product_type") not in ("ALL", "", None):
        r += 1
    return r


async def _booking_eligibility(booking, basis):
    status = booking.get("status")
    if status == "CANCELLED":
        return False, None
    bid = str(booking["_id"])
    if basis == "BOOKED":
        return True, (booking.get("created_at") or "")[:10]
    if basis == "CONFIRMED":
        if status in ("CONFIRMED", "COMPLETED"):
            return True, (booking.get("confirmed_at") or booking.get("created_at") or "")[:10]
        return False, None
    if basis == "COMPLETED":
        if status == "COMPLETED":
            return True, (booking.get("completed_at") or booking.get("departure_date") or booking.get("created_at") or "")[:10]
        return False, None
    if basis == "PAID":
        invs = await db.invoices.find({"booking_id": bid}).to_list(50)
        if not invs:
            return False, None
        paid_dates, all_paid = [], True
        for inv in invs:
            await _recompute_invoice_status(str(inv["_id"]))
            inv = await db.invoices.find_one({"_id": inv["_id"]})
            if inv.get("status") != "Paid":
                all_paid = False
            for p in await db.payments.find({"invoice_id": str(inv["_id"])}).to_list(200):
                if p.get("payment_date"):
                    paid_dates.append(p["payment_date"][:10])
        if not all_paid or not paid_dates:
            return False, None
        return True, max(paid_dates)
    return False, None


async def _compute_period(period, only_sales_id=None):
    settings = await get_settings_dict()
    auto_on = bool((settings.get("commission") or {}).get("auto_sales_commission", False))
    schemes = [serialize(s) for s in await db.commission_schemes.find({"status": "ACTIVE"}).to_list(500)]
    start, end = _period_bounds(period)
    claimed = set()
    async for it in db.commission_items.find({"period": {"$ne": period}}):
        claimed.add((it.get("booking_id"), it.get("traveler_id")))
    q = {} if not only_sales_id else {"sales_pic_id": only_sales_id}
    bookings = await db.bookings.find(q).to_list(5000)
    sales_map = {}
    for b in bookings:
        if b.get("status") == "CANCELLED":
            continue
        bid = str(b["_id"])
        is_auto = (b.get("booking_source") == "AUTO SALES")
        if is_auto and not auto_on:
            continue
        pkg = await db.packages.find_one({"_id": ObjectId(b["package_id"])}) if b.get("package_id") else None
        product_type = norm_type((pkg or {}).get("product_type") or "")
        cands = [s for s in schemes if _scheme_matches(s, is_auto, product_type, b.get("package_id"))]
        cands.sort(key=lambda s: (_scheme_rank(s), s.get("effective_from") or ""), reverse=True)
        chosen, bdate = None, None
        for s in cands:
            elig, d = await _booking_eligibility(b, s.get("calculation_basis", "PAID"))
            if not elig or not d:
                continue
            ef, eu = s.get("effective_from") or "", s.get("effective_until") or ""
            if ef and d < ef:
                continue
            if eu and d > eu:
                continue
            chosen, bdate = s, d
            break
        if not chosen or not (start <= bdate <= end):
            continue
        travelers = await db.travelers.find({"booking_id": bid}).to_list(500)
        if travelers:
            tlist = [(str(t["_id"]), t.get("full_name", "Traveler")) for t in travelers]
        else:
            n = int(b.get("pax") or 0)
            tlist = [(f"{bid}#pax{i + 1}", f"Pax {i + 1}") for i in range(n)]
        sid, sname = b.get("sales_pic_id"), b.get("sales_pic_name", "")
        for tid, tname in tlist:
            if (bid, tid) in claimed:
                continue
            grp = sales_map.setdefault(sid, {"name": sname, "groups": {}})
            g = grp["groups"].setdefault(chosen["_id"], {"scheme": chosen, "items": []})
            g["items"].append({"booking_id": bid, "booking_number": b.get("booking_number"),
                "traveler_id": tid, "traveler_name": tname, "package_name": b.get("package_name"),
                "product_type": product_type, "departure_date": b.get("departure_date") or "",
                "basis_date": bdate, "scheme_id": chosen["_id"], "scheme_name": chosen.get("scheme_name"),
                "calculation_basis": chosen.get("calculation_basis")})
    lines, items = [], []
    for sid, data in sales_map.items():
        total_pax, total_comm, ngroups, single_label, single_rate = 0, 0.0, 0, None, None
        for scheme_id, g in data["groups"].items():
            pax = len(g["items"])
            ngroups += 1
            rate, label = _tier_for(g["scheme"].get("tiers", []), pax)
            total_pax += pax
            total_comm += rate * pax
            single_label, single_rate = label, rate
            for it in g["items"]:
                items.append({**it, "period": period, "sales_pic_id": sid, "sales_pic_name": data["name"],
                              "commission_rate": rate, "tier": label})
        tier = single_label if ngroups == 1 else "Multiple"
        rate_disp = single_rate if ngroups == 1 else (round(total_comm / total_pax) if total_pax else 0)
        lines.append({"period": period, "sales_pic_id": sid, "sales_pic_name": data["name"],
            "total_pax": total_pax, "tier": tier, "commission_rate": rate_disp,
            "total_commission": total_comm})
    return lines, items


async def _get_closing(period):
    return await db.commission_closings.find_one({"period": period})


# ---------- Commission Schemes (view: commission.manage; edit: Super Admin only) ----------
@api_router.get("/commissions/schemes")
async def list_commission_schemes(user: dict = Depends(require_permission("commission.manage"))):
    docs = await db.commission_schemes.find().sort("created_at", -1).to_list(500)
    return [serialize(d) for d in docs]


@api_router.post("/commissions/schemes")
async def create_commission_scheme(body: CommissionScheme, request: Request, user: dict = Depends(require_role("super_admin"))):
    if body.product_type not in COMMISSION_PRODUCT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid product type")
    if body.calculation_basis not in COMMISSION_BASES:
        raise HTTPException(status_code=400, detail="Invalid calculation basis")
    doc = body.model_dump()
    doc.update({"created_at": now_iso(), "created_by": user["name"]})
    res = await db.commission_schemes.insert_one(doc)
    await log_audit(user, "commission", "create_scheme", request, record_id=str(res.inserted_id), new={"name": body.scheme_name})
    return serialize(await db.commission_schemes.find_one({"_id": res.inserted_id}))


@api_router.put("/commissions/schemes/{sid}")
async def update_commission_scheme(sid: str, body: CommissionScheme, request: Request, user: dict = Depends(require_role("super_admin"))):
    old = await db.commission_schemes.find_one({"_id": ObjectId(sid)})
    if not old:
        raise HTTPException(status_code=404, detail="Scheme not found")
    await db.commission_schemes.update_one({"_id": ObjectId(sid)}, {"$set": body.model_dump()})
    await log_audit(user, "commission", "update_scheme", request, record_id=sid, new={"name": body.scheme_name})
    return serialize(await db.commission_schemes.find_one({"_id": ObjectId(sid)}))


@api_router.delete("/commissions/schemes/{sid}")
async def delete_commission_scheme(sid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    await db.commission_schemes.delete_one({"_id": ObjectId(sid)})
    await log_audit(user, "commission", "delete_scheme", request, record_id=sid)
    return {"ok": True}


# ---------- Commission Settings (AUTO SALES) — Super Admin edit only ----------
@api_router.get("/commissions/settings")
async def get_commission_settings2(user: dict = Depends(require_permission("commission.manage"))):
    s = await get_settings_dict()
    c = s.get("commission", {}) or {}
    return {"auto_sales_commission": bool(c.get("auto_sales_commission", False)),
            "default_percent": c.get("default_percent", 2.5)}


@api_router.put("/commissions/settings")
async def put_commission_settings2(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    await db.system_settings.update_one({"key": "system"},
        {"$set": {"settings.commission.auto_sales_commission": bool(body.get("auto_sales_commission", False))}})
    await log_audit(user, "commission", "update_settings", request, new=body)
    s = await get_settings_dict()
    return s.get("commission", {})


# ---------- Commission Closings ----------
@api_router.get("/commissions/closings")
async def list_closings(user: dict = Depends(require_permission("commission.manage"))):
    docs = await db.commission_closings.find().sort("period", -1).to_list(200)
    return [serialize(d) for d in docs]


@api_router.post("/commissions/closings")
async def create_closing(body: dict, request: Request, user: dict = Depends(require_permission("commission.manage"))):
    period = (body or {}).get("period", "")
    if len(period) != 7 or period[4] != "-":
        raise HTTPException(status_code=400, detail="Period must be YYYY-MM")
    existing = await _get_closing(period)
    if existing:
        return serialize(existing)
    doc = {"period": period, "status": "OPEN", "total_pax": 0, "total_commission": 0,
           "created_at": now_iso(), "created_by": user["name"]}
    res = await db.commission_closings.insert_one(doc)
    await log_audit(user, "commission", "create_closing", request, record_id=period, new={"period": period})
    return serialize(await db.commission_closings.find_one({"_id": res.inserted_id}))


@api_router.post("/commissions/closings/{period}/calculate")
async def calculate_closing(period: str, request: Request, user: dict = Depends(require_permission("commission.manage"))):
    c = await _get_closing(period)
    if not c:
        c = {"period": period, "status": "OPEN", "created_at": now_iso(), "created_by": user["name"]}
        await db.commission_closings.insert_one(dict(c))
    if c.get("status") in ("CLOSED", "PAID"):
        raise HTTPException(status_code=400, detail="Closing sudah CLOSED. Lakukan REOPEN dulu (Super Admin).")
    await db.commission_closings.update_one({"period": period}, {"$set": {"status": "CALCULATING"}})
    await db.commission_items.delete_many({"period": period})
    await db.commission_lines.delete_many({"period": period})
    lines, items = await _compute_period(period)
    total_pax = total_comm = 0
    for ln in lines:
        ln.update({"adjustment": 0, "final_commission": ln["total_commission"], "payment_status": "UNPAID",
                   "created_at": now_iso()})
        total_pax += ln["total_pax"]
        total_comm += ln["total_commission"]
    if lines:
        await db.commission_lines.insert_many([dict(x) for x in lines])
    if items:
        await db.commission_items.insert_many([dict(x) for x in items])
    await db.commission_closings.update_one({"period": period},
        {"$set": {"status": "REVIEW", "total_pax": total_pax, "total_commission": total_comm,
                  "calculated_at": now_iso(), "calculated_by": user["name"]}})
    await log_audit(user, "commission", "calculate", request, record_id=period,
                    new={"lines": len(lines), "pax": total_pax})
    return {"period": period, "lines": len(lines), "total_pax": total_pax, "total_commission": total_comm}


@api_router.get("/commissions/closings/{period}")
async def get_closing_detail(period: str, user: dict = Depends(require_permission("commission.manage"))):
    c = await _get_closing(period)
    lines = [serialize(x) for x in await db.commission_lines.find({"period": period}).sort("total_commission", -1).to_list(1000)]
    return {"closing": serialize(c) if c else None, "lines": lines}


@api_router.get("/commissions/closings/{period}/sales/{sid}")
async def closing_sales_detail(period: str, sid: str, user: dict = Depends(require_permission("commission.manage"))):
    items = [serialize(x) for x in await db.commission_items.find({"period": period, "sales_pic_id": sid}).to_list(3000)]
    return {"period": period, "sales_pic_id": sid, "items": items}


@api_router.patch("/commissions/closings/{period}/status")
async def set_closing_status(period: str, body: dict, request: Request, user: dict = Depends(require_permission("commission.manage"))):
    c = await _get_closing(period)
    if not c:
        raise HTTPException(status_code=404, detail="Closing not found")
    new_status = (body or {}).get("status")
    if new_status not in CLOSING_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if c.get("status") in ("CLOSED", "PAID") and new_status not in ("PAID",):
        raise HTTPException(status_code=400, detail="Closing terkunci. Gunakan REOPEN (Super Admin).")
    await db.commission_closings.update_one({"period": period}, {"$set": {"status": new_status}})
    if new_status == "PAID":
        await db.commission_lines.update_many({"period": period}, {"$set": {"payment_status": "PAID"}})
    await log_audit(user, "commission", "closing_status", request, record_id=period, new={"status": new_status})
    return serialize(await _get_closing(period))


@api_router.post("/commissions/closings/{period}/reopen")
async def reopen_closing(period: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    c = await _get_closing(period)
    if not c:
        raise HTTPException(status_code=404, detail="Closing not found")
    await db.commission_closings.update_one({"period": period}, {"$set": {"status": "OPEN"}})
    await log_audit(user, "commission", "reopen", request, record_id=period)
    return serialize(await _get_closing(period))


@api_router.patch("/commissions/lines/{line_id}/adjustment")
async def set_line_adjustment(line_id: str, body: dict, request: Request, user: dict = Depends(require_permission("commission.manage"))):
    ln = await db.commission_lines.find_one({"_id": ObjectId(line_id)})
    if not ln:
        raise HTTPException(status_code=404, detail="Line not found")
    c = await _get_closing(ln["period"])
    if c and c.get("status") in ("CLOSED", "PAID"):
        raise HTTPException(status_code=400, detail="Closing terkunci, adjustment tidak diizinkan.")
    adj = float((body or {}).get("adjustment", 0) or 0)
    final = float(ln.get("total_commission") or 0) + adj
    await db.commission_lines.update_one({"_id": ObjectId(line_id)},
        {"$set": {"adjustment": adj, "adjustment_notes": (body or {}).get("notes", ""), "final_commission": final}})
    await log_audit(user, "commission", "adjustment", request, record_id=line_id, new={"adjustment": adj})
    return serialize(await db.commission_lines.find_one({"_id": ObjectId(line_id)}))


@api_router.patch("/commissions/lines/{line_id}/payment")
async def set_line_payment(line_id: str, body: dict, request: Request, user: dict = Depends(require_permission("commission.manage"))):
    ln = await db.commission_lines.find_one({"_id": ObjectId(line_id)})
    if not ln:
        raise HTTPException(status_code=404, detail="Line not found")
    ps = (body or {}).get("payment_status", "PAID")
    await db.commission_lines.update_one({"_id": ObjectId(line_id)}, {"$set": {"payment_status": ps}})
    await log_audit(user, "commission", "line_payment", request, record_id=line_id, new={"payment_status": ps})
    return serialize(await db.commission_lines.find_one({"_id": ObjectId(line_id)}))


# ---------- My Commission (Sales) ----------
@api_router.get("/commissions/my")
async def my_commission(user: dict = Depends(require_permission("commission.view"))):
    now = datetime.now(timezone.utc)
    period = f"{now.year:04d}-{now.month:02d}"
    lines, _ = await _compute_period(period, only_sales_id=user["_id"])
    current = lines[0] if lines else {"period": period, "total_pax": 0, "tier": "-",
                                      "commission_rate": 0, "total_commission": 0}
    prev = []
    for ln in await db.commission_lines.find({"sales_pic_id": user["_id"]}).sort("period", -1).to_list(200):
        c = await _get_closing(ln["period"])
        if c and c.get("status") in ("APPROVED", "CLOSED", "PAID"):
            prev.append({**serialize(ln), "closing_status": c.get("status")})
    return {"current": current, "period": period, "previous": prev}



# ============================================================================
# PHASE 7 — N8N INTEGRATION API (machine-to-machine) & AUTO SALES
# ============================================================================
_FERNET = Fernet(os.environ["ENCRYPTION_KEY"].encode())
_N8N_RATE = {}
N8N_RATE_LIMIT = 120  # requests / 60s per api key
N8N_TS_WINDOW = 300   # seconds


def _enc(s):
    return _FERNET.encrypt((s or "").encode()).decode()


def _dec(s):
    try:
        return _FERNET.decrypt((s or "").encode()).decode()
    except Exception:
        return ""


def _mask(s):
    return ("••••" + s[-4:]) if s and len(s) >= 4 else ("••••" if s else "")


async def _n8n_api_cfg():
    return await db.n8n_api_config.find_one({"key": "n8n_api"}) or {}


async def _api_log(request, endpoint, method, external_id, ok, code, start, error=""):
    cfg = await _n8n_api_cfg()
    await db.n8n_api_logs.insert_one({
        "timestamp": now_iso(), "endpoint": endpoint, "method": method,
        "request_id": request.headers.get("X-Request-Id") or str(_uuid.uuid4()),
        "external_id": external_id, "status": "success" if ok else "failed",
        "response_code": code, "processing_time_ms": round((_time.time() - start) * 1000, 1),
        "error": (error or "")[:300], "ip": request.client.host if request and request.client else None,
        "api_key_mask": _mask(cfg.get("api_key", "")),
    })


async def n8n_auth(request: Request):
    cfg = await _n8n_api_cfg()
    if not cfg.get("api_key"):
        raise HTTPException(status_code=401, detail="n8n API not configured")
    if request.headers.get("X-API-Key", "") != cfg.get("api_key"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    ts = request.headers.get("X-Timestamp", "")
    try:
        if abs(_time.time() - float(ts)) > N8N_TS_WINDOW:
            raise HTTPException(status_code=401, detail="Timestamp outside allowed window")
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid timestamp")
    secret = _dec(cfg.get("api_secret_enc", ""))
    body = await request.body()
    expected = _hmac.new(secret.encode(), (ts + "." + body.decode("utf-8")).encode(), _hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expected, request.headers.get("X-Signature", "")):
        raise HTTPException(status_code=401, detail="Invalid signature")
    now = _time.time()
    key = cfg.get("api_key")
    arr = [t for t in _N8N_RATE.get(key, []) if now - t < 60]
    if len(arr) >= N8N_RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    arr.append(now)
    _N8N_RATE[key] = arr
    return {"n8n": True}


def _v1_err(code, msg, http=400):
    return JSONResponse(status_code=http, content={"success": False, "error_code": code, "message": msg})


# ---------- N8N API config (Super Admin only) ----------
@api_router.get("/integrations/n8n/api-config")
async def get_n8n_api_config(user: dict = Depends(require_role("super_admin"))):
    c = await _n8n_api_cfg()
    return {"base_url": c.get("base_url", ""), "webhook_url": c.get("webhook_url", ""),
            "crm_api_url": c.get("crm_api_url", ""), "environment": c.get("environment", "production"),
            "connection_status": c.get("connection_status", "NOT_CONFIGURED"),
            "api_key": _mask(c.get("api_key", "")), "has_secret": bool(c.get("api_secret_enc")),
            "has_webhook_secret": bool(c.get("webhook_secret_enc"))}


@api_router.put("/integrations/n8n/api-config")
async def put_n8n_api_config(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    updates = {k: body.get(k, "") for k in ("base_url", "webhook_url", "crm_api_url", "environment")}
    updates["updated_at"] = now_iso()
    await db.n8n_api_config.update_one({"key": "n8n_api"}, {"$set": updates}, upsert=True)
    await log_audit(user, "integration", "n8n_api_config", request, new={k: updates[k] for k in updates if k != "updated_at"})
    return await get_n8n_api_config(user)


@api_router.post("/integrations/n8n/api-config/generate")
async def generate_n8n_credentials(request: Request, user: dict = Depends(require_role("super_admin"))):
    api_key = "n8n_" + secrets.token_hex(16)
    api_secret = secrets.token_urlsafe(32)
    webhook_secret = secrets.token_urlsafe(32)
    await db.n8n_api_config.update_one({"key": "n8n_api"},
        {"$set": {"api_key": api_key, "api_secret_enc": _enc(api_secret),
                  "webhook_secret_enc": _enc(webhook_secret), "connection_status": "CONFIGURED",
                  "updated_at": now_iso()}}, upsert=True)
    await log_audit(user, "integration", "n8n_generate_credentials", request, new={"api_key": _mask(api_key)})
    return {"api_key": api_key, "api_secret": api_secret, "webhook_secret": webhook_secret,
            "note": "Simpan sekarang. Secret hanya ditampilkan sekali."}


@api_router.get("/integrations/n8n/api-logs")
async def get_n8n_api_logs(user: dict = Depends(require_role("super_admin"))):
    docs = await db.n8n_api_logs.find().sort("timestamp", -1).to_list(200)
    return [serialize(d) for d in docs]


# ---------- N8N MACHINE API /api/v1/* ----------
@api_router.get("/v1/packages")
async def v1_packages(request: Request, _n=Depends(n8n_auth)):
    start = _time.time()
    docs = await db.packages.find({"status": "ACTIVE"}).to_list(1000)
    out = [strip_hpp(d, False) for d in docs]
    await _api_log(request, "/v1/packages", "GET", None, True, 200, start)
    return {"success": True, "packages": out}


@api_router.get("/v1/departures")
async def v1_departures(request: Request, package_id: Optional[str] = None, _n=Depends(n8n_auth)):
    start = _time.time()
    q = {"package_id": package_id} if package_id else {}
    docs = [compute_departure(serialize(d)) for d in await db.departures.find(q).sort("departure_date", 1).to_list(500)]
    await _api_log(request, "/v1/departures", "GET", None, True, 200, start)
    return {"success": True, "departures": docs}


@api_router.get("/v1/customers/{cid}")
async def v1_get_customer(cid: str, request: Request, _n=Depends(n8n_auth)):
    start = _time.time()
    c = await db.customers.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not c:
        await _api_log(request, f"/v1/customers/{cid}", "GET", None, False, 404, start, "not found")
        return _v1_err("CUSTOMER_NOT_FOUND", "Customer tidak ditemukan", 404)
    await _api_log(request, f"/v1/customers/{cid}", "GET", None, True, 200, start)
    return {"success": True, "customer": serialize(c)}


@api_router.get("/v1/bookings/{bid}")
async def v1_get_booking(bid: str, request: Request, _n=Depends(n8n_auth)):
    start = _time.time()
    b = await db.bookings.find_one({"_id": ObjectId(bid)}) if ObjectId.is_valid(bid) else None
    if not b:
        await _api_log(request, f"/v1/bookings/{bid}", "GET", None, False, 404, start, "not found")
        return _v1_err("BOOKING_NOT_FOUND", "Booking tidak ditemukan", 404)
    await _api_log(request, f"/v1/bookings/{bid}", "GET", b.get("external_booking_id"), True, 200, start)
    return {"success": True, "booking": serialize(b)}


@api_router.post("/v1/customers")
async def v1_create_customer(payload: dict = Body(default={}), request: Request = None, _n=Depends(n8n_auth)):
    start = _time.time()
    name = (payload.get("full_name") or "").strip()
    wa = (payload.get("whatsapp") or payload.get("phone") or "").strip()
    if not name and not wa:
        await _api_log(request, "/v1/customers", "POST", None, False, 400, start, "missing name/phone")
        return _v1_err("INVALID_CUSTOMER", "full_name atau whatsapp wajib diisi")
    existing = None
    if wa:
        existing = await db.customers.find_one({"whatsapp": wa})
    if not existing and payload.get("email"):
        existing = await db.customers.find_one({"email": payload.get("email")})
    if existing:
        await _api_log(request, "/v1/customers", "POST", None, True, 200, start)
        return {"success": True, "existing": True, "customer": serialize(existing)}
    count = await db.customers.count_documents({})
    doc = {"customer_code": f"CUST-{count + 1:05d}", "full_name": name or wa, "whatsapp": wa,
           "email": payload.get("email", ""), "city": payload.get("city", ""), "country": payload.get("country", "Indonesia"),
           "customer_type": payload.get("customer_type", "Prospect"), "customer_source": "N8N",
           "sales_pic_id": None, "sales_pic_name": "AUTO SALES", "branch": "",
           "created_at": now_iso(), "created_by": "SYSTEM"}
    res = await db.customers.insert_one(doc)
    await _api_log(request, "/v1/customers", "POST", None, True, 201, start)
    return {"success": True, "existing": False, "customer": serialize(await db.customers.find_one({"_id": res.inserted_id}))}


@api_router.post("/v1/leads")
async def v1_create_lead(payload: dict = Body(default={}), request: Request = None, _n=Depends(n8n_auth)):
    start = _time.time()
    cid = payload.get("customer_id")
    cust = await db.customers.find_one({"_id": ObjectId(cid)}) if cid and ObjectId.is_valid(cid) else None
    if not cust:
        await _api_log(request, "/v1/leads", "POST", None, False, 404, start, "customer not found")
        return _v1_err("CUSTOMER_NOT_FOUND", "Customer tidak ditemukan", 404)
    count = await db.leads.count_documents({})
    doc = {"lead_code": f"LEAD-{count + 1:05d}", "customer_id": cid, "customer_name": cust.get("full_name"),
           "source": "N8N", "interested_package": payload.get("interested_package", ""),
           "destination": payload.get("destination", ""), "pax": int(payload.get("pax") or 0),
           "budget": float(payload.get("budget") or 0), "status": "NEW", "sales_pic_id": None,
           "sales_pic_name": "AUTO SALES", "branch": "", "last_contact": now_iso(), "created_at": now_iso(),
           "next_follow_up": "", "notes": payload.get("notes", "")}
    res = await db.leads.insert_one(doc)
    lead = serialize(await db.leads.find_one({"_id": res.inserted_id}))
    await log_activity(cid, lead["_id"], "lead_created", "Lead created (n8n)", "AUTO SALES", None)
    trigger_n8n("lead.created", {"id": lead["_id"], "lead_code": lead["lead_code"], "customer_name": cust.get("full_name")})
    await _api_log(request, "/v1/leads", "POST", None, True, 201, start)
    return {"success": True, "lead": lead}


@api_router.post("/v1/bookings")
async def v1_create_booking(payload: dict = Body(default={}), request: Request = None, _n=Depends(n8n_auth)):
    start = _time.time()
    ext = payload.get("external_booking_id") or (request.headers.get("X-Idempotency-Key") if request else None)
    if ext:
        dup = await db.bookings.find_one({"external_booking_id": ext})
        if dup:
            await _api_log(request, "/v1/bookings", "POST", ext, True, 200, start, "idempotent")
            return {"success": True, "idempotent": True, "booking": serialize(dup)}
    cid = payload.get("customer_id")
    cust = await db.customers.find_one({"_id": ObjectId(cid)}) if cid and ObjectId.is_valid(cid) else None
    if not cust:
        await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "customer not found")
        return _v1_err("CUSTOMER_NOT_FOUND", "Customer tidak ditemukan")
    pid = payload.get("package_id")
    pkg = await db.packages.find_one({"_id": ObjectId(pid)}) if pid and ObjectId.is_valid(pid) else None
    if not pkg:
        await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "package not found")
        return _v1_err("PACKAGE_NOT_FOUND", "Package tidak ditemukan")
    if pkg.get("status") != "ACTIVE":
        await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "package not active")
        return _v1_err("PACKAGE_NOT_ACTIVE", "Package tidak aktif")
    pax = int(payload.get("pax") or 0)
    if pax < 1:
        await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "invalid pax")
        return _v1_err("INVALID_PAX", "Jumlah pax tidak valid")
    dep = None
    did = payload.get("departure_id")
    if did:
        dep = await db.departures.find_one({"_id": ObjectId(did)}) if ObjectId.is_valid(did) else None
        if not dep:
            await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "departure not found")
            return _v1_err("DEPARTURE_NOT_FOUND", "Departure tidak ditemukan")
        dep = compute_departure(serialize(dep))
        if int(dep.get("available_seat") or 0) < pax:
            await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "departure full")
            return _v1_err("DEPARTURE_FULL", "Departure is fully booked")
    settings = await get_settings_dict()
    per_pax = compute_pax_price(pkg, pax)
    subtotal = per_pax * pax
    pct, _amt = resolve_category_tax(pkg, settings)
    tax_amount = round(subtotal * pct / 100)
    total = subtotal + tax_amount
    if payload.get("total") is not None and abs(float(payload["total"]) - total) > 1:
        await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "price invalid")
        return _v1_err("PRICE_INVALID", f"Harga tidak valid. Expected total {total}")
    travelers = payload.get("travelers") or []
    for t in travelers:
        if not (t.get("full_name") or "").strip():
            await _api_log(request, "/v1/bookings", "POST", ext, False, 400, start, "invalid traveler")
            return _v1_err("INVALID_TRAVELER", "Data traveler tidak valid (full_name wajib)")
    number = await next_number((settings.get("numbering") or {}).get("booking_prefix", "BKG"), db.bookings, "booking_number")
    booking = {"booking_number": number, "quotation_id": None, "customer_id": cid, "customer_name": cust.get("full_name"),
               "package_id": pid, "package_name": pkg.get("package_name"), "package_version": pkg.get("version", 1),
               "departure_id": did, "departure_date": (dep or {}).get("departure_date", ""), "pax": pax,
               "room_type": payload.get("room_type", ""), "addons": [], "booking_source": "AUTO SALES",
               "sales_type": "AUTO", "sales_user_id": None, "sales_name": "AUTO SALES",
               "per_pax_price": per_pax, "subtotal": subtotal, "discount_percent": 0, "discount_amount": 0,
               "tax_percent": pct, "tax_amount": tax_amount, "total": total, "payment_schedule": [],
               "status": "CONFIRMED", "sales_pic_id": None, "sales_pic_name": "AUTO SALES", "branch": "",
               "external_booking_id": ext, "workflow_id": payload.get("workflow_id", ""),
               "created_at": now_iso(), "created_by": "SYSTEM"}
    res = await db.bookings.insert_one(booking)
    bid = str(res.inserted_id)
    for t in travelers:
        await db.travelers.insert_one({**t, "booking_id": bid, "created_at": now_iso(), "created_by": "SYSTEM"})
    if did:
        await db.departures.update_one({"_id": ObjectId(did)}, {"$inc": {"confirmed_pax": pax}})
    inv_number = await next_number((settings.get("numbering") or {}).get("invoice_prefix", "INV"), db.invoices, "invoice_number")
    await db.invoices.insert_one({"invoice_number": inv_number, "booking_id": bid, "booking_number": number,
        "customer_id": cid, "customer_name": cust.get("full_name"), "package_id": pid, "package_name": pkg.get("package_name"),
        "pax": pax, "amount": subtotal, "discount_amount": 0, "discount_percent": 0, "tax_percent": pct,
        "tax_amount": tax_amount, "total": total, "paid_amount": 0, "outstanding": total,
        "due_date": payload.get("due_date", ""), "status": "Unpaid", "sales_pic_id": None,
        "sales_pic_name": "AUTO SALES", "branch": "", "terms": pkg.get("terms", ""),
        "created_at": now_iso(), "created_by": "SYSTEM"})
    if ext:
        await db.idempotency_keys.update_one({"key": ext}, {"$set": {"booking_id": bid, "created_at": now_iso()}}, upsert=True)
    trigger_n8n("booking.created", {"id": bid, "booking_number": number, "customer_name": cust.get("full_name"),
        "customer_phone": cust.get("whatsapp", ""), "total": total, "source": "AUTO SALES"})
    await _api_log(request, "/v1/bookings", "POST", ext, True, 201, start)
    return {"success": True, "booking": serialize(await db.bookings.find_one({"_id": res.inserted_id})), "invoice_number": inv_number}


@api_router.put("/v1/bookings/{bid}")
async def v1_update_booking(bid: str, payload: dict = Body(default={}), request: Request = None, _n=Depends(n8n_auth)):
    start = _time.time()
    b = await db.bookings.find_one({"_id": ObjectId(bid)}) if ObjectId.is_valid(bid) else None
    if not b:
        await _api_log(request, f"/v1/bookings/{bid}", "PUT", None, False, 404, start, "not found")
        return _v1_err("BOOKING_NOT_FOUND", "Booking tidak ditemukan", 404)
    updates = {}
    new_status = payload.get("status")
    if new_status:
        if new_status not in ("CONFIRMED", "PENDING", "CANCELLED", "COMPLETED"):
            return _v1_err("INVALID_STATUS", "Status tidak valid")
        updates["status"] = new_status
    for k in ("room_type", "notes"):
        if k in payload:
            updates[k] = payload[k]
    if updates:
        await db.bookings.update_one({"_id": ObjectId(bid)}, {"$set": updates})
    if new_status == "CANCELLED":
        if b.get("departure_id"):
            await db.departures.update_one({"_id": ObjectId(b["departure_id"])}, {"$inc": {"confirmed_pax": -int(b.get("pax") or 0)}})
        trigger_n8n("booking.cancelled", {"id": bid, "booking_number": b.get("booking_number")})
    else:
        trigger_n8n("booking.updated", {"id": bid, "booking_number": b.get("booking_number"), "status": new_status})
    await _api_log(request, f"/v1/bookings/{bid}", "PUT", b.get("external_booking_id"), True, 200, start)
    return {"success": True, "booking": serialize(await db.bookings.find_one({"_id": ObjectId(bid)}))}


@api_router.post("/v1/payments")
async def v1_create_payment(payload: dict = Body(default={}), request: Request = None, _n=Depends(n8n_auth)):
    start = _time.time()
    iid = payload.get("invoice_id")
    inv = None
    if iid and ObjectId.is_valid(iid):
        inv = await db.invoices.find_one({"_id": ObjectId(iid)})
    elif payload.get("booking_id"):
        inv = await db.invoices.find_one({"booking_id": payload["booking_id"]}, sort=[("created_at", -1)])
    if not inv:
        await _api_log(request, "/v1/payments", "POST", None, False, 404, start, "invoice not found")
        return _v1_err("INVOICE_NOT_FOUND", "Invoice tidak ditemukan", 404)
    amount = float(payload.get("amount") or 0)
    if amount <= 0:
        return _v1_err("INVALID_AMOUNT", "Amount tidak valid")
    iid = str(inv["_id"])
    await db.payments.insert_one({"invoice_id": iid, "invoice_number": inv.get("invoice_number"),
        "booking_id": inv.get("booking_id"), "payment_date": payload.get("payment_date", today_str()),
        "amount": amount, "payment_method": payload.get("payment_method", "Transfer"),
        "bank": payload.get("bank", ""), "reference_number": payload.get("reference_number", ""),
        "notes": payload.get("notes", "n8n"), "attachment_url": "", "recorded_by": "SYSTEM", "created_at": now_iso()})
    status = await _recompute_invoice_status(iid)
    trigger_n8n("payment.created", {"invoice_number": inv.get("invoice_number"), "amount": amount, "invoice_status": status})
    if status == "Paid":
        trigger_n8n("payment.confirmed", {"invoice_number": inv.get("invoice_number"), "customer_name": inv.get("customer_name")})
    await _api_log(request, "/v1/payments", "POST", None, True, 201, start)
    return {"success": True, "invoice_status": status, "invoice_number": inv.get("invoice_number")}


@api_router.post("/v1/communications")
async def v1_create_communication(payload: dict = Body(default={}), request: Request = None, _n=Depends(n8n_auth)):
    start = _time.time()
    doc = {"customer_id": payload.get("customer_id"), "lead_id": payload.get("lead_id"),
           "booking_id": payload.get("booking_id"), "phone": payload.get("phone", ""),
           "direction": payload.get("direction", "outbound"), "message": payload.get("message", ""),
           "channel": (payload.get("channel") or "WHATSAPP").upper(), "source": "N8N", "automation": True,
           "external_message_id": payload.get("external_message_id", ""), "workflow_id": payload.get("workflow_id", ""),
           "sales_pic_name": "AUTO SALES", "timestamp": now_iso()}
    res = await db.communications.insert_one(doc)
    if payload.get("customer_id"):
        await log_activity(payload.get("customer_id"), payload.get("lead_id"), "communication",
                           f"WhatsApp ({doc['direction']}) via n8n", doc["message"], None)
    await _api_log(request, "/v1/communications", "POST", None, True, 201, start)
    return {"success": True, "communication": serialize(await db.communications.find_one({"_id": res.inserted_id}))}


# ============================================================================
# PHASE 8 — CANCELLATION & REFUND APPROVAL WORKFLOW (Super Admin approval)
# ============================================================================
CANCEL_STATUSES = ["REQUESTED", "ACCOUNTING_REVIEWED", "APPROVED", "REJECTED"]
REFUND_STATUSES = ["CALCULATED", "ACCOUNTING_REVIEWED", "APPROVED", "REJECTED", "PROCESSING", "PARTIALLY_REFUNDED", "REFUNDED"]


async def _notify(title, body, link="", role=None, user_id=None):
    await db.notifications.insert_one({"role": role, "user_id": user_id, "title": title,
        "body": body, "link": link, "read": False, "created_at": now_iso()})


def _timeline_entry(user, action, old_status, new_status, request, reason="", amount=None):
    return {"action": action, "by": user.get("name"), "role": user.get("role"),
            "at": now_iso(), "old_status": old_status, "new_status": new_status,
            "reason": reason, "amount": amount,
            "ip": request.client.host if request and request.client else None}


async def _booking_financials(bid):
    invs = await db.invoices.find({"booking_id": bid}).to_list(50)
    total_paid = sum(float(i.get("paid_amount") or 0) for i in invs)
    total_billed = sum(float(i.get("total") or 0) for i in invs)
    return total_paid, total_billed


# ---- Phase 4B: Refund deduction engine ----
def _ded_amount(method, unit, qty, total_paid):
    unit = float(unit or 0)
    qty = float(qty or 1)
    if method == "PERCENTAGE":
        return round(float(total_paid or 0) * unit / 100)
    if method in ("PER_PAX", "PER_TRAVELER"):
        return round(unit * qty)
    return round(unit)  # FIXED / FULL_NON_REFUNDABLE


def _ded_item(dtype, description, method, source, qty, unit_amount, amount, non_refundable, traveler_id, by, attachment_url="", notes=""):
    return {"id": str(_uuid.uuid4())[:8], "type": dtype, "description": description, "method": method,
            "source": source, "qty": qty, "unit_amount": float(unit_amount or 0), "amount": round(float(amount or 0)),
            "non_refundable": bool(non_refundable), "traveler_id": traveler_id, "attachment_url": attachment_url,
            "notes": notes, "added_by": by, "added_at": now_iso()}


def _recalc_refund(d):
    tp = float(d.get("total_paid") or 0)
    total_ded = sum(float(x.get("amount") or 0) for x in d.get("deductions", []))
    adj = float(d.get("refund_adjustment") or 0)
    warning = "Deduction exceeds total paid amount." if total_ded > tp else None
    final = max(0.0, tp - total_ded + adj)
    return round(total_ded, 2), round(final, 2), warning


def _refund_version(d, reason, by, new_amount):
    return {"version": len(d.get("versions", [])) + 1, "changed_by": by, "date": now_iso(),
            "reason": reason, "previous_amount": round(float(d.get("proposed_refund") or 0)), "new_amount": round(float(new_amount or 0))}


async def _suggested_deductions(package_id, departure_id, cancelled_pax, total_paid):
    pol = None
    if departure_id:
        pol = await db.refund_policies.find_one({"scope": "departure", "ref_id": departure_id})
    if not pol and package_id:
        pol = await db.refund_policies.find_one({"scope": "package", "ref_id": package_id})
    out = []
    for it in (pol or {}).get("items", []):
        method = it.get("method", "PER_PAX")
        qty = cancelled_pax if method in ("PER_PAX", "PER_TRAVELER") else 1
        amt = _ded_amount(method, it.get("unit_amount"), qty, total_paid)
        out.append(_ded_item(it.get("type", "Deduction"), it.get("description", "Policy default"), method,
                             it.get("source", "Package"), qty, it.get("unit_amount"), amt, it.get("non_refundable", True), None, "POLICY"))
    return out


async def _apply_commission_impact(cx, user):
    """If cancelled travelers are in a finalized commission period, record a negative pax adjustment (do not delete closing)."""
    for tid in cx.get("cancelled_traveler_ids", []) or []:
        item = await db.commission_items.find_one({"booking_id": cx["booking_id"], "traveler_id": tid})
        if not item:
            continue
        closing = await db.commission_closings.find_one({"period": item["period"]})
        if closing and closing.get("status") in ("APPROVED", "CLOSED", "PAID"):
            await db.commission_adjustments.insert_one({"period": item["period"], "sales_pic_id": item.get("sales_pic_id"),
                "booking_id": cx["booking_id"], "traveler_id": tid, "pax_delta": -1,
                "reason": f"Cancellation {cx['cancellation_number']}", "created_by": user["name"], "created_at": now_iso()})


async def _can_view_cancellation(user, doc):
    if user["role"] in ("super_admin", "accounting"):
        return True
    return doc.get("sales_pic_id") == user["_id"]


# ---------- CANCELLATION ----------
@api_router.post("/cancellations")
async def create_cancellation(body: dict, request: Request, user: dict = Depends(require_permission("cancellation.request"))):
    bid = body.get("booking_id")
    b = await db.bookings.find_one({"_id": ObjectId(bid)}) if bid and ObjectId.is_valid(bid) else None
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    if user["role"] == "sales" and b.get("sales_pic_id") != user["_id"]:
        raise HTTPException(status_code=403, detail="403 Forbidden")
    if b.get("status") in ("CANCELLED",):
        raise HTTPException(status_code=400, detail="Booking sudah dibatalkan")
    existing = await db.cancellation_requests.find_one({"booking_id": bid, "status": {"$in": ["REQUESTED", "ACCOUNTING_REVIEWED"]}})
    if existing:
        raise HTTPException(status_code=400, detail="Sudah ada pengajuan cancellation aktif untuk booking ini")
    total_pax = int(b.get("pax") or 0)
    trav_ids = body.get("cancelled_traveler_ids") or []
    cancelled_pax = len(trav_ids) if trav_ids else total_pax
    is_partial = bool(trav_ids) and cancelled_pax < total_pax
    number = await next_number("CXL", db.cancellation_requests, "cancellation_number")
    total_paid, _tb = await _booking_financials(bid)
    doc = {"cancellation_number": number, "booking_id": bid, "booking_number": b.get("booking_number"),
           "customer_id": b.get("customer_id"), "customer_name": b.get("customer_name"),
           "package_id": b.get("package_id"), "package_name": b.get("package_name"),
           "departure_id": b.get("departure_id"), "departure_date": b.get("departure_date", ""),
           "sales_pic_id": b.get("sales_pic_id"), "sales_name": b.get("sales_name") or b.get("sales_pic_name"),
           "total_pax": total_pax, "cancelled_pax": cancelled_pax, "cancelled_traveler_ids": trav_ids,
           "is_partial": is_partial, "total_booking_value": float(b.get("total") or 0),
           "total_paid": total_paid, "outstanding": float(b.get("total") or 0) - total_paid,
           "reason": body.get("reason", ""), "detail": body.get("detail", ""), "notes": body.get("notes", ""),
           "supporting_documents": body.get("supporting_documents", []),
           "accounting_review": None, "approval": None, "prev_booking_status": b.get("status"),
           "status": "REQUESTED", "created_by": user["name"], "created_by_id": user["_id"], "created_at": now_iso(),
           "timeline": [_timeline_entry(user, "Request Created", None, "REQUESTED", request, body.get("reason", ""))]}
    res = await db.cancellation_requests.insert_one(doc)
    await log_audit(user, "cancellation", "request", request, record_id=str(res.inserted_id), new={"number": number, "cancelled_pax": cancelled_pax})
    await _notify("Cancellation baru diajukan", f"{number} • {b.get('booking_number')} oleh {user['name']}", "/approvals", role="accounting")
    await _notify("Cancellation baru diajukan", f"{number} • {b.get('booking_number')} menunggu review", "/approvals", role="super_admin")
    return serialize(await db.cancellation_requests.find_one({"_id": res.inserted_id}))


@api_router.get("/cancellations")
async def list_cancellations(status: Optional[str] = None, user: dict = Depends(require_permission("cancellation.request"))):
    q = {}
    if user["role"] == "sales":
        q["sales_pic_id"] = user["_id"]
    if status and status != "all":
        q["status"] = status
    docs = await db.cancellation_requests.find(q).sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.get("/cancellations/{cid}")
async def get_cancellation(cid: str, user: dict = Depends(require_permission("cancellation.request"))):
    d = await db.cancellation_requests.find_one({"_id": ObjectId(cid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if not await _can_view_cancellation(user, d):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    return serialize(d)


@api_router.patch("/cancellations/{cid}/review")
async def review_cancellation(cid: str, body: dict, request: Request, user: dict = Depends(require_permission("cancellation.review"))):
    d = await db.cancellation_requests.find_one({"_id": ObjectId(cid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if d["status"] not in ("REQUESTED",):
        raise HTTPException(status_code=400, detail="Status tidak valid untuk review")
    fee = float(body.get("cancellation_fee") or 0)
    nonref = float(body.get("non_refundable_cost") or 0)
    supplier = float(body.get("supplier_cost") or 0)
    other = float(body.get("other_deduction") or 0)
    estimated = max(0.0, float(d.get("total_paid") or 0) - fee - nonref - other)
    review = {"cancellation_fee": fee, "non_refundable_cost": nonref, "supplier_cost": supplier,
              "other_deduction": other, "estimated_refund": estimated,
              "financial_impact": fee + nonref + supplier + other,
              "recommendation": body.get("recommendation", ""), "reviewed_by": user["name"], "reviewed_at": now_iso()}
    tl = d.get("timeline", []) + [_timeline_entry(user, "Accounting Reviewed", d["status"], "ACCOUNTING_REVIEWED", request, body.get("recommendation", ""), estimated)]
    await db.cancellation_requests.update_one({"_id": ObjectId(cid)}, {"$set": {"accounting_review": review, "status": "ACCOUNTING_REVIEWED", "timeline": tl}})
    await log_audit(user, "cancellation", "review", request, record_id=cid, new=review)
    await _notify("Cancellation siap approval", f"{d['cancellation_number']} sudah direview Accounting", "/approvals", role="super_admin")
    return serialize(await db.cancellation_requests.find_one({"_id": ObjectId(cid)}))


@api_router.patch("/cancellations/{cid}/approve")
async def approve_cancellation(cid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    d = await db.cancellation_requests.find_one({"_id": ObjectId(cid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    action = (body.get("action") or "").upper()
    if action not in ("APPROVE", "REJECT", "REQUEST_REVISION"):
        raise HTTPException(status_code=400, detail="Invalid action")
    if d["status"] not in ("ACCOUNTING_REVIEWED",):
        raise HTTPException(status_code=400, detail="Cancellation harus melalui Accounting Review dulu")
    old = d["status"]
    if action == "REJECT":
        reason = body.get("reason", "")
        if not reason:
            raise HTTPException(status_code=400, detail="Rejection reason wajib diisi")
        tl = d.get("timeline", []) + [_timeline_entry(user, "Super Admin Rejected", old, "REJECTED", request, reason)]
        await db.cancellation_requests.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "REJECTED", "approval": {"action": "REJECT", "by": user["name"], "at": now_iso(), "reason": reason}, "timeline": tl}})
        await log_audit(user, "cancellation", "reject", request, record_id=cid, old={"status": old}, new={"status": "REJECTED", "reason": reason})
        await _notify("Cancellation ditolak", f"{d['cancellation_number']} ditolak: {reason}", "/approvals", role="accounting")
        await _notify("Cancellation ditolak", f"{d['cancellation_number']} ditolak: {reason}", "/approvals", user_id=d.get("created_by_id"))
        return serialize(await db.cancellation_requests.find_one({"_id": ObjectId(cid)}))
    if action == "REQUEST_REVISION":
        tl = d.get("timeline", []) + [_timeline_entry(user, "Revision Requested", old, "REQUESTED", request, body.get("reason", ""))]
        await db.cancellation_requests.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "REQUESTED", "timeline": tl}})
        await log_audit(user, "cancellation", "request_revision", request, record_id=cid)
        await _notify("Revisi cancellation diminta", f"{d['cancellation_number']} perlu revisi", "/approvals", role="accounting")
        return serialize(await db.cancellation_requests.find_one({"_id": ObjectId(cid)}))
    # APPROVE — Super Admin may override amounts
    review = d.get("accounting_review") or {}
    fee = float(body.get("cancellation_fee", review.get("cancellation_fee", 0)) or 0)
    nonref = float(body.get("non_refundable_cost", review.get("non_refundable_cost", 0)) or 0)
    other = float(body.get("other_deduction", review.get("other_deduction", 0)) or 0)
    estimated = max(0.0, float(d.get("total_paid") or 0) - fee - nonref - other)
    b = await db.bookings.find_one({"_id": ObjectId(d["booking_id"])})
    new_booking_status = "PARTIALLY_CANCELLED" if d.get("is_partial") else "CANCELLED"
    upd = {"status": new_booking_status}
    if d.get("is_partial"):
        upd["pax"] = max(0, int(b.get("pax") or 0) - int(d.get("cancelled_pax") or 0))
        await db.travelers.update_many({"_id": {"$in": [ObjectId(t) for t in d.get("cancelled_traveler_ids", []) if ObjectId.is_valid(t)]}}, {"$set": {"cancelled": True}})
    if b:
        await db.bookings.update_one({"_id": b["_id"]}, {"$set": upd})
        if b.get("departure_id") and ObjectId.is_valid(b["departure_id"]):
            await db.departures.update_one({"_id": ObjectId(b["departure_id"])}, {"$inc": {"confirmed_pax": -int(d.get("cancelled_pax") or 0)}})
    tl = d.get("timeline", []) + [_timeline_entry(user, "Super Admin Approved", old, "APPROVED", request, "", estimated)]
    await db.cancellation_requests.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "APPROVED",
        "approval": {"action": "APPROVE", "by": user["name"], "at": now_iso(),
                     "cancellation_fee": fee, "non_refundable_cost": nonref, "other_deduction": other, "estimated_refund": estimated},
        "timeline": tl}})
    await log_audit(user, "cancellation", "approve", request, record_id=cid, old={"status": old, "booking_status": b.get("status") if b else None}, new={"status": "APPROVED", "booking_status": new_booking_status, "estimated_refund": estimated})
    # Auto-create refund request (CALCULATED) with itemized deductions + version
    rnum = await next_number("RFD", db.refund_requests, "refund_number")
    tp = float(d.get("total_paid") or 0)
    init_deductions = []
    if fee:
        init_deductions.append(_ded_item("Cancellation Fee", "Cancellation fee", "FIXED", "Manual Adjustment", 1, fee, fee, True, None, "SYSTEM"))
    if nonref:
        init_deductions.append(_ded_item("Non-Refundable Cost", "Non-refundable cost", "FIXED", "Booking", 1, nonref, nonref, True, None, "SYSTEM"))
    if other:
        init_deductions.append(_ded_item("Other Deduction", "Other deduction", "FIXED", "Manual Adjustment", 1, other, other, False, None, "SYSTEM"))
    init_deductions += await _suggested_deductions(d.get("package_id"), d.get("departure_id"), int(d.get("cancelled_pax") or 0), tp)
    total_ded = sum(float(x["amount"]) for x in init_deductions)
    final = max(0.0, tp - total_ded)
    orig_tax = float((b or {}).get("tax_amount") or 0)
    ratio = (int(d.get("cancelled_pax") or 0) / int(d.get("total_pax") or 1)) if d.get("total_pax") else 1
    cancelled_tax = round(orig_tax * ratio)
    refund = {"refund_number": rnum, "cancellation_id": cid, "cancellation_number": d["cancellation_number"],
              "booking_id": d["booking_id"], "booking_number": d["booking_number"], "package_id": d.get("package_id"),
              "departure_id": d.get("departure_id"), "customer_id": d.get("customer_id"), "customer_name": d.get("customer_name"),
              "package_name": d.get("package_name"), "sales_pic_id": d.get("sales_pic_id"), "sales_name": d.get("sales_name"),
              "original_booking_value": d.get("total_booking_value"), "discount": 0,
              "net_booking_value": d.get("total_booking_value"), "total_paid": tp,
              "cancelled_pax": d.get("cancelled_pax"), "total_pax": d.get("total_pax"),
              "deductions": init_deductions, "total_deduction": round(total_ded, 2),
              "refund_adjustment": 0.0, "adjustment_reason": "",
              "cancellation_fee": fee, "non_refundable_cost": nonref, "other_deduction": other,
              "original_tax": orig_tax, "cancelled_tax": cancelled_tax, "tax_adjustment": -cancelled_tax, "final_tax": orig_tax - cancelled_tax,
              "proposed_refund": round(final, 2), "approved_refund": 0.0, "recommendation": review.get("recommendation", ""),
              "bank": {"bank_name": "", "account_number": "", "account_holder": ""},
              "supporting_documents": [], "payments": [], "refunded_amount": 0.0,
              "approval": None, "status": "CALCULATED", "created_by": "SYSTEM", "created_at": now_iso(),
              "versions": [{"version": 1, "changed_by": "SYSTEM", "date": now_iso(), "reason": "Initial calculation", "previous_amount": 0, "new_amount": round(final, 2)}],
              "timeline": [_timeline_entry(user, "Refund Calculated", None, "CALCULATED", request, "", final)]}
    await db.refund_requests.insert_one(refund)
    trigger_n8n("refund.calculated", {"refund_id": rnum, "booking_id": d["booking_id"], "customer_id": d.get("customer_id"),
        "proposed_refund": round(final, 2), "total_deduction": round(total_ded, 2), "currency": "IDR"})
    await _notify("Booking dibatalkan", f"{d['booking_number']} disetujui. Refund {rnum} dibuat (Rp {final:,.0f})".replace(",", "."), "/approvals", role="accounting")
    await _notify("Cancellation disetujui", f"{d['cancellation_number']} disetujui Super Admin", "/approvals", user_id=d.get("created_by_id"))
    await _apply_commission_impact(d, user)
    return serialize(await db.cancellation_requests.find_one({"_id": ObjectId(cid)}))


@api_router.post("/cancellations/{cid}/reopen")
async def reopen_cancellation(cid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    d = await db.cancellation_requests.find_one({"_id": ObjectId(cid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    tl = d.get("timeline", []) + [_timeline_entry(user, "Reopened", d["status"], "REQUESTED", request)]
    await db.cancellation_requests.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "REQUESTED", "timeline": tl}})
    await log_audit(user, "cancellation", "reopen", request, record_id=cid)
    return serialize(await db.cancellation_requests.find_one({"_id": ObjectId(cid)}))


# ---------- REFUND ----------
@api_router.get("/refund-requests")
async def list_refund_requests(status: Optional[str] = None, user: dict = Depends(require_permission("refund.view"))):
    q = {}
    if user["role"] == "sales":
        q["sales_pic_id"] = user["_id"]
    if status and status != "all":
        q["status"] = status
    docs = await db.refund_requests.find(q).sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.get("/refund-requests/{rid}")
async def get_refund_request(rid: str, user: dict = Depends(require_permission("refund.view"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if user["role"] == "sales" and d.get("sales_pic_id") != user["_id"]:
        raise HTTPException(status_code=403, detail="403 Forbidden")
    return serialize(d)


@api_router.patch("/refund-requests/{rid}/review")
async def review_refund(rid: str, body: dict, request: Request, user: dict = Depends(require_permission("refund.review"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if d["status"] not in ("CALCULATED",):
        raise HTTPException(status_code=400, detail="Status tidak valid untuk review")
    bank = body.get("bank") or {}
    tl = d.get("timeline", []) + [_timeline_entry(user, "Accounting Reviewed (submitted)", d["status"], "ACCOUNTING_REVIEWED", request, body.get("recommendation", ""))]
    await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {
        "bank": {"bank_name": bank.get("bank_name", ""), "account_number": bank.get("account_number", ""), "account_holder": bank.get("account_holder", "")},
        "supporting_documents": body.get("supporting_documents", d.get("supporting_documents", [])),
        "recommendation": body.get("recommendation", d.get("recommendation", "")),
        "status": "ACCOUNTING_REVIEWED", "timeline": tl}})
    await log_audit(user, "refund", "review", request, record_id=rid, new={"bank": bank})
    trigger_n8n("refund.submitted", {"refund_id": d["refund_number"], "booking_id": d["booking_id"], "customer_id": d.get("customer_id"), "proposed_refund": d.get("proposed_refund"), "currency": "IDR"})
    await _notify("Refund menunggu approval", f"{d['refund_number']} siap di-approve Super Admin", "/approvals", role="super_admin")
    return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))


@api_router.patch("/refund-requests/{rid}/approve")
async def approve_refund(rid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    action = (body.get("action") or "").upper()
    if action not in ("APPROVE", "REJECT", "REQUEST_REVISION"):
        raise HTTPException(status_code=400, detail="Invalid action")
    if d["status"] not in ("ACCOUNTING_REVIEWED",):
        raise HTTPException(status_code=400, detail="Refund harus melalui Accounting Review dulu")
    old = d["status"]
    if action == "REJECT":
        reason = body.get("reason", "")
        if not reason:
            raise HTTPException(status_code=400, detail="Rejection reason wajib diisi")
        tl = d.get("timeline", []) + [_timeline_entry(user, "Refund Rejected", old, "REJECTED", request, reason)]
        await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {"status": "REJECTED", "approval": {"action": "REJECT", "by": user["name"], "at": now_iso(), "reason": reason}, "timeline": tl}})
        await log_audit(user, "refund", "reject", request, record_id=rid, new={"reason": reason})
        trigger_n8n("refund.rejected", {"refund_id": d["refund_number"], "booking_id": d["booking_id"], "customer_id": d.get("customer_id"), "reason": reason})
        await _notify("Refund ditolak", f"{d['refund_number']}: {reason}", "/approvals", role="accounting")
        return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))
    if action == "REQUEST_REVISION":
        tl = d.get("timeline", []) + [_timeline_entry(user, "Revision Requested", old, "CALCULATED", request, body.get("reason", ""))]
        await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {"status": "CALCULATED", "timeline": tl}})
        await log_audit(user, "refund", "request_revision", request, record_id=rid)
        await _notify("Revisi refund diminta", f"{d['refund_number']} perlu revisi", "/approvals", role="accounting")
        return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))
    proposed = float(body.get("proposed_refund", d.get("proposed_refund", 0)) or 0)
    if body.get("proposed_refund") is not None and abs(proposed - float(d.get("proposed_refund") or 0)) > 0.5 and not body.get("adjustment_reason"):
        raise HTTPException(status_code=400, detail="Adjustment reason wajib jika mengubah nominal refund")
    versions = d.get("versions", [])
    if abs(proposed - float(d.get("proposed_refund") or 0)) > 0.5:
        versions = versions + [_refund_version(d, body.get("adjustment_reason", "Super Admin adjustment"), user["name"], proposed)]
    tl = d.get("timeline", []) + [_timeline_entry(user, "Refund Approved", old, "APPROVED", request, "", proposed)]
    await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {"status": "APPROVED", "proposed_refund": proposed, "approved_refund": proposed,
        "approval": {"action": "APPROVE", "by": user["name"], "at": now_iso(), "proposed_refund": proposed, "adjustment_reason": body.get("adjustment_reason", "")}, "versions": versions, "timeline": tl}})
    await log_audit(user, "refund", "approve", request, record_id=rid, new={"approved_refund": proposed})
    trigger_n8n("refund.approved", {"refund_id": d["refund_number"], "booking_id": d["booking_id"], "customer_id": d.get("customer_id"), "approved_refund": proposed, "total_deduction": d.get("total_deduction"), "currency": "IDR"})
    await _notify("Refund disetujui", f"{d['refund_number']} disetujui. Accounting dapat memproses pembayaran.", "/approvals", role="accounting")
    await _notify("Refund disetujui", f"{d['refund_number']} disetujui Super Admin", "/approvals", user_id=d.get("sales_pic_id"))
    return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))


@api_router.post("/refund-requests/{rid}/process")
async def process_refund(rid: str, body: dict, request: Request, user: dict = Depends(require_permission("refund.process"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if d["status"] not in ("APPROVED", "PROCESSING", "PARTIALLY_REFUNDED"):
        raise HTTPException(status_code=403, detail="403 Forbidden — Refund belum disetujui Super Admin")
    amount = float(body.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount tidak valid")
    approved = float(d.get("approved_refund") or d.get("proposed_refund") or 0)
    already = float(d.get("refunded_amount") or 0)
    if already + amount > approved + 0.5:
        raise HTTPException(status_code=400, detail=f"Pembayaran melebihi approved refund (sisa Rp {approved - already:,.0f}). Ajukan revisi ke Super Admin.".replace(",", "."))
    payment = {"payment_date": body.get("payment_date", today_str()), "amount": amount,
               "bank": body.get("bank", ""), "account": body.get("account", ""),
               "transaction_reference": body.get("transaction_reference", ""),
               "proof_url": body.get("proof_url", ""), "notes": body.get("notes", ""),
               "processed_by": user["name"], "processed_at": now_iso()}
    refunded = already + amount
    new_status = "REFUNDED" if refunded >= approved - 0.5 else "PARTIALLY_REFUNDED"
    tl = d.get("timeline", []) + [_timeline_entry(user, "Payment Processed", d["status"], new_status, request, "", amount)]
    await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$push": {"payments": payment},
        "$set": {"refunded_amount": refunded, "status": new_status, "timeline": tl}})
    await db.refunds.insert_one({"amount": amount, "reason": f"Refund {d['refund_number']} • {d['booking_number']}",
        "method": body.get("bank", ""), "date": payment["payment_date"], "status": "PAID",
        "refund_request_id": rid, "created_at": now_iso(), "created_by": user["name"]})
    await log_audit(user, "refund", "process", request, record_id=rid, new={"amount": amount, "status": new_status})
    trigger_n8n("refund.processing" if new_status == "PARTIALLY_REFUNDED" else "refund.completed", {"refund_id": d["refund_number"], "booking_id": d["booking_id"], "customer_id": d.get("customer_id"), "paid": amount, "refunded_total": refunded, "status": new_status, "currency": "IDR"})
    if new_status == "PARTIALLY_REFUNDED":
        trigger_n8n("refund.partially_paid", {"refund_id": d["refund_number"], "booking_id": d["booking_id"], "customer_id": d.get("customer_id"), "refunded_total": refunded, "currency": "IDR"})
    await _notify("Refund diproses", f"{d['refund_number']} • Rp {amount:,.0f} ({new_status})".replace(",", "."), "/approvals", role="super_admin")
    await _notify("Refund diproses", f"{d['refund_number']} telah diproses", "/approvals", user_id=d.get("sales_pic_id"))
    return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))


@api_router.post("/refund-requests/{rid}/reopen")
async def reopen_refund(rid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    tl = d.get("timeline", []) + [_timeline_entry(user, "Reopened", d["status"], "CALCULATED", request)]
    await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {"status": "CALCULATED", "timeline": tl}})
    await log_audit(user, "refund", "reopen", request, record_id=rid)
    return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))


# ---------- PHASE 4B — Deduction Types, Deductions, Adjustment, Policy, Impact, Reports ----------
@api_router.get("/deduction-types")
async def list_deduction_types(user: dict = Depends(require_permission("refund.view"))):
    return [serialize(d) for d in await db.deduction_types.find().sort("name", 1).to_list(200)]


@api_router.post("/deduction-types")
async def create_deduction_type(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name wajib diisi")
    if await db.deduction_types.find_one({"name": name}):
        raise HTTPException(status_code=400, detail="Type sudah ada")
    res = await db.deduction_types.insert_one({"name": name, "system": False, "created_at": now_iso(), "created_by": user["name"]})
    await log_audit(user, "deduction_type", "create", request, record_id=str(res.inserted_id), new={"name": name})
    return serialize(await db.deduction_types.find_one({"_id": res.inserted_id}))


@api_router.delete("/deduction-types/{tid}")
async def delete_deduction_type(tid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    await db.deduction_types.delete_one({"_id": ObjectId(tid), "system": {"$ne": True}})
    await log_audit(user, "deduction_type", "delete", request, record_id=tid)
    return {"ok": True}


def _refund_editable(d):
    return d.get("status") in ("CALCULATED", "ACCOUNTING_REVIEWED")


@api_router.post("/refund-requests/{rid}/deductions")
async def add_refund_deduction(rid: str, body: dict, request: Request, user: dict = Depends(require_permission("refund.review"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if not _refund_editable(d):
        raise HTTPException(status_code=400, detail="Refund terkunci untuk perubahan deduction")
    method = body.get("method", "FIXED")
    qty = float(body.get("qty") or 1)
    unit = float(body.get("unit_amount") or 0)
    amount = _ded_amount(method, unit, qty, d.get("total_paid"))
    item = _ded_item(body.get("type", "Other"), body.get("description", ""), method, body.get("source", "Manual Adjustment"),
                     qty, unit, amount, body.get("non_refundable", False), body.get("traveler_id"), user["name"],
                     body.get("attachment_url", ""), body.get("notes", ""))
    d["deductions"] = d.get("deductions", []) + [item]
    total_ded, final, warning = _recalc_refund(d)
    versions = d.get("versions", []) + [_refund_version(d, f"Add deduction {item['type']}", user["name"], final)]
    await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {"deductions": d["deductions"], "total_deduction": total_ded, "proposed_refund": final, "versions": versions}})
    await log_audit(user, "refund", "add_deduction", request, record_id=rid, new={"type": item["type"], "amount": amount})
    return {**serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)})), "warning": warning}


@api_router.delete("/refund-requests/{rid}/deductions/{item_id}")
async def remove_refund_deduction(rid: str, item_id: str, request: Request, user: dict = Depends(require_permission("refund.review"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if not _refund_editable(d):
        raise HTTPException(status_code=400, detail="Refund terkunci")
    d["deductions"] = [x for x in d.get("deductions", []) if x.get("id") != item_id]
    total_ded, final, _w = _recalc_refund(d)
    versions = d.get("versions", []) + [_refund_version(d, "Remove deduction", user["name"], final)]
    await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {"deductions": d["deductions"], "total_deduction": total_ded, "proposed_refund": final, "versions": versions}})
    await log_audit(user, "refund", "remove_deduction", request, record_id=rid)
    return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))


@api_router.patch("/refund-requests/{rid}/adjustment")
async def adjust_refund(rid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    reason = body.get("reason", "")
    if not reason:
        raise HTTPException(status_code=400, detail="Adjustment reason wajib diisi")
    d["refund_adjustment"] = float(body.get("refund_adjustment") or 0)
    total_ded, final, _w = _recalc_refund(d)
    versions = d.get("versions", []) + [_refund_version(d, f"Manual adjustment: {reason}", user["name"], final)]
    await db.refund_requests.update_one({"_id": ObjectId(rid)}, {"$set": {"refund_adjustment": d["refund_adjustment"], "adjustment_reason": reason, "proposed_refund": final, "versions": versions}})
    await log_audit(user, "refund", "adjustment", request, record_id=rid, new={"refund_adjustment": d["refund_adjustment"], "reason": reason})
    return serialize(await db.refund_requests.find_one({"_id": ObjectId(rid)}))


@api_router.get("/refund-requests/{rid}/impact")
async def refund_impact(rid: str, user: dict = Depends(require_permission("refund.view"))):
    d = await db.refund_requests.find_one({"_id": ObjectId(rid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    if user["role"] == "sales":
        raise HTTPException(status_code=403, detail="403 Forbidden — Sales tidak dapat melihat profitability/HPP")
    b = await db.bookings.find_one({"_id": ObjectId(d["booking_id"])}) if ObjectId.is_valid(d["booking_id"]) else None
    pkg = await db.packages.find_one({"_id": ObjectId(b["package_id"])}) if b and b.get("package_id") and ObjectId.is_valid(b["package_id"]) else None
    hpp = float((pkg or {}).get("total_cost") or (pkg or {}).get("hpp") or 0) * int((b or {}).get("pax") or 0)
    original_sales = float((b or {}).get("total") or 0)
    non_ref = sum(float(x.get("amount") or 0) for x in d.get("deductions", []) if x.get("non_refundable"))
    return {"original_sales": original_sales, "original_hpp": hpp, "original_gross_profit": original_sales - hpp,
            "refund": d.get("proposed_refund"), "non_refundable_cost": non_ref, "total_deduction": d.get("total_deduction"),
            "original_tax": d.get("original_tax"), "cancelled_tax": d.get("cancelled_tax"), "final_tax": d.get("final_tax"),
            "net_financial_impact": original_sales - hpp - float(d.get("proposed_refund") or 0)}


# Refund policy (per package / departure) — Super Admin
@api_router.get("/refund-policies/{scope}/{ref_id}")
async def get_refund_policy(scope: str, ref_id: str, user: dict = Depends(require_permission("refund.view"))):
    p = await db.refund_policies.find_one({"scope": scope, "ref_id": ref_id})
    return serialize(p) if p else {"scope": scope, "ref_id": ref_id, "items": []}


@api_router.put("/refund-policies/{scope}/{ref_id}")
async def set_refund_policy(scope: str, ref_id: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    await db.refund_policies.update_one({"scope": scope, "ref_id": ref_id}, {"$set": {"items": body.get("items", []), "updated_at": now_iso()}}, upsert=True)
    await log_audit(user, "refund_policy", "set", request, record_id=f"{scope}:{ref_id}", new={"items": len(body.get("items", []))})
    return serialize(await db.refund_policies.find_one({"scope": scope, "ref_id": ref_id}))


# Reports
@api_router.get("/refund-reports/summary")
async def report_refund_summary(user: dict = Depends(require_permission("refund.view"))):
    q = {"sales_pic_id": user["_id"]} if user["role"] == "sales" else {}
    rows = await db.refund_requests.find(q).to_list(5000)
    total_req = sum(float(r.get("proposed_refund") or 0) for r in rows)
    total_appr = sum(float(r.get("approved_refund") or 0) for r in rows if r.get("status") in ("APPROVED", "PROCESSING", "PARTIALLY_REFUNDED", "REFUNDED"))
    total_paid = sum(float(r.get("refunded_amount") or 0) for r in rows)
    total_ded = sum(float(r.get("total_deduction") or 0) for r in rows)
    total_fee = sum(float(r.get("cancellation_fee") or 0) for r in rows)
    total_nonref = sum(float(r.get("non_refundable_cost") or 0) for r in rows)
    return {"count": len(rows), "total_refund_requested": total_req, "total_refund_approved": total_appr,
            "total_refund_paid": total_paid, "outstanding_refund": total_appr - total_paid,
            "total_deduction": total_ded, "total_cancellation_fee": total_fee, "total_non_refundable_cost": total_nonref}


@api_router.get("/refund-reports/deduction-breakdown")
async def report_deduction_breakdown(user: dict = Depends(require_permission("refund.view"))):
    q = {"sales_pic_id": user["_id"]} if user["role"] == "sales" else {}
    rows = await db.refund_requests.find(q).to_list(5000)
    agg = {}
    for r in rows:
        for x in r.get("deductions", []):
            agg[x.get("type", "Other")] = agg.get(x.get("type", "Other"), 0) + float(x.get("amount") or 0)
    return {"breakdown": [{"type": k, "amount": v} for k, v in sorted(agg.items(), key=lambda i: -i[1])]}


@api_router.get("/sales-dashboard")
async def sales_dashboard_v2(sales_id: Optional[str] = None, user: dict = Depends(require_permission("sales.view"))):
    if user["role"] == "super_admin":
        base = {"sales_pic_id": sales_id} if sales_id else {}
    else:
        base = {"sales_pic_id": user["_id"]}
    leads = await db.leads.find(base).to_list(5000)
    quotes = await db.quotations.find(base).to_list(5000)
    bookings = await db.bookings.find(base).to_list(5000)
    fups = await db.follow_ups.find(base).to_list(5000)

    def cnt(items, pred):
        return sum(1 for x in items if pred(x))
    active_stages = {"NEW", "CONTACTED", "QUALIFIED", "QUOTATION", "NEGOTIATION", "BOOKING"}
    total_q = len(quotes)
    converted_q = cnt(quotes, lambda q: q.get("status") == "ACCEPTED" or q.get("converted_booking_id"))
    outstanding_q = cnt(quotes, lambda q: q.get("status") in ("DRAFT", "SENT"))
    total_pax = sum(int(b.get("pax") or 0) for b in bookings if b.get("status") != "CANCELLED")
    total_sales = sum(float(b.get("total") or 0) for b in bookings if b.get("status") != "CANCELLED")
    today = today_str()

    def fu_stat(f):
        if f.get("status") == "completed":
            return "completed"
        dd = (f.get("due_date") or "")[:10]
        if not dd:
            return "upcoming"
        return "overdue" if dd < today else ("due_today" if dd == today else "upcoming")
    fu_counts = {"due_today": 0, "upcoming": 0, "overdue": 0, "completed": 0}
    for f in fups:
        fu_counts[fu_stat(f)] += 1

    # trends (last 6 months)
    from datetime import date
    months = []
    y, m = date.fromisoformat(today).year, date.fromisoformat(today).month
    for i in range(5, -1, -1):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append(f"{yy:04d}-{mm:02d}")
    sales_trend, booking_trend, pax_trend = [], [], []
    for mo in months:
        mb = [b for b in bookings if (b.get("created_at") or "")[:7] == mo and b.get("status") != "CANCELLED"]
        sales_trend.append({"month": mo, "value": sum(float(b.get("total") or 0) for b in mb)})
        booking_trend.append({"month": mo, "count": len(mb)})
        pax_trend.append({"month": mo, "pax": sum(int(b.get("pax") or 0) for b in mb)})

    # lead funnel
    order = ["QUALIFIED", "QUOTATION", "NEGOTIATION", "BOOKING", "PAID"]
    idx = {s: i for i, s in enumerate(LEAD_STAGES)}
    funnel = [{"stage": "Lead", "count": len(leads)}]
    for s in order:
        si = idx.get(s, 99)
        funnel.append({"stage": s.title(), "count": cnt(leads, lambda x: idx.get(x.get("status"), -1) >= si and x.get("status") != "LOST")})

    # package performance
    perf = {}
    for lst, key in ((leads, "lead"), (quotes, "quotation"), (bookings, "booking")):
        for x in lst:
            name = x.get("package_name") or x.get("interested_package") or "—"
            perf.setdefault(name, {"package": name, "lead": 0, "quotation": 0, "booking": 0, "pax": 0, "sales_value": 0})
            perf[name][key] += 1
            if key == "booking" and x.get("status") != "CANCELLED":
                perf[name]["pax"] += int(x.get("pax") or 0)
                perf[name]["sales_value"] += float(x.get("total") or 0)
    package_performance = sorted(perf.values(), key=lambda p: -p["sales_value"])[:10]

    # lead source
    src = {}
    for x in leads:
        s = x.get("source") or "Other"
        src[s] = src.get(s, 0) + 1
    lead_source = [{"source": k, "count": v} for k, v in sorted(src.items(), key=lambda i: -i[1])]

    # commission (current month)
    now = datetime.now(timezone.utc)
    period = f"{now.year:04d}-{now.month:02d}"
    comm_sid = sales_id if (user["role"] == "super_admin" and sales_id) else (None if user["role"] == "super_admin" else user["_id"])
    try:
        clines, _ = await _compute_period(period, only_sales_id=comm_sid)
    except Exception:
        clines = []
    cur = clines[0] if clines else {"total_pax": 0, "tier": "-", "total_commission": 0}
    lq = {"sales_pic_id": comm_sid} if comm_sid else {}
    approved_c = paid_c = 0
    for ln in await db.commission_lines.find(lq).to_list(2000):
        clo = await db.commission_closings.find_one({"period": ln["period"]})
        st = (clo or {}).get("status")
        if st in ("APPROVED", "CLOSED", "PAID"):
            approved_c += float(ln.get("final_commission") or 0)
        if ln.get("payment_status") == "PAID":
            paid_c += float(ln.get("final_commission") or 0)

    # payment outstanding: invoices with outstanding balance in scope
    b_ids = [str(b["_id"]) for b in bookings if b.get("status") != "CANCELLED"]
    payment_outstanding = await db.invoices.count_documents({"booking_id": {"$in": b_ids}, "outstanding": {"$gt": 0}}) if b_ids else 0

    return {
        "kpi": {
            "lead": {"new": cnt(leads, lambda x: x.get("status") == "NEW"),
                     "active": cnt(leads, lambda x: x.get("status") in active_stages),
                     "qualified": cnt(leads, lambda x: x.get("status") == "QUALIFIED"),
                     "lost": cnt(leads, lambda x: x.get("status") == "LOST")},
            "quotation": {"total": total_q, "outstanding": outstanding_q, "converted": converted_q,
                          "conversion_rate": round(converted_q / total_q * 100, 1) if total_q else 0},
            "booking": {"total": len([b for b in bookings if b.get("status") != "CANCELLED"]), "total_pax": total_pax, "total_sales": total_sales},
            "follow_up": fu_counts,
            "commission": {"current_pax": cur.get("total_pax", 0), "tier": cur.get("tier", "-"),
                           "estimated": cur.get("total_commission", 0), "approved": approved_c, "paid": paid_c},
        },
        "outstanding": {
            "leads_no_followup": cnt(leads, lambda x: not x.get("next_follow_up") and x.get("status") not in ("PAID", "COMPLETED", "LOST")),
            "quotation_outstanding": outstanding_q,
            "booking_outstanding": cnt(bookings, lambda b: b.get("status") in ("PENDING",)),
            "payment_outstanding": payment_outstanding,
            "upcoming_departure": cnt(bookings, lambda b: (b.get("departure_date") or "") >= today and b.get("status") not in ("CANCELLED",)),
        },
        "trends": {"sales": sales_trend, "booking": booking_trend, "pax": pax_trend},
        "funnel": funnel, "package_performance": package_performance, "lead_source": lead_source,
        "period": period,
    }


@api_router.get("/accounting-dashboard")
async def accounting_dashboard(user: dict = Depends(require_permission("accounting.view"))):
    from datetime import date
    invoices = await db.invoices.find({}).to_list(10000)
    payments = await db.payments.find({}).to_list(20000)
    expenses = await db.expenses.find({}).to_list(10000)
    refunds = await db.refund_requests.find({}).to_list(5000)
    clines = await db.commission_lines.find({}).to_list(5000)
    today = today_str()
    td = date.fromisoformat(today)

    revenue = sum(float(i.get("total") or 0) for i in invoices)
    dpp = sum(float(i.get("amount") or 0) for i in invoices)
    ppn = sum(float(i.get("tax_amount") or 0) for i in invoices)
    payment_received = sum(float(p.get("amount") or 0) for p in payments)

    def psum(t):
        return sum(float(p.get("amount") or 0) for p in payments if (p.get("payment_type") or p.get("type") or "").upper().startswith(t))
    dp_recv, inst_recv, final_recv = psum("DP"), psum("INSTALL"), psum("FINAL")

    expense_total = sum(float(e.get("amount") or 0) for e in expenses)

    def esum(cat):
        return sum(float(e.get("amount") or 0) for e in expenses if cat.lower() in (e.get("category") or "").lower())
    supplier_pay, operational = esum("supplier"), esum("operation")
    refund_paid = sum(float(r.get("refunded_amount") or 0) for r in refunds)
    commission_payable = sum(float(c.get("final_commission") or 0) for c in clines if c.get("payment_status") != "PAID")

    # receivable aging
    aging = {"current": 0.0, "d1_30": 0.0, "d31_60": 0.0, "d61_90": 0.0, "d90": 0.0}
    total_receivable = 0.0
    for i in invoices:
        out = float(i.get("outstanding") or 0)
        if out <= 0 or i.get("status") == "Paid":
            continue
        total_receivable += out
        dd = (i.get("due_date") or "")[:10]
        days = (td - date.fromisoformat(dd)).days if dd else 0
        if days <= 0:
            aging["current"] += out
        elif days <= 30:
            aging["d1_30"] += out
        elif days <= 60:
            aging["d31_60"] += out
        elif days <= 90:
            aging["d61_90"] += out
        else:
            aging["d90"] += out

    def rsum(statuses):
        return sum(float(r.get("proposed_refund") or 0) for r in refunds if r.get("status") in statuses)
    refund_block = {
        "requested": len(refunds),
        "pending_approval": len([r for r in refunds if r.get("status") in ("CALCULATED", "ACCOUNTING_REVIEWED")]),
        "approved": rsum(("APPROVED", "PROCESSING", "PARTIALLY_REFUNDED", "REFUNDED")),
        "paid": refund_paid,
        "outstanding": rsum(("APPROVED", "PROCESSING", "PARTIALLY_REFUNDED")) - refund_paid,
    }

    # payment status counts
    ps = {"Paid": 0, "Partial": 0, "Unpaid": 0, "Overdue": 0}
    for i in invoices:
        st = i.get("status", "Unpaid")
        dd = (i.get("due_date") or "")[:10]
        if st != "Paid" and dd and dd < today:
            ps["Overdue"] += 1
        ps[st if st in ps else "Unpaid"] = ps.get(st if st in ps else "Unpaid", 0) + 1

    # trends 6 months
    months = []
    y, m = td.year, td.month
    for i in range(5, -1, -1):
        mm, yy = m - i, y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append(f"{yy:04d}-{mm:02d}")
    cash_in, cash_out = [], []
    for mo in months:
        ci = sum(float(p.get("amount") or 0) for p in payments if (p.get("payment_date") or "")[:7] == mo)
        co = sum(float(e.get("amount") or 0) for e in expenses if (e.get("date") or e.get("created_at") or "")[:7] == mo)
        cash_in.append({"month": mo, "value": ci})
        cash_out.append({"month": mo, "value": co})

    rev_pkg = {}
    for i in invoices:
        n = i.get("package_name") or "—"
        rev_pkg[n] = rev_pkg.get(n, 0) + float(i.get("total") or 0)
    revenue_by_package = sorted([{"package": k, "value": v} for k, v in rev_pkg.items()], key=lambda x: -x["value"])[:8]

    exp_cat = {}
    for e in expenses:
        c = e.get("category") or "Other"
        exp_cat[c] = exp_cat.get(c, 0) + float(e.get("amount") or 0)
    expense_breakdown = [{"category": k, "value": v} for k, v in sorted(exp_cat.items(), key=lambda x: -x[1])]

    return {
        "money_in": {"revenue": revenue, "invoice": revenue, "payment_received": payment_received,
                     "dp_received": dp_recv, "installment_received": inst_recv, "final_received": final_recv},
        "money_out": {"expense": expense_total, "supplier_payment": supplier_pay, "refund": refund_paid,
                      "commission_payable": commission_payable, "operational_expense": operational},
        "receivable": {"total": total_receivable, **aging},
        "refund": refund_block,
        "tax": {"dpp": dpp, "ppn": ppn, "pph": 0, "tax_payable": ppn},
        "trends": {"cash_in": cash_in, "cash_out": cash_out},
        "payment_status": ps, "revenue_by_package": revenue_by_package, "expense_breakdown": expense_breakdown,
        "outstanding": {
            "unpaid_invoice": len([i for i in invoices if i.get("status") == "Unpaid"]),
            "overdue_invoice": ps["Overdue"],
            "outstanding_receivable": total_receivable,
            "pending_refund": refund_block["pending_approval"],
            "pending_commission": len([c for c in clines if c.get("payment_status") != "PAID"]),
            "outstanding_supplier": supplier_pay,
            "tax_payable": ppn,
        },
        "period": f"{td.year:04d}-{td.month:02d}",
    }


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------------
# STARTUP: indexes + seed
# ----------------------------------------------------------------------------
async def seed():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.customers.create_index("sales_pic_id")
    await db.leads.create_index("sales_pic_id")
    await db.follow_ups.create_index("sales_pic_id")
    await db.packages.create_index("package_code")
    await db.departures.create_index("package_id")
    await db.package_itineraries.create_index("package_id")

    for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
        if not await db.role_permissions.find_one({"role": role}):
            await db.role_permissions.insert_one({"role": role, "permissions": perms})
        elif role != "super_admin":
            await db.role_permissions.update_one({"role": role}, {"$addToSet": {"permissions": {"$each": perms}}})

    seed_users = [
        {"email": os.environ["SUPER_ADMIN_EMAIL"], "password": os.environ["SUPER_ADMIN_PASSWORD"],
         "name": "Dedy Irawan", "username": "superadmin", "role": "super_admin", "phone": "+62 811 0000 001",
         "branch": "HQ Jakarta", "data_scope": "all"},
        {"email": os.environ["SALES_EMAIL"], "password": os.environ["SALES_PASSWORD"],
         "name": "Rina Sales", "username": "rina.sales", "role": "sales", "phone": "+62 811 0000 002",
         "branch": "Bandung", "data_scope": "own"},
        {"email": os.environ["SALES_B_EMAIL"], "password": os.environ["SALES_B_PASSWORD"],
         "name": "Andi Sales", "username": "andi.sales", "role": "sales", "phone": "+62 811 0000 004",
         "branch": "Surabaya", "data_scope": "own"},
        {"email": os.environ["ACCOUNTING_EMAIL"], "password": os.environ["ACCOUNTING_PASSWORD"],
         "name": "Budi Accounting", "username": "budi.acc", "role": "accounting", "phone": "+62 811 0000 003",
         "branch": "HQ Jakarta", "data_scope": "all"},
    ]
    for su in seed_users:
        existing = await db.users.find_one({"email": su["email"]})
        if not existing:
            await db.users.insert_one({
                "email": su["email"], "password_hash": hash_password(su["password"]),
                "name": su["name"], "username": su["username"], "role": su["role"],
                "phone": su["phone"], "branch": su["branch"], "data_scope": su["data_scope"],
                "status": "active", "created_at": datetime.now(timezone.utc).isoformat(),
            })
        elif not verify_password(su["password"], existing["password_hash"]):
            await db.users.update_one({"email": su["email"]}, {"$set": {"password_hash": hash_password(su["password"])}})

    if not await db.company_settings.find_one({"key": "company"}):
        await db.company_settings.insert_one({
            "key": "company", "company_name": "Safar Travel Indonesia", "logo": "",
            "address": "Jl. Sudirman No. 21, Jakarta Pusat", "phone": "+62 21 5000 1234",
            "email": "info@safartravel.co.id", "website": "www.safartravel.co.id",
            "npwp": "01.234.567.8-901.000", "nib": "1234567890123", "bank_account": "BSI 7001234567 a.n Safar Travel",
        })
    if not await db.system_settings.find_one({"key": "system"}):
        await db.system_settings.insert_one({"key": "system", "settings": {
            "numbering": {"quotation_prefix": "QT", "invoice_prefix": "INV", "receipt_prefix": "RCT"},
            "payment_methods": ["Bank Transfer", "Cash", "Virtual Account"],
            "lead_sources": ["Instagram", "WhatsApp", "Referral", "Walk-in"],
            "booking_sources": ["Direct", "Agent", "Online"],
            "customer_categories": ["Umrah", "Haji", "Tour", "Corporate"],
            "tax": {"ppn_percent": 11},
            "commission": {"default_percent": 2.5},
            "n8n": {"webhook_url": "", "enabled": False},
            "notification": {"email_enabled": True, "whatsapp_enabled": False},
            "category_tax": {"umroh_percent": 0, "tour_percent": 1.1, "umroh_plus_percent": 1.1},
            "login_page": DEFAULT_LOGIN_PAGE,
        }})

    # Phase 2 demo data (only if empty)
    if await db.customers.count_documents({}) == 0:
        sales = await db.users.find_one({"email": os.environ["SALES_EMAIL"]})
        if sales:
            sid = str(sales["_id"])
            sname = sales["name"]
            sbranch = sales.get("branch", "")
            demo_customers = [
                {"full_name": "Ahmad Fauzi", "whatsapp": "+62 812 3456 7890", "email": "ahmad.fauzi@gmail.com",
                 "gender": "Male", "city": "Bandung", "country": "Indonesia", "customer_type": "Umrah Customer",
                 "customer_source": "WhatsApp", "tags": ["hot-lead"], "notes": "Interested in Ramadhan Umrah."},
                {"full_name": "Siti Rahma", "whatsapp": "+62 813 2222 1111", "email": "siti.rahma@gmail.com",
                 "gender": "Female", "city": "Jakarta", "country": "Indonesia", "customer_type": "VIP",
                 "customer_source": "Referral", "tags": ["vip"], "notes": "Repeat customer, family of 5."},
                {"full_name": "Budi Santoso", "whatsapp": "+62 811 9999 0000", "email": "budi.s@gmail.com",
                 "gender": "Male", "city": "Surabaya", "country": "Indonesia", "customer_type": "Prospect",
                 "customer_source": "Instagram", "tags": [], "notes": "Asking about Turkey tour."},
            ]
            cust_ids = []
            for i, c in enumerate(demo_customers):
                c.update({"customer_code": f"CUST-{i + 1:05d}", "sales_pic_id": sid, "sales_pic_name": sname,
                          "branch": sbranch, "created_at": now_iso(), "created_by": sname})
                r = await db.customers.insert_one(c)
                cust_ids.append(str(r.inserted_id))
            demo_leads = [
                {"customer_id": cust_ids[0], "customer_name": "Ahmad Fauzi", "source": "WhatsApp",
                 "interested_package": "Umrah Reguler 9 Hari", "destination": "Makkah & Madinah", "pax": 2,
                 "budget": 55000000, "departure_date": (datetime.now(timezone.utc) + timedelta(days=45)).date().isoformat(),
                 "status": "QUALIFIED"},
                {"customer_id": cust_ids[1], "customer_name": "Siti Rahma", "source": "Referral",
                 "interested_package": "Umrah Plus Turki 12 Hari", "destination": "Makkah, Madinah, Istanbul", "pax": 5,
                 "budget": 192500000, "departure_date": (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                 "status": "QUOTATION"},
                {"customer_id": cust_ids[2], "customer_name": "Budi Santoso", "source": "Instagram",
                 "interested_package": "Turkey Tour 8 Hari", "destination": "Istanbul, Cappadocia", "pax": 2,
                 "budget": 40000000, "departure_date": (datetime.now(timezone.utc) + timedelta(days=60)).date().isoformat(),
                 "status": "NEW"},
            ]
            for i, l in enumerate(demo_leads):
                l.update({"lead_code": f"LEAD-{i + 1:05d}", "sales_pic_id": sid, "sales_pic_name": sname,
                          "branch": sbranch, "last_contact": now_iso(), "created_at": now_iso(), "next_follow_up": "", "notes": ""})
                await db.leads.insert_one(l)
            await db.follow_ups.insert_many([
                {"customer_id": cust_ids[0], "customer_name": "Ahmad Fauzi", "lead_id": None, "activity_type": "WhatsApp",
                 "due_date": today_str(), "notes": "Send Umrah brochure", "status": "pending",
                 "sales_pic_id": sid, "sales_pic_name": sname, "branch": sbranch, "created_at": now_iso()},
                {"customer_id": cust_ids[1], "customer_name": "Siti Rahma", "lead_id": None, "activity_type": "Call",
                 "due_date": (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat(), "notes": "Confirm payment",
                 "status": "pending", "sales_pic_id": sid, "sales_pic_name": sname, "branch": sbranch, "created_at": now_iso()},
            ])

    await db.packages.update_many({"product_type": "UMRAH"}, {"$set": {"product_type": "UMROH"}})
    await db.system_settings.update_one(
        {"key": "system", "settings.category_tax": {"$exists": False}},
        {"$set": {"settings.category_tax": {"umroh_percent": 0, "tour_percent": 1.1, "umroh_plus_percent": 1.1}}})
    await db.packages.update_many({"sub_category": {"$exists": False}}, {"$set": {"sub_category": "OPEN_TRIP"}})
    await db.system_settings.update_one(
        {"key": "system", "settings.discount_approval": {"$exists": False}},
        {"$set": {"settings.discount_approval": {"sales_max_percent": 5, "approval_max_percent": 10}}})
    await db.system_settings.update_one(
        {"key": "system"},
        {"$set": {"settings.booking_sources": ["SALES", "AUTO SALES", "ADMIN", "AGENT", "PARTNER", "WEBSITE", "OTHER"],
                  "settings.numbering.booking_prefix": "BKG"}})
    await db.quotations.create_index("sales_pic_id")
    await db.bookings.create_index("sales_pic_id")
    await db.invoices.create_index("booking_id")
    await db.payments.create_index("invoice_id")
    await db.travelers.create_index("booking_id")
    await db.documents.create_index("traveler_id")
    await db.commission_schemes.create_index("status")
    await db.commission_closings.create_index("period", unique=True)
    await db.commission_lines.create_index("period")
    try:
        await db.commission_items.create_index([("booking_id", 1), ("traveler_id", 1), ("period", 1)], unique=True)
    except Exception:
        pass
    await db.system_settings.update_one(
        {"key": "system", "settings.commission.auto_sales_commission": {"$exists": False}},
        {"$set": {"settings.commission.auto_sales_commission": False}})
    await db.idempotency_keys.create_index("key", unique=True)
    await db.bookings.create_index("external_booking_id")
    await db.n8n_api_logs.create_index("timestamp")
    await db.cancellation_requests.create_index("booking_id")
    await db.cancellation_requests.create_index("status")
    await db.refund_requests.create_index("status")
    await db.notifications.create_index([("role", 1), ("created_at", -1)])
    if await db.deduction_types.count_documents({}) == 0:
        _defaults = ["Cancellation Fee", "Flight", "Hotel", "Visa", "Transport", "Handling", "Muthawwif",
                     "Guide", "Insurance", "Meal", "Airport Tax", "Supplier Cost", "Administration Fee", "Bank Fee", "Other"]
        await db.deduction_types.insert_many([{"name": n, "system": True, "created_at": now_iso()} for n in _defaults])
    await db.refund_policies.create_index([("scope", 1), ("ref_id", 1)])
    await db.commission_adjustments.create_index("period")
    if await db.tax_masters.count_documents({}) == 0:
        await db.tax_masters.insert_many([
            {"tax_code": "NONTAX", "tax_name": "Non Taxable", "tax_type": "OTHER", "rate": 0, "tax_base": "SELLING_PRICE",
             "effective_from": "2024-01-01", "effective_until": "", "treatment": "NON_TAXABLE", "tax_account": "",
             "description": "Umrah murni / non taxable", "active": True, "created_at": now_iso(), "created_by": "system"},
            {"tax_code": "PPN11", "tax_name": "PPN Standard 11%", "tax_type": "PPN", "rate": 11, "tax_base": "DPP",
             "effective_from": "2024-01-01", "effective_until": "", "treatment": "PPN_STANDARD", "tax_account": "2100",
             "description": "PPN standar", "active": True, "created_at": now_iso(), "created_by": "system"},
            {"tax_code": "PPN11T", "tax_name": "PPN Besaran Tertentu 1.1%", "tax_type": "PPN", "rate": 1.1, "tax_base": "SELLING_PRICE",
             "effective_from": "2024-01-01", "effective_until": "", "treatment": "PPN_TERTENTU", "tax_account": "2100",
             "description": "PPN besaran tertentu paket tour", "active": True, "created_at": now_iso(), "created_by": "system"},
            {"tax_code": "UMRPLUS", "tax_name": "Umrah Plus 1.1%", "tax_type": "PPN", "rate": 1.1, "tax_base": "TOUR_PORTION",
             "effective_from": "2024-01-01", "effective_until": "", "treatment": "UMRAH_PLUS", "tax_account": "2100",
             "description": "Umrah plus - porsi tour", "active": True, "created_at": now_iso(), "created_by": "system"},
        ])
    if await db.packages.count_documents({}) == 0:
        umrah = {
            "package_code": "UMR-0001", "package_name": "Umrah Reguler 9 Hari", "product_type": "UMRAH",
            "category": "Umrah Regular", "destination": "Makkah & Madinah", "country": "Saudi Arabia",
            "duration": "9 Days", "description": "Paket umrah reguler 9 hari dengan hotel dekat Masjid.",
            "cover_image": "", "gallery": [], "min_pax": 4, "max_pax": 45,
            "selling_price": 27500000, "child_price": 25000000, "infant_price": 5000000, "single_supplement": 6000000,
            "currency": "IDR", "tax_treatment": "Non-PPN", "commission_eligibility": True, "status": "ACTIVE",
            "promo_text": "Early bird diskon Rp1jt", "terms": "DP 50%, pelunasan H-30.", "version": 1,
            "umrah": {"makkah_hotel": "Fairmont Makkah", "madinah_hotel": "Anwar Al Madinah Movenpick",
                      "makkah_nights": 4, "madinah_nights": 3, "airline": "Saudia", "visa": "Umrah Visa",
                      "transport": "Bus VIP", "handling": "Included", "muthawwif": "Included", "manasik": "2x",
                      "zamzam": "5L", "insurance": "Included", "baggage": "23kg + 7kg", "room_type": "QUAD"},
            "hpp": 22500000, "total_cost": 22500000, "cost_per_pax": 22500000, "gross_profit": 5000000, "gross_margin": 18.18,
            "created_at": now_iso(), "created_by": "System",
        }
        tour = {
            "package_code": "TOUR-0001", "package_name": "Turkey Tour 8 Hari", "product_type": "TOUR",
            "category": "Turkey", "destination": "Istanbul & Cappadocia", "country": "Turkey",
            "duration": "8 Days", "description": "Explore Istanbul, Cappadocia, and Bursa.",
            "cover_image": "", "gallery": [], "min_pax": 2, "max_pax": 30,
            "selling_price": 20000000, "child_price": 18000000, "infant_price": 3000000, "single_supplement": 4500000,
            "currency": "IDR", "tax_treatment": "Non-PPN", "commission_eligibility": True, "status": "ACTIVE",
            "promo_text": "", "terms": "Non-refundable after ticketing.", "version": 1, "umrah": {},
            "hpp": 16000000, "total_cost": 16000000, "cost_per_pax": 16000000, "gross_profit": 4000000, "gross_margin": 20.0,
            "created_at": now_iso(), "created_by": "System",
        }
        u = await db.packages.insert_one(umrah)
        t = await db.packages.insert_one(tour)
        uid, tid = str(u.inserted_id), str(t.inserted_id)
        await db.package_costs.insert_many([
            {"package_id": uid, "components": {"flight": 12000000, "hotel": 6500000, "visa": 1500000, "transport": 1000000,
             "guide": 300000, "muthawwif": 400000, "handling": 300000, "meal": 500000, "insurance": 0, "other": 0},
             "total_cost": 22500000, "cost_per_pax": 22500000, "gross_profit": 5000000, "gross_margin": 18.18, "updated_at": now_iso()},
            {"package_id": tid, "components": {"flight": 9000000, "hotel": 4500000, "visa": 500000, "transport": 1200000,
             "guide": 800000, "muthawwif": 0, "handling": 0, "meal": 0, "insurance": 0, "other": 0},
             "total_cost": 16000000, "cost_per_pax": 16000000, "gross_profit": 4000000, "gross_margin": 20.0, "updated_at": now_iso()},
        ])
        await db.package_itineraries.insert_many([
            {"package_id": uid, "day": 1, "location": "Jakarta → Jeddah", "activity": "Keberangkatan & penerbangan",
             "hotel": "In-flight", "meal": "Dinner", "transport": "Flight", "flight": "SV817", "description": "Berkumpul di bandara.", "notes": "", "images": [], "created_at": now_iso()},
            {"package_id": uid, "day": 2, "location": "Makkah", "activity": "Umrah pertama",
             "hotel": "Fairmont Makkah", "meal": "Full board", "transport": "Bus", "flight": "", "description": "Tawaf & Sa'i.", "notes": "", "images": [], "created_at": now_iso()},
            {"package_id": tid, "day": 1, "location": "Istanbul", "activity": "City tour Sultanahmet",
             "hotel": "Istanbul Hotel", "meal": "Dinner", "transport": "Bus", "flight": "", "description": "Blue Mosque, Hagia Sophia.", "notes": "", "images": [], "created_at": now_iso()},
        ])
        await db.departures.insert_many([
            {"package_id": uid, "departure_date": (datetime.now(timezone.utc) + timedelta(days=40)).date().isoformat(),
             "return_date": (datetime.now(timezone.utc) + timedelta(days=49)).date().isoformat(), "quota": 45, "confirmed_pax": 30,
             "flight": "Saudia", "hotel": "Fairmont", "price": 27500000, "available_seat": 15, "status": "OPEN", "created_at": now_iso()},
            {"package_id": tid, "departure_date": (datetime.now(timezone.utc) + timedelta(days=60)).date().isoformat(),
             "return_date": (datetime.now(timezone.utc) + timedelta(days=67)).date().isoformat(), "quota": 30, "confirmed_pax": 28,
             "flight": "Turkish", "hotel": "Istanbul Hotel", "price": 20000000, "available_seat": 2, "status": "ALMOST FULL", "created_at": now_iso()},
        ])


@app.on_event("startup")
async def on_startup():
    await seed()
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    logger.info("Safar CRM startup: indexes + seed complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

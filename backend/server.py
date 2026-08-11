from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import logging
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
]

DEFAULT_ROLE_PERMISSIONS = {
    "super_admin": list(ALL_PERMISSIONS),
    "sales": [
        "dashboard.view", "crm.view", "sales.view", "packages.view",
        "departures.view", "commission.view", "notifications.view",
    ],
    "accounting": [
        "accounting.view", "transactions.view", "hpp.view", "tax.view",
        "commission.view", "reports.view", "reports.export", "notifications.view",
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
        active_users = await db.users.count_documents({"status": "active"})
        audit_count = await db.audit_logs.count_documents({})
        return {"role": role, "cards": [
            {"label": "Total Users", "value": total_users, "hint": "across all roles"},
            {"label": "Active Users", "value": active_users, "hint": "currently enabled"},
            {"label": "Audit Events", "value": audit_count, "hint": "logged actions"},
            {"label": "Active Bookings", "value": 128, "hint": "this month"},
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


@api_router.get("/notifications")
async def notifications(user: dict = Depends(require_permission("notifications.view"))):
    return [
        {"id": 1, "title": "Welcome to Safar CRM", "body": "Your account is ready.", "time": "just now"},
        {"id": 2, "title": "New departure added", "body": "Umrah Ramadhan 2026 is now live.", "time": "2h ago"},
    ]


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

    for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
        if not await db.role_permissions.find_one({"role": role}):
            await db.role_permissions.insert_one({"role": role, "permissions": perms})

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


@app.on_event("startup")
async def on_startup():
    await seed()
    logger.info("Safar CRM startup: indexes + seed complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

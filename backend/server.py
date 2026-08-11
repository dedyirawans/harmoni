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


@api_router.get("/")
async def root():
    return {"message": "Safar Travel CRM API"}


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
        }})


@app.on_event("startup")
async def on_startup():
    await seed()
    logger.info("Safar CRM startup: indexes + seed complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

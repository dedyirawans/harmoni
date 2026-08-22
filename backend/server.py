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
from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends, BackgroundTasks, Query
import re
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
async def log_audit(user, module, action, request: Request, record_id=None, old=None, new=None, reason=None):
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
        "reason": reason,
        "session_id": request.headers.get("x-session-id") if request else None,
        "ip": request.client.host if request and request.client else None,
        "user_agent": request.headers.get("user-agent") if request else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.audit_logs.insert_one(doc)


MASTER_STATUSES = ["ACTIVE", "INACTIVE", "ARCHIVED"]


def serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
        doc["id"] = doc["_id"]
    if doc:
        for _k, _v in list(doc.items()):
            if isinstance(_v, ObjectId):
                doc[_k] = str(_v)
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
    title: Optional[str] = ""
    signature: Optional[str] = ""


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
    title: Optional[str] = None
    signature: Optional[str] = None


class MyProfileUpdate(BaseModel):
    signature: Optional[str] = None


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
    app_domain: Optional[str] = None


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


@api_router.put("/auth/me/profile")
async def update_my_profile(body: MyProfileUpdate, request: Request, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if updates:
        await db.users.update_one({"_id": ObjectId(user["_id"])}, {"$set": updates})
        await log_audit(user, "user", "update_profile", request, record_id=user["_id"],
                        new={k: (v if k != "signature" else "[signature]") for k, v in updates.items()})
    return serialize(await db.users.find_one({"_id": ObjectId(user["_id"])}))


# ----------------------------------------------------------------------------
# HOTEL MODULE — Agoda Affiliate Long Tail Search (foundation)
# ----------------------------------------------------------------------------
class HotelSettings(BaseModel):
    provider: str = "Agoda"
    site_id: Optional[str] = ""
    api_key: Optional[str] = ""
    endpoint: Optional[str] = "http://affiliateapi7643.agoda.com/affiliateservice/lt_v1"
    language: Optional[str] = "id-id"
    currency: Optional[str] = "IDR"
    active: bool = True


async def _hotel_settings_raw():
    doc = await db.company_settings.find_one({"key": "hotel_agoda"})
    return (doc or {}).get("settings", {}) if doc else {}


def _mask_key(k):
    if not k:
        return ""
    return ("•" * max(len(k) - 4, 0)) + k[-4:] if len(k) > 4 else "••••"


def _hotel_api_key(s):
    # Prefer encrypted-at-rest key; fall back to legacy plaintext for backward compat.
    if s.get("api_key_enc"):
        return _dec(s.get("api_key_enc"))
    return s.get("api_key", "")


def _hotel_settings_public(s):
    _k = _hotel_api_key(s)
    return {"provider": s.get("provider", "Agoda"), "site_id": s.get("site_id", ""),
            "api_key_masked": _mask_key(_k), "api_key_set": bool(_k),
            "endpoint": s.get("endpoint") or "http://affiliateapi7643.agoda.com/affiliateservice/lt_v1",
            "language": s.get("language", "id-id"), "currency": s.get("currency", "IDR"),
            "active": s.get("active", True)}


def _normalize_hotel(r):
    return {"hotelId": r.get("hotelId"), "hotelName": r.get("hotelName"), "roomtypeName": r.get("roomtypeName"),
            "starRating": r.get("starRating"), "reviewScore": r.get("reviewScore"), "reviewCount": r.get("reviewCount"),
            "currency": r.get("currency"), "dailyRate": r.get("dailyRate"), "crossedOutRate": r.get("crossedOutRate"),
            "discountPercentage": r.get("discountPercentage"), "imageURL": r.get("imageURL"), "landingURL": r.get("landingURL"),
            "includeBreakfast": r.get("includeBreakfast"), "freeWifi": r.get("freeWifi")}


# --- Hotel provider abstraction (future: add other providers without rebuilding CRM) ---
class HotelProvider:
    name = "generic"

    async def search(self, criteria, user, search_type, log_meta):
        raise NotImplementedError


class AgodaProvider(HotelProvider):
    name = "AGODA_API"

    async def search(self, criteria, user, search_type, log_meta):
        return await _agoda_call(criteria, user, search_type=search_type, log_meta=log_meta)


HOTEL_PROVIDERS = {"AGODA_API": AgodaProvider()}


def get_hotel_provider(name="AGODA_API"):
    return HOTEL_PROVIDERS.get(name, HOTEL_PROVIDERS["AGODA_API"])


def _nights_between(ci, co):
    from datetime import datetime as _dt
    try:
        return max((_dt.strptime(str(co), "%Y-%m-%d") - _dt.strptime(str(ci), "%Y-%m-%d")).days, 0)
    except Exception:
        return 0


def _hotel_item_snapshot(it: dict):
    """Freeze the hotel figures at quotation time so old quotations never depend on live API data."""
    it = it or {}
    ci, co = str(it.get("checkInDate") or ""), str(it.get("checkOutDate") or "")
    nights = _nights_between(ci, co)
    rooms = int(it.get("numberOfRooms") or 1)
    rate = float(it.get("dailyRate") or it.get("agoda_daily_rate") or 0)
    return {"hotelId": it.get("hotelId"), "hotelName": it.get("hotelName") or "Hotel",
            "roomtypeName": it.get("roomtypeName") or "", "checkInDate": ci, "checkOutDate": co,
            "nights": nights, "numberOfRooms": rooms,
            "numberOfAdults": int(it.get("numberOfAdults") or 1), "numberOfChildren": int(it.get("numberOfChildren") or 0),
            "currency": it.get("currency") or "IDR", "agoda_daily_rate": rate,
            "crossedOutRate": it.get("crossedOutRate"), "discountPercentage": it.get("discountPercentage"),
            "total": round(rate * nights * rooms), "landingURL": it.get("landingURL") or "",
            "imageURL": it.get("imageURL") or "", "includeBreakfast": it.get("includeBreakfast"),
            "freeWifi": it.get("freeWifi"), "source": it.get("source") or "AGODA_API", "added_at": now_iso()}


async def _hotel_log(user, req_type, search_type, params, status, ms, count, err_code=None, err_msg=None):
    safe = {k: v for k, v in (params or {}).items() if k not in ("api_key", "authorization", "site_id")}
    await db.hotel_api_logs.insert_one({
        "timestamp": now_iso(), "request_type": req_type, "search_type": search_type, "params": safe,
        "response_status": status, "response_time_ms": ms, "result_count": count,
        "error_code": err_code, "error_message": err_msg, "by": user.get("name") if user else None})


DEFAULT_HOTEL_ENDPOINT = "http://affiliateapi7643.agoda.com/affiliateservice/lt_v1"


def _hotel_user_msg(status, code=None):
    if code == "TIMEOUT":
        return "Pencarian hotel memakan waktu terlalu lama. Silakan coba lagi."
    return {400: "Permintaan pencarian tidak valid.",
            401: "Autentikasi layanan hotel gagal. Silakan hubungi administrator.",
            403: "Batas permintaan atau pembatasan akses layanan hotel.",
            404: "Data tidak ditemukan.",
            410: "Sumber daya sudah tidak tersedia lagi.",
            500: "Layanan hotel mengalami gangguan. Silakan coba lagi nanti.",
            503: "Layanan hotel sementara tidak tersedia. Silakan coba lagi nanti.",
            506: "Konfigurasi layanan hotel bermasalah."}.get(status, "Terjadi kesalahan pada layanan hotel.")


class HotelSearchRequest(BaseModel):
    searchType: str = "city"  # "city" | "hotel"
    cityId: Optional[int] = None
    hotelId: Optional[List[int]] = None
    checkInDate: str
    checkOutDate: str
    language: Optional[str] = None
    currency: Optional[str] = None
    sortBy: Optional[str] = None
    maxResult: Optional[int] = 30
    discountOnly: Optional[bool] = False
    minimumStarRating: Optional[float] = None
    minimumReviewScore: Optional[float] = None
    dailyRateMin: Optional[float] = None
    dailyRateMax: Optional[float] = None
    numberOfAdult: int = 2
    numberOfChildren: int = 0
    childrenAges: Optional[List[int]] = None
    customer_id: Optional[str] = None  # optional: log a "Hotel Search" activity to this customer's timeline


def _valid_ymd(d):
    from datetime import datetime as _dt
    try:
        _dt.strptime(d, "%Y-%m-%d")
        return True
    except Exception:
        return False


def _build_agoda_criteria(req: "HotelSearchRequest"):
    from datetime import date as _date
    if not _valid_ymd(req.checkInDate) or not _valid_ymd(req.checkOutDate):
        raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD.")
    if req.checkOutDate <= req.checkInDate:
        raise HTTPException(status_code=400, detail="Check-out harus setelah check-in.")
    if req.checkInDate < _date.today().isoformat():
        raise HTTPException(status_code=400, detail="Tanggal check-in tidak boleh di masa lalu.")
    ages = [int(a) for a in (req.childrenAges or [])]
    if int(req.numberOfChildren) != len(ages):
        raise HTTPException(status_code=400,
                            detail=f"Jumlah 'Children Ages' ({len(ages)}) harus sama dengan jumlah anak ({req.numberOfChildren}).")
    occ = {"numberOfAdult": max(int(req.numberOfAdult), 1), "numberOfChildren": int(req.numberOfChildren)}
    if ages:
        occ["childrenAges"] = ages
    additional = {"currency": req.currency or "IDR", "language": req.language or "id-id",
                  "maxResult": int(req.maxResult or 30), "discountOnly": bool(req.discountOnly),
                  "occupancy": occ}
    criteria = {"checkInDate": req.checkInDate, "checkOutDate": req.checkOutDate, "additional": additional}
    st = (req.searchType or "city").lower()
    if st == "hotel":
        ids = [int(h) for h in (req.hotelId or []) if str(h).strip() != ""]
        if not ids:
            raise HTTPException(status_code=400, detail="Minimal satu Hotel ID diperlukan untuk Hotel List Search.")
        criteria["hotelId"] = ids
        search_type = "hotel"
    else:
        if not req.cityId:
            raise HTTPException(status_code=400, detail="City ID diperlukan untuk City Search.")
        criteria["cityId"] = int(req.cityId)
        if req.sortBy:
            additional["sortBy"] = req.sortBy
        if req.minimumStarRating is not None:
            additional["minimumStarRating"] = float(req.minimumStarRating)
        if req.minimumReviewScore is not None:
            additional["minimumReviewScore"] = float(req.minimumReviewScore)
        dr = {}
        if req.dailyRateMin is not None:
            dr["minimum"] = float(req.dailyRateMin)
        if req.dailyRateMax is not None:
            dr["maximum"] = float(req.dailyRateMax)
        if dr:
            additional["dailyRate"] = dr
        search_type = "city"
    log_meta = {"searchType": search_type, "cityId": criteria.get("cityId"), "hotelId": criteria.get("hotelId"),
                "checkInDate": req.checkInDate, "checkOutDate": req.checkOutDate,
                "numberOfAdult": occ["numberOfAdult"], "numberOfChildren": occ["numberOfChildren"],
                "currency": additional["currency"], "language": additional["language"],
                "sortBy": additional.get("sortBy"), "discountOnly": additional["discountOnly"]}
    import json as _hj
    import hashlib as _hh
    cache_key = _hh.sha256(_hj.dumps({"c": criteria, "st": search_type}, sort_keys=True, default=str).encode()).hexdigest()
    return criteria, search_type, log_meta, cache_key


async def _hotel_cache_get(key):
    import time as _t
    doc = await db.hotel_search_cache.find_one({"key": key})
    if not doc:
        return None
    if _t.time() - float(doc.get("ts", 0)) > 600:  # 10-minute TTL
        return None
    return doc.get("payload")


async def _hotel_cache_set(key, payload):
    import time as _t
    await db.hotel_search_cache.update_one({"key": key},
                                           {"$set": {"key": key, "ts": _t.time(), "payload": payload}}, upsert=True)


async def _agoda_call(criteria, user, search_type="city", log_meta=None, req_type="SEARCH"):
    s = await _hotel_settings_raw()
    _api_key = _hotel_api_key(s)
    if not s.get("site_id") or not _api_key:
        raise HTTPException(status_code=400, detail="Kredensial Agoda belum diisi di API Settings.")
    if not s.get("active", True):
        raise HTTPException(status_code=400, detail="Hotel API status non-aktif.")
    endpoint = s.get("endpoint") or DEFAULT_HOTEL_ENDPOINT
    body = {"criteria": criteria}
    headers = {"Authorization": f"{s['site_id']}:{_api_key}", "Accept-Encoding": "gzip,deflate",
               "Content-Type": "application/json"}
    import time as _t
    t0 = _t.time()
    status_code, count, results, err_code, err_msg = 0, 0, [], None, None
    try:
        resp = _requests.post(endpoint, json=body, headers=headers, timeout=25)
        status_code = resp.status_code
        if status_code in (200, 206):
            try:
                data = resp.json()
            except Exception:
                data = {}
            raw = data.get("results") or data.get("Results") or []
            results = [_normalize_hotel(r) for r in raw]
            count = len(results)
        elif status_code == 204:
            err_msg = "No content"
        else:
            err_code = str(status_code)
            err_msg = _hotel_user_msg(status_code)
    except _requests.exceptions.Timeout:
        err_code = "TIMEOUT"
        err_msg = "Request timed out"
    except Exception as e:
        err_code = "EXC"
        err_msg = str(e)[:200]
    ms = int((_t.time() - t0) * 1000)
    await _hotel_log(user, req_type, search_type, log_meta or {}, status_code, ms, count, err_code, err_msg)
    return {"status": status_code, "count": count, "results": results, "error_code": err_code,
            "error_message": err_msg, "response_time_ms": ms}


@api_router.get("/hotel/settings")
async def hotel_get_settings(user: dict = Depends(require_role("super_admin"))):
    return _hotel_settings_public(await _hotel_settings_raw())


@api_router.put("/hotel/settings")
async def hotel_put_settings(body: HotelSettings, request: Request, user: dict = Depends(require_role("super_admin"))):
    cur = await _hotel_settings_raw()
    new = {**cur, "provider": body.provider, "site_id": (body.site_id or "").strip(),
           "endpoint": (body.endpoint or "").strip(), "language": body.language, "currency": body.currency,
           "active": body.active}
    if body.api_key:  # only overwrite when a new key is provided (encrypted at rest)
        new["api_key_enc"] = _enc(body.api_key.strip())
        new.pop("api_key", None)
    await db.company_settings.update_one({"key": "hotel_agoda"}, {"$set": {"settings": new}}, upsert=True)
    await log_audit(user, "hotel", "update_settings", request, new={"site_id": new.get("site_id"), "active": new.get("active")})
    return _hotel_settings_public(new)


@api_router.post("/hotel/test-connection")
async def hotel_test_connection(user: dict = Depends(require_role("super_admin"))):
    from datetime import date, timedelta as _td
    ci = (date.today() + _td(days=14)).isoformat()
    co = (date.today() + _td(days=15)).isoformat()
    req = HotelSearchRequest(searchType="city", cityId=9395, checkInDate=ci, checkOutDate=co, maxResult=1)
    try:
        criteria, st, meta, _ = _build_agoda_criteria(req)
        res = await _agoda_call(criteria, user, search_type=st, log_meta=meta, req_type="TEST")
    except HTTPException as e:
        return {"success": False, "message": "Agoda API connection failed.", "detail": e.detail}
    ok = res["status"] in (200, 202, 204, 206)
    return {"success": ok, "message": "Agoda API connection successful." if ok else "Agoda API connection failed.",
            "detail": {"status": res["status"], "error_code": res["error_code"], "error_message": res["error_message"],
                       "response_time_ms": res["response_time_ms"]}}


@api_router.post("/hotel/search")
async def hotel_search(req: HotelSearchRequest, user: dict = Depends(get_current_user)):
    criteria, search_type, log_meta, cache_key = _build_agoda_criteria(req)
    cached = await _hotel_cache_get(cache_key)
    if cached is not None:
        return {**cached, "cached": True}
    res = await _agoda_call(criteria, user, search_type=search_type, log_meta=log_meta, req_type="SEARCH")
    status = res["status"]
    if req.customer_id and ObjectId.is_valid(req.customer_id):
        dest = f"City {criteria.get('cityId')}" if search_type == "city" else f"Hotel {criteria.get('hotelId')}"
        await log_activity(req.customer_id, None, "hotel", f"Hotel Search — {dest}",
                           f"{req.checkInDate} → {req.checkOutDate} · {res['count']} hasil", user)
    out = {"results": res["results"], "count": res["count"], "status": status, "cached": False,
           "searchType": search_type, "error": False, "partial": False, "message": None}
    if status in (200, 206) and res["count"] > 0:
        if status == 206:
            out["partial"] = True
            out["message"] = "Sebagian hasil mungkin belum lengkap."
        await _hotel_cache_set(cache_key, out)
        return out
    if status in (200, 206, 204):
        out["message"] = "Tidak ada hotel untuk kriteria yang dipilih."
        return out
    # error path — return graceful 200 with user-friendly message; details live in API Logs
    out["error"] = True
    out["message"] = _hotel_user_msg(status, res["error_code"])
    return out


@api_router.get("/hotel/logs")
async def hotel_logs(user: dict = Depends(require_role("super_admin"))):
    return [serialize(d) for d in await db.hotel_api_logs.find({}).sort("timestamp", -1).to_list(200)]


@api_router.get("/hotel/search-history")
async def hotel_search_history(user: dict = Depends(get_current_user)):
    docs = await db.hotel_api_logs.find({"request_type": "SEARCH"}).sort("timestamp", -1).to_list(100)
    out = []
    for d in [serialize(x) for x in docs]:
        p = d.get("params") or {}
        out.append({"timestamp": d.get("timestamp"), "searchType": p.get("searchType"),
                    "cityId": p.get("cityId"), "hotelId": p.get("hotelId"),
                    "checkInDate": p.get("checkInDate"), "checkOutDate": p.get("checkOutDate"),
                    "numberOfAdult": p.get("numberOfAdult"), "numberOfChildren": p.get("numberOfChildren"),
                    "currency": p.get("currency"), "language": p.get("language"),
                    "result_count": d.get("result_count"), "response_status": d.get("response_status"),
                    "by": d.get("by")})
    return out


class HotelAddToQuotation(BaseModel):
    customer_id: Optional[str] = None
    new_customer: Optional[dict] = None   # {full_name, whatsapp, email} — create if no existing match
    quotation_id: Optional[str] = None    # append to this existing quotation
    package_id: Optional[str] = None      # optional package for a NEW quotation (else hotel-only)
    sales_pic_id: Optional[str] = None
    hotel: dict                           # hotel snapshot input (from search result + rooms)


async def _resolve_or_create_customer(body: "HotelAddToQuotation", user):
    cid = body.customer_id
    if cid and ObjectId.is_valid(cid):
        cust = await db.customers.find_one({"_id": ObjectId(cid)})
        if cust:
            return str(cust["_id"]), cust
    nc = body.new_customer or {}
    wa = str(nc.get("whatsapp") or "").strip()
    name = str(nc.get("full_name") or "").strip()
    # avoid duplicates: match on whatsapp, then exact name
    match = None
    if wa:
        match = await db.customers.find_one({"whatsapp": wa, "is_deleted": {"$ne": True}})
    if not match and name:
        match = await db.customers.find_one({"full_name": name, "is_deleted": {"$ne": True}})
    if match:
        return str(match["_id"]), match
    if not name:
        raise HTTPException(status_code=400, detail="Customer wajib dipilih atau isi nama customer baru.")
    pic_id, pic_name, branch = await resolve_pic(user, body.sales_pic_id)
    doc = {"full_name": name, "whatsapp": wa, "email": str(nc.get("email") or ""),
           "customer_type": "Prospect", "sales_pic_id": pic_id, "sales_pic_name": pic_name, "branch": branch,
           "is_deleted": False, "created_at": now_iso(), "created_by": user["name"]}
    r = await db.customers.insert_one(doc)
    return str(r.inserted_id), await db.customers.find_one({"_id": r.inserted_id})


@api_router.post("/hotel/add-to-quotation")
async def hotel_add_to_quotation(body: HotelAddToQuotation, request: Request,
                                 user: dict = Depends(require_permission("quotation.manage"))):
    cid, cust = await _resolve_or_create_customer(body, user)
    snap = _hotel_item_snapshot(body.hotel or {})
    if not snap.get("hotelName") or snap.get("nights", 0) <= 0:
        raise HTTPException(status_code=400, detail="Data hotel tidak lengkap (nama & tanggal check-in/out valid diperlukan).")
    if body.quotation_id and ObjectId.is_valid(body.quotation_id):
        q = await db.quotations.find_one({"_id": ObjectId(body.quotation_id)})
        if not q:
            raise HTTPException(status_code=404, detail="Quotation tidak ditemukan.")
        if not can_access_record(user, q):
            raise HTTPException(status_code=403, detail="403 Forbidden")
        items = (q.get("hotel_items") or []) + [snap]
        htotal = sum(float(x.get("total") or 0) for x in items)
        await db.quotations.update_one({"_id": q["_id"]}, {"$set": {
            "hotel_items": items, "hotel_total": htotal,
            "grand_total_with_hotel": float(q.get("total") or 0) + htotal}})
        qid, qnum = str(q["_id"]), q.get("quotation_number")
    else:
        settings = await get_settings_dict()
        pic_id, pic_name, branch = await resolve_pic(user, body.sales_pic_id)
        number = await next_number((settings.get("numbering") or {}).get("quotation_prefix", "QT"), db.quotations, "quotation_number")
        pax = snap["numberOfAdults"] + snap["numberOfChildren"]
        amt = {"per_pax_price": 0, "base_price": 0, "gross": 0, "addon_total": 0, "subtotal": 0,
               "discount_type": "PERCENT", "discount_value": 0, "discount_percent": 0, "discount_amount": 0,
               "tax_percent": 0, "tax_amount": 0, "total": 0}
        pkg_name, pkg_id = "(Hotel Only)", None
        if body.package_id and ObjectId.is_valid(body.package_id):
            pkg = await db.packages.find_one({"_id": ObjectId(body.package_id)})
            if pkg:
                amt = await _compute_quotation_amounts(pkg, max(pax, 1), [], "PERCENT", 0, settings)
                pkg_name, pkg_id = pkg["package_name"], body.package_id
        htotal = snap["total"]
        doc = {"quotation_number": number, "customer_id": cid, "customer_name": cust["full_name"],
               "package_id": pkg_id, "package_name": pkg_name, "package_version": 1, "departure_id": None,
               "lead_id": None, "pax": max(pax, 1), "room_type": "", "addons": [], **amt,
               "discount_status": "APPROVED", "discount_level": None, "status": "DRAFT", "notes": "", "terms": "",
               "hotel_items": [snap], "hotel_total": htotal, "grand_total_with_hotel": float(amt["total"]) + htotal,
               "sales_pic_id": pic_id, "sales_pic_name": pic_name, "branch": branch,
               "converted_booking_id": None, "created_at": now_iso(), "created_by": user["name"]}
        res = await db.quotations.insert_one(doc)
        qid, qnum = str(res.inserted_id), number
    await db.sales_activities.insert_one({
        "activity_type": "Hotel Added to Quotation", "customer_id": cid, "customer_name": cust.get("full_name", ""),
        "lead_id": None, "notes": f"{snap['hotelName']} · {snap['checkInDate']}→{snap['checkOutDate']} · {snap['nights']} malam × {snap['numberOfRooms']} kamar · Total {snap['total']} · Quotation {qnum}",
        "sales_pic_id": (user["_id"] if user["role"] == "sales" else cust.get("sales_pic_id")), "sales_pic_name": user["name"],
        "branch": user.get("branch"), "hotel": snap, "quotation_id": qid, "source": "AGODA_API", "timestamp": now_iso()})
    await log_activity(cid, None, "hotel", f"Hotel added to Quotation {qnum}",
                       f"{snap['hotelName']} — {snap['nights']} malam × {snap['numberOfRooms']} kamar (Total {snap['total']})", user)
    await log_audit(user, "hotel", "add_to_quotation", request, record_id=qid,
                    new={"quotation": qnum, "hotel": snap.get("hotelName")})
    return {"quotation_id": qid, "quotation_number": qnum, "customer_id": cid,
            "hotel_total": snap["total"], "grand_total_with_hotel": None}


@api_router.get("/hotel/stats")
async def hotel_stats(user: dict = Depends(require_permission("quotation.manage"))):
    log_q = {"request_type": "SEARCH"}
    if user["role"] == "sales":
        log_q["by"] = user["name"]
    searches = await db.hotel_api_logs.count_documents(log_q)
    q_scope = {**owner_filter(user), "hotel_items.0": {"$exists": True}}
    qs = await db.quotations.find(q_scope).to_list(5000)
    revenue = sum(float(q.get("hotel_total") or 0) for q in qs)
    return {"hotel_searches": searches, "hotel_quotations": len(qs), "hotel_revenue": round(revenue)}


@api_router.get("/hotel/cities")
async def hotel_cities_list(q: Optional[str] = None, limit: int = 30, user: dict = Depends(get_current_user)):
    """Autocomplete kota dari master data resmi Agoda (agoda_cities)."""
    limit = max(1, min(int(limit or 30), 50))
    if q and q.strip():
        term = q.strip().lower()
        _aliases = {"makkah": "mecca", "mekah": "mecca", "mekkah": "mecca", "makkatul": "mecca",
                    "madinah": "medina", "madina": "medina", "madinatul": "medina"}
        term = _aliases.get(term, term)
        term = re.escape(term)
        cur = db.agoda_cities.find({"name_lower": {"$regex": term}}).sort("count", -1).limit(limit)
    else:
        cur = db.agoda_cities.find({}).sort("count", -1).limit(limit)
    return [serialize(d) for d in await cur.to_list(limit)]


@api_router.get("/hotel/hotels/search")
async def hotel_hotels_search(q: Optional[str] = None, cityId: Optional[int] = None, limit: int = 20,
                              user: dict = Depends(get_current_user)):
    """Cari hotel by nama dari master data Agoda (agoda_hotels). Prefix match (index-backed)."""
    limit = max(1, min(int(limit or 20), 30))
    query = {}
    if cityId:
        query["cityId"] = int(cityId)
    if q and q.strip():
        query["name_lower"] = {"$regex": "^" + re.escape(q.strip().lower())}
    elif not cityId:
        return []
    cur = db.agoda_hotels.find(query).sort("reviewCount", -1).limit(limit)
    return [serialize(d) for d in await cur.to_list(limit)]


# ----------------------------------------------------------------------------
# USER MANAGEMENT (super admin)
# ----------------------------------------------------------------------------
@api_router.get("/users")
async def list_users(include_archived: bool = False, user: dict = Depends(require_permission("users.view"))):
    query = {} if include_archived else {"is_deleted": {"$ne": True}}
    users = await db.users.find(query).sort("created_at", -1).to_list(1000)
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
        "title": body.title or "", "signature": body.signature or "",
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
async def delete_user(user_id: str, request: Request, reason: str = Query(""), user: dict = Depends(require_role("super_admin"))):
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Reason is required to archive a user")
    existing = await db.users.find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    if str(existing["_id"]) == user["_id"]:
        raise HTTPException(status_code=400, detail="You cannot archive your own account")
    _summary = await _user_assigned_summary(user_id)
    if sum(_summary.values()) > 0:
        raise HTTPException(status_code=409, detail={
            "message": "User masih memiliki data yang ter-assign. Data harus dipindahkan ke user lain sebelum user dapat dihapus.",
            "summary": _summary})
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_deleted": True, "status": "ARCHIVED", "archived_by": user["name"], "archived_at": now_iso()}})
    await log_audit(user, "user", "archive_user", request, record_id=user_id, old=serialize(dict(existing)), new={"status": "ARCHIVED"}, reason=reason)
    return {"message": "User archived", "status": "ARCHIVED"}


@api_router.post("/users/{user_id}/restore")
async def restore_user(user_id: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    existing = await db.users.find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_deleted": False, "status": "active"}})
    await log_audit(user, "user", "restore_user", request, record_id=user_id, new={"status": "active"})
    return {"message": "User restored"}


_ASSIGN_OWNER_FIELDS = ["sales_pic_id", "assigned_to_id", "salesperson_id", "owner_id", "pic_id", "assigned_user_id"]
_ASSIGN_NAME_MAP = {"sales_pic_id": "sales_pic_name", "assigned_to_id": "assigned_to_name",
                    "salesperson_id": "salesperson_name", "owner_id": "owner_name", "pic_id": "pic_name",
                    "assigned_user_id": "assigned_user_name"}
_ASSIGN_COLLECTIONS = {"Customers": "customers", "Leads": "leads", "Orders": "orders", "Bookings": "bookings",
                       "Quotations": "quotations", "Follow Ups": "ai_followup_queue", "Tasks": "tasks",
                       "Forecasts": "forecasts", "Sales Activities": "sales_activities"}


async def _user_assigned_summary(uid: str):
    out = {}
    for label, coll in _ASSIGN_COLLECTIONS.items():
        q = {"is_deleted": {"$ne": True}, "$or": [{f: uid} for f in _ASSIGN_OWNER_FIELDS]}
        try:
            c = await db[coll].count_documents(q)
        except Exception:
            c = 0
        if c:
            out[label] = c
    return out


@api_router.get("/users/{user_id}/assigned-summary")
async def user_assigned_summary(user_id: str, user: dict = Depends(require_role("super_admin"))):
    return {"user_id": user_id, "summary": await _user_assigned_summary(user_id),
            "total": sum((await _user_assigned_summary(user_id)).values())}


@api_router.post("/users/{user_id}/reassign")
async def reassign_user_data(user_id: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    to_id = (body or {}).get("to_user_id")
    if not to_id or not ObjectId.is_valid(to_id) or to_id == user_id:
        raise HTTPException(status_code=400, detail="Pilih user tujuan yang valid (berbeda).")
    target = await db.users.find_one({"_id": ObjectId(to_id)})
    if not target or target.get("is_deleted"):
        raise HTTPException(status_code=404, detail="User tujuan tidak ditemukan")
    tname = target.get("name")
    moved = {}
    for label, coll in _ASSIGN_COLLECTIONS.items():
        n = 0
        for f in _ASSIGN_OWNER_FIELDS:
            try:
                r = await db[coll].update_many({f: user_id}, {"$set": {f: to_id, _ASSIGN_NAME_MAP.get(f, f + "_name"): tname}})
                n += r.modified_count
            except Exception:
                pass
        if n:
            moved[label] = n
    src = await db.users.find_one({"_id": ObjectId(user_id)})
    await db.reassign_audit.insert_one({"from_user_id": user_id, "from_user_name": (src or {}).get("name"),
        "to_user_id": to_id, "to_user_name": tname, "records_moved": moved,
        "total": sum(moved.values()), "performed_by": user["name"], "timestamp": now_iso()})
    await log_audit(user, "user", "reassign_user_data", request, record_id=user_id,
                    new={"to": tname, "moved": moved})
    return {"ok": True, "moved": moved, "total": sum(moved.values()), "to_user_name": tname}


@api_router.get("/customers/{cid}/audit")
async def get_customer_audit(cid: str, user: dict = Depends(require_permission("crm.view"))):
    logs = await db.customer_audit.find({"customer_id": cid}).sort("timestamp", -1).to_list(500)
    return [serialize(x) for x in logs]


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
async def get_audit_logs(module: Optional[str] = None, action: Optional[str] = None,
                         user_q: Optional[str] = None, date_from: Optional[str] = None,
                         date_to: Optional[str] = None, user: dict = Depends(require_permission("audit.view"))):
    query = {}
    if module and module != "all":
        query["module"] = module
    if action:
        query["action"] = {"$regex": action, "$options": "i"}
    if user_q:
        query["$or"] = [{"user_name": {"$regex": user_q, "$options": "i"}}, {"user_email": {"$regex": user_q, "$options": "i"}}]
    if date_from or date_to:
        tr = {}
        if date_from:
            tr["$gte"] = date_from
        if date_to:
            tr["$lte"] = date_to + "T23:59:59"
        query["timestamp"] = tr
    logs = await db.audit_logs.find(query).sort("timestamp", -1).to_list(1000)
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


# ----------------------------------------------------------------------------
# Phase 9N — Sales & Financial Forecasting (Super Admin only)
# ----------------------------------------------------------------------------
STAGE_PROBABILITY = {
    "NEW": 0.10, "CONTACTED": 0.20, "QUALIFIED": 0.30,
    "QUOTATION": 0.50, "NEGOTIATION": 0.70, "BOOKING": 0.90,
}


def _shift_month(y, m, k):
    idx = (y * 12 + (m - 1)) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


@api_router.get("/forecast/dashboard")
async def forecast_dashboard(user: dict = Depends(require_role("super_admin"))):
    now = datetime.now(timezone.utc)
    cur = _shift_month(now.year, now.month, 0)
    nxt = _shift_month(now.year, now.month, 1)
    m3 = [_shift_month(now.year, now.month, i) for i in range(3)]
    window = [_shift_month(now.year, now.month, i) for i in range(6)]

    leads = await db.leads.find({}).to_list(5000)
    quotes = await db.quotations.find({}).to_list(5000)
    bookings = await db.bookings.find({}).to_list(5000)
    invoices = await db.invoices.find({}).to_list(5000)
    payments = await db.payments.find({}).to_list(5000)
    sup_pays = await db.supplier_payments.find({}).to_list(5000)
    comm_items = await db.commission_items.find({}).to_list(5000)
    refunds = await db.refunds.find({}).to_list(5000)
    expenses = await db.expenses.find({}).to_list(5000)

    # ---------- 1) SALES FORECAST (weighted pipeline) ----------
    q_by_lead = {}
    for q in quotes:
        lid = q.get("lead_id")
        if lid:
            q_by_lead[lid] = q_by_lead.get(lid, 0) + float(q.get("total") or 0)
    pipeline = []
    for l in leads:
        st = l.get("status")
        if st not in STAGE_PROBABILITY:
            continue
        lid = str(l["_id"])
        deal = float(l.get("budget") or 0)
        if deal <= 0:
            deal = q_by_lead.get(lid, 0)
        prob = STAGE_PROBABILITY[st]
        close = (l.get("departure_date") or l.get("next_follow_up") or l.get("created_at") or "")[:7]
        pipeline.append({
            "lead_id": lid, "lead_code": l.get("lead_code"), "customer": l.get("customer_name"),
            "stage": st, "value": deal, "probability": prob, "weighted": round(deal * prob, 2),
            "close_month": close, "sales": l.get("sales_pic_name"),
        })
    pipeline_value = round(sum(p["value"] for p in pipeline), 2)
    weighted_value = round(sum(p["weighted"] for p in pipeline), 2)
    stage_summary = [{
        "stage": st, "probability": STAGE_PROBABILITY[st],
        "count": sum(1 for p in pipeline if p["stage"] == st),
        "value": round(sum(p["value"] for p in pipeline if p["stage"] == st), 2),
        "weighted": round(sum(p["weighted"] for p in pipeline if p["stage"] == st), 2),
    } for st in STAGE_PROBABILITY]

    def _bkt(months):
        ms = months if isinstance(months, list) else [months]
        return {
            "pipeline": round(sum(p["value"] for p in pipeline if p["close_month"] in ms), 2),
            "weighted": round(sum(p["weighted"] for p in pipeline if p["close_month"] in ms), 2),
        }

    # ACTUAL booked revenue (won) per month — from bookings created_at
    actual_by_month = {}
    for b in bookings:
        mk = (b.get("created_at") or "")[:7]
        actual_by_month[mk] = actual_by_month.get(mk, 0) + float(b.get("total") or 0)

    def _actual(months):
        ms = months if isinstance(months, list) else [months]
        return round(sum(v for k, v in actual_by_month.items() if k in ms), 2)

    sales_forecast = {
        "pipeline_value": pipeline_value,
        "weighted_value": weighted_value,
        "stage_summary": stage_summary,
        "buckets": {
            "current_month": {"label": cur, **_bkt(cur), "actual": _actual(cur)},
            "next_month": {"label": nxt, **_bkt(nxt), "actual": _actual(nxt)},
            "next_3_months": {"label": f"{m3[0]} → {m3[-1]}", "months": m3, **_bkt(m3), "actual": _actual(m3)},
        },
        "pipeline": sorted(pipeline, key=lambda p: -p["weighted"])[:30],
    }

    # ---------- 3) RECEIVABLE / CASH-IN FORECAST (payment schedule) ----------
    recv_items = []
    recv_by_month = {}
    for b in bookings:
        for it in (b.get("payment_schedule") or []):
            out = float(it.get("outstanding") or 0)
            if out <= 0 or it.get("status") == "PAID":
                continue
            mk = (it.get("due_date") or "")[:7]
            recv_by_month[mk] = recv_by_month.get(mk, 0) + out
            recv_items.append({
                "booking_number": b.get("booking_number"), "customer": b.get("customer_name"),
                "label": it.get("label"), "due_date": it.get("due_date"),
                "amount": round(out, 2), "status": it.get("status"),
            })
    total_receivable = round(sum(recv_by_month.values()), 2)
    receivable_forecast = {
        "total_outstanding": total_receivable,
        "by_month": [{"month": mk, "amount": round(recv_by_month.get(mk, 0), 2)} for mk in window],
        "items": sorted(recv_items, key=lambda x: x.get("due_date") or "")[:40],
    }

    # ---------- Upcoming COMMISSION (payable) ----------
    comm_by_month = {}
    comm_list = []
    for ci in comm_items:
        mk = (ci.get("payout_month") or ci.get("commission_month") or "")[:7]
        amt = float(ci.get("commission_amount") or 0)
        if amt <= 0:
            continue
        comm_by_month[mk] = comm_by_month.get(mk, 0) + amt
        comm_list.append({
            "sales": ci.get("sales_pic_name"), "customer": ci.get("customer_name"),
            "booking_number": ci.get("booking_number"), "payout_month": mk,
            "amount": round(amt, 2), "package": ci.get("package_name"),
        })
    upcoming_commission = {
        "total": round(sum(v for k, v in comm_by_month.items() if k >= cur), 2),
        "by_month": [{"month": mk, "amount": round(comm_by_month.get(mk, 0), 2)} for mk in window],
        "items": sorted([c for c in comm_list if c["payout_month"] >= cur], key=lambda x: x["payout_month"])[:40],
    }

    # ---------- Upcoming EXPENSE (supplier payment outstanding + refund pending) ----------
    sup_by_month, refund_by_month = {}, {}
    exp_items = []
    for sp in sup_pays:
        out = float(sp.get("amount") or 0) - float(sp.get("paid") or 0)
        if out <= 0:
            continue
        mk = (sp.get("due_date") or "")[:7]
        sup_by_month[mk] = sup_by_month.get(mk, 0) + out
        exp_items.append({
            "type": "SUPPLIER", "name": sp.get("supplier_name"), "invoice_number": sp.get("invoice_number"),
            "due_date": sp.get("due_date"), "amount": round(out, 2),
        })
    for r in refunds:
        if (r.get("status") or "").upper() != "PENDING":
            continue
        amt = float(r.get("amount") or 0)
        mk = (r.get("date") or r.get("created_at") or "")[:7]
        refund_by_month[mk] = refund_by_month.get(mk, 0) + amt
        exp_items.append({
            "type": "REFUND", "name": r.get("customer_name"), "invoice_number": r.get("reason"),
            "due_date": r.get("date"), "amount": round(amt, 2),
        })
    total_sup = round(sum(sup_by_month.values()), 2)
    total_refund_pending = round(sum(refund_by_month.values()), 2)
    upcoming_expense = {
        "total": round(total_sup + total_refund_pending, 2),
        "supplier_total": total_sup,
        "refund_total": total_refund_pending,
        "by_month": [{"month": mk, "supplier": round(sup_by_month.get(mk, 0), 2),
                      "refund": round(refund_by_month.get(mk, 0), 2),
                      "total": round(sup_by_month.get(mk, 0) + refund_by_month.get(mk, 0), 2)} for mk in window],
        "items": sorted(exp_items, key=lambda x: x.get("due_date") or "")[:40],
    }

    # ---------- 2) CASH FLOW FORECAST (In - Out per month) ----------
    cf_series = []
    for mk in window:
        cin = round(recv_by_month.get(mk, 0), 2)
        cout = round(sup_by_month.get(mk, 0) + refund_by_month.get(mk, 0) + comm_by_month.get(mk, 0), 2)
        cf_series.append({
            "month": mk, "cash_in": cin,
            "supplier": round(sup_by_month.get(mk, 0), 2),
            "commission": round(comm_by_month.get(mk, 0), 2),
            "refund": round(refund_by_month.get(mk, 0), 2),
            "cash_out": cout, "net": round(cin - cout, 2),
        })

    # ACTUAL current month (realized) — payments in, expenses/refunds paid out
    act_in = round(sum(float(p.get("amount") or 0) for p in payments if (p.get("payment_date") or p.get("created_at") or "")[:7] == cur), 2)
    act_exp = sum(float(e.get("amount") or 0) for e in expenses if (e.get("date") or e.get("created_at") or "")[:7] == cur)
    act_refund = sum(float(r.get("amount") or 0) for r in refunds if (r.get("status") or "").upper() == "PAID" and (r.get("date") or r.get("created_at") or "")[:7] == cur)
    act_sup_paid = sum(float(sp.get("paid") or 0) for sp in sup_pays if (sp.get("created_at") or sp.get("due_date") or "")[:7] == cur)
    act_out = round(act_exp + act_refund + act_sup_paid, 2)
    cash_flow_forecast = {
        "series": cf_series,
        "actual_current_month": {"month": cur, "cash_in": act_in, "cash_out": act_out, "net": round(act_in - act_out, 2)},
        "forecast_total_in": round(sum(s["cash_in"] for s in cf_series), 2),
        "forecast_total_out": round(sum(s["cash_out"] for s in cf_series), 2),
    }

    return {
        "generated_at": now_iso(),
        "probabilities": STAGE_PROBABILITY,
        "window": window,
        "sales_forecast": sales_forecast,
        "cash_flow_forecast": cash_flow_forecast,
        "receivable_forecast": receivable_forecast,
        "upcoming_expense": upcoming_expense,
        "upcoming_commission": upcoming_commission,
    }


# ----------------------------------------------------------------------------
# Phase 10E-2 — Manual Forecast CRUD (Super Admin only)
# ----------------------------------------------------------------------------
class ForecastCreate(BaseModel):
    period: str                                 # "YYYY-MM"
    salesperson_id: Optional[str] = None
    salesperson_name: str
    team: Optional[str] = ""
    branch: Optional[str] = ""
    forecast_revenue: float = 0
    forecast_pax: int = 0
    forecast_gross_profit: float = 0
    forecast_margin: Optional[float] = None     # percent; auto-computed if None
    category: str = "GENERAL"
    status: str = "DRAFT"
    notes: Optional[str] = ""


class ForecastUpdate(BaseModel):
    period: Optional[str] = None
    salesperson_id: Optional[str] = None
    salesperson_name: Optional[str] = None
    team: Optional[str] = None
    branch: Optional[str] = None
    forecast_revenue: Optional[float] = None
    forecast_pax: Optional[int] = None
    forecast_gross_profit: Optional[float] = None
    forecast_margin: Optional[float] = None
    category: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


FORECAST_CATEGORIES = ["UMRAH", "HAJI", "TOUR", "CORPORATE", "GENERAL", "OTHER"]
FORECAST_STATUSES = ["DRAFT", "SUBMITTED", "APPROVED", "ACHIEVED", "MISSED"]
_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _forecast_out(doc: dict) -> dict:
    d = serialize(dict(doc))
    return d


def _validate_forecast(period, salesperson_name, revenue, pax, gp):
    if not period or not _PERIOD_RE.match(str(period).strip()):
        raise HTTPException(status_code=400, detail="Periode wajib diisi dengan format YYYY-MM (contoh 2026-07).")
    if not (salesperson_name or "").strip():
        raise HTTPException(status_code=400, detail="Salesperson wajib diisi.")
    for label, val in (("Forecast Revenue", revenue), ("Forecast Pax", pax), ("Forecast Gross Profit", gp)):
        try:
            n = float(val)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"{label} harus berupa angka.")
        if n < 0:
            raise HTTPException(status_code=400, detail=f"{label} tidak boleh negatif.")


def _forecast_margin(revenue, gp, provided):
    if provided is not None:
        return round(float(provided), 2)
    r = float(revenue or 0)
    return round((float(gp or 0) / r) * 100, 2) if r > 0 else 0.0


async def _forecast_summary():
    docs = await db.forecasts.find({"is_deleted": {"$ne": True}}).to_list(5000)
    by_period, by_category = {}, {}
    tot_rev = tot_pax = tot_gp = 0.0
    for d in docs:
        rev = float(d.get("forecast_revenue") or 0)
        pax = int(d.get("forecast_pax") or 0)
        gp = float(d.get("forecast_gross_profit") or 0)
        tot_rev += rev; tot_pax += pax; tot_gp += gp
        p = d.get("period") or "—"
        bp = by_period.setdefault(p, {"period": p, "revenue": 0.0, "pax": 0, "gross_profit": 0.0, "count": 0})
        bp["revenue"] += rev; bp["pax"] += pax; bp["gross_profit"] += gp; bp["count"] += 1
        c = d.get("category") or "OTHER"
        bc = by_category.setdefault(c, {"category": c, "revenue": 0.0, "pax": 0, "gross_profit": 0.0, "count": 0})
        bc["revenue"] += rev; bc["pax"] += pax; bc["gross_profit"] += gp; bc["count"] += 1
    for bp in by_period.values():
        bp["revenue"] = round(bp["revenue"], 2); bp["gross_profit"] = round(bp["gross_profit"], 2)
        bp["margin"] = round((bp["gross_profit"] / bp["revenue"]) * 100, 2) if bp["revenue"] > 0 else 0.0
    for bc in by_category.values():
        bc["revenue"] = round(bc["revenue"], 2); bc["gross_profit"] = round(bc["gross_profit"], 2)
    return {
        "total_revenue": round(tot_rev, 2),
        "total_pax": tot_pax,
        "total_gross_profit": round(tot_gp, 2),
        "total_margin": round((tot_gp / tot_rev) * 100, 2) if tot_rev > 0 else 0.0,
        "count": len(docs),
        "by_period": sorted(by_period.values(), key=lambda x: x["period"], reverse=True),
        "by_category": sorted(by_category.values(), key=lambda x: -x["revenue"]),
    }


@api_router.get("/forecast/meta")
async def forecast_meta(user: dict = Depends(require_role("super_admin"))):
    sales = await db.users.find({"role": {"$in": ["sales", "super_admin"]}, "is_deleted": {"$ne": True}}).to_list(500)
    return {
        "categories": FORECAST_CATEGORIES,
        "statuses": FORECAST_STATUSES,
        "salespeople": [{"id": str(u["_id"]), "name": u.get("name"), "role": u.get("role"),
                         "branch": u.get("branch", "")} for u in sales],
    }


@api_router.get("/forecast/records")
async def list_forecasts(period: Optional[str] = None, status: Optional[str] = None,
                         category: Optional[str] = None, include_deleted: bool = False,
                         user: dict = Depends(require_role("super_admin"))):
    query = {} if include_deleted else {"is_deleted": {"$ne": True}}
    if period:
        query["period"] = period
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    docs = await db.forecasts.find(query).sort([("period", -1), ("created_at", -1)]).to_list(5000)
    return {"records": [_forecast_out(d) for d in docs], "summary": await _forecast_summary()}


@api_router.get("/forecast/records/{fid}")
async def get_forecast(fid: str, user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="Forecast tidak ditemukan")
    doc = await db.forecasts.find_one({"_id": ObjectId(fid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Forecast tidak ditemukan")
    return _forecast_out(doc)


@api_router.post("/forecast/records")
async def create_forecast(body: ForecastCreate, request: Request, user: dict = Depends(require_role("super_admin"))):
    _validate_forecast(body.period, body.salesperson_name, body.forecast_revenue, body.forecast_pax, body.forecast_gross_profit)
    category = (body.category or "GENERAL").strip().upper()
    period = body.period.strip()
    # Duplicate guard: same salesperson + period + category
    dup_or = [{"salesperson_name": body.salesperson_name.strip()}]
    if body.salesperson_id:
        dup_or.append({"salesperson_id": body.salesperson_id})
    dup = await db.forecasts.find_one({"is_deleted": {"$ne": True}, "period": period,
                                       "category": category, "$or": dup_or})
    if dup:
        raise HTTPException(status_code=409, detail="Forecast untuk salesperson, periode, dan kategori ini sudah ada.")
    doc = {
        "period": period,
        "salesperson_id": body.salesperson_id,
        "salesperson_name": body.salesperson_name.strip(),
        "team": (body.team or "").strip(),
        "branch": (body.branch or "").strip(),
        "forecast_revenue": round(float(body.forecast_revenue or 0), 2),
        "forecast_pax": int(body.forecast_pax or 0),
        "forecast_gross_profit": round(float(body.forecast_gross_profit or 0), 2),
        "forecast_margin": _forecast_margin(body.forecast_revenue, body.forecast_gross_profit, body.forecast_margin),
        "category": category,
        "status": (body.status or "DRAFT").strip().upper(),
        "notes": (body.notes or "").strip(),
        "is_deleted": False,
        "created_by": user["name"], "created_by_id": user["_id"],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    res = await db.forecasts.insert_one(doc)
    doc["_id"] = res.inserted_id
    await log_audit(user, "forecast", "create_forecast", request, record_id=str(res.inserted_id), new=serialize(dict(doc)))
    return _forecast_out(doc)


@api_router.put("/forecast/records/{fid}")
async def update_forecast(fid: str, body: ForecastUpdate, request: Request, user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="Forecast tidak ditemukan")
    doc = await db.forecasts.find_one({"_id": ObjectId(fid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Forecast tidak ditemukan")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    merged = {**doc, **updates}
    if "category" in updates:
        updates["category"] = (updates["category"] or "GENERAL").strip().upper()
        merged["category"] = updates["category"]
    if "period" in updates:
        updates["period"] = (updates["period"] or "").strip()
        merged["period"] = updates["period"]
    if "status" in updates:
        updates["status"] = (updates["status"] or "DRAFT").strip().upper()
    _validate_forecast(merged.get("period"), merged.get("salesperson_name"),
                       merged.get("forecast_revenue"), merged.get("forecast_pax"), merged.get("forecast_gross_profit"))
    # Duplicate guard on the resulting combination
    dup_or = [{"salesperson_name": merged.get("salesperson_name")}]
    if merged.get("salesperson_id"):
        dup_or.append({"salesperson_id": merged.get("salesperson_id")})
    dup = await db.forecasts.find_one({"_id": {"$ne": ObjectId(fid)}, "is_deleted": {"$ne": True},
                                       "period": merged.get("period"), "category": merged.get("category"),
                                       "$or": dup_or})
    if dup:
        raise HTTPException(status_code=409, detail="Forecast untuk salesperson, periode, dan kategori ini sudah ada.")
    if "forecast_revenue" in updates:
        updates["forecast_revenue"] = round(float(updates["forecast_revenue"] or 0), 2)
    if "forecast_pax" in updates:
        updates["forecast_pax"] = int(updates["forecast_pax"] or 0)
    if "forecast_gross_profit" in updates:
        updates["forecast_gross_profit"] = round(float(updates["forecast_gross_profit"] or 0), 2)
    # Recompute margin whenever money fields change, unless explicitly provided
    if body.forecast_margin is not None:
        updates["forecast_margin"] = round(float(body.forecast_margin), 2)
    elif ("forecast_revenue" in updates) or ("forecast_gross_profit" in updates):
        updates["forecast_margin"] = _forecast_margin(merged.get("forecast_revenue"), merged.get("forecast_gross_profit"), None)
    updates["updated_at"] = now_iso()
    updates["updated_by"] = user["name"]
    await db.forecasts.update_one({"_id": ObjectId(fid)}, {"$set": updates})
    await log_audit(user, "forecast", "update_forecast", request, record_id=fid,
                    old=serialize(dict(doc)), new=updates)
    return _forecast_out(await db.forecasts.find_one({"_id": ObjectId(fid)}))


@api_router.delete("/forecast/records/{fid}")
async def delete_forecast(fid: str, request: Request, reason: str = Query(""), user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="Forecast tidak ditemukan")
    doc = await db.forecasts.find_one({"_id": ObjectId(fid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Forecast tidak ditemukan")
    if doc.get("is_deleted"):
        raise HTTPException(status_code=400, detail="Forecast sudah dihapus.")
    await db.forecasts.update_one({"_id": ObjectId(fid)}, {"$set": {
        "is_deleted": True, "deleted_by": user["name"], "deleted_at": now_iso()}})
    await log_audit(user, "forecast", "delete_forecast", request, record_id=fid,
                    old=serialize(dict(doc)), new={"is_deleted": True}, reason=(reason or "").strip() or None)
    return {"message": "Forecast dihapus", "id": fid}


@api_router.get("/notifications")
async def notifications(unread_only: bool = False, user: dict = Depends(require_permission("notifications.view"))):
    q = {"$or": [{"user_id": user["_id"]}, {"role": user["role"]}]}
    if unread_only:
        q["read"] = False
    docs = await db.notifications.find(q).sort("created_at", -1).to_list(100)
    return [{"id": str(d["_id"]), "title": d.get("title", ""), "body": d.get("body", ""),
             "link": d.get("link", ""), "type": d.get("type", "info"), "priority": d.get("priority", "normal"),
             "read": d.get("read", False), "time": d.get("created_at", "")} for d in docs]


@api_router.patch("/notifications/{nid}/read")
async def mark_notification_read(nid: str, user: dict = Depends(require_permission("notifications.view"))):
    await db.notifications.update_one({"_id": ObjectId(nid)}, {"$set": {"read": True}})
    return {"ok": True}


async def notify(title, body, link="", role=None, user_id=None, ntype="info", priority="normal", dedupe=None):
    if dedupe and await db.notifications.find_one({"dedupe": dedupe}):
        return
    await db.notifications.insert_one({"role": role, "user_id": user_id, "title": title, "body": body,
        "link": link, "type": ntype, "priority": priority, "dedupe": dedupe, "read": False, "created_at": now_iso()})


async def create_task(task_name, assigned_user_id=None, assigned_user_name="", customer_id=None,
                      booking_id=None, lead_id=None, due_date=None, priority="MEDIUM", notes="",
                      created_by="system", source="manual", dedupe=None):
    if dedupe and await db.tasks.find_one({"dedupe": dedupe}):
        return None
    doc = {"task_name": task_name, "assigned_user_id": assigned_user_id, "assigned_user_name": assigned_user_name,
           "customer_id": customer_id, "booking_id": booking_id, "lead_id": lead_id, "due_date": due_date,
           "priority": priority, "status": "TODO", "notes": notes, "created_by": created_by,
           "source": source, "auto": source != "manual", "dedupe": dedupe, "created_at": now_iso()}
    res = await db.tasks.insert_one(doc)
    return str(res.inserted_id)


@api_router.get("/notifications/unread-count")
async def notifications_unread_count(user: dict = Depends(require_permission("notifications.view"))):
    n = await db.notifications.count_documents({"$or": [{"user_id": user["_id"]}, {"role": user["role"]}], "read": False})
    return {"count": n}


@api_router.post("/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(require_permission("notifications.view"))):
    await db.notifications.update_many({"$or": [{"user_id": user["_id"]}, {"role": user["role"]}], "read": False}, {"$set": {"read": True}})
    return {"ok": True}


# ---------- Task Center ----------
TASK_STATUSES = ["TODO", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
TASK_PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"]


def _task_owner_q(user):
    return {} if user["role"] == "super_admin" else {"$or": [{"assigned_user_id": user["_id"]}, {"created_by": user["name"]}]}


@api_router.get("/tasks")
async def list_tasks(status: Optional[str] = None, scope: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = _task_owner_q(user)
    if status and status != "all":
        q["status"] = status
    docs = await db.tasks.find(q).sort("due_date", 1).to_list(3000)
    today = today_str()
    out = []
    for d in docs:
        d = serialize(d)
        due = (d.get("due_date") or "")[:10]
        st = d.get("status")
        if scope == "due_today":
            if st in ("TODO", "IN_PROGRESS") and due == today: out.append(d)
        elif scope == "overdue":
            if st in ("TODO", "IN_PROGRESS") and due and due < today: out.append(d)
        elif scope == "upcoming":
            if st in ("TODO", "IN_PROGRESS") and due and due > today: out.append(d)
        elif scope == "completed":
            if st == "COMPLETED": out.append(d)
        else:
            out.append(d)
    return out


@api_router.get("/tasks/stats")
async def task_stats(user: dict = Depends(get_current_user)):
    docs = await db.tasks.find(_task_owner_q(user)).to_list(5000)
    today = today_str()
    due = over = up = done = 0
    for d in docs:
        st = d.get("status")
        due_d = (d.get("due_date") or "")[:10]
        if st == "COMPLETED":
            done += 1; continue
        if st == "CANCELLED":
            continue
        if due_d == today: due += 1
        elif due_d and due_d < today: over += 1
        elif due_d and due_d > today: up += 1
    return {"due_today": due, "overdue": over, "upcoming": up, "completed": done}


@api_router.post("/tasks")
async def create_task_api(body: dict, user: dict = Depends(get_current_user)):
    aid = body.get("assigned_user_id") or user["_id"]
    aname = body.get("assigned_user_name") or user["name"]
    if body.get("assigned_user_id") and ObjectId.is_valid(body["assigned_user_id"]):
        u = await db.users.find_one({"_id": ObjectId(body["assigned_user_id"])})
        if u:
            aname = u.get("name", aname)
    tid = await create_task(body.get("task_name", "Task"), assigned_user_id=aid, assigned_user_name=aname,
        customer_id=body.get("customer_id"), booking_id=body.get("booking_id"), lead_id=body.get("lead_id"),
        due_date=body.get("due_date"), priority=body.get("priority", "MEDIUM"), notes=body.get("notes", ""),
        created_by=user["name"], source="manual")
    if aid and aid != user["_id"]:
        await notify("New Task Assigned", body.get("task_name", "Task"), link="/tasks", user_id=aid, ntype="TASK")
    return serialize(await db.tasks.find_one({"_id": ObjectId(tid)}))


@api_router.patch("/tasks/{tid}")
async def update_task_api(tid: str, body: dict, user: dict = Depends(get_current_user)):
    t = await db.tasks.find_one({"_id": ObjectId(tid)})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if user["role"] != "super_admin" and t.get("assigned_user_id") != user["_id"] and t.get("created_by") != user["name"]:
        raise HTTPException(status_code=403, detail="403 Forbidden")
    allowed = {k: v for k, v in body.items() if k in ("task_name", "status", "priority", "due_date", "notes", "assigned_user_id", "customer_id", "booking_id", "lead_id")}
    if allowed.get("status") == "COMPLETED":
        allowed["completed_at"] = now_iso()
    await db.tasks.update_one({"_id": ObjectId(tid)}, {"$set": allowed})
    return serialize(await db.tasks.find_one({"_id": ObjectId(tid)}))


# ---------- Cron: due/overdue notifications + automatic tasks ----------
def _days_ago(n):
    return (datetime.now(timezone.utc) - timedelta(days=n)).date().isoformat()


async def _run_auto_scan():
    today = today_str()
    for d in await db.documents.find({"is_deleted": False, "doc_type": {"$in": ["PASSPORT", "Passport", "VISA", "Visa"]}, "expiry_date": {"$nin": ["", None]}}).to_list(5000):
        exp = (d.get("expiry_date") or "")[:10]
        try:
            days = (datetime.fromisoformat(exp).date() - datetime.now(timezone.utc).date()).days
        except Exception:
            continue
        if days > 0 and days not in (90, 60, 30):
            continue
        title = (f"Dokumen KEDALUWARSA — {d.get('doc_type')}" if days < 0 else f"Dokumen kedaluwarsa {days} hari — {d.get('doc_type')}")
        sid = cid = None
        if d.get("booking_id") and ObjectId.is_valid(d["booking_id"]):
            bk = await db.bookings.find_one({"_id": ObjectId(d["booking_id"])})
            if bk:
                sid, cid = bk.get("sales_pic_id"), bk.get("customer_id")
        prio = "urgent" if days < 0 else "high"
        body = f"{d.get('document_number', '')} exp {exp}"
        link = f"/crm/{cid}" if cid else "/booking"
        await notify(title, body, link=link, user_id=sid, ntype="DOCUMENT_EXPIRY", priority=prio, dedupe=f"docexp:{d.get('id')}:{today}")
        await notify(title, body, link="/booking", role="super_admin", ntype="DOCUMENT_EXPIRY", priority=prio, dedupe=f"docexpsa:{d.get('id')}:{today}")
    for f in await db.follow_ups.find({"status": {"$ne": "completed"}}).to_list(5000):
        due = (f.get("due_date") or "")[:10]
        fid = str(f["_id"])
        if not due:
            continue
        link = f"/crm/{f.get('customer_id')}" if f.get("customer_id") else "/follow-ups"
        if due == today:
            await notify("Follow Up Due Today", f"{f.get('activity_type', 'Follow up')} — {f.get('customer_name', '')}",
                link=link, user_id=f.get("sales_pic_id"), ntype="FOLLOW_UP_DUE", priority="high", dedupe=f"fudue:{fid}:{today}")
        elif due < today:
            await notify("Follow Up Overdue", f"{f.get('activity_type', 'Follow up')} — {f.get('customer_name', '')} (due {due})",
                link=link, user_id=f.get("sales_pic_id"), ntype="FOLLOW_UP_OVERDUE", priority="urgent", dedupe=f"fuover:{fid}:{today}")
    for q in await db.quotations.find({"status": {"$nin": ["CONVERTED", "EXPIRED", "REJECTED"]}}).to_list(5000):
        created = (q.get("created_at") or "")[:10]
        if created and created <= _days_ago(3):
            await create_task(f"Follow up quotation {q.get('quotation_number', '')}",
                assigned_user_id=q.get("sales_pic_id"), assigned_user_name=q.get("sales_pic_name", ""),
                customer_id=q.get("customer_id"), due_date=today, priority="HIGH",
                notes="Quotation belum di-follow-up 3+ hari", created_by="system", source="auto_quotation",
                dedupe=f"autoq:{str(q['_id'])}")
            await notify("Quotation Needs Follow Up", f"{q.get('quotation_number', '')} — {q.get('customer_name', '')}",
                link="/quotations", user_id=q.get("sales_pic_id"), ntype="QUOTATION_EXPIRING", priority="high",
                dedupe=f"qexp:{str(q['_id'])}:{today}")
    for inv in await db.invoices.find({"status": {"$nin": ["Paid", "PAID", "Cancelled", "CANCELLED"]}}).to_list(5000):
        due = (inv.get("due_date") or "")[:10]
        if not due or due > today:
            continue
        overdue = due < today
        await notify("Invoice Overdue" if overdue else "Invoice Due Today",
            f"{inv.get('invoice_number', '')} — {inv.get('customer_name', '')} (Rp {inv.get('outstanding', 0)})",
            link="/accounting", role="accounting", ntype="INVOICE_OVERDUE" if overdue else "INVOICE_DUE",
            priority="high", dedupe=f"inv:{str(inv['_id'])}:{today}")
        if inv.get("sales_pic_id") and overdue:
            await notify("Payment Overdue", f"{inv.get('invoice_number', '')} — {inv.get('customer_name', '')}",
                link=f"/crm/{inv.get('customer_id')}" if inv.get("customer_id") else "/accounting",
                user_id=inv.get("sales_pic_id"), ntype="PAYMENT_OVERDUE", priority="urgent", dedupe=f"payover:{str(inv['_id'])}:{today}")
        await create_task(f"Collect payment {inv.get('invoice_number', '')}",
            assigned_user_id=inv.get("sales_pic_id"), assigned_user_name=inv.get("sales_pic_name", ""),
            customer_id=inv.get("customer_id"), booking_id=inv.get("booking_id"), due_date=today,
            priority="HIGH", notes="Pembayaran jatuh tempo", created_by="system", source="auto_invoice",
            dedupe=f"autoinv:{str(inv['_id'])}:{today}")
    for c in await db.conversations.find({"status": "REQUIRES_HUMAN"}).to_list(3000):
        cid = c.get("customer_id")
        key = cid or c.get("whatsapp")
        await create_task(f"Reply WhatsApp — {c.get('customer_name') or c.get('whatsapp', '')}",
            customer_id=cid, due_date=today, priority="URGENT", notes="Customer butuh CS (handover)",
            created_by="system", source="auto_handover", dedupe=f"autohandover:{key}")
        await notify("Customer Needs Human Reply", f"{c.get('customer_name') or c.get('whatsapp', '')}",
            link=f"/crm/{cid}" if cid else "/ai-hub", role="super_admin", ntype="CUSTOMER_REPLY", priority="urgent",
            dedupe=f"handover:{key}:{today}")
    for b in await db.bookings.find({"status": {"$ne": "CANCELLED"}}).to_list(5000):
        bid = str(b["_id"])
        if await db.documents.count_documents({"booking_id": bid, "is_deleted": False}) == 0:
            await create_task(f"Upload documents — {b.get('booking_number', '')}",
                assigned_user_id=b.get("sales_pic_id"), assigned_user_name=b.get("sales_pic_name", ""),
                customer_id=b.get("customer_id"), booking_id=bid, due_date=today, priority="MEDIUM",
                notes="Booking membutuhkan dokumen jamaah", created_by="system", source="auto_document", dedupe=f"autodoc:{bid}")
        for it in (b.get("payment_schedule") or []):
            st = it.get("status")
            if st in ("PAID", "CANCELLED"):
                continue
            due = (it.get("due_date") or "")[:10]
            if not due:
                continue
            offset = (datetime.fromisoformat(due).date() - datetime.now(timezone.utc).date()).days
            stage = None
            if due < today:
                stage = "Overdue"
            elif offset == 0:
                stage = "Due Today"
            elif offset in (1, 3, 7):
                stage = f"{offset} hari lagi"
            if not stage:
                continue
            key = f"payrem:{bid}:{it.get('payment_number')}:{today}"
            out = it.get("outstanding", it.get("amount"))
            if b.get("sales_pic_id"):
                await notify(f"Payment Reminder ({stage})",
                    f"{b.get('booking_number', '')} • {b.get('customer_name', '')} • Rp {out} jatuh tempo {due}",
                    link=f"/crm/{b.get('customer_id')}" if b.get("customer_id") else "/accounting",
                    user_id=b.get("sales_pic_id"), ntype="PAYMENT_OVERDUE" if stage == "Overdue" else "PAYMENT_DUE",
                    priority="urgent" if stage == "Overdue" else "high", dedupe=key)
            # N8N WhatsApp reminder + log to conversation history
            phone = await _cust_phone(b.get("customer_id"))
            if phone and not await db.conversations.find_one({"dedupe": key}):
                msg = f"Assalamualaikum {b.get('customer_name', '')}, pengingat pembayaran {b.get('booking_number', '')} sebesar Rp {out}, jatuh tempo {due} ({stage}). Terima kasih."
                trigger_n8n("payment.reminder", {"booking_number": b.get("booking_number"), "customer_id": b.get("customer_id"),
                    "customer_phone": phone, "outstanding": out, "due_date": due, "stage": stage, "message": msg})
                await db.conversations.insert_one({"conversation_id": str(_uuid.uuid4()), "customer_id": b.get("customer_id"),
                    "customer_name": b.get("customer_name", ""), "whatsapp": phone, "channel": "WHATSAPP", "direction": "OUTBOUND",
                    "message": msg, "message_type": "TEXT", "sender_type": "SYSTEM", "ai_or_human": "AUTO", "status": "SENT",
                    "dedupe": key, "timestamp": now_iso(), "created_at": now_iso()})


@api_router.post("/cron/notifications-tasks")
async def cron_notifications_tasks(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not secret or not _hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background.add_task(_run_auto_scan)
    return {"accepted": True}


# ---------- Phase 9C: Central Approval Center ----------
ADJ_TYPES = ["PRICE_ADJUSTMENT", "PAYMENT_ADJUSTMENT", "ACCOUNTING_ADJUSTMENT", "OTHER"]


def _ac_can(user):
    return user["role"] in ("super_admin", "accounting")


def _ac_norm_status(s):
    s = (s or "").upper()
    if s in ("APPROVED", "REFUNDED", "PARTIALLY_REFUNDED", "PAID"):
        return "APPROVED"
    if s == "REJECTED":
        return "REJECTED"
    if s in ("REVISION", "NEEDS_REVISION", "REQUEST_REVISION"):
        return "REVISION"
    return "PENDING"


def _ac_last_at(timeline):
    if isinstance(timeline, list) and timeline:
        return timeline[-1].get("at")
    return None


async def _collect_approvals(user, type_filter=None):
    role = user["role"]
    rows = []
    if not type_filter or type_filter in ADJ_TYPES or type_filter == "ADJUSTMENT":
        async for d in db.approvals.find({}):
            rows.append({"source": "adjustment", "id": str(d["_id"]), "approval_number": d.get("approval_number"),
                "type": d.get("atype"), "reference": d.get("reference", ""), "customer": d.get("customer_name", ""),
                "amount": d.get("amount", 0), "requested_by": d.get("requested_by", ""), "requested_date": d.get("created_at"),
                "status": _ac_norm_status(d.get("status")), "decided_date": d.get("decided_at"), "actionable": role == "super_admin"})
    if role in ("super_admin", "accounting") and (not type_filter or type_filter == "REFUND"):
        async for d in db.refund_requests.find({}):
            rows.append({"source": "refund", "id": str(d["_id"]), "approval_number": d.get("refund_number"),
                "type": "REFUND", "reference": d.get("booking_number") or d.get("cancellation_number", ""),
                "customer": d.get("customer_name", ""), "amount": d.get("approved_refund") or d.get("proposed_refund") or 0,
                "requested_by": d.get("created_by") or "System", "requested_date": d.get("created_at"),
                "status": _ac_norm_status(d.get("status")), "decided_date": _ac_last_at(d.get("timeline")),
                "actionable": role == "super_admin" and d.get("status") == "ACCOUNTING_REVIEWED", "link": "/approvals"})
    if role in ("super_admin", "accounting") and (not type_filter or type_filter == "CANCELLATION"):
        async for d in db.cancellation_requests.find({}):
            rows.append({"source": "cancellation", "id": str(d["_id"]), "approval_number": d.get("cancellation_number"),
                "type": "CANCELLATION", "reference": d.get("booking_number", ""), "customer": d.get("customer_name", ""),
                "amount": d.get("penalty") or d.get("refund_amount") or 0, "requested_by": d.get("created_by", ""),
                "requested_date": d.get("created_at"), "status": _ac_norm_status(d.get("status")),
                "decided_date": _ac_last_at(d.get("timeline")),
                "actionable": role == "super_admin" and d.get("status") == "ACCOUNTING_REVIEWED", "link": "/approvals"})
    if role == "super_admin" and (not type_filter or type_filter == "COMMISSION"):
        async for d in db.commission_closings.find({"status": {"$nin": ["DRAFT", "CALCULATING"]}}):
            sa = d.get("sa_approval")
            if sa == "APPROVED" or d.get("status") in ("APPROVED", "PAID"):
                st = "APPROVED"
            elif sa == "REJECTED":
                st = "REJECTED"
            elif sa == "REVISION":
                st = "REVISION"
            else:
                st = "PENDING"
            act_ok = role == "super_admin" and st == "PENDING" and d.get("status") in ("REVIEW", "CLOSED")
            rows.append({"source": "commission", "id": str(d.get("period")), "approval_number": f"COMM-{d.get('period')}",
                "type": "COMMISSION", "reference": d.get("period", ""), "customer": "—",
                "amount": d.get("total_final") or d.get("total_commission") or 0, "requested_by": "System",
                "requested_date": d.get("created_at"), "status": st,
                "decided_date": d.get("sa_approval_at") or d.get("approved_at"), "actionable": act_ok, "link": "/commission"})
    if type_filter and type_filter in ADJ_TYPES:
        rows = [r for r in rows if r["type"] == type_filter]
    rows.sort(key=lambda x: (x.get("requested_date") or ""), reverse=True)
    return rows


@api_router.get("/approval-center")
async def approval_center_list(type: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not _ac_can(user):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    rows = await _collect_approvals(user, type)
    if status and status != "all":
        rows = [r for r in rows if r["status"] == status.upper()]
    return rows


@api_router.get("/approval-center/stats")
async def approval_center_stats(user: dict = Depends(get_current_user)):
    if not _ac_can(user):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    rows = await _collect_approvals(user)
    today = today_str()
    month = today[:7]
    return {"pending": sum(1 for r in rows if r["status"] == "PENDING"),
            "approved_today": sum(1 for r in rows if r["status"] == "APPROVED" and (r.get("decided_date") or "")[:10] == today),
            "rejected_today": sum(1 for r in rows if r["status"] == "REJECTED" and (r.get("decided_date") or "")[:10] == today),
            "total_this_month": sum(1 for r in rows if (r.get("requested_date") or "")[:7] == month)}


@api_router.post("/approval-center/adjustments")
async def create_adjustment(body: dict, user: dict = Depends(get_current_user)):
    if user["role"] not in ("super_admin", "accounting"):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    atype = body.get("atype", "OTHER")
    if atype not in ADJ_TYPES:
        atype = "OTHER"
    num = await next_number("APR", db.approvals, "approval_number")
    cust_name = body.get("customer_name", "")
    if body.get("customer_id") and ObjectId.is_valid(body["customer_id"]):
        c = await db.customers.find_one({"_id": ObjectId(body["customer_id"])})
        cust_name = (c or {}).get("full_name", cust_name)
    doc = {"approval_number": num, "atype": atype, "reference": body.get("reference", ""),
           "customer_id": body.get("customer_id"), "customer_name": cust_name,
           "amount": float(body.get("amount") or 0), "reason": body.get("reason", ""),
           "evidence_url": body.get("evidence_url", ""), "related_documents": body.get("related_documents", []),
           "requested_by": user["name"], "requested_by_id": user["_id"], "requested_by_role": user["role"],
           "status": "PENDING", "history": [{"user": user["name"], "role": user["role"], "action": "CREATED",
               "comment": body.get("reason", ""), "at": now_iso()}], "created_at": now_iso()}
    res = await db.approvals.insert_one(doc)
    await notify("Approval Pending", f"{num} • {atype} oleh {user['name']}", "/approval-center", role="super_admin", ntype="APPROVAL_PENDING", priority="high")
    return serialize(await db.approvals.find_one({"_id": res.inserted_id}))


@api_router.get("/approval-center/detail/{source}/{aid}")
async def approval_detail(source: str, aid: str, user: dict = Depends(get_current_user)):
    if not _ac_can(user):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    if source == "commission":
        d = await db.commission_closings.find_one({"period": aid})
        if not d:
            raise HTTPException(status_code=404, detail="Not found")
        d = serialize(d)
        d["history"] = d.get("timeline", [])
        return d
    coll = {"adjustment": db.approvals, "refund": db.refund_requests, "cancellation": db.cancellation_requests}.get(source)
    if coll is None:
        raise HTTPException(status_code=404, detail="Not found")
    d = await coll.find_one({"_id": ObjectId(aid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    d = serialize(d)
    d["history"] = d.get("history") or d.get("timeline") or []
    return d


@api_router.post("/approval-center/adjustments/{aid}/action")
async def adjustment_action(aid: str, body: dict, user: dict = Depends(require_role("super_admin"))):
    action = (body.get("action") or "").upper()
    reason = (body.get("reason") or body.get("comment") or "").strip()
    if action not in ("APPROVE", "REJECT", "REQUEST_REVISION"):
        raise HTTPException(status_code=400, detail="Invalid action")
    if action in ("REJECT", "REQUEST_REVISION") and not reason:
        raise HTTPException(status_code=400, detail="Reason wajib diisi untuk Reject / Request Revision")
    d = await db.approvals.find_one({"_id": ObjectId(aid)})
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    new_status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_REVISION": "REVISION"}[action]
    hist = d.get("history", [])
    hist.append({"user": user["name"], "role": user["role"], "action": action, "comment": reason, "at": now_iso()})
    await db.approvals.update_one({"_id": ObjectId(aid)}, {"$set": {"status": new_status, "decided_at": now_iso(), "history": hist}})
    await notify(f"Approval {new_status.title()}", f"{d.get('approval_number')} • {d.get('atype')}" + (f" — {reason}" if reason else ""),
                 "/approval-center", user_id=d.get("requested_by_id"), ntype="APPROVAL_RESULT", priority="normal")
    return serialize(await db.approvals.find_one({"_id": ObjectId(aid)}))




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
    company_name: Optional[str] = ""


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
    sales_pic_id: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    phone: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    company_name: Optional[str] = None
    customer_category: Optional[str] = None
    status: Optional[str] = None


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
                         include_archived: bool = False,
                         user: dict = Depends(require_permission("crm.view"))):
    query = owner_filter(user)
    if not include_archived:
        query["is_deleted"] = {"$ne": True}
    if customer_type and customer_type != "all":
        query["customer_type"] = customer_type
    if q:
        query["$or"] = [
            {"full_name": {"$regex": q, "$options": "i"}},
            {"company_name": {"$regex": q, "$options": "i"}},
            {"whatsapp": {"$regex": q, "$options": "i"}},
            {"phone": {"$regex": q, "$options": "i"}},
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


@api_router.get("/customers/check-duplicate")
async def check_customer_duplicate(phone: str = "", whatsapp: str = "", email: str = "", passport_number: str = "",
                                   exclude_id: str = "", user: dict = Depends(require_permission("crm.view"))):
    phone, whatsapp, email, passport_number = phone.strip(), whatsapp.strip(), email.strip(), passport_number.strip()
    ors = []
    if phone:
        ors.append({"whatsapp": phone})
    if whatsapp:
        ors.append({"whatsapp": whatsapp})
    if email:
        ors.append({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
    if passport_number:
        ors.append({"passport_number": passport_number})
    if not ors:
        return {"duplicates": []}
    query = {"$or": ors, "is_deleted": {"$ne": True}}
    if exclude_id and ObjectId.is_valid(exclude_id):
        query["_id"] = {"$ne": ObjectId(exclude_id)}
    docs = await db.customers.find(query).limit(10).to_list(10)
    out = []
    for d in docs:
        matched = []
        if (whatsapp and d.get("whatsapp") == whatsapp) or (phone and d.get("whatsapp") == phone):
            matched.append("whatsapp")
        if email and (d.get("email") or "").lower() == email.lower():
            matched.append("email")
        if passport_number and d.get("passport_number") == passport_number:
            matched.append("passport_number")
        out.append({"id": str(d["_id"]), "full_name": d.get("full_name"), "customer_code": d.get("customer_code"),
                    "whatsapp": d.get("whatsapp"), "email": d.get("email"), "passport_number": d.get("passport_number"),
                    "matched_fields": matched})
    return {"duplicates": out}


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
    for fld in ("phone", "whatsapp"):
        val = (updates.get(fld) or "").strip()
        if val:
            dup = await db.customers.find_one({"_id": {"$ne": ObjectId(cid)}, "is_deleted": {"$ne": True},
                                               "$or": [{"phone": val}, {"whatsapp": val}]})
            if dup:
                raise HTTPException(status_code=409, detail="Nomor HP/WhatsApp sudah terdaftar pada customer lain.")
    new_pic = updates.pop("sales_pic_id", None)
    if new_pic is not None:
        if user["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="Hanya Super Admin yang dapat mengganti PIC sales")
        pic = await db.users.find_one({"_id": ObjectId(new_pic)}) if ObjectId.is_valid(new_pic) else None
        if not pic or pic.get("is_deleted"):
            raise HTTPException(status_code=400, detail="Sales PIC tidak ditemukan")
        updates["sales_pic_id"] = str(pic["_id"])
        updates["sales_pic_name"] = pic.get("name")
        updates["branch"] = pic.get("branch", doc.get("branch", ""))
    await db.customers.update_one({"_id": ObjectId(cid)}, {"$set": updates})
    for _k, _v in updates.items():
        if _k in ("sales_pic_name", "branch"):
            continue
        _old = doc.get(_k)
        if str(_old if _old is not None else "") != str(_v if _v is not None else ""):
            await db.customer_audit.insert_one({"customer_id": cid, "customer_name": doc.get("full_name"),
                "field": _k, "old_value": _old, "new_value": _v, "changed_by": user["name"],
                "changed_by_id": user["_id"], "changed_by_role": user["role"], "timestamp": now_iso()})
    if new_pic is not None and str(doc.get("sales_pic_id") or "") != str(new_pic):
        await log_activity(cid, None, "pic_change",
                           f"PIC Sales diganti: {doc.get('sales_pic_name') or '—'} → {updates.get('sales_pic_name')}",
                           f"Diubah oleh {user['name']}", user)
    await log_audit(user, "customer", "update_customer", request, record_id=cid, new=updates)
    return serialize(await db.customers.find_one({"_id": ObjectId(cid)}))


@api_router.delete("/customers/{cid}")
async def delete_customer(cid: str, request: Request, reason: str = Query(""), user: dict = Depends(require_role("super_admin"))):
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Reason is required to archive a customer")
    doc = await db.customers.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one({"_id": ObjectId(cid)}, {"$set": {"is_deleted": True, "status": "ARCHIVED", "archived_by": user["name"], "archived_at": now_iso()}})
    await log_audit(user, "customer", "archive_customer", request, record_id=cid, new={"status": "ARCHIVED"}, reason=reason)
    return {"message": "Customer archived", "status": "ARCHIVED"}


@api_router.post("/customers/{cid}/restore")
async def restore_customer(cid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.customers.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one({"_id": ObjectId(cid)}, {"$set": {"is_deleted": False, "status": "ACTIVE"}})
    await log_audit(user, "customer", "restore_customer", request, record_id=cid, new={"status": "ACTIVE"})
    return {"message": "Customer restored"}


@api_router.patch("/customers/{cid}/status")
async def set_customer_status(cid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    status = (body or {}).get("status")
    reason = ((body or {}).get("reason") or "").strip()
    if status not in MASTER_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if not reason:
        raise HTTPException(status_code=400, detail="Reason is required")
    doc = await db.customers.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.customers.update_one({"_id": ObjectId(cid)}, {"$set": {"status": status, "is_deleted": status == "ARCHIVED"}})
    await log_audit(user, "customer", "status", request, record_id=cid, old={"status": doc.get("status")}, new={"status": status}, reason=reason)
    return {"status": status}


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
    try:
        oid = ObjectId(cid)
    except Exception:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = await db.customers.find_one({"_id": oid})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not can_access_record(user, customer):
        raise HTTPException(status_code=403, detail="403 Forbidden: not your customer")
    leads = [serialize(d) for d in await db.leads.find({"customer_id": cid}).sort("created_at", -1).to_list(500)]
    follow_ups = [serialize(d) for d in await db.follow_ups.find({"customer_id": cid}).sort("due_date", -1).to_list(500)]
    comms = [serialize(d) for d in await db.communications.find({"customer_id": cid}).sort("timestamp", -1).to_list(500)]
    notes = [serialize(d) for d in await db.customer_notes.find({"customer_id": cid}).sort("timestamp", -1).to_list(500)]
    acts = [serialize(d) for d in await db.lead_activities.find({"customer_id": cid}).sort("timestamp", -1).to_list(500)]

    raw_bookings = await db.bookings.find({"customer_id": cid}).sort("created_at", -1).to_list(1000)
    booking_ids = [str(b["_id"]) for b in raw_bookings]
    bookings = [serialize(b) for b in raw_bookings]
    quotations = [serialize(d) for d in await db.quotations.find({"customer_id": cid}).sort("created_at", -1).to_list(1000)]
    raw_invoices = await db.invoices.find({"customer_id": cid}).sort("created_at", -1).to_list(1000)
    invoices = [serialize(d) for d in raw_invoices]
    inv_ids = [str(i["_id"]) for i in raw_invoices]
    payments = [serialize(d) for d in await db.payments.find({"$or": [{"invoice_id": {"$in": inv_ids}}, {"booking_id": {"$in": booking_ids}}]}).sort("created_at", -1).to_list(2000)]
    refunds = [serialize(d) for d in await db.refund_requests.find({"$or": [{"customer_id": cid}, {"booking_id": {"$in": booking_ids}}]}).sort("created_at", -1).to_list(500)]
    commissions = [serialize(d) for d in await db.commission_items.find({"booking_id": {"$in": booking_ids}}).to_list(2000)]
    conversations = [serialize(d) for d in await db.conversations.find({"customer_id": cid}).sort("timestamp", 1).to_list(2000)]
    documents = [serialize(d) for d in await db.documents.find({"$or": [{"booking_id": {"$in": booking_ids}}, {"customer_id": cid}], "is_deleted": False}).to_list(2000)]

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
    for qq in quotations:
        timeline.append({"kind": "quotation", "title": f"Quotation {qq.get('quotation_number', '')} Created",
                         "detail": f"{qq.get('package_name', '')} · {qq.get('pax', 0)} pax", "user_name": qq.get("sales_pic_name"), "timestamp": qq.get("created_at")})
        if qq.get("status") == "CONVERTED":
            timeline.append({"kind": "quotation", "title": f"Quotation {qq.get('quotation_number', '')} Converted",
                             "detail": "", "user_name": qq.get("sales_pic_name"), "timestamp": qq.get("created_at")})
    for bb in bookings:
        timeline.append({"kind": "booking", "title": f"Booking {bb.get('booking_number', '')} Created",
                         "detail": f"{bb.get('package_name', '')} · {bb.get('pax', 0)} pax", "user_name": bb.get("sales_pic_name"), "timestamp": bb.get("created_at")})
        if bb.get("status") == "CANCELLED":
            timeline.append({"kind": "cancellation", "title": f"Booking {bb.get('booking_number', '')} Cancelled",
                             "detail": "", "user_name": "", "timestamp": bb.get("updated_at") or bb.get("created_at")})
    for pp in payments:
        timeline.append({"kind": "payment", "title": "Payment Received",
                         "detail": f"{pp.get('invoice_number', '')} · Rp {pp.get('amount', 0)}", "user_name": pp.get("recorded_by"), "timestamp": pp.get("created_at") or pp.get("payment_date")})
    for dd in documents:
        timeline.append({"kind": "document", "title": f"Document Uploaded — {dd.get('doc_type', '')}",
                         "detail": dd.get("status", ""), "user_name": dd.get("uploaded_by", ""), "timestamp": dd.get("created_at") or dd.get("uploaded_at")})
    for rr in refunds:
        timeline.append({"kind": "refund", "title": f"Refund {rr.get('refund_number', '')}",
                         "detail": rr.get("status", ""), "user_name": "", "timestamp": rr.get("created_at")})
    for cm in commissions:
        timeline.append({"kind": "commission", "title": f"Commission {cm.get('period', '')}",
                         "detail": cm.get("booking_number", ""), "user_name": cm.get("sales_pic_name", ""), "timestamp": cm.get("created_at") or ((cm.get("period", "") + "-01") if cm.get("period") else "")})
    timeline.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

    total_value = sum(float(l.get("budget") or 0) for l in leads if l.get("status") != "LOST")
    total_pax = sum(int(b.get("pax") or 0) for b in bookings if b.get("status") != "CANCELLED")
    total_sales = sum(float(b.get("total") or 0) for b in bookings if b.get("status") != "CANCELLED")
    total_paid = sum(float(p.get("amount") or 0) for p in payments)
    outstanding = sum(float(i.get("outstanding") or 0) for i in invoices)
    total_refund = sum(float(r.get("approved_refund") or r.get("proposed_refund") or 0) for r in refunds)
    last_booking = bookings[0].get("created_at") if bookings else None
    return {
        "customer": serialize(customer), "leads": leads, "follow_ups": follow_ups,
        "communications": comms, "notes": notes, "quotations": quotations, "bookings": bookings,
        "invoices": invoices, "payments": payments, "refunds": refunds, "commissions": commissions,
        "conversations": conversations, "documents": documents, "timeline": timeline,
        "totals": {"leads": len(leads), "follow_ups": len(follow_ups), "communications": len(comms),
                   "quotations": len(quotations), "bookings": len(bookings), "total_pax": total_pax,
                   "total_sales": total_sales, "total_paid": total_paid, "outstanding": outstanding,
                   "total_refund": total_refund, "total_value": total_value, "last_booking": last_booking},
    }


# ============================================================================
# PHASE 9L — CUSTOMER PORTAL (OTP login · read-only)
# ============================================================================
import random as _random


def _norm_phone(s):
    d = "".join(ch for ch in str(s or "") if ch.isdigit())
    return d.lstrip("0")


def create_customer_token(customer_id: str, identifier: str) -> str:
    payload = {"sub": customer_id, "customer_id": customer_id, "identifier": identifier,
               "type": "customer_access", "exp": datetime.now(timezone.utc) + timedelta(days=7)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def get_current_customer(request: Request) -> dict:
    token = request.cookies.get("portal_token")
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "customer_access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        cust = await db.customers.find_one({"_id": ObjectId(payload["customer_id"])})
        if not cust or cust.get("is_deleted"):
            raise HTTPException(status_code=401, detail="Customer not found")
        return cust
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def _find_customer_by_identifier(channel: str, identifier: str):
    if channel == "email":
        return await db.customers.find_one({"email": identifier.strip().lower(), "is_deleted": {"$ne": True}})
    target = _norm_phone(identifier)
    if not target:
        return None
    for c in await db.customers.find({"is_deleted": {"$ne": True}}).to_list(20000):
        cand = _norm_phone(c.get("whatsapp") or c.get("phone"))
        if cand and (cand == target or cand.endswith(target[-8:]) or target.endswith(cand[-8:])):
            return c
    return None


class PortalOtpRequest(BaseModel):
    channel: str
    identifier: str


class PortalOtpVerify(BaseModel):
    channel: str
    identifier: str
    otp: str


@api_router.post("/portal/auth/request-otp")
async def portal_request_otp(body: PortalOtpRequest, request: Request):
    channel = (body.channel or "").lower()
    if channel not in ("email", "whatsapp"):
        raise HTTPException(status_code=400, detail="channel harus 'email' atau 'whatsapp'")
    ident = (body.identifier or "").strip()
    if not ident:
        raise HTTPException(status_code=400, detail="Identifier wajib diisi")
    cust = await _find_customer_by_identifier(channel, ident)
    resp = {"sent": True, "channel": channel}
    if not cust:
        # Hindari user enumeration: tetap balas sukses tanpa OTP
        return resp
    key = ident.lower() if channel == "email" else _norm_phone(ident)
    otp = f"{_random.randint(0, 999999):06d}"
    await db.customer_otps.delete_many({"channel": channel, "key": key})
    await db.customer_otps.insert_one({
        "channel": channel, "key": key, "otp_hash": hash_password(otp),
        "customer_id": str(cust["_id"]), "attempts": 0,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "created_at": now_iso()})
    logger.info(f"[PORTAL OTP] {channel}:{key} -> {otp}")
    delivered = False
    if channel == "email" and EMAIL_KEY and cust.get("email"):
        html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;background:#f1f5f9;padding:32px"><tr><td align="center">
        <table width="440" style="background:#fff;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden">
          <tr><td style="background:#0f172a;padding:20px 28px"><span style="color:#fbbf24;font-size:18px;font-weight:700">Safar Customer Portal</span></td></tr>
          <tr><td style="padding:28px">
            <p style="color:#475569">Halo {cust.get('full_name','')}, berikut kode OTP login portal Anda:</p>
            <p style="font-size:32px;letter-spacing:8px;font-weight:800;color:#0f172a;margin:16px 0">{otp}</p>
            <p style="color:#94a3b8;font-size:12px">Berlaku 5 menit. Jangan bagikan kode ini kepada siapa pun.</p>
          </td></tr>
        </table></td></tr></table>"""
        await send_email(cust.get("email"), "Kode OTP Customer Portal", html)
        delivered = True
    elif channel == "whatsapp":
        try:
            trigger_n8n("portal.otp", {"customer_id": str(cust["_id"]), "customer_name": cust.get("full_name"),
                                       "phone": cust.get("whatsapp") or cust.get("phone"), "otp": otp})
        except Exception:
            pass
    resp["delivered"] = delivered
    # Preview/non-produksi: tampilkan OTP agar dapat diuji (terutama saat pengiriman belum aktif)
    resp["debug_otp"] = otp
    return resp


@api_router.post("/portal/auth/verify-otp")
async def portal_verify_otp(body: PortalOtpVerify, request: Request):
    channel = (body.channel or "").lower()
    key = (body.identifier or "").strip().lower() if channel == "email" else _norm_phone(body.identifier)
    rec = await db.customer_otps.find_one({"channel": channel, "key": key})
    if not rec:
        raise HTTPException(status_code=400, detail="OTP tidak ditemukan. Minta kirim ulang.")
    if rec.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
        await db.customer_otps.delete_one({"_id": rec["_id"]})
        raise HTTPException(status_code=400, detail="OTP kedaluwarsa. Minta kirim ulang.")
    if rec.get("attempts", 0) >= 5:
        await db.customer_otps.delete_one({"_id": rec["_id"]})
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan salah. Minta kirim ulang OTP.")
    if not verify_password((body.otp or "").strip(), rec["otp_hash"]):
        await db.customer_otps.update_one({"_id": rec["_id"]}, {"$inc": {"attempts": 1}})
        left = 5 - (rec.get("attempts", 0) + 1)
        raise HTTPException(status_code=400, detail=f"OTP salah. Sisa {max(left, 0)} percobaan.")
    await db.customer_otps.delete_one({"_id": rec["_id"]})
    cust = await db.customers.find_one({"_id": ObjectId(rec["customer_id"])})
    if not cust:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    token = create_customer_token(str(cust["_id"]), key)
    return {"token": token, "customer": {"id": str(cust["_id"]), "full_name": cust.get("full_name"),
                                         "email": cust.get("email"), "whatsapp": cust.get("whatsapp")}}


@api_router.get("/portal/me")
async def portal_me(cust: dict = Depends(get_current_customer)):
    return {"id": str(cust["_id"]), "full_name": cust.get("full_name"), "email": cust.get("email"),
            "whatsapp": cust.get("whatsapp"), "phone": cust.get("phone"), "city": cust.get("city"),
            "customer_code": cust.get("customer_code"), "customer_type": cust.get("customer_type")}


@api_router.get("/portal/dashboard")
async def portal_dashboard(cust: dict = Depends(get_current_customer)):
    cid = str(cust["_id"])
    tpl = await _get_doc_template()
    raw_bookings = await db.bookings.find({"customer_id": cid}).sort("created_at", -1).to_list(1000)
    booking_ids = [str(b["_id"]) for b in raw_bookings]
    today = today_str()
    dep_ids = [ObjectId(b["departure_id"]) for b in raw_bookings if b.get("departure_id") and ObjectId.is_valid(b.get("departure_id"))]
    deps = {str(d["_id"]): d for d in (await db.departures.find({"_id": {"$in": dep_ids}}).to_list(1000) if dep_ids else [])}
    bookings = []
    for b in raw_bookings:
        sched = b.get("payment_schedule") or []
        for it in sched:
            it["status"] = _sched_item_status(it, today)
            it["outstanding"] = round(float(it.get("amount") or 0) - float(it.get("paid_amount") or 0), 2)
        dep = deps.get(str(b.get("departure_id"))) if b.get("departure_id") else None
        bookings.append({
            "id": str(b["_id"]), "booking_number": b.get("booking_number"), "package_name": b.get("package_name"),
            "package_id": b.get("package_id"), "pax": b.get("pax"), "status": b.get("status"),
            "total": b.get("total"), "room_type": b.get("room_type"), "created_at": b.get("created_at"),
            "departure": ({"date": dep.get("departure_date"), "return_date": dep.get("return_date"), "flight": dep.get("flight")} if dep else None),
            "payment_schedule": sched})
    raw_invoices = await db.invoices.find({"customer_id": cid}).sort("created_at", -1).to_list(1000)
    invoices = [{"id": str(i["_id"]), "invoice_number": i.get("invoice_number"),
                 "total": i.get("total") if i.get("total") is not None else i.get("amount"),
                 "outstanding": i.get("outstanding"), "status": i.get("status"),
                 "due_date": i.get("due_date"), "created_at": i.get("created_at"),
                 "public_url": _public_pdf_url(tpl, "invoice", str(i["_id"])),
                 "booking_number": i.get("booking_number")} for i in raw_invoices]
    inv_ids = [str(i["_id"]) for i in raw_invoices]
    payments = await db.payments.find({"$or": [{"invoice_id": {"$in": inv_ids}}, {"booking_id": {"$in": booking_ids}}]}).to_list(2000)
    refunds = [{"refund_number": r.get("refund_number"), "status": r.get("status"),
                "amount": r.get("approved_refund") or r.get("proposed_refund") or 0,
                "created_at": r.get("created_at"), "booking_number": r.get("booking_number")}
               for r in await db.refund_requests.find({"$or": [{"customer_id": cid}, {"booking_id": {"$in": booking_ids}}]}).sort("created_at", -1).to_list(500)]
    documents = [{"doc_type": d.get("doc_type"), "status": d.get("status"),
                  "file_url": d.get("file_url") or d.get("url"), "expiry_date": d.get("expiry_date"),
                  "booking_id": d.get("booking_id"), "created_at": d.get("created_at") or d.get("uploaded_at")}
                 for d in await db.documents.find({"$or": [{"booking_id": {"$in": booking_ids}}, {"customer_id": cid}], "is_deleted": {"$ne": True}}).to_list(2000)]
    total = sum(float(b.get("total") or 0) for b in raw_bookings if b.get("status") != "CANCELLED")
    paid = sum(float(p.get("amount") or 0) for p in payments)
    outstanding = sum(float(i.get("outstanding") or 0) for i in raw_invoices)
    if outstanding <= 0:
        outstanding = max(total - paid, 0)
    next_due = None
    for b in bookings:
        for it in (b["payment_schedule"] or []):
            if it.get("status") in ("PENDING", "PARTIAL", "OVERDUE") and it.get("due_date"):
                cand = {"date": (it.get("due_date") or "")[:10], "amount": it.get("outstanding"), "booking_number": b["booking_number"]}
                if next_due is None or cand["date"] < next_due["date"]:
                    next_due = cand
    profile = {"id": cid, "full_name": cust.get("full_name"), "email": cust.get("email"),
               "whatsapp": cust.get("whatsapp"), "phone": cust.get("phone"), "city": cust.get("city"),
               "customer_code": cust.get("customer_code"), "customer_type": cust.get("customer_type")}
    receipts = [{"id": str(r["_id"]), "receipt_number": r.get("receipt_number"), "amount": r.get("amount"),
                 "booking_number": r.get("booking_number"), "label": r.get("label"),
                 "public_url": _public_pdf_url(tpl, "receipt", str(r["_id"])),
                 "created_at": r.get("created_at")}
                for r in await db.schedule_payments.find({"customer_id": cid}).sort("created_at", -1).to_list(500)]
    return {"profile": profile, "bookings": bookings, "invoices": invoices, "refunds": refunds, "documents": documents,
            "receipts": receipts,
            "summary": {"total": round(total, 2), "paid": round(paid, 2), "outstanding": round(outstanding, 2),
                        "next_due": next_due, "bookings_count": len([b for b in raw_bookings if b.get('status') != 'CANCELLED'])}}



# ---------- Leads / Pipeline ----------
@api_router.get("/leads")
async def list_leads(status: Optional[str] = None, include_archived: bool = False, user: dict = Depends(require_permission("sales.view"))):
    query = owner_filter(user)
    if not include_archived:
        query["is_deleted"] = {"$ne": True}
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
    await notify("New Lead", f"{lead.get('customer_name') or lead.get('interested_package') or lead.get('lead_code')} assigned to you",
                 link=f"/crm/{body.customer_id}" if body.customer_id else "/sales", user_id=pic_id, ntype="NEW_LEAD", priority="high")
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
async def delete_lead(lid: str, request: Request, reason: str = Query(""), user: dict = Depends(require_role("super_admin"))):
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Reason is required to archive a lead")
    doc = await db.leads.find_one({"_id": ObjectId(lid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.leads.update_one({"_id": ObjectId(lid)}, {"$set": {"is_deleted": True, "status": "ARCHIVED", "archived_by": user["name"], "archived_at": now_iso()}})
    await log_audit(user, "lead", "archive_lead", request, record_id=lid, new={"status": "ARCHIVED"}, reason=reason)
    return {"message": "Lead archived", "status": "ARCHIVED"}


@api_router.post("/leads/{lid}/restore")
async def restore_lead(lid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.leads.find_one({"_id": ObjectId(lid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Lead not found")
    await db.leads.update_one({"_id": ObjectId(lid)}, {"$set": {"is_deleted": False, "status": "NEW"}})
    await log_audit(user, "lead", "restore_lead", request, record_id=lid, new={"status": "NEW"})
    return {"message": "Lead restored"}


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
    await create_task(f"Follow Up: {body.activity_type}" + (f" — {customer_name}" if customer_name else ""),
                      assigned_user_id=pic_id, assigned_user_name=pic_name, customer_id=body.customer_id,
                      lead_id=body.lead_id, due_date=body.due_date, priority="MEDIUM",
                      notes=body.notes or "", created_by=user["name"], source="follow_up")
    await notify("Follow Up Scheduled", f"{body.activity_type}" + (f" — {customer_name}" if customer_name else ""),
                 link=f"/crm/{body.customer_id}" if body.customer_id else "/follow-ups",
                 user_id=pic_id, ntype="FOLLOW_UP", priority="normal")
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


# ============================================================================
# PHASE 9K — SALES ACTIVITY & PERFORMANCE
# ============================================================================
SALES_ACTIVITY_TYPES = ["Call", "WhatsApp", "Email", "Meeting"]
ACTIVITY_TYPES_ALL = ["Call", "WhatsApp", "Email", "Meeting", "Follow Up", "Quotation", "Booking"]
ACTIVITY_SCORE_WEIGHTS = {"Call": 1, "WhatsApp": 1, "Email": 1, "Meeting": 3, "Follow Up": 2, "Quotation": 5, "Booking": 10}


class SalesActivityCreate(BaseModel):
    activity_type: str
    customer_id: Optional[str] = None
    lead_id: Optional[str] = None
    notes: Optional[str] = ""
    sales_id: Optional[str] = None  # super admin may log on behalf of a sales


@api_router.post("/sales/activities")
async def create_sales_activity(body: SalesActivityCreate, user: dict = Depends(require_permission("sales.view"))):
    if body.activity_type not in SALES_ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail=f"activity_type harus salah satu dari {SALES_ACTIVITY_TYPES}")
    pic_id, pic_name, branch = await resolve_pic(user, body.sales_id)
    cust = await db.customers.find_one({"_id": ObjectId(body.customer_id)}) if (body.customer_id and ObjectId.is_valid(body.customer_id)) else None
    doc = {"activity_type": body.activity_type, "customer_id": body.customer_id,
           "customer_name": (cust or {}).get("full_name", ""), "lead_id": body.lead_id,
           "notes": body.notes or "", "sales_pic_id": pic_id, "sales_pic_name": pic_name,
           "branch": branch, "timestamp": now_iso()}
    res = await db.sales_activities.insert_one(doc)
    return serialize(await db.sales_activities.find_one({"_id": res.inserted_id}))


@api_router.get("/sales/activities")
async def list_sales_activities(sales_id: Optional[str] = None, activity_type: Optional[str] = None,
                                frm: Optional[str] = None, to: Optional[str] = None, limit: int = 100,
                                user: dict = Depends(require_permission("sales.view"))):
    scope = {"sales_pic_id": user["_id"]} if user["role"] == "sales" else ({"sales_pic_id": sales_id} if sales_id else {})
    feed = []
    mq = dict(scope)
    if activity_type and activity_type in SALES_ACTIVITY_TYPES:
        mq["activity_type"] = activity_type
    for a in await db.sales_activities.find(mq).sort("timestamp", -1).to_list(3000):
        if _in_range(a.get("timestamp"), frm, to):
            feed.append({"id": str(a["_id"]), "activity_type": a.get("activity_type"), "sales": a.get("sales_pic_name"),
                         "sales_pic_id": a.get("sales_pic_id"), "customer_name": a.get("customer_name", ""),
                         "detail": a.get("notes", ""), "timestamp": a.get("timestamp")})
    show_all = not activity_type
    if show_all or activity_type == "Follow Up":
        for f in await db.follow_ups.find(scope).to_list(3000):
            ts = f.get("created_at") or f.get("due_date")
            if _in_range(ts, frm, to):
                feed.append({"id": str(f["_id"]), "activity_type": "Follow Up", "sales": f.get("sales_pic_name"),
                             "sales_pic_id": f.get("sales_pic_id"), "customer_name": f.get("customer_name", ""),
                             "detail": f"{f.get('activity_type', '')} — {f.get('notes', '')}".strip(" —"), "timestamp": ts})
    if show_all or activity_type == "Quotation":
        for qd in await db.quotations.find(scope).to_list(3000):
            if _in_range(qd.get("created_at"), frm, to):
                feed.append({"id": str(qd["_id"]), "activity_type": "Quotation", "sales": qd.get("sales_pic_name"),
                             "sales_pic_id": qd.get("sales_pic_id"), "customer_name": qd.get("customer_name", ""),
                             "detail": f"{qd.get('package_name', '')} · {qd.get('pax', 0)} pax", "timestamp": qd.get("created_at")})
    if show_all or activity_type == "Booking":
        for bd in await db.bookings.find({**scope, "status": {"$ne": "CANCELLED"}}).to_list(3000):
            if _in_range(bd.get("created_at"), frm, to):
                feed.append({"id": str(bd["_id"]), "activity_type": "Booking", "sales": bd.get("sales_pic_name"),
                             "sales_pic_id": bd.get("sales_pic_id"), "customer_name": bd.get("customer_name", ""),
                             "detail": f"{bd.get('package_name', '')} · {bd.get('pax', 0)} pax", "timestamp": bd.get("created_at")})
    feed.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return feed[:max(1, min(limit, 500))]


@api_router.get("/sales/performance")
async def sales_performance(frm: Optional[str] = None, to: Optional[str] = None, sales_id: Optional[str] = None,
                            period: Optional[str] = None, user: dict = Depends(require_permission("sales.view"))):
    if period and not frm and not to:
        y, m = int(period[:4]), int(period[5:7])
        import calendar
        frm = f"{period}-01"
        to = f"{period}-{calendar.monthrange(y, m)[1]:02d}"
    susers = await db.users.find({"role": "sales"}).to_list(500)
    if user["role"] == "sales":
        susers = [u for u in susers if str(u["_id"]) == user["_id"]]
    elif sales_id:
        susers = [u for u in susers if str(u["_id"]) == sales_id]

    leads = await db.leads.find({}).to_list(20000)
    quotes = await db.quotations.find({}).to_list(20000)
    bks = [b for b in await db.bookings.find({}).to_list(20000) if b.get("status") != "CANCELLED" and _in_range(b.get("created_at"), frm, to)]
    fus = await db.follow_ups.find({}).to_list(20000)
    lines = await db.commission_lines.find({}).to_list(20000)
    acts = [a for a in await db.sales_activities.find({}).to_list(50000) if _in_range(a.get("timestamp"), frm, to)]
    tmap = {}
    if period:
        for t in await db.sales_targets.find({"period": period}).to_list(2000):
            tmap[t.get("sales_id")] = t

    rows = []
    for u in susers:
        sid = str(u["_id"])
        ul = [l for l in leads if l.get("sales_pic_id") == sid and _in_range(l.get("created_at"), frm, to)]
        uq = [x for x in quotes if x.get("sales_pic_id") == sid and _in_range(x.get("created_at"), frm, to)]
        conv = [x for x in uq if x.get("status") == "ACCEPTED" or x.get("converted_booking_id")]
        ub = [b for b in bks if b.get("sales_pic_id") == sid]
        ufu = [f for f in fus if f.get("sales_pic_id") == sid and _in_range(f.get("created_at") or f.get("due_date"), frm, to)]
        ua = [a for a in acts if a.get("sales_pic_id") == sid]
        breakdown = {t: 0 for t in ACTIVITY_TYPES_ALL}
        for a in ua:
            if a.get("activity_type") in breakdown:
                breakdown[a["activity_type"]] += 1
        breakdown["Follow Up"] = len(ufu)
        breakdown["Quotation"] = len(uq)
        breakdown["Booking"] = len(ub)
        activity_score = sum(breakdown[t] * ACTIVITY_SCORE_WEIGHTS.get(t, 0) for t in breakdown)
        revenue = sum(float(b.get("total") or 0) for b in ub)
        pax = sum(int(b.get("pax") or 0) for b in ub)
        t = tmap.get(sid) or {}
        rt = float(t.get("revenue_target") or 0)
        pt = int(t.get("pax_target") or 0)
        rows.append({
            "sales_id": sid, "sales": u.get("name"),
            "leads": len(ul), "follow_up": len(ufu), "quotation": len(uq),
            "converted": len(conv), "conversion_rate": _pct(len(conv), len(uq)),
            "booking": len(ub), "pax": pax, "revenue": revenue,
            "commission": sum(float(c.get("final_commission") or 0) for c in lines if c.get("sales_pic_id") == sid),
            "activity_breakdown": breakdown, "total_activities": sum(breakdown.values()),
            "activity_score": activity_score,
            "revenue_target": rt, "pax_target": pt,
            "revenue_progress": _pct(revenue, rt) if rt else 0,
            "pax_progress": _pct(pax, pt) if pt else 0,
        })

    def top(k):
        return [{"sales_id": r["sales_id"], "sales": r["sales"], "value": r[k]} for r in sorted(rows, key=lambda r: -(r[k] or 0))]

    return {"title": "Sales Activity & Performance", "period": {"from": frm, "to": to, "month": period},
            "score_weights": ACTIVITY_SCORE_WEIGHTS, "rows": rows,
            "rankings": {"by_revenue": top("revenue"), "by_pax": top("pax"), "by_booking": top("booking"),
                         "by_conversion": top("conversion_rate"), "by_activity": top("activity_score")}}


@api_router.post("/sales/ai-assist/{customer_id}")
async def sales_ai_assist(customer_id: str, body: dict, user: dict = Depends(require_permission("sales.view"))):
    import json as _json
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    mode = (body or {}).get("mode", "summary")
    if not ObjectId.is_valid(customer_id):
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    c = await db.customers.find_one({"_id": ObjectId(customer_id), "is_deleted": {"$ne": True}})
    if not c:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if user["role"] == "sales" and str(c.get("sales_pic_id")) != user["_id"]:
        raise HTTPException(status_code=403, detail="Bukan customer Anda")
    cid = str(c["_id"])
    leads = await db.leads.find({"customer_id": cid}).to_list(50)
    comms = await db.communications.find({"customer_id": cid}).sort("timestamp", -1).to_list(20)
    quotes = await db.quotations.find({"customer_id": cid}).to_list(20)
    bks = await db.bookings.find({"customer_id": cid}).to_list(20)
    fus = await db.follow_ups.find({"customer_id": cid}).sort("created_at", -1).to_list(10)
    pkgs = await db.packages.find({"is_active": True}).to_list(30)

    def m(n):
        return f"Rp{int(float(n or 0)):,}".replace(",", ".")

    ctx = {
        "customer": {"name": c.get("full_name"), "phone": c.get("whatsapp") or c.get("phone"), "city": c.get("city"),
                     "interest": c.get("interest") or c.get("notes"), "stage": c.get("stage")},
        "interests": [l.get("interest") or l.get("notes") for l in leads],
        "conversations": [{"t": (x.get("timestamp") or "")[:16], "dir": x.get("direction"), "ch": x.get("channel"),
                           "msg": (x.get("message") or x.get("content") or "")[:200]} for x in comms],
        "quotations": [{"pkg": q.get("package_name"), "pax": q.get("pax"), "total": m(q.get("total")), "status": q.get("status")} for q in quotes],
        "bookings": [{"pkg": b.get("package_name"), "pax": b.get("pax"), "status": b.get("status"), "total": m(b.get("total"))} for b in bks],
        "last_follow_up": ({"date": (fus[0].get("created_at") or "")[:16], "type": fus[0].get("activity_type"), "notes": fus[0].get("notes")} if fus else None),
        "packages_catalog": [{"name": p.get("package_name"), "price": m(p.get("selling_price") or p.get("price")), "type": p.get("package_type")} for p in pkgs],
    }
    prompts = {
        "summary": "Ringkas customer ini untuk sales (Bahasa Indonesia): profil, minat, ringkasan percakapan, status quotation & booking, dan follow up terakhir. Singkat, poin-poin.",
        "followup": "Buat 1 draft pesan follow-up WhatsApp yang sopan, personal, dan persuasif (Bahasa Indonesia) berdasarkan history customer, dengan ajakan langkah berikutnya. Ini hanya draft; jangan kirim.",
        "suggestion": "Berikan: 1) Recommended package (pilih dari katalog) + alasan singkat, 2) Suggested response untuk pesan terakhir customer, 3) Follow up strategy. Bahasa Indonesia, ringkas.",
    }
    sys = ("Anda asisten internal untuk tim SALES travel umrah. Gunakan HANYA data yang diberikan. "
           "DILARANG menyebut HPP, modal, biaya supplier, atau margin. Output hanya saran/draft; "
           "sales wajib menyetujui sebelum mengirim ke customer.")
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"ai-{cid}-{mode}", system_message=sys).with_model("gemini", "gemini-3-flash-preview")
    prompt = prompts.get(mode, prompts["summary"]) + "\n\nDATA:\n" + _json.dumps(ctx, ensure_ascii=False)
    try:
        resp = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI error: {e}")
    return {"mode": mode, "draft": resp, "requires_approval": True, "customer_name": c.get("full_name")}


class SalesTargetInput(BaseModel):
    sales_id: str
    period: str
    revenue_target: float = 0
    pax_target: int = 0


@api_router.get("/sales/targets")
async def list_sales_targets(period: Optional[str] = None, sales_id: Optional[str] = None,
                             user: dict = Depends(require_permission("sales.view"))):
    q = {}
    if period:
        q["period"] = period
    if user["role"] == "sales":
        q["sales_id"] = user["_id"]
    elif sales_id:
        q["sales_id"] = sales_id
    docs = await db.sales_targets.find(q).to_list(2000)
    return [serialize(d) for d in docs]


@api_router.put("/sales/targets")
async def upsert_sales_target(body: SalesTargetInput, request: Request, user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(body.sales_id):
        raise HTTPException(status_code=400, detail="sales_id tidak valid")
    su = await db.users.find_one({"_id": ObjectId(body.sales_id), "role": "sales"})
    if not su:
        raise HTTPException(status_code=404, detail="Sales tidak ditemukan")
    doc = {"sales_id": body.sales_id, "sales_name": su.get("name"), "period": body.period,
           "revenue_target": float(body.revenue_target or 0), "pax_target": int(body.pax_target or 0),
           "updated_at": now_iso(), "updated_by": user["name"]}
    await db.sales_targets.update_one({"sales_id": body.sales_id, "period": body.period}, {"$set": doc}, upsert=True)
    await log_audit(user, "sales_target", "upsert", request, record_id=f"{body.sales_id}:{body.period}",
                    new={"revenue_target": doc["revenue_target"], "pax_target": doc["pax_target"]})
    return {"success": True, **doc}


class SalesTargetBulkItem(BaseModel):
    period: str
    revenue_target: float = 0
    pax_target: int = 0


class SalesTargetBulkInput(BaseModel):
    sales_id: str
    targets: List[SalesTargetBulkItem]


@api_router.put("/sales/targets/bulk")
async def bulk_upsert_sales_targets(body: SalesTargetBulkInput, request: Request, user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(body.sales_id):
        raise HTTPException(status_code=400, detail="sales_id tidak valid")
    su = await db.users.find_one({"_id": ObjectId(body.sales_id), "role": "sales"})
    if not su:
        raise HTTPException(status_code=404, detail="Sales tidak ditemukan")
    count = 0
    for t in body.targets:
        if not t.period:
            continue
        doc = {"sales_id": body.sales_id, "sales_name": su.get("name"), "period": t.period,
               "revenue_target": float(t.revenue_target or 0), "pax_target": int(t.pax_target or 0),
               "updated_at": now_iso(), "updated_by": user["name"]}
        await db.sales_targets.update_one({"sales_id": body.sales_id, "period": t.period}, {"$set": doc}, upsert=True)
        count += 1
    await log_audit(user, "sales_target", "bulk_upsert", request, record_id=body.sales_id, new={"months": count})
    return {"success": True, "count": count}


# ---------- Global Search ----------
@api_router.get("/search")
async def global_search(q: str, user: dict = Depends(require_permission("crm.view"))):
    of = owner_filter(user)
    rx = {"$regex": q, "$options": "i"}
    sales_scope = user["role"] == "sales" and user.get("data_scope", "own") not in ("all",)
    customers = [serialize(d) for d in await db.customers.find({**of, "$or": [
        {"full_name": rx}, {"whatsapp": rx}, {"phone": rx}, {"email": rx}, {"customer_code": rx}]}).limit(8).to_list(8)]
    leads = [serialize(d) for d in await db.leads.find({**of, "$or": [
        {"lead_code": rx}, {"customer_name": rx}, {"interested_package": rx}, {"destination": rx}]}).limit(8).to_list(8)]
    quotations = [serialize(d) for d in await db.quotations.find({**of, "$or": [
        {"quotation_number": rx}, {"customer_name": rx}, {"package_name": rx}]}).limit(8).to_list(8)]
    bookings = [serialize(d) for d in await db.bookings.find({**of, "$or": [
        {"booking_number": rx}, {"customer_name": rx}, {"package_name": rx}]}).limit(8).to_list(8)]
    inv_of = {"sales_pic_id": user["_id"]} if sales_scope else {}
    invoices = [serialize(d) for d in await db.invoices.find({**inv_of, "$or": [
        {"invoice_number": rx}, {"customer_name": rx}, {"booking_number": rx}]}).limit(8).to_list(8)]
    packages = [{"_id": str(p["_id"]), "id": str(p["_id"]), "package_code": p.get("package_code", ""),
                 "package_name": p.get("package_name", ""), "product_type": p.get("product_type", ""),
                 "destination": p.get("destination", "")} for p in await db.packages.find({"$or": [
        {"package_name": rx}, {"package_code": rx}]}).limit(8).to_list(8)]
    allowed_bids = allowed_cids = None
    if sales_scope:
        mine = await db.bookings.find({"sales_pic_id": user["_id"]}).to_list(5000)
        allowed_bids = {str(b["_id"]) for b in mine}
        myc = await db.customers.find({"sales_pic_id": user["_id"]}).to_list(5000)
        allowed_cids = {str(cc["_id"]) for cc in myc}
    pay_docs = await db.payments.find({"$or": [{"reference_number": rx}, {"invoice_number": rx}]}).limit(30).to_list(30)
    if allowed_bids is not None:
        pay_docs = [p for p in pay_docs if p.get("booking_id") in allowed_bids]
    payments = [serialize(d) for d in pay_docs[:8]]
    ref_docs = await db.refund_requests.find({"$or": [{"refund_number": rx}, {"customer_name": rx}]}).limit(30).to_list(30)
    if allowed_bids is not None:
        ref_docs = [r for r in ref_docs if (r.get("booking_id") in allowed_bids or r.get("customer_id") in (allowed_cids or set()))]
    refunds = [serialize(d) for d in ref_docs[:8]]
    conv_docs = await db.conversations.find({"$or": [{"whatsapp": rx}, {"customer_name": rx}, {"message": rx}]}).limit(30).to_list(30)
    if allowed_cids is not None:
        conv_docs = [cv for cv in conv_docs if cv.get("customer_id") in allowed_cids]
    conversations = [serialize(d) for d in conv_docs[:8]]
    return {"customers": customers, "leads": leads, "quotations": quotations, "bookings": bookings,
            "invoices": invoices, "packages": packages, "payments": payments, "refunds": refunds,
            "conversations": conversations}


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


async def resolve_ppn_config(date_str, tax_type="PPN"):
    """Return the ACTIVE PPN configuration version that applies on a given date (versioned by effective range)."""
    d = (date_str or now_iso())[:10]
    cfgs = await db.ppn_configurations.find({"status": "ACTIVE", "tax_type": tax_type}).sort("effective_from", -1).to_list(200)
    for c in cfgs:
        ef = (c.get("effective_from") or "")[:10]
        eu = (c.get("effective_until") or "")[:10]
        if ef and d < ef:
            continue
        if eu and d > eu:
            continue
        return c
    return None


async def tax_snapshot(date_str, dpp_base):
    """Snapshot the applicable PPN config version onto a transaction (non-destructive; does not alter monetary tax)."""
    c = await resolve_ppn_config(date_str)
    if not c:
        return {}
    dppp = float(c.get("dpp_percentage") or 100)
    return {"tax_type": c.get("tax_type", "PPN"), "tax_config_id": str(c["_id"]),
            "tax_config_version": c.get("config_name"), "tax_rate": float(c.get("tax_rate") or 0),
            "dpp_percentage": dppp, "dpp_amount": round(float(dpp_base or 0) * dppp / 100)}


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
    include: Optional[str] = ""
    exclude: Optional[str] = ""
    min_pax: Optional[int] = 1
    max_pax: Optional[int] = 40
    selling_price: Optional[float] = 0
    child_price: Optional[float] = 0
    infant_price: Optional[float] = 0
    single_supplement: Optional[float] = 0
    currency: Optional[str] = "IDR"
    tax_treatment: Optional[str] = "Non-PPN"
    commission_eligibility: Optional[bool] = True
    max_discount_type: Optional[str] = "PERCENT"
    max_discount_value: Optional[float] = 0
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


# ---- Operations: Departure Management (Phase 9I) ----
UMRAH_REQUIRED_DOCS = ["KTP", "KK", "PASSPORT", "PHOTO", "VISA", "VACCINE_CERT", "SISKOPATUH"]
TOUR_REQUIRED_DOCS = ["KTP", "PASSPORT"]


def _required_docs(product_type):
    return TOUR_REQUIRED_DOCS if (product_type or "").upper() == "TOUR" else UMRAH_REQUIRED_DOCS


async def _dep_payment_map(bookings):
    paid = partial = unpaid = 0
    bmap = {}
    for b in bookings:
        invs = await db.invoices.find({"booking_id": str(b["_id"])}).to_list(50)
        tot = sum(float(i.get("total") or i.get("amount") or 0) for i in invs)
        pd = sum(float(i.get("paid_amount") or 0) for i in invs)
        if invs and tot > 0 and pd >= tot:
            st = "PAID"; paid += 1
        elif pd > 0:
            st = "PARTIAL"; partial += 1
        else:
            st = "UNPAID"; unpaid += 1
        bmap[str(b["_id"])] = {"payment_status": st, "outstanding": max(tot - pd, 0)}
    return bmap, paid, partial, unpaid


@api_router.get("/operations/departures")
async def operations_departures(within: str = "all", user: dict = Depends(require_role("super_admin", "accounting"))):
    from datetime import date, timedelta
    today = date.today()
    q = {}
    if within in ("7", "14", "30", "60"):
        end = (today + timedelta(days=int(within))).isoformat()
        q = {"departure_date": {"$gte": today.isoformat(), "$lte": end}}
    deps = await db.departures.find(q).sort("departure_date", 1).to_list(500)
    pkgs = {str(p["_id"]): p for p in await db.packages.find({}).to_list(1000)}
    out = []
    for d in deps:
        did = str(d["_id"])
        pkg = pkgs.get(d.get("package_id"))
        bookings = await db.bookings.find({"departure_id": did, "status": {"$ne": "CANCELLED"}}).to_list(1000)
        booked = sum(int(b.get("pax") or 0) for b in bookings)
        total_seat = int(d.get("quota") or 0)
        cd = compute_departure(serialize(d))
        out.append({"id": did, "_id": did, "package_id": d.get("package_id"),
                    "package_name": (pkg or {}).get("package_name", ""), "product_type": (pkg or {}).get("product_type", ""),
                    "departure_date": d.get("departure_date"), "return_date": d.get("return_date"),
                    "total_seat": total_seat, "booked_seat": booked, "available_seat": max(total_seat - booked, 0),
                    "status": cd.get("status"), "flight": d.get("flight"), "hotel": d.get("hotel")})
    return out


@api_router.get("/operations/departures/{did}")
async def operations_departure_detail(did: str, user: dict = Depends(require_role("super_admin", "accounting"))):
    dep = await db.departures.find_one({"_id": ObjectId(did)}) if ObjectId.is_valid(did) else None
    if not dep:
        raise HTTPException(status_code=404, detail="Departure not found")
    pkg = await db.packages.find_one({"_id": ObjectId(dep["package_id"])}) if ObjectId.is_valid(dep.get("package_id") or "") else None
    ptype = (pkg or {}).get("product_type", "TOUR")
    required = _required_docs(ptype)
    bookings = await db.bookings.find({"departure_id": did, "status": {"$ne": "CANCELLED"}}).to_list(1000)
    booked = sum(int(b.get("pax") or 0) for b in bookings)
    total_seat = int(dep.get("quota") or 0)
    available = max(total_seat - booked, 0)
    bmap, paid, partial, unpaid = await _dep_payment_map(bookings)
    bids = [str(b["_id"]) for b in bookings]
    travelers = await db.travelers.find({"booking_id": {"$in": bids}}).to_list(2000)
    dep_date = (dep.get("departure_date") or "")[:10]
    docs_complete = docs_missing = passport_expired_cnt = 0
    passengers = []
    for t in travelers:
        tid = str(t["_id"])
        tdocs = await db.documents.find({"traveler_id": tid, "is_deleted": {"$ne": True}}).to_list(50)
        have = {d.get("doc_type") for d in tdocs}
        missing = [r for r in required if r not in have]
        complete = len(missing) == 0
        docs_complete += 1 if complete else 0
        docs_missing += 0 if complete else 1
        pexp = (t.get("passport_expiry") or "")[:10]
        expired = bool(pexp and dep_date and pexp < dep_date)
        passport_expired_cnt += 1 if expired else 0
        b = next((x for x in bookings if str(x["_id"]) == t.get("booking_id")), None)
        pinfo = bmap.get(t.get("booking_id"), {})
        passengers.append({"traveler_id": tid, "booking_id": t.get("booking_id"),
                           "customer_name": (b or {}).get("customer_name", t.get("full_name", "")),
                           "full_name": t.get("full_name"), "gender": t.get("gender"),
                           "passport_number": t.get("passport_number"), "passport_expiry": pexp, "passport_expired": expired,
                           "payment_status": pinfo.get("payment_status", "UNPAID"), "booking_status": (b or {}).get("status", ""),
                           "document_status": "COMPLETE" if complete else "INCOMPLETE", "missing_docs": missing,
                           "room": t.get("room", ""), "group": t.get("group", ""), "bus": t.get("bus", ""), "room_type": t.get("room_type", "")})
    days_to = None
    if dep_date:
        from datetime import date as _d
        try:
            days_to = (_d.fromisoformat(dep_date) - _d.today()).days
        except Exception:
            days_to = None
    alerts = []
    if total_seat and 0 < available <= max(1, round(total_seat * 0.1)):
        alerts.append({"type": "SEAT_ALMOST_FULL", "severity": "warning", "message": f"Seat hampir penuh: sisa {available} dari {total_seat}"})
    if total_seat and available == 0:
        alerts.append({"type": "SEAT_FULL", "severity": "info", "message": "Seat penuh"})
    if unpaid + partial > 0:
        alerts.append({"type": "PAYMENT_DUE", "severity": "warning", "message": f"{unpaid + partial} booking belum lunas ({unpaid} unpaid, {partial} partial)"})
    if passport_expired_cnt > 0:
        alerts.append({"type": "PASSPORT_EXPIRED", "severity": "danger", "message": f"{passport_expired_cnt} paspor kedaluwarsa sebelum keberangkatan"})
    if docs_missing > 0:
        alerts.append({"type": "DOCS_INCOMPLETE", "severity": "warning", "message": f"{docs_missing} jamaah dokumen belum lengkap"})
    if days_to is not None and 0 <= days_to <= 14:
        alerts.append({"type": "DEPARTURE_APPROACHING", "severity": "info", "message": f"Keberangkatan dalam {days_to} hari"})
    return {"departure": {**serialize(dep), "package_name": (pkg or {}).get("package_name", ""), "product_type": ptype,
                          "total_seat": total_seat, "booked_seat": booked, "available_seat": available, "days_to": days_to},
            "dashboard": {"total_seat": total_seat, "booked": booked, "available": available, "paid": paid, "partial": partial,
                          "unpaid": unpaid, "documents_complete": docs_complete, "documents_missing": docs_missing, "required_docs": required},
            "passengers": passengers, "alerts": alerts}


@api_router.patch("/operations/travelers/{tid}/rooming")
async def set_traveler_rooming(tid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin", "accounting"))):
    if not ObjectId.is_valid(tid):
        raise HTTPException(status_code=404, detail="Traveler not found")
    upd = {k: body.get(k) for k in ("room", "group", "bus", "room_type") if k in body}
    if not upd:
        raise HTTPException(status_code=400, detail="No rooming fields provided")
    r = await db.travelers.update_one({"_id": ObjectId(tid)}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Traveler not found")
    await log_audit(user, "booking", "rooming", request, record_id=tid, new=upd)
    return {"success": True, **upd}


async def _op_departure_passengers(did):
    dep = await db.departures.find_one({"_id": ObjectId(did)}) if ObjectId.is_valid(did) else None
    if not dep:
        return None, None, []
    pkg = await db.packages.find_one({"_id": ObjectId(dep["package_id"])}) if ObjectId.is_valid(dep.get("package_id") or "") else None
    required = _required_docs((pkg or {}).get("product_type", "TOUR"))
    bookings = await db.bookings.find({"departure_id": did, "status": {"$ne": "CANCELLED"}}).to_list(1000)
    bmap, _, _, _ = await _dep_payment_map(bookings)
    bids = [str(b["_id"]) for b in bookings]
    travelers = await db.travelers.find({"booking_id": {"$in": bids}}).to_list(2000)
    dep_date = (dep.get("departure_date") or "")[:10]
    out = []
    for t in travelers:
        tid = str(t["_id"])
        tdocs = await db.documents.find({"traveler_id": tid, "is_deleted": {"$ne": True}}).to_list(50)
        have = {d.get("doc_type") for d in tdocs}
        missing = [r for r in required if r not in have]
        b = next((x for x in bookings if str(x["_id"]) == t.get("booking_id")), None)
        pinfo = bmap.get(t.get("booking_id"), {})
        pexp = (t.get("passport_expiry") or "")[:10]
        out.append({"full_name": t.get("full_name"), "customer_name": (b or {}).get("customer_name", ""),
                    "gender": t.get("gender") or "", "passport_number": t.get("passport_number") or "",
                    "passport_expiry": pexp, "passport_expired": bool(pexp and dep_date and pexp < dep_date),
                    "room": t.get("room") or "", "group": t.get("group") or "", "bus": t.get("bus") or "",
                    "room_type": t.get("room_type") or "", "payment_status": pinfo.get("payment_status", "UNPAID"),
                    "document_status": "COMPLETE" if not missing else "INCOMPLETE"})
    return dep, pkg, out


@api_router.get("/operations/departures/{did}/manifest.pdf")
async def departure_manifest_pdf(did: str, request: Request, auth: str = Query(None)):
    auth_h = request.headers.get("authorization") or ""
    token = auth_h[7:] if auth_h.startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user or user.get("role") not in ("super_admin", "accounting"):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    dep, pkg, passengers = await _op_departure_passengers(did)
    if not dep:
        raise HTTPException(status_code=404, detail="Departure not found")
    import io
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=12 * mm, rightMargin=12 * mm)
    styles = getSampleStyleSheet()
    el = [Paragraph(f"Manifest Keberangkatan — {(pkg or {}).get('package_name', '')}", styles["Title"]),
          Paragraph(f"Tanggal: {(dep.get('departure_date') or '')[:10]} s/d {(dep.get('return_date') or '')[:10]} | Flight: {dep.get('flight') or '-'} | Hotel: {dep.get('hotel') or '-'}", styles["Normal"]),
          Spacer(1, 6 * mm)]
    rows = [["No", "Nama", "L/P", "Paspor", "Room", "Group", "Bus", "Payment", "Docs"]]
    for i, p in enumerate(passengers, 1):
        rows.append([str(i), p["full_name"] or "", (p["gender"] or "")[:1],
                     (p["passport_number"] or "") + (" (EXP)" if p["passport_expired"] else ""),
                     p["room_type"] or p["room"], p["group"], p["bus"], p["payment_status"], p["document_status"]])
    if len(rows) == 1:
        rows.append(["-", "Tidak ada penumpang", "", "", "", "", "", "", ""])
    tbl = Table(rows, repeatRows=1)
    tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                             ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8),
                             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])]))
    el.append(tbl)
    doc.build(el)
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=manifest_{did}.pdf"})


@api_router.get("/operations/alerts-summary")
async def operations_alerts_summary(user: dict = Depends(require_role("super_admin", "accounting"))):
    from datetime import date, timedelta
    today = date.today()
    end = (today + timedelta(days=30)).isoformat()
    deps = await db.departures.find({"departure_date": {"$gte": today.isoformat(), "$lte": end}}).sort("departure_date", 1).to_list(200)
    pkgs = {str(p["_id"]): p for p in await db.packages.find({}).to_list(1000)}
    out = []
    for d in deps:
        did = str(d["_id"])
        pkg = pkgs.get(d.get("package_id"))
        required = _required_docs((pkg or {}).get("product_type", "TOUR"))
        bookings = await db.bookings.find({"departure_id": did, "status": {"$ne": "CANCELLED"}}).to_list(1000)
        booked = sum(int(b.get("pax") or 0) for b in bookings)
        total_seat = int(d.get("quota") or 0)
        available = max(total_seat - booked, 0)
        _, paid, partial, unpaid = await _dep_payment_map(bookings)
        bids = [str(b["_id"]) for b in bookings]
        travelers = await db.travelers.find({"booking_id": {"$in": bids}}).to_list(2000)
        dep_date = (d.get("departure_date") or "")[:10]
        docs_missing = pexp_cnt = 0
        for t in travelers:
            tdocs = await db.documents.find({"traveler_id": str(t["_id"]), "is_deleted": {"$ne": True}}).to_list(50)
            have = {x.get("doc_type") for x in tdocs}
            if any(r not in have for r in required):
                docs_missing += 1
            pe = (t.get("passport_expiry") or "")[:10]
            if pe and dep_date and pe < dep_date:
                pexp_cnt += 1
        try:
            days_to = (date.fromisoformat(dep_date) - today).days
        except Exception:
            days_to = None
        types = []
        if total_seat and 0 < available <= max(1, round(total_seat * 0.1)):
            types.append("SEAT_ALMOST_FULL")
        if unpaid + partial > 0:
            types.append("PAYMENT_DUE")
        if pexp_cnt > 0:
            types.append("PASSPORT_EXPIRED")
        if docs_missing > 0:
            types.append("DOCS_INCOMPLETE")
        if days_to is not None and 0 <= days_to <= 7:
            types.append("DEPARTURE_APPROACHING")
        if types:
            out.append({"id": did, "package_name": (pkg or {}).get("package_name", ""), "departure_date": dep_date,
                        "days_to": days_to, "available": available, "total_seat": total_seat,
                        "unpaid": unpaid + partial, "docs_missing": docs_missing, "passport_expired": pexp_cnt, "alerts": types})
    return out


@api_router.get("/operations/departures/{did}/manifest.xlsx")
async def departure_manifest_xlsx(did: str, request: Request, auth: str = Query(None)):
    auth_h = request.headers.get("authorization") or ""
    token = auth_h[7:] if auth_h.startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user or user.get("role") not in ("super_admin", "accounting"):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    dep, pkg, passengers = await _op_departure_passengers(did)
    if not dep:
        raise HTTPException(status_code=404, detail="Departure not found")
    import io
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Manifest"
    ws.append([f"Manifest — {(pkg or {}).get('package_name', '')}"])
    ws.append([f"{(dep.get('departure_date') or '')[:10]} s/d {(dep.get('return_date') or '')[:10]} | Flight {dep.get('flight') or '-'} | Hotel {dep.get('hotel') or '-'}"])
    ws.append([])
    ws.append(["No", "Nama", "L/P", "Paspor", "Paspor Exp", "Room Type", "Room", "Group", "Bus", "Payment", "Docs"])
    for i, p in enumerate(passengers, 1):
        ws.append([i, p["full_name"] or "", p["gender"] or "", p["passport_number"] or "", p["passport_expiry"] or "",
                   p["room_type"] or "", p["room"] or "", p["group"] or "", p["bus"] or "", p["payment_status"], p["document_status"]])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(content=buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename=manifest_{did}.xlsx"})


@api_router.get("/operations/sales-alerts")
async def sales_departure_alerts(user: dict = Depends(require_permission("sales.view"))):
    from datetime import date, timedelta
    today = date.today()
    end = (today + timedelta(days=60)).isoformat()
    q = owner_filter(user)
    q["status"] = {"$ne": "CANCELLED"}
    bookings = await db.bookings.find(q).to_list(1000)
    out = []
    for b in bookings:
        did = b.get("departure_id")
        dep = await db.departures.find_one({"_id": ObjectId(did)}) if did and ObjectId.is_valid(did) else None
        if not dep:
            continue
        dep_date = (dep.get("departure_date") or "")[:10]
        if not (today.isoformat() <= dep_date <= end):
            continue
        pkg = await db.packages.find_one({"_id": ObjectId(dep["package_id"])}) if ObjectId.is_valid(dep.get("package_id") or "") else None
        required = _required_docs((pkg or {}).get("product_type", "TOUR"))
        invs = await db.invoices.find({"booking_id": str(b["_id"])}).to_list(50)
        tot = sum(float(i.get("total") or i.get("amount") or 0) for i in invs)
        pd = sum(float(i.get("paid_amount") or 0) for i in invs)
        outstanding = max(tot - pd, 0)
        pstat = "PAID" if (invs and tot > 0 and pd >= tot) else ("PARTIAL" if pd > 0 else "UNPAID")
        travelers = await db.travelers.find({"booking_id": str(b["_id"])}).to_list(200)
        docs_missing = pexp = 0
        for t in travelers:
            tdocs = await db.documents.find({"traveler_id": str(t["_id"]), "is_deleted": {"$ne": True}}).to_list(50)
            have = {x.get("doc_type") for x in tdocs}
            if any(r not in have for r in required):
                docs_missing += 1
            pe = (t.get("passport_expiry") or "")[:10]
            if pe and dep_date and pe < dep_date:
                pexp += 1
        issues = []
        if outstanding > 0:
            issues.append("PAYMENT_DUE")
        if docs_missing > 0:
            issues.append("DOCS_INCOMPLETE")
        if pexp > 0:
            issues.append("PASSPORT_EXPIRED")
        if issues:
            out.append({"booking_id": str(b["_id"]), "booking_number": b.get("booking_number"), "customer_name": b.get("customer_name"),
                        "package_name": (pkg or {}).get("package_name", ""), "departure_date": dep_date, "payment_status": pstat,
                        "outstanding": outstanding, "docs_missing": docs_missing, "passport_expired": pexp, "issues": issues})
    return out


# ---- Supplier Management (Phase 9J) ----
SUPPLIER_TYPES = ["Airline", "Hotel", "Transport", "Visa Provider", "Tour Operator", "Guide", "Muthawwif", "Insurance", "Other"]
_SUP_ROLE = require_role("super_admin", "accounting")


def _sup_aging_bucket(due_date, outstanding):
    if outstanding <= 0 or not due_date:
        return "current"
    from datetime import date
    try:
        overdue = (date.today() - date.fromisoformat(due_date[:10])).days
    except Exception:
        return "current"
    if overdue <= 0:
        return "current"
    if overdue <= 30:
        return "1-30"
    if overdue <= 60:
        return "31-60"
    return "60+"


@api_router.post("/suppliers")
async def create_supplier(body: dict, request: Request, user: dict = Depends(_SUP_ROLE)):
    if not (body.get("name") or "").strip():
        raise HTTPException(status_code=400, detail="Supplier name is required")
    doc = {"name": body.get("name"), "type": body.get("type") if body.get("type") in SUPPLIER_TYPES else "Other",
           "contact": body.get("contact", ""), "email": body.get("email", ""), "phone": body.get("phone", ""),
           "address": body.get("address", ""), "tax_info": body.get("tax_info", ""), "bank_account": body.get("bank_account", ""),
           "status": body.get("status", "ACTIVE"), "is_deleted": False, "created_at": now_iso(), "created_by": user["name"]}
    res = await db.suppliers.insert_one(doc)
    await log_audit(user, "supplier", "create", request, record_id=str(res.inserted_id), new={"name": doc["name"]})
    return serialize(await db.suppliers.find_one({"_id": res.inserted_id}))


@api_router.get("/suppliers")
async def list_suppliers(type: Optional[str] = None, status: Optional[str] = None,
                         include_archived: bool = False, user: dict = Depends(_SUP_ROLE)):
    q = {} if include_archived else {"is_deleted": {"$ne": True}}
    if type and type != "all":
        q["type"] = type
    if status and status != "all":
        q["status"] = status
    docs = await db.suppliers.find(q).sort("name", 1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.patch("/suppliers/{sid}")
async def update_supplier(sid: str, body: dict, request: Request, user: dict = Depends(_SUP_ROLE)):
    if not ObjectId.is_valid(sid):
        raise HTTPException(status_code=404, detail="Supplier not found")
    fields = {k: body[k] for k in ("name", "type", "contact", "email", "phone", "address", "tax_info", "bank_account", "status") if k in body}
    r = await db.suppliers.update_one({"_id": ObjectId(sid)}, {"$set": fields})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Supplier not found")
    await log_audit(user, "supplier", "update", request, record_id=sid, new=fields)
    return serialize(await db.suppliers.find_one({"_id": ObjectId(sid)}))


# ---- Supplier Bank Accounts (Phase 10E-4) ----
def _validate_bank(body: dict):
    bn = (body.get("bank_name") or "").strip()
    ah = (body.get("account_holder") or "").strip()
    an = (body.get("account_number") or "").strip()
    if not bn:
        raise HTTPException(status_code=400, detail="Nama bank wajib diisi")
    if not ah:
        raise HTTPException(status_code=400, detail="Nama pemilik rekening wajib diisi")
    if not an:
        raise HTTPException(status_code=400, detail="Nomor rekening wajib diisi")
    return bn, ah, an


async def _get_supplier(sid: str):
    if not ObjectId.is_valid(sid):
        raise HTTPException(status_code=404, detail="Supplier not found")
    sup = await db.suppliers.find_one({"_id": ObjectId(sid)})
    if not sup:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return sup


@api_router.post("/suppliers/{sid}/bank-accounts")
async def add_bank_account(sid: str, body: dict, request: Request, user: dict = Depends(_SUP_ROLE)):
    sup = await _get_supplier(sid)
    bn, ah, an = _validate_bank(body)
    accounts = sup.get("bank_accounts") or []
    if any((a.get("account_number") or "").strip() == an for a in accounts):
        raise HTTPException(status_code=409, detail="Nomor rekening sudah ada untuk supplier ini")
    make_primary = bool(body.get("is_primary")) or len(accounts) == 0
    if make_primary:
        for a in accounts:
            a["is_primary"] = False
    acc = {"id": str(ObjectId()), "bank_name": bn, "account_holder": ah, "account_number": an,
           "is_primary": make_primary, "status": (body.get("status") or "ACTIVE").upper(),
           "created_at": now_iso()}
    accounts.append(acc)
    await db.suppliers.update_one({"_id": ObjectId(sid)}, {"$set": {"bank_accounts": accounts}})
    await log_audit(user, "supplier", "add_bank_account", request, record_id=sid, new=acc)
    return serialize(await db.suppliers.find_one({"_id": ObjectId(sid)}))


@api_router.put("/suppliers/{sid}/bank-accounts/{aid}")
async def update_bank_account(sid: str, aid: str, body: dict, request: Request, user: dict = Depends(_SUP_ROLE)):
    sup = await _get_supplier(sid)
    bn, ah, an = _validate_bank(body)
    accounts = sup.get("bank_accounts") or []
    target = next((a for a in accounts if a.get("id") == aid), None)
    if not target:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    if any(a.get("id") != aid and (a.get("account_number") or "").strip() == an for a in accounts):
        raise HTTPException(status_code=409, detail="Nomor rekening sudah ada untuk supplier ini")
    make_primary = bool(body.get("is_primary"))
    for a in accounts:
        if a.get("id") == aid:
            a.update({"bank_name": bn, "account_holder": ah, "account_number": an,
                      "status": (body.get("status") or a.get("status") or "ACTIVE").upper()})
            if make_primary:
                a["is_primary"] = True
        elif make_primary:
            a["is_primary"] = False
    if not any(a.get("is_primary") for a in accounts):
        accounts[0]["is_primary"] = True
    await db.suppliers.update_one({"_id": ObjectId(sid)}, {"$set": {"bank_accounts": accounts}})
    await log_audit(user, "supplier", "update_bank_account", request, record_id=sid, new={"id": aid, "account_number": an})
    return serialize(await db.suppliers.find_one({"_id": ObjectId(sid)}))


@api_router.post("/suppliers/{sid}/bank-accounts/{aid}/set-primary")
async def set_primary_bank_account(sid: str, aid: str, request: Request, user: dict = Depends(_SUP_ROLE)):
    sup = await _get_supplier(sid)
    accounts = sup.get("bank_accounts") or []
    if not any(a.get("id") == aid for a in accounts):
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    for a in accounts:
        a["is_primary"] = (a.get("id") == aid)
    await db.suppliers.update_one({"_id": ObjectId(sid)}, {"$set": {"bank_accounts": accounts}})
    await log_audit(user, "supplier", "set_primary_bank", request, record_id=sid, new={"id": aid})
    return serialize(await db.suppliers.find_one({"_id": ObjectId(sid)}))


@api_router.delete("/suppliers/{sid}/bank-accounts/{aid}")
async def delete_bank_account(sid: str, aid: str, request: Request, user: dict = Depends(_SUP_ROLE)):
    sup = await _get_supplier(sid)
    accounts = sup.get("bank_accounts") or []
    target = next((a for a in accounts if a.get("id") == aid), None)
    if not target:
        raise HTTPException(status_code=404, detail="Rekening tidak ditemukan")
    was_primary = target.get("is_primary")
    accounts = [a for a in accounts if a.get("id") != aid]
    if was_primary and accounts and not any(a.get("is_primary") for a in accounts):
        accounts[0]["is_primary"] = True
    await db.suppliers.update_one({"_id": ObjectId(sid)}, {"$set": {"bank_accounts": accounts}})
    await log_audit(user, "supplier", "delete_bank_account", request, record_id=sid, old={"id": aid})
    return serialize(await db.suppliers.find_one({"_id": ObjectId(sid)}))


@api_router.delete("/suppliers/{sid}")
async def delete_supplier(sid: str, request: Request, reason: str = Query(""), user: dict = Depends(require_role("super_admin"))):
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="Reason is required to archive a supplier")
    if not ObjectId.is_valid(sid):
        raise HTTPException(status_code=404, detail="Supplier not found")
    r = await db.suppliers.update_one({"_id": ObjectId(sid)}, {"$set": {"is_deleted": True, "status": "ARCHIVED"}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Supplier not found")
    await log_audit(user, "supplier", "archive", request, record_id=sid, reason=reason.strip())
    return {"success": True}


@api_router.post("/supplier-costs")
async def create_supplier_cost(body: dict, request: Request, user: dict = Depends(_SUP_ROLE)):
    qty = float(body.get("quantity") or 0)
    unit = float(body.get("unit_cost") or 0)
    if qty <= 0 or unit < 0:
        raise HTTPException(status_code=400, detail="Quantity/Unit Cost tidak valid")
    sup = await db.suppliers.find_one({"_id": ObjectId(body["supplier_id"])}) if ObjectId.is_valid(body.get("supplier_id") or "") else None
    doc = {"supplier_id": body.get("supplier_id"), "supplier_name": (sup or {}).get("name", ""),
           "package_id": body.get("package_id"), "departure_id": body.get("departure_id"),
           "service": body.get("service", ""), "quantity": qty, "unit_cost": unit, "total_cost": round(qty * unit, 2),
           "invoice_number": body.get("invoice_number", ""), "payment_status": body.get("payment_status", "UNPAID"),
           "created_at": now_iso(), "created_by": user["name"]}
    res = await db.supplier_costs.insert_one(doc)
    await log_audit(user, "supplier", "cost_create", request, record_id=str(res.inserted_id), new={"total": doc["total_cost"]})
    return serialize(await db.supplier_costs.find_one({"_id": res.inserted_id}))


@api_router.get("/supplier-costs")
async def list_supplier_costs(package_id: Optional[str] = None, departure_id: Optional[str] = None, user: dict = Depends(_SUP_ROLE)):
    q = {}
    if package_id:
        q["package_id"] = package_id
    if departure_id:
        q["departure_id"] = departure_id
    docs = await db.supplier_costs.find(q).sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api_router.get("/supplier-costs/summary")
async def supplier_cost_summary(package_id: Optional[str] = None, departure_id: Optional[str] = None, user: dict = Depends(_SUP_ROLE)):
    q = {}
    if package_id:
        q["package_id"] = package_id
    if departure_id:
        q["departure_id"] = departure_id
    docs = await db.supplier_costs.find(q).to_list(2000)
    total = sum(float(d.get("total_cost") or 0) for d in docs)
    by_type = {}
    for d in docs:
        by_type[d.get("service") or "Other"] = by_type.get(d.get("service") or "Other", 0) + float(d.get("total_cost") or 0)
    return {"total_supplier_cost": round(total, 2), "count": len(docs), "by_service": by_type}


@api_router.delete("/supplier-costs/{cid}")
async def delete_supplier_cost(cid: str, request: Request, user: dict = Depends(_SUP_ROLE)):
    if not ObjectId.is_valid(cid):
        raise HTTPException(status_code=404, detail="Not found")
    await db.supplier_costs.delete_one({"_id": ObjectId(cid)})
    await log_audit(user, "supplier", "cost_delete", request, record_id=cid)
    return {"success": True}


@api_router.post("/supplier-payments")
async def create_supplier_payment(body: dict, request: Request, user: dict = Depends(_SUP_ROLE)):
    amt = float(body.get("amount") or 0)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Amount harus lebih dari 0")
    sup = await db.suppliers.find_one({"_id": ObjectId(body["supplier_id"])}) if ObjectId.is_valid(body.get("supplier_id") or "") else None
    doc = {"supplier_id": body.get("supplier_id"), "supplier_name": (sup or {}).get("name", ""),
           "invoice_number": body.get("invoice_number", ""), "due_date": body.get("due_date", ""),
           "amount": amt, "paid": float(body.get("paid") or 0), "cost_id": body.get("cost_id"),
           "created_at": now_iso(), "created_by": user["name"]}
    res = await db.supplier_payments.insert_one(doc)
    await log_audit(user, "supplier", "payment_create", request, record_id=str(res.inserted_id), new={"amount": amt})
    return serialize(await db.supplier_payments.find_one({"_id": res.inserted_id}))


@api_router.get("/supplier-payments")
async def list_supplier_payments(supplier_id: Optional[str] = None, user: dict = Depends(_SUP_ROLE)):
    q = {}
    if supplier_id:
        q["supplier_id"] = supplier_id
    docs = await db.supplier_payments.find(q).sort("due_date", 1).to_list(1000)
    out = []
    for d in docs:
        s = serialize(d)
        outstanding = round(float(d.get("amount") or 0) - float(d.get("paid") or 0), 2)
        s["outstanding"] = outstanding
        s["status"] = "PAID" if outstanding <= 0 else ("PARTIAL" if float(d.get("paid") or 0) > 0 else "UNPAID")
        s["aging"] = _sup_aging_bucket(d.get("due_date"), outstanding)
        out.append(s)
    return out


@api_router.patch("/supplier-payments/{pid}")
async def update_supplier_payment(pid: str, body: dict, request: Request, user: dict = Depends(_SUP_ROLE)):
    if not ObjectId.is_valid(pid):
        raise HTTPException(status_code=404, detail="Not found")
    fields = {k: body[k] for k in ("invoice_number", "due_date", "amount", "paid") if k in body}
    if "amount" in fields:
        fields["amount"] = float(fields["amount"] or 0)
    if "paid" in fields:
        fields["paid"] = float(fields["paid"] or 0)
    r = await db.supplier_payments.update_one({"_id": ObjectId(pid)}, {"$set": fields})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Not found")
    await log_audit(user, "supplier", "payment_update", request, record_id=pid, new=fields)
    return serialize(await db.supplier_payments.find_one({"_id": ObjectId(pid)}))


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
# DOCUMENT TEMPLATE (Invoice / Quotation / Kwitansi) — Super Admin configurable
# ============================================================================
DOC_TEMPLATE_DEFAULTS = {
    "primary_color": "#1d4ed8", "accent_color": "#f59e0b", "font": "Helvetica",
    "logo_url": "", "company_name": "", "address": "", "phone": "", "email": "", "website": "",
    "footer_text": "Terima kasih atas kepercayaan Anda.",
    "invoice_title": "INVOICE", "quotation_title": "QUOTATION", "receipt_title": "KWITANSI PEMBAYARAN",
    "show_qr": True, "paid_stamp_text": "PAID", "public_base_url": "", "quotation_watermark_text": "DRAFT",
    "invoice_terms": "", "quotation_terms": "",
    "signer_name": "", "signer_title": "", "signature_url": "", "stamp_url": "",
    "signer_place": "", "stamp_scale": 1.0, "stamp_offset_x": 0, "stamp_offset_y": 0,
}
_FRONTEND_BASE_CACHE = None


def _read_frontend_base():
    global _FRONTEND_BASE_CACHE
    if _FRONTEND_BASE_CACHE is not None:
        return _FRONTEND_BASE_CACHE
    val = ""
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.strip().startswith("REACT_APP_BACKEND_URL="):
                    val = line.split("=", 1)[1].strip()
                    break
    except Exception:
        val = ""
    _FRONTEND_BASE_CACHE = val
    return val


async def _get_doc_template():
    doc = await db.company_settings.find_one({"key": "doc_template"}) or {}
    tpl = {**DOC_TEMPLATE_DEFAULTS}
    for k in DOC_TEMPLATE_DEFAULTS:
        if doc.get(k) not in (None, ""):
            tpl[k] = doc.get(k)
    company = await db.company_settings.find_one({"key": "company"}) or {}
    # fallback company identity fields
    tpl["company_name"] = tpl["company_name"] or company.get("company_name") or "Safar Travel"
    tpl["address"] = tpl["address"] or company.get("address", "")
    tpl["phone"] = tpl["phone"] or company.get("phone", "")
    tpl["email"] = tpl["email"] or company.get("email", "")
    tpl["logo_url"] = tpl["logo_url"] or company.get("logo", "")
    return tpl


def _public_base(tpl):
    return (tpl.get("public_base_url") or os.environ.get("PUBLIC_BASE_URL") or _read_frontend_base() or "").rstrip("/")


def _doc_sig(kind, doc_id):
    msg = f"{kind}:{doc_id}".encode()
    return _hmac.new(os.environ["JWT_SECRET"].encode(), msg, _hashlib.sha256).hexdigest()[:32]


def _public_pdf_url(tpl, kind, doc_id):
    return f"{_public_base(tpl)}/api/public/documents/{kind}/{doc_id}?sig={_doc_sig(kind, doc_id)}"


class DocTemplateUpdate(BaseModel):
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    font: Optional[str] = None
    logo_url: Optional[str] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    footer_text: Optional[str] = None
    invoice_title: Optional[str] = None
    quotation_title: Optional[str] = None
    receipt_title: Optional[str] = None
    show_qr: Optional[bool] = None
    paid_stamp_text: Optional[str] = None
    quotation_watermark_text: Optional[str] = None
    invoice_terms: Optional[str] = None
    quotation_terms: Optional[str] = None
    signer_name: Optional[str] = None
    signer_title: Optional[str] = None
    signature_url: Optional[str] = None
    stamp_url: Optional[str] = None
    signer_place: Optional[str] = None
    stamp_scale: Optional[float] = None
    stamp_offset_x: Optional[int] = None
    stamp_offset_y: Optional[int] = None
    public_base_url: Optional[str] = None


@api_router.get("/doc-template")
async def get_doc_template(user: dict = Depends(require_permission("settings.view"))):
    return await _get_doc_template()


@api_router.put("/doc-template")
async def update_doc_template(body: DocTemplateUpdate, request: Request, user: dict = Depends(require_permission("settings.manage"))):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    updates["key"] = "doc_template"
    await db.company_settings.update_one({"key": "doc_template"}, {"$set": updates}, upsert=True)
    await log_audit(user, "settings", "doc_template", request, new={k: v for k, v in updates.items() if k != "logo_url"})
    return await _get_doc_template()


@api_router.post("/doc-template/preview")
async def doc_template_preview(body: dict, user: dict = Depends(require_permission("settings.view"))):
    body = body or {}
    kind = (body.pop("kind", None) or "invoice").lower()
    tpl = {**DOC_TEMPLATE_DEFAULTS, **{k: v for k, v in body.items() if v is not None}}
    company = await db.company_settings.find_one({"key": "company"}) or {}
    if kind == "receipt":
        sample_r = {"_id": "contoh", "receipt_number": "KW-CONTOH", "created_at": now_iso(),
                    "booking_number": "BKG-CONTOH", "customer_name": "Budi Santoso", "payment_number": 2,
                    "label": "Pelunasan", "amount": 25000000, "outstanding_after": 0, "outstanding_total": 0}
        pdf, _ = await _render_receipt_pdf(sample_r, tpl=tpl)
    else:
        k = "QUOTATION" if kind == "quotation" else "INVOICE"
        sample = {"number": ("QT-CONTOH" if k == "QUOTATION" else "INV-CONTOH"), "created_at": now_iso(),
                  "customer_name": "Budi Santoso", "sales_pic_name": "Rina Sales",
                  "package_name": "Umrah Reguler 9 Hari", "package_version": 1, "room_type": "QUAD", "pax": 2,
                  "per_pax_price": 25000000, "gross": 50000000, "subtotal": 50000000, "discount_percent": 0,
                  "discount_amount": 0, "tax_percent": 0, "tax_amount": 0, "total": 50000000,
                  "due_date": "2026-09-01", "status": "PAID", "addons": [],
                  "terms": "Pembayaran DP minimal 50%. Sisa dilunasi H-30 keberangkatan."}
        sample["terms"] = tpl.get("invoice_terms" if k == "INVOICE" else "quotation_terms") or sample["terms"]
        qr = _public_pdf_url(tpl, kind, "contoh")
        wm = tpl.get("quotation_watermark_text", "DRAFT") if k == "QUOTATION" else None
        pdf = build_document_pdf(k, sample, company, tpl=tpl, qr_url=qr, paid=(kind == "invoice"), watermark=wm, signer=_default_signer(tpl))
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": "inline; filename=preview.pdf"})


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
    # N8N integration removed — feature disabled (tidak ada pengiriman keluar).
    return {"ok": False, "skipped": True, "reason": "n8n removed"}


def trigger_n8n(event, data):
    # N8N integration removed — no-op.
    return None


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


def _clean_terms(html):
    if not html:
        return ""
    import re
    s = str(html).replace("<strong>", "<b>").replace("</strong>", "</b>").replace("<em>", "<i>").replace("</em>", "</i>")

    def _ol(m):
        items = re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S | re.I)
        return "".join(f"{i + 1}. {it}<br/>" for i, it in enumerate(items))

    def _ul(m):
        items = re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.S | re.I)
        return "".join(f"&bull; {it}<br/>" for it in items)

    s = re.sub(r"<ol[^>]*>(.*?)</ol>", _ol, s, flags=re.S | re.I)
    s = re.sub(r"<ul[^>]*>(.*?)</ul>", _ul, s, flags=re.S | re.I)
    s = re.sub(r"</(div|p)>", "<br/>", s, flags=re.I)
    s = re.sub(r"<(div|p)[^>]*>", "", s, flags=re.I)
    s = re.sub(r"<br[^>]*>", "<br/>", s, flags=re.I)
    s = re.sub(r"<(/?)(b|i|u)(\s[^>]*)?>", r"<\1\2>", s, flags=re.I)
    s = re.sub(r"<(?!/?(?:b|i|u)>|br/>)[^>]*>", "", s)
    s = re.sub(r"(<br/>\s*)+$", "", s)
    # Escape stray ampersands not part of a valid entity (ReportLab is strict).
    s = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", s)
    # Balance inline tags (b/i/u) so ReportLab's mini-parser never fails on
    # malformed rich-text (e.g. a stray </b> without a matching <b>).
    stack, out = [], []
    for m in re.finditer(r"(<br/>)|<(/?)(b|i|u)>|([^<]+)", s):
        br, closing, tag, text = m.group(1), m.group(2), m.group(3), m.group(4)
        if br:
            out.append("<br/>")
        elif tag and not closing:
            stack.append(tag)
            out.append(f"<{tag}>")
        elif tag and closing:
            if tag in stack:
                reopen = []
                while stack:
                    t = stack.pop()
                    out.append(f"</{t}>")
                    if t == tag:
                        break
                    reopen.append(t)
                for t in reversed(reopen):
                    stack.append(t)
                    out.append(f"<{t}>")
        elif text:
            out.append(text)
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)


def _pdf_fonts(tpl):
    return {"Helvetica": ("Helvetica", "Helvetica-Bold"), "Times-Roman": ("Times-Roman", "Times-Bold"),
            "Courier": ("Courier", "Courier-Bold")}.get(tpl.get("font") or "Helvetica", ("Helvetica", "Helvetica-Bold"))


def _img_from_src(src, max_w_mm, max_h_mm):
    try:
        if not src:
            return None
        if src.startswith("data:"):
            import base64
            raw = base64.b64decode(src.split(",", 1)[1])
        elif src.startswith("http"):
            raw = _requests.get(src, timeout=10).content
        else:
            return None
        im = RLImage(BytesIO(raw))
        ratio = min(max_w_mm * mm / im.imageWidth, max_h_mm * mm / im.imageHeight)
        im.drawWidth = im.imageWidth * ratio
        im.drawHeight = im.imageHeight * ratio
        return im
    except Exception:
        return None


def _qr_image(url, size_mm=22):
    try:
        import qrcode
        img = qrcode.make(url)
        b = BytesIO()
        img.save(b, format="PNG")
        b.seek(0)
        return RLImage(b, width=size_mm * mm, height=size_mm * mm)
    except Exception:
        return None


def _load_pil_image(src):
    try:
        if not src:
            return None
        import base64
        from PIL import Image
        if src.startswith("data:"):
            raw = base64.b64decode(src.split(",", 1)[1])
        elif src.startswith("http"):
            raw = _requests.get(src, timeout=10).content
        else:
            return None
        return Image.open(BytesIO(raw)).convert("RGBA")
    except Exception:
        return None


def _remove_white_bg(img, lo=208, hi=246):
    """Make white/near-white pixels transparent so a stamp behind a signature blends naturally.
    Soft ramp between lo..hi for anti-aliased edges. Preserves existing transparency."""
    try:
        from PIL import ImageChops
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        gray = img.convert("L")
        span = max(hi - lo, 1)
        lut = [255 if p <= lo else (0 if p >= hi else int((hi - p) * 255 / span)) for p in range(256)]
        mask = gray.point(lut)
        new_a = ImageChops.multiply(img.split()[3], mask)
        img.putalpha(new_a)
        return img
    except Exception:
        return img


def _compose_sign_stamp(signature_src, stamp_src, w_px=520, h_px=300, stamp_scale=1.0, stamp_dx=0, stamp_dy=0):
    """Composite signature (front) + company stamp (behind, semi-transparent) into one PNG.
    stamp_scale/stamp_dx/stamp_dy let Settings tune the stamp size & position."""
    try:
        from PIL import Image
        sign = _load_pil_image(signature_src)
        stamp = _load_pil_image(stamp_src)
        if not sign and not stamp:
            return None
        if sign:
            sign = _remove_white_bg(sign)
        if stamp:
            stamp = _remove_white_bg(stamp)
        try:
            sc = max(0.3, min(float(stamp_scale or 1.0), 2.2))
        except Exception:
            sc = 1.0
        dx, dy = int(stamp_dx or 0), int(stamp_dy or 0)
        canvas = Image.new("RGBA", (w_px, h_px), (255, 255, 255, 0))
        if stamp:
            s = stamp.copy()
            ratio = min(w_px / s.width, h_px / s.height) * sc
            s = s.resize((max(1, int(s.width * ratio)), max(1, int(s.height * ratio))))
            alpha = s.split()[3].point(lambda p: int(p * 0.8))
            s.putalpha(alpha)
            canvas.paste(s, ((w_px - s.width) // 2 + dx, (h_px - s.height) // 2 + dy), s)
        if sign:
            g = sign.copy()
            ratio = min(w_px / g.width, (h_px * 0.7) / g.height)
            g = g.resize((max(1, int(g.width * ratio)), max(1, int(g.height * ratio))))
            canvas.paste(g, ((w_px - g.width) // 2, (h_px - g.height) // 2), g)
        out = BytesIO()
        canvas.save(out, format="PNG")
        out.seek(0)
        return out
    except Exception:
        return None
    except Exception:
        return None


_ID_MONTHS = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
              "Agustus", "September", "Oktober", "November", "Desember"]


def _id_dateline(tpl, iso_date):
    place = (tpl.get("signer_place") or "").strip()
    s = str(iso_date or "")[:10]
    try:
        y, m, d = s.split("-")
        txt = f"{int(d)} {_ID_MONTHS[int(m)]} {int(y)}"
    except Exception:
        n = datetime.now(timezone.utc)
        txt = f"{n.day} {_ID_MONTHS[n.month]} {n.year}"
    return f"{place}, {txt}" if place else txt


def _signature_block(signer, tpl, base_font, bold_font, place_date=""):
    """Build a right-aligned signature flowable: [place, date] + 'Hormat kami,' + signature/stamp + name + title."""
    if not signer:
        return None
    name = (signer.get("name") or "").strip()
    title = (signer.get("title") or "").strip()
    stamp_src = signer.get("stamp_url") or tpl.get("stamp_url")
    if not name and not title and not signer.get("signature_url") and not stamp_src:
        return None
    styles = getSampleStyleSheet()
    cen = ParagraphStyle("sigc", parent=styles["Normal"], fontName=base_font, fontSize=9,
                         alignment=1, textColor=colors.HexColor("#334155"))
    cenb = ParagraphStyle("sigcb", parent=cen, fontName=bold_font, fontSize=9.5,
                          textColor=colors.HexColor("#0f172a"))
    parts = []
    if place_date:
        parts.append(Paragraph(place_date, cen))
    parts.append(Paragraph("Hormat kami,", cen))
    img_buf = _compose_sign_stamp(signer.get("signature_url"), stamp_src,
                                  stamp_scale=tpl.get("stamp_scale", 1.0),
                                  stamp_dx=tpl.get("stamp_offset_x", 0),
                                  stamp_dy=tpl.get("stamp_offset_y", 0))
    if img_buf:
        im = RLImage(img_buf)
        ratio = min(46 * mm / im.imageWidth, 23 * mm / im.imageHeight)
        im.drawWidth = im.imageWidth * ratio
        im.drawHeight = im.imageHeight * ratio
        im.hAlign = "CENTER"
        parts += [Spacer(1, 2 * mm), im, Spacer(1, 1 * mm)]
    else:
        parts.append(Spacer(1, 20 * mm))
    parts.append(Paragraph(f"<u>{name or '&nbsp;'}</u>", cenb))
    if title:
        parts.append(Paragraph(title, cen))
    inner = Table([[p] for p in parts], colWidths=[56 * mm])
    inner.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    wrap = Table([["", inner]], colWidths=[114 * mm, 56 * mm])
    wrap.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return wrap


def build_document_pdf(kind: str, data: dict, company: dict, itineraries=None, tpl=None, qr_url=None, paid=False, watermark=None, signer=None) -> bytes:
    tpl = tpl or DOC_TEMPLATE_DEFAULTS
    primary = colors.HexColor(tpl.get("primary_color") or "#1d4ed8")
    accent = colors.HexColor(tpl.get("accent_color") or "#f59e0b")
    base_font, bold_font = _pdf_fonts(tpl)
    title = {"INVOICE": tpl.get("invoice_title", "INVOICE"), "QUOTATION": tpl.get("quotation_title", "QUOTATION")}.get(kind, kind)
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=20 * mm, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading1"], textColor=primary, fontSize=18, fontName=bold_font)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#475569"), fontName=base_font)
    boldn = ParagraphStyle("b", parent=styles["Normal"], fontName=bold_font)
    el = []
    logo = _img_from_src(tpl.get("logo_url") or company.get("logo", ""), 34, 18)
    header_left = []
    if logo:
        header_left.append(logo)
    header_left.append(Paragraph(f"<b>{tpl.get('company_name') or company.get('company_name', 'Safar Travel')}</b>", boldn))
    header_left.append(Paragraph(tpl.get("address") or company.get("address", ""), small))
    header_left.append(Paragraph(f"{tpl.get('phone') or company.get('phone', '')} · {tpl.get('email') or company.get('email', '')}", small))
    right = [Paragraph(f"<b>{title}</b>", h), Paragraph(f"No: {data.get('number', '')}", small),
             Paragraph(f"Tanggal: {(data.get('created_at') or '')[:10]}", small)]
    if tpl.get("show_qr", True) and qr_url:
        qr = _qr_image(qr_url, 22)
        if qr:
            right += [Spacer(1, 2 * mm), qr, Paragraph("Scan untuk PDF", ParagraphStyle("qs", parent=small, fontSize=7))]
    el.append(Table([[header_left, right]], colWidths=[100 * mm, 70 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))
    el.append(Spacer(1, 8 * mm))
    _cust_html = f"<b>Customer</b><br/>{data.get('customer_name', '')}"
    if data.get("cust_phone"):
        _cust_html += f"<br/>{data.get('cust_phone')}"
    if data.get("cust_email"):
        _cust_html += f"<br/>{data.get('cust_email')}"
    if data.get("cust_address"):
        _cust_html += f"<br/>{data.get('cust_address')}"
    el.append(Table([[Paragraph(_cust_html, small),
                      Paragraph(f"<b>Sales PIC</b><br/>{data.get('sales_pic_name', '')}", small),
                      Paragraph(f"<b>Package</b><br/>{data.get('package_name', '')} (v{data.get('package_version', 1)})", small)]],
                     colWidths=[56 * mm, 56 * mm, 58 * mm]))
    if data.get("valid_until_label"):
        el.append(Spacer(1, 2 * mm))
        el.append(Paragraph(f"<b>Masa Berlaku s/d:</b> {data.get('valid_until_label')}", small))
    el.append(Spacer(1, 6 * mm))
    rows = [["Deskripsi", "Qty", "Harga", "Jumlah"]]
    rows.append([f"{data.get('package_name', '')} — {data.get('room_type', '') or 'Standard'}", str(data.get("pax", 1)), _money(data.get("per_pax_price")), _money(data.get("gross"))])
    for a in (data.get("addons") or []):
        rows.append([f"Add-on: {a.get('name', '')}", "1", _money(a.get("amount")), _money(a.get("amount"))])
    t = Table(rows, colWidths=[92 * mm, 18 * mm, 30 * mm, 30 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), primary), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTNAME", (0, 0), (-1, 0), bold_font), ("FONTNAME", (0, 1), (-1, -1), base_font),
                           ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                           ("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    el.append(t)
    el.append(Spacer(1, 4 * mm))
    summ = [["Subtotal", _money(data.get("subtotal"))],
            [f"Discount ({data.get('discount_percent', 0)}%)", "- " + _money(data.get("discount_amount"))],
            [f"Pajak ({data.get('tax_percent', 0)}%)", _money(data.get("tax_amount"))],
            ["TOTAL", _money(data.get("total"))]]
    ts = Table(summ, colWidths=[140 * mm, 30 * mm])
    ts.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 10), ("FONTNAME", (0, 0), (-1, -1), base_font),
                            ("LINEABOVE", (0, -1), (-1, -1), 0.6, primary), ("FONTNAME", (0, -1), (-1, -1), bold_font)]))
    el.append(ts)
    if kind == "QUOTATION" and data.get("hotel_items"):
        el.append(Spacer(1, 6 * mm))
        el.append(Paragraph("<b>HOTEL</b>", boldn))
        hrows = [["Hotel / Kamar", "Check-in", "Check-out", "Mlm", "Kmr", "Rate", "Total"]]
        for hi in data.get("hotel_items"):
            nm = hi.get("hotelName", "")
            if hi.get("roomtypeName"):
                nm += f"<br/><font size=7 color='#64748b'>{hi.get('roomtypeName')}</font>"
            hrows.append([Paragraph(nm, small), hi.get("checkInDate", ""), hi.get("checkOutDate", ""),
                          str(hi.get("nights", 0)), str(hi.get("numberOfRooms", 1)),
                          _money(hi.get("agoda_daily_rate")), _money(hi.get("total"))])
        htbl = Table(hrows, colWidths=[52 * mm, 22 * mm, 22 * mm, 12 * mm, 12 * mm, 24 * mm, 24 * mm])
        htbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), primary), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                  ("FONTNAME", (0, 0), (-1, 0), bold_font), ("FONTNAME", (0, 1), (-1, -1), base_font),
                                  ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                                  ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        el.append(htbl)
        el.append(Spacer(1, 2 * mm))
        _gt = data.get("grand_total_with_hotel")
        if _gt is None:
            _gt = float(data.get("total") or 0) + float(data.get("hotel_total") or 0)
        gtbl = Table([["Total Hotel", _money(data.get("hotel_total"))],
                      ["TOTAL ESTIMASI (termasuk hotel)", _money(_gt)]], colWidths=[140 * mm, 30 * mm])
        gtbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 10),
                                  ("FONTNAME", (0, 0), (-1, -1), base_font), ("FONTNAME", (0, -1), (-1, -1), bold_font),
                                  ("LINEABOVE", (0, -1), (-1, -1), 0.6, primary)]))
        el.append(gtbl)
    if kind == "INVOICE" and data.get("outstanding") is not None and float(data.get("outstanding") or 0) > 0:
        extra = [["Sudah Dibayar", _money(data.get("paid_amount"))],
                 ["Kekurangan Pembayaran", _money(data.get("outstanding"))]]
        et = Table(extra, colWidths=[140 * mm, 30 * mm])
        et.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 10),
                                ("FONTNAME", (0, 0), (-1, -1), base_font), ("FONTNAME", (0, 1), (-1, 1), bold_font),
                                ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#dc2626"))]))
        el.append(et)
    if itineraries:
        el.append(Spacer(1, 6 * mm))
        el.append(Paragraph("<b>Itinerary</b>", boldn))
        for i, it in enumerate(itineraries):
            el.append(Paragraph(f"Day {it.get('day', i + 1)}: {it.get('location', '')} — {it.get('activity', '')}", small))
    if data.get("terms"):
        el.append(Spacer(1, 6 * mm))
        el.append(Paragraph("<b>Terms &amp; Conditions</b>", boldn))
        el.append(Paragraph(_clean_terms(str(data.get("terms"))), small))
    if kind == "INVOICE" and data.get("due_date"):
        el.append(Spacer(1, 4 * mm))
        el.append(Paragraph(f"<b>Jatuh Tempo:</b> {data.get('due_date')} · <b>Status:</b> {data.get('status', '')}", small))
    if tpl.get("footer_text"):
        el.append(Spacer(1, 8 * mm))
        el.append(Paragraph(_clean_terms(tpl.get("footer_text")), ParagraphStyle("f", parent=small, textColor=accent)))

    sig = _signature_block(signer, tpl, base_font, bold_font, place_date=_id_dateline(tpl, data.get("created_at")))
    if sig:
        el.append(Spacer(1, 10 * mm))
        el.append(sig)

    def _stamp(canvas, _d):
        if paid:
            text, col, size = tpl.get("paid_stamp_text", "PAID"), colors.Color(0.13, 0.7, 0.4, alpha=0.22), 84
        elif watermark:
            text, col, size = str(watermark), colors.Color(0.5, 0.5, 0.5, alpha=0.16), 90
        else:
            return
        w, hh = _d.pagesize
        canvas.saveState()
        canvas.translate(w / 2.0, hh / 2.0)
        canvas.rotate(35)
        canvas.setFont(bold_font, size)
        canvas.setFillColor(col)
        canvas.drawCentredString(0, -size * 0.35, text)
        canvas.restoreState()

    doc.build(el, onFirstPage=_stamp, onLaterPages=_stamp)
    return buf.getvalue()


def _default_signer(tpl):
    return {"name": tpl.get("signer_name") or "", "title": tpl.get("signer_title") or "",
            "signature_url": tpl.get("signature_url") or ""}


async def _resolve_signer(kind, doc, tpl):
    """Invoice/receipt -> default signer from settings. Quotation -> the sales who made it,
    unless it was created by AI/Auto Sales (then default)."""
    default = _default_signer(tpl)
    if kind != "quotation":
        return default
    sid = doc.get("sales_pic_id")
    nm = str(doc.get("sales_pic_name") or "").upper()
    cb = str(doc.get("created_by") or "").upper()
    auto = (not sid) or (nm in ("AUTO SALES", "AI AGENT")) or (cb in ("AI AGENT", "AUTO SALES"))
    if auto:
        return default
    u = None
    try:
        if ObjectId.is_valid(str(sid)):
            u = await db.users.find_one({"_id": ObjectId(sid)})
    except Exception:
        u = None
    if not u:
        return default
    return {"name": u.get("name") or default["name"], "title": u.get("title") or "",
            "signature_url": u.get("signature") or ""}


async def _freeze_signer(kind, doc, tpl, collection):
    """Return the signer snapshot frozen at issue time. If the document has no snapshot yet,
    resolve the current signer + stamp, persist it on the document, then return it. Later changes
    to a user's signature or the default signer never affect already-issued documents."""
    snap = doc.get("signature_snapshot")
    if isinstance(snap, dict) and (snap.get("name") or snap.get("title") or snap.get("signature_url") or snap.get("stamp_url")):
        return snap
    base = await _resolve_signer(kind, doc, tpl)
    snap = {"name": base.get("name", ""), "title": base.get("title", ""),
            "signature_url": base.get("signature_url", ""), "stamp_url": tpl.get("stamp_url", "")}
    _id = doc.get("_id")
    try:
        oid = _id if isinstance(_id, ObjectId) else (ObjectId(str(_id)) if ObjectId.is_valid(str(_id)) else None)
        if oid is not None:
            await db[collection].update_one({"_id": oid}, {"$set": {"signature_snapshot": snap}})
    except Exception:
        pass
    return snap


async def _customer_contact(customer_id=None, booking_id=None, whatsapp="", email=""):
    phone, mail, addr = (whatsapp or ""), (email or ""), ""
    cust = None
    if customer_id and ObjectId.is_valid(str(customer_id)):
        cust = await db.customers.find_one({"_id": ObjectId(str(customer_id))})
    if not cust and booking_id and ObjectId.is_valid(str(booking_id)):
        bk = await db.bookings.find_one({"_id": ObjectId(str(booking_id))})
        if bk and bk.get("customer_id") and ObjectId.is_valid(str(bk["customer_id"])):
            cust = await db.customers.find_one({"_id": ObjectId(str(bk["customer_id"]))})
    if cust:
        phone = phone or cust.get("whatsapp") or cust.get("phone") or ""
        mail = mail or cust.get("email") or ""
        parts = [cust.get("address"), cust.get("city"), cust.get("province"), cust.get("postal_code"), cust.get("country")]
        addr = ", ".join([str(p).strip() for p in parts if p and str(p).strip()])
    return {"phone": phone, "email": mail, "address": addr}


def _valid_until_label(created_at, days):
    s = str(created_at or "")[:10]
    try:
        from datetime import datetime as _dt, timedelta
        d = _dt.strptime(s, "%Y-%m-%d") + timedelta(days=days)
        return f"{d.day} {_ID_MONTHS[d.month]} {d.year}"
    except Exception:
        return ""


async def _render_invoice_pdf(inv):
    tpl = await _get_doc_template()
    company = await db.company_settings.find_one({"key": "company"}) or {}
    iid = str(inv.get("_id"))
    paid = (float(inv.get("outstanding") or 0) <= 0) or (str(inv.get("status", "")).upper() in ("PAID", "LUNAS"))
    data = {**inv, "number": inv.get("invoice_number"), "subtotal": inv.get("amount"),
            "per_pax_price": round(float(inv.get("amount") or 0) / max(int(inv.get("pax") or 1), 1)), "gross": inv.get("amount"), "addons": []}
    _tot = float(inv.get("total") or inv.get("amount") or 0)
    _out = float(inv.get("outstanding") or 0)
    data["outstanding"] = _out
    data["paid_amount"] = max(_tot - _out, 0)
    data["terms"] = tpl.get("invoice_terms") or inv.get("terms") or ""
    _ct = await _customer_contact(inv.get("customer_id"), inv.get("booking_id"), inv.get("whatsapp"), inv.get("email"))
    data["cust_phone"], data["cust_email"], data["cust_address"] = _ct["phone"], _ct["email"], _ct["address"]
    data["valid_until_label"] = _valid_until_label(inv.get("created_at"), 3)
    qr = _public_pdf_url(tpl, "invoice", iid)
    signer = await _freeze_signer("invoice", inv, tpl, "invoices")
    return build_document_pdf("INVOICE", data, company, tpl=tpl, qr_url=qr, paid=paid, signer=signer), inv.get("invoice_number")


async def _render_quotation_pdf(q):
    tpl = await _get_doc_template()
    company = await db.company_settings.find_one({"key": "company"}) or {}
    itins = await db.package_itineraries.find({"package_id": q.get("package_id")}).sort("day", 1).to_list(200)
    data = {**q, "number": q.get("quotation_number")}
    data["terms"] = tpl.get("quotation_terms") or q.get("terms") or ""
    _ct = await _customer_contact(q.get("customer_id"), q.get("booking_id"), q.get("whatsapp"), q.get("email"))
    data["cust_phone"], data["cust_email"], data["cust_address"] = _ct["phone"], _ct["email"], _ct["address"]
    data["valid_until_label"] = _valid_until_label(q.get("created_at"), 7)
    qr = _public_pdf_url(tpl, "quotation", str(q.get("_id")))
    wm = tpl.get("quotation_watermark_text", "DRAFT") if str(q.get("status", "")).upper() != "ACCEPTED" else None
    signer = await _freeze_signer("quotation", q, tpl, "quotations")
    return build_document_pdf("QUOTATION", data, company, itins, tpl=tpl, qr_url=qr, watermark=wm, signer=signer), q.get("quotation_number")


async def _render_receipt_pdf(r, tpl=None):
    if tpl is None:
        tpl = await _get_doc_template()
    primary = colors.HexColor(tpl.get("primary_color") or "#1d4ed8")
    base_font, bold_font = _pdf_fonts(tpl)
    rid = str(r.get("_id"))

    def rp(n):
        return "Rp " + f"{float(n or 0):,.0f}".replace(",", ".")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], textColor=primary, fontName=bold_font)
    logo = _img_from_src(tpl.get("logo_url"), 40, 20)
    rows = [["No. Kwitansi", r.get("receipt_number", "")], ["Tanggal", (r.get("created_at") or "")[:16].replace("T", " ")],
            ["Booking", r.get("booking_number", "")], ["Customer", r.get("customer_name", "")],
            ["Termin", f"#{r.get('payment_number')} {r.get('label', '')}"], ["Jumlah Dibayar", rp(r.get("amount"))],
            ["Sisa Termin", rp(r.get("outstanding_after"))], ["Sisa Total Booking", rp(r.get("outstanding_total"))]]
    _rc_ct = await _customer_contact(r.get("customer_id"), r.get("booking_id"))
    _rc_extra = []
    if _rc_ct["phone"]:
        _rc_extra.append(["No. HP", _rc_ct["phone"]])
    if _rc_ct["email"]:
        _rc_extra.append(["Email", _rc_ct["email"]])
    if _rc_ct["address"]:
        _rc_extra.append(["Alamat", _rc_ct["address"]])
    if _rc_extra:
        _ci = next((k for k, rr in enumerate(rows) if rr and rr[0] == "Customer"), 3) + 1
        rows[_ci:_ci] = _rc_extra
    t = Table(rows, colWidths=[55 * mm, 110 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                           ("FONTNAME", (0, 0), (-1, -1), base_font), ("FONTSIZE", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    el = []
    if logo:
        el.append(logo)
    el += [Paragraph(f"<b>{tpl.get('company_name', 'Travel CRM')}</b>", title),
           Paragraph(tpl.get("receipt_title", "KWITANSI PEMBAYARAN"), styles["Heading2"]), Spacer(1, 8), t]
    if tpl.get("show_qr", True):
        qr = _qr_image(_public_pdf_url(tpl, "receipt", rid), 24)
        if qr:
            el += [Spacer(1, 10), qr, Paragraph("Scan untuk verifikasi kwitansi", ParagraphStyle("qs", parent=styles["Normal"], fontSize=8))]
    el += [Spacer(1, 16), Paragraph(_clean_terms(tpl.get("footer_text")) or "Terima kasih atas pembayaran Anda.", styles["Normal"])]
    _rc_signer = await _freeze_signer("receipt", r, tpl, "schedule_payments")
    _rc_sig = _signature_block(_rc_signer, tpl, base_font, bold_font, place_date=_id_dateline(tpl, r.get("created_at")))
    if _rc_sig:
        el += [Spacer(1, 10 * mm), _rc_sig]
    paid_full = float(r.get("outstanding_total") or 0) <= 0

    def _stamp(canvas, _d):
        if not paid_full:
            return
        canvas.saveState()
        canvas.translate(105 * mm, 148.5 * mm)
        canvas.rotate(30)
        canvas.setFont(bold_font, 72)
        canvas.setFillColor(colors.Color(0.13, 0.7, 0.4, alpha=0.25))
        canvas.drawCentredString(0, 0, tpl.get("paid_stamp_text", "LUNAS"))
        canvas.restoreState()

    doc.build(el, onFirstPage=_stamp)
    return buf.getvalue(), r.get("receipt_number")


@api_router.get("/public/documents/{kind}/{doc_id}")
async def public_document_pdf(kind: str, doc_id: str, sig: str = Query("")):
    if kind not in ("invoice", "quotation", "receipt") or not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=404, detail="Not found")
    if not sig or not _hmac.compare_digest(sig, _doc_sig(kind, doc_id)):
        raise HTTPException(status_code=403, detail="Invalid signature")
    if kind == "invoice":
        inv = await db.invoices.find_one({"_id": ObjectId(doc_id)})
        if not inv:
            raise HTTPException(status_code=404, detail="Not found")
        await _recompute_invoice_status(doc_id)
        inv = await db.invoices.find_one({"_id": ObjectId(doc_id)})
        pdf, name = await _render_invoice_pdf(inv)
    elif kind == "quotation":
        q = await db.quotations.find_one({"_id": ObjectId(doc_id)})
        if not q:
            raise HTTPException(status_code=404, detail="Not found")
        pdf, name = await _render_quotation_pdf(q)
    else:
        r = await db.schedule_payments.find_one({"_id": ObjectId(doc_id)})
        if not r:
            raise HTTPException(status_code=404, detail="Not found")
        pdf, name = await _render_receipt_pdf(r)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={name}.pdf"})


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
    hotel_items: Optional[List[dict]] = []


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
    # Auto-expire: quotations older than 7 days that are still open become EXPIRED.
    _cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    await db.quotations.update_many(
        {"status": {"$in": ["DRAFT", "SENT"]}, "created_at": {"$lt": _cutoff},
         "converted_booking_id": {"$in": [None, ""]}},
        {"$set": {"status": "EXPIRED"}})
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
    _h_items = [_hotel_item_snapshot(h) for h in (body.hotel_items or [])]
    _h_total = sum(x["total"] for x in _h_items)
    doc["hotel_items"] = _h_items
    doc["hotel_total"] = _h_total
    doc["grand_total_with_hotel"] = float(amt["total"]) + _h_total
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
    _hi_in = body.hotel_items or []
    _h_items = [_hotel_item_snapshot(h) for h in _hi_in] if _hi_in else (q.get("hotel_items") or [])
    _h_total = sum(float(x.get("total") or 0) for x in _h_items)
    updates["hotel_items"] = _h_items
    updates["hotel_total"] = _h_total
    updates["grand_total_with_hotel"] = float(amt["total"]) + _h_total
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
    pdf, name = await _render_quotation_pdf(q)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={name}.pdf"})


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
    idem = (body or {}).get("idempotency_key") or None
    ext_order = (body or {}).get("external_order_id") or None
    n8n_wf = (body or {}).get("n8n_workflow_id") or None
    if idem:
        dup = await db.bookings.find_one({"idempotency_key": idem})
        if dup:
            return serialize(dup)
    cust = await db.customers.find_one({"_id": ObjectId(q["customer_id"])}) if ObjectId.is_valid(q.get("customer_id") or "") else None
    if not cust:
        raise HTTPException(status_code=400, detail="Customer tidak ditemukan")
    pkg = await db.packages.find_one({"_id": ObjectId(q["package_id"])})
    if not pkg:
        raise HTTPException(status_code=400, detail="Package tidak ditemukan")
    pax = int(q.get("pax") or 0)
    if pax < 1:
        raise HTTPException(status_code=400, detail="Jumlah pax minimal 1")
    if float(q.get("total") or 0) <= 0 or float(q.get("per_pax_price") or 0) <= 0:
        raise HTTPException(status_code=400, detail="Harga booking tidak valid (harus dari konfigurasi paket/departure)")
    dep = None
    dep_id = q.get("departure_id")
    if dep_id and ObjectId.is_valid(dep_id):
        dep = await db.departures.find_one({"_id": ObjectId(dep_id)})
        if not dep:
            raise HTTPException(status_code=400, detail="Departure tidak ditemukan")
        if dep.get("status") in ("CLOSED", "CANCELLED"):
            raise HTTPException(status_code=400, detail=f"Departure {dep.get('status')} — booking tidak dapat dibuat")
        available = max(int(dep.get("quota") or 0) - int(dep.get("confirmed_pax") or 0), 0)
        if available <= 0:
            raise HTTPException(status_code=400, detail="Seat habis (available = 0) — booking tidak dapat dibuat")
        if available < pax:
            raise HTTPException(status_code=400, detail=f"Seat tidak cukup: tersedia {available}, dibutuhkan {pax}")
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
               "idempotency_key": idem, "external_order_id": ext_order, "n8n_workflow_id": n8n_wf,
               "branch": q.get("branch", ""), "created_at": now_iso(), "created_by": user["name"]}
    res = await db.bookings.insert_one(booking)
    bid = str(res.inserted_id)
    if dep:
        await db.departures.update_one({"_id": ObjectId(dep_id)}, {"$inc": {"confirmed_pax": pax}})
    await db.quotations.update_one({"_id": ObjectId(qid)}, {"$set": {"converted_booking_id": bid, "status": "CONVERTED"}})
    await log_audit(user, "booking", "convert", request, record_id=bid, new={"number": number})
    phone = await _cust_phone(q.get("customer_id"))
    trigger_n8n("booking.created", {"id": bid, "booking_number": number, "customer_name": q["customer_name"],
        "customer_phone": phone, "total": q.get("total")})
    return serialize(await db.bookings.find_one({"_id": res.inserted_id}))


@api_router.get("/bookings")
async def list_bookings(status: Optional[str] = None, search: Optional[str] = None,
                        user: dict = Depends(require_permission("booking.view"))):
    query = owner_filter(user)
    if status and status != "all":
        query = {**query, "status": status}
    s = (search or "").strip()
    if s:
        rx = {"$regex": re.escape(s), "$options": "i"}
        or_clauses = [{"booking_number": rx}, {"customer_name": rx}]
        # Resolve phone / email / name against customers to search by customer_id
        cust = await db.customers.find({"$or": [{"phone": rx}, {"whatsapp": rx}, {"email": rx}, {"full_name": rx}]}).to_list(500)
        cids = [str(c["_id"]) for c in cust]
        if cids:
            or_clauses.append({"customer_id": {"$in": cids}})
        query = {**query, "$and": [{"$or": or_clauses}]} if query else {"$or": or_clauses}
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


BOOKING_STATUSES = ["DRAFT", "PENDING", "CONFIRMED", "PARTIAL_PAID", "PAID", "READY", "COMPLETED", "CANCELLED", "REFUNDED"]
BOOKING_TRANSITIONS = {
    "DRAFT": ["PENDING", "CONFIRMED", "CANCELLED"],
    "PENDING": ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["PARTIAL_PAID", "PAID", "CANCELLED"],
    "PARTIAL_PAID": ["PAID", "CANCELLED"],
    "PAID": ["READY", "CANCELLED"],
    "READY": ["COMPLETED", "CANCELLED"],
    "COMPLETED": [],
    "CANCELLED": ["REFUNDED"],
    "REFUNDED": [],
}


async def _booking_payments(bid):
    inv_ids = [str(i["_id"]) for i in await db.invoices.find({"booking_id": bid}).to_list(200)]
    return await db.payments.find({"$or": [{"booking_id": bid}, {"invoice_id": {"$in": inv_ids}}]}).sort("created_at", 1).to_list(500)


@api_router.patch("/bookings/{bid}/status")
async def update_booking_status(bid: str, body: dict, request: Request, user: dict = Depends(require_permission("booking.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not can_access_record(user, b):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    old = b.get("status", "DRAFT")
    new = (body.get("status") or "").upper()
    reason = (body.get("reason") or "").strip()
    if new not in BOOKING_STATUSES:
        raise HTTPException(status_code=400, detail="Status tidak valid")
    if new == old:
        return serialize(b)
    allowed = BOOKING_TRANSITIONS.get(old, [])
    if new not in allowed:
        raise HTTPException(status_code=400, detail=f"Transisi {old} → {new} tidak diizinkan. Pilihan: {', '.join(allowed) or '-'}")
    if new in ("PARTIAL_PAID", "PAID") and not await _booking_payments(bid):
        raise HTTPException(status_code=400, detail="Tidak bisa ke status pembayaran tanpa transaksi payment tercatat")
    entry = {"old_status": old, "new_status": new, "user": user["name"], "role": user["role"], "reason": reason, "at": now_iso()}
    hist = b.get("status_history", []) + [entry]
    if new == "CANCELLED" and old != "CANCELLED" and b.get("departure_id") and ObjectId.is_valid(b["departure_id"]):
        await db.departures.update_one({"_id": ObjectId(b["departure_id"])}, {"$inc": {"confirmed_pax": -int(b.get("pax") or 0)}})
    await db.bookings.update_one({"_id": ObjectId(bid)}, {"$set": {"status": new, "status_history": hist, "updated_at": now_iso()}})
    await log_audit(user, "booking", "status_change", request, record_id=bid, old={"status": old}, new={"status": new, "reason": reason})
    trigger_n8n("booking.updated", {"id": bid, "booking_number": b.get("booking_number"), "status": new})
    return serialize(await db.bookings.find_one({"_id": ObjectId(bid)}))


@api_router.get("/bookings/{bid}/timeline")
async def booking_timeline(bid: str, user: dict = Depends(require_permission("booking.view"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not can_access_record(user, b):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    status = b.get("status", "DRAFT")
    quo = None
    if b.get("quotation_id") and ObjectId.is_valid(b["quotation_id"]):
        quo = await db.quotations.find_one({"_id": ObjectId(b["quotation_id"])})
    pays = await _booking_payments(bid)
    tids = [t["_id"] for t in await db.travelers.find({"booking_id": bid}).to_list(200)]
    doc_count = await db.documents.count_documents({"traveler_id": {"$in": tids}, "is_deleted": False}) if tids else 0
    today = today_str()

    def step(name, done, at=None, detail=""):
        return {"step": name, "done": bool(done), "at": at, "detail": detail}

    if status in ("CANCELLED", "REFUNDED"):
        cx = await db.cancellation_requests.find_one({"booking_id": bid}, sort=[("created_at", -1)])
        rf = await db.refund_requests.find_one({"booking_id": bid}, sort=[("created_at", -1)])
        cs = (cx or {}).get("status", "")
        rs = (rf or {}).get("status", "")
        steps = [
            step("Booking", True, b.get("created_at"), b.get("booking_number")),
            step("Cancellation Requested", bool(cx), (cx or {}).get("created_at"), (cx or {}).get("cancellation_number", "")),
            step("Super Admin Approval", cs == "APPROVED", None, cs),
            step("Refund Calculation", bool(rf), (rf or {}).get("created_at"), (rf or {}).get("refund_number", "")),
            step("Refund Approved", rs in ("APPROVED", "PROCESSING", "PARTIALLY_REFUNDED", "REFUNDED"), None, rs),
            step("Refund Paid", rs in ("REFUNDED", "PARTIALLY_REFUNDED"), None, rs),
        ]
        return {"branch": "cancellation", "status": status, "steps": steps, "allowed_next": BOOKING_TRANSITIONS.get(status, [])}
    dep_done = status in ("READY", "COMPLETED") or bool(b.get("departure_date") and (b.get("departure_date") or "")[:10] <= today)
    steps = [
        step("Lead", bool(b.get("lead_id") or (quo and quo.get("lead_id"))), None, ""),
        step("Quotation", bool(quo), (quo or {}).get("created_at"), (quo or {}).get("quotation_number", "")),
        step("Quotation Converted", bool(quo and quo.get("status") == "CONVERTED"), None, ""),
        step("Booking", True, b.get("created_at"), b.get("booking_number")),
        step("Payment", len(pays) > 0, (pays[0].get("created_at") if pays else None), f"{len(pays)} payment"),
        step("Documents", doc_count > 0, None, f"{doc_count} dokumen"),
        step("Departure", dep_done, b.get("departure_date"), ""),
        step("Completed", status == "COMPLETED", None, ""),
    ]
    return {"branch": "normal", "status": status, "steps": steps, "allowed_next": BOOKING_TRANSITIONS.get(status, [])}


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


PAY_PLAN_TYPES = ["FULL", "DP", "INSTALLMENT"]


def _sched_item_status(item, today):
    amt = float(item.get("amount") or 0)
    paid = float(item.get("paid_amount") or 0)
    if item.get("status") == "CANCELLED":
        return "CANCELLED"
    if paid >= amt and amt > 0:
        return "PAID"
    if (item.get("due_date") or "")[:10] and (item.get("due_date") or "")[:10] < today and paid < amt:
        return "OVERDUE"
    if paid > 0:
        return "PARTIAL"
    return "PENDING"


def _add_days(base_iso, n):
    try:
        d = datetime.fromisoformat((base_iso or now_iso())[:10])
    except Exception:
        d = datetime.now(timezone.utc)
    return (d + timedelta(days=n)).date().isoformat()


@api_router.post("/bookings/{bid}/payment-plan")
async def generate_payment_plan(bid: str, body: dict, request: Request, user: dict = Depends(require_permission("payment.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    total = round(float(b.get("total") or 0), 2)
    if total <= 0:
        raise HTTPException(status_code=400, detail="Total booking belum tersedia")
    plan = (body.get("plan_type") or "FULL").upper()
    if plan not in PAY_PLAN_TYPES:
        raise HTTPException(status_code=400, detail="Plan tidak valid")
    first_due = body.get("first_due") or today_str()
    items = []
    if plan == "FULL":
        items = [{"payment_number": 1, "label": "Full Payment", "due_date": first_due, "amount": total}]
    elif plan == "DP":
        dp = round(float(body.get("dp_amount") or 0), 2)
        if dp <= 0 or dp >= total:
            raise HTTPException(status_code=400, detail="DP harus > 0 dan < total")
        interval = int(body.get("interval_days") or 30)
        items = [{"payment_number": 1, "label": "DP", "due_date": first_due, "amount": dp},
                 {"payment_number": 2, "label": "Pelunasan", "due_date": _add_days(first_due, interval), "amount": round(total - dp, 2)}]
    else:  # INSTALLMENT
        n = int(body.get("installments") or 3)
        if n < 2:
            raise HTTPException(status_code=400, detail="Installment minimal 2")
        interval = int(body.get("interval_days") or 30)
        base = round(total / n, 2)
        for i in range(n):
            amt = round(total - base * (n - 1), 2) if i == n - 1 else base
            items.append({"payment_number": i + 1, "label": f"Installment {i + 1}", "due_date": _add_days(first_due, interval * i), "amount": amt})
    today = today_str()
    for it in items:
        it.update({"paid_amount": 0, "outstanding": it["amount"], "status": _sched_item_status(it, today)})
    await db.bookings.update_one({"_id": ObjectId(bid)}, {"$set": {"payment_plan": plan, "payment_schedule": items}})
    await log_audit(user, "booking", "payment_plan", request, record_id=bid, new={"plan": plan, "items": len(items)})
    return serialize(await db.bookings.find_one({"_id": ObjectId(bid)}))


@api_router.patch("/bookings/{bid}/schedule/{pnum}/record")
async def record_schedule_payment(bid: str, pnum: int, body: dict, request: Request, user: dict = Depends(require_permission("payment.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)})
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    sched = b.get("payment_schedule") or []
    amount = round(float(body.get("amount") or 0), 2)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount pembayaran wajib > 0")
    today = today_str()
    found = False
    for it in sched:
        if int(it.get("payment_number")) == int(pnum):
            it["paid_amount"] = round(float(it.get("paid_amount") or 0) + amount, 2)
            it["outstanding"] = max(round(float(it.get("amount") or 0) - it["paid_amount"], 2), 0)
            it["status"] = _sched_item_status(it, today)
            it["last_paid_at"] = now_iso()
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Jadwal pembayaran tidak ditemukan")
    total = round(sum(float(i.get("amount") or 0) for i in sched if i.get("status") != "CANCELLED"), 2)
    paid_total = round(sum(float(i.get("paid_amount") or 0) for i in sched), 2)
    outstanding = max(round(total - paid_total, 2), 0)
    upd = {"payment_schedule": sched, "paid_total": paid_total, "outstanding_total": outstanding}
    if outstanding <= 0 and total > 0:
        upd["payment_status"] = "PAID"
        upd["full_payment_date"] = today
        if b.get("status") in ("CONFIRMED", "PARTIAL_PAID"):
            hist = b.get("status_history", []) + [{"old_status": b.get("status"), "new_status": "PAID", "user": user["name"], "role": user["role"], "reason": "Full payment (schedule lunas)", "at": now_iso()}]
            upd["status"] = "PAID"
            upd["status_history"] = hist
        # Commission Eligibility: mark eligible on full payment date + notify sales
        upd["commission_eligible"] = True
        upd["commission_eligible_date"] = today
        if b.get("sales_pic_id"):
            await notify("Commission Eligible", f"{b.get('booking_number', '')} lunas — komisi eligible ({today})",
                         link=f"/crm/{b.get('customer_id')}" if b.get("customer_id") else "/commission",
                         user_id=b.get("sales_pic_id"), ntype="COMMISSION_ELIGIBLE", priority="high")
    elif paid_total > 0:
        upd["payment_status"] = "PARTIAL"
        if b.get("status") == "CONFIRMED":
            hist = b.get("status_history", []) + [{"old_status": "CONFIRMED", "new_status": "PARTIAL_PAID", "user": user["name"], "role": user["role"], "reason": "DP/cicilan diterima", "at": now_iso()}]
            upd["status"] = "PARTIAL_PAID"
            upd["status_history"] = hist
    rnum = await next_number("KW", db.schedule_payments, "receipt_number")
    rec = {"receipt_number": rnum, "booking_id": bid, "booking_number": b.get("booking_number"),
           "customer_id": b.get("customer_id"), "customer_name": b.get("customer_name", ""),
           "payment_number": int(pnum), "label": it.get("label", ""), "amount": amount,
           "paid_after": it["paid_amount"], "outstanding_after": it["outstanding"],
           "outstanding_total": outstanding, "recorded_by": user["name"], "created_at": now_iso()}
    rid = str((await db.schedule_payments.insert_one(rec)).inserted_id)
    it["last_receipt_id"] = rid
    it["last_receipt_number"] = rnum
    upd["payment_schedule"] = sched
    await db.bookings.update_one({"_id": ObjectId(bid)}, {"$set": upd})
    await log_audit(user, "booking", "schedule_payment", request, record_id=bid, new={"payment_number": pnum, "amount": amount, "receipt": rnum})
    out_doc = serialize(await db.bookings.find_one({"_id": ObjectId(bid)}))
    out_doc["last_receipt_id"] = rid
    out_doc["last_receipt_number"] = rnum
    return out_doc


@api_router.get("/receipts/{rid}/pdf")
async def receipt_pdf(rid: str, user: dict = Depends(require_permission("booking.view"))):
    r = await db.schedule_payments.find_one({"_id": ObjectId(rid)})
    if not r:
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan")
    pdf, name = await _render_receipt_pdf(r)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=kwitansi-{name}.pdf"})


# ---- Customer Portal: uploads & PDF downloads (Phase 9L.1) ----
PORTAL_DOC_TYPES = ["PASSPORT", "KTP", "KK", "PHOTO", "VISA", "VACCINE_CERT", "OTHER"]


async def _portal_customer_from_token(token):
    if not token:
        return None
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "customer_access":
            return None
        return await db.customers.find_one({"_id": ObjectId(payload["customer_id"])})
    except jwt.InvalidTokenError:
        return None


@api_router.post("/portal/documents")
async def portal_upload_document(doc_type: str = Form(...), file: UploadFile = File(...),
                                 document_number: str = Form(""), expiry_date: str = Form(""),
                                 cust: dict = Depends(get_current_customer)):
    dtype = (doc_type or "OTHER").upper()
    if dtype not in PORTAL_DOC_TYPES:
        dtype = "OTHER"
    cid = str(cust["_id"])
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 10MB")
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "bin"
    doc_id = str(_uuid.uuid4())
    path = f"{_APP_NAME}/documents/customer/{cid}/{doc_id}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    rec = {"id": doc_id, "traveler_id": None, "booking_id": None, "customer_id": cid, "doc_type": dtype,
           "document_number": document_number, "issue_date": "", "expiry_date": expiry_date,
           "storage_path": result["path"], "original_filename": file.filename, "content_type": file.content_type,
           "size": result.get("size", len(data)), "status": "Uploaded", "is_deleted": False,
           "uploaded_by": (cust.get("full_name") or "customer") + " (portal)", "source": "portal", "created_at": now_iso()}
    await db.documents.insert_one(rec)
    return {"success": True, "id": doc_id, "doc_type": dtype, "status": "Uploaded"}


@api_router.get("/portal/invoices/{iid}/pdf")
async def portal_invoice_pdf(iid: str, authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    cust = await _portal_customer_from_token(token)
    if not cust:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not ObjectId.is_valid(iid):
        raise HTTPException(status_code=404, detail="Invoice not found")
    inv = await db.invoices.find_one({"_id": ObjectId(iid)})
    if not inv or str(inv.get("customer_id")) != str(cust["_id"]):
        raise HTTPException(status_code=404, detail="Invoice not found")
    pdf, name = await _render_invoice_pdf(inv)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={name}.pdf"})


@api_router.get("/portal/receipts/{rid}/pdf")
async def portal_receipt_pdf(rid: str, authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    cust = await _portal_customer_from_token(token)
    if not cust:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not ObjectId.is_valid(rid):
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan")
    r = await db.schedule_payments.find_one({"_id": ObjectId(rid)})
    if not r or str(r.get("customer_id")) != str(cust["_id"]):
        raise HTTPException(status_code=404, detail="Kwitansi tidak ditemukan")
    pdf, name = await _render_receipt_pdf(r)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename=kwitansi-{name}.pdf"})



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
FINANCIAL_DOC_TYPES = {"Quotation", "Invoice", "Payment Proof", "Refund Document", "Supplier Invoice", "Booking Confirmation"}


@api_router.post("/travelers/{tid}/documents")
async def upload_document(tid: str, doc_type: str = Form(...), file: UploadFile = File(...),
                          document_number: str = Form(""), issue_date: str = Form(""), expiry_date: str = Form(""),
                          user: dict = Depends(require_permission("document.manage"))):
    t = await db.travelers.find_one({"_id": ObjectId(tid)})
    if not t:
        raise HTTPException(status_code=404, detail="Traveler not found")
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    doc_id = str(_uuid.uuid4())
    path = f"{_APP_NAME}/documents/{tid}/{doc_id}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type or "application/octet-stream")
    rec = {"id": doc_id, "traveler_id": tid, "booking_id": t.get("booking_id"), "doc_type": doc_type,
           "document_number": document_number, "issue_date": issue_date, "expiry_date": expiry_date,
           "storage_path": result["path"], "original_filename": file.filename, "content_type": file.content_type,
           "size": result.get("size", len(data)), "status": "Uploaded", "is_deleted": False,
           "uploaded_by": user["name"], "created_at": now_iso()}
    await db.documents.insert_one(rec)
    if doc_type in ("PASSPORT", "Passport"):
        tset = {}
        if document_number:
            tset["passport_number"] = document_number
        if expiry_date:
            tset["passport_expiry"] = expiry_date
        if tset:
            await db.travelers.update_one({"_id": ObjectId(tid)}, {"$set": tset})
    return {k: v for k, v in rec.items() if k != "_id"}


async def _doc_scope_ok(user, d):
    if user["role"] == "super_admin":
        return True
    if user["role"] == "accounting":
        return d.get("doc_type") in FINANCIAL_DOC_TYPES
    if user["role"] == "sales":
        if d.get("booking_id") and ObjectId.is_valid(d["booking_id"]):
            bk = await db.bookings.find_one({"_id": ObjectId(d["booking_id"])})
            return bool(bk and bk.get("sales_pic_id") == user["_id"])
        if d.get("customer_id") and ObjectId.is_valid(d["customer_id"]):
            cust = await db.customers.find_one({"_id": ObjectId(d["customer_id"])})
            return bool(cust and can_access_record(user, cust))
        return False
    return True


async def _find_doc(doc_id):
    d = await db.documents.find_one({"id": doc_id, "is_deleted": False})
    if not d and ObjectId.is_valid(doc_id):
        d = await db.documents.find_one({"_id": ObjectId(doc_id), "is_deleted": False})
    return d


@api_router.post("/customers/{cid}/documents")
async def upload_customer_document(cid: str, doc_type: str = Form(...), file: UploadFile = File(...),
                                   document_number: str = Form(""), issue_date: str = Form(""), expiry_date: str = Form(""),
                                   user: dict = Depends(require_permission("document.manage"))):
    try:
        oid = ObjectId(cid)
    except Exception:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = await db.customers.find_one({"_id": oid})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not can_access_record(user, customer):
        raise HTTPException(status_code=403, detail="403 Forbidden: not your customer")
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    doc_id = str(_uuid.uuid4())
    path = f"{_APP_NAME}/documents/customer/{cid}/{doc_id}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type or "application/octet-stream")
    rec = {"id": doc_id, "traveler_id": None, "booking_id": None, "customer_id": cid, "doc_type": doc_type,
           "document_number": document_number, "issue_date": issue_date, "expiry_date": expiry_date,
           "storage_path": result["path"], "original_filename": file.filename, "content_type": file.content_type,
           "size": result.get("size", len(data)), "status": "Uploaded", "is_deleted": False,
           "uploaded_by": user["name"], "created_at": now_iso()}
    await db.documents.insert_one(rec)
    return {k: v for k, v in rec.items() if k != "_id"}


@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(require_permission("document.manage"))):
    d = await _find_doc(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    if not await _doc_scope_ok(user, d):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    await db.documents.update_one({"_id": d["_id"]}, {"$set": {"is_deleted": True, "deleted_by": user["name"], "deleted_at": now_iso()}})
    return {"success": True}


@api_router.post("/documents/{doc_id}/replace")
async def replace_document(doc_id: str, file: UploadFile = File(...),
                           document_number: str = Form(None), issue_date: str = Form(None), expiry_date: str = Form(None),
                           user: dict = Depends(require_permission("document.manage"))):
    d = await _find_doc(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    if not await _doc_scope_ok(user, d):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    key = d.get("id") or str(d["_id"])
    scope = d.get("traveler_id") or (f"customer/{d['customer_id']}" if d.get("customer_id") else "misc")
    path = f"{_APP_NAME}/documents/{scope}/{key}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type or "application/octet-stream")
    upd = {"storage_path": result["path"], "original_filename": file.filename, "content_type": file.content_type,
           "size": result.get("size", len(data)), "status": "Uploaded", "uploaded_by": user["name"], "updated_at": now_iso()}
    if document_number is not None:
        upd["document_number"] = document_number
    if issue_date is not None:
        upd["issue_date"] = issue_date
    if expiry_date is not None:
        upd["expiry_date"] = expiry_date
    await db.documents.update_one({"_id": d["_id"]}, {"$set": upd})
    if d.get("doc_type") in ("PASSPORT", "Passport") and d.get("traveler_id"):
        tset = {}
        if upd.get("document_number"):
            tset["passport_number"] = upd["document_number"]
        if upd.get("expiry_date"):
            tset["passport_expiry"] = upd["expiry_date"]
        if tset:
            await db.travelers.update_one({"_id": ObjectId(d["traveler_id"])}, {"$set": tset})
    nd = await db.documents.find_one({"_id": d["_id"]})
    return {k: v for k, v in serialize(nd).items() if k != "_id"}


@api_router.patch("/documents/{doc_id}/status")
async def set_document_status(doc_id: str, body: dict, user: dict = Depends(require_permission("document.manage"))):
    status = body.get("status")
    if status not in DOC_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    d = await _find_doc(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.documents.update_one({"_id": d["_id"]}, {"$set": {"status": status, "verified_by": user["name"]}})
    d = await db.documents.find_one({"_id": d["_id"]})
    return {k: v for k, v in serialize(d).items() if k != "_id"} if d else {}


@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    d = await _find_doc(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    if not await _doc_scope_ok(user, d):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    data, ct = get_object(d["storage_path"])
    return Response(content=data, media_type=d.get("content_type") or ct)


# ============================================================================
# Phase 10E-5 — File Download Center (internal, secure, RBAC-scoped)
# ============================================================================
FILE_CATEGORIES = ["Price List", "Sales Material", "Product Information", "SOP",
                   "Company Document", "Accounting Document", "Tax Document", "Training", "Other"]
FILE_ACCESS_TYPES = ["ALL_STAFF", "SALES", "ACCOUNTING", "SALES_ACCOUNTING", "SPECIFIC"]
FILE_ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "ppt", "pptx", "jpg", "jpeg", "png", "zip"}
FILE_MAX_BYTES = 25 * 1024 * 1024


def _file_roles_for(access_type):
    return {"ALL_STAFF": ["sales", "accounting"], "SALES": ["sales"], "ACCOUNTING": ["accounting"],
            "SALES_ACCOUNTING": ["sales", "accounting"], "SPECIFIC": []}.get(access_type, [])


def _parse_id_list(raw):
    import json as _json
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    raw = str(raw).strip()
    try:
        v = _json.loads(raw)
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in raw.split(",") if x.strip()]


def _bump_version(v):
    m = re.match(r"^v?(\d+)$", (v or "").strip(), re.I)
    return f"v{int(m.group(1)) + 1}" if m else (v or "v1")


def _file_access_ok(user, f):
    if user["role"] == "super_admin":
        return True
    if (f.get("status") or "ACTIVE") != "ACTIVE" or f.get("is_deleted"):
        return False
    if user["role"] in (f.get("allowed_roles") or []):
        return True
    return user["_id"] in (f.get("allowed_user_ids") or [])


def _file_out(f):
    d = serialize(dict(f))
    d.pop("storage_path", None)
    d.pop("version_history", None)
    return d


@api_router.get("/files/meta")
async def files_meta(user: dict = Depends(require_role("super_admin"))):
    users = await db.users.find({"is_deleted": {"$ne": True}}).to_list(500)
    return {"categories": FILE_CATEGORIES, "access_types": FILE_ACCESS_TYPES,
            "users": [{"id": str(u["_id"]), "name": u.get("name"), "role": u.get("role")} for u in users]}


@api_router.get("/files/download-logs")
async def file_download_logs(file_id: Optional[str] = None, user: dict = Depends(require_role("super_admin"))):
    q = {"file_id": file_id} if file_id else {}
    logs = await db.file_downloads.find(q).sort("timestamp", -1).to_list(1000)
    return [serialize(x) for x in logs]


@api_router.get("/files")
async def list_files(category: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"is_deleted": {"$ne": True}}
    if category and category != "all":
        q["category"] = category
    docs = await db.company_files.find(q).sort("created_at", -1).to_list(1000)
    return [_file_out(d) for d in docs if _file_access_ok(user, d)]


@api_router.post("/files")
async def upload_company_file(request: Request, file: UploadFile = File(...), file_name: str = Form(""),
                              description: str = Form(""), category: str = Form("Other"),
                              version: str = Form("v1"), access_type: str = Form("ALL_STAFF"),
                              allowed_user_ids: str = Form(""), user: dict = Depends(require_role("super_admin"))):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in FILE_ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Tipe file tidak didukung: .{ext or '?'}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(data) > FILE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran file melebihi 25MB")
    if access_type not in FILE_ACCESS_TYPES:
        access_type = "ALL_STAFF"
    uid = str(ObjectId())
    path = f"{_APP_NAME}/company_files/{uid}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    uids = _parse_id_list(allowed_user_ids)
    doc = {"file_name": (file_name or file.filename or "Untitled").strip(),
           "description": (description or "").strip(),
           "category": category if category in FILE_CATEGORIES else "Other",
           "version": (version or "v1").strip(), "storage_path": result["path"],
           "content_type": file.content_type or "application/octet-stream",
           "original_filename": file.filename, "size": len(data),
           "access_type": access_type, "allowed_roles": _file_roles_for(access_type),
           "allowed_user_ids": uids, "status": "ACTIVE", "version_history": [], "is_deleted": False,
           "uploaded_by": user["name"], "uploaded_by_id": user["_id"],
           "created_at": now_iso(), "updated_at": now_iso()}
    res = await db.company_files.insert_one(doc)
    doc["_id"] = res.inserted_id
    for r in doc["allowed_roles"]:
        await notify("File baru tersedia untuk diunduh", f"{doc['file_name']} ({doc['category']})", link="/documents", role=r)
    for u in uids:
        await notify("File baru tersedia untuk diunduh", f"{doc['file_name']} ({doc['category']})", link="/documents", user_id=u)
    await log_audit(user, "file", "upload_file", request, record_id=str(res.inserted_id),
                    new={"file_name": doc["file_name"], "access_type": access_type})
    return _file_out(doc)


@api_router.get("/files/{fid}")
async def get_company_file(fid: str, user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    f = await db.company_files.find_one({"_id": ObjectId(fid)})
    if not f:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    d = serialize(dict(f))
    d.pop("storage_path", None)
    return d


@api_router.put("/files/{fid}")
async def update_company_file(fid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    f = await db.company_files.find_one({"_id": ObjectId(fid)})
    if not f:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    upd = {}
    for k in ("file_name", "description", "category", "version", "status"):
        if body.get(k) is not None:
            upd[k] = body[k]
    if body.get("access_type") in FILE_ACCESS_TYPES:
        upd["access_type"] = body["access_type"]
        upd["allowed_roles"] = _file_roles_for(body["access_type"])
    if "allowed_user_ids" in body:
        upd["allowed_user_ids"] = _parse_id_list(body["allowed_user_ids"])
    upd["updated_at"] = now_iso()
    await db.company_files.update_one({"_id": ObjectId(fid)}, {"$set": upd})
    await log_audit(user, "file", "update_file", request, record_id=fid, new=upd)
    return _file_out(await db.company_files.find_one({"_id": ObjectId(fid)}))


@api_router.post("/files/{fid}/replace")
async def replace_company_file(fid: str, request: Request, file: UploadFile = File(...),
                               version: str = Form(""), user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    f = await db.company_files.find_one({"_id": ObjectId(fid)})
    if not f:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in FILE_ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Tipe file tidak didukung: .{ext or '?'}")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(data) > FILE_MAX_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran file melebihi 25MB")
    hist = f.get("version_history") or []
    hist.append({"version": f.get("version"), "storage_path": f.get("storage_path"),
                 "original_filename": f.get("original_filename"), "size": f.get("size"),
                 "replaced_at": now_iso(), "replaced_by": user["name"]})
    uid = str(ObjectId())
    path = f"{_APP_NAME}/company_files/{uid}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    new_ver = (version or "").strip() or _bump_version(f.get("version"))
    await db.company_files.update_one({"_id": ObjectId(fid)}, {"$set": {
        "storage_path": result["path"], "content_type": file.content_type or "application/octet-stream",
        "original_filename": file.filename, "size": len(data), "version": new_ver,
        "version_history": hist, "updated_at": now_iso()}})
    await log_audit(user, "file", "replace_file", request, record_id=fid, new={"version": new_ver})
    return _file_out(await db.company_files.find_one({"_id": ObjectId(fid)}))


@api_router.delete("/files/{fid}")
async def delete_company_file(fid: str, request: Request, reason: str = Query(""), user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    f = await db.company_files.find_one({"_id": ObjectId(fid)})
    if not f:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    await db.company_files.update_one({"_id": ObjectId(fid)}, {"$set": {
        "is_deleted": True, "status": "ARCHIVED", "deleted_by": user["name"], "deleted_at": now_iso()}})
    await log_audit(user, "file", "delete_file", request, record_id=fid, reason=(reason or "").strip() or None)
    return {"message": "File dihapus"}


@api_router.get("/files/{fid}/download")
async def download_company_file(fid: str, request: Request, inline: bool = False,
                                authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not ObjectId.is_valid(fid):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    f = await db.company_files.find_one({"_id": ObjectId(fid)})
    if not f or f.get("is_deleted"):
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    if not _file_access_ok(user, f):
        raise HTTPException(status_code=403, detail="403 Forbidden: no access to this file")
    data, ct = get_object(f["storage_path"])
    await db.file_downloads.insert_one({"file_id": fid, "file_name": f.get("file_name"), "version": f.get("version"),
        "user_id": user.get("_id"), "user_name": user.get("name"), "user_role": user.get("role"),
        "action": "PREVIEW" if inline else "DOWNLOAD",
        "ip": request.client.host if request and request.client else None,
        "user_agent": request.headers.get("user-agent") if request else None, "timestamp": now_iso()})
    fname = f.get("original_filename") or f.get("file_name") or "file"
    disp = "inline" if inline else "attachment"
    return Response(content=data, media_type=f.get("content_type") or ct,
                    headers={"Content-Disposition": f'{disp}; filename="{fname}"'})


@api_router.get("/documents/expiring")
async def documents_expiring(within: int = 90, user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date()
    out = []
    q = {"is_deleted": False, "doc_type": {"$in": ["PASSPORT", "Passport", "VISA", "Visa"]}, "expiry_date": {"$nin": ["", None]}}
    async for d in db.documents.find(q):
        exp = (d.get("expiry_date") or "")[:10]
        try:
            days = (datetime.fromisoformat(exp).date() - today).days
        except Exception:
            continue
        if days > within:
            continue
        if user["role"] == "sales":
            ok = False
            if d.get("booking_id") and ObjectId.is_valid(d["booking_id"]):
                bk = await db.bookings.find_one({"_id": ObjectId(d["booking_id"])})
                ok = bool(bk and bk.get("sales_pic_id") == user["_id"])
            elif d.get("customer_id") and ObjectId.is_valid(d["customer_id"]):
                cust = await db.customers.find_one({"_id": ObjectId(d["customer_id"])})
                ok = bool(cust and can_access_record(user, cust))
            if not ok:
                continue
        d = serialize(d)
        d["days_left"] = days
        out.append(d)
    out.sort(key=lambda x: x["days_left"])
    return out


# ---------- Invoices ----------
async def _recompute_invoice_status(invoice_id: str):
    inv = await db.invoices.find_one({"_id": ObjectId(invoice_id)})
    if not inv:
        return None
    payments = await db.payments.find({"invoice_id": invoice_id, "status": {"$ne": "VOID"}}).to_list(500)
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
    # Nominal invoice = harga paket (per pax booking) x jumlah peserta terdaftar di booking.
    # Fallback ke booking.pax bila belum ada peserta yang didaftarkan.
    trav_count = await db.travelers.count_documents({"booking_id": bid})
    booking_pax = max(int(b.get("pax") or 1), 1)
    pax_count = trav_count if trav_count > 0 else booking_pax
    per_pax = float(b.get("per_pax_price") or 0)
    addon_total = sum(float(a.get("amount") or 0) for a in (b.get("addons") or []))
    gross = per_pax * pax_count
    subtotal = gross + addon_total
    disc_pct = float(b.get("discount_percent") or 0)
    if disc_pct > 0:
        discount_amount = round(subtotal * disc_pct / 100)
    else:
        discount_amount = float(b.get("discount_amount") or 0)
    tax_pct = float(b.get("tax_percent") or 0)
    tax_unit = float(b.get("tax_amount") or 0) / booking_pax
    tax_amount = round(tax_unit * pax_count)
    total = subtotal - discount_amount + tax_amount
    amount = subtotal
    doc = {"invoice_number": number, "booking_id": bid, "booking_number": b.get("booking_number"),
           "customer_id": b.get("customer_id"), "customer_name": b.get("customer_name"),
           "package_id": b.get("package_id"), "package_name": b.get("package_name"),
           "pax": pax_count, "per_pax_price": per_pax,
           "amount": amount, "subtotal": subtotal,
           "discount_amount": discount_amount, "discount_percent": disc_pct,
           "tax_percent": tax_pct, "tax_amount": tax_amount, "total": total,
           "paid_amount": 0, "outstanding": total, "due_date": due_date, "status": "Unpaid",
           "sales_pic_id": b.get("sales_pic_id"), "sales_pic_name": b.get("sales_pic_name"), "branch": b.get("branch", ""),
           "terms": (await db.packages.find_one({"_id": ObjectId(b["package_id"])}) or {}).get("terms", ""),
           "created_at": now_iso(), "created_by": user["name"]}
    doc.update(await tax_snapshot(now_iso()[:10], subtotal))
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


async def _booking_invoice_amounts(b, pax_count=None):
    """Nominal invoice = per_pax_price paket x jumlah peserta terdaftar (fallback booking.pax)."""
    booking_pax = max(int(b.get("pax") or 1), 1)
    if pax_count is None:
        tc = await db.travelers.count_documents({"booking_id": str(b["_id"])})
        pax_count = tc if tc > 0 else booking_pax
    pax_count = max(int(pax_count), 1)
    per_pax = float(b.get("per_pax_price") or 0)
    # Harga tiered otomatis: paket PRIVATE mengikuti bracket jumlah peserta terbaru
    pkg = await db.packages.find_one({"_id": ObjectId(b["package_id"])}) if ObjectId.is_valid(b.get("package_id") or "") else None
    if pkg and pkg.get("sub_category") == "PRIVATE":
        tiered = compute_pax_price(pkg, pax_count, b.get("room_type"))
        if tiered > 0:
            per_pax = float(tiered)
    addon_total = sum(float(a.get("amount") or 0) for a in (b.get("addons") or []))
    gross = per_pax * pax_count
    subtotal = gross + addon_total
    disc_pct = float(b.get("discount_percent") or 0)
    discount_amount = round(subtotal * disc_pct / 100) if disc_pct > 0 else float(b.get("discount_amount") or 0)
    tax_pct = float(b.get("tax_percent") or 0)
    tax_unit = float(b.get("tax_amount") or 0) / booking_pax
    tax_amount = round(tax_unit * pax_count)
    total = subtotal - discount_amount + tax_amount
    return {"pax": pax_count, "per_pax_price": per_pax, "amount": subtotal, "subtotal": subtotal,
            "discount_amount": discount_amount, "discount_percent": disc_pct,
            "tax_percent": tax_pct, "tax_amount": tax_amount, "total": total}


class BulkPicReassign(BaseModel):
    customer_ids: List[str]
    sales_pic_id: str


@api_router.post("/customers/bulk-reassign-pic")
async def bulk_reassign_pic(body: BulkPicReassign, request: Request, user: dict = Depends(require_role("super_admin"))):
    pic = await db.users.find_one({"_id": ObjectId(body.sales_pic_id)}) if ObjectId.is_valid(body.sales_pic_id) else None
    if not pic or pic.get("is_deleted"):
        raise HTTPException(status_code=400, detail="Sales PIC tidak ditemukan")
    ids = [ObjectId(c) for c in body.customer_ids if ObjectId.is_valid(c)]
    if not ids:
        raise HTTPException(status_code=400, detail="Tidak ada customer dipilih")
    custs = await db.customers.find({"_id": {"$in": ids}}).to_list(5000)
    count = 0
    for c in custs:
        if str(c.get("sales_pic_id") or "") == str(pic["_id"]):
            continue
        await db.customers.update_one({"_id": c["_id"]}, {"$set": {
            "sales_pic_id": str(pic["_id"]), "sales_pic_name": pic.get("name"),
            "branch": pic.get("branch", c.get("branch", ""))}})
        await log_activity(str(c["_id"]), None, "pic_change",
                           f"PIC Sales diganti (massal): {c.get('sales_pic_name') or '—'} → {pic.get('name')}",
                           f"Diubah oleh {user['name']}", user)
        count += 1
    await log_audit(user, "customer", "bulk_reassign_pic", request,
                    new={"count": count, "sales_pic_id": str(pic["_id"]), "sales_pic_name": pic.get("name")})
    return {"reassigned": count, "sales_pic_name": pic.get("name")}


@api_router.put("/invoices/{iid}")
async def update_invoice(iid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    inv = await db.invoices.find_one({"_id": ObjectId(iid)}) if ObjectId.is_valid(iid) else None
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    body = body or {}
    old_per_pax = float(inv.get("per_pax_price") or 0)
    old_pax = max(int(inv.get("pax") or 1), 1)
    addon_component = max(float(inv.get("subtotal") or inv.get("amount") or 0) - old_per_pax * old_pax, 0)
    per_pax = float(body.get("per_pax_price", old_per_pax) or 0)
    pax = max(int(body.get("pax", old_pax) or 1), 1)
    subtotal = per_pax * pax + addon_component
    discount_amount = float(body.get("discount_amount", inv.get("discount_amount") or 0) or 0)
    tax_amount = float(body.get("tax_amount", inv.get("tax_amount") or 0) or 0)
    total = subtotal - discount_amount + tax_amount
    disc_pct = round(discount_amount / subtotal * 100, 2) if subtotal else 0.0
    upd = {"due_date": body.get("due_date", inv.get("due_date")), "pax": pax, "per_pax_price": per_pax,
           "subtotal": subtotal, "amount": subtotal, "discount_amount": discount_amount,
           "discount_percent": disc_pct, "tax_amount": tax_amount, "total": total}
    if body.get("notes") is not None:
        upd["notes"] = body.get("notes")
    await db.invoices.update_one({"_id": ObjectId(iid)}, {"$set": upd})
    await _recompute_invoice_status(iid)
    await log_audit(user, "invoice", "update", request, record_id=iid,
                    old={"total": inv.get("total")}, new={"total": total})
    inv2 = await db.invoices.find_one({"_id": ObjectId(iid)})
    return serialize(inv2)


@api_router.delete("/invoices/{iid}")
async def delete_invoice(iid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    inv = await db.invoices.find_one({"_id": ObjectId(iid)}) if ObjectId.is_valid(iid) else None
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    pays = await db.payments.count_documents({"invoice_id": iid, "status": {"$ne": "VOID"}})
    if pays > 0 or float(inv.get("paid_amount") or 0) > 0:
        raise HTTPException(status_code=400, detail="Invoice memiliki pembayaran. VOID pembayaran terlebih dahulu sebelum menghapus.")
    await db.invoices.delete_one({"_id": ObjectId(iid)})
    await log_audit(user, "invoice", "delete", request, record_id=iid, old={"invoice_number": inv.get("invoice_number"), "total": inv.get("total")})
    return {"ok": True, "deleted": inv.get("invoice_number")}


@api_router.post("/invoices/{iid}/regenerate")
async def regenerate_invoice(iid: str, request: Request, user: dict = Depends(require_permission("invoice.manage"))):
    inv = await db.invoices.find_one({"_id": ObjectId(iid)}) if ObjectId.is_valid(iid) else None
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    b = await db.bookings.find_one({"_id": ObjectId(inv["booking_id"])}) if ObjectId.is_valid(inv.get("booking_id") or "") else None
    if not b:
        raise HTTPException(status_code=400, detail="Booking sumber tidak ditemukan")
    amounts = await _booking_invoice_amounts(b)
    await db.invoices.update_one({"_id": ObjectId(iid)}, {"$set": amounts})
    await _recompute_invoice_status(iid)
    await log_audit(user, "invoice", "regenerate", request, record_id=iid,
                    old={"total": inv.get("total"), "pax": inv.get("pax")},
                    new={"total": amounts["total"], "pax": amounts["pax"]})
    inv2 = await db.invoices.find_one({"_id": ObjectId(iid)})
    return serialize(inv2)


@api_router.post("/bookings/{bid}/invoices/regenerate-all")
async def regenerate_all_invoices(bid: str, request: Request, user: dict = Depends(require_permission("invoice.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)}) if ObjectId.is_valid(bid) else None
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    invs = await db.invoices.find({"booking_id": bid}).to_list(500)
    amounts = await _booking_invoice_amounts(b)
    updated = 0
    for inv in invs:
        await db.invoices.update_one({"_id": inv["_id"]}, {"$set": amounts})
        await _recompute_invoice_status(str(inv["_id"]))
        updated += 1
    await log_audit(user, "invoice", "regenerate_all", request, record_id=bid, new={"updated": updated, "pax": amounts["pax"]})
    return {"updated": updated, "pax": amounts["pax"], "total_each": amounts["total"]}


@api_router.post("/bookings/{bid}/sync-pax")
async def sync_booking_pax(bid: str, request: Request, user: dict = Depends(require_permission("booking.manage"))):
    b = await db.bookings.find_one({"_id": ObjectId(bid)}) if ObjectId.is_valid(bid) else None
    if not b:
        raise HTTPException(status_code=404, detail="Booking not found")
    tc = await db.travelers.count_documents({"booking_id": bid, "cancelled": {"$ne": True}})
    if tc <= 0:
        raise HTTPException(status_code=400, detail="Belum ada peserta terdaftar")
    amounts = await _booking_invoice_amounts(b, pax_count=tc)
    old_pax = b.get("pax")
    await db.bookings.update_one({"_id": ObjectId(bid)}, {"$set": {
        "pax": amounts["pax"], "per_pax_price": amounts["per_pax_price"],
        "subtotal": amounts["subtotal"], "discount_amount": amounts["discount_amount"],
        "discount_percent": amounts["discount_percent"], "tax_amount": amounts["tax_amount"],
        "tax_percent": amounts["tax_percent"], "total": amounts["total"]}})
    invs = await db.invoices.find({"booking_id": bid}).to_list(500)
    for inv in invs:
        await db.invoices.update_one({"_id": inv["_id"]}, {"$set": amounts})
        await _recompute_invoice_status(str(inv["_id"]))
    await log_audit(user, "booking", "sync_pax", request, record_id=bid, old={"pax": old_pax}, new={"pax": amounts["pax"], "invoices_updated": len(invs)})
    return {"pax": amounts["pax"], "per_pax_price": amounts["per_pax_price"], "total": amounts["total"], "invoices_updated": len(invs)}


@api_router.post("/approval-center/action/{source}/{aid}")
async def approval_center_action(source: str, aid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    action = (body.get("action") or "").upper()
    reason = (body.get("reason") or body.get("comment") or "").strip()
    if action not in ("APPROVE", "REJECT", "REQUEST_REVISION"):
        raise HTTPException(status_code=400, detail="Invalid action")
    if action in ("REJECT", "REQUEST_REVISION") and not reason:
        raise HTTPException(status_code=400, detail="Reason wajib diisi untuk Reject / Request Revision")
    if source == "adjustment":
        d = await db.approvals.find_one({"_id": ObjectId(aid)}) if ObjectId.is_valid(aid) else None
        if not d:
            raise HTTPException(status_code=404, detail="Not found")
        new_status = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_REVISION": "REVISION"}[action]
        hist = d.get("history", [])
        hist.append({"user": user["name"], "role": user["role"], "action": action, "comment": reason, "at": now_iso()})
        await db.approvals.update_one({"_id": ObjectId(aid)}, {"$set": {"status": new_status, "decided_at": now_iso(), "history": hist}})
        await notify(f"Approval {new_status.title()}", f"{d.get('approval_number')} • {d.get('atype')}" + (f" — {reason}" if reason else ""),
                     "/approval-center", user_id=d.get("requested_by_id"), ntype="APPROVAL_RESULT", priority="normal")
        return serialize(await db.approvals.find_one({"_id": ObjectId(aid)}))
    if source == "commission":
        c = await _get_closing(aid)
        if not c:
            raise HTTPException(status_code=404, detail="Closing not found")
        if c.get("status") not in ("REVIEW", "CLOSED"):
            raise HTTPException(status_code=400, detail="Approval komisi hanya untuk closing REVIEW/CLOSED")
        decision = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_REVISION": "REVISION"}[action]
        await db.commission_closings.update_one({"period": aid}, {"$set": {
            "sa_approval": decision, "sa_approval_reason": reason,
            "sa_approval_by": user["name"], "sa_approval_at": now_iso()}})
        await log_audit(user, "commission", "sa_approval", request, record_id=aid, new={"decision": decision, "reason": reason})
        return serialize(await _get_closing(aid))
    if source == "cancellation":
        return await approve_cancellation(aid, {"action": action, "reason": reason}, request, user)
    if source == "refund":
        return await approve_refund(aid, {"action": action, "reason": reason}, request, user)
    raise HTTPException(status_code=400, detail="Sumber approval ini harus diproses di halaman terkait")


@api_router.get("/reports/pic-changes")
async def report_pic_changes(frm: Optional[str] = None, to: Optional[str] = None, user: dict = Depends(require_role("super_admin"))):
    acts = await db.lead_activities.find({"type": "pic_change"}).sort("timestamp", -1).to_list(2000)
    cust_ids = [ObjectId(a["customer_id"]) for a in acts if a.get("customer_id") and ObjectId.is_valid(a["customer_id"])]
    cust_map = {}
    if cust_ids:
        async for c in db.customers.find({"_id": {"$in": cust_ids}}):
            cust_map[str(c["_id"])] = c.get("full_name") or c.get("customer_code") or "—"
    rows = []
    for a in acts:
        ts = a.get("timestamp") or ""
        if (frm and ts[:10] < frm) or (to and ts[:10] > to):
            continue
        title = a.get("title") or ""
        change = title.split(":", 1)[1].strip() if ":" in title else title
        rows.append({
            "date": ts.replace("T", " ")[:16],
            "customer": cust_map.get(str(a.get("customer_id")), "—"),
            "change": change,
            "mode": "Massal" if "massal" in title.lower() else "Satuan",
            "by": a.get("user_name") or "—",
        })
    return {"title": "Laporan Perpindahan PIC Sales", "count": len(rows), "rows": rows}


@api_router.get("/invoices/{iid}/pdf")
async def invoice_pdf(iid: str, authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    await _recompute_invoice_status(iid)
    inv = await db.invoices.find_one({"_id": ObjectId(iid)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    pdf, name = await _render_invoice_pdf(inv)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={name}.pdf"})


# ---------- Payments ----------
class PaymentCreate(BaseModel):
    payment_date: str
    amount: float
    payment_method: Optional[str] = ""
    bank: Optional[str] = ""
    reference_number: Optional[str] = ""
    notes: Optional[str] = ""
    attachment_url: Optional[str] = ""


@api_router.get("/invoices/{iid}/payments")
async def list_invoice_payments(iid: str, user: dict = Depends(require_permission("payment.view"))):
    pays = await db.payments.find({"invoice_id": iid}).sort("created_at", -1).to_list(500)
    return [serialize(p) for p in pays]


@api_router.post("/invoices/{iid}/payments")
async def record_payment(iid: str, body: PaymentCreate, request: Request, user: dict = Depends(require_permission("payment.manage"))):
    inv = await db.invoices.find_one({"_id": ObjectId(iid)})
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    amt = float(body.amount or 0)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Jumlah pembayaran harus lebih dari 0")
    existing = await db.payments.find({"invoice_id": iid, "status": {"$ne": "VOID"}}).to_list(500)
    paid_before = sum(float(p.get("amount") or 0) for p in existing)
    inv_total = float(inv.get("total") or inv.get("amount") or 0)
    outstanding = round(inv_total - paid_before, 2)
    if amt > outstanding + 0.01:
        raise HTTPException(status_code=400, detail=f"Payment Rp {amt:,.0f} melebihi outstanding Rp {outstanding:,.0f}. Gunakan adjustment workflow.")
    doc = {**body.model_dump(), "invoice_id": iid, "invoice_number": inv.get("invoice_number"),
           "booking_id": inv.get("booking_id"), "status": "ACTIVE", "recorded_by": user["name"], "created_at": now_iso()}
    res = await db.payments.insert_one(doc)
    status = await _recompute_invoice_status(iid)
    await log_audit(user, "payment", "record", request, record_id=str(res.inserted_id), new={"amount": body.amount, "invoice_status": status})
    await notify("New Payment Recorded", f"{inv.get('invoice_number', '')} — Rp {body.amount}", link="/accounting", role="accounting", ntype="NEW_PAYMENT", priority="high")
    if inv.get("sales_pic_id"):
        await notify("Payment Received", f"{inv.get('invoice_number', '')} — Rp {body.amount}",
                     link=f"/crm/{inv.get('customer_id')}" if inv.get("customer_id") else "/accounting",
                     user_id=inv.get("sales_pic_id"), ntype="PAYMENT_RECEIVED", priority="normal")
    return serialize(await db.payments.find_one({"_id": res.inserted_id}))


@api_router.post("/payments/{pid}/void")
async def void_payment(pid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    reason = ((body or {}).get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Reason is required to void a payment")
    p = await db.payments.find_one({"_id": ObjectId(pid)})
    if not p:
        raise HTTPException(status_code=404, detail="Payment not found")
    if p.get("status") == "VOID":
        raise HTTPException(status_code=400, detail="Payment already voided")
    await db.payments.update_one({"_id": ObjectId(pid)}, {"$set": {"status": "VOID", "void_by": user["name"], "void_at": now_iso(), "void_reason": reason}})
    status = await _recompute_invoice_status(p["invoice_id"]) if p.get("invoice_id") else None
    await log_audit(user, "payment", "void", request, record_id=pid, old={"amount": p.get("amount"), "status": "ACTIVE"}, new={"status": "VOID", "invoice_status": status}, reason=reason)
    return {"message": "Payment voided", "status": "VOID", "invoice_status": status}


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
TAX_TYPES = ["PPN", "PPh21", "PPh23", "OTHER"]
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


# ---------- PPN Configuration (versioned) ----------
class PPNConfigModel(BaseModel):
    config_name: str
    tax_type: str = "PPN"
    tax_rate: float = 0
    dpp_percentage: float = 100
    effective_from: str = ""
    effective_until: Optional[str] = ""
    status: str = "ACTIVE"
    description: Optional[str] = ""


@api_router.get("/ppn-configurations")
async def list_ppn_configs(user: dict = Depends(require_permission("tax.view"))):
    docs = await db.ppn_configurations.find({}).sort("effective_from", -1).to_list(500)
    return [serialize(d) for d in docs]


@api_router.post("/ppn-configurations")
async def create_ppn_config(body: PPNConfigModel, request: Request, user: dict = Depends(require_permission("tax.manage"))):
    doc = {**body.model_dump(), "created_at": now_iso(), "created_by": user["name"]}
    res = await db.ppn_configurations.insert_one(doc)
    await log_audit(user, "tax", "create_ppn_config", request, record_id=str(res.inserted_id), new={**body.model_dump()})
    return serialize(await db.ppn_configurations.find_one({"_id": res.inserted_id}))


@api_router.put("/ppn-configurations/{cid}")
async def update_ppn_config(cid: str, body: dict, request: Request, user: dict = Depends(require_permission("tax.manage"))):
    old = await db.ppn_configurations.find_one({"_id": ObjectId(cid)})
    if not old:
        raise HTTPException(status_code=404, detail="PPN configuration not found")
    reason = (body or {}).get("reason", "")
    if not reason:
        raise HTTPException(status_code=400, detail="Reason wajib diisi untuk perubahan konfigurasi pajak (audit).")
    fields = {k: body[k] for k in ["config_name", "tax_type", "tax_rate", "dpp_percentage", "effective_from", "effective_until", "status", "description"] if k in (body or {})}
    await db.ppn_configurations.update_one({"_id": ObjectId(cid)}, {"$set": fields})
    await log_audit(user, "tax", "update_ppn_config", request, record_id=cid, old=serialize(old), new={**fields, "reason": reason})
    return serialize(await db.ppn_configurations.find_one({"_id": ObjectId(cid)}))


@api_router.delete("/ppn-configurations/{cid}")
async def deactivate_ppn_config(cid: str, request: Request, user: dict = Depends(require_permission("tax.manage"))):
    old = await db.ppn_configurations.find_one({"_id": ObjectId(cid)})
    if not old:
        raise HTTPException(status_code=404, detail="PPN configuration not found")
    await db.ppn_configurations.update_one({"_id": ObjectId(cid)}, {"$set": {"status": "INACTIVE"}})
    await log_audit(user, "tax", "deactivate_ppn_config", request, record_id=cid, old=serialize(old), new={"status": "INACTIVE", "reason": "deactivated"})
    return {"ok": True}


@api_router.get("/tax-transactions")
async def tax_transactions(frm: Optional[str] = None, to: Optional[str] = None, user: dict = Depends(require_permission("tax.view"))):
    invs = await db.invoices.find({}).to_list(20000)
    rows = []
    for i in invs:
        if not _in_range(i.get("created_at"), frm, to):
            continue
        rate = i.get("tax_rate") if i.get("tax_rate") is not None else i.get("tax_percent")
        dpp = i.get("dpp_amount") if i.get("dpp_amount") is not None else i.get("amount")
        rows.append({"id": str(i["_id"]), "invoice_number": i.get("invoice_number"),
                     "transaction_date": (i.get("created_at") or "")[:10],
                     "customer_name": i.get("customer_name"), "package_name": i.get("package_name"),
                     "tax_type": i.get("tax_type") or "PPN", "tax_rate": float(rate or 0),
                     "dpp": float(dpp or 0), "tax_amount": float(i.get("tax_amount") or 0),
                     "total": float(i.get("total") or 0), "tax_config_version": i.get("tax_config_version") or "-"})
    rows.sort(key=lambda r: r["transaction_date"], reverse=True)
    return rows


@api_router.get("/tax-dashboard")
async def tax_dashboard(user: dict = Depends(require_permission("tax.view"))):
    from datetime import date
    invs = await db.invoices.find({}).to_list(20000)
    total_dpp = sum(float(i.get("dpp_amount") if i.get("dpp_amount") is not None else i.get("amount") or 0) for i in invs)
    total_ppn = sum(float(i.get("tax_amount") or 0) for i in invs)
    taxable = sum(float(i.get("amount") or 0) for i in invs if float(i.get("tax_amount") or 0) > 0)
    non_taxable = sum(float(i.get("amount") or 0) for i in invs if float(i.get("tax_amount") or 0) <= 0)
    by_type = {}
    for i in invs:
        t = i.get("tax_type") or "PPN"
        by_type[t] = by_type.get(t, 0) + float(i.get("tax_amount") or 0)
    td = date.fromisoformat(today_str())
    months = []
    y, m = td.year, td.month
    for k in range(5, -1, -1):
        mm, yy = m - k, y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append(f"{yy:04d}-{mm:02d}")
    by_month = [{"month": mo, "value": sum(float(i.get("tax_amount") or 0) for i in invs if (i.get("created_at") or "")[:7] == mo)} for mo in months]
    ac = await resolve_ppn_config(now_iso()[:10])
    active_config = None
    if ac:
        active_config = {"config_name": ac.get("config_name"), "tax_type": ac.get("tax_type"),
                         "tax_rate": ac.get("tax_rate"), "dpp_percentage": ac.get("dpp_percentage"),
                         "effective_from": ac.get("effective_from"), "effective_until": ac.get("effective_until")}
    return {"active_config": active_config, "total_dpp": total_dpp, "total_ppn": total_ppn,
            "taxable": taxable, "non_taxable": non_taxable, "transaction_count": len(invs),
            "by_type": [{"type": k, "value": v} for k, v in by_type.items()], "by_month": by_month}


@api_router.get("/tax-reports")
async def tax_reports(frm: Optional[str] = None, to: Optional[str] = None, user: dict = Depends(require_permission("tax.view"))):
    return await report_tax(frm, to)


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
    amt = float(body.amount or 0)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Jumlah refund harus lebih dari 0")
    if body.booking_id:
        pays = await _booking_payments(body.booking_id)
        paid = sum(float(p.get("amount") or 0) for p in pays if p.get("status") != "VOID")
        prev = await db.refunds.find({"booking_id": body.booking_id, "status": {"$ne": "REJECTED"}}).to_list(500)
        refunded = sum(float(r.get("amount") or 0) for r in prev)
        refundable = round(paid - refunded, 2)
        if amt > refundable + 0.01:
            raise HTTPException(status_code=400, detail=f"Refund Rp {amt:,.0f} melebihi refundable Rp {refundable:,.0f} (dibayar {paid:,.0f} − sudah direfund {refunded:,.0f}).")
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


# ================= PHASE 8G — Financial & Management Reports =================
async def _pkg_maps():
    pkgs = await db.packages.find({}).to_list(5000)
    pmap = {str(p["_id"]): {"product_type": norm_type(p.get("product_type") or ""),
            "name": p.get("name") or p.get("package_name") or "",
            "destination": p.get("destination") or p.get("destination_name") or ""} for p in pkgs}
    costs = await db.package_costs.find({}).to_list(5000)
    cmap = {str(c.get("package_id")): c for c in costs}
    return pmap, cmap


def _pct(part, whole):
    return round(part / whole * 100, 1) if whole else 0


@api_router.get("/mgmt-reports/filters")
async def rpt_filters(user: dict = Depends(get_current_user)):
    pmap, _ = await _pkg_maps()
    packages = [{"id": k, "name": v["name"], "product_type": v["product_type"], "destination": v.get("destination", "")} for k, v in pmap.items()]
    sales = []
    if user["role"] in ("accounting", "super_admin"):
        sales = [{"id": str(u["_id"]), "name": u.get("name")} for u in await db.users.find({"role": "sales"}).to_list(500)]
    dests = sorted({v.get("destination", "") for v in pmap.values() if v.get("destination")})
    return {"packages": packages, "sales": sales, "product_types": ["TOUR", "UMROH", "UMROH_PLUS"], "destinations": dests, "tax_types": TAX_TYPES}


@api_router.get("/mgmt-reports/profit-loss")
async def rpt_profit_loss(frm: Optional[str] = None, to: Optional[str] = None, product_type: Optional[str] = None,
                          package_id: Optional[str] = None, destination: Optional[str] = None,
                          user: dict = Depends(require_role("accounting", "super_admin"))):
    pmap, cmap = await _pkg_maps()
    bmap = {str(b["_id"]): b for b in await db.bookings.find({}).to_list(20000)}
    invs = [i for i in await db.invoices.find({}).to_list(20000) if _in_range(i.get("created_at"), frm, to)]

    def inv_pid(i):
        b = bmap.get(str(i.get("booking_id") or ""))
        return str((b or {}).get("package_id") or i.get("package_id") or "")

    def keep(pid):
        if package_id and pid != package_id:
            return False
        if product_type and pmap.get(pid, {}).get("product_type", "") != product_type.upper():
            return False
        if destination and (pmap.get(pid, {}).get("destination", "") or "").lower() != destination.lower():
            return False
        return True
    invs = [i for i in invs if keep(inv_pid(i))]
    tour_rev = sum(float(i.get("total") or 0) for i in invs if pmap.get(inv_pid(i), {}).get("product_type") == "TOUR")
    umrah_rev = sum(float(i.get("total") or 0) for i in invs if pmap.get(inv_pid(i), {}).get("product_type") in ("UMROH", "UMROH_PLUS"))
    total_rev_all = sum(float(i.get("total") or 0) for i in invs)
    other_rev = total_rev_all - tour_rev - umrah_rev
    revenue = total_rev_all
    hpp = {"flight": 0, "hotel": 0, "visa": 0, "transport": 0, "supplier": 0, "other": 0}
    for b in bmap.values():
        if b.get("status") == "CANCELLED" or not _in_range(b.get("created_at"), frm, to):
            continue
        pid = str(b.get("package_id") or "")
        if not keep(pid):
            continue
        c = cmap.get(pid)
        if not c:
            continue
        pax = int(b.get("pax") or 0)
        comps = c.get("components") or {}
        per_pax_total = float(c.get("total_cost") or c.get("cost_per_pax") or 0)
        used = 0
        for key in ("flight", "hotel", "visa", "transport"):
            v = float(comps.get(key) or 0) * pax
            hpp[key] += v
            used += v
        hpp["supplier"] += max(per_pax_total * pax - used, 0)
    hpp_total = sum(hpp.values())
    gross_profit = revenue - hpp_total
    exps = [e for e in await db.expenses.find({}).to_list(20000) if _in_range(e.get("date") or e.get("created_at"), frm, to)]
    opex = {"salary": 0, "marketing": 0, "office": 0, "transportation": 0, "commission": 0, "bank_fee": 0, "other": 0}
    for e in exps:
        cat = (e.get("category") or "").lower()
        amt = float(e.get("amount") or 0)
        if "market" in cat:
            opex["marketing"] += amt
        elif "operational" in cat or "office" in cat:
            opex["office"] += amt
        elif "transport" in cat:
            opex["transportation"] += amt
        elif "salary" in cat:
            opex["salary"] += amt
        elif "bank" in cat:
            opex["bank_fee"] += amt
        elif cat in ("flight", "hotel", "visa", "guide") or "commission" in cat or "refund" in cat:
            continue
        else:
            opex["other"] += amt
    comm = 0
    for ln in await db.commission_lines.find({}).to_list(20000):
        p = ln.get("period") or ""
        d = (p + "-01") if len(p) == 7 else p
        if _in_range(d, frm, to):
            comm += float(ln.get("final_commission") or 0)
    opex["commission"] = comm
    opex_total = sum(opex.values())
    net_profit = gross_profit - opex_total

    def L(label, amount):
        return {"label": label, "amount": amount, "percent": _pct(amount, revenue)}
    return {"title": "Laporan Laba Rugi", "period": {"from": frm, "to": to},
            "revenue": {"tour": L("Penjualan Tour", tour_rev), "umrah": L("Penjualan Umrah", umrah_rev), "other": L("Pendapatan Lainnya", other_rev), "total": L("Total Pendapatan", revenue)},
            "hpp": {"flight": L("Flight", hpp["flight"]), "hotel": L("Hotel", hpp["hotel"]), "visa": L("Visa", hpp["visa"]), "transport": L("Transport", hpp["transport"]), "supplier": L("Supplier Cost", hpp["supplier"]), "other": L("Other Direct Cost", hpp["other"]), "total": L("Total HPP", hpp_total)},
            "gross_profit": L("Gross Profit", gross_profit),
            "opex": {"salary": L("Salary", opex["salary"]), "marketing": L("Marketing", opex["marketing"]), "office": L("Office", opex["office"]), "transportation": L("Transportation", opex["transportation"]), "commission": L("Commission", opex["commission"]), "bank_fee": L("Bank Fee", opex["bank_fee"]), "other": L("Other Expense", opex["other"]), "total": L("Total Operating Expense", opex_total)},
            "net_profit": L("Net Profit", net_profit),
            "summary": {"revenue": revenue, "hpp": hpp_total, "gross_profit": gross_profit, "opex": opex_total, "net_profit": net_profit, "gross_margin": _pct(gross_profit, revenue), "net_margin": _pct(net_profit, revenue)}}


@api_router.get("/mgmt-reports/balance-sheet")
async def rpt_balance_sheet(as_of: Optional[str] = None, user: dict = Depends(require_role("accounting", "super_admin"))):
    ason = (as_of or today_str())[:10]

    def le(dt):
        return (dt or "")[:10] <= ason
    payments = [p for p in await db.payments.find({}).to_list(40000) if le(p.get("payment_date"))]
    expenses = [e for e in await db.expenses.find({}).to_list(20000) if le(e.get("date") or e.get("created_at"))]
    refunds = await db.refund_requests.find({}).to_list(10000)
    invoices = [i for i in await db.invoices.find({}).to_list(20000) if le(i.get("created_at"))]
    cash = sum(float(p.get("amount") or 0) for p in payments) - sum(float(e.get("amount") or 0) for e in expenses) - sum(float(r.get("refunded_amount") or 0) for r in refunds)
    ar = sum(float(i.get("outstanding") or 0) for i in invoices if float(i.get("outstanding") or 0) > 0)
    customer_deposit = sum(float(i.get("paid_amount") or 0) for i in invoices if i.get("status") != "Paid" and float(i.get("outstanding") or 0) > 0)
    tax_payable = sum(float(i.get("tax_amount") or 0) for i in invoices if float(i.get("outstanding") or 0) > 0)
    commission_payable = sum(float(c.get("final_commission") or 0) for c in await db.commission_lines.find({}).to_list(20000) if c.get("payment_status") != "PAID")
    pl = await rpt_profit_loss(frm=f"{ason[:4]}-01-01", to=ason, user=user)
    current_pl = pl["summary"]["net_profit"]
    assets_current = {"cash": cash, "bank": 0, "accounts_receivable": ar, "prepaid_expense": 0, "other_current": 0}
    assets_noncurrent = {"fixed_asset": 0, "accumulated_depreciation": 0, "other_asset": 0}
    total_assets = sum(assets_current.values()) + sum(assets_noncurrent.values())
    liabilities = {"accounts_payable": 0, "customer_deposit": customer_deposit, "tax_payable": tax_payable, "commission_payable": commission_payable, "other_payable": 0}
    total_liabilities = sum(liabilities.values())
    retained = total_assets - total_liabilities - current_pl
    equity = {"paid_in_capital": 0, "retained_earnings": retained, "current_year_pl": current_pl, "other_equity": 0}
    total_equity = sum(equity.values())
    diff = round(total_assets - (total_liabilities + total_equity))
    return {"title": "Neraca / Posisi Keuangan", "as_of": ason, "assets_current": assets_current,
            "assets_noncurrent": assets_noncurrent, "total_assets": total_assets, "liabilities": liabilities,
            "total_liabilities": total_liabilities, "equity": equity, "total_equity": total_equity,
            "balanced": abs(diff) < 1, "difference": diff}


@api_router.get("/mgmt-reports/cash-flow")
async def rpt_cash_flow(frm: Optional[str] = None, to: Optional[str] = None, user: dict = Depends(require_role("accounting", "super_admin"))):
    payments = await db.payments.find({}).to_list(40000)
    expenses = await db.expenses.find({}).to_list(20000)
    refunds = await db.refund_requests.find({}).to_list(10000)

    def pd(p):
        return (p.get("payment_date") or "")[:10]

    def ed(e):
        return (e.get("date") or e.get("created_at") or "")[:10]
    opening = 0
    if frm:
        opening = sum(float(p.get("amount") or 0) for p in payments if pd(p) < frm) - sum(float(e.get("amount") or 0) for e in expenses if ed(e) < frm)
    in_pay = sum(float(p.get("amount") or 0) for p in payments if _in_range(p.get("payment_date"), frm, to))
    pe = [e for e in expenses if _in_range(e.get("date") or e.get("created_at"), frm, to)]
    supplier = sum(float(e.get("amount") or 0) for e in pe if (e.get("category") or "").lower() in ("flight", "hotel", "visa", "transport", "guide"))
    tax = sum(float(e.get("amount") or 0) for e in pe if "tax" in (e.get("category") or "").lower())
    commp = sum(float(e.get("amount") or 0) for e in pe if "commission" in (e.get("category") or "").lower())
    opex = sum(float(e.get("amount") or 0) for e in pe) - supplier - tax - commp
    refund_out = sum(float(r.get("refunded_amount") or 0) for r in refunds if _in_range(r.get("refunded_at") or r.get("updated_at"), frm, to))
    cash_in = in_pay
    cash_out = supplier + opex + tax + commp + refund_out
    net = cash_in - cash_out
    return {"title": "Laporan Arus Kas", "period": {"from": frm, "to": to}, "opening_cash": opening,
            "operating": {"customer_payment": in_pay, "supplier_payment": -supplier, "operational_expense": -opex, "tax_payment": -tax, "commission_payment": -commp, "refund": -refund_out},
            "investing": {"asset_purchase": 0, "asset_sale": 0},
            "financing": {"capital_injection": 0, "loan": 0, "loan_repayment": 0, "other_financing": 0},
            "cash_in": cash_in, "cash_out": cash_out, "net_cash_flow": net, "ending_cash": opening + net}


@api_router.get("/mgmt-reports/sales-detail")
async def rpt_sales_detail(frm: Optional[str] = None, to: Optional[str] = None, product_type: Optional[str] = None,
                           package_id: Optional[str] = None, sales_id: Optional[str] = None, status: Optional[str] = None,
                           user: dict = Depends(get_current_user)):
    q = {}
    if user["role"] == "sales":
        q["sales_pic_id"] = user["_id"]
    elif sales_id and user["role"] == "super_admin":
        q["sales_pic_id"] = sales_id
    bks = [b for b in await db.bookings.find(q).sort("created_at", -1).to_list(20000) if _in_range(b.get("created_at"), frm, to)]
    pmap, _ = await _pkg_maps()
    invagg = {}
    for i in await db.invoices.find({}).to_list(20000):
        k = str(i.get("booking_id") or "")
        a = invagg.setdefault(k, {"paid": 0, "out": 0})
        a["paid"] += float(i.get("paid_amount") or 0)
        a["out"] += float(i.get("outstanding") or 0)
    rows = []
    tot = {"pax": 0, "gross": 0, "disc": 0, "net": 0, "paid": 0, "out": 0}
    for b in bks:
        pid = str(b.get("package_id") or "")
        pt = pmap.get(pid, {}).get("product_type", "")
        if product_type and pt != product_type.upper():
            continue
        if package_id and pid != package_id:
            continue
        if status and (b.get("status") or "") != status:
            continue
        gross = float(b.get("subtotal") or b.get("total") or 0)
        disc = float(b.get("discount") or b.get("discount_amount") or 0)
        net = float(b.get("total") or 0)
        inv = invagg.get(str(b["_id"]), {"paid": 0, "out": 0})
        rows.append({"booking_number": b.get("booking_number"), "date": (b.get("created_at") or "")[:10],
                     "customer": b.get("customer_name"), "sales": b.get("sales_pic_name"), "package": b.get("package_name"),
                     "product_type": pt, "destination": pmap.get(pid, {}).get("destination", ""), "departure": b.get("departure_date") or "",
                     "pax": int(b.get("pax") or 0), "selling_price": gross, "discount": disc, "net_sales": net,
                     "payment": inv["paid"], "outstanding": inv["out"], "status": b.get("status")})
        tot["pax"] += int(b.get("pax") or 0); tot["gross"] += gross; tot["disc"] += disc; tot["net"] += net; tot["paid"] += inv["paid"]; tot["out"] += inv["out"]
    return {"title": "Laporan Penjualan", "rows": rows, "summary": {"total_booking": len(rows), "total_pax": tot["pax"], "gross_sales": tot["gross"], "discount": tot["disc"], "net_sales": tot["net"], "paid": tot["paid"], "outstanding": tot["out"]}}


@api_router.get("/mgmt-reports/team-performance")
async def rpt_team_performance(frm: Optional[str] = None, to: Optional[str] = None, sales_id: Optional[str] = None,
                               user: dict = Depends(get_current_user)):
    susers = await db.users.find({"role": "sales"}).to_list(500)
    if user["role"] == "sales":
        susers = [u for u in susers if str(u["_id"]) == user["_id"]]
    elif sales_id and user["role"] == "super_admin":
        susers = [u for u in susers if str(u["_id"]) == sales_id]
    leads = await db.leads.find({}).to_list(20000)
    quotes = await db.quotations.find({}).to_list(20000)
    bks = [b for b in await db.bookings.find({}).to_list(20000) if b.get("status") != "CANCELLED" and _in_range(b.get("created_at"), frm, to)]
    fus = await db.follow_ups.find({}).to_list(20000)
    lines = await db.commission_lines.find({}).to_list(20000)
    today = today_str()
    rows = []
    for u in susers:
        sid = str(u["_id"])
        ul = [l for l in leads if l.get("sales_pic_id") == sid and _in_range(l.get("created_at"), frm, to)]
        uq = [x for x in quotes if x.get("sales_pic_id") == sid and _in_range(x.get("created_at"), frm, to)]
        conv = [x for x in uq if x.get("status") == "ACCEPTED" or x.get("converted_booking_id")]
        ub = [b for b in bks if b.get("sales_pic_id") == sid]
        ufu = [f for f in fus if f.get("sales_pic_id") == sid]
        overdue = [f for f in ufu if (f.get("status") not in ("DONE", "COMPLETED")) and f.get("due_date") and (f.get("due_date") or "")[:10] < today]
        rows.append({"sales_id": sid, "sales": u.get("name"), "leads": len(ul),
                     "qualified": len([l for l in ul if l.get("status") == "QUALIFIED"]), "quotations": len(uq),
                     "converted": len(conv), "bookings": len(ub), "pax": sum(int(b.get("pax") or 0) for b in ub),
                     "sales_value": sum(float(b.get("total") or 0) for b in ub), "conversion_rate": _pct(len(conv), len(uq)),
                     "follow_up": len(ufu), "overdue_follow_up": len(overdue),
                     "commission": sum(float(c.get("final_commission") or 0) for c in lines if c.get("sales_pic_id") == sid)})

    def top(k):
        return sorted(rows, key=lambda r: -r[k])[:5]
    return {"title": "Laporan Kinerja Tim Sales", "rows": rows,
            "rankings": {"by_revenue": top("sales_value"), "by_pax": top("pax"), "by_conversion": top("conversion_rate"), "by_booking": top("bookings")}}


@api_router.get("/mgmt-reports/tax-recap")
async def rpt_tax_recap(month: Optional[str] = None, year: Optional[str] = None, tax_type: str = "PPN",
                        user: dict = Depends(require_role("accounting", "super_admin"))):
    if year and month:
        prefix = f"{int(year):04d}-{int(month):02d}"
    elif year:
        prefix = f"{int(year):04d}"
    else:
        prefix = now_iso()[:7]
    invs = [i for i in await db.invoices.find({}).to_list(20000) if (i.get("created_at") or "").startswith(prefix)]
    res = {"title": "Rekapitulasi Pajak Bulanan", "period": prefix, "tax_type": tax_type}
    if tax_type == "PPN":
        taxable = sum(float(i.get("amount") or 0) for i in invs if float(i.get("tax_amount") or 0) > 0)
        dpp = sum(float(i.get("dpp_amount") if i.get("dpp_amount") is not None else i.get("amount") or 0) for i in invs if float(i.get("tax_amount") or 0) > 0)
        output = sum(float(i.get("tax_amount") or 0) for i in invs)
        res["ppn"] = {"taxable_sales": taxable, "dpp": dpp, "ppn_output": output, "ppn_input": 0, "ppn_payable": output, "tax_adjustment": 0}
        res["columns"] = ["Invoice", "Customer", "DPP", "Rate %", "PPN", "Config"]
        res["rows"] = [[i.get("invoice_number"), i.get("customer_name"),
                        float(i.get("dpp_amount") if i.get("dpp_amount") is not None else i.get("amount") or 0),
                        float(i.get("tax_rate") if i.get("tax_rate") is not None else i.get("tax_percent") or 0),
                        float(i.get("tax_amount") or 0), i.get("tax_config_version") or "-"] for i in invs]
        res["summary"] = {"taxable_sales": taxable, "dpp": dpp, "ppn_output": output, "ppn_payable": output}
    elif tax_type == "PPh21":
        res["columns"] = ["Employee", "Tax Base", "Tax Amount", "Withholding Date", "Status"]
        res["rows"] = []
        res["summary"] = {"tax_amount": 0}
    elif tax_type == "PPh23":
        res["columns"] = ["Vendor", "Transaction", "DPP", "Rate %", "Tax Amount", "Withholding Date", "Status"]
        res["rows"] = []
        res["summary"] = {"tax_amount": 0}
    else:
        res["columns"] = ["Description", "Amount"]
        res["rows"] = []
        res["summary"] = {"tax_amount": 0}
    return res


@api_router.get("/mgmt-reports/payable")
async def rpt_payable(frm: Optional[str] = None, to: Optional[str] = None, vendor: Optional[str] = None, status: Optional[str] = None,
                      user: dict = Depends(require_role("accounting", "super_admin"))):
    from datetime import date
    exps = [e for e in await db.expenses.find({}).sort("date", -1).to_list(20000) if _in_range(e.get("date") or e.get("created_at"), frm, to)]
    today = today_str()
    rows = []
    buckets = {"current": 0, "d1_30": 0, "d31_60": 0, "d61_90": 0, "d90": 0}
    tot_out = 0
    tot_amt = 0
    for e in exps:
        v = e.get("vendor") or "-"
        if vendor and vendor.lower() not in v.lower():
            continue
        amt = float(e.get("amount") or 0)
        paid = float(e.get("paid_amount") if e.get("paid_amount") is not None else amt)
        out = amt - paid
        st = "PAID" if out <= 0 else ("OVERDUE" if (e.get("due_date") or "")[:10] < today and e.get("due_date") else "UNPAID")
        if status and st != status:
            continue
        edt = (e.get("date") or e.get("created_at") or "")[:10]
        due = (e.get("due_date") or edt)[:10]
        try:
            days = (date.fromisoformat(today) - date.fromisoformat(due)).days if due else 0
        except Exception:
            days = 0
        if out > 0:
            if days <= 0:
                buckets["current"] += out
            elif days <= 30:
                buckets["d1_30"] += out
            elif days <= 60:
                buckets["d31_60"] += out
            elif days <= 90:
                buckets["d61_90"] += out
            else:
                buckets["d90"] += out
        aging = "Current" if days <= 0 else ("1-30" if days <= 30 else ("31-60" if days <= 60 else ("61-90" if days <= 90 else ">90")))
        rows.append({"vendor": v, "invoice": e.get("reference") or e.get("description") or "-", "invoice_date": edt,
                     "due_date": due, "amount": amt, "paid": paid, "outstanding": out, "aging": aging, "status": st})
        tot_out += out
        tot_amt += amt
    return {"title": "Laporan Utang Usaha", "rows": rows, "summary": {"total_payable": tot_amt, "total_outstanding": tot_out, **buckets}}


@api_router.get("/mgmt-reports/receivable-aging")
async def rpt_receivable_aging(frm: Optional[str] = None, to: Optional[str] = None, customer: Optional[str] = None,
                               sales_id: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
    from datetime import date
    invs = await db.invoices.find({}).to_list(20000)
    bmap = {str(b["_id"]): b for b in await db.bookings.find({}).to_list(20000)}
    today = today_str()
    rows = []
    buckets = {"current": 0, "d1_30": 0, "d31_60": 0, "d61_90": 0, "d90": 0}
    tot_out = 0
    overdue = 0
    for i in invs:
        if not _in_range(i.get("created_at"), frm, to):
            continue
        out = float(i.get("outstanding") or 0)
        if out <= 0:
            continue
        b = bmap.get(str(i.get("booking_id") or ""))
        sid = (b or {}).get("sales_pic_id")
        sname = (b or {}).get("sales_pic_name")
        if user["role"] == "sales" and sid != user["_id"]:
            continue
        if sales_id and user["role"] == "super_admin" and sid != sales_id:
            continue
        if customer and customer.lower() not in (i.get("customer_name") or "").lower():
            continue
        due = (i.get("due_date") or (i.get("created_at") or "")[:10])[:10]
        try:
            days = (date.fromisoformat(today) - date.fromisoformat(due)).days if due else 0
        except Exception:
            days = 0
        if days <= 0:
            buckets["current"] += out
        elif days <= 30:
            buckets["d1_30"] += out
        elif days <= 60:
            buckets["d31_60"] += out
        elif days <= 90:
            buckets["d61_90"] += out
        else:
            buckets["d90"] += out
        if days > 0:
            overdue += out
        aging = "Current" if days <= 0 else ("1-30" if days <= 30 else ("31-60" if days <= 60 else ("61-90" if days <= 90 else ">90")))
        st = i.get("status") or "Unpaid"
        if status and st != status:
            continue
        rows.append({"customer": i.get("customer_name"), "invoice": i.get("invoice_number"), "invoice_date": (i.get("created_at") or "")[:10],
                     "due_date": due, "total_invoice": float(i.get("total") or 0), "paid": float(i.get("paid_amount") or 0),
                     "outstanding": out, "aging": aging, "status": st, "sales": sname})
        tot_out += out
    return {"title": "Laporan Piutang Usaha", "rows": rows, "summary": {"total_receivable": tot_out, "overdue": overdue, **buckets}}


# ---------- Phase 8H: Report Export, Download & Validation ----------
ID_MONTHS = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
REPORT_META = {
    "profit-loss": ("Laporan_Laba_Rugi", True),
    "balance-sheet": ("Neraca_Bulanan", True),
    "cash-flow": ("Laporan_Arus_Kas", True),
    "sales-detail": ("Laporan_Penjualan", False),
    "team-performance": ("Laporan_Kinerja_Tim", False),
    "tax-recap": ("Rekap_Pajak", True),
    "payable": ("Laporan_Utang_Usaha", True),
    "receivable-aging": ("Laporan_Piutang_Usaha", False),
}


def _flatten_report(key, d):
    if key == "profit-loss":
        cols = ["Bagian", "Item", "Nominal", "%"]
        rows = []
        for k in ("tour", "umrah", "other", "total"):
            x = d["revenue"][k]
            rows.append(["Pendapatan", x["label"], x["amount"], x["percent"]])
        for k in ("flight", "hotel", "visa", "transport", "supplier", "other", "total"):
            x = d["hpp"][k]
            rows.append(["HPP", x["label"], x["amount"], x["percent"]])
        rows.append(["", d["gross_profit"]["label"], d["gross_profit"]["amount"], d["gross_profit"]["percent"]])
        for k in ("salary", "marketing", "office", "transportation", "commission", "bank_fee", "other", "total"):
            x = d["opex"][k]
            rows.append(["Operating Expense", x["label"], x["amount"], x["percent"]])
        rows.append(["", d["net_profit"]["label"], d["net_profit"]["amount"], d["net_profit"]["percent"]])
        s = d["summary"]
        summ = [["Revenue", s["revenue"]], ["HPP", s["hpp"]], ["Gross Profit", s["gross_profit"]], ["Operating Expense", s["opex"]], ["Net Profit", s["net_profit"]]]
        return cols, rows, summ
    if key == "balance-sheet":
        cols = ["Bagian", "Item", "Nominal"]
        rows = []
        for grp, lbl in (("assets_current", "Asset"), ("assets_noncurrent", "Asset"), ("liabilities", "Liability"), ("equity", "Equity")):
            for k, v in d[grp].items():
                rows.append([lbl, k.replace("_", " ").title(), v])
        summ = [["Total Asset", d["total_assets"]], ["Total Liability", d["total_liabilities"]], ["Total Equity", d["total_equity"]], ["Balanced", "YA" if d["balanced"] else "TIDAK"]]
        return cols, rows, summ
    if key == "cash-flow":
        cols = ["Aktivitas", "Item", "Nominal"]
        rows = []
        for grp, lbl in (("operating", "Operating"), ("investing", "Investing"), ("financing", "Financing")):
            for k, v in d[grp].items():
                rows.append([lbl, k.replace("_", " ").title(), v])
        summ = [["Opening Cash", d["opening_cash"]], ["Cash In", d["cash_in"]], ["Cash Out", d["cash_out"]], ["Net Cash Flow", d["net_cash_flow"]], ["Ending Cash", d["ending_cash"]]]
        return cols, rows, summ
    if key == "sales-detail":
        cols = ["Booking", "Date", "Customer", "Sales", "Package", "Type", "Departure", "Pax", "Selling", "Discount", "Net", "Paid", "Outstanding", "Status"]
        rows = [[r["booking_number"], r["date"], r["customer"], r["sales"], r["package"], r["product_type"], r["departure"], r["pax"], r["selling_price"], r["discount"], r["net_sales"], r["payment"], r["outstanding"], r["status"]] for r in d["rows"]]
        s = d["summary"]
        summ = [["Total Booking", s["total_booking"]], ["Total Pax", s["total_pax"]], ["Gross Sales", s["gross_sales"]], ["Net Sales", s["net_sales"]], ["Paid", s["paid"]], ["Outstanding", s["outstanding"]]]
        return cols, rows, summ
    if key == "team-performance":
        cols = ["Sales", "Leads", "Qualified", "Quotations", "Converted", "Bookings", "Pax", "Sales Value", "Conversion %", "Follow Up", "Overdue FU", "Commission"]
        rows = [[r["sales"], r["leads"], r["qualified"], r["quotations"], r["converted"], r["bookings"], r["pax"], r["sales_value"], r["conversion_rate"], r["follow_up"], r["overdue_follow_up"], r["commission"]] for r in d["rows"]]
        summ = [["Total Sales (PIC)", len(d["rows"])], ["Total Booking", sum(r["bookings"] for r in d["rows"])], ["Total Pax", sum(r["pax"] for r in d["rows"])], ["Total Value", sum(r["sales_value"] for r in d["rows"])]]
        return cols, rows, summ
    if key == "tax-recap":
        cols = d.get("columns") or []
        rows = [list(r) for r in (d.get("rows") or [])]
        summ = [[k.replace("_", " ").title(), v] for k, v in (d.get("summary") or {}).items()]
        return cols, rows, summ
    if key == "payable":
        cols = ["Vendor", "Invoice", "Inv Date", "Due", "Amount", "Paid", "Outstanding", "Aging", "Status"]
        rows = [[r["vendor"], r["invoice"], r["invoice_date"], r["due_date"], r["amount"], r["paid"], r["outstanding"], r["aging"], r["status"]] for r in d["rows"]]
        s = d["summary"]
        summ = [["Total Payable", s["total_payable"]], ["Outstanding", s["total_outstanding"]], ["Current", s["current"]], [">90", s["d90"]]]
        return cols, rows, summ
    if key == "receivable-aging":
        cols = ["Customer", "Invoice", "Inv Date", "Due", "Total", "Paid", "Outstanding", "Aging", "Status", "Sales"]
        rows = [[r["customer"], r["invoice"], r["invoice_date"], r["due_date"], r["total_invoice"], r["paid"], r["outstanding"], r["aging"], r["status"], r["sales"]] for r in d["rows"]]
        s = d["summary"]
        summ = [["Total Receivable", s["total_receivable"]], ["Overdue", s["overdue"]], ["Current", s["current"]], [">90", s["d90"]]]
        return cols, rows, summ
    return [], [], []


def _validate_report(key, d, rows):
    try:
        if key == "sales-detail":
            return abs(sum(float(r[10]) for r in rows) - float(d["summary"]["net_sales"])) < 1
        if key == "receivable-aging":
            return abs(sum(float(r[6]) for r in rows) - float(d["summary"]["total_receivable"])) < 1
        if key == "payable":
            return abs(sum(float(r[6]) for r in rows) - float(d["summary"]["total_outstanding"])) < 1
        if key == "profit-loss":
            return abs((d["summary"]["revenue"] - d["summary"]["hpp"]) - d["summary"]["gross_profit"]) < 1
        if key == "balance-sheet":
            return bool(d.get("balanced"))
    except Exception:
        return True
    return True


def _num_or_money(v):
    return _money(v) if isinstance(v, (int, float)) else str(v)


def export_mgmt_file(fmt, company, meta, cols, rows, summ):
    from openpyxl.styles import Font, PatternFill
    fname = meta["fname"]
    if fmt == "csv":
        sio = StringIO()
        w = _csv.writer(sio)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)
        if summ:
            w.writerow([])
            for s in summ:
                w.writerow(s)
        return Response(content=sio.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={fname}.csv"})
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        _st = (meta["report_name"] or "Report")
        for _ch in "\\/*?:[]":
            _st = _st.replace(_ch, "-")
        ws.title = _st[:31]
        ws.append([company.get("company_name", "Safar Travel CRM")]); ws["A1"].font = Font(bold=True, size=14)
        ws.append([meta["report_name"]]); ws["A2"].font = Font(bold=True, size=12)
        ws.append([f"Periode: {meta['period']}"])
        ws.append([f"Generated: {meta['generated']}"])
        ws.append([f"Filter: {meta['filter']}"])
        ws.append([])
        hr = ws.max_row + 1
        ws.append(cols)
        for c in range(1, len(cols) + 1):
            cell = ws.cell(row=hr, column=c)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1D4ED8")
        for r in rows:
            ws.append([_fmt_cell(c) for c in r])
        if summ:
            ws.append([])
            ws.append(["TOTAL / SUMMARY"])
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
            for s in summ:
                ws.append([s[0], _fmt_cell(s[1])] + [str(x) for x in s[2:]])
        for col in ws.columns:
            ln = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max(ln + 2, 12), 42)
        bio = BytesIO()
        wb.save(bio)
        return Response(content=bio.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename={fname}.xlsx"})
    # pdf
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=14 * mm, rightMargin=14 * mm)
    styles = getSampleStyleSheet()
    small = ParagraphStyle("s8", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#475569"))
    el = []
    logo = _logo_flowable(company)
    head = []
    if logo:
        head.append(logo)
    head.append(Paragraph(f"<b>{company.get('company_name', 'Safar Travel CRM')}</b>", styles["Normal"]))
    right = [Paragraph(f"<b>{meta['report_name']}</b>", styles["Heading3"]),
             Paragraph(f"Periode: {meta['period']}", small),
             Paragraph(f"Generated: {meta['generated']}", small),
             Paragraph(f"Filter: {meta['filter']}", small)]
    el.append(Table([[head, right]], colWidths=[80 * mm, 90 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])))
    el.append(Spacer(1, 5 * mm))
    data = [cols] + [[_num_or_money(c) for c in r] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")])]))
    el.append(t)
    if summ:
        el.append(Spacer(1, 4 * mm))
        el.append(Paragraph("<b>Summary</b>", styles["Normal"]))
        st = Table([[str(s[0]), _num_or_money(s[1])] for s in summ], colWidths=[80 * mm, 55 * mm])
        st.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1"))]))
        el.append(st)

    def _pg(canvas, docx):
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawRightString(A4[0] - 14 * mm, 10 * mm, f"Halaman {docx.page}")
    doc.build(el, onFirstPage=_pg, onLaterPages=_pg)
    return Response(content=buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={fname}.pdf"})


async def _run_report_for_export(key, user, q):
    if key == "profit-loss":
        return await rpt_profit_loss(frm=q.get("frm"), to=q.get("to"), product_type=q.get("product_type"), package_id=q.get("package_id"), destination=q.get("destination"), user=user)
    if key == "balance-sheet":
        return await rpt_balance_sheet(as_of=q.get("as_of") or q.get("to"), user=user)
    if key == "cash-flow":
        return await rpt_cash_flow(frm=q.get("frm"), to=q.get("to"), user=user)
    if key == "sales-detail":
        return await rpt_sales_detail(frm=q.get("frm"), to=q.get("to"), product_type=q.get("product_type"), package_id=q.get("package_id"), sales_id=q.get("sales_id"), status=q.get("status"), user=user)
    if key == "team-performance":
        return await rpt_team_performance(frm=q.get("frm"), to=q.get("to"), sales_id=q.get("sales_id"), user=user)
    if key == "tax-recap":
        return await rpt_tax_recap(month=q.get("month"), year=q.get("year"), tax_type=q.get("tax_type") or "PPN", user=user)
    if key == "payable":
        return await rpt_payable(frm=q.get("frm"), to=q.get("to"), vendor=q.get("vendor"), status=q.get("status"), user=user)
    if key == "receivable-aging":
        return await rpt_receivable_aging(frm=q.get("frm"), to=q.get("to"), customer=q.get("customer"), sales_id=q.get("sales_id"), status=q.get("status"), user=user)
    raise HTTPException(status_code=404, detail="Report not found")


@api_router.get("/mgmt-reports/{key}/export")
async def export_mgmt_report(key: str, format: str = "xlsx", frm: Optional[str] = None, to: Optional[str] = None,
                             as_of: Optional[str] = None, product_type: Optional[str] = None, package_id: Optional[str] = None,
                             sales_id: Optional[str] = None, destination: Optional[str] = None, status: Optional[str] = None,
                             vendor: Optional[str] = None, customer: Optional[str] = None, month: Optional[str] = None,
                             year: Optional[str] = None, tax_type: Optional[str] = None,
                             authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    user = await user_from_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if key not in REPORT_META:
        raise HTTPException(status_code=404, detail="Report not found")
    rname, finance = REPORT_META[key]
    if finance and user["role"] not in ("accounting", "super_admin"):
        raise HTTPException(status_code=403, detail="403 Forbidden")
    q = {"frm": frm, "to": to, "as_of": as_of, "product_type": product_type, "package_id": package_id,
         "sales_id": sales_id, "destination": destination, "status": status, "vendor": vendor,
         "customer": customer, "month": month, "year": year, "tax_type": tax_type}
    d = await _run_report_for_export(key, user, q)
    cols, rows, summ = _flatten_report(key, d)
    if not _validate_report(key, d, rows):
        raise HTTPException(status_code=409, detail="Total laporan tidak konsisten dengan database. Export dibatalkan.")
    fmt = format if format in ("csv", "xlsx", "pdf") else "xlsx"
    b = await db.system_settings.find_one({}) or {}
    company = {"company_name": b.get("company_name") or "Safar Travel CRM", "logo": b.get("logo") or "",
               "address": b.get("address", ""), "phone": b.get("phone", ""), "email": b.get("email", "")}
    if month and year:
        period = f"{ID_MONTHS[int(month)]} {year}"
        pslug = f"{ID_MONTHS[int(month)]}_{year}"
    elif as_of or (key == "balance-sheet" and to):
        av = as_of or to or today_str()
        period, pslug = f"Per {av}", av
    elif frm or to:
        period = f"{frm or '...'} s/d {to or '...'}"
        pslug = f"{frm or 'all'}_{to or 'all'}"
    else:
        period, pslug = "Semua Periode", "All"
    gen = now_iso()[:10]
    fname = f"{rname}_{pslug}_{gen}".replace(" ", "_").replace("/", "-").replace(":", "-")
    filt = ", ".join(f"{k}={v}" for k, v in q.items() if v) or "-"
    meta = {"report_name": d.get("title") or rname.replace("_", " "), "period": period, "generated": gen, "filter": filt, "fname": fname}
    await db.report_exports.insert_one({"report_key": key, "report_name": meta["report_name"], "user_id": user["_id"],
                                        "user_name": user.get("name"), "format": fmt, "filter": filt, "period": period,
                                        "file_name": f"{fname}.{fmt}", "created_at": now_iso()})
    return export_mgmt_file(fmt, company, meta, cols, rows, summ)


@api_router.get("/report-exports")
async def list_report_exports(user: dict = Depends(get_current_user)):
    qq = {} if user["role"] in ("accounting", "super_admin") else {"user_id": user["_id"]}
    docs = await db.report_exports.find(qq).sort("created_at", -1).to_list(200)
    return [serialize(x) for x in docs]


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
    commission_method: str = "PER_PAX"
    effective_from: Optional[str] = ""
    effective_until: Optional[str] = ""
    calculation_basis: str = "PAID"
    tiers: List[dict] = []
    auto_sales: bool = False
    status: str = "ACTIVE"
    notes: Optional[str] = ""


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


def _next_month(period: str):
    y, m = int(period[:4]), int(period[5:7])
    m += 1
    if m > 12:
        m = 1
        y += 1
    return f"{y:04d}-{m:02d}"


def _current_month():
    n = datetime.now(timezone.utc)
    return f"{n.year:04d}-{n.month:02d}"


def _commission_status(closing, line=None):
    """Derive Phase 8E commission status for a line/booking given its closing."""
    if line and (line.get("payment_status") == "PAID"):
        return "PAID"
    if not closing:
        return "ELIGIBLE"
    st = closing.get("status")
    sa = closing.get("sa_approval", "PENDING")
    if st == "PAID":
        return "PAID"
    if sa == "REJECTED":
        return "REJECTED"
    if st in ("OPEN", "CALCULATING", "REVIEW"):
        return "PENDING CLOSING"
    if st == "CLOSED":
        if sa == "APPROVED":
            payout = closing.get("payout_month") or _next_month(closing["period"])
            return "PENDING PAYOUT" if _current_month() >= payout else "APPROVED"
        return "CLOSED"
    return "ELIGIBLE"


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
    dep_cache = {}
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
        dep_date = b.get("departure_date") or ""
        depid = str(b.get("departure_id") or "")
        if not dep_date and depid and ObjectId.is_valid(depid):
            if depid not in dep_cache:
                dep = await db.departures.find_one({"_id": ObjectId(depid)})
                dep_cache[depid] = (dep or {}).get("departure_date") or (dep or {}).get("date") or ""
            dep_date = dep_cache[depid]
        sid, sname = b.get("sales_pic_id"), b.get("sales_pic_name", "")
        for tid, tname in tlist:
            if (bid, tid) in claimed:
                continue
            grp = sales_map.setdefault(sid, {"name": sname, "groups": {}})
            g = grp["groups"].setdefault(chosen["_id"], {"scheme": chosen, "items": []})
            g["items"].append({"booking_id": bid, "booking_number": b.get("booking_number"),
                "customer_name": b.get("customer_name") or "", "traveler_id": tid, "traveler_name": tname,
                "package_name": b.get("package_name"), "product_type": product_type,
                "departure_date": dep_date, "basis_date": bdate, "full_payment_date": bdate,
                "scheme_id": chosen["_id"], "scheme_name": chosen.get("scheme_name"),
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
                              "commission_rate": rate, "commission_amount": rate, "tier": label,
                              "commission_month": period, "payout_month": _next_month(period)})
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
           "payout_month": _next_month(period), "sa_approval": "PENDING", "sa_approval_reason": "",
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
                  "payout_month": _next_month(period), "sa_approval": "PENDING", "sa_approval_reason": "",
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
    if new_status == "PAID":
        if c.get("status") != "CLOSED":
            raise HTTPException(status_code=400, detail="Payout hanya dapat diproses saat closing berstatus CLOSED.")
        if c.get("sa_approval") != "APPROVED":
            raise HTTPException(status_code=400, detail="Payout membutuhkan approval Super Admin (APPROVED).")
        payout = c.get("payout_month") or _next_month(period)
        if _current_month() < payout:
            raise HTTPException(status_code=400, detail=f"Payout baru dapat diproses pada {payout} (bulan setelah pembayaran lunas).")
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
    if c and c.get("status") == "PAID":
        raise HTTPException(status_code=400, detail="Closing sudah PAID, adjustment tidak diizinkan.")
    if c and c.get("status") == "CLOSED" and user["role"] != "super_admin":
        raise HTTPException(status_code=400, detail="Closing terkunci. Adjustment hanya oleh Super Admin saat approval.")
    adj = float((body or {}).get("adjustment", 0) or 0)
    final = float(ln.get("total_commission") or 0) + adj
    await db.commission_lines.update_one({"_id": ObjectId(line_id)},
        {"$set": {"adjustment": adj, "adjustment_notes": (body or {}).get("notes", ""), "final_commission": final}})
    tot = sum(float(x.get("final_commission") or 0) for x in await db.commission_lines.find({"period": ln["period"]}).to_list(2000))
    await db.commission_closings.update_one({"period": ln["period"]}, {"$set": {"total_commission": tot}})
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
    lines, live_items = await _compute_period(period, only_sales_id=user["_id"])
    current = lines[0] if lines else {"period": period, "total_pax": 0, "tier": "-",
                                      "commission_rate": 0, "total_commission": 0}
    closings = {c["period"]: c for c in await db.commission_closings.find({}).to_list(300)}
    stored = await db.commission_items.find({"sales_pic_id": user["_id"]}).to_list(5000)
    if period not in closings:
        stored = [it for it in stored if it.get("period") != period] + live_items
    by_booking = {}
    for it in stored:
        p = it.get("period")
        key = (p, it.get("booking_id"))
        row = by_booking.setdefault(key, {
            "period": p, "booking_id": it.get("booking_id"), "booking_number": it.get("booking_number"),
            "customer_name": it.get("customer_name") or "", "package_name": it.get("package_name"),
            "departure_date": it.get("departure_date") or "",
            "full_payment_date": it.get("full_payment_date") or it.get("basis_date") or "",
            "tier": it.get("tier"),
            "commission_rate": it.get("commission_rate") or it.get("commission_amount") or 0,
            "commission_month": it.get("commission_month") or p,
            "payout_month": it.get("payout_month") or _next_month(p), "pax": 0})
        row["pax"] += 1
    bookings = []
    for (p, _bid), row in by_booking.items():
        row["commission_amount"] = float(row["commission_rate"] or 0) * row["pax"]
        row["status"] = _commission_status(closings.get(p), None)
        bookings.append(row)
    bookings.sort(key=lambda r: (r["payout_month"], r["booking_number"] or ""), reverse=True)
    prev = []
    for ln in await db.commission_lines.find({"sales_pic_id": user["_id"]}).sort("period", -1).to_list(200):
        c = closings.get(ln["period"])
        if c and c.get("status") in ("APPROVED", "CLOSED", "PAID"):
            prev.append({**serialize(ln), "closing_status": c.get("status")})
    return {"current": current, "period": period, "bookings": bookings, "previous": prev}


@api_router.get("/commissions/master-packages")
async def commission_master_packages(user: dict = Depends(require_role("super_admin"))):
    pkgs = await db.packages.find({}).sort("name", 1).to_list(2000)
    out = []
    for p in pkgs:
        out.append({"id": str(p["_id"]),
                    "name": p.get("name") or p.get("package_name") or p.get("code") or "(untitled)",
                    "code": p.get("code") or p.get("package_code") or "",
                    "product_type": norm_type(p.get("product_type") or ""),
                    "status": p.get("status")})
    return out


@api_router.get("/commissions/pending-approval")
async def commission_pending_approval(user: dict = Depends(require_role("super_admin"))):
    docs = await db.commission_closings.find({"status": {"$in": ["REVIEW", "CLOSED"]}}).sort("period", -1).to_list(200)
    out = []
    for c in docs:
        lines = [serialize(x) for x in await db.commission_lines.find({"period": c["period"]}).sort("total_commission", -1).to_list(1000)]
        out.append({"closing": serialize(c), "lines": lines})
    return out


@api_router.get("/commissions/accounting-summary")
async def commission_accounting_summary(user: dict = Depends(require_permission("commission.manage"))):
    cm = _current_month()
    closings = await db.commission_closings.find({}).sort("period", -1).to_list(300)
    groups = {"current": [], "upcoming_payout": [], "pending_approval": [], "paid": []}
    for c in closings:
        period = c["period"]
        payout = c.get("payout_month") or _next_month(period)
        lines = await db.commission_lines.find({"period": period}).to_list(1000)
        total = sum(float(l.get("final_commission") or 0) for l in lines)
        row = {"period": period, "payout_month": payout, "status": c.get("status"),
               "sa_approval": c.get("sa_approval", "PENDING"), "total_commission": total,
               "total_pax": c.get("total_pax", 0), "lines": len(lines)}
        st = c.get("status")
        if st == "PAID":
            groups["paid"].append(row)
        elif st == "CLOSED" and c.get("sa_approval") != "APPROVED":
            groups["pending_approval"].append(row)
        elif st == "CLOSED" and c.get("sa_approval") == "APPROVED":
            groups["upcoming_payout"].append({**row, "payable_now": cm >= payout})
        else:
            groups["current"].append(row)
    return groups


@api_router.patch("/commissions/closings/{period}/approval")
async def set_closing_approval(period: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    c = await _get_closing(period)
    if not c:
        raise HTTPException(status_code=404, detail="Closing not found")
    decision = (body or {}).get("decision")
    reason = (body or {}).get("reason", "")
    if decision not in ("APPROVED", "REJECTED", "REVISION"):
        raise HTTPException(status_code=400, detail="decision must be APPROVED/REJECTED/REVISION")
    if decision in ("REJECTED", "REVISION") and not reason:
        raise HTTPException(status_code=400, detail="Reason wajib untuk Reject / Request Revision")
    if c.get("status") not in ("REVIEW", "CLOSED"):
        raise HTTPException(status_code=400, detail="Approval hanya untuk closing REVIEW/CLOSED")
    await db.commission_closings.update_one({"period": period}, {"$set": {
        "sa_approval": decision, "sa_approval_reason": reason,
        "sa_approval_by": user["name"], "sa_approval_at": now_iso()}})
    await log_audit(user, "commission", "sa_approval", request, record_id=period, new={"decision": decision, "reason": reason})
    return serialize(await _get_closing(period))



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


def _inbox_key(customer_id, whatsapp):
    return customer_id if customer_id else ("wa:" + (whatsapp or ""))


@api_router.get("/integrations/n8n/monitor")
async def n8n_monitor(user: dict = Depends(require_role("super_admin"))):
    today = today_str()
    convs = await db.conversations.find({}).to_list(8000)
    tc = [c for c in convs if (c.get("timestamp") or c.get("created_at") or "")[:10] == today]
    auto = await db.bookings.find({"booking_source": "AUTO SALES"}).sort("created_at", -1).to_list(3000)
    logs = await db.n8n_api_logs.find({}).sort("timestamp", -1).to_list(500)
    wf_raw = await db.n8n_logs.find({}).sort("created_at", -1).to_list(500)
    _lat = [float(l.get("processing_time_ms") or 0) for l in logs if l.get("processing_time_ms")]
    _avg_lat = round(sum(_lat) / len(_lat), 1) if _lat else 0
    _err_rate = round(100 * sum(1 for l in logs if not l.get("ok")) / len(logs), 1) if logs else 0
    _last_req = logs[0] if logs else None
    cfg = await _n8n_cfg()
    sysdoc = await db.system_settings.find_one({"key": "system"}) or {}
    sla_min = int((sysdoc.get("settings") or {}).get("n8n_sla_minutes") or 15)
    reads = {r.get("key"): (r.get("last_read_at") or "") for r in await db.n8n_inbox_reads.find({}).to_list(5000)}
    assigns = {a.get("key"): a for a in await db.n8n_inbox_assignments.find({}).to_list(5000)}
    bycust = {}
    for c in sorted(convs, key=lambda x: x.get("timestamp") or x.get("created_at") or ""):
        k = c.get("customer_id") or c.get("whatsapp") or "?"
        ts = c.get("timestamp") or c.get("created_at") or ""
        e = bycust.get(k) or {"_inbound_ts": []}
        e.update({"customer_id": c.get("customer_id"), "customer_name": c.get("customer_name") or e.get("customer_name"),
                  "whatsapp": c.get("whatsapp"), "last_message": c.get("message"),
                  "ai_status": c.get("ai_or_human"), "status": c.get("status"), "last_activity": c.get("timestamp"),
                  "last_direction": c.get("direction")})
        if c.get("direction") == "INBOUND":
            e.setdefault("_inbound_ts", []).append(ts)
        bycust[k] = e
    now_dt = datetime.now(timezone.utc)
    for e in bycust.values():
        key = _inbox_key(e.get("customer_id"), e.get("whatsapp"))
        lr = reads.get(key) or ""
        e["unread_count"] = sum(1 for t in e.pop("_inbound_ts", []) if t and t > lr)
        a = assigns.get(key) or {}
        e["assigned_to_id"] = a.get("assigned_to_id")
        e["assigned_to_name"] = a.get("assigned_to_name")
        wait = 0
        if e.get("last_direction") == "INBOUND" and e.get("last_activity"):
            try:
                wait = max(0, int((now_dt - datetime.fromisoformat(e["last_activity"])).total_seconds() // 60))
            except Exception:
                wait = 0
        e.pop("last_direction", None)
        e["waiting_minutes"] = wait
        e["sla_overdue"] = bool(e.get("status") == "REQUIRES_HUMAN" and wait > sla_min)
    conversations = sorted(bycust.values(), key=lambda x: x.get("last_activity") or "", reverse=True)[:100]
    orders = [{"order_id": b.get("booking_number"), "customer": b.get("customer_name"), "package": b.get("package_name"),
               "departure": b.get("departure_date"), "pax": b.get("pax"), "order_date": (b.get("created_at") or "")[:10],
               "source": b.get("booking_source"), "booking_status": b.get("status"), "payment_status": b.get("payment_status")} for b in auto[:200]]
    sync_logs = [{"request_id": str(l.get("_id")), "event": l.get("endpoint"), "method": l.get("method"), "direction": "INBOUND",
                  "timestamp": l.get("timestamp"), "status": "SUCCESS" if l.get("ok") else "FAILED",
                  "response": l.get("code"), "error": l.get("error", ""), "retry_count": l.get("retry_count", 0)} for l in logs[:200]]
    workflow_logs = [{"id": str(l.get("_id")), "workflow_id": (l.get("data") or {}).get("n8n_workflow_id") or (l.get("data") or {}).get("workflow_id") or "—",
                      "event": l.get("event"), "customer": (l.get("data") or {}).get("customer_name") or "—",
                      "booking": (l.get("data") or {}).get("booking_number") or "—", "timestamp": l.get("created_at"),
                      "status": "SKIPPED" if l.get("skipped") else ("SUCCESS" if l.get("ok") else "FAILED"),
                      "error": l.get("error") or l.get("reason") or "", "retry_count": l.get("retry_count", 0)} for l in wf_raw[:200]]
    api_logs_out = [{"timestamp": l.get("timestamp"), "endpoint": l.get("endpoint"), "method": l.get("method"),
                     "status": (l.get("status") or ("success" if l.get("ok") else "failed")), "response_code": l.get("response_code") or l.get("code"),
                     "latency_ms": l.get("processing_time_ms"), "error": (l.get("error") or "")[:120], "api_key": l.get("api_key_mask") or "—"} for l in logs[:200]]
    conn_status = "CONNECTED" if (cfg.get("enabled") and cfg.get("webhook_url")) else ("DISABLED" if cfg.get("webhook_url") else "NOT_CONFIGURED")
    return {"connection": {"status": conn_status, "base_url": cfg.get("webhook_url", ""), "last_sync": (logs[0]["timestamp"] if logs else None)},
            "health": {"connection": conn_status, "last_request": (_last_req or {}).get("timestamp"), "last_request_endpoint": (_last_req or {}).get("endpoint"),
                       "last_response": ((_last_req or {}).get("status") or "—") if _last_req else "—", "last_response_code": (_last_req or {}).get("response_code"),
                       "api_latency_ms": _avg_lat, "error_rate": _err_rate, "total_requests": len(logs)},
            "stats": {"total_today": len(tc), "inbound": sum(1 for c in tc if c.get("direction") == "INBOUND"),
                      "outbound": sum(1 for c in tc if c.get("direction") == "OUTBOUND"),
                      "ai_responses": sum(1 for c in tc if c.get("sender_type") == "AI"),
                      "human_handover": sum(1 for c in convs if c.get("status") == "REQUIRES_HUMAN"),
                      "orders_today": sum(1 for b in auto if (b.get("created_at") or "")[:10] == today),
                      "auto_sales_orders": len(auto),
                      "failed_requests": sum(1 for l in logs if not l.get("ok")),
                      "api_errors": sum(1 for l in logs if (l.get("code") or 200) >= 500),
                      "sla_minutes": sla_min, "sla_overdue": sum(1 for c in conversations if c.get("sla_overdue"))},
            "conversations": conversations, "orders": orders, "sync_logs": sync_logs,
            "workflow_logs": workflow_logs, "api_logs": api_logs_out}


@api_router.post("/integrations/n8n/sync/{log_id}/retry")
async def n8n_retry(log_id: str, user: dict = Depends(require_role("super_admin"))):
    l = await db.n8n_api_logs.find_one({"_id": ObjectId(log_id)}) if ObjectId.is_valid(log_id) else None
    if not l:
        raise HTTPException(status_code=404, detail="Log not found")
    cfg = await _n8n_cfg()
    configured = bool(cfg.get("enabled") and cfg.get("webhook_url"))
    delivered = None
    if configured:
        delivered = await _deliver_n8n("retry", {"endpoint": l.get("endpoint"), "method": l.get("method"),
                                                 "external_id": l.get("external_id"), "retried_by": user["name"]})
    ok = bool(delivered and delivered.get("ok"))
    status = "SUCCESS" if ok else ("FAILED" if configured else "REJECTED")
    await db.n8n_api_logs.update_one({"_id": l["_id"]}, {"$set": {"ok": ok, "status": status}, "$inc": {"retry_count": 1}})
    return {"success": ok, "status": status}


@api_router.post("/integrations/n8n/workflow/{log_id}/retry")
async def n8n_workflow_retry(log_id: str, user: dict = Depends(require_role("super_admin"))):
    l = await db.n8n_logs.find_one({"_id": ObjectId(log_id)}) if ObjectId.is_valid(log_id) else None
    if not l:
        raise HTTPException(status_code=404, detail="Workflow log not found")
    # Re-deliver original outbound event. Idempotent: outbound webhook re-send; inbound booking creation dedups by external id.
    res = await _deliver_n8n(l.get("event"), l.get("data") or {})
    await db.n8n_logs.update_one({"_id": l["_id"]}, {"$inc": {"retry_count": 1}})
    return {"success": bool(res.get("ok")), "status": "SUCCESS" if res.get("ok") else "FAILED", "reason": res.get("error") or res.get("reason") or ""}


@api_router.post("/integrations/n8n/conversations/reply")
async def n8n_reply(body: dict, user: dict = Depends(require_role("super_admin"))):
    cid = body.get("customer_id")
    msg = (body.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Pesan tidak boleh kosong")
    cust = await db.customers.find_one({"_id": ObjectId(cid)}) if (cid and ObjectId.is_valid(cid)) else None
    wa = (cust or {}).get("whatsapp") or body.get("whatsapp", "")
    doc = {"conversation_id": str(_uuid.uuid4()), "customer_id": cid, "customer_name": (cust or {}).get("full_name"),
           "whatsapp": wa, "channel": "WHATSAPP", "direction": "OUTBOUND", "message": msg, "message_type": "TEXT",
           "sender_type": "SALES", "sender_name": user["name"], "receiver": wa, "ai_or_human": "HUMAN", "n8n_workflow_id": "", "status": "SENT",
           "timestamp": now_iso(), "created_at": now_iso()}
    await db.conversations.insert_one(doc)
    if cid and ObjectId.is_valid(cid):
        await db.customers.update_one({"_id": ObjectId(cid)}, {"$set": {"conversation_status": "AGENT_REPLIED"}})
    trigger_n8n("conversation.reply", {"customer_id": cid, "whatsapp": wa, "message": msg, "agent": user["name"]})
    return {"success": True, "conversation": serialize(doc)}


@api_router.get("/integrations/n8n/conversations/thread")
async def n8n_conv_thread(customer_id: Optional[str] = None, whatsapp: Optional[str] = None,
                          user: dict = Depends(require_role("super_admin"))):
    q = {}
    if customer_id:
        q = {"customer_id": customer_id}
    elif whatsapp:
        q = {"whatsapp": whatsapp}
    else:
        raise HTTPException(status_code=400, detail="customer_id atau whatsapp wajib diisi")
    docs = await db.conversations.find(q).sort("timestamp", 1).to_list(2000)
    return [serialize(d) for d in docs]


@api_router.post("/integrations/n8n/conversations/read")
async def n8n_conv_read(body: dict, user: dict = Depends(require_role("super_admin"))):
    key = _inbox_key(body.get("customer_id"), body.get("whatsapp"))
    await db.n8n_inbox_reads.update_one({"key": key}, {"$set": {"key": key, "last_read_at": now_iso()}}, upsert=True)
    return {"success": True}


@api_router.post("/integrations/n8n/conversations/assign")
async def n8n_conv_assign(body: dict, user: dict = Depends(require_role("super_admin"))):
    key = _inbox_key(body.get("customer_id"), body.get("whatsapp"))
    if body.get("release"):
        await db.n8n_inbox_assignments.delete_one({"key": key})
        return {"success": True, "assigned_to_name": None, "assigned_to_id": None}
    uid = user.get("id") or str(user.get("_id", ""))
    await db.n8n_inbox_assignments.update_one({"key": key},
        {"$set": {"key": key, "assigned_to_id": uid, "assigned_to_name": user["name"], "assigned_at": now_iso()}}, upsert=True)
    return {"success": True, "assigned_to_name": user["name"], "assigned_to_id": uid}


# ---------- Phase 8I: Availability, Conversation Log, Human Handover ----------
async def _availability(package_id, departure_id=None):
    pkg = await db.packages.find_one({"_id": ObjectId(package_id)}) if ObjectId.is_valid(package_id) else None
    if not pkg:
        return None
    q = {"_id": ObjectId(departure_id)} if (departure_id and ObjectId.is_valid(departure_id)) else {"package_id": package_id}
    dep = await db.departures.find_one(q, sort=[("departure_date", 1)])
    total = int((dep or {}).get("total_seat") or (dep or {}).get("seat") or 0)
    depid = str(dep["_id"]) if dep else (departure_id or None)
    booked = 0
    if depid:
        for b in await db.bookings.find({"departure_id": depid, "status": {"$ne": "CANCELLED"}}).to_list(3000):
            booked += int(b.get("pax") or 0)
    return {"package_id": package_id, "package_name": pkg.get("package_name") or pkg.get("name"),
            "departure_id": depid, "departure_date": (dep or {}).get("departure_date") or (dep or {}).get("date") or "",
            "total_seat": total, "booked_seat": booked, "available_seat": max(total - booked, 0)}


@api_router.get("/v1/packages/{package_id}/availability")
async def v1_availability(package_id: str, request: Request, departure_id: Optional[str] = None, _n=Depends(n8n_auth)):
    start = _time.time()
    a = await _availability(package_id, departure_id)
    if not a:
        await _api_log(request, f"/v1/packages/{package_id}/availability", "GET", None, False, 404, start, "not found")
        return _v1_err("PACKAGE_NOT_FOUND", "Package tidak ditemukan", 404)
    await _api_log(request, f"/v1/packages/{package_id}/availability", "GET", None, True, 200, start)
    return {"success": True, **a}


@api_router.get("/packages/{package_id}/availability")
async def crm_availability(package_id: str, departure_id: Optional[str] = None, user: dict = Depends(get_current_user)):
    a = await _availability(package_id, departure_id)
    if not a:
        raise HTTPException(status_code=404, detail="Package tidak ditemukan")
    return a


async def _match_or_create_customer(payload):
    wa = (payload.get("whatsapp") or payload.get("customer_phone") or payload.get("phone") or "").strip()
    cid = payload.get("customer_id")
    if cid and ObjectId.is_valid(cid):
        c = await db.customers.find_one({"_id": ObjectId(cid)})
        if c:
            return c
    if wa:
        c = await db.customers.find_one({"whatsapp": wa})
        if c:
            return c
        count = await db.customers.count_documents({})
        doc = {"customer_code": f"CUST-{count + 1:05d}", "full_name": payload.get("customer_name") or wa, "whatsapp": wa,
               "email": payload.get("email", ""), "customer_type": "Prospect", "customer_source": "N8N",
               "sales_pic_id": None, "sales_pic_name": "AUTO SALES", "created_at": now_iso(), "created_by": "SYSTEM"}
        r = await db.customers.insert_one(doc)
        return await db.customers.find_one({"_id": r.inserted_id})
    return None


@api_router.post("/v1/conversations")
async def v1_log_conversation(payload: dict = Body(default={}), request: Request = None, _n=Depends(n8n_auth)):
    start = _time.time()
    ext = payload.get("external_message_id") or (request.headers.get("X-Idempotency-Key") if request else None)
    if ext:
        dup = await db.conversations.find_one({"external_message_id": ext})
        if dup:
            await _api_log(request, "/v1/conversations", "POST", ext, True, 200, start, "idempotent")
            return {"success": True, "idempotent": True, "conversation": serialize(dup)}
    cust = await _match_or_create_customer(payload)
    direction = (payload.get("direction") or "INBOUND").upper()
    requires_human = bool(payload.get("requires_human"))
    doc = {"conversation_id": payload.get("conversation_id") or str(_uuid.uuid4()),
           "customer_id": str(cust["_id"]) if cust else None, "customer_name": (cust or {}).get("full_name"),
           "whatsapp": (payload.get("whatsapp") or payload.get("customer_phone") or (cust or {}).get("whatsapp") or ""),
           "channel": payload.get("channel", "WHATSAPP"), "direction": direction,
           "message": payload.get("message", ""), "message_type": payload.get("message_type", "TEXT"),
           "sender_type": (payload.get("sender_type") or ("CUSTOMER" if direction == "INBOUND" else "AI")).upper(),
           "receiver": payload.get("receiver", ""), "ai_or_human": payload.get("ai_or_human", "AI"),
           "n8n_workflow_id": payload.get("n8n_workflow_id", ""), "external_message_id": ext,
           "status": "REQUIRES_HUMAN" if requires_human else payload.get("status", "LOGGED"),
           "timestamp": payload.get("timestamp") or now_iso(), "created_at": now_iso()}
    r = await db.conversations.insert_one(doc)
    if requires_human and cust:
        await db.customers.update_one({"_id": cust["_id"]}, {"$set": {"conversation_status": "HUMAN_HANDOVER"}})
        trigger_n8n("conversation.handover", {"customer_id": doc["customer_id"], "whatsapp": doc["whatsapp"]})
    await _api_log(request, "/v1/conversations", "POST", ext, True, 201, start)
    return {"success": True, "conversation": serialize(await db.conversations.find_one({"_id": r.inserted_id}))}


@api_router.get("/v1/conversations")
async def v1_list_conversations(request: Request, customer_id: Optional[str] = None, whatsapp: Optional[str] = None, _n=Depends(n8n_auth)):
    start = _time.time()
    q = {}
    if customer_id:
        q["customer_id"] = customer_id
    if whatsapp:
        q["whatsapp"] = whatsapp
    docs = await db.conversations.find(q).sort("timestamp", 1).to_list(1000)
    await _api_log(request, "/v1/conversations", "GET", None, True, 200, start)
    return {"success": True, "conversations": [serialize(d) for d in docs]}


@api_router.get("/customers/{cid}/conversations")
async def crm_conversations(cid: str, user: dict = Depends(require_permission("crm.view"))):
    docs = await db.conversations.find({"customer_id": cid}).sort("timestamp", 1).to_list(2000)
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
    _inv_snap = await tax_snapshot(now_iso()[:10], subtotal)
    await db.invoices.insert_one({**_inv_snap, "invoice_number": inv_number, "booking_id": bid, "booking_number": number,
        "customer_id": cid, "customer_name": cust.get("full_name"), "package_id": pid, "package_name": pkg.get("package_name"),
        "pax": pax, "amount": subtotal, "discount_amount": 0, "discount_percent": 0, "tax_percent": pct,
        "tax_amount": tax_amount, "total": total, "paid_amount": 0, "outstanding": total,
        "due_date": payload.get("due_date", ""), "status": "Unpaid", "sales_pic_id": None,
        "sales_pic_name": "AUTO SALES", "branch": "", "terms": pkg.get("terms", ""),
        "created_at": now_iso(), "created_by": "SYSTEM"})
    if ext:
        await db.idempotency_keys.update_one({"key": ext}, {"$set": {"booking_id": bid, "created_at": now_iso()}}, upsert=True)
    pay_link = f"/pay/{inv_number}"
    conf_msg = (f"Halo {cust.get('full_name')}, booking Anda berhasil dibuat.\n"
                f"No Booking: {number}\nPaket: {pkg.get('package_name')}\nPax: {pax}\n"
                f"Total: Rp {int(total):,}\nStatus Bayar: Unpaid\nPembayaran: {pay_link}").replace(",", ".")
    await db.conversations.insert_one({"conversation_id": str(_uuid.uuid4()), "customer_id": cid,
        "customer_name": cust.get("full_name"), "whatsapp": cust.get("whatsapp", ""), "channel": "WHATSAPP",
        "direction": "OUTBOUND", "message": conf_msg, "message_type": "ORDER_CONFIRMATION", "sender_type": "SYSTEM",
        "receiver": cust.get("whatsapp", ""), "ai_or_human": "SYSTEM", "n8n_workflow_id": payload.get("workflow_id", ""),
        "status": "SENT", "timestamp": now_iso(), "created_at": now_iso()})
    trigger_n8n("order.confirmation", {"booking_number": number, "customer": cust.get("full_name"),
        "customer_phone": cust.get("whatsapp", ""), "package": pkg.get("package_name"),
        "departure": (dep or {}).get("departure_date", ""), "pax": pax, "total_price": total,
        "payment_status": "Unpaid", "booking_status": "CONFIRMED", "payment_link": pay_link,
        "invoice_number": inv_number, "message": conf_msg})
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


@api_router.get("/executive-dashboard")
async def executive_dashboard(month: Optional[str] = None, user: dict = Depends(require_role("super_admin"))):
    from datetime import date
    today = today_str()
    td = date.fromisoformat(today)
    period = month or f"{td.year:04d}-{td.month:02d}"

    leads = await db.leads.find({}).to_list(20000)
    quotes = await db.quotations.find({}).to_list(20000)
    bookings = await db.bookings.find({}).to_list(20000)
    invoices = await db.invoices.find({}).to_list(20000)
    payments = await db.payments.find({}).to_list(40000)
    expenses = await db.expenses.find({}).to_list(20000)
    refunds = await db.refund_requests.find({}).to_list(10000)
    clines = await db.commission_lines.find({}).to_list(10000)
    packages = await db.packages.find({}).to_list(5000)

    pkg_cost = {str(p["_id"]): float(p.get("total_cost") or p.get("hpp") or 0) for p in packages}

    def in_period(dt):
        return (dt or "")[:7] == period

    def bk_hpp(b):
        return pkg_cost.get(str(b.get("package_id") or ""), 0) * int(b.get("pax") or 0)

    active_stages = {"NEW", "CONTACTED", "QUALIFIED", "QUOTATION", "NEGOTIATION", "BOOKING"}
    active_bookings = [b for b in bookings if b.get("status") != "CANCELLED"]
    period_leads = [l for l in leads if in_period(l.get("created_at"))]
    period_bookings = [b for b in active_bookings if in_period(b.get("created_at"))]
    period_quotes = [q for q in quotes if in_period(q.get("created_at"))]
    total_q = len(period_quotes)
    converted_q = len([q for q in period_quotes if q.get("status") == "ACCEPTED" or q.get("converted_booking_id")])
    period_pax = sum(int(b.get("pax") or 0) for b in period_bookings)
    booking_revenue = sum(float(b.get("total") or 0) for b in period_bookings)
    period_hpp = sum(bk_hpp(b) for b in period_bookings)
    gross_profit = booking_revenue - period_hpp

    # --- financial (period invoices/payments/expenses) ---
    period_invoices = [i for i in invoices if in_period(i.get("created_at"))]
    inv_revenue = sum(float(i.get("total") or 0) for i in period_invoices)
    dpp = sum(float(i.get("amount") or 0) for i in period_invoices)
    ppn = sum(float(i.get("tax_amount") or 0) for i in period_invoices)
    cash_in = sum(float(p.get("amount") or 0) for p in payments if in_period(p.get("payment_date")))
    cash_out = sum(float(e.get("amount") or 0) for e in expenses if in_period(e.get("date") or e.get("created_at")))

    # --- cumulative receivable aging ---
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

    # --- refunds (cumulative) ---
    refund_paid = sum(float(r.get("refunded_amount") or 0) for r in refunds)

    def rsum(statuses):
        return sum(float(r.get("proposed_refund") or 0) for r in refunds if r.get("status") in statuses)
    pending_refund = len([r for r in refunds if r.get("status") in ("CALCULATED", "ACCOUNTING_REVIEWED")])
    refund_block = {
        "pending_approval": pending_refund,
        "approved": rsum(("APPROVED", "PROCESSING", "PARTIALLY_REFUNDED", "REFUNDED")),
        "paid": refund_paid,
        "outstanding": rsum(("APPROVED", "PROCESSING", "PARTIALLY_REFUNDED")) - refund_paid,
    }

    commission_payable = sum(float(c.get("final_commission") or 0) for c in clines if c.get("payment_status") != "PAID")
    pending_commission = len([c for c in clines if c.get("payment_status") != "PAID"])
    supplier_pay = sum(float(e.get("amount") or 0) for e in expenses if "supplier" in (e.get("category") or "").lower())

    # --- lead funnel (all) ---
    idx = {s: i for i, s in enumerate(LEAD_STAGES)}

    def cnt(items, pred):
        return sum(1 for x in items if pred(x))
    order = ["QUALIFIED", "QUOTATION", "NEGOTIATION", "BOOKING", "PAID"]
    funnel = [{"stage": "Lead", "count": len(leads)}]
    for s in order:
        si = idx.get(s, 99)
        funnel.append({"stage": s.title(), "count": cnt(leads, lambda x: idx.get(x.get("status"), -1) >= si and x.get("status") != "LOST")})

    # --- 6-month trend ---
    months = []
    y, m = td.year, td.month
    for i in range(5, -1, -1):
        mm, yy = m - i, y
        while mm <= 0:
            mm += 12
            yy -= 1
        months.append(f"{yy:04d}-{mm:02d}")
    trend = []
    for mo in months:
        rev = sum(float(i.get("total") or 0) for i in invoices if (i.get("created_at") or "")[:7] == mo)
        mb = [b for b in active_bookings if (b.get("created_at") or "")[:7] == mo]
        hpp_m = sum(bk_hpp(b) for b in mb)
        bkrev = sum(float(b.get("total") or 0) for b in mb)
        ci = sum(float(p.get("amount") or 0) for p in payments if (p.get("payment_date") or "")[:7] == mo)
        co = sum(float(e.get("amount") or 0) for e in expenses if (e.get("date") or e.get("created_at") or "")[:7] == mo)
        trend.append({"month": mo, "revenue": rev, "hpp": hpp_m, "gross_profit": bkrev - hpp_m, "cash_in": ci, "cash_out": co})

    # --- revenue by package (period) ---
    rev_pkg = {}
    for i in period_invoices:
        n = i.get("package_name") or "—"
        rev_pkg[n] = rev_pkg.get(n, 0) + float(i.get("total") or 0)
    revenue_by_package = sorted([{"package": k, "value": v} for k, v in rev_pkg.items()], key=lambda x: -x["value"])[:8]

    # --- sales by person (period) ---
    by_sales = {}
    for b in period_bookings:
        n = b.get("sales_name") or "—"
        by_sales.setdefault(n, {"sales": n, "bookings": 0, "pax": 0, "value": 0})
        by_sales[n]["bookings"] += 1
        by_sales[n]["pax"] += int(b.get("pax") or 0)
        by_sales[n]["value"] += float(b.get("total") or 0)
    sales_performance = sorted(by_sales.values(), key=lambda x: -x["value"])[:8]

    # payment status counts (cumulative)
    ps = {"Paid": 0, "Partial": 0, "Unpaid": 0, "Overdue": 0}
    for i in invoices:
        st = i.get("status", "Unpaid")
        dd = (i.get("due_date") or "")[:10]
        if st != "Paid" and dd and dd < today:
            ps["Overdue"] += 1
        ps[st if st in ps else "Unpaid"] = ps.get(st if st in ps else "Unpaid", 0) + 1

    return {
        "period": period,
        "sales": {
            "leads_total": len(period_leads),
            "leads_new": cnt(period_leads, lambda x: x.get("status") == "NEW"),
            "leads_qualified": cnt(period_leads, lambda x: x.get("status") == "QUALIFIED"),
            "leads_lost": cnt(period_leads, lambda x: x.get("status") == "LOST"),
            "quotation_total": total_q,
            "quotation_converted": converted_q,
            "conversion_rate": round(converted_q / total_q * 100, 1) if total_q else 0,
            "booking_total": len(period_bookings),
            "total_pax": period_pax,
            "booking_revenue": booking_revenue,
            "auto_sales_bookings": len([b for b in period_bookings if b.get("booking_source") == "AUTO SALES"]),
            "auto_sales_revenue": sum(float(b.get("total") or 0) for b in period_bookings if b.get("booking_source") == "AUTO SALES"),
        },
        "financial": {
            "revenue": inv_revenue,
            "cash_in": cash_in,
            "cash_out": cash_out,
            "net_cash_flow": cash_in - cash_out,
            "outstanding_receivable": total_receivable,
            "refund_paid": refund_paid,
        },
        "profitability": {
            "revenue": booking_revenue,
            "hpp": period_hpp,
            "gross_profit": gross_profit,
            "gross_margin": round(gross_profit / booking_revenue * 100, 1) if booking_revenue else 0,
            "commission_payable": commission_payable,
        },
        "tax": {"dpp": dpp, "ppn": ppn, "pph": 0, "tax_payable": ppn},
        "refund": refund_block,
        "trend": trend,
        "funnel": funnel,
        "receivable_aging": {"total": total_receivable, **aging},
        "revenue_by_package": revenue_by_package,
        "sales_performance": sales_performance,
        "payment_status": ps,
        "outstanding": {
            "unpaid_invoice": len([i for i in invoices if i.get("status") == "Unpaid"]),
            "overdue_invoice": ps["Overdue"],
            "outstanding_receivable": total_receivable,
            "pending_refund": pending_refund,
            "pending_commission": pending_commission,
            "outstanding_supplier": supplier_pay,
            "tax_payable": ppn,
            "commission_payable": commission_payable,
        },
    }




# ============================================================================
# PHASE 10A — Native WhatsApp (WAHA) Integration — Tahap 1 (Super Admin)
# ============================================================================
import re as _re
from fastapi.responses import PlainTextResponse


def _wa_norm_phone(s):
    d = _re.sub(r"\D", "", s or "")
    return d[-12:] if len(d) > 12 else d


def _wa_chat_id(num):
    return f"{_re.sub(chr(92)+'D', '', num or '')}@c.us"


APICO_PROVIDER = "API_CO_ID"
_apico_typing_last = {}


def _wa_public(cfg):
    return {"provider": APICO_PROVIDER, "base_url": cfg.get("base_url"),
            "api_key_mask": _mask(cfg.get("_api_key") or ""), "has_key": bool(cfg.get("_api_key")),
            "phone_number_id": cfg.get("phone_number_id"), "phone_number": cfg.get("phone_number"),
            "phone_display_name": cfg.get("phone_display_name"),
            "connection_status": cfg.get("connection_status", "UNKNOWN"), "updated_at": cfg.get("updated_at")}


async def _wa_log(account_id, kind, direction, ref, ok, error="", payload=None):
    await db.whatsapp_logs.insert_one({"account_id": account_id or "apico", "kind": kind, "direction": direction,
        "ref": ref, "ok": bool(ok), "error": (error or "")[:500],
        "payload": payload if isinstance(payload, dict) else None, "created_at": now_iso()})


async def _apico_config():
    doc = await db.whatsapp_provider_config.find_one({"_id": "main"}) or {}
    base_url = (doc.get("base_url") or os.environ.get("APICO_BASE_URL") or "https://chat.api.co.id").rstrip("/")
    key = _dec(doc.get("api_key_enc") or "") or os.environ.get("APICO_API_KEY") or ""
    pnid = doc.get("phone_number_id") or os.environ.get("APICO_WHATSAPP_PHONE_NUMBER_ID") or ""
    return {"base_url": base_url, "_api_key": key, "phone_number_id": pnid,
            "phone_number": doc.get("phone_number"), "phone_display_name": doc.get("phone_display_name"),
            "connection_status": doc.get("connection_status", "UNKNOWN"), "updated_at": doc.get("updated_at")}


def _apico_categorize(status, err_text=""):
    if status in (401, 403):
        return "AUTH_ERROR"
    if status == 429:
        return "RATE_LIMIT"
    if status in (0, 408):
        return "TIMEOUT"
    if status and status >= 500:
        return "PROVIDER_ERROR"
    t = (err_text or "").lower()
    if "phone" in t and "invalid" in t:
        return "INVALID_PHONE"
    if "template" in t:
        return "INVALID_TEMPLATE"
    if "window" in t:
        return "WINDOW_CLOSED"
    if status and status >= 400:
        return "PROVIDER_ERROR"
    return "UNKNOWN_ERROR"


async def _apico_log(endpoint, method, status, duration_ms, ok, category="", error=""):
    await db.whatsapp_api_logs.insert_one({"provider": APICO_PROVIDER, "endpoint": endpoint, "method": method,
        "status_code": status, "duration_ms": duration_ms, "ok": bool(ok), "error_category": category,
        "error": (error or "")[:400], "created_at": now_iso()})


class WhatsAppProvider:
    """Abstract WhatsApp transport. Implementations must not leak provider structures to AI/Sales modules."""
    async def health(self): raise NotImplementedError
    async def get_phone_numbers(self): raise NotImplementedError
    async def send_message(self, phone_number, message_type, content=None, template=None, media_url=None): raise NotImplementedError
    async def mark_as_read(self, message_id): raise NotImplementedError
    async def send_typing(self, customer_phone): raise NotImplementedError
    async def get_customer(self, customer_phone): raise NotImplementedError
    async def check_window(self, customer_id): raise NotImplementedError
    async def get_templates(self): raise NotImplementedError


class ApiCoWhatsAppProvider(WhatsAppProvider):
    """Centralized Api.co.id client: auth, timeout, retry, logging, error normalization."""
    def __init__(self, cfg):
        self.base_url = cfg["base_url"]
        self.key = cfg["_api_key"]
        self.phone_number_id = cfg.get("phone_number_id")

    def _headers(self):
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    async def _call(self, method, path, json=None, params=None, retries=2, log=True):
        if not self.key:
            return {"ok": False, "status": 0, "data": None, "category": "AUTH_ERROR", "error": "API Key belum dikonfigurasi"}
        url = f"{self.base_url}{path}"
        attempt, backoff = 0, 1.0
        while True:
            start = _time.time()
            try:
                r = await asyncio.to_thread(_requests.request, method, url, headers=self._headers(),
                                            json=json, params=params, timeout=20)
                dur = int((_time.time() - start) * 1000)
                ok = r.status_code < 400
                cat = "" if ok else _apico_categorize(r.status_code, r.text)
                if log:
                    await _apico_log(path, method, r.status_code, dur, ok, cat, "" if ok else r.text[:300])
                if (not ok) and r.status_code >= 500 and attempt < retries:
                    attempt += 1
                    await asyncio.sleep(backoff); backoff *= 2
                    continue
                try:
                    data = r.json()
                except Exception:
                    data = None
                return {"ok": ok, "status": r.status_code, "data": data, "category": cat,
                        "error": "" if ok else (r.text or "")[:300]}
            except Exception as e:
                dur = int((_time.time() - start) * 1000)
                if log:
                    await _apico_log(path, method, 0, dur, False, "TIMEOUT", str(e)[:300])
                if attempt < retries:
                    attempt += 1
                    await asyncio.sleep(backoff); backoff *= 2
                    continue
                return {"ok": False, "status": 0, "data": None, "category": "TIMEOUT", "error": str(e)[:300]}

    async def health(self):
        return await self._call("GET", "/api/v1/public/health")

    async def get_phone_numbers(self):
        return await self._call("GET", "/api/v1/public/phone-numbers")

    async def send_message(self, phone_number, message_type, content=None, template=None, media_url=None):
        payload = {"phone_number": phone_number, "channel": "whatsapp", "message_type": message_type,
                   "whatsapp_phone_number_id": self.phone_number_id}
        if message_type == "template":
            payload["template"] = template or {}
        elif message_type == "text":
            payload["content"] = content or ""
        else:
            if media_url:
                payload["media_url"] = media_url
            if content:
                payload["caption"] = content
        return await self._call("POST", "/api/v1/public/messages/send", json=payload)

    async def mark_as_read(self, message_id):
        return await self._call("POST", f"/api/v1/public/messages/{message_id}/read")

    async def send_typing(self, customer_phone):
        import time as _t
        now = _t.time()
        if now - _apico_typing_last.get(customer_phone, 0) < 3:
            return {"ok": True, "skipped": True}
        _apico_typing_last[customer_phone] = now
        return await self._call("POST", f"/api/v1/public/conversations/{customer_phone}/typing",
                                json={"channel": "whatsapp", "whatsapp_phone_number_id": self.phone_number_id}, log=False)

    async def get_customer(self, customer_phone):
        return await self._call("GET", f"/api/v1/public/customers/{customer_phone}")

    async def check_window(self, customer_id):
        return await self._call("GET", f"/api/v1/public/customers/{customer_id}/window-status")

    async def get_templates(self):
        return await self._call("GET", "/api/v1/public/templates")


async def get_wa_provider():
    return ApiCoWhatsAppProvider(await _apico_config())


def _apico_norm(phone):
    d = _re.sub(r"\D", "", phone or "")
    if d.startswith("620"):
        d = "62" + d[3:]
    elif d.startswith("0"):
        d = "62" + d[1:]
    elif d and not d.startswith("62") and len(d) >= 9:
        d = "62" + d
    return d


async def _apico_resolve_customer(phone, name="", created_by="AI AGENT"):
    norm = _apico_norm(phone)
    last = norm[-9:] if len(norm) >= 9 else norm
    cust = None
    if last:
        rx = {"$regex": _re.escape(last) + "$"}
        cust = await db.customers.find_one({"is_deleted": {"$ne": True}, "$or": [{"whatsapp": rx}, {"phone": rx}]})
    if cust:
        return cust, False
    count = await db.customers.count_documents({})
    doc = {"customer_code": f"CUST-{count + 1:05d}", "full_name": name or norm, "whatsapp": norm, "phone": norm,
           "customer_type": "Prospect", "customer_source": "WHATSAPP", "sales_pic_id": None,
           "sales_pic_name": "AUTO SALES", "attribution": "AUTO SALES",
           "created_at": now_iso(), "created_by": created_by}
    r = await db.customers.insert_one(doc)
    return await db.customers.find_one({"_id": r.inserted_id}), True


@api_router.get("/whatsapp/provider")
async def wa_provider_get(user: dict = Depends(require_role("super_admin"))):
    return _wa_public(await _apico_config())


@api_router.put("/whatsapp/provider")
async def wa_provider_save(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    upd = {"provider": APICO_PROVIDER, "updated_at": now_iso(), "updated_by": user["name"]}
    if body.get("base_url") is not None:
        upd["base_url"] = (body["base_url"] or "").rstrip("/")
    if body.get("api_key"):
        upd["api_key_enc"] = _enc(body["api_key"])
    if body.get("phone_number_id") is not None:
        upd["phone_number_id"] = body["phone_number_id"]
    if body.get("phone_number") is not None:
        upd["phone_number"] = body["phone_number"]
    if body.get("phone_display_name") is not None:
        upd["phone_display_name"] = body["phone_display_name"]
    await db.whatsapp_provider_config.update_one({"_id": "main"}, {"$set": upd}, upsert=True)
    await log_audit(user, "whatsapp", "save_provider", request, new={k: v for k, v in upd.items() if "enc" not in k and k != "api_key"})
    return _wa_public(await _apico_config())


@api_router.post("/whatsapp/provider/test-connection")
async def wa_provider_test(user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc.health()
    status = "CONNECTED" if res["ok"] else "ERROR"
    await db.whatsapp_provider_config.update_one({"_id": "main"}, {"$set": {"connection_status": status, "last_checked": now_iso()}}, upsert=True)
    if not res["ok"]:
        return {"connection_status": "ERROR", "ok": False, "error_category": res["category"],
                "message": "Koneksi gagal. Periksa API Key & Base URL."}
    return {"connection_status": "CONNECTED", "ok": True, "message": "Terhubung ke Api.co.id."}


@api_router.get("/whatsapp/provider/phone-numbers")
async def wa_provider_phone_numbers(user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc.get_phone_numbers()
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Gagal memuat nomor WhatsApp ({res['category']}).")
    data = res["data"]
    items = data.get("data") if isinstance(data, dict) else data
    return {"phone_numbers": items or []}


async def _wa_upsert_conversation(wa_number, name="", created_by="AI AGENT"):
    norm = _apico_norm(wa_number)
    cust, is_new = await _apico_resolve_customer(norm, name, created_by)
    conv = await db.whatsapp_conversations.find_one({"wa_number": norm})
    if conv:
        return conv, cust
    doc = {"account_id": "apico", "provider": APICO_PROVIDER, "wa_number": norm,
           "customer_id": str(cust["_id"]) if cust else None,
           "customer_name": (cust.get("full_name") if cust else name) or norm, "is_new_customer": is_new,
           "status": "AI ACTIVE", "assigned_sales_id": (cust.get("sales_pic_id") if cust else None),
           "ai_status": "ACTIVE", "handover_status": "NONE", "created_at": now_iso(),
           "last_message": "", "last_activity": now_iso()}
    r = await db.whatsapp_conversations.insert_one(doc)
    doc["_id"] = r.inserted_id
    return doc, cust


def _apico_extract_message(body):
    payload = body.get("data") or body.get("payload") or body.get("message") or body
    if not isinstance(payload, dict):
        return None
    msg = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    mid = msg.get("message_id") or msg.get("id") or payload.get("message_id") or payload.get("id")
    ev = (body.get("event") or body.get("type") or payload.get("event") or msg.get("event") or "").lower()
    _dir = (msg.get("direction") or payload.get("direction") or "").lower()
    if _dir:
        direction = _dir
    elif any(k in ev for k in ["receiv", "incoming", "inbound"]):
        direction = "inbound"
    elif any(k in ev for k in ["sent", "deliver", "read", "fail", "status", "outbound"]):
        direction = "outbound"
    else:
        direction = "inbound"
    phone = (msg.get("customer_phone") or msg.get("from") or msg.get("sender") or msg.get("wa_id")
             or payload.get("customer_phone") or payload.get("phone_number") or payload.get("from") or "")
    content = (msg.get("content") or msg.get("text") or msg.get("body") or payload.get("content") or "")
    mtype = (msg.get("message_type") or msg.get("type") or "text").lower()
    media_obj = msg.get("media") if isinstance(msg.get("media"), dict) else {}
    media_url = (msg.get("media_url") or msg.get("url") or msg.get("link") or msg.get("file_url")
                 or media_obj.get("url") or media_obj.get("link") or payload.get("media_url") or "")
    if isinstance(media_url, dict):
        media_url = media_url.get("url") or media_url.get("link") or ""
    media_filename = (msg.get("filename") or msg.get("file_name") or media_obj.get("filename") or "")
    name = payload.get("customer_name") or msg.get("customer_name") or ""
    if not (mid or content or media_url):
        return None
    return {"message_id": str(mid) if mid else f"in-{now_iso()}", "direction": direction,
            "phone": phone, "content": content, "type": mtype, "name": name,
            "media_url": media_url or "", "media_filename": media_filename or ""}


async def _apico_process_inbound(event_db_id, parsed):
    try:
        dup = await db.whatsapp_messages.find_one({"message_id": parsed["message_id"]})
        if dup:
            await db.whatsapp_webhook_events.update_one({"_id": event_db_id}, {"$set": {"status": "DUPLICATE", "processed_at": now_iso()}})
            return
        conv, cust = await _wa_upsert_conversation(parsed["phone"], parsed["name"], created_by="AI AGENT")
        msg = {"message_id": parsed["message_id"], "conversation_id": str(conv["_id"]), "account_id": "apico",
               "external_provider": APICO_PROVIDER, "external_message_id": parsed["message_id"],
               "sender": "CUSTOMER", "sender_type": "CUSTOMER", "receiver": "CRM", "direction": "INBOUND",
               "type": parsed["type"], "message_type": parsed["type"], "content": parsed["content"],
               "media_url": parsed.get("media_url") or "", "media_filename": parsed.get("media_filename") or "",
               "media_type": parsed["type"] if (parsed.get("media_url") and parsed["type"] != "text") else "",
               "timestamp": now_iso(), "created_at": now_iso(), "ai_generated": False, "human_generated": False,
               "delivery_status": "RECEIVED", "status": "RECEIVED", "read_status": False}
        await db.whatsapp_messages.insert_one(msg)
        await db.whatsapp_conversations.update_one({"_id": conv["_id"]}, {"$set": {"last_message": (parsed["content"] or "")[:200], "last_activity": now_iso()}})
        await _mirror_crm_conversation(conv, parsed["content"], "INBOUND", "CUSTOMER", parsed.get("type") or "TEXT", parsed.get("media_url"))
        await _wa_log("apico", "WEBHOOK", "IN", parsed["message_id"], True, "", {"from": parsed["phone"], "type": parsed["type"]})
        try:
            svc = await get_wa_provider()
            rr = await svc.mark_as_read(parsed["message_id"])
            if rr.get("ok"):
                await db.whatsapp_messages.update_one({"message_id": parsed["message_id"]}, {"$set": {"read_at": now_iso(), "read_status": True}})
        except Exception:
            pass
        try:
            _wa_debounce_schedule(str(conv["_id"]), parsed["content"])
        except Exception as _e:
            await _wa_log("apico", "AI", "IN", str(conv["_id"]), False, str(_e))
        await db.whatsapp_webhook_events.update_one({"_id": event_db_id}, {"$set": {"status": "PROCESSED", "processed_at": now_iso()}})
    except Exception as e:
        await db.whatsapp_webhook_events.update_one({"_id": event_db_id}, {"$set": {"status": "ERROR", "error": str(e)[:300], "processed_at": now_iso()}})


@api_router.post("/webhooks/api-co-id/whatsapp")
async def apico_webhook(request: Request, background: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        body = {}
    event_id = (body.get("event_id") or body.get("id") or (body.get("data") or {}).get("message_id") or f"evt-{now_iso()}")
    existing = await db.whatsapp_webhook_events.find_one({"event_id": str(event_id)})
    if existing:
        return {"ok": True, "duplicate": True}
    rec = {"provider": APICO_PROVIDER, "event_id": str(event_id), "event_type": body.get("event") or body.get("type") or "",
           "raw": body if isinstance(body, dict) else {}, "status": "RECEIVED", "received_at": now_iso(), "processed_at": None}
    r = await db.whatsapp_webhook_events.insert_one(rec)
    parsed = _apico_extract_message(body)
    if parsed and parsed["direction"] == "inbound":
        background.add_task(_apico_process_inbound, r.inserted_id, parsed)
    else:
        await db.whatsapp_webhook_events.update_one({"_id": r.inserted_id}, {"$set": {"status": "IGNORED", "processed_at": now_iso()}})
    return {"ok": True}


@api_router.get("/whatsapp/conversations")
async def wa_conversations(status: str = "", user: dict = Depends(require_role("super_admin"))):
    q = {} if not status else {"status": status}
    convs = await db.whatsapp_conversations.find(q).sort("last_activity", -1).to_list(200)
    return [serialize(c) for c in convs]


@api_router.get("/whatsapp/conversations/{cid}/messages")
async def wa_conv_messages(cid: str, user: dict = Depends(require_role("super_admin"))):
    msgs = await db.whatsapp_messages.find({"conversation_id": cid}).sort("timestamp", 1).to_list(1000)
    return [serialize(m) for m in msgs]


@api_router.post("/whatsapp/conversations/{cid}/send")
async def wa_send(cid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    mtype = body.get("type") or "text"
    svc = await get_wa_provider()
    if not svc.key:
        raise HTTPException(status_code=400, detail="Api.co.id belum dikonfigurasi. Isi API Key di menu Provider.")
    res = await svc.send_message(conv["wa_number"], mtype, content=body.get("content") or "",
                                 media_url=body.get("url") or body.get("media_url"))
    mid = f"out-{now_iso()}"
    if not res["ok"]:
        await _wa_log(conv.get("account_id", "apico"), "SEND", "OUT", mid, False, res.get("error", ""))
        raise HTTPException(status_code=502, detail=f"Gagal mengirim pesan ({res.get('category')}).")
    data = res.get("data") or {}
    inner = data.get("data") if isinstance(data, dict) else {}
    mid = (inner or {}).get("message_id") or data.get("message_id") or mid
    await _wa_log(conv.get("account_id", "apico"), "SEND", "OUT", str(mid), True, "")
    msg = {"message_id": str(mid), "conversation_id": cid, "account_id": conv.get("account_id", "apico"),
           "external_provider": APICO_PROVIDER, "external_message_id": str(mid),
           "sender": "SALES" if not body.get("ai_generated") else "AI",
           "sender_type": "SALES" if not body.get("ai_generated") else "AI",
           "receiver": conv["wa_number"], "direction": "OUTBOUND", "type": mtype, "message_type": mtype,
           "content": body.get("content") or "", "timestamp": now_iso(), "created_at": now_iso(), "sent_at": now_iso(),
           "ai_generated": bool(body.get("ai_generated")), "human_generated": not bool(body.get("ai_generated")),
           "delivery_status": "SENT", "status": "SENT", "read_status": False}
    await db.whatsapp_messages.insert_one(msg)
    await db.whatsapp_conversations.update_one({"_id": conv["_id"]}, {"$set": {"last_message": msg["content"][:200], "last_activity": now_iso(), "status": "WAITING CUSTOMER"}})
    return serialize(msg)


WA_MEDIA_TYPES = {"image", "document", "audio", "video"}


def _wa_media_sig(mid):
    return _hmac.new(os.environ["JWT_SECRET"].encode(), f"wamedia:{mid}".encode(), _hashlib.sha256).hexdigest()[:32]


@api_router.post("/whatsapp/conversations/{cid}/send-media")
async def wa_send_media(cid: str, request: Request, media_type: str = Form(...), file: UploadFile = File(...),
                        caption: str = Form(""), user: dict = Depends(require_role("super_admin"))):
    conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    mtype = (media_type or "").lower()
    if mtype not in WA_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Tipe media tidak valid (image/document/audio/video)")
    data = await file.read()
    if len(data) > 16 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 16MB")
    allowed, _r = await _wa_outbound_allowed(conv.get("customer_id"))
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Pengiriman diblokir: {_r}")
    media_id = str(_uuid.uuid4())
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "bin"
    path = f"{_APP_NAME}/whatsapp/media/{cid}/{media_id}.{ext}"
    result = put_object(path, data, file.content_type or "application/octet-stream")
    await db.wa_media.insert_one({"id": media_id, "conversation_id": cid, "storage_path": result["path"],
        "content_type": file.content_type or "application/octet-stream", "original_filename": file.filename,
        "size": result.get("size", len(data)), "media_type": mtype, "created_at": now_iso()})
    media_url = f"{_public_base({})}/api/public/wa-media/{media_id}?sig={_wa_media_sig(media_id)}"
    svc = await get_wa_provider()
    if not svc.key:
        raise HTTPException(status_code=400, detail="Api.co.id belum dikonfigurasi. Isi API Key di menu Provider.")
    res = await svc.send_message(conv["wa_number"], mtype, content=caption or "", media_url=media_url)
    mid = f"out-{now_iso()}"
    if not res["ok"]:
        await _wa_log(conv.get("account_id", "apico"), "SEND", "OUT", mid, False, res.get("error", ""))
        raise HTTPException(status_code=502, detail=f"Gagal mengirim media ({res.get('category')}).")
    data_r = res.get("data") or {}
    inner = data_r.get("data") if isinstance(data_r, dict) else {}
    mid = (inner or {}).get("message_id") or data_r.get("message_id") or mid
    await _wa_log(conv.get("account_id", "apico"), "SEND", "OUT", str(mid), True, "")
    msg = {"message_id": str(mid), "conversation_id": cid, "account_id": conv.get("account_id", "apico"),
           "external_provider": APICO_PROVIDER, "external_message_id": str(mid),
           "sender": "SALES", "sender_type": "SALES", "receiver": conv["wa_number"],
           "direction": "OUTBOUND", "type": mtype, "message_type": mtype, "content": caption or "",
           "media_url": media_url, "media_type": mtype, "media_filename": file.filename,
           "timestamp": now_iso(), "created_at": now_iso(), "sent_at": now_iso(),
           "ai_generated": False, "human_generated": True, "delivery_status": "SENT", "status": "SENT", "read_status": False}
    await db.whatsapp_messages.insert_one(msg)
    await db.whatsapp_conversations.update_one({"_id": conv["_id"]}, {"$set": {
        "last_message": (f"[{mtype}] " + (caption or file.filename or ""))[:200], "last_activity": now_iso(), "status": "WAITING CUSTOMER"}})
    return serialize(msg)


@api_router.get("/public/wa-media/{media_id}")
async def public_wa_media(media_id: str, sig: str = Query("")):
    if not sig or not _hmac.compare_digest(sig, _wa_media_sig(media_id)):
        raise HTTPException(status_code=403, detail="Invalid signature")
    rec = await db.wa_media.find_one({"id": media_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Not found")
    content, ct = get_object(rec["storage_path"])
    return Response(content=content, media_type=rec.get("content_type") or ct)


@api_router.get("/whatsapp/brochure-packages")
async def wa_brochure_packages(user: dict = Depends(require_role("super_admin"))):
    docs = await db.packages.find({"status": "ACTIVE"}).sort("created_at", -1).to_list(60)
    out = []
    for p in docs:
        pid_s = str(p["_id"])
        cov = (p.get("cover_image") or "").strip()
        has_bro = await db.package_brochures.find_one({"package_id": pid_s, "is_deleted": {"$ne": True}, "content_type": {"$regex": "^image/"}})
        if not cov and not has_bro:
            continue
        out.append({"id": pid_s, "package_name": p.get("package_name"),
                    "selling_price": p.get("selling_price"), "destination": p.get("destination"),
                    "duration": p.get("duration")})
    return out


@api_router.post("/whatsapp/conversations/{cid}/send-brochure")
async def wa_send_brochure(cid: str, body: dict, user: dict = Depends(require_role("super_admin"))):
    conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    pid = body.get("package_id")
    brochure_id = body.get("brochure_id")
    pkg = await db.packages.find_one({"_id": ObjectId(pid)}) if pid and ObjectId.is_valid(pid) else None
    if not pkg:
        raise HTTPException(status_code=404, detail="Package tidak ditemukan")
    bro = None
    if brochure_id:
        bro = await db.package_brochures.find_one({"id": brochure_id, "is_deleted": {"$ne": True}})
    if not bro:
        bro = await db.package_brochures.find_one({"package_id": pid, "is_deleted": {"$ne": True}, "is_primary": True}) \
            or await db.package_brochures.find_one({"package_id": pid, "is_deleted": {"$ne": True}, "content_type": {"$regex": "^image/"}}, sort=[("created_at", -1)])
    is_pdf = bool(bro and (bro.get("content_type") or "").startswith("application/pdf"))
    if bro:
        cov = f"{_public_base({})}/api/public/brochure/{bro['id']}?sig={_brochure_sig(bro['id'])}"
    else:
        cov = (pkg.get("cover_image") or "").strip()
    if not cov:
        raise HTTPException(status_code=400, detail="Paket belum memiliki brosur/gambar. Upload atau generate brosur dulu.")
    allowed, _r = await _wa_outbound_allowed(conv.get("customer_id"))
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Pengiriman diblokir: {_r}")
    price = int(pkg.get("selling_price") or 0)
    caption = (body.get("caption") or "").strip() or (
        f"*{pkg.get('package_name', '')}*\n"
        + (f"{pkg.get('destination') or ''} · {pkg.get('duration') or ''}\n" if (pkg.get('destination') or pkg.get('duration')) else "")
        + (f"Mulai Rp{price:,}/pax\n" if price else "")
        + (pkg.get("promo_text") or "")
    ).strip()
    send_type = "document" if is_pdf else "image"
    media_filename = (bro.get("original_filename") if bro else None) or ("brosur.pdf" if is_pdf else "brochure.png")
    if cov.startswith("http://") or cov.startswith("https://"):
        media_url = cov
    else:
        raw = cov.split(",", 1)[1] if cov.startswith("data:") else cov
        try:
            import base64 as _b64
            data = _b64.b64decode(raw)
        except Exception:
            raise HTTPException(status_code=400, detail="Gambar brosur tidak valid")
        media_id = str(_uuid.uuid4())
        path = f"{_APP_NAME}/whatsapp/brochure/{media_id}.png"
        result = put_object(path, data, "image/png")
        await db.wa_media.insert_one({"id": media_id, "conversation_id": cid, "storage_path": result["path"],
            "content_type": "image/png", "original_filename": "brochure.png", "size": result.get("size", len(data)),
            "media_type": "image", "created_at": now_iso()})
        media_url = f"{_public_base({})}/api/public/wa-media/{media_id}?sig={_wa_media_sig(media_id)}"
    svc = await get_wa_provider()
    if not svc.key:
        raise HTTPException(status_code=400, detail="Api.co.id belum dikonfigurasi. Isi API Key di menu Provider.")
    res = await svc.send_message(conv["wa_number"], send_type, content=caption, media_url=media_url)
    mid = f"out-{now_iso()}"
    if not res["ok"]:
        await _wa_log(conv.get("account_id", "apico"), "SEND", "OUT", mid, False, res.get("error", ""))
        raise HTTPException(status_code=502, detail=f"Gagal mengirim brosur ({res.get('category')}).")
    data_r = res.get("data") or {}
    inner = data_r.get("data") if isinstance(data_r, dict) else {}
    mid = (inner or {}).get("message_id") or data_r.get("message_id") or mid
    await _wa_log(conv.get("account_id", "apico"), "SEND", "OUT", str(mid), True, "")
    msg = {"message_id": str(mid), "conversation_id": cid, "account_id": conv.get("account_id", "apico"),
           "external_provider": APICO_PROVIDER, "external_message_id": str(mid),
           "sender": "SALES", "sender_type": "SALES", "receiver": conv["wa_number"],
           "direction": "OUTBOUND", "type": send_type, "message_type": send_type, "content": caption,
           "media_url": media_url, "media_type": send_type, "media_filename": media_filename,
           "timestamp": now_iso(), "created_at": now_iso(), "sent_at": now_iso(),
           "ai_generated": False, "human_generated": True, "delivery_status": "SENT", "status": "SENT", "read_status": False}
    await db.whatsapp_messages.insert_one(msg)
    await db.whatsapp_conversations.update_one({"_id": conv["_id"]}, {"$set": {
        "last_message": ("[brosur] " + (pkg.get("package_name") or ""))[:200], "last_activity": now_iso(), "status": "WAITING CUSTOMER"}})
    return serialize(msg)


# ---------- Package Brochures (upload/generate/download) ----------
def _brochure_sig(bid):
    return _hmac.new(os.environ["JWT_SECRET"].encode(), f"brochure:{bid}".encode(), _hashlib.sha256).hexdigest()[:32]


def _brochure_out(b):
    is_img = (b.get("content_type") or "").startswith("image/")
    return {"id": b["id"], "package_id": b.get("package_id"), "kind": b.get("kind"),
            "content_type": b.get("content_type"), "filename": b.get("original_filename"),
            "size": b.get("size"), "created_at": b.get("created_at"), "created_by": b.get("created_by"),
            "is_image": is_img, "is_primary": bool(b.get("is_primary")),
            "public_url": (f"{_public_base({})}/api/public/brochure/{b['id']}?sig={_brochure_sig(b['id'])}" if is_img else None)}


@api_router.get("/packages/{pid}/brochures")
async def list_brochures(pid: str, user: dict = Depends(require_any_permission("product.view", "product.manage", "packages.view"))):
    docs = await db.package_brochures.find({"package_id": pid, "is_deleted": {"$ne": True}}).sort("created_at", -1).to_list(100)
    return [_brochure_out(b) for b in docs]


@api_router.post("/packages/{pid}/brochures")
async def upload_brochure(pid: str, file: UploadFile = File(...), user: dict = Depends(require_permission("product.manage"))):
    pkg = await db.packages.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not pkg:
        raise HTTPException(status_code=404, detail="Package tidak ditemukan")
    ct = file.content_type or "application/octet-stream"
    if not (ct.startswith("image/") or ct == "application/pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF atau gambar (JPG/PNG) yang diperbolehkan")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 15MB")
    bid = str(_uuid.uuid4())
    ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else ("pdf" if ct == "application/pdf" else "png")
    path = f"{_APP_NAME}/brochures/{pid}/{bid}.{ext}"
    result = put_object(path, data, ct)
    rec = {"id": bid, "package_id": pid, "kind": "UPLOAD", "storage_path": result["path"], "content_type": ct,
           "original_filename": file.filename or f"brosur.{ext}", "size": result.get("size", len(data)),
           "is_deleted": False, "created_by": user["name"], "created_at": now_iso()}
    await db.package_brochures.insert_one(rec)
    return _brochure_out(rec)


@api_router.get("/brochures/{bid}/download")
async def download_brochure(bid: str, format: str = Query(None), authorization: str = Header(None), auth: str = Query(None)):
    token = authorization[7:] if (authorization or "").startswith("Bearer ") else auth
    u = await user_from_token(token) if token else None
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    b = await db.package_brochures.find_one({"id": bid, "is_deleted": {"$ne": True}})
    if not b:
        raise HTTPException(status_code=404, detail="Brosur tidak ditemukan")
    content, ct = get_object(b["storage_path"])
    fn = b.get("original_filename") or "brosur"
    mt = b.get("content_type") or ct
    if (format or "").lower() == "pdf" and mt.startswith("image/"):
        try:
            import io as _io
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas as _rcanvas
            buf = _io.BytesIO()
            c = _rcanvas.Canvas(buf, pagesize=A4)
            PW, PH = A4
            img = ImageReader(_io.BytesIO(content))
            iw, ih = img.getSize()
            ratio = min((PW - 16 * mm) / iw, (PH - 16 * mm) / ih)
            dw, dh = iw * ratio, ih * ratio
            c.drawImage(img, (PW - dw) / 2, (PH - dh) / 2, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
            c.save()
            content = buf.getvalue()
            mt = "application/pdf"
            fn = (fn.rsplit(".", 1)[0] if "." in fn else fn) + ".pdf"
        except Exception:
            pass
    return Response(content=content, media_type=mt,
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@api_router.delete("/brochures/{bid}")
async def delete_brochure(bid: str, user: dict = Depends(require_permission("product.manage"))):
    r = await db.package_brochures.update_one({"id": bid}, {"$set": {"is_deleted": True, "deleted_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Brosur tidak ditemukan")
    return {"deleted": True}


@api_router.get("/public/brochure/{bid}")
async def public_brochure(bid: str, sig: str = Query("")):
    if not sig or not _hmac.compare_digest(sig, _brochure_sig(bid)):
        raise HTTPException(status_code=403, detail="Invalid signature")
    b = await db.package_brochures.find_one({"id": bid, "is_deleted": {"$ne": True}})
    if not b:
        raise HTTPException(status_code=404, detail="Not found")
    content, ct = get_object(b["storage_path"])
    return Response(content=content, media_type=b.get("content_type") or ct)


def _fetch_img_bytes(src):
    try:
        if not src:
            return None
        if src.startswith("data:"):
            import base64 as _b
            return _b.b64decode(src.split(",", 1)[1])
        if src.startswith("http"):
            r = _requests.get(src, timeout=10)
            return r.content if r.ok else None
    except Exception:
        return None
    return None


def _stamp_brochure_image(img_bytes, info, opts=None):
    """Tempelkan LOGO agency (dari Settings) di bagian atas gambar brosur. opts: logo_position/scale/opacity/margin."""
    try:
        logo_b = _fetch_img_bytes(info.get("logo_url"))
        if not logo_b:
            return img_bytes
        opts = opts or {}
        position = opts.get("logo_position") or "top-right"
        scale = float(opts.get("logo_scale") or 0.12)
        scale = min(0.4, max(0.05, scale))
        opacity = int(opts.get("logo_opacity") if opts.get("logo_opacity") is not None else 180)
        opacity = min(255, max(0, opacity))
        margin_pct = float(opts.get("logo_margin") or 0.03)
        from PIL import Image
        import io as _io
        im = Image.open(_io.BytesIO(img_bytes)).convert("RGBA")
        W, H = im.size
        lg = Image.open(_io.BytesIO(logo_b)).convert("RGBA")
        if opacity < 255:
            a = lg.split()[3].point(lambda p: int(p * (opacity / 255.0)))
            lg.putalpha(a)
        lh = max(40, int(H * scale))
        lw = max(1, int(lg.width * (lh / max(1, lg.height))))
        lg = lg.resize((lw, lh))
        margin = max(12, int(W * margin_pct))
        pos = (position or "top-right").lower()
        if "left" in pos or "kiri" in pos:
            x = margin
        elif "center" in pos or "tengah" in pos:
            x = (W - lw) // 2
        else:
            x = W - lw - margin
        y = margin
        pad = int(lh * 0.16)
        bg = Image.new("RGBA", (lw + 2 * pad, lh + 2 * pad), (255, 255, 255, 170))
        im.alpha_composite(bg, (max(0, x - pad), max(0, y - pad)))
        im.alpha_composite(lg, (x, y))
        out = _io.BytesIO()
        im.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return img_bytes


async def _brochure_reference_images(ref_ids):
    imgs = []
    import base64 as _b64
    for rid in (ref_ids or [])[:4]:
        rb = await db.package_brochures.find_one({"id": rid, "is_deleted": {"$ne": True}})
        if rb and (rb.get("content_type") or "").startswith("image/"):
            try:
                content, _ct = get_object(rb["storage_path"])
                imgs.append(_b64.b64encode(content).decode())
            except Exception:
                pass
    return imgs


def _brochure_prompt(pkg, itin_txt, price, theme, highlights, promo, cta, extra, has_ref):
    p = (
        "Buatkan POSTER INFOGRAFIS BROSUR PARIWISATA format potret (portrait) yang menarik, modern, rapi, "
        "layak cetak, dengan hierarki teks yang jelas dan ikon sederhana. Semua teks dalam BAHASA INDONESIA dan dieja dengan benar. "
        f"Tema warna: {theme}. "
        f"JUDUL BESAR: {pkg.get('package_name', 'Paket Wisata')}. "
        f"Destinasi: {pkg.get('destination') or pkg.get('country') or '-'}. Durasi: {pkg.get('duration') or '-'}. "
        + (f"Harga mulai Rp{price:,}/pax. " if price else "")
        + (f"Highlight fasilitas: {highlights}. " if highlights else "")
        + (f"Promo: {promo}. " if promo else "")
        + (f"Ajakan (CTA) di bagian bawah: {cta}. " if cta else "")
        + (f"Catatan tambahan: {extra}. " if extra else "")
        + ("Gunakan FOTO REFERENSI terlampir sebagai elemen visual utama (mis. foto hotel/destinasi), integrasikan secara natural. " if has_ref else "")
        + "Sertakan nuansa Islami/perjalanan yang relevan bila ini paket Umrah. JANGAN memuat jadwal/itinerary harian. PENTING: JANGAN menggambar logo apa pun, kotak/placeholder logo, atau tulisan 'LOGO'/'LOGO AGENCY'/'LOGO HERE'/'YOUR LOGO' — cukup sisakan area kosong polos di bagian ATAS (logo asli akan ditempel otomatis oleh sistem). Tata letak bersih dan profesional."
    )
    return p


async def _nano_banana_image(prompt, ref_imgs, session_tag):
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    import base64 as _b64
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"{session_tag}-{_uuid.uuid4()}",
                   system_message="You are a professional graphic designer creating travel brochure infographics.")
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
    msg = UserMessage(text=prompt, file_contents=[ImageContent(x) for x in ref_imgs]) if ref_imgs else UserMessage(text=prompt)
    _t, images = await chat.send_message_multimodal_response(msg)
    if not images:
        return None
    return _b64.b64decode(images[0]["data"])


@api_router.post("/packages/{pid}/brochures/generate-infographic")
async def generate_brochure_infographic(pid: str, body: dict, user: dict = Depends(require_permission("product.manage"))):
    pkg = await db.packages.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not pkg:
        raise HTTPException(status_code=404, detail="Package tidak ditemukan")
    variants = max(1, min(3, int(body.get("variants") or 1)))
    itins = await db.package_itineraries.find({"package_id": pid}).sort("day", 1).to_list(30)
    itin_txt = "; ".join(f"Hari {i.get('day')}: {i.get('activity') or i.get('location') or ''}" for i in itins[:8]) or "-"
    price = int(pkg.get("selling_price") or 0)
    theme = (body.get("theme") or "hijau elegan dengan aksen emas").strip()
    highlights = (body.get("highlights") or "").strip()
    promo = (body.get("promo") or "").strip()
    cta = (body.get("cta") or "").strip()
    extra = (body.get("extra") or "").strip()
    ref_imgs = await _brochure_reference_images(body.get("reference_ids"))
    info = await _get_doc_template()
    base_prompt = _brochure_prompt(pkg, itin_txt, price, theme, highlights, promo, cta, extra, bool(ref_imgs))
    styles = ["gaya modern minimalis dengan banyak white space", "gaya mewah elegan premium dengan aksen emas",
              "gaya cerah dinamis ramah keluarga dengan ilustrasi"]
    import asyncio as _asyncio
    prompts = [base_prompt + (f" Gunakan {styles[i % len(styles)]}." if variants > 1 else "") for i in range(variants)]
    results = await _asyncio.gather(*[_nano_banana_image(p, ref_imgs, f"brochure-{pid}") for p in prompts], return_exceptions=True)
    recs = []
    first_err = None
    for i, raw in enumerate(results):
        if isinstance(raw, Exception):
            first_err = first_err or raw
            continue
        if not raw:
            continue
        img_bytes = _stamp_brochure_image(raw, info, body)
        bid = str(_uuid.uuid4())
        path = f"{_APP_NAME}/brochures/{pid}/{bid}.png"
        result = put_object(path, img_bytes, "image/png")
        rec = {"id": bid, "package_id": pid, "kind": "AI", "storage_path": result["path"], "content_type": "image/png",
               "original_filename": f"brosur-ai-{(pkg.get('package_name') or 'paket')[:24]}-v{i + 1}.png",
               "size": result.get("size", len(img_bytes)), "is_deleted": False, "created_by": user["name"],
               "created_at": now_iso(), "gen_meta": {"theme": theme, "style": styles[i % len(styles)] if variants > 1 else theme,
               "highlights": highlights, "promo": promo, "cta": cta}}
        await db.package_brochures.insert_one(rec)
        recs.append(_brochure_out(rec))
    if not recs:
        raise HTTPException(status_code=502, detail=f"AI tidak menghasilkan gambar. {str(first_err)[:140] if first_err else 'Coba lagi atau ubah input.'}")
    return recs


@api_router.post("/packages/{pid}/brochures/generate-pdf")
async def generate_brochure_pdf(pid: str, body: dict, user: dict = Depends(require_permission("product.manage"))):
    pkg = await db.packages.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not pkg:
        raise HTTPException(status_code=404, detail="Package tidak ditemukan")
    itins = await db.package_itineraries.find({"package_id": pid}).sort("day", 1).to_list(50)
    itin_txt = "; ".join(f"Hari {i.get('day')}: {i.get('activity') or i.get('location') or ''}" for i in itins[:8]) or "-"
    price = int(pkg.get("selling_price") or 0)
    theme = (body.get("theme") or "hijau elegan dengan aksen emas").strip()
    highlights = (body.get("highlights") or "").strip()
    promo = (body.get("promo") or "").strip()
    cta = (body.get("cta") or "").strip()
    ref_imgs = await _brochure_reference_images(body.get("reference_ids"))
    info = await _get_doc_template()
    cover_prompt = _brochure_prompt(pkg, itin_txt, price, theme, highlights, promo, cta, "", bool(ref_imgs)) + " Fokus sebagai HALAMAN SAMPUL (cover) brosur."
    try:
        cover_raw = await _nano_banana_image(cover_prompt, ref_imgs, f"brochure-pdf-{pid}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal generate cover AI: {str(e)[:160]}")
    cover_bytes = _stamp_brochure_image(cover_raw, info, body) if cover_raw else None
    try:
        import io as _io
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas as _rcanvas
        buf = _io.BytesIO()
        c = _rcanvas.Canvas(buf, pagesize=A4)
        PW, PH = A4

        def footer():
            c.setFillColorRGB(0.06, 0.09, 0.16)
            c.rect(0, 0, PW, 16 * mm, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(12 * mm, 9 * mm, (info.get("company_name") or "Safar Travel")[:60])
            c.setFont("Helvetica", 8)
            c.setFillColorRGB(0.8, 0.85, 0.9)
            contact = "  |  ".join([v for v in [info.get("phone"), info.get("website"), info.get("address")] if v])
            c.drawString(12 * mm, 4.5 * mm, contact[:120])
            lb = _fetch_img_bytes(info.get("logo_url"))
            if lb:
                try:
                    c.drawImage(ImageReader(_io.BytesIO(lb)), PW - 32 * mm, 3.5 * mm, width=20 * mm, height=10 * mm, preserveAspectRatio=True, mask="auto")
                except Exception:
                    pass

        # Page 1: cover
        if cover_bytes:
            try:
                img = ImageReader(_io.BytesIO(cover_bytes))
                iw, ih = img.getSize()
                ratio = min((PW - 20 * mm) / iw, (PH - 40 * mm) / ih)
                dw, dh = iw * ratio, ih * ratio
                c.drawImage(img, (PW - dw) / 2, (PH - dh) / 2 + 8 * mm, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
        footer()
        c.showPage()

        # Page 2: harga & fasilitas
        c.setFillColorRGB(0.1, 0.1, 0.12); c.setFont("Helvetica-Bold", 18)
        c.drawString(15 * mm, PH - 25 * mm, "Harga & Fasilitas")
        y = PH - 38 * mm
        c.setFont("Helvetica", 12); c.setFillColorRGB(0.1, 0.1, 0.12)
        for lbl, val in [("Harga Dewasa / Pax", price), ("Harga Anak", pkg.get("child_price")), ("Harga Infant", pkg.get("infant_price"))]:
            if val:
                c.drawString(15 * mm, y, f"{lbl}: Rp{int(val):,}"); y -= 8 * mm
        if highlights:
            y -= 4 * mm; c.setFont("Helvetica-Bold", 12); c.drawString(15 * mm, y, "Highlight Fasilitas:"); y -= 7 * mm
            c.setFont("Helvetica", 10)
            for ln in [highlights[k:k + 90] for k in range(0, len(highlights), 90)][:6]:
                c.drawString(18 * mm, y, ln); y -= 6 * mm
        if promo:
            y -= 4 * mm; c.setFillColorRGB(0.85, 0.3, 0.1); c.setFont("Helvetica-Bold", 12)
            c.drawString(15 * mm, y, f"Promo: {promo[:80]}"); y -= 7 * mm
        if cta:
            c.setFillColorRGB(0.1, 0.45, 0.2); c.setFont("Helvetica-Bold", 12)
            c.drawString(15 * mm, y, cta[:90])
        footer()
        c.showPage()
        c.save()
        pdf_bytes = buf.getvalue()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal menyusun PDF: {str(e)[:160]}")
    bid = str(_uuid.uuid4())
    path = f"{_APP_NAME}/brochures/{pid}/{bid}.pdf"
    result = put_object(path, pdf_bytes, "application/pdf")
    rec = {"id": bid, "package_id": pid, "kind": "AI_PDF", "storage_path": result["path"], "content_type": "application/pdf",
           "original_filename": f"brosur-{(pkg.get('package_name') or 'paket')[:24]}.pdf", "size": result.get("size", len(pdf_bytes)),
           "is_deleted": False, "created_by": user["name"], "created_at": now_iso(),
           "gen_meta": {"theme": theme, "pages": ["cover", "harga"]}}
    await db.package_brochures.insert_one(rec)
    return _brochure_out(rec)


@api_router.post("/brochures/{bid}/regenerate")
async def regenerate_brochure(bid: str, body: dict, user: dict = Depends(require_permission("product.manage"))):
    b = await db.package_brochures.find_one({"id": bid, "is_deleted": {"$ne": True}})
    if not b:
        raise HTTPException(status_code=404, detail="Brosur tidak ditemukan")
    if b.get("kind") != "AI":
        raise HTTPException(status_code=400, detail="Hanya brosur gambar AI yang bisa diregenerate. Untuk PDF, gunakan Generate PDF.")
    pkg = await db.packages.find_one({"_id": ObjectId(b["package_id"])}) if ObjectId.is_valid(b["package_id"]) else None
    if not pkg:
        raise HTTPException(status_code=404, detail="Package tidak ditemukan")
    gm = b.get("gen_meta") or {}
    info = await _get_doc_template()
    prompt = _brochure_prompt(pkg, "", int(pkg.get("selling_price") or 0), gm.get("theme") or "elegan",
                              gm.get("highlights") or "", gm.get("promo") or "", gm.get("cta") or "", "", False)
    if gm.get("style"):
        prompt += f" Gunakan {gm.get('style')}."
    try:
        raw = await _nano_banana_image(prompt, [], f"regen-{bid}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal regenerate: {str(e)[:150]}")
    if not raw:
        raise HTTPException(status_code=502, detail="AI tidak menghasilkan gambar. Coba lagi.")
    img_bytes = _stamp_brochure_image(raw, info, {**gm, **(body or {})})
    path = f"{_APP_NAME}/brochures/{b['package_id']}/{bid}.png"
    result = put_object(path, img_bytes, "image/png")
    await db.package_brochures.update_one({"id": bid}, {"$set": {"storage_path": result["path"], "size": result.get("size", len(img_bytes)), "created_at": now_iso()}})
    return _brochure_out(await db.package_brochures.find_one({"id": bid}))


@api_router.post("/brochures/{bid}/set-primary")
async def set_primary_brochure(bid: str, user: dict = Depends(require_permission("product.manage"))):
    b = await db.package_brochures.find_one({"id": bid, "is_deleted": {"$ne": True}})
    if not b:
        raise HTTPException(status_code=404, detail="Brosur tidak ditemukan")
    await db.package_brochures.update_many({"package_id": b["package_id"]}, {"$set": {"is_primary": False}})
    await db.package_brochures.update_one({"id": bid}, {"$set": {"is_primary": True}})
    if (b.get("content_type") or "").startswith("image/"):
        url = f"{_public_base({})}/api/public/brochure/{bid}?sig={_brochure_sig(bid)}"
        await db.packages.update_one({"_id": ObjectId(b["package_id"])}, {"$set": {"cover_image": url}})
    return {"ok": True, "is_primary": True}


@api_router.post("/packages/{pid}/cover")
async def upload_package_cover(pid: str, file: UploadFile = File(...), user: dict = Depends(require_permission("product.manage"))):
    if not ObjectId.is_valid(pid) or not await db.packages.find_one({"_id": ObjectId(pid)}):
        raise HTTPException(status_code=404, detail="Package not found")
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    if ext not in ("jpg", "jpeg", "png", "webp"):
        raise HTTPException(status_code=400, detail="Format gambar harus JPG/PNG/WEBP")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran gambar maksimal 8MB")
    # Center-crop to 16:9 and resize so covers are always proportional
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(data)).convert("RGB")
        w, h = img.size
        target = 16 / 9
        if w / h > target:
            nw = int(h * target); x = (w - nw) // 2; img = img.crop((x, 0, x + nw, h))
        elif w / h < target:
            nh = int(w / target); y = (h - nh) // 2; img = img.crop((0, y, w, y + nh))
        if img.width > 1280:
            img = img.resize((1280, 720))
        buf = _io.BytesIO(); img.save(buf, format="JPEG", quality=85); data = buf.getvalue()
        ext = "jpg"; ctype = "image/jpeg"
    except Exception:
        ctype = file.content_type or f"image/{ext}"
    result = put_object(f"{_APP_NAME}/package_covers/{pid}.{ext}", data, ctype)
    import time as _t
    url = f"{_public_base({})}/api/public/package-cover/{pid}?v={int(_t.time())}"
    await db.packages.update_one({"_id": ObjectId(pid)}, {"$set": {
        "cover_storage_path": result["path"], "cover_content_type": ctype, "cover_image": url}})
    return {"cover_image": url}


@api_router.delete("/packages/{pid}/cover")
async def delete_package_cover(pid: str, user: dict = Depends(require_permission("product.manage"))):
    if not ObjectId.is_valid(pid):
        raise HTTPException(status_code=404, detail="Package not found")
    await db.packages.update_one({"_id": ObjectId(pid)}, {"$set": {"cover_image": "", "cover_storage_path": ""}})
    return {"ok": True}


@api_router.get("/public/package-cover/{pid}")
async def public_package_cover(pid: str):
    if not ObjectId.is_valid(pid):
        raise HTTPException(status_code=404, detail="Not found")
    p = await db.packages.find_one({"_id": ObjectId(pid)})
    if not p or not p.get("cover_storage_path"):
        raise HTTPException(status_code=404, detail="No cover")
    data, ct = get_object(p["cover_storage_path"])
    return Response(content=data, media_type=p.get("cover_content_type") or ct)


@api_router.get("/whatsapp/logs")
async def wa_logs(kind: str = "", user: dict = Depends(require_role("super_admin"))):
    q = {} if not kind else ({"kind": {"$ne": "API"}} if kind == "wa" else {"kind": kind})
    logs = await db.whatsapp_logs.find(q).sort("created_at", -1).to_list(300)
    return [serialize(l) for l in logs]


@api_router.get("/whatsapp/api-logs")
async def wa_api_logs(user: dict = Depends(require_role("super_admin"))):
    logs = await db.whatsapp_api_logs.find({}).sort("created_at", -1).to_list(300)
    return [serialize(l) for l in logs]


@api_router.post("/whatsapp/ai/simulate")
async def wa_ai_simulate(body: dict, user: dict = Depends(require_role("super_admin"))):
    msg = (body.get("message") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message wajib diisi")
    reset = bool(body.get("reset"))
    conv = await db.whatsapp_conversations.find_one({"wa_number": "628000000000"})
    if conv and reset:
        await db.whatsapp_messages.delete_many({"conversation_id": str(conv["_id"])})
        await db.whatsapp_conversations.delete_one({"_id": conv["_id"]})
        conv = None
    if not conv:
        conv, _c = await _wa_upsert_conversation("628000000000", "SIM Customer", created_by="AI AGENT")
        conv = await db.whatsapp_conversations.find_one({"_id": conv["_id"]})
    if conv.get("ai_status") != "ACTIVE":
        return {"conversation_id": str(conv["_id"]), "handover": True,
                "reason": "Conversation dalam status HANDOVER. Gunakan reset untuk mulai ulang.", "reply": None, "tools_used": []}
    convid = str(conv["_id"])
    await db.whatsapp_messages.insert_one({
        "message_id": f"sim-in-{now_iso()}", "conversation_id": convid, "account_id": conv.get("account_id", "apico"),
        "external_provider": APICO_PROVIDER, "sender": "CUSTOMER", "sender_type": "CUSTOMER", "receiver": "CRM",
        "direction": "INBOUND", "type": "text", "message_type": "text", "content": msg,
        "timestamp": now_iso(), "created_at": now_iso(), "ai_generated": False, "human_generated": False,
        "delivery_status": "RECEIVED", "status": "RECEIVED", "read_status": False, "simulated": True})
    result = await _wa_ai_journey(conv, msg, ctx_extra={"confirmed": bool(body.get("confirmed"))})
    if result.get("handover"):
        await _wa_handover(conv, result.get("reason") or "Eskalasi")
    elif result.get("reply"):
        await db.whatsapp_messages.insert_one({
            "message_id": f"sim-out-{now_iso()}", "conversation_id": convid, "account_id": conv.get("account_id", "apico"),
            "external_provider": APICO_PROVIDER, "sender": "AI", "sender_type": "AI", "receiver": conv["wa_number"],
            "direction": "OUTBOUND", "type": "text", "message_type": "text", "content": result["reply"],
            "timestamp": now_iso(), "created_at": now_iso(), "ai_generated": True, "human_generated": False,
            "delivery_status": "SENT", "status": "SENT", "read_status": False, "simulated": True})
    return {"conversation_id": convid, **result}


WA_HANDOVER_KEYWORDS = ["sales", "admin", "manusia", "customer service", " cs ", "komplain", "complain", "bicara dengan", "telepon", "hubungi saya", "orang asli", "marah", "kecewa", "keluhan", "refund", "batal", "pembatalan", "cancel", "permintaan khusus", "special request"]


async def _wa_ai_config():
    cfg = await db.whatsapp_ai_config.find_one({"_id": "main"})
    return cfg or {"_id": "main", "enabled": True, "knowledge": "",
                   "style": "Ramah, sopan, profesional, jawab singkat dalam Bahasa Indonesia.",
                   "rules": "Jangan mengarang harga di luar data. Jika tidak yakin, serahkan ke sales.",
                   "greeting": "", "handover_keywords": WA_HANDOVER_KEYWORDS}


async def _wa_pkg_context():
    pkgs = await db.packages.find({"status": {"$ne": "ARCHIVED"}}).to_list(20)
    lines = []
    for p in pkgs:
        seats = p.get("available_seats")
        lines.append(f"- {p.get('package_name')}: Rp{int(p.get('selling_price') or p.get('price') or 0):,} | {p.get('destination') or p.get('package_type') or ''} | durasi {p.get('duration','-')} | sisa kursi {seats if seats is not None else '-'}")
    return "\n".join(lines[:20]) or "(belum ada paket aktif)"


async def _wa_handover(conv, reason):
    await db.whatsapp_conversations.update_one({"_id": conv["_id"]}, {"$set": {
        "status": "HUMAN HANDOVER", "ai_status": "PAUSED", "handover_status": "PENDING", "last_activity": now_iso()}})
    sid = conv.get("assigned_sales_id")
    try:
        await create_task(f"WhatsApp Handover — {conv.get('customer_name')}", assigned_user_id=sid,
                          customer_id=conv.get("customer_id"), priority="HIGH",
                          notes=f"AI eskalasi ke sales: {reason}", created_by="AI Agent", source="whatsapp_handover")
    except Exception:
        pass
    await notify("WhatsApp Human Handover", f"{conv.get('customer_name')} butuh bantuan sales",
                 link="/whatsapp", user_id=sid, ntype="WHATSAPP_HANDOVER", priority="high")
    await _wa_log(conv["account_id"], "HANDOVER", "IN", str(conv["_id"]), True, reason)


def _journey_prompt(base, tool_catalog):
    return base + (
        "\n\nANDA AI SALES ASSISTANT WHATSAPP dengan alur CUSTOMER JOURNEY:\n"
        "(1) Customer baru → tanyakan nama & kebutuhannya, lalu buat Customer + Lead (Source WHATSAPP AI).\n"
        "(2) Jika customer tertarik → buat/perbarui Lead (paket, destinasi, tanggal, pax, budget bila ada).\n"
        "(3) Rekomendasikan paket sesuai destinasi/tanggal/pax/budget/ketersediaan. WAJIB CHECK_SEAT sebelum menyebut ketersediaan; JANGAN mengarang harga/seat.\n"
        "(4) Jika customer minta DIDAFTARKAN / BOOKING / INVOICE → kumpulkan data (nama, paket, pax, tanggal keberangkatan), lalu KONFIRMASI ringkas ke customer (mis. 'Saya daftarkan a.n. X, paket Y, 2 pax, brgkt Z, ya?'). Setelah customer menjawab YA, jalankan berurutan: (a) SEARCH_PACKAGE untuk memperoleh package_id & departure_id yang VALID (WAJIB — jangan menebak id), (b) CREATE_CUSTOMER bila customer baru (butuh full_name & whatsapp), (c) CREATE_LEAD, (d) CREATE_BOOKING dengan params.confirmed=true beserta customer_id, package_id, departure_id, pax. JANGAN membuat booking ulang bila pada percakapan ini booking sudah dibuat/terkonfirmasi — cukup gunakan GET_PAYMENT_STATUS/GET_BOOKING untuk nomor invoice & total; sistem juga otomatis mencegah booking duplikat. Semua otomatis ter-tag AUTO SALES.\n"
        "(5) DISKON: hanya bila diminta/relevan, sertakan discount_type ('PERCENT' atau 'NOMINAL') & discount_value di params CREATE_BOOKING. Sistem otomatis membatasi diskon ke maksimal per paket. WAJIB: setelah CREATE_BOOKING berhasil, sampaikan angka PERSIS dari OBSERVATION (invoice_number, discount_amount/discount_percent, total, payment_status) — JANGAN menyebut angka/persentase diskon versi Anda sendiri atau versi yang diminta customer bila berbeda dari OBSERVATION. Bila diskon yang diminta melebihi batas, jelaskan dengan sopan bahwa diskon yang dapat diberikan adalah yang tercantum di OBSERVATION. AI TIDAK PERNAH menandai LUNAS/PAID — status selalu 'Unpaid'; verifikasi pembayaran dilakukan admin.\n"
        "(6) STATUS/INVOICE/TAGIHAN: bila customer menanyakan invoice/total/status pembayaran, atau menyusul SETELAH booking dibuat, WAJIB panggil GET_PAYMENT_STATUS dengan customer_id (atau booking_id) untuk data aktual. JANGAN menjalankan CHECK_SEAT lagi dan JANGAN PERNAH mengatakan 'kursi/kuota penuh' kepada customer yang SUDAH memiliki booking — kursinya SUDAH direservasi untuknya. CHECK_SEAT hanya untuk pertanyaan ketersediaan pada booking BARU.\n"
        "(7) PERTANYAAN DISKON: bila customer menanyakan/meminta diskon, JANGAN eskalasi ke manusia. Cek field 'max_discount_value'/'discount_available'/'max_discount_note' dari SEARCH_PACKAGE/GET_PACKAGE paket terkait. Bila discount_available true → sampaikan batas diskon maksimal yang tersedia (sesuai max_discount_note) dengan sopan. Bila discount_available false / max_discount_value 0 → sampaikan dengan sopan bahwa 'belum ada diskon untuk paket ini saat ini' (JANGAN mengarang diskon). Saat CREATE_BOOKING, sistem otomatis membatasi diskon ke batas tsb.\n"
        "\nUNTUK MENGAKSES DATA/AKSI CRM, balas TEPAT satu baris diawali 'ACTION:' diikuti JSON, contoh:\n"
        "ACTION: {\"tool\":\"SEARCH_PACKAGE\",\"params\":{\"q\":\"umrah\"}}\n"
        "Sistem akan membalas 'OBSERVATION' lalu lanjutkan. Tool tersedia:\n" + tool_catalog +
        "\nEskalasi ke manusia — balas TEPAT '[HANDOVER] <alasan>' bila: customer minta sales/manusia, marah, komplain, refund, pembatalan, negosiasi harga, permintaan khusus, atau Anda tidak yakin.\n"
        "Jika sudah cukup menjawab customer, tulis pesan biasa (TANPA 'ACTION:')."
    )


async def _wa_ai_journey(conv, text, ctx_extra=None):
    import json as _jj
    import re as _rej
    cfg = await _wa_ai_config()
    kb = await _kb_build_context()
    base = _kb_system_prompt(kb, extra_style=cfg.get("style", ""), extra_rules=cfg.get("rules", ""), comm_block=await _comm_active_block())
    extra_know = (cfg.get("knowledge") or "").strip()
    if extra_know:
        base += f"\n\n=== PENGETAHUAN TAMBAHAN (WhatsApp) ===\n{extra_know}"
    tools = [t for t in AI_TOOL_REGISTRY if t["risk"] != "HIGH_RISK" and await _ai_tool_enabled(t["tool"])]
    catalog = "\n".join(f"- {t['tool']}: {t['label']}" for t in tools)
    sys = _journey_prompt(base, catalog)
    convo_id = str(conv["_id"])
    # Riwayat percakapan berjalan → agar AI tidak mengulang salam/penutup di tiap pesan
    hist_msgs = await db.whatsapp_messages.find({"conversation_id": convo_id}).sort("created_at", 1).to_list(1000)
    prior = [m for m in hist_msgs if (m.get("content") or "").strip()][-12:]
    is_first = not any(m.get("direction") == "OUTBOUND" for m in hist_msgs)
    hist_text = "\n".join(f"{'Customer' if m.get('direction') == 'INBOUND' else 'Anda (AI)'}: {(m.get('content') or '')[:300]}" for m in prior)
    sys += ("\n\n=== KONTEKS PERCAKAPAN YANG SEDANG BERLANGSUNG ===\n" + (hist_text or "(percakapan baru)")
            + "\n\nATURAN PERCAKAPAN (WAJIB): Ini percakapan WhatsApp yang SEDANG BERLANGSUNG. "
            + ("Ini pesan PERTAMA customer — beri salam pembuka SATU KALI secukupnya. " if is_first
               else "Customer SUDAH pernah disapa sebelumnya — JANGAN memberi salam/greeting pembuka lagi. ")
            + "JANGAN mengulang salam, perkenalan diri, atau kalimat penutup/closing yang sama di setiap pesan. "
            "Langsung tanggapi inti pesan TERAKHIR customer secara natural, seperti melanjutkan obrolan.")
    ctx = {"conversation_id": convo_id, "customer_id": conv.get("customer_id"), "confirmed": (ctx_extra or {}).get("confirmed")}
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"wa-j-{convo_id}", system_message=sys).with_model("gemini", "gemini-3-flash-preview")

    def _clean(r):
        out = [ln for ln in (r or "").splitlines() if not ln.strip().upper().startswith(("ACTION:", "OBSERVATION"))]
        return "\n".join(out).strip()

    tools_used = []
    turn = text or ""
    reply = ""
    for _ in range(6):
        reply = ((await chat.send_message(UserMessage(text=turn))) or "").strip()
        if "[HANDOVER]" in reply.upper():
            reason = reply.upper().split("[HANDOVER]", 1)[-1].strip(" ]:") or "Eskalasi ke sales"
            return {"handover": True, "reason": reason, "reply": None, "tools_used": tools_used}
        mm = _rej.search(r'ACTION:\s*(\{.*\})', reply, _rej.DOTALL)
        if mm:
            raw = mm.group(1)
            try:
                act = _jj.loads(raw)
            except Exception:
                act = None
            if not act:
                turn = ("Format ACTION tidak valid. Jika butuh data CRM, kirim ULANG tepat satu baris "
                        "ACTION JSON yang benar. Jika sudah cukup, jawab customer langsung TANPA menuliskan ACTION/JSON.")
                continue
            tool = (act.get("tool") or "").upper()
            params = act.get("params") or {}
            res = await _ai_tool_dispatch(tool, params, {**ctx, "confirmed": params.get("confirmed", ctx.get("confirmed")), "approved_by": "AI AGENT"})
            tools_used.append({"tool": tool, "ok": res.get("ok"), "summary": res.get("message") or res.get("error") or "ok"})
            turn = (f"OBSERVATION dari {tool}: {_jj.dumps(res)[:1500]}. Lanjutkan journey; jika sudah cukup, "
                    "balas ke customer dengan bahasa natural TANPA menulis ACTION/JSON/OBSERVATION.")
            continue
        cleaned = _clean(reply)
        if cleaned:
            return {"handover": False, "reply": cleaned, "tools_used": tools_used}
        turn = "Jawab customer langsung dengan bahasa natural (TANPA ACTION/JSON/OBSERVATION)."
    # Upaya terakhir: paksa jawaban langsung agar customer TIDAK pernah didiamkan
    reply = ((await chat.send_message(UserMessage(text="Sekarang jawab customer LANGSUNG dalam bahasa natural berdasarkan informasi yang sudah ada, TANPA menulis ACTION/JSON/OBSERVATION."))) or "").strip()
    cleaned = _clean(reply)
    if cleaned:
        return {"handover": False, "reply": cleaned, "tools_used": tools_used}
    return {"handover": False, "reply": "Mohon tunggu sebentar ya Kak, saya cek detailnya dulu dan segera saya kabari. 🙏", "tools_used": tools_used}


async def _wa_ai_process(conv_id, text):
    conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(conv_id)})
    if not conv or conv.get("ai_status") != "ACTIVE":
        return
    cfg = await _wa_ai_config()
    if not cfg.get("enabled", True):
        return
    low = (text or "").lower()
    if any(k.strip() in low for k in (cfg.get("handover_keywords") or WA_HANDOVER_KEYWORDS)):
        await _wa_handover(conv, "Customer meminta bantuan sales/manusia")
        return
    try:
        result = await _wa_ai_journey(conv, text)
    except Exception as e:
        await _wa_log(conv.get("account_id", "apico"), "AI", "IN", conv_id, False, str(e))
        return
    if result.get("handover"):
        await _wa_handover(conv, result.get("reason") or "AI eskalasi")
        return
    reply = result.get("reply")
    if not reply:
        await _wa_handover(conv, "AI tidak dapat menjawab")
        return
    allowed, _reason = await _wa_outbound_allowed(conv.get("customer_id"))
    if not allowed:
        await _wa_log(conv.get("account_id", "apico"), "AI", "OUT", conv_id, False, f"outbound blocked: {_reason}")
        return
    s = await _wa_safety()
    if not s.get("messaging_enabled", True):
        return
    if not _wa_business_open(s):
        beh = s.get("off_hours_behavior", "AUTO_RESPONSE")
        if beh == "HUMAN_HANDOVER":
            await _wa_handover(conv, "Di luar jam kerja")
            return
        if beh == "WAIT_UNTIL_BUSINESS_HOURS":
            reply = s.get("away_message") or reply
    # Follow-up cap: jangan kirim lebih dari max_followup pesan otomatis tanpa balasan customer
    last_in = await db.whatsapp_messages.find_one({"conversation_id": conv_id, "direction": "INBOUND"}, sort=[("created_at", -1)])
    since = (last_in or {}).get("created_at") or "1970-01-01"
    ai_out = await db.whatsapp_messages.count_documents({"conversation_id": conv_id, "direction": "OUTBOUND", "sender": "AI", "created_at": {"$gt": since}})
    q_pending = await db.whatsapp_outbound_queue.count_documents({"conversation_id": conv_id, "status": {"$in": ["QUEUED", "SENDING"]}})
    if (ai_out + q_pending) >= int(s.get("max_followup") or 2):
        await _wa_log(conv.get("account_id", "apico"), "FOLLOWUP_CAP", "OUT", conv_id, False, "max followup tercapai (menunggu balasan customer)")
        return
    # Masukkan balasan ke antrean outbound; background worker yang mengirim (rate-limit, typing, delay, splitting)
    await _wa_enqueue_outbound(conv, reply, sender="AI")


@api_router.get("/whatsapp/ai-config")
async def wa_get_ai_config(user: dict = Depends(require_role("super_admin"))):
    cfg = await _wa_ai_config()
    cfg.pop("_id", None)
    return cfg


@api_router.put("/whatsapp/ai-config")
async def wa_put_ai_config(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    upd = {k: body[k] for k in ("enabled", "knowledge", "style", "rules", "greeting", "handover_keywords") if k in body}
    await db.whatsapp_ai_config.update_one({"_id": "main"}, {"$set": upd}, upsert=True)
    await log_audit(user, "whatsapp", "update_ai_config", request, new={k: v for k, v in upd.items() if k != "knowledge"})
    cfg = await _wa_ai_config()
    cfg.pop("_id", None)
    return cfg


@api_router.post("/whatsapp/conversations/{cid}/resume-ai")
async def wa_resume_ai(cid: str, request: Request, user: dict = Depends(require_permission("sales.view"))):
    conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.whatsapp_conversations.update_one({"_id": conv["_id"]}, {"$set": {"ai_status": "ACTIVE", "status": "AI ACTIVE", "handover_status": "RESOLVED", "last_activity": now_iso()}})
    await _wa_log(conv["account_id"], "RESUME_AI", "IN", cid, True, f"by {user['name']}")
    return {"ai_status": "ACTIVE", "status": "AI ACTIVE"}


@api_router.post("/whatsapp/conversations/{cid}/handover")
async def wa_manual_handover(cid: str, body: dict, user: dict = Depends(require_permission("sales.view"))):
    conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await _wa_handover(conv, (body or {}).get("reason") or "Handover manual")
    return {"status": "HUMAN HANDOVER"}


# ============================================================================
# PHASE 10B — AI Knowledge Base Center (Super Admin)
# ============================================================================
KNOWLEDGE_CATEGORIES = [
    "PRODUCT", "PACKAGE TOUR", "PACKAGE UMRAH", "DESTINATION", "ITINERARY", "HOTEL",
    "AIRLINE", "VISA", "DOCUMENT", "PAYMENT", "REFUND", "CANCELLATION", "FAQ",
    "COMPANY INFORMATION", "TERMS & CONDITIONS", "CUSTOMER SERVICE", "OTHER",
]
ARTICLE_STATUSES = ["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"]
# Categories treated as "Active Company Policy" (priority 2, above FAQ)
KB_POLICY_CATS = {"COMPANY INFORMATION", "TERMS & CONDITIONS", "PAYMENT", "REFUND",
                  "CANCELLATION", "VISA", "DOCUMENT", "CUSTOMER SERVICE"}


def _kb_today():
    return datetime.now(timezone.utc).date().isoformat()


def _kb_date_active(doc, today=None):
    today = today or _kb_today()
    frm = (doc.get("effective_from") or "").strip()
    unt = (doc.get("effective_until") or "").strip()
    if frm and today < frm:
        return False
    if unt and today > unt:
        return False
    return True


async def _kb_active_articles():
    """Return ACTIVE articles that are within their effective window (sorted by priority desc)."""
    docs = await db.knowledge_articles.find({"status": "ACTIVE"}).to_list(500)
    out = [d for d in docs if _kb_date_active(d)]
    out.sort(key=lambda d: (d.get("priority") or 0), reverse=True)
    return out


async def _kb_active_faqs():
    docs = await db.knowledge_faqs.find({"status": "ACTIVE"}).to_list(500)
    return docs


async def _kb_package_knowledge(limit=50):
    """Assemble AI-usable package data directly from CRM Package Master (single source of truth)."""
    pkgs = await db.packages.find({"status": {"$ne": "ARCHIVED"}}).sort("created_at", -1).to_list(limit)
    out = []
    for p in pkgs:
        pid = str(p["_id"])
        deps = await db.departures.find({"package_id": pid}).sort("departure_date", 1).to_list(20)
        dep_rows = []
        for d in deps:
            if (d.get("status") or "").upper() in ("CANCELLED", "CLOSED"):
                continue
            dep_rows.append({
                "departure_date": d.get("departure_date"), "return_date": d.get("return_date"),
                "price": d.get("price") or p.get("selling_price"),
                "available_seat": d.get("available_seat"), "quota": d.get("quota"),
                "hotel": d.get("hotel"), "airline": d.get("flight"), "status": d.get("status"),
            })
        out.append({
            "id": pid, "package_name": p.get("package_name"), "package_code": p.get("package_code"),
            "package_type": p.get("product_type"), "sub_category": p.get("sub_category"),
            "destination": p.get("destination"), "country": p.get("country"),
            "duration": p.get("duration"), "selling_price": p.get("selling_price"),
            "child_price": p.get("child_price"), "infant_price": p.get("infant_price"),
            "description": p.get("description"), "terms": p.get("terms"),
            "status": p.get("status"), "departures": dep_rows,
        })
    return out


async def _kb_build_context():
    """Build prioritized context blocks + the lists of sources actually used (for preview)."""
    pkgs = await _kb_package_knowledge(limit=40)
    articles = await _kb_active_articles()
    faqs = await _kb_active_faqs()

    pkg_lines, pkg_used = [], []
    for p in pkgs:
        deps = p.get("departures") or []
        if deps:
            dep_txt = "; ".join(
                f"{d.get('departure_date','-')}→{d.get('return_date','-')} | Rp{int(d.get('price') or 0):,} | sisa kursi {d.get('available_seat') if d.get('available_seat') is not None else '-'}"
                for d in deps[:6])
        else:
            dep_txt = "(belum ada jadwal keberangkatan)"
        pkg_lines.append(
            f"- [{p.get('package_code','')}] {p.get('package_name','')} | tipe {p.get('package_type') or ''}/{p.get('sub_category') or ''} | "
            f"destinasi {p.get('destination') or '-'} | durasi {p.get('duration') or '-'} | harga dasar Rp{int(p.get('selling_price') or 0):,} | "
            f"status {p.get('status')}\n    Jadwal: {dep_txt}")
        pkg_used.append({"id": p["id"], "package_name": p.get("package_name"), "package_code": p.get("package_code")})

    policy_lines, general_lines, kn_used = [], [], []
    for a in articles:
        block = f"- ({a.get('category')}) {a.get('title')}: {a.get('content')}"
        if (a.get("category") or "") in KB_POLICY_CATS:
            policy_lines.append(block)
        else:
            general_lines.append(block)
        kn_used.append({"id": str(a["_id"]), "title": a.get("title"), "category": a.get("category"),
                        "type": "ARTICLE", "version": a.get("version", 1)})

    faq_lines = []
    for f in faqs:
        faq_lines.append(f"- Q: {f.get('question')}\n  A: {f.get('answer')}")
        kn_used.append({"id": str(f["_id"]), "title": f.get("question"), "category": f.get("category"),
                        "type": "FAQ"})

    return {
        "pkg_text": "\n".join(pkg_lines) or "(belum ada paket aktif)",
        "policy_text": "\n".join(policy_lines) or "(belum ada kebijakan perusahaan aktif)",
        "faq_text": "\n".join(faq_lines) or "(belum ada FAQ aktif)",
        "general_text": "\n".join(general_lines) or "(belum ada pengetahuan umum aktif)",
        "package_used": pkg_used, "knowledge_used": kn_used,
    }


def _kb_system_prompt(ctx, extra_style="", extra_rules="", comm_block=""):
    intro = ("Anda adalah AI Assistant untuk agen travel umroh, haji & tour. "
             + ("Jawab dengan ringkas, sopan, dan profesional.\n" if comm_block
                else "Jawab dalam Bahasa Indonesia yang ringkas, sopan, dan profesional.\n"))
    return (
        intro
        + (comm_block + "\n\n" if comm_block else "")
        + f"{('Gaya: ' + extra_style + chr(10)) if extra_style else ''}"
        f"{('Aturan tambahan: ' + extra_rules + chr(10)) if extra_rules else ''}"
        "URUTAN PRIORITAS SUMBER JAWABAN: (1) DATA PAKET terkini, (2) Kebijakan Perusahaan aktif, "
        "(3) FAQ aktif, (4) Pengetahuan umum aktif. Jika ada informasi baru yang aktif, JANGAN gunakan informasi lama.\n"
        "ATURAN KERAS — JANGAN MENGARANG: harga, sisa kursi (seat), jadwal keberangkatan, itinerary, hotel, "
        "maskapai, visa, atau kebijakan perusahaan. Gunakan HANYA data yang tersedia di bawah ini. "
        "Jika informasi yang diminta TIDAK tersedia dalam data, katakan dengan jujur bahwa informasi belum tersedia "
        "dan sarankan agar customer dihubungkan dengan tim sales (human handover). Jangan menebak.\n\n"
        f"=== DATA PAKET (SUMBER UTAMA) ===\n{ctx['pkg_text']}\n\n"
        f"=== KEBIJAKAN PERUSAHAAN AKTIF ===\n{ctx['policy_text']}\n\n"
        f"=== FAQ AKTIF ===\n{ctx['faq_text']}\n\n"
        f"=== PENGETAHUAN UMUM AKTIF ===\n{ctx['general_text']}"
    )


# ---- Categories ----
@api_router.get("/knowledge/categories")
async def kb_categories(user: dict = Depends(require_role("super_admin"))):
    return {"categories": KNOWLEDGE_CATEGORIES, "article_statuses": ARTICLE_STATUSES}


# ---- Articles ----
@api_router.get("/knowledge/articles")
async def kb_list_articles(category: str = "", status: str = "", q: str = "",
                           user: dict = Depends(require_role("super_admin"))):
    query = {}
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    if q:
        rx = {"$regex": _re.escape(q), "$options": "i"}
        query["$or"] = [{"title": rx}, {"content": rx}]
    docs = await db.knowledge_articles.find(query).sort("updated_at", -1).to_list(500)
    for d in docs:
        d["is_effective_now"] = _kb_date_active(d)
    return [serialize(d) for d in docs]


@api_router.get("/knowledge/articles/{aid}")
async def kb_get_article(aid: str, user: dict = Depends(require_role("super_admin"))):
    doc = await db.knowledge_articles.find_one({"_id": ObjectId(aid)}) if ObjectId.is_valid(aid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Artikel tidak ditemukan")
    return serialize(doc)


@api_router.post("/knowledge/articles")
async def kb_create_article(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    cat = (body.get("category") or "OTHER").strip()
    if cat not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Kategori tidak valid")
    st = (body.get("status") or "DRAFT").strip().upper()
    if st not in ARTICLE_STATUSES:
        raise HTTPException(status_code=400, detail="Status tidak valid")
    doc = {
        "title": (body.get("title") or "").strip(), "category": cat, "content": body.get("content") or "",
        "status": st, "priority": int(body.get("priority") or 0),
        "effective_from": (body.get("effective_from") or "").strip(),
        "effective_until": (body.get("effective_until") or "").strip(),
        "version": 1, "history": [], "created_at": now_iso(), "created_by": user["name"],
        "updated_at": now_iso(), "updated_by": user["name"],
    }
    if not doc["title"]:
        raise HTTPException(status_code=400, detail="Judul wajib diisi")
    r = await db.knowledge_articles.insert_one(doc)
    await log_audit(user, "knowledge", "create_article", request, record_id=str(r.inserted_id), new={"title": doc["title"], "category": cat})
    return serialize(await db.knowledge_articles.find_one({"_id": r.inserted_id}))


@api_router.put("/knowledge/articles/{aid}")
async def kb_update_article(aid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.knowledge_articles.find_one({"_id": ObjectId(aid)}) if ObjectId.is_valid(aid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Artikel tidak ditemukan")
    # snapshot previous version (never delete history)
    snapshot = {"version": doc.get("version", 1), "title": doc.get("title"), "category": doc.get("category"),
                "content": doc.get("content"), "status": doc.get("status"), "priority": doc.get("priority"),
                "effective_from": doc.get("effective_from"), "effective_until": doc.get("effective_until"),
                "updated_by": doc.get("updated_by"), "updated_at": doc.get("updated_at")}
    upd = {}
    for k in ("title", "content", "priority"):
        if k in body:
            upd[k] = int(body[k]) if k == "priority" else body[k]
    if "category" in body:
        if body["category"] not in KNOWLEDGE_CATEGORIES:
            raise HTTPException(status_code=400, detail="Kategori tidak valid")
        upd["category"] = body["category"]
    if "status" in body:
        st = (body["status"] or "").upper()
        if st not in ARTICLE_STATUSES:
            raise HTTPException(status_code=400, detail="Status tidak valid")
        upd["status"] = st
    for k in ("effective_from", "effective_until"):
        if k in body:
            upd[k] = (body[k] or "").strip()
    upd["version"] = doc.get("version", 1) + 1
    upd["updated_at"] = now_iso()
    upd["updated_by"] = user["name"]
    await db.knowledge_articles.update_one({"_id": doc["_id"]}, {"$set": upd, "$push": {"history": snapshot}})
    await log_audit(user, "knowledge", "update_article", request, record_id=aid, old=snapshot, new={k: v for k, v in upd.items() if k != "version"})
    return serialize(await db.knowledge_articles.find_one({"_id": doc["_id"]}))


@api_router.get("/knowledge/articles/{aid}/versions")
async def kb_article_versions(aid: str, user: dict = Depends(require_role("super_admin"))):
    doc = await db.knowledge_articles.find_one({"_id": ObjectId(aid)}) if ObjectId.is_valid(aid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Artikel tidak ditemukan")
    return {"current_version": doc.get("version", 1), "history": list(reversed(doc.get("history") or []))}


@api_router.delete("/knowledge/articles/{aid}")
async def kb_archive_article(aid: str, request: Request, reason: str = "", user: dict = Depends(require_role("super_admin"))):
    doc = await db.knowledge_articles.find_one({"_id": ObjectId(aid)}) if ObjectId.is_valid(aid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Artikel tidak ditemukan")
    snapshot = {"version": doc.get("version", 1), "title": doc.get("title"), "content": doc.get("content"),
                "status": doc.get("status"), "updated_by": doc.get("updated_by"), "updated_at": doc.get("updated_at")}
    await db.knowledge_articles.update_one({"_id": doc["_id"]}, {
        "$set": {"status": "ARCHIVED", "version": doc.get("version", 1) + 1, "updated_at": now_iso(), "updated_by": user["name"]},
        "$push": {"history": snapshot}})
    await log_audit(user, "knowledge", "archive_article", request, record_id=aid, reason=reason or "archived")
    return {"ok": True, "status": "ARCHIVED"}


# ---- FAQ ----
@api_router.get("/knowledge/faqs")
async def kb_list_faqs(category: str = "", status: str = "", q: str = "",
                       user: dict = Depends(require_role("super_admin"))):
    query = {}
    if category:
        query["category"] = category
    if status:
        query["status"] = status
    if q:
        rx = {"$regex": _re.escape(q), "$options": "i"}
        query["$or"] = [{"question": rx}, {"answer": rx}, {"keywords": rx}]
    docs = await db.knowledge_faqs.find(query).sort("updated_at", -1).to_list(500)
    return [serialize(d) for d in docs]


@api_router.post("/knowledge/faqs")
async def kb_create_faq(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    cat = (body.get("category") or "FAQ").strip()
    if cat not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Kategori tidak valid")
    kws = body.get("keywords")
    if isinstance(kws, str):
        kws = [k.strip() for k in kws.split(",") if k.strip()]
    doc = {"question": (body.get("question") or "").strip(), "answer": body.get("answer") or "",
           "category": cat, "keywords": kws or [], "status": (body.get("status") or "ACTIVE").upper(),
           "created_at": now_iso(), "created_by": user["name"], "updated_at": now_iso(), "updated_by": user["name"]}
    if not doc["question"]:
        raise HTTPException(status_code=400, detail="Pertanyaan wajib diisi")
    r = await db.knowledge_faqs.insert_one(doc)
    await log_audit(user, "knowledge", "create_faq", request, record_id=str(r.inserted_id), new={"question": doc["question"]})
    return serialize(await db.knowledge_faqs.find_one({"_id": r.inserted_id}))


@api_router.put("/knowledge/faqs/{fid}")
async def kb_update_faq(fid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.knowledge_faqs.find_one({"_id": ObjectId(fid)}) if ObjectId.is_valid(fid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="FAQ tidak ditemukan")
    upd = {}
    for k in ("question", "answer"):
        if k in body:
            upd[k] = body[k]
    if "category" in body and body["category"] in KNOWLEDGE_CATEGORIES:
        upd["category"] = body["category"]
    if "status" in body:
        upd["status"] = (body["status"] or "").upper()
    if "keywords" in body:
        kws = body["keywords"]
        if isinstance(kws, str):
            kws = [k.strip() for k in kws.split(",") if k.strip()]
        upd["keywords"] = kws or []
    upd["updated_at"] = now_iso()
    upd["updated_by"] = user["name"]
    await db.knowledge_faqs.update_one({"_id": doc["_id"]}, {"$set": upd})
    await log_audit(user, "knowledge", "update_faq", request, record_id=fid, new={k: v for k, v in upd.items() if k in ("question", "status")})
    return serialize(await db.knowledge_faqs.find_one({"_id": doc["_id"]}))


@api_router.delete("/knowledge/faqs/{fid}")
async def kb_delete_faq(fid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.knowledge_faqs.find_one({"_id": ObjectId(fid)}) if ObjectId.is_valid(fid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="FAQ tidak ditemukan")
    await db.knowledge_faqs.delete_one({"_id": doc["_id"]})
    await log_audit(user, "knowledge", "delete_faq", request, record_id=fid)
    return {"ok": True}


# ---- Package Knowledge (read-only view of CRM data the AI can use) ----
@api_router.get("/knowledge/packages")
async def kb_packages(user: dict = Depends(require_role("super_admin"))):
    return await _kb_package_knowledge(limit=100)


# ---- Test AI Knowledge ----
@api_router.post("/knowledge/test-ai")
async def kb_test_ai(body: dict, user: dict = Depends(require_role("super_admin"))):
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Pertanyaan wajib diisi")
    ctx = await _kb_build_context()
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sys = _kb_system_prompt(ctx, comm_block=await _comm_active_block())
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"kb-test-{now_iso()}",
                       system_message=sys).with_model("gemini", "gemini-3-flash-preview")
        answer = ((await chat.send_message(UserMessage(text=question))) or "").strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI tidak dapat memproses: {str(e)[:200]}")
    return {
        "answer": answer or "Maaf, informasi belum tersedia. Silakan dihubungkan dengan tim sales kami.",
        "knowledge_used": ctx["knowledge_used"],
        "package_used": ctx["package_used"],
        "source_data": {
            "packages_count": len(ctx["package_used"]),
            "knowledge_count": len(ctx["knowledge_used"]),
        },
    }


# ============================================================================
# PHASE 10C — AI Communication Style, Personality & Brand Voice (Super Admin)
# ============================================================================
COMM_TONES = ["Friendly", "Professional", "Warm", "Helpful", "Casual", "Formal"]
COMM_LANGUAGES = ["AUTO", "ID", "EN"]
COMM_EMOJI = ["OFF", "LIMITED", "NORMAL"]
COMM_LENGTH = ["SHORT", "MEDIUM", "DETAILED"]
COMM_STATUSES = ["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"]
COMM_DEFAULTS = {
    "language": "AUTO", "tone": ["Friendly", "Professional", "Helpful"], "emoji_usage": "LIMITED",
    "response_length": "MEDIUM", "formality": "", "personality": "", "greeting_style": "",
    "closing_style": "", "sales_style": "", "brand_voice": "", "examples": [], "do_list": [], "dont_list": [],
}


def _comm_style_block(p):
    """Build the brand-voice / communication instruction text from a profile dict."""
    if not p:
        return ""
    tones = ", ".join(p.get("tone") or []) or "Friendly, Professional, Helpful"
    lang = {
        "AUTO": "Deteksi bahasa customer (Bahasa Indonesia atau English) dan balas dalam bahasa yang SAMA. Jangan berpindah bahasa tanpa alasan.",
        "ID": "Selalu balas dalam Bahasa Indonesia.",
        "EN": "Always reply in English.",
    }.get(p.get("language", "AUTO"), "Deteksi bahasa customer dan balas dalam bahasa yang sama.")
    emoji = {
        "OFF": "Jangan gunakan emoji sama sekali.",
        "LIMITED": "Gunakan emoji secukupnya (maksimal satu bila benar-benar perlu).",
        "NORMAL": "Boleh gunakan emoji wajar, tidak berlebihan.",
    }.get(p.get("emoji_usage", "LIMITED"))
    length = {
        "SHORT": "Jawaban singkat, 1-2 kalimat.",
        "MEDIUM": "Jawaban ringkas & mudah dibaca di WhatsApp; hindari paragraf terlalu panjang.",
        "DETAILED": "Jawaban lebih lengkap namun tetap terstruktur dan mudah dibaca.",
    }.get(p.get("response_length", "MEDIUM"))
    parts = [
        f"=== GAYA KOMUNIKASI & BRAND VOICE (profil: {p.get('profile_name') or '-'}) ===",
        f"Bahasa: {lang}",
        f"Tone: {tones}." + (f" Formality: {p.get('formality')}." if p.get('formality') else "") + (f" Kepribadian: {p.get('personality')}." if p.get('personality') else ""),
    ]
    if p.get("brand_voice"):
        parts.append(f"Brand voice perusahaan: {p.get('brand_voice')}")
    parts.append(f"Emoji: {emoji}")
    parts.append(f"Panjang jawaban: {length}")
    parts.append(
        "Gaya sales: consultative selling" + (f" — {p.get('sales_style')}" if p.get('sales_style') else "") +
        ". JANGAN memaksa, spam, memberi tekanan, membuat klaim palsu, mengatakan 'pasti', atau 'termurah' tanpa data. "
        "Pahami kebutuhan, tanyakan jumlah pax/tanggal/budget bila relevan, rekomendasikan paket yang sesuai, dan transparan.")
    if p.get("greeting_style"):
        parts.append(f"Greeting: {p.get('greeting_style')} — jangan mengulang greeting yang sama berkali-kali dalam satu percakapan.")
    if p.get("closing_style"):
        parts.append(f"Closing: {p.get('closing_style')}")
    do = p.get("do_list") or []
    dont = p.get("dont_list") or []
    if do:
        parts.append("DO: " + "; ".join(do))
    if dont:
        parts.append("DON'T: " + "; ".join(dont))
    ex = p.get("examples") or []
    if ex:
        parts.append("CONTOH KOMUNIKASI IDEAL (tiru GAYA-nya, bukan menyalin isinya):")
        for e in ex[:8]:
            if (e.get("customer") or e.get("ideal_ai")):
                parts.append(f"- Customer: {e.get('customer','')}\n  AI ideal: {e.get('ideal_ai','')}")
    parts.append("Personalisasi: gunakan nama customer bila dikenal & sesuai konteks, TETAPI jangan berlebihan menyebut nama di setiap pesan.")
    parts.append("ALUR RESPONS WAJIB: (1) Pahami, (2) Ambil data, (3) Validasi, (4) Jawab, (5) Tawarkan langkah berikutnya. "
                 "JANGAN pernah mengaku sebagai manusia. JANGAN memberikan informasi yang belum pasti.")
    return "\n".join(parts)


async def _comm_get_active():
    return await db.communication_profiles.find_one({"status": "ACTIVE"})


async def _comm_active_block():
    return _comm_style_block(await _comm_get_active())


def _comm_sanitize(body):
    tone = body.get("tone")
    if isinstance(tone, str):
        tone = [t.strip() for t in tone.split(",") if t.strip()]
    tone = [t for t in (tone or []) if t in COMM_TONES]

    def _lines(v):
        if isinstance(v, str):
            return [x.strip() for x in v.splitlines() if x.strip()]
        return [str(x).strip() for x in (v or []) if str(x).strip()]

    ex = []
    for e in (body.get("examples") or []):
        if isinstance(e, dict) and (e.get("customer") or e.get("ideal_ai")):
            ex.append({"customer": e.get("customer", ""), "ideal_ai": e.get("ideal_ai", "")})
    return {
        "profile_name": (body.get("profile_name") or "").strip(),
        "language": body.get("language") if body.get("language") in COMM_LANGUAGES else "AUTO",
        "tone": tone or ["Friendly", "Professional", "Helpful"],
        "formality": body.get("formality") or "", "personality": body.get("personality") or "",
        "greeting_style": body.get("greeting_style") or "", "closing_style": body.get("closing_style") or "",
        "emoji_usage": body.get("emoji_usage") if body.get("emoji_usage") in COMM_EMOJI else "LIMITED",
        "response_length": body.get("response_length") if body.get("response_length") in COMM_LENGTH else "MEDIUM",
        "sales_style": body.get("sales_style") or "", "brand_voice": body.get("brand_voice") or "",
        "examples": ex, "do_list": _lines(body.get("do_list")), "dont_list": _lines(body.get("dont_list")),
    }


@api_router.get("/communication/meta")
async def comm_meta(user: dict = Depends(require_role("super_admin"))):
    return {"tones": COMM_TONES, "languages": COMM_LANGUAGES, "emoji": COMM_EMOJI,
            "lengths": COMM_LENGTH, "statuses": COMM_STATUSES, "defaults": COMM_DEFAULTS}


@api_router.get("/communication/profiles")
async def comm_list(user: dict = Depends(require_role("super_admin"))):
    docs = await db.communication_profiles.find({"status": {"$ne": "ARCHIVED"}}).sort("updated_at", -1).to_list(200)
    return [serialize(d) for d in docs]


@api_router.get("/communication/profiles/{pid}")
async def comm_get(pid: str, user: dict = Depends(require_role("super_admin"))):
    doc = await db.communication_profiles.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Profil tidak ditemukan")
    return serialize(doc)


@api_router.post("/communication/profiles")
async def comm_create(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    data = _comm_sanitize(body)
    if not data["profile_name"]:
        raise HTTPException(status_code=400, detail="Nama profil wajib diisi")
    want_active = (body.get("status") or "DRAFT").upper() == "ACTIVE"
    data.update({"status": "ACTIVE" if want_active else "DRAFT", "version": 1, "history": [],
                 "created_at": now_iso(), "created_by": user["name"], "updated_at": now_iso(), "updated_by": user["name"]})
    if want_active:
        await db.communication_profiles.update_many({"status": "ACTIVE"}, {"$set": {"status": "INACTIVE"}})
    r = await db.communication_profiles.insert_one(data)
    await log_audit(user, "communication", "create_profile", request, record_id=str(r.inserted_id), new={"profile_name": data["profile_name"]})
    return serialize(await db.communication_profiles.find_one({"_id": r.inserted_id}))


@api_router.put("/communication/profiles/{pid}")
async def comm_update(pid: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.communication_profiles.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Profil tidak ditemukan")
    snapshot = {k: doc.get(k) for k in ("profile_name", "language", "tone", "formality", "personality",
                "greeting_style", "closing_style", "emoji_usage", "response_length", "sales_style",
                "brand_voice", "examples", "do_list", "dont_list", "status")}
    snapshot["version"] = doc.get("version", 1)
    snapshot["updated_by"] = doc.get("updated_by")
    snapshot["updated_at"] = doc.get("updated_at")
    data = _comm_sanitize(body)
    if not data["profile_name"]:
        raise HTTPException(status_code=400, detail="Nama profil wajib diisi")
    data.update({"version": doc.get("version", 1) + 1, "updated_at": now_iso(), "updated_by": user["name"]})
    await db.communication_profiles.update_one({"_id": doc["_id"]}, {"$set": data, "$push": {"history": snapshot}})
    await log_audit(user, "communication", "update_profile", request, record_id=pid, old=snapshot, new={"profile_name": data["profile_name"]})
    return serialize(await db.communication_profiles.find_one({"_id": doc["_id"]}))


@api_router.post("/communication/profiles/{pid}/activate")
async def comm_activate(pid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.communication_profiles.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Profil tidak ditemukan")
    await db.communication_profiles.update_many({"status": "ACTIVE"}, {"$set": {"status": "INACTIVE"}})
    await db.communication_profiles.update_one({"_id": doc["_id"]}, {"$set": {"status": "ACTIVE", "updated_at": now_iso(), "updated_by": user["name"]}})
    await log_audit(user, "communication", "activate_profile", request, record_id=pid)
    return {"ok": True, "status": "ACTIVE"}


@api_router.get("/communication/profiles/{pid}/versions")
async def comm_versions(pid: str, user: dict = Depends(require_role("super_admin"))):
    doc = await db.communication_profiles.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Profil tidak ditemukan")
    return {"current_version": doc.get("version", 1), "history": list(reversed(doc.get("history") or []))}


@api_router.delete("/communication/profiles/{pid}")
async def comm_archive(pid: str, request: Request, user: dict = Depends(require_role("super_admin"))):
    doc = await db.communication_profiles.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
    if not doc:
        raise HTTPException(status_code=404, detail="Profil tidak ditemukan")
    await db.communication_profiles.update_one({"_id": doc["_id"]}, {"$set": {"status": "ARCHIVED", "updated_at": now_iso(), "updated_by": user["name"]}})
    await log_audit(user, "communication", "archive_profile", request, record_id=pid)
    return {"ok": True, "status": "ARCHIVED"}


@api_router.post("/communication/preview")
async def comm_preview(body: dict, user: dict = Depends(require_role("super_admin"))):
    msg = (body.get("customer_message") or body.get("question") or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Pesan customer wajib diisi")
    if body.get("profile"):
        prof = _comm_sanitize(body["profile"])
        prof["profile_name"] = body["profile"].get("profile_name") or "Preview"
    elif body.get("profile_id") and ObjectId.is_valid(body["profile_id"]):
        prof = await db.communication_profiles.find_one({"_id": ObjectId(body["profile_id"])})
    else:
        prof = await _comm_get_active()
    ctx = await _kb_build_context()
    comm = _comm_style_block(prof)
    cust_name = (body.get("customer_name") or "").strip()
    if cust_name:
        comm += f"\nNama customer yang sedang chat: {cust_name} (gunakan seperlunya)."
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        sys = _kb_system_prompt(ctx, comm_block=comm)
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"comm-{now_iso()}",
                       system_message=sys).with_model("gemini", "gemini-3-flash-preview")
        answer = ((await chat.send_message(UserMessage(text=msg))) or "").strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI tidak dapat memproses: {str(e)[:200]}")
    return {"answer": answer or "Maaf, informasi belum tersedia. Boleh saya bantu hubungkan dengan tim sales kami?",
            "profile_used": (prof or {}).get("profile_name") if prof else None,
            "knowledge_used": ctx["knowledge_used"], "package_used": ctx["package_used"]}


# ============================================================================
# PHASE 10D — AI Agent CRM Tools & Actions (Super Admin)
# AI interacts with CRM ONLY through this secure tool layer (no direct DB access).
# ============================================================================
AI_TOOL_REGISTRY = [
    # READ
    {"tool": "SEARCH_CUSTOMER", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Search Customer"},
    {"tool": "GET_CUSTOMER", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get Customer"},
    {"tool": "SEARCH_PACKAGE", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Search Package"},
    {"tool": "GET_PACKAGE", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get Package"},
    {"tool": "GET_ITINERARY", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get Itinerary"},
    {"tool": "CHECK_SEAT", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Check Seat Availability"},
    {"tool": "GET_DEPARTURE", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get Departure"},
    {"tool": "GET_PAYMENT_STATUS", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get Payment Status"},
    {"tool": "GET_BOOKING", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get Booking"},
    {"tool": "GET_FAQ", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get FAQ"},
    {"tool": "GET_COMPANY_POLICY", "type": "READ", "risk": "NORMAL", "confirm": False, "label": "Get Company Policy"},
    # WRITE
    {"tool": "CREATE_CUSTOMER", "type": "WRITE", "risk": "NORMAL", "confirm": False, "label": "Create Customer"},
    {"tool": "UPDATE_CUSTOMER", "type": "WRITE", "risk": "NORMAL", "confirm": False, "label": "Update Customer"},
    {"tool": "CREATE_LEAD", "type": "WRITE", "risk": "NORMAL", "confirm": False, "label": "Create Lead"},
    {"tool": "CREATE_ORDER", "type": "WRITE", "risk": "TRANSACTIONAL", "confirm": True, "label": "Create Order"},
    {"tool": "CREATE_BOOKING", "type": "WRITE", "risk": "TRANSACTIONAL", "confirm": True, "label": "Create Booking"},
    {"tool": "CREATE_FOLLOWUP", "type": "WRITE", "risk": "NORMAL", "confirm": False, "label": "Create Follow Up"},
    {"tool": "ASSIGN_SALES", "type": "WRITE", "risk": "NORMAL", "confirm": False, "label": "Assign Sales"},
    {"tool": "REQUEST_HUMAN_HANDOVER", "type": "WRITE", "risk": "NORMAL", "confirm": False, "label": "Request Human Handover"},
    # HIGH RISK — AI may only create an approval REQUEST, never execute directly
    {"tool": "CANCEL_BOOKING", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Cancel Booking"},
    {"tool": "REFUND", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Refund"},
    {"tool": "CHANGE_PRICE", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Change Price"},
    {"tool": "CHANGE_HPP", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Change HPP"},
    {"tool": "CHANGE_TAX", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Change Tax"},
    {"tool": "CHANGE_COMMISSION", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Change Commission"},
    {"tool": "CHANGE_ACCOUNTING", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Change Accounting"},
    {"tool": "DELETE_TRANSACTION", "type": "WRITE", "risk": "HIGH_RISK", "confirm": True, "label": "Delete Transaction"},
]
AI_TOOL_MAP = {t["tool"]: t for t in AI_TOOL_REGISTRY}


async def _ai_tool_enabled(tool):
    doc = await db.ai_tool_permissions.find_one({"tool": tool})
    if doc is not None:
        return bool(doc.get("enabled", True))
    return True  # default enabled; Super Admin can disable


async def _ai_audit(tool, params, result, ok, ctx, approval_required=False):
    await db.ai_action_logs.insert_one({
        "agent": "AI AGENT", "conversation_id": (ctx or {}).get("conversation_id"),
        "customer_id": (ctx or {}).get("customer_id"), "tool": tool,
        "parameters": params if isinstance(params, dict) else {}, "result": (result if isinstance(result, dict) else {"value": str(result)[:500]}),
        "ok": bool(ok), "approval_required": bool(approval_required),
        "user_approval": (ctx or {}).get("approved_by"), "timestamp": now_iso()})


def _ai_pkg_public(p):
    _mdt = (p.get("max_discount_type") or "PERCENT").upper()
    _mdv = float(p.get("max_discount_value") or 0)
    return {"id": str(p["_id"]), "package_name": p.get("package_name"), "package_code": p.get("package_code"),
            "package_type": p.get("product_type"), "sub_category": p.get("sub_category"),
            "destination": p.get("destination"), "country": p.get("country"), "duration": p.get("duration"),
            "selling_price": p.get("selling_price"), "child_price": p.get("child_price"),
            "infant_price": p.get("infant_price"), "description": p.get("description"),
            "max_discount_type": _mdt, "max_discount_value": _mdv,
            "discount_available": _mdv > 0,
            "max_discount_note": (f"Maksimal diskon {int(_mdv)}%" if _mdt == "PERCENT" else f"Maksimal diskon Rp{int(_mdv):,}") if _mdv > 0 else "Belum ada diskon untuk paket ini saat ini",
            "terms": p.get("terms"), "status": p.get("status")}  # HPP/cost/margin never exposed


# ---- Individual tool handlers (each returns a dict; raise on genuine failure) ----
async def _ait_search_customer(pr):
    q = (pr.get("q") or pr.get("query") or "").strip()
    if not q:
        return {"results": []}
    rx = {"$regex": _re.escape(q), "$options": "i"}
    docs = await db.customers.find({"is_deleted": {"$ne": True}, "$or": [
        {"full_name": rx}, {"whatsapp": rx}, {"phone": rx}, {"email": rx}, {"customer_code": rx}]}).limit(10).to_list(10)
    return {"results": [{"id": str(c["_id"]), "full_name": c.get("full_name"), "whatsapp": c.get("whatsapp"),
                         "email": c.get("email"), "customer_code": c.get("customer_code")} for c in docs]}


async def _ait_get_customer(pr):
    cid = pr.get("customer_id")
    c = await db.customers.find_one({"_id": ObjectId(cid)}) if cid and ObjectId.is_valid(cid) else None
    if not c:
        raise ValueError("Customer tidak ditemukan")
    return {"id": str(c["_id"]), "full_name": c.get("full_name"), "whatsapp": c.get("whatsapp"),
            "email": c.get("email"), "customer_type": c.get("customer_type"), "city": c.get("city"),
            "sales_pic_name": c.get("sales_pic_name"), "customer_code": c.get("customer_code")}


async def _ait_search_package(pr):
    q = (pr.get("q") or pr.get("query") or "").strip()
    query = {"status": "ACTIVE"}
    if q:
        rx = {"$regex": _re.escape(q), "$options": "i"}
        query["$or"] = [{"package_name": rx}, {"package_code": rx}, {"destination": rx}, {"product_type": rx}]
    docs = await db.packages.find(query).limit(15).to_list(15)
    return {"results": [_ai_pkg_public(p) for p in docs]}


async def _ait_get_package(pr):
    pid = pr.get("package_id")
    p = await db.packages.find_one({"_id": ObjectId(pid)}) if pid and ObjectId.is_valid(pid) else None
    if not p:
        raise ValueError("Package tidak ditemukan")
    return _ai_pkg_public(p)


async def _ait_get_itinerary(pr):
    pid = pr.get("package_id")
    p = await db.packages.find_one({"_id": ObjectId(pid)}) if pid and ObjectId.is_valid(pid) else None
    if not p:
        raise ValueError("Package tidak ditemukan")
    return {"package_name": p.get("package_name"), "description": p.get("description"), "terms": p.get("terms")}


async def _ait_check_seat(pr):
    a = await _availability(pr.get("package_id"), pr.get("departure_id"))
    if not a:
        raise ValueError("Package tidak ditemukan")
    return a


async def _ait_get_departure(pr):
    pid = pr.get("package_id")
    if pr.get("departure_id") and ObjectId.is_valid(pr["departure_id"]):
        d = await db.departures.find_one({"_id": ObjectId(pr["departure_id"])})
        return compute_departure(serialize(d)) if d else {}
    deps = await db.departures.find({"package_id": pid}).sort("departure_date", 1).to_list(20)
    return {"departures": [compute_departure(serialize(d)) for d in deps]}


async def _ait_get_payment_status(pr):
    q = {}
    if pr.get("booking_id"):
        q["booking_id"] = pr["booking_id"]
    elif pr.get("customer_id"):
        q["customer_id"] = pr["customer_id"]
    else:
        raise ValueError("booking_id atau customer_id wajib diisi")
    invs = await db.invoices.find(q).to_list(50)
    return {"invoices": [{"invoice_number": i.get("invoice_number"), "total": i.get("total"),
                          "paid_amount": i.get("paid_amount"), "outstanding": i.get("outstanding"),
                          "status": i.get("status")} for i in invs],
            "total_outstanding": sum(float(i.get("outstanding") or 0) for i in invs)}


async def _ait_get_booking(pr):
    bid = pr.get("booking_id")
    b = await db.bookings.find_one({"_id": ObjectId(bid)}) if bid and ObjectId.is_valid(bid) else None
    if not b:
        raise ValueError("Booking tidak ditemukan")
    return {"id": str(b["_id"]), "booking_number": b.get("booking_number"), "customer_name": b.get("customer_name"),
            "package_name": b.get("package_name"), "departure_date": b.get("departure_date"), "pax": b.get("pax"),
            "total": b.get("total"), "status": b.get("status"), "payment_status": b.get("payment_status"),
            "booking_source": b.get("booking_source")}


async def _ait_get_faq(pr):
    q = (pr.get("q") or "").strip()
    query = {"status": "ACTIVE"}
    if q:
        rx = {"$regex": _re.escape(q), "$options": "i"}
        query["$or"] = [{"question": rx}, {"answer": rx}, {"keywords": rx}]
    docs = await db.knowledge_faqs.find(query).limit(20).to_list(20)
    return {"faqs": [{"question": f.get("question"), "answer": f.get("answer"), "category": f.get("category")} for f in docs]}


async def _ait_get_company_policy(pr):
    cat = pr.get("category")
    arts = await _kb_active_articles()
    if cat:
        arts = [a for a in arts if a.get("category") == cat]
    else:
        arts = [a for a in arts if a.get("category") in KB_POLICY_CATS]
    return {"policies": [{"title": a.get("title"), "category": a.get("category"), "content": a.get("content")} for a in arts]}


async def _ait_create_customer(pr):
    name = (pr.get("full_name") or "").strip()
    wa = (pr.get("whatsapp") or pr.get("phone") or "").strip()
    if not name and not wa:
        raise ValueError("full_name atau whatsapp wajib diisi")
    if wa:
        ex = await db.customers.find_one({"whatsapp": wa})
        if ex:
            return {"existing": True, "id": str(ex["_id"]), "full_name": ex.get("full_name")}
    count = await db.customers.count_documents({})
    doc = {"customer_code": f"CUST-{count + 1:05d}", "full_name": name or wa, "whatsapp": wa,
           "email": pr.get("email", ""), "city": pr.get("city", ""), "customer_type": "Prospect",
           "customer_source": "WHATSAPP AI", "sales_pic_id": None, "sales_pic_name": "AUTO SALES",
           "attribution": "AUTO SALES", "created_at": now_iso(), "created_by": "AI AGENT"}
    r = await db.customers.insert_one(doc)
    return {"existing": False, "id": str(r.inserted_id), "full_name": doc["full_name"]}


async def _ait_update_customer(pr):
    cid = pr.get("customer_id")
    c = await db.customers.find_one({"_id": ObjectId(cid)}) if cid and ObjectId.is_valid(cid) else None
    if not c:
        raise ValueError("Customer tidak ditemukan")
    upd = {k: pr[k] for k in ("full_name", "email", "city", "whatsapp", "notes") if k in pr}
    if not upd:
        raise ValueError("Tidak ada field yang diubah")
    await db.customers.update_one({"_id": c["_id"]}, {"$set": upd})
    return {"id": cid, "updated": list(upd.keys())}


async def _ait_create_lead(pr):
    cid = pr.get("customer_id")
    cust = await db.customers.find_one({"_id": ObjectId(cid)}) if cid and ObjectId.is_valid(cid) else None
    if not cust:
        raise ValueError("Customer tidak ditemukan")
    count = await db.leads.count_documents({})
    doc = {"lead_code": f"LEAD-{count + 1:05d}", "customer_id": cid, "customer_name": cust.get("full_name"),
           "source": "WHATSAPP AI", "interested_package": pr.get("interested_package", ""),
           "destination": pr.get("destination", ""), "pax": int(pr.get("pax") or 0),
           "budget": float(pr.get("budget") or 0), "status": "NEW", "sales_pic_id": None,
           "sales_pic_name": "AUTO SALES", "attribution": "AUTO SALES", "last_contact": now_iso(),
           "created_at": now_iso(), "created_by": "AI AGENT", "notes": pr.get("notes", "")}
    r = await db.leads.insert_one(doc)
    return {"id": str(r.inserted_id), "lead_code": doc["lead_code"]}


async def _ait_create_followup(pr):
    cid = pr.get("customer_id")
    await create_task(pr.get("title") or "Follow Up (AI)", customer_id=cid, priority=pr.get("priority", "MEDIUM"),
                      notes=pr.get("notes", ""), created_by="AI AGENT", source="whatsapp_ai")
    return {"created": True, "customer_id": cid}


async def _ai_create_booking(pr):
    """Mirror AUTO SALES booking creation, tagged as AI. Full CRM validation, seat reserve, idempotency."""
    ext = pr.get("external_booking_id")
    if ext:
        dup = await db.bookings.find_one({"external_booking_id": ext})
        if dup:
            return {"idempotent": True, "id": str(dup["_id"]), "booking_number": dup.get("booking_number")}
    cid = pr.get("customer_id")
    cust = await db.customers.find_one({"_id": ObjectId(cid)}) if cid and ObjectId.is_valid(cid) else None
    if not cust:
        raise ValueError("Customer tidak ditemukan")
    pid = pr.get("package_id")
    pkg = await db.packages.find_one({"_id": ObjectId(pid)}) if pid and ObjectId.is_valid(pid) else None
    if not pkg:
        raise ValueError("Package tidak ditemukan")
    if pkg.get("status") != "ACTIVE":
        raise ValueError("Package tidak aktif")
    pax = int(pr.get("pax") or 0)
    if pax < 1:
        raise ValueError("Jumlah pax tidak valid")
    dep = None
    did = pr.get("departure_id")
    # Cek DULU apakah booking untuk permintaan ini sudah ada (hindari duplikat & error "seat penuh" padahal sudah booking).
    dup_q = {"customer_id": cid, "package_id": pid, "pax": pax,
             "booking_source": "AUTO SALES", "ai_generated": True, "status": {"$ne": "CANCELLED"}}
    if did:
        dup_q["departure_id"] = did
    existing = await db.bookings.find_one(dup_q)
    if not existing and did:
        # Fallback: retry AI kadang tak menyertakan departure_id → cocokkan customer+paket+pax saja.
        existing = await db.bookings.find_one({"customer_id": cid, "package_id": pid, "pax": pax,
            "booking_source": "AUTO SALES", "ai_generated": True, "status": {"$ne": "CANCELLED"}})
    if existing:
        einv = await db.invoices.find_one({"booking_id": str(existing["_id"])})
        return {"idempotent": True, "id": str(existing["_id"]), "booking_number": existing.get("booking_number"),
                "invoice_number": (einv or {}).get("invoice_number"), "total": existing.get("total"),
                "pax": existing.get("pax"), "discount_amount": existing.get("discount_amount"),
                "discount_percent": existing.get("discount_percent"), "payment_status": (einv or {}).get("status", "Unpaid"),
                "package_name": existing.get("package_name"), "source": "WHATSAPP AI"}
    if did:
        dep = await db.departures.find_one({"_id": ObjectId(did)}) if ObjectId.is_valid(did) else None
        if not dep:
            raise ValueError("Departure tidak ditemukan")
        dep = compute_departure(serialize(dep))
        if int(dep.get("available_seat") or 0) < pax:
            raise ValueError("Kursi tidak mencukupi (departure penuh)")
    settings = await get_settings_dict()
    per_pax = compute_pax_price(pkg, pax)
    subtotal = per_pax * pax
    # Diskon dalam batas maksimal per paket (nominal/persen). AI tidak boleh melebihi batas.
    d_type = (pr.get("discount_type") or "").upper()
    d_val = float(pr.get("discount_value") or 0)
    max_type = (pkg.get("max_discount_type") or "PERCENT").upper()
    max_val = float(pkg.get("max_discount_value") or 0)
    disc_amt = 0
    if d_val > 0 and max_val > 0:
        req_amt = round(subtotal * d_val / 100) if d_type == "PERCENT" else round(d_val)
        cap_amt = round(subtotal * max_val / 100) if max_type == "PERCENT" else round(max_val)
        disc_amt = max(0, min(req_amt, cap_amt, subtotal))
    disc_pct = round(disc_amt / subtotal * 100, 2) if subtotal else 0
    taxable = subtotal - disc_amt
    pct, _amt = resolve_category_tax(pkg, settings)
    tax_amount = round(taxable * pct / 100)
    total = taxable + tax_amount
    number = await next_number((settings.get("numbering") or {}).get("booking_prefix", "BKG"), db.bookings, "booking_number")
    booking = {"booking_number": number, "quotation_id": None, "customer_id": cid, "customer_name": cust.get("full_name"),
               "package_id": pid, "package_name": pkg.get("package_name"), "package_version": pkg.get("version", 1),
               "departure_id": did, "departure_date": (dep or {}).get("departure_date", ""), "pax": pax,
               "room_type": pr.get("room_type", ""), "addons": [], "booking_source": "AUTO SALES",
               "source_channel": "WHATSAPP AI", "attribution": "AUTO SALES", "ai_generated": True,
               "sales_type": "AUTO", "sales_user_id": None, "sales_name": "AUTO SALES",
               "per_pax_price": per_pax, "subtotal": subtotal, "discount_percent": disc_pct, "discount_amount": disc_amt,
               "tax_percent": pct, "tax_amount": tax_amount, "total": total, "payment_schedule": [],
               "status": "CONFIRMED", "sales_pic_id": None, "sales_pic_name": "AUTO SALES", "branch": "",
               "external_booking_id": ext, "created_at": now_iso(), "created_by": "AI AGENT"}
    res = await db.bookings.insert_one(booking)
    bid = str(res.inserted_id)
    if did:
        await db.departures.update_one({"_id": ObjectId(did)}, {"$inc": {"confirmed_pax": pax}})
    inv_number = await next_number((settings.get("numbering") or {}).get("invoice_prefix", "INV"), db.invoices, "invoice_number")
    _inv_snap = await tax_snapshot(now_iso()[:10], taxable)
    await db.invoices.insert_one({**_inv_snap, "invoice_number": inv_number, "booking_id": bid, "booking_number": number,
        "customer_id": cid, "customer_name": cust.get("full_name"), "package_id": pid, "package_name": pkg.get("package_name"),
        "pax": pax, "amount": subtotal, "discount_amount": disc_amt, "discount_percent": disc_pct, "tax_percent": pct,
        "tax_amount": tax_amount, "total": total, "paid_amount": 0, "outstanding": total, "due_date": pr.get("due_date", ""),
        "status": "Unpaid", "sales_pic_id": None, "sales_pic_name": "AUTO SALES", "branch": "",
        "terms": pkg.get("terms", ""), "created_at": now_iso(), "created_by": "AI AGENT"})
    if ext:
        await db.idempotency_keys.update_one({"key": ext}, {"$set": {"booking_id": bid, "created_at": now_iso()}}, upsert=True)
    return {"id": bid, "booking_number": number, "invoice_number": inv_number, "total": total, "pax": pax,
            "discount_amount": disc_amt, "discount_percent": disc_pct, "payment_status": "Unpaid",
            "package_name": pkg.get("package_name"), "source": "WHATSAPP AI"}


async def _ait_assign_sales(pr):
    sid = pr.get("sales_id")
    su = await db.users.find_one({"_id": ObjectId(sid)}) if sid and ObjectId.is_valid(sid) else None
    if not su:
        raise ValueError("Sales user tidak ditemukan")
    sales_set = {"sales_pic_id": sid, "sales_pic_name": su.get("name"), "attribution": "AI → SALES",
                 "original_source": "WHATSAPP AI"}
    if pr.get("booking_id") and ObjectId.is_valid(pr["booking_id"]):
        await db.bookings.update_one({"_id": ObjectId(pr["booking_id"])}, {"$set": sales_set})
    if pr.get("customer_id") and ObjectId.is_valid(pr["customer_id"]):
        await db.customers.update_one({"_id": ObjectId(pr["customer_id"])}, {"$set": sales_set})
    return {"assigned_sales": su.get("name"), "attribution": "AI → SALES"}


async def _ait_request_handover(pr, ctx):
    conv = None
    convid = pr.get("conversation_id") or (ctx or {}).get("conversation_id")
    if convid and ObjectId.is_valid(convid):
        conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(convid)})
    if conv:
        await _wa_handover(conv, pr.get("reason") or "Handover diminta AI")
        return {"handover": True, "conversation_id": convid}
    cid = pr.get("customer_id") or (ctx or {}).get("customer_id")
    await create_task("Human Handover (AI)", customer_id=cid, priority="HIGH",
                      notes=pr.get("reason") or "AI meminta handover ke manusia", created_by="AI AGENT", source="whatsapp_ai")
    await notify("AI Human Handover", pr.get("reason") or "AI meminta bantuan manusia", link="/whatsapp", ntype="WHATSAPP_HANDOVER", priority="high")
    return {"handover": True, "task_created": True}


AI_TOOL_HANDLERS = {
    "SEARCH_CUSTOMER": _ait_search_customer, "GET_CUSTOMER": _ait_get_customer,
    "SEARCH_PACKAGE": _ait_search_package, "GET_PACKAGE": _ait_get_package,
    "GET_ITINERARY": _ait_get_itinerary, "CHECK_SEAT": _ait_check_seat,
    "GET_DEPARTURE": _ait_get_departure, "GET_PAYMENT_STATUS": _ait_get_payment_status,
    "GET_BOOKING": _ait_get_booking, "GET_FAQ": _ait_get_faq, "GET_COMPANY_POLICY": _ait_get_company_policy,
    "CREATE_CUSTOMER": _ait_create_customer, "UPDATE_CUSTOMER": _ait_update_customer,
    "CREATE_LEAD": _ait_create_lead, "CREATE_FOLLOWUP": _ait_create_followup,
    "CREATE_ORDER": _ai_create_booking, "CREATE_BOOKING": _ai_create_booking,
    "ASSIGN_SALES": _ait_assign_sales,
}


async def _ai_tool_dispatch(tool, params, ctx):
    """Secure dispatcher: permission -> risk/confirmation -> execute -> audit. Never fabricates."""
    params = params or {}
    ctx = ctx or {}
    meta = AI_TOOL_MAP.get(tool)
    if not meta:
        await _ai_audit(tool, params, {"error": "unknown tool"}, False, ctx)
        return {"ok": False, "error": f"Tool '{tool}' tidak dikenal"}
    if not await _ai_tool_enabled(tool):
        await _ai_audit(tool, params, {"error": "tool disabled"}, False, ctx)
        return {"ok": False, "error": f"Tool '{tool}' dinonaktifkan oleh Super Admin"}
    # High-risk: never execute; create an approval REQUEST for humans
    if meta["risk"] == "HIGH_RISK":
        req = {"tool": tool, "parameters": params, "conversation_id": ctx.get("conversation_id"),
               "customer_id": ctx.get("customer_id"), "status": "PENDING", "requested_by": "AI AGENT",
               "reason": params.get("reason", ""), "created_at": now_iso()}
        r = await db.ai_action_requests.insert_one(req)
        await notify("AI High-Risk Request", f"AI meminta approval: {meta['label']}", link="/ai-tools",
                     ntype="AI_ACTION_REQUEST", priority="high")
        await _ai_audit(tool, params, {"request_id": str(r.inserted_id), "status": "PENDING"}, True, ctx, approval_required=True)
        return {"ok": True, "request_created": True, "request_id": str(r.inserted_id),
                "message": f"Aksi '{meta['label']}' berisiko tinggi dan memerlukan persetujuan manusia. Permintaan telah dibuat."}
    # Transactional writes need explicit customer confirmation
    if meta["confirm"] and not (params.get("confirmed") or ctx.get("confirmed")):
        await _ai_audit(tool, params, {"needs_confirmation": True}, False, ctx)
        return {"ok": False, "needs_confirmation": True,
                "message": "Aksi ini butuh konfirmasi customer terlebih dahulu sebelum diproses."}
    handler = AI_TOOL_HANDLERS.get(tool)
    if tool == "REQUEST_HUMAN_HANDOVER":
        try:
            res = await _ait_request_handover(params, ctx)
            await _ai_audit(tool, params, res, True, ctx)
            return {"ok": True, "result": res}
        except Exception as e:
            await _ai_audit(tool, params, {"error": str(e)}, False, ctx)
            return {"ok": False, "error": str(e)[:200]}
    if not handler:
        await _ai_audit(tool, params, {"error": "no handler"}, False, ctx)
        return {"ok": False, "error": "Handler tidak tersedia"}
    try:
        res = await handler(params)
        await _ai_audit(tool, params, res, True, ctx)
        return {"ok": True, "result": res}
    except Exception as e:
        await _ai_audit(tool, params, {"error": str(e)}, False, ctx)
        return {"ok": False, "error": str(e)[:200]}


@api_router.get("/ai/tools")
async def ai_list_tools(user: dict = Depends(require_role("super_admin"))):
    perms = {d["tool"]: d.get("enabled", True) async for d in db.ai_tool_permissions.find({})}
    return [{**t, "enabled": perms.get(t["tool"], True)} for t in AI_TOOL_REGISTRY]


@api_router.put("/ai/tools/{tool}")
async def ai_toggle_tool(tool: str, body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    if tool not in AI_TOOL_MAP:
        raise HTTPException(status_code=404, detail="Tool tidak dikenal")
    enabled = bool(body.get("enabled", True))
    await db.ai_tool_permissions.update_one({"tool": tool}, {"$set": {"tool": tool, "enabled": enabled, "updated_at": now_iso(), "updated_by": user["name"]}}, upsert=True)
    await log_audit(user, "ai_tools", "toggle_tool", request, record_id=tool, new={"enabled": enabled})
    return {"tool": tool, "enabled": enabled}


@api_router.post("/ai/tools/execute")
async def ai_execute_tool(body: dict, user: dict = Depends(require_role("super_admin"))):
    tool = (body.get("tool") or "").strip().upper()
    ctx = {"conversation_id": body.get("conversation_id"), "customer_id": body.get("customer_id"),
           "confirmed": bool(body.get("confirmed")), "approved_by": user["name"]}
    return await _ai_tool_dispatch(tool, body.get("params") or {}, ctx)


@api_router.get("/ai/action-logs")
async def ai_action_logs(tool: str = "", limit: int = 200, user: dict = Depends(require_role("super_admin"))):
    q = {} if not tool else {"tool": tool}
    logs = await db.ai_action_logs.find(q).sort("timestamp", -1).to_list(min(limit, 500))
    return [serialize(l) for l in logs]


@api_router.get("/ai/requests")
async def ai_requests(status: str = "", user: dict = Depends(require_role("super_admin"))):
    q = {} if not status else {"status": status}
    reqs = await db.ai_action_requests.find(q).sort("created_at", -1).to_list(200)
    return [serialize(r) for r in reqs]


# ============================================================================
# PHASE 10A-REWORK — TAHAP 2 (Templates, Consent, Blacklist, Window, Broadcast,
# Webhook Health, AI Outbound Rule). All Api.co.id calls go through the service.
# ============================================================================
async def _wa_outbound_allowed(customer_id):
    """AI/outbound guard: block if CRM blacklist or opt-out. Returns (allowed, reason)."""
    if not customer_id or not ObjectId.is_valid(customer_id):
        return True, ""
    c = await db.customers.find_one({"_id": ObjectId(customer_id)})
    if not c:
        return True, ""
    if c.get("wa_blacklisted"):
        return False, "Customer di-blacklist"
    if (c.get("wa_consent") or "").upper() == "OPT_OUT":
        return False, "Customer opt-out"
    return True, ""


# ---- Templates ----
@api_router.get("/whatsapp/templates")
async def wa_templates(sync: int = 0, status: str = "", user: dict = Depends(require_role("super_admin"))):
    if sync:
        svc = await get_wa_provider()
        res = await svc._call("GET", "/api/v1/public/templates", params={"limit": 200})
        if res["ok"]:
            data = res["data"]
            items = (data.get("data") if isinstance(data, dict) else data) or []
            for t in items:
                await db.whatsapp_templates.update_one({"provider_template_id": str(t.get("id"))}, {"$set": {
                    "provider_template_id": str(t.get("id")), "template_name": t.get("template_name") or t.get("name"),
                    "category": t.get("category"), "language": t.get("language"), "status": (t.get("status") or "PENDING").upper(),
                    "meta_template_id": t.get("meta_template_id"), "whatsapp_phone_number_id": t.get("whatsapp_phone_number_id"),
                    "body": t.get("body"), "synced_at": now_iso()}}, upsert=True)
    q = {} if not status else {"status": status.upper()}
    docs = await db.whatsapp_templates.find(q).sort("synced_at", -1).to_list(300)
    return [serialize(d) for d in docs]


@api_router.post("/whatsapp/templates")
async def wa_create_template(body: dict, user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc._call("POST", "/api/v1/public/templates", json=body)
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Gagal membuat template ({res['category']}).")
    data = (res["data"] or {}).get("data") or res["data"] or {}
    await db.whatsapp_templates.update_one({"provider_template_id": str(data.get("id"))}, {"$set": {
        "provider_template_id": str(data.get("id")), "template_name": body.get("template_name"),
        "category": body.get("category"), "language": body.get("language"), "status": "PENDING",
        "body": body.get("body"), "created_at": now_iso(), "synced_at": now_iso()}}, upsert=True)
    return {"ok": True, "id": data.get("id")}


@api_router.post("/whatsapp/templates/{tid}/submit")
async def wa_submit_template(tid: str, user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc._call("POST", f"/api/v1/public/templates/{tid}/submit")
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Gagal submit template ({res['category']}).")
    return {"ok": True}


@api_router.post("/whatsapp/templates/send")
async def wa_send_template(body: dict, user: dict = Depends(require_role("super_admin"))):
    name = body.get("template_name") or (body.get("template") or {}).get("name")
    tpl = await db.whatsapp_templates.find_one({"template_name": name})
    if not tpl or (tpl.get("status") or "").upper() != "APPROVED":
        raise HTTPException(status_code=400, detail="Template belum APPROVED — tidak dapat dikirim.")
    cust = await db.customers.find_one({"_id": ObjectId(body["customer_id"])}) if body.get("customer_id") and ObjectId.is_valid(body["customer_id"]) else None
    if cust:
        allowed, reason = await _wa_outbound_allowed(str(cust["_id"]))
        if not allowed:
            raise HTTPException(status_code=400, detail=f"Outbound diblokir: {reason}")
    phone = body.get("phone_number") or (cust or {}).get("whatsapp")
    svc = await get_wa_provider()
    res = await svc.send_message(phone, "template", template=body.get("template") or {"name": name, "language": {"code": tpl.get("language", "id")}})
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Gagal kirim template ({res['category']}).")
    return {"ok": True, "data": res.get("data")}


# ---- Consent / Blacklist / Window ----
@api_router.post("/whatsapp/customers/{cid}/consent")
async def wa_consent(cid: str, body: dict, user: dict = Depends(require_role("super_admin"))):
    action = (body.get("action") or "").upper()
    if action not in ("OPT_IN", "OPT_OUT", "UPDATE"):
        raise HTTPException(status_code=400, detail="action tidak valid")
    c = await db.customers.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not c:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    await db.customers.update_one({"_id": c["_id"]}, {"$set": {"wa_consent": action, "wa_consent_at": now_iso()}})
    await db.whatsapp_consent_logs.insert_one({"customer_id": cid, "action": action, "source": body.get("source", "crm"),
        "purpose": body.get("purpose", ""), "created_at": now_iso(), "by": user["name"]})
    if c.get("apico_customer_id"):
        svc = await get_wa_provider()
        await svc._call("POST", f"/api/v1/public/customers/{c['apico_customer_id']}/consent",
                        json={"action": action, "source": body.get("source", "crm"), "purpose": body.get("purpose", "")})
    return {"ok": True, "wa_consent": action}


@api_router.patch("/whatsapp/customers/{cid}/blacklist")
async def wa_blacklist(cid: str, body: dict, user: dict = Depends(require_role("super_admin"))):
    c = await db.customers.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not c:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    bl = bool(body.get("blacklisted"))
    await db.customers.update_one({"_id": c["_id"]}, {"$set": {"wa_blacklisted": bl, "wa_blacklisted_at": now_iso()}})
    if c.get("apico_customer_id"):
        svc = await get_wa_provider()
        await svc._call("PATCH", f"/api/v1/public/customers/{c['apico_customer_id']}/blacklist", json={"blacklisted": bl})
    return {"ok": True, "blacklisted": bl}


@api_router.get("/whatsapp/customers/{cid}/window-status")
async def wa_window(cid: str, user: dict = Depends(require_role("super_admin"))):
    c = await db.customers.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
    if not c:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    if not c.get("apico_customer_id"):
        return {"window_active": None, "message": "Customer belum terhubung ke Api.co.id"}
    svc = await get_wa_provider()
    res = await svc.check_window(c["apico_customer_id"])
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Gagal cek window ({res['category']}).")
    return res["data"]


# ---- Broadcast (Super Admin only; approved template + eligible customers) ----
@api_router.post("/whatsapp/broadcast")
async def wa_broadcast(body: dict, user: dict = Depends(require_role("super_admin"))):
    name = body.get("template_name")
    tpl = await db.whatsapp_templates.find_one({"template_name": name})
    if not tpl or (tpl.get("status") or "").upper() != "APPROVED":
        raise HTTPException(status_code=400, detail="Broadcast wajib memakai template APPROVED.")
    # Filter eligible: exclude blacklist/opt-out
    raw_ids = body.get("customer_ids") or []
    phones, skipped = [], 0
    for cid in raw_ids:
        allowed, _ = await _wa_outbound_allowed(cid)
        c = await db.customers.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
        if allowed and c and c.get("whatsapp"):
            phones.append("+" + _apico_norm(c["whatsapp"]))
        else:
            skipped += 1
    phones = list(dict.fromkeys(phones)) + [p for p in (body.get("phone_numbers") or [])]
    if not phones:
        raise HTTPException(status_code=400, detail="Tidak ada penerima yang memenuhi syarat.")
    svc = await get_wa_provider()
    res = await svc._call("POST", "/api/v1/public/broadcast/send", json={
        "template_name": name, "language": tpl.get("language", "id"), "phone_numbers": phones,
        "whatsapp_phone_number_id": svc.phone_number_id, "components": body.get("components") or {}})
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Broadcast gagal ({res['category']}).")
    data = (res["data"] or {}).get("data") or res["data"] or {}
    job_id = data.get("job_id")
    await db.whatsapp_broadcasts.insert_one({"broadcast_job_id": job_id, "template_name": name,
        "recipients": len(phones), "skipped": skipped, "status": "SENT", "created_at": now_iso(), "by": user["name"]})
    return {"ok": True, "broadcast_job_id": job_id, "recipients": len(phones), "skipped": skipped}


@api_router.get("/whatsapp/broadcast/jobs")
async def wa_broadcast_jobs(user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc._call("GET", "/api/v1/public/broadcast/jobs", params={"limit": 50})
    remote = (res["data"] or {}).get("data") if res["ok"] and isinstance(res["data"], dict) else []
    local = await db.whatsapp_broadcasts.find({}).sort("created_at", -1).to_list(100)
    return {"remote": remote or [], "local": [serialize(x) for x in local]}


@api_router.get("/whatsapp/broadcast/jobs/{jid}")
async def wa_broadcast_job(jid: str, user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc._call("GET", f"/api/v1/public/broadcast/jobs/{jid}")
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Gagal ambil job ({res['category']}).")
    return res["data"]


@api_router.post("/whatsapp/broadcast/jobs/{jid}/cancel")
async def wa_broadcast_cancel(jid: str, user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc._call("POST", f"/api/v1/public/broadcast/jobs/{jid}/cancel")
    await db.whatsapp_broadcasts.update_one({"broadcast_job_id": jid}, {"$set": {"status": "CANCELLED"}})
    return {"ok": res["ok"]}


# ---- Webhook management & health ----
@api_router.get("/whatsapp/webhooks")
async def wa_webhooks(user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc._call("GET", "/api/v1/public/webhooks")
    remote = (res["data"] or {}).get("data") if res["ok"] and isinstance(res["data"], dict) else []
    return {"ok": res["ok"], "webhooks": remote or [], "error_category": res.get("category")}


@api_router.post("/whatsapp/webhooks/{wid}/enable")
async def wa_webhook_enable(wid: str, user: dict = Depends(require_role("super_admin"))):
    svc = await get_wa_provider()
    res = await svc._call("POST", f"/api/v1/public/webhooks/{wid}/enable")
    if not res["ok"]:
        raise HTTPException(status_code=502, detail=f"Gagal enable webhook ({res['category']}).")
    return {"ok": True}


@api_router.get("/whatsapp/webhook-health")
async def wa_webhook_health(user: dict = Depends(require_role("super_admin"))):
    total = await db.whatsapp_webhook_events.count_documents({})
    errors = await db.whatsapp_webhook_events.count_documents({"status": "ERROR"})
    last = await db.whatsapp_webhook_events.find_one({}, sort=[("received_at", -1)])
    last_ok = await db.whatsapp_webhook_events.find_one({"status": "PROCESSED"}, sort=[("processed_at", -1)])
    return {"total_events": total, "error_events": errors,
            "last_event_at": (last or {}).get("received_at"), "last_success_at": (last_ok or {}).get("processed_at")}


@api_router.get("/whatsapp/health")
async def wa_health(user: dict = Depends(require_role("super_admin"))):
    cfg = await _apico_config()
    svc = ApiCoWhatsAppProvider(cfg)
    api_ok = (await svc.health())["ok"] if cfg["_api_key"] else False
    has_phone = bool(cfg.get("phone_number_id"))
    err_events = await db.whatsapp_webhook_events.count_documents({"status": "ERROR"})
    if api_ok and has_phone and err_events == 0:
        overall = "CONNECTED"
    elif api_ok:
        overall = "DEGRADED"
    else:
        overall = "ERROR"
    return {"overall": overall, "api_ok": api_ok, "has_phone_number": has_phone,
            "webhook_error_events": err_events}


async def _mon_rate(n, d):
    return round((n / d) * 100, 1) if d else 0.0


@api_router.get("/ai/monitoring/dashboard")
async def ai_mon_dashboard(user: dict = Depends(require_role("super_admin"))):
    total = await db.whatsapp_conversations.count_documents({})
    handover = await db.whatsapp_conversations.count_documents({"status": "HUMAN HANDOVER"})
    ai_handled = max(total - handover, 0)
    new_customers = await db.customers.count_documents({"customer_source": {"$in": ["WHATSAPP", "WHATSAPP AI"]}})
    new_leads = await db.leads.count_documents({"source": {"$in": ["WHATSAPP AI", "WHATSAPP"]}})
    orders = await db.bookings.count_documents({"source_channel": "WHATSAPP AI"})
    bookings = orders
    auto_sales = await db.bookings.count_documents({"attribution": "AUTO SALES"})
    ai_to_sales = await db.bookings.count_documents({"attribution": "AI → SALES"}) + await db.customers.count_documents({"attribution": "AI → SALES"})
    failed = await db.whatsapp_logs.count_documents({"kind": "AI", "ok": False})
    ai_msgs = await db.whatsapp_messages.count_documents({"sender": "AI"})
    return {
        "counts": {"total_conversations": total, "ai_handled": ai_handled, "human_handover": handover,
                   "new_customers": new_customers, "new_leads": new_leads, "orders": orders, "bookings": bookings,
                   "auto_sales": auto_sales, "ai_to_sales": ai_to_sales, "failed_responses": failed},
        "performance": {
            "ai_resolution_rate": await _mon_rate(ai_handled, total),
            "human_handover_rate": await _mon_rate(handover, total),
            "lead_creation_rate": await _mon_rate(new_leads, total),
            "order_creation_rate": await _mon_rate(orders, total),
            "booking_conversion": await _mon_rate(bookings, new_leads),
            "response_failure_rate": await _mon_rate(failed, ai_msgs)},
    }


@api_router.get("/ai/monitoring/quality")
async def ai_mon_quality(user: dict = Depends(require_role("super_admin"))):
    msgs = await db.whatsapp_messages.find({"sender": "AI"}).sort("created_at", -1).to_list(80)
    conv_cache = {}
    out = []
    for m in msgs:
        cid = m.get("conversation_id")
        if cid and cid not in conv_cache:
            conv_cache[cid] = await db.whatsapp_conversations.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None
        conv = conv_cache.get(cid) or {}
        out.append({"id": str(m["_id"]), "message_id": m.get("message_id"), "conversation_id": cid,
                    "customer_name": conv.get("customer_name"), "content": m.get("content"),
                    "created_at": m.get("created_at"), "quality_flag": m.get("quality_flag")})
    return out


@api_router.post("/ai/monitoring/flag")
async def ai_mon_flag(body: dict, user: dict = Depends(require_role("super_admin"))):
    flag = (body.get("flag") or "").upper()
    if flag not in ("GOOD", "NEEDS_IMPROVEMENT", "INCORRECT", "OUTDATED_KNOWLEDGE"):
        raise HTTPException(status_code=400, detail="flag tidak valid")
    mid = body.get("message_id")
    await db.whatsapp_messages.update_one({"message_id": mid}, {"$set": {"quality_flag": flag}})
    await db.ai_response_flags.insert_one({"message_id": mid, "conversation_id": body.get("conversation_id"),
        "flag": flag, "note": body.get("note", ""), "content": body.get("content", ""),
        "created_at": now_iso(), "by": user["name"]})
    return {"ok": True, "flag": flag}


@api_router.get("/ai/monitoring/errors")
async def ai_mon_errors(user: dict = Depends(require_role("super_admin"))):
    wa = await db.whatsapp_logs.find({"ok": False}).sort("created_at", -1).to_list(100)
    tools = await db.ai_action_logs.find({"ok": False}).sort("timestamp", -1).to_list(100)
    apis = await db.whatsapp_api_logs.find({"ok": False}).sort("created_at", -1).to_list(50)
    return {
        "ai_errors": [{"kind": l.get("kind"), "ref": l.get("ref"), "error": l.get("error"), "at": l.get("created_at")} for l in wa],
        "tool_errors": [{"tool": t.get("tool"), "error": (t.get("result") or {}).get("error"), "at": t.get("timestamp")} for t in tools],
        "api_errors": [{"endpoint": a.get("endpoint"), "category": a.get("error_category"), "at": a.get("created_at")} for a in apis],
    }


@api_router.get("/ai/monitoring/gaps")
async def ai_mon_gaps(user: dict = Depends(require_role("super_admin"))):
    reasons = await db.whatsapp_logs.aggregate([{"$match": {"kind": "HANDOVER"}},
        {"$group": {"_id": "$error", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]).to_list(10)
    pkgs = await db.bookings.aggregate([{"$match": {"source_channel": "WHATSAPP AI"}},
        {"$group": {"_id": "$package_name", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]).to_list(10)
    flagged = await db.ai_response_flags.find({"flag": {"$in": ["INCORRECT", "OUTDATED_KNOWLEDGE", "NEEDS_IMPROVEMENT"]}}).sort("created_at", -1).to_list(40)
    return {
        "top_handover_reasons": [{"reason": r["_id"] or "—", "count": r["count"]} for r in reasons],
        "top_packages": [{"package": p["_id"] or "—", "count": p["count"]} for p in pkgs],
        "flagged_responses": [{"id": str(f["_id"]), "flag": f.get("flag"), "content": f.get("content"), "note": f.get("note"), "at": f.get("created_at")} for f in flagged],
    }


@api_router.post("/ai/monitoring/to-faq")
async def ai_mon_to_faq(body: dict, user: dict = Depends(require_role("super_admin"))):
    q = (body.get("question") or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="question wajib diisi")
    doc = {"question": q, "answer": body.get("answer") or "", "category": body.get("category") or "FAQ",
           "keywords": [], "status": "ACTIVE", "created_at": now_iso(), "created_by": user["name"],
           "updated_at": now_iso(), "updated_by": user["name"]}
    r = await db.knowledge_faqs.insert_one(doc)
    return {"ok": True, "id": str(r.inserted_id)}


WA_SAFETY_DEFAULTS = {"messaging_enabled": True, "ai_auto_reply": True, "read_receipt": True,
    "typing_indicator": True, "min_delay": 1.0, "max_delay": 8.0, "typing_speed": 45,
    "typing_speed_min": 35, "typing_speed_max": 60,
    "debounce_window": 3, "rate_per_minute": 8, "rate_per_hour": 60, "rate_per_day": 300,
    "max_followup": 2, "business_hours_enabled": False, "opening_time": "09:00", "closing_time": "18:00",
    "off_hours_behavior": "AUTO_RESPONSE", "away_message": "Halo Kak, pesan sudah kami terima. Tim kami akan membantu pada jam operasional.",
    "marketing_enabled": False, "message_splitting": False, "split_max_chars": 320, "split_max_messages": 3}

WA_WRITING_HARD_CAP = 12.0  # batas aman keras (detik) — delay tidak boleh tak wajar


async def _wa_safety():
    doc = await db.whatsapp_safety_settings.find_one({"_id": "main"}) or {}
    return {**WA_SAFETY_DEFAULTS, **{k: v for k, v in doc.items() if k != "_id"}}


def _wa_writing_time(reply, s):
    """Natural writing time dari char/word/sentence/complexity + speed range + variasi ringan, dengan hard cap."""
    import random as _rnd
    t = reply or ""
    chars = len(t)
    words = len(t.split())
    sentences = max(1, t.count(".") + t.count("!") + t.count("?"))
    smin = float(s.get("typing_speed_min") or 35)
    smax = float(s.get("typing_speed_max") or 60)
    if smax < smin:
        smin, smax = smax, smin
    speed = _rnd.uniform(max(10.0, smin), max(11.0, smax))  # variasi per-message
    base = chars / speed
    base += words * 0.02 + (sentences - 1) * 0.12  # kompleksitas ringan
    base *= _rnd.uniform(0.92, 1.08)  # randomization ringan (bukan ekstrem)
    lo = float(s.get("min_delay") or 1)
    hi = float(s.get("max_delay") or 8)
    return round(min(WA_WRITING_HARD_CAP, min(hi, max(lo, base))), 2)


_wa_typing_delay = _wa_writing_time  # kompat


async def _wa_rate_check(s):
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    async def cnt(mins):
        since = (now - timedelta(minutes=mins)).isoformat()
        return await db.whatsapp_messages.count_documents({"direction": "OUTBOUND", "created_at": {"$gte": since}})
    if await cnt(1) >= int(s.get("rate_per_minute") or 8):
        return False, "per_minute"
    if await cnt(60) >= int(s.get("rate_per_hour") or 60):
        return False, "per_hour"
    if await cnt(1440) >= int(s.get("rate_per_day") or 300):
        return False, "per_day"
    return True, ""


def _wa_business_open(s):
    if not s.get("business_hours_enabled"):
        return True
    from datetime import datetime as _dt
    now = _dt.now(timezone.utc)
    hm = now.strftime("%H:%M")
    return (s.get("opening_time") or "00:00") <= hm <= (s.get("closing_time") or "23:59")


@api_router.get("/whatsapp/safety")
async def wa_safety_get(user: dict = Depends(require_role("super_admin"))):
    return await _wa_safety()


@api_router.put("/whatsapp/safety")
async def wa_safety_put(body: dict, user: dict = Depends(require_role("super_admin"))):
    upd = {k: body[k] for k in WA_SAFETY_DEFAULTS if k in body}
    upd["updated_at"] = now_iso()
    await db.whatsapp_safety_settings.update_one({"_id": "main"}, {"$set": upd}, upsert=True)
    return await _wa_safety()


@api_router.get("/whatsapp/messaging-monitor")
async def wa_messaging_monitor(user: dict = Depends(require_role("super_admin"))):
    from datetime import timedelta
    today = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    q = {"created_at": {"$gte": today}}
    inbound = await db.whatsapp_messages.count_documents({**q, "direction": "INBOUND"})
    outbound = await db.whatsapp_messages.count_documents({**q, "direction": "OUTBOUND"})
    ai_resp = await db.whatsapp_messages.count_documents({**q, "sender": "AI"})
    human = await db.whatsapp_messages.count_documents({**q, "sender": "SALES"})
    failed = await db.whatsapp_logs.count_documents({"kind": "AI", "ok": False, "created_at": {"$gte": today}})
    rate_events = await db.whatsapp_logs.count_documents({"kind": "RATE_LIMIT", "created_at": {"$gte": today}})
    followup_cap = await db.whatsapp_logs.count_documents({"kind": "FOLLOWUP_CAP", "created_at": {"$gte": today}})
    optout = await db.customers.count_documents({"wa_consent": "OPT_OUT"})
    handover = await db.whatsapp_conversations.count_documents({"status": "HUMAN HANDOVER"})
    queued = await db.whatsapp_outbound_queue.count_documents({"status": {"$in": ["QUEUED", "SENDING"]}})
    return {"messages_today": inbound + outbound, "inbound": inbound, "outbound": outbound,
            "ai_responses": ai_resp, "human_responses": human, "failed_messages": failed,
            "rate_limit_events": rate_events, "followup_capped": followup_cap, "opt_out_customers": optout,
            "human_handover": handover, "queue_pending": queued}


# ----------------------------------------------------------------------------
# PHASE 10G — Increment 2: Debounce + Outbound Queue + Worker + Message Splitting
# ----------------------------------------------------------------------------
_WA_DEBOUNCE = {}  # conv_id -> {"texts": [...], "task": asyncio.Task}


async def _wa_debounce_fire(conv_id):
    """Tunggu jendela debounce, gabungkan pesan beruntun, lalu proses AI sekali."""
    try:
        s = await _wa_safety()
        win = float(s.get("debounce_window") or 0)
        if win > 0:
            await asyncio.sleep(win)
    except asyncio.CancelledError:
        return
    entry = _WA_DEBOUNCE.pop(conv_id, None)
    if not entry:
        return
    combined = "\n".join([t for t in entry.get("texts", []) if t]).strip()
    if not combined:
        return
    try:
        await _wa_ai_process(conv_id, combined)
    except Exception as e:
        await _wa_log("apico", "AI", "IN", conv_id, False, str(e))


def _wa_debounce_schedule(conv_id, text):
    """Kumpulkan pesan masuk beruntun; reset timer tiap pesan baru."""
    entry = _WA_DEBOUNCE.get(conv_id)
    if entry is None:
        entry = {"texts": []}
        _WA_DEBOUNCE[conv_id] = entry
    entry["texts"].append(text)
    old = entry.get("task")
    if old and not old.done():
        old.cancel()
    entry["task"] = asyncio.create_task(_wa_debounce_fire(conv_id))


async def _mirror_crm_conversation(conv, content, direction, sender_kind, mtype="TEXT", media_url=""):
    """Mirror a WhatsApp message into the CRM `conversations` collection (linked by customer_id)
    so incoming/AI chats appear in the CRM conversation submenu + Customer 360 and can be analysed by AI."""
    try:
        cid = conv.get("customer_id")
        if not cid or not (content or media_url):
            return
        direction = (direction or "").upper()
        if direction == "INBOUND":
            sender_type, ai_or_human = "CUSTOMER", "CUSTOMER"
        elif sender_kind == "AI":
            sender_type, ai_or_human = "AI", "AI"
        else:
            sender_type, ai_or_human = "SALES", "HUMAN"
        await db.conversations.insert_one({
            "conversation_id": str(_uuid.uuid4()), "wa_conversation_id": str(conv.get("_id")),
            "customer_id": cid, "whatsapp": conv.get("wa_number", ""),
            "channel": "whatsapp", "source": "WHATSAPP", "direction": direction,
            "message": content or "", "message_type": (mtype or "TEXT").upper(), "media_url": media_url or "",
            "sender_type": sender_type, "ai_or_human": ai_or_human, "status": "SENT",
            "timestamp": now_iso(), "created_at": now_iso(),
        })
    except Exception:
        pass


async def _wa_enqueue_outbound(conv, content, sender="AI"):
    await db.whatsapp_outbound_queue.insert_one({
        "conversation_id": str(conv["_id"]), "wa_number": conv["wa_number"],
        "account_id": conv.get("account_id", "apico"), "content": content, "sender": sender,
        "status": "QUEUED", "attempts": 0, "created_at": now_iso(), "updated_at": now_iso()})
    await _mirror_crm_conversation(conv, content, "OUTBOUND", sender)


def _wa_split_message(text, max_chars, max_messages=3):
    """Pecah balasan panjang menjadi beberapa bubble natural (per paragraf/kalimat), dibatasi max_messages."""
    import re as _re
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    chunks, cur = [], ""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    for block in blocks:
        pieces = [block]
        if len(block) > max_chars:
            pieces = _re.split(r"(?<=[.!?])\s+", block)
        for p in pieces:
            p = p.strip()
            if not p:
                continue
            if len(p) > max_chars:
                for i in range(0, len(p), max_chars):
                    chunks.append(p[i:i + max_chars])
                continue
            if not cur:
                cur = p
            elif len(cur) + 1 + len(p) <= max_chars:
                cur = f"{cur} {p}"
            else:
                chunks.append(cur); cur = p
        if cur:
            chunks.append(cur); cur = ""
    if cur:
        chunks.append(cur)
    chunks = [c for c in chunks if c]
    if max_messages and len(chunks) > max_messages:
        head = chunks[:max_messages - 1]
        tail = " ".join(chunks[max_messages - 1:])
        chunks = head + [tail]
    return chunks


async def _wa_process_queue_item(item):
    """Item sudah diklaim (status SENDING) oleh worker. Kirim via provider dgn typing/delay/splitting."""
    conv = None
    cid = item.get("conversation_id")
    if cid and ObjectId.is_valid(cid):
        conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(cid)})
    if not conv:
        await db.whatsapp_outbound_queue.update_one({"_id": item["_id"]}, {"$set": {"status": "FAILED", "error": "conversation not found", "updated_at": now_iso()}})
        return
    s = await _wa_safety()
    ok_rate, rk = await _wa_rate_check(s)
    if not ok_rate:
        if int(item.get("attempts") or 0) > 30:
            await db.whatsapp_outbound_queue.update_one({"_id": item["_id"]}, {"$set": {"status": "FAILED", "error": f"rate limit {rk}", "updated_at": now_iso()}})
        else:
            from datetime import timedelta
            nxt = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
            await db.whatsapp_outbound_queue.update_one({"_id": item["_id"]}, {"$set": {"status": "QUEUED", "next_attempt_at": nxt, "error": f"rate limit {rk}", "updated_at": now_iso()}})
        await _wa_log(conv.get("account_id", "apico"), "RATE_LIMIT", "OUT", cid, False, f"rate limit {rk}")
        return
    svc = await get_wa_provider()
    reply = item.get("content") or ""
    bubbles = _wa_split_message(reply, int(s.get("split_max_chars") or 320), int(s.get("split_max_messages") or 3)) if s.get("message_splitting") else [reply]
    if not bubbles:
        bubbles = [reply]
    first_mid = None
    ok_any = False
    last_err = ""
    typing_start = now_iso()
    total_writing = 0.0
    for bub in bubbles:
        mid = f"ai-{now_iso()}"
        try:
            if s.get("typing_indicator", True):
                await svc.send_typing(conv["wa_number"])  # START TYPING
            wt = _wa_writing_time(bub, s)  # CALCULATE writing duration (per-message)
            total_writing += wt
            await asyncio.sleep(wt)
            # STOP TYPING happens implicitly on send (provider); lalu SEND MESSAGE
            res = await svc.send_message(conv["wa_number"], "text", content=bub)
            if res.get("ok"):
                ok_any = True
                data = res.get("data") or {}
                inner = data.get("data") if isinstance(data, dict) else {}
                mid = (inner or {}).get("message_id") or data.get("message_id") or mid
            else:
                last_err = res.get("error", "")
        except Exception as e:
            last_err = str(e)
        if first_mid is None:
            first_mid = mid
    first_mid = first_mid or f"ai-{now_iso()}"
    typing_stop = now_iso()
    await db.whatsapp_messages.insert_one({"message_id": str(first_mid), "conversation_id": cid, "account_id": conv.get("account_id", "apico"),
        "external_provider": APICO_PROVIDER, "external_message_id": str(first_mid),
        "sender": item.get("sender", "AI"), "sender_type": item.get("sender", "AI"), "receiver": conv["wa_number"], "direction": "OUTBOUND",
        "type": "text", "message_type": "text", "content": reply, "timestamp": now_iso(), "created_at": now_iso(), "sent_at": now_iso(),
        "ai_generated": item.get("sender", "AI") == "AI", "human_generated": False,
        "delivery_status": "SENT" if ok_any else "FAILED", "status": "SENT" if ok_any else "FAILED", "read_status": False})
    await db.whatsapp_conversations.update_one({"_id": conv["_id"]}, {"$set": {"last_message": reply[:200], "last_activity": now_iso(), "status": "WAITING CUSTOMER"}})
    await db.whatsapp_outbound_queue.update_one({"_id": item["_id"]}, {"$set": {
        "status": "SENT" if ok_any else "FAILED", "message_id": str(first_mid),
        "bubbles": len(bubbles), "writing_duration": round(total_writing, 2),
        "typing_start": typing_start, "typing_stop": typing_stop, "send_time": now_iso(),
        "error": "" if ok_any else last_err, "sent_at": now_iso(), "updated_at": now_iso()}})
    await _wa_log(conv.get("account_id", "apico"), "AI", "OUT", str(first_mid), ok_any, "" if ok_any else last_err)


async def _wa_outbound_worker():
    """Background worker: klaim item QUEUED secara atomik lalu kirim."""
    logger.info("[WA QUEUE] outbound worker started")
    while True:
        try:
            nowi = now_iso()
            item = await db.whatsapp_outbound_queue.find_one_and_update(
                {"status": "QUEUED", "$or": [{"next_attempt_at": {"$exists": False}}, {"next_attempt_at": {"$lte": nowi}}]},
                {"$set": {"status": "SENDING", "updated_at": nowi}, "$inc": {"attempts": 1}},
                sort=[("created_at", 1)])
            if not item:
                await asyncio.sleep(1.0)
                continue
            await _wa_process_queue_item(item)
        except Exception as e:
            logger.error(f"[WA QUEUE] worker error: {e}")
            await asyncio.sleep(1.0)


@api_router.get("/whatsapp/outbound-queue")
async def wa_outbound_queue(user: dict = Depends(require_role("super_admin"))):
    items = await db.whatsapp_outbound_queue.find({}).sort("created_at", -1).to_list(100)
    counts = {}
    for st in ["QUEUED", "SENDING", "SENT", "FAILED"]:
        counts[st] = await db.whatsapp_outbound_queue.count_documents({"status": st})
    return {"items": [serialize(i) for i in items], "counts": counts}


# ============================================================================
# PHASE 10H — AI Auto Follow-Up & Lead Nurturing (Super Admin)
# ============================================================================
AFU_ELIGIBLE_STAGES = ["NEW", "CONTACTED", "QUALIFIED", "QUOTATION", "NEGOTIATION"]
AFU_INTENTS = ["PACKAGE_INQUIRY", "PRICE_INQUIRY", "AVAILABILITY_INQUIRY", "DOCUMENT_INQUIRY",
               "BOOKING_INTENT", "PAYMENT_PENDING", "QUOTATION_PENDING", "GENERAL_INTEREST"]
AFU_QUEUE_STATUSES = ["SCHEDULED", "READY", "PROCESSING", "SENT", "CANCELLED", "FAILED"]
AFU_DEFAULTS = {
    "enabled": False, "max_followup": 3, "min_interval_hours": 24, "daily_limit_per_customer": 1,
    "business_hours_enabled": False, "opening_time": "09:00", "closing_time": "18:00",
    "schedule": [{"number": 1, "delay_hours": 24}, {"number": 2, "delay_hours": 72}, {"number": 3, "delay_hours": 168}],
    "intent_guidance": {}, "handover_on_booking_intent": True,
    "quotation_followup_enabled": True, "departure_nudge_enabled": True, "departure_nudge_days": 30,
    "payment_followup_enabled": True, "payment_followup_max": 3,
    "ab_testing_enabled": False, "ab_min_sample": 20,
    "ab_style_a": "Ringkas & langsung ke inti (sopan, 2-3 kalimat).",
    "ab_style_b": "Hangat & konsultatif (empatik, menawarkan bantuan lanjutan).",
}
AFU_SETTING_KEYS = list(AFU_DEFAULTS.keys())


async def _afu_settings():
    doc = await db.autofollowup_settings.find_one({"_id": "main"}) or {}
    return {**AFU_DEFAULTS, **{k: v for k, v in doc.items() if k != "_id"}}


def _afu_hours_since(iso):
    if not iso:
        return 1e9
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return 1e9


def _afu_detect_intent(text, has_quotation, has_unpaid_booking):
    if has_unpaid_booking:
        return "PAYMENT_PENDING"
    if has_quotation:
        return "QUOTATION_PENDING"
    low = (text or "").lower()
    kw = [
        ("BOOKING_INTENT", ["booking sekarang", "mau booking", "daftar", "pesan sekarang", "ambil paket", "jadi ikut", "deal", "fix ikut"]),
        ("DOCUMENT_INQUIRY", ["dokumen", "paspor", "passport", "visa", "syarat", "berkas"]),
        ("PRICE_INQUIRY", ["harga", "biaya", "berapa", "price", "budget"]),
        ("AVAILABILITY_INQUIRY", ["kursi", "seat", "tersedia", "kuota", "tanggal", "jadwal", "keberangkatan", "berangkat"]),
        ("PACKAGE_INQUIRY", ["paket", "umrah", "umroh", "haji", "tour", "wisata"]),
    ]
    for intent, words in kw:
        if any(w in low for w in words):
            return intent
    return "GENERAL_INTEREST"


async def _afu_pkg_snapshot(package_id):
    if not package_id or not ObjectId.is_valid(package_id):
        return ""
    p = await db.packages.find_one({"_id": ObjectId(package_id)})
    if not p:
        return ""
    today = today_str()
    deps = await db.departures.find({"package_id": str(p["_id"])}).sort("departure_date", 1).to_list(30)
    upcoming = [d for d in deps if (d.get("departure_date") or "") >= today]
    lines = []
    for d in upcoming[:4]:
        seat = max(0, int(d.get("quota") or 0) - int(d.get("confirmed_pax") or 0)) if d.get("available_seat") is None else int(d.get("available_seat") or 0)
        lines.append(f"{d.get('departure_date','-')} | harga Rp{int(d.get('price') or p.get('selling_price') or 0):,} | sisa kursi {seat}")
    dep_txt = "; ".join(lines) if lines else "(belum ada jadwal keberangkatan mendatang)"
    return (f"PAKET DIMINATI (data TERBARU CRM): [{p.get('package_code','')}] {p.get('package_name','')} — "
            f"destinasi {p.get('destination') or '-'}, durasi {p.get('duration') or '-'}, status {p.get('status')}, "
            f"harga dasar Rp{int(p.get('selling_price') or 0):,}.\nJadwal terbaru: {dep_txt}")


async def _afu_generate_message(lead, conv, settings, followup_number, intent, extra_context="", variant_style=""):
    msgs = await db.whatsapp_messages.find({"conversation_id": str(conv["_id"])}).sort("created_at", 1).to_list(1000)
    tail = msgs[-12:]
    hist = "\n".join(
        f"{'Customer' if m.get('direction') == 'INBOUND' else 'Kami'}: {(m.get('content') or '')[:300]}"
        for m in tail if (m.get("content") or "").strip()
    ) or "(belum ada riwayat pesan)"
    pkg_snap = await _afu_pkg_snapshot((lead or {}).get("package_id"))
    guidance = (settings.get("intent_guidance") or {}).get(intent, "")
    kb = await _kb_build_context()
    base = _kb_system_prompt(kb, comm_block=await _comm_active_block())
    sys = base + (
        "\n\nTUGAS: Buat SATU pesan FOLLOW-UP WhatsApp yang natural, sopan, dan CONTEXT-AWARE untuk lead yang belum closing. "
        "Rujuk topik/paket yang customer tanyakan sebelumnya (lihat riwayat). Gunakan HANYA data paket TERBARU di bawah "
        "(harga & sisa kursi terkini) — JANGAN mengarang dan JANGAN membuat false urgency (mis. 'seat tinggal 1!') kecuali "
        "data CRM benar menunjukkannya. Jangan menyapa generik seperti 'apakah masih tertarik?'. "
        "Balas HANYA teks pesan siap kirim (tanpa tanda kutip, tanpa 'ACTION:', tanpa penjelasan)."
    )
    prompt = (
        f"Ini follow-up ke-{followup_number}. Customer intent: {intent}.\n"
        + (f"Panduan gaya intent: {guidance}\n" if guidance else "")
        + (f"Gaya varian (A/B): {variant_style}\n" if variant_style else "")
        + (f"\n{extra_context}\n" if extra_context else "")
        + (f"\n{pkg_snap}\n" if pkg_snap else "")
        + f"\nRIWAYAT PERCAKAPAN TERAKHIR:\n{hist}\n\nTulis pesan follow-up sekarang."
    )
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"afu-{str((lead or conv)['_id'])}-{followup_number}",
                       system_message=sys).with_model("gemini", "gemini-3-flash-preview")
        reply = ((await chat.send_message(UserMessage(text=prompt))) or "").strip()
        reply = reply.strip('"').strip()
        return reply
    except Exception as e:
        logger.error(f"[AFU] generate failed: {e}")
        return ""


async def _afu_quotation_context(cid):
    """Konteks quotation aktif (belum converted) + status/expiry — untuk quotation follow-up."""
    q = await db.quotations.find_one({"customer_id": cid, "status": {"$nin": ["CONVERTED", "EXPIRED", "REJECTED"]}}, sort=[("created_at", -1)])
    if not q:
        return None, ""
    exp = q.get("valid_until") or q.get("expiry_date") or q.get("valid_till") or ""
    total = q.get("total") or q.get("grand_total") or q.get("total_amount") or 0
    ctx = (f"QUOTATION AKTIF (data CRM): No {q.get('quotation_number','-')}, status {q.get('status','-')}, "
           f"total Rp{int(total or 0):,}" + (f", berlaku s/d {str(exp)[:10]}" if exp else "") + ".")
    return q, ctx


async def _afu_departure_context(package_id, nudge_days):
    """Bila paket punya keberangkatan dalam nudge_days hari → konteks nudge (tanpa false urgency)."""
    if not package_id or not ObjectId.is_valid(package_id):
        return ""
    today = today_str()
    deps = await db.departures.find({"package_id": package_id}).sort("departure_date", 1).to_list(30)
    for d in deps:
        dd = d.get("departure_date") or ""
        if dd >= today:
            try:
                offset = (datetime.fromisoformat(dd).date() - datetime.now(timezone.utc).date()).days
            except Exception:
                offset = 999
            if 0 <= offset <= int(nudge_days or 30):
                seat = max(0, int(d.get("quota") or 0) - int(d.get("confirmed_pax") or 0)) if d.get("available_seat") is None else int(d.get("available_seat") or 0)
                return f"CATATAN: Keberangkatan {dd} tinggal {offset} hari lagi (sisa kursi {seat} per data CRM). Ingatkan dengan sopan tanpa menekan."
            break
    return ""


async def _afu_terminal(lead, status, reason):
    await db.leads.update_one({"_id": lead["_id"]}, {"$set": {
        "auto_followup_status": status, "followup_stopped_reason": reason, "followup_updated_at": now_iso()}})
    await db.ai_followup_queue.update_many({"lead_id": str(lead["_id"]), "status": {"$in": ["SCHEDULED", "READY", "PROCESSING"]}},
                                           {"$set": {"status": "CANCELLED", "cancel_reason": reason, "updated_at": now_iso()}})


async def _afu_evaluate_and_schedule(dry_run_default=True):
    """Evaluasi eligibility semua lead & jadwalkan follow-up. Kembalikan ringkasan."""
    s = await _afu_settings()
    sched_map = {int(r.get("number")): int(r.get("delay_hours")) for r in (s.get("schedule") or []) if r.get("number")}
    summary = {"evaluated": 0, "scheduled": 0, "cancelled": 0, "handover": 0, "skipped": 0}
    await _afu_ab_count_responses()
    leads = await db.leads.find({"is_deleted": {"$ne": True}, "status": {"$in": AFU_ELIGIBLE_STAGES}}).to_list(2000)
    for lead in leads:
        summary["evaluated"] += 1
        lid = str(lead["_id"])
        afu_status = lead.get("auto_followup_status", "ACTIVE")
        if afu_status in ("STOPPED", "PAUSED", "OPTED OUT", "COMPLETED", "CONVERTED", "HANDOVER"):
            summary["skipped"] += 1
            continue
        cid = lead.get("customer_id")
        if not cid or not ObjectId.is_valid(cid):
            summary["skipped"] += 1
            continue
        cust = await db.customers.find_one({"_id": ObjectId(cid)})
        if not cust:
            summary["skipped"] += 1
            continue
        # opt-out / blacklist
        if (cust.get("wa_consent") == "OPT_OUT") or cust.get("wa_blacklisted"):
            await _afu_terminal(lead, "OPTED OUT", "customer_opted_out"); summary["cancelled"] += 1
            continue
        # booking / paid → converted
        booking = await db.bookings.find_one({"customer_id": cid, "status": {"$ne": "CANCELLED"}})
        if booking:
            if (booking.get("payment_status") == "PAID"):
                await _afu_terminal(lead, "CONVERTED", "customer_paid")
            else:
                await _afu_terminal(lead, "CONVERTED", "customer_booked")
            summary["cancelled"] += 1
            continue
        # conversation basis (safety: hanya lead dgn interaksi WhatsApp)
        conv = await db.whatsapp_conversations.find_one({"customer_id": cid})
        if not conv:
            summary["skipped"] += 1
            continue
        if conv.get("status") == "HUMAN HANDOVER":
            await _afu_terminal(lead, "HANDOVER", "sales_handover"); summary["cancelled"] += 1
            continue
        cvid = str(conv["_id"])
        last_msg = await db.whatsapp_messages.find_one({"conversation_id": cvid}, sort=[("created_at", -1)])
        last_in = await db.whatsapp_messages.find_one({"conversation_id": cvid, "direction": "INBOUND"}, sort=[("created_at", -1)])
        # customer replied / active (spoke last) → STOP: batalkan follow-up terjadwal
        if last_msg and last_msg.get("direction") == "INBOUND":
            r = await db.ai_followup_queue.update_many({"lead_id": lid, "status": {"$in": ["SCHEDULED", "READY", "PROCESSING"]}},
                                                       {"$set": {"status": "CANCELLED", "cancel_reason": "customer_responded", "updated_at": now_iso()}})
            summary["cancelled"] += (r.modified_count if r else 0)
            summary["skipped"] += 1
            continue
        # detect intent + trigger context (quotation / departure)
        quote, quote_ctx = await _afu_quotation_context(cid)
        has_q = bool(quote)
        intent = _afu_detect_intent((last_in or {}).get("content", ""), has_q, False)
        afu_extra = ""
        afu_trigger = "NO_RESPONSE"
        if quote and s.get("quotation_followup_enabled", True):
            intent = "QUOTATION_PENDING"; afu_trigger = "QUOTATION"; afu_extra = quote_ctx
        if s.get("departure_nudge_enabled", True):
            dep_ctx = await _afu_departure_context(lead.get("package_id"), s.get("departure_nudge_days", 30))
            if dep_ctx:
                afu_extra = (afu_extra + "\n" + dep_ctx).strip()
                if afu_trigger == "NO_RESPONSE":
                    afu_trigger = "DEPARTURE"
        # high purchase intent → sales handover (bukan auto follow-up)
        if s.get("handover_on_booking_intent", True) and intent == "BOOKING_INTENT":
            await _wa_handover(conv, "High purchase intent — lead siap closing")
            await _afu_terminal(lead, "HANDOVER", "high_purchase_intent"); summary["handover"] += 1
            continue
        count = int(lead.get("followup_count") or 0)
        number = count + 1
        if number > int(s.get("max_followup") or 3):
            await _afu_terminal(lead, "COMPLETED", "max_followup_reached"); summary["skipped"] += 1
            continue
        # pending?
        if await db.ai_followup_queue.find_one({"lead_id": lid, "status": {"$in": ["SCHEDULED", "READY", "PROCESSING"]}}):
            summary["skipped"] += 1
            continue
        # timing
        ref = (last_in or {}).get("created_at") or conv.get("created_at")
        elapsed = _afu_hours_since(ref)
        threshold = sched_map.get(number, 24 * (number))
        if elapsed < threshold:
            summary["skipped"] += 1
            continue
        if _afu_hours_since(lead.get("last_followup_at")) < float(s.get("min_interval_hours") or 24):
            summary["skipped"] += 1
            continue
        # daily limit per customer
        day0 = (datetime.now(timezone.utc).date()).isoformat()
        sent_today = await db.ai_followup_queue.count_documents({"customer_id": cid, "status": "SENT", "sent_at": {"$gte": day0}})
        if sent_today >= int(s.get("daily_limit_per_customer") or 1):
            summary["skipped"] += 1
            continue
        # generate message
        abv, abstyle = await _afu_ab_choose(s)
        message = await _afu_generate_message(lead, conv, s, number, intent, extra_context=afu_extra, variant_style=abstyle)
        if not message:
            summary["skipped"] += 1
            continue
        dry = dry_run_default or (not s.get("enabled"))
        item = {"lead_id": lid, "customer_id": cid, "conversation_id": cvid, "wa_number": conv.get("wa_number"),
                "customer_name": cust.get("full_name"), "followup_number": number, "intent": intent,
                "reason": f"{afu_trigger} • {int(elapsed)}h ≥ {threshold}h (FU#{number})", "message": message,
                "trigger": afu_trigger, "source": "LEAD", "ab_variant": abv,
                "package_id": lead.get("package_id"), "status": "SCHEDULED" if dry else "READY",
                "dry_run": dry, "scheduled_at": now_iso(), "sent_at": None, "created_at": now_iso(), "updated_at": now_iso()}
        await db.ai_followup_queue.insert_one(item)
        await db.leads.update_one({"_id": lead["_id"]}, {"$set": {"auto_followup_status": "ACTIVE", "customer_intent": intent, "followup_updated_at": now_iso()}})
        summary["scheduled"] += 1
    return summary


async def _afu_evaluate_payment_followups(dry_run_default=True):
    """Payment follow-up track: booking belum lunas, jatuh tempo dekat/overdue (tidak PAID/CANCELLED/refund)."""
    s = await _afu_settings()
    summary = {"scheduled": 0, "skipped": 0, "cancelled": 0}
    if not s.get("payment_followup_enabled", True):
        return summary
    today = today_str()
    bookings = await db.bookings.find({"status": {"$nin": ["CANCELLED", "REFUNDED"]}, "payment_status": {"$ne": "PAID"}}).to_list(2000)
    for b in bookings:
        cid = b.get("customer_id")
        bnum = b.get("booking_number")
        if not cid or not ObjectId.is_valid(cid):
            summary["skipped"] += 1; continue
        rf = await db.refund_requests.find_one({"$or": [{"booking_id": str(b["_id"])}, {"booking_number": bnum}],
                                                "status": {"$nin": ["REJECTED", "PAID", "REFUNDED", "PARTIALLY_REFUNDED", "COMPLETED"]}})
        cn = await db.cancellation_requests.find_one({"booking_number": bnum, "status": {"$nin": ["REJECTED", "APPROVED", "COMPLETED"]}})
        if rf or cn:
            summary["skipped"] += 1; continue
        cust = await db.customers.find_one({"_id": ObjectId(cid)})
        if not cust or cust.get("wa_consent") == "OPT_OUT" or cust.get("wa_blacklisted"):
            summary["skipped"] += 1; continue
        conv = await db.whatsapp_conversations.find_one({"customer_id": cid})
        if not conv or conv.get("status") == "HUMAN HANDOVER":
            summary["skipped"] += 1; continue
        due_item = None; stage = None
        for it in (b.get("payment_schedule") or []):
            out = float(it.get("outstanding") or (float(it.get("amount") or 0) - float(it.get("paid_amount") or 0)))
            if out <= 0:
                continue
            due = (it.get("due_date") or "")[:10]
            if not due:
                continue
            try:
                offset = (datetime.fromisoformat(due).date() - datetime.now(timezone.utc).date()).days
            except Exception:
                continue
            st = "Overdue" if due < today else ("Jatuh tempo hari ini" if offset == 0 else (f"{offset} hari lagi" if offset in (1, 3, 7) else None))
            if st:
                due_item = it; stage = st; break
        if not due_item:
            summary["skipped"] += 1; continue
        sent_cnt = await db.ai_followup_queue.count_documents({"booking_number": bnum, "source": "PAYMENT", "status": "SENT"})
        if sent_cnt >= int(s.get("payment_followup_max") or 3):
            summary["skipped"] += 1; continue
        if await db.ai_followup_queue.find_one({"booking_number": bnum, "source": "PAYMENT", "status": {"$in": ["SCHEDULED", "READY", "PROCESSING"]}}):
            summary["skipped"] += 1; continue
        out = float(due_item.get("outstanding") or 0)
        due = (due_item.get("due_date") or "")[:10]
        extra = (f"KONTEKS PEMBAYARAN (data CRM): Booking {bnum}, sisa tagihan Rp{int(out):,}, jatuh tempo {due} ({stage}). "
                 "Ingatkan pembayaran dengan sopan, sertakan nominal & jatuh tempo, tanpa menekan.")
        number = sent_cnt + 1
        abv, abstyle = await _afu_ab_choose(s)
        message = await _afu_generate_message(None, conv, s, number, "PAYMENT_PENDING", extra_context=extra, variant_style=abstyle)
        if not message:
            summary["skipped"] += 1; continue
        dry = dry_run_default or (not s.get("enabled"))
        await db.ai_followup_queue.insert_one({"lead_id": None, "customer_id": cid, "conversation_id": str(conv["_id"]),
            "wa_number": conv.get("wa_number"), "customer_name": cust.get("full_name"), "booking_number": bnum,
            "followup_number": number, "intent": "PAYMENT_PENDING", "reason": f"PAYMENT • {stage} • Rp{int(out):,} due {due}",
            "message": message, "trigger": "PAYMENT", "source": "PAYMENT", "ab_variant": abv, "status": "SCHEDULED" if dry else "READY",
            "dry_run": dry, "scheduled_at": now_iso(), "sent_at": None, "created_at": now_iso(), "updated_at": now_iso()})
        summary["scheduled"] += 1
    return summary


async def _afu_process_ready():
    """Kirim item READY via antrean WhatsApp Phase 10G (menghormati safety). Menangani follow-up lead & payment."""
    s = await _afu_settings()
    summary = {"sent": 0, "cancelled": 0, "skipped": 0}
    if not s.get("enabled"):
        return summary
    wa = await _wa_safety()
    if not wa.get("messaging_enabled", True):
        return summary
    if s.get("business_hours_enabled"):
        hm = datetime.now(timezone.utc).strftime("%H:%M")
        if not ((s.get("opening_time") or "00:00") <= hm <= (s.get("closing_time") or "23:59")):
            return summary
    items = await db.ai_followup_queue.find({"status": "READY"}).sort("created_at", 1).to_list(100)
    for it in items:
        cid = it.get("customer_id")
        lead = await db.leads.find_one({"_id": ObjectId(it["lead_id"])}) if it.get("lead_id") and ObjectId.is_valid(it["lead_id"]) else None
        conv = await db.whatsapp_conversations.find_one({"_id": ObjectId(it["conversation_id"])}) if ObjectId.is_valid(it.get("conversation_id") or "") else None
        if not conv:
            await db.ai_followup_queue.update_one({"_id": it["_id"]}, {"$set": {"status": "CANCELLED", "cancel_reason": "missing conv", "updated_at": now_iso()}})
            summary["cancelled"] += 1
            continue
        if conv.get("status") == "HUMAN HANDOVER":
            await db.ai_followup_queue.update_one({"_id": it["_id"]}, {"$set": {"status": "CANCELLED", "cancel_reason": "handover", "updated_at": now_iso()}})
            summary["cancelled"] += 1
            continue
        allowed, why = await _wa_outbound_allowed(cid)
        if not allowed:
            await db.ai_followup_queue.update_one({"_id": it["_id"]}, {"$set": {"status": "CANCELLED", "cancel_reason": why, "updated_at": now_iso()}})
            summary["cancelled"] += 1
            continue
        last_sent = await db.ai_followup_queue.find_one({"customer_id": cid, "status": "SENT"}, sort=[("sent_at", -1)])
        if last_sent and _afu_hours_since(last_sent.get("sent_at")) < float(s.get("min_interval_hours") or 24):
            summary["skipped"] += 1
            continue
        day0 = (datetime.now(timezone.utc).date()).isoformat()
        sent_today = await db.ai_followup_queue.count_documents({"customer_id": cid, "status": "SENT", "sent_at": {"$gte": day0}})
        if sent_today >= int(s.get("daily_limit_per_customer") or 1):
            summary["skipped"] += 1
            continue
        await db.ai_followup_queue.update_one({"_id": it["_id"]}, {"$set": {"status": "PROCESSING", "updated_at": now_iso()}})
        await _wa_enqueue_outbound(conv, it["message"], sender="AI")
        if lead:
            newcount = int(lead.get("followup_count") or 0) + 1
            lead_upd = {"followup_count": newcount, "last_followup_at": now_iso(), "followup_updated_at": now_iso()}
            if newcount >= int(s.get("max_followup") or 3):
                lead_upd["auto_followup_status"] = "COMPLETED"
                lead_upd["followup_stopped_reason"] = "max_followup_reached"
            await db.leads.update_one({"_id": lead["_id"]}, {"$set": lead_upd})
        await db.ai_followup_queue.update_one({"_id": it["_id"]}, {"$set": {"status": "SENT", "sent_at": now_iso(), "updated_at": now_iso()}})
        if it.get("ab_variant"):
            await _afu_ab_inc("sent", it.get("ab_variant"))
        summary["sent"] += 1
    return summary


async def _afu_cron_run():
    try:
        sch = await _afu_evaluate_and_schedule()
        pay = await _afu_evaluate_payment_followups()
        snd = await _afu_process_ready()
        logger.info(f"[AFU] cron scheduled={sch} payment={pay} sent={snd}")
    except Exception as e:
        logger.error(f"[AFU] cron error: {e}")


@api_router.post("/cron/ai-followup")
async def cron_ai_followup(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not secret or not _hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    background.add_task(_afu_cron_run)
    return {"accepted": True}


@api_router.get("/ai/followup/settings")
async def afu_get_settings(user: dict = Depends(require_role("super_admin"))):
    return {**await _afu_settings(), "intents": AFU_INTENTS, "queue_statuses": AFU_QUEUE_STATUSES}


@api_router.put("/ai/followup/settings")
async def afu_put_settings(body: dict, request: Request, user: dict = Depends(require_role("super_admin"))):
    upd = {k: body[k] for k in AFU_SETTING_KEYS if k in body}
    upd["updated_at"] = now_iso()
    await db.autofollowup_settings.update_one({"_id": "main"}, {"$set": upd}, upsert=True)
    await log_audit(user, "ai_followup", "update_settings", request, new={k: v for k, v in upd.items() if k != "intent_guidance"})
    return await _afu_settings()


@api_router.get("/ai/followup/queue")
async def afu_queue(status: str = "", user: dict = Depends(require_role("super_admin"))):
    q = {} if not status else {"status": status.upper()}
    items = await db.ai_followup_queue.find(q).sort("created_at", -1).to_list(200)
    counts = {st: await db.ai_followup_queue.count_documents({"status": st}) for st in AFU_QUEUE_STATUSES}
    return {"items": [serialize(i) for i in items], "counts": counts}


@api_router.post("/ai/followup/queue/{qid}/cancel")
async def afu_queue_cancel(qid: str, user: dict = Depends(require_role("super_admin"))):
    if not ObjectId.is_valid(qid):
        raise HTTPException(status_code=404, detail="Not found")
    await db.ai_followup_queue.update_one({"_id": ObjectId(qid)}, {"$set": {"status": "CANCELLED", "cancel_reason": "manual", "updated_at": now_iso()}})
    return {"ok": True}


@api_router.post("/ai/followup/run")
async def afu_run(body: dict = None, user: dict = Depends(require_role("super_admin"))):
    dry = True if body is None else bool(body.get("dry_run", True))
    sch = await _afu_evaluate_and_schedule(dry_run_default=dry)
    pay = await _afu_evaluate_payment_followups(dry_run_default=dry)
    snd = await _afu_process_ready() if not dry else {"sent": 0, "cancelled": 0, "skipped": 0}
    return {"scheduled": sch, "payment": pay, "sent": snd, "dry_run": dry}


@api_router.post("/ai/followup/preview")
async def afu_preview(body: dict, user: dict = Depends(require_role("super_admin"))):
    lid = (body or {}).get("lead_id")
    if not lid or not ObjectId.is_valid(lid):
        raise HTTPException(status_code=400, detail="lead_id wajib")
    lead = await db.leads.find_one({"_id": ObjectId(lid)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead tidak ditemukan")
    cid = lead.get("customer_id")
    conv = await db.whatsapp_conversations.find_one({"customer_id": cid}) if cid else None
    if not conv:
        return {"ok": False, "message": None, "note": "Lead belum punya percakapan WhatsApp (tidak ada dasar interaksi)."}
    cvid = str(conv["_id"])
    last_in = await db.whatsapp_messages.find_one({"conversation_id": cvid, "direction": "INBOUND"}, sort=[("created_at", -1)])
    has_q = bool(await db.quotations.find_one({"customer_id": cid, "status": {"$nin": ["CONVERTED", "EXPIRED", "REJECTED"]}}))
    intent = (body.get("intent") or _afu_detect_intent((last_in or {}).get("content", ""), has_q, False)).upper()
    s = await _afu_settings()
    number = int(lead.get("followup_count") or 0) + 1
    msg = await _afu_generate_message(lead, conv, s, number, intent)
    return {"ok": bool(msg), "message": msg, "intent": intent, "followup_number": number,
            "customer_name": lead.get("customer_name"), "last_message": (last_in or {}).get("content", "")}


@api_router.get("/ai/followup/leads")
async def afu_leads(user: dict = Depends(require_role("super_admin"))):
    leads = await db.leads.find({"is_deleted": {"$ne": True}, "status": {"$in": AFU_ELIGIBLE_STAGES}}).sort("created_at", -1).to_list(500)
    out = []
    for l in leads:
        cid = l.get("customer_id")
        conv = await db.whatsapp_conversations.find_one({"customer_id": cid}) if cid and ObjectId.is_valid(cid) else None
        out.append({"id": str(l["_id"]), "lead_code": l.get("lead_code"), "customer_name": l.get("customer_name"),
                    "stage": l.get("status"), "auto_followup_status": l.get("auto_followup_status", "ACTIVE"),
                    "followup_count": int(l.get("followup_count") or 0), "customer_intent": l.get("customer_intent"),
                    "last_followup_at": l.get("last_followup_at"), "interested_package": l.get("interested_package"),
                    "has_conversation": bool(conv), "stopped_reason": l.get("followup_stopped_reason")})
    return out


@api_router.post("/ai/followup/leads/{lid}/status")
async def afu_lead_status(lid: str, body: dict, user: dict = Depends(require_role("super_admin"))):
    st = (body or {}).get("status", "").upper()
    if st not in ("ACTIVE", "PAUSED", "STOPPED"):
        raise HTTPException(status_code=400, detail="status harus ACTIVE/PAUSED/STOPPED")
    if not ObjectId.is_valid(lid):
        raise HTTPException(status_code=404, detail="Not found")
    await db.leads.update_one({"_id": ObjectId(lid)}, {"$set": {"auto_followup_status": st, "followup_updated_at": now_iso()}})
    if st in ("PAUSED", "STOPPED"):
        await db.ai_followup_queue.update_many({"lead_id": lid, "status": {"$in": ["SCHEDULED", "READY", "PROCESSING"]}},
                                               {"$set": {"status": "CANCELLED", "cancel_reason": f"admin_{st.lower()}", "updated_at": now_iso()}})
    return {"ok": True, "auto_followup_status": st}


async def _afu_ab_stats():
    doc = await db.afu_ab_stats.find_one({"_id": "main"}) or {}
    return {"A": doc.get("A", {"sent": 0, "response": 0}), "B": doc.get("B", {"sent": 0, "response": 0}), "winner": doc.get("winner")}


async def _afu_ab_choose(s):
    if not s.get("ab_testing_enabled"):
        return None, ""
    st = await _afu_ab_stats()
    styles = {"A": s.get("ab_style_a", ""), "B": s.get("ab_style_b", "")}
    if st.get("winner") in ("A", "B"):
        return st["winner"], styles.get(st["winner"], "")
    import random as _r
    v = "A" if _r.random() < 0.5 else "B"
    return v, styles.get(v, "")


async def _afu_ab_inc(field, variant):
    if variant in ("A", "B"):
        await db.afu_ab_stats.update_one({"_id": "main"}, {"$inc": {f"{variant}.{field}": 1}}, upsert=True)


async def _afu_ab_check_winner(s):
    st = await _afu_ab_stats()
    if st.get("winner"):
        return
    mn = int(s.get("ab_min_sample") or 20)
    A, B = st["A"], st["B"]
    if A.get("sent", 0) >= mn and B.get("sent", 0) >= mn:
        ra = A.get("response", 0) / A["sent"] if A.get("sent") else 0
        rb = B.get("response", 0) / B["sent"] if B.get("sent") else 0
        await db.afu_ab_stats.update_one({"_id": "main"}, {"$set": {"winner": "A" if ra >= rb else "B", "winner_at": now_iso()}}, upsert=True)


async def _afu_ab_count_responses():
    """Idempotent: tiap follow-up A/B terkirim → cek balasan customer setelahnya → +response, lalu evaluasi pemenang."""
    s = await _afu_settings()
    async for it in db.ai_followup_queue.find({"ab_variant": {"$in": ["A", "B"]}, "status": "SENT", "ab_response_counted": {"$ne": True}}):
        reply = await db.whatsapp_messages.find_one({"conversation_id": it.get("conversation_id"), "direction": "INBOUND", "created_at": {"$gt": it.get("sent_at") or ""}})
        if reply:
            await _afu_ab_inc("response", it.get("ab_variant"))
            await db.ai_followup_queue.update_one({"_id": it["_id"]}, {"$set": {"ab_response_counted": True}})
    await _afu_ab_check_winner(s)


@api_router.get("/ai/followup/ab")
async def afu_ab_get(user: dict = Depends(require_role("super_admin"))):
    s = await _afu_settings()
    st = await _afu_ab_stats()
    rate = lambda x: round((x.get("response", 0) / x["sent"]) * 100, 1) if x.get("sent") else 0.0
    return {"enabled": s.get("ab_testing_enabled"), "min_sample": s.get("ab_min_sample"),
            "style_a": s.get("ab_style_a"), "style_b": s.get("ab_style_b"),
            "A": {"sent": st["A"].get("sent", 0), "response": st["A"].get("response", 0), "rate": rate(st["A"])},
            "B": {"sent": st["B"].get("sent", 0), "response": st["B"].get("response", 0), "rate": rate(st["B"])},
            "winner": st.get("winner")}


@api_router.post("/ai/followup/ab/reset")
async def afu_ab_reset(user: dict = Depends(require_role("super_admin"))):
    await db.afu_ab_stats.delete_one({"_id": "main"})
    return {"ok": True}


@api_router.get("/ai/followup/analytics")
async def afu_analytics(user: dict = Depends(require_role("super_admin"))):
    total_leads = await db.leads.count_documents({"is_deleted": {"$ne": True}, "status": {"$in": AFU_ELIGIBLE_STAGES}})
    active = await db.leads.count_documents({"is_deleted": {"$ne": True}, "auto_followup_status": "ACTIVE", "status": {"$in": AFU_ELIGIBLE_STAGES}})
    sent = await db.ai_followup_queue.count_documents({"status": "SENT"})
    scheduled = await db.ai_followup_queue.count_documents({"status": {"$in": ["SCHEDULED", "READY", "PROCESSING"]}})
    stopped = await db.leads.count_documents({"auto_followup_status": {"$in": ["STOPPED", "PAUSED", "COMPLETED"]}})
    optout = await db.leads.count_documents({"auto_followup_status": "OPTED OUT"})
    handover = await db.leads.count_documents({"auto_followup_status": "HANDOVER"})
    converted = await db.leads.count_documents({"auto_followup_status": "CONVERTED"})
    # response: customers who replied AFTER a follow-up was sent + weekly buckets
    from datetime import date as _date, timedelta as _td
    response = 0
    revenue = 0
    booking_cnt = 0
    wk_map = {}

    def _wk(dstr):
        d10 = (dstr or "")[:10]
        if len(d10) != 10:
            return None
        try:
            dt = _date.fromisoformat(d10)
            return (dt - _td(days=dt.weekday())).isoformat()
        except Exception:
            return None

    async for it in db.ai_followup_queue.find({"status": "SENT"}):
        cvid = it.get("conversation_id")
        sent_at = it.get("sent_at") or ""
        reply = await db.whatsapp_messages.find_one({"conversation_id": cvid, "direction": "INBOUND", "created_at": {"$gt": sent_at}})
        replied = bool(reply)
        if replied:
            response += 1
        wk = _wk(sent_at)
        if wk:
            w = wk_map.setdefault(wk, {"week": wk, "sent": 0, "response": 0, "booking": 0})
            w["sent"] += 1
            if replied:
                w["response"] += 1
    # bookings & revenue from leads that got at least one follow-up
    fu_customers = await db.ai_followup_queue.distinct("customer_id", {"status": "SENT"})
    for cid in fu_customers:
        b = await db.bookings.find_one({"customer_id": cid, "status": {"$ne": "CANCELLED"}})
        if b:
            booking_cnt += 1
            revenue += float(b.get("total_amount") or b.get("total") or 0)
            bwk = _wk(b.get("created_at"))
            if bwk and bwk in wk_map:
                wk_map[bwk]["booking"] += 1
    rate = lambda n, d: round((n / d) * 100, 1) if d else 0.0
    weekly = []
    for wk in sorted(wk_map.keys())[-8:]:
        w = wk_map[wk]
        weekly.append({**w, "response_rate": rate(w["response"], w["sent"]),
                       "conversion_rate": rate(w["booking"], w["sent"])})
    payment_sent = await db.ai_followup_queue.count_documents({"source": "PAYMENT", "status": "SENT"})
    return {
        "total_leads": total_leads, "active_followup": active, "followup_sent": sent, "followup_scheduled": scheduled,
        "followup_response": response, "followup_converted": converted, "followup_booking": booking_cnt,
        "followup_revenue": revenue, "stopped_followup": stopped, "opt_out": optout, "human_handover": handover,
        "payment_followup_sent": payment_sent, "weekly": weekly,
        "response_rate": rate(response, sent), "conversion_rate": rate(converted, total_leads),
        "booking_rate": rate(booking_cnt, len(fu_customers)),
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
    await db.whatsapp_messages.create_index("message_id", unique=True)
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
    await db.bookings.create_index("booking_number")
    await db.bookings.create_index("customer_id")
    await db.bookings.create_index("customer_name")
    await db.customers.create_index("phone")
    await db.customers.create_index("email")
    await db.customers.create_index("whatsapp")
    await db.company_files.create_index("category")
    await db.company_files.create_index("created_at")
    await db.file_downloads.create_index("file_id")
    await db.file_downloads.create_index("timestamp")
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
    if await db.ppn_configurations.count_documents({}) == 0:
        await db.ppn_configurations.insert_one({
            "config_name": "PPN Besaran Tertentu 1.1% (V1)", "tax_type": "PPN", "tax_rate": 1.1, "dpp_percentage": 100,
            "effective_from": "2024-01-01", "effective_until": "", "status": "ACTIVE",
            "description": "Konfigurasi PPN default (besaran tertentu 1.1%).", "created_at": now_iso(), "created_by": "system"})
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
    asyncio.create_task(_wa_outbound_worker())
    logger.info("Safar CRM startup: indexes + seed complete")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

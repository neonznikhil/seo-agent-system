import logging
import re
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import get_supabase
from services.email_service import send_email_alert

logger = logging.getLogger("backend.routers.email")
router = APIRouter()


def _is_valid_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()))


class EmailSendIn(BaseModel):
    to: str
    subject: str
    html: str
    website_id: Optional[str] = None


class AlertEmailIn(BaseModel):
    to: str
    alert: dict
    website_id: Optional[str] = None


@router.post("/email/send")
async def send_email(body: EmailSendIn, request: Request):
    if not body.to or not body.subject or not body.html:
        raise HTTPException(status_code=400, detail="to, subject, and html are required")
    if not _is_valid_email(body.to):
        raise HTTPException(status_code=400, detail="Invalid recipient email address")

    try:
        ok = await send_email_alert(body.to, {"title": body.subject, "html": body.html})
        return {"success": ok, "message": "Email sent" if ok else "Email provider not configured"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/email/alert")
async def send_alert_email(body: AlertEmailIn, request: Request):
    if not body.to or not body.alert:
        raise HTTPException(status_code=400, detail="to and alert are required")
    if not _is_valid_email(body.to):
        raise HTTPException(status_code=400, detail="Invalid recipient email address")

    try:
        ok = await send_email_alert(body.to, body.alert)
        return {"success": ok, "message": "Alert email sent" if ok else "Email provider not configured"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

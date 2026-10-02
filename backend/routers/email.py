import logging
import re
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from database import get_supabase
from services.email_service import (
    STATUS_NOT_CONFIGURED,
    send_email_alert_detailed,
)

logger = logging.getLogger("backend.routers.email")
router = APIRouter()


def _is_valid_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()))


def _delivery_response(result: Dict[str, Any], sent_message: str, failed_message: str) -> Dict[str, Any]:
    """Map a delivery result onto the response without lying about the cause.

    A rejected key (401/403) or a provider 5xx is NOT "not configured" — reporting
    it as such told users their working setup was missing whenever Resend
    answered with an error. `success` is now False for every failure, and the
    message names the real cause.
    """
    status = result.get("status")
    if result.get("sent"):
        message = sent_message
    elif status == STATUS_NOT_CONFIGURED:
        message = failed_message
    elif status == "rejected":
        message = (
            "Email provider rejected the credentials (Resend returned 401/403). "
            "Update RESEND_API_KEY in Connectors."
        )
    else:
        message = "Email provider returned an error."

    response = {
        "success": bool(result.get("sent")),
        "message": message,
        "status": status,
        "provider": result.get("provider"),
        "provider_configured": status != STATUS_NOT_CONFIGURED,
    }
    if result.get("http_status"):
        response["provider_status_code"] = result["http_status"]
    if result.get("error") and not result.get("sent"):
        response["error"] = result["error"]
    return response


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
        result = await send_email_alert_detailed(body.to, {"title": body.subject, "html": body.html})
        return _delivery_response(result, "Email sent", "Email provider not configured")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/email/alert")
async def send_alert_email(body: AlertEmailIn, request: Request):
    if not body.to or not body.alert:
        raise HTTPException(status_code=400, detail="to and alert are required")
    if not _is_valid_email(body.to):
        raise HTTPException(status_code=400, detail="Invalid recipient email address")

    try:
        result = await send_email_alert_detailed(body.to, body.alert)
        return _delivery_response(result, "Alert email sent", "Email provider not configured")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

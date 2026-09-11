"""Workflows Router: API endpoints for 9 independent SEO workflows.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException

try:
    from database import get_supabase, set_account_context
except (ImportError, ValueError):
    from backend.database import get_supabase, set_account_context

from middleware.auth import get_current_account_id
from services.workflow_service import (
    WORKFLOW_JOBS,
    run_workflow_job,
    get_all_workflows_status,
)

logger = logging.getLogger("backend.routers.workflows")
router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/{website_id}/status")
async def get_workflows_status(website_id: str, request: Request):
    """Return status, description, and latest diff/summary for all 9 workflows."""
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    try:
        data = await get_all_workflows_status(website_id)
        return data
    except Exception as e:
        logger.error(f"[WorkflowsAPI] status failed for {website_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{website_id}/run/{job_name}")
async def run_single_workflow(website_id: str, job_name: str, request: Request):
    """Trigger a single independent workflow job under a run envelope."""
    account_id = get_current_account_id(request)
    supabase = get_supabase()
    set_account_context(supabase, account_id)

    if job_name not in WORKFLOW_JOBS:
        raise HTTPException(status_code=400, detail=f"Invalid job_name '{job_name}'. Valid: {WORKFLOW_JOBS}")

    try:
        res = await run_workflow_job(website_id, job_name)
        return res
    except Exception as e:
        logger.error(f"[WorkflowsAPI] run failed for {job_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import logging
from typing import Dict, Any, Type, Optional
from pydantic import BaseModel, ValidationError
from datetime import datetime
from backend.database import get_supabase

logger = logging.getLogger("backend.services.validation_service")


class ValidationService:
    """Enterprise Data Validation Layer using Pydantic v2."""

    @classmethod
    def validate_and_insert(cls, table_name: str, model_cls: Type[BaseModel], data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payload against Pydantic schema before executing Supabase insert."""
        supabase = get_supabase()
        try:
            validated_obj = model_cls.model_validate(data)
            dumped = validated_obj.model_dump()
            res = supabase.table(table_name).insert(dumped).execute()
            return {"success": True, "data": res.data[0] if res.data else dumped}
        except ValidationError as ve:
            err_msg = str(ve)
            logger.error(f"[DataValidation] Validation failed for table '{table_name}': {err_msg}")
            # Record in validation_errors table
            try:
                supabase.table("validation_errors").insert({
                    "table_name": table_name,
                    "failed_data": data,
                    "error_message": err_msg[:500],
                    "severity": "warning",
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            except Exception:
                pass
            return {"success": False, "error": err_msg, "validation_error": True}
        except Exception as e:
            logger.error(f"[DataValidation] DB Insert error for '{table_name}': {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def get_validation_errors(cls, limit: int = 50) -> Dict[str, Any]:
        """Retrieve recent data validation errors for Data Health dashboard."""
        supabase = get_supabase()
        try:
            res = supabase.table("validation_errors").select("*").order("created_at", desc=True).limit(limit).execute()
            errors = res.data or []
            counts_by_table = {}
            for e in errors:
                tbl = e.get("table_name", "unknown")
                counts_by_table[tbl] = counts_by_table.get(tbl, 0) + 1
            return {
                "success": True,
                "total_errors": len(errors),
                "counts_by_table": counts_by_table,
                "errors": errors
            }
        except Exception as e:
            return {"success": True, "total_errors": 0, "counts_by_table": {}, "errors": []}

# Implementation Plan: Fix GA4 & GSC Connector Integrations

**Date:** 2026-10-02  
**Goal:** Fix connector integration bugs preventing Google Analytics 4 (GA4) and Google Search Console (GSC) from validating, saving, and syncing credentials properly, eliminate false-positive success toasts in the frontend, and ensure dynamic in-memory credential testing and property ID sanitization work reliably.

---

## 1. Problem Diagnosis & Root Causes

1. **Dynamic Payload Credentials Dropped During Testing**:
   - `/api/connectors/test-ga4` receives `payload.property_id` and `payload.credentials_json`, but calls `ga4_service.get_recent_sessions(website_id=..., days=7)` without passing either argument. It falls back to global environment variables which might not be set yet.
   - `/api/connectors/test-gsc` receives `payload.credentials_json` and `payload.property_url`, but calls `list_verified_sites()` with zero arguments, dropping both credentials and target URL.
2. **Environment Variable Mismatch & Lack of Dynamic JSON Support**:
   - `save_generic_connector` and `save_all_connectors` persist `GA4_CREDENTIALS_JSON` and `GSC_SERVICE_ACCOUNT_JSON`.
   - `ga4_service.py` only looked for `GA4_CREDENTIALS` or `GSC_CREDENTIALS`.
   - `gsc_service.py` only looked for `GSC_CREDENTIALS` or `GOOGLE_APPLICATION_CREDENTIALS`.
   - Neither service supported passing `credentials_json` directly into `__init__`.
3. **GA4 Response Error Masking**:
   - `ga4_service.get_recent_sessions()` returns errors as `{"connected": False, "error": str(e)[:200], "sessions": 0}`.
   - `connectors.py::test_ga4` checked `res.get("message")` and defaulted to `"GA4 not configured. Set GA4_PROPERTY_ID and credentials."`, hiding the true error (e.g. Permission Denied, Invalid Property ID, or Quota Exceeded).
4. **Frontend False Positives**:
   - In `frontend-next/app/connectors/page.tsx`, `handleTestGsc` and `handleTestGa4` called `showToast(...)` unconditionally on HTTP 200 without checking `res.connected === true`.
5. **Property ID Formatting**:
   - Users frequently input `properties/123456789` or values with leading/trailing whitespace. Both frontend and backend need to sanitize this to clean numeric IDs.

---

### Status: COMPLETE (Commit `67c68bf`)

---

## 2. Changes Implemented

### Task 1: Update `backend/services/ga4_service.py` [x]
- Modified `GA4Service.__init__(self, property_id: str = None, credentials_path: str = None, credentials_json: Union[str, dict] = None)`.
- In `_ensure_initialized()`: Support `self._credentials_json` before reading `os.getenv("GA4_CREDENTIALS")`, `os.getenv("GA4_CREDENTIALS_JSON")`, `os.getenv("GSC_CREDENTIALS")`, `os.getenv("GSC_SERVICE_ACCOUNT_JSON")`.
- In `is_connected()`: Check `self._credentials_json` and `os.getenv("GA4_CREDENTIALS_JSON")`.
- In `get_recent_sessions()` and `_GA4SingletonWrapper.get_recent_sessions()`: Accept `property_id: Optional[str] = None` and `credentials_json: Optional[Union[str, dict]] = None`. When provided, instantiate a scoped `GA4Service(property_id=property_id, credentials_json=credentials_json)`.

### Task 2: Update `backend/services/gsc_service.py` [x]
- Modified `GSCService.__init__(self, website_url: str = None, credentials_path: str = None, credentials_json: Union[str, dict] = None)`.
- In `_get_service()`: Support `self.credentials_json` first, and check `os.getenv("GSC_SERVICE_ACCOUNT_JSON")` alongside `GSC_CREDENTIALS`.
- In `is_connected()`: Recognize `self.credentials_json` and `os.getenv("GSC_SERVICE_ACCOUNT_JSON")`.
- In `list_verified_sites()`: Accept `website_url: Optional[str] = None` and `credentials_json: Optional[Union[str, dict]] = None` and pass both to `GSCService`.

### Task 3: Update `backend/routers/connectors.py` [x]
- In `test_gsc`: Pass `website_url=payload.property_url` and `credentials_json=cred_json` to `list_verified_sites`.
- In `test_ga4`: Sanitize `prop_id` (strip `properties/` and whitespace); pass `property_id=clean_prop_id` and `credentials_json=payload.credentials_json` to `ga4_service.get_recent_sessions()`. Ensure error message extraction falls back to `res.get("error")`.
- In `save_generic_connector` & `save_all_connectors`: Ensure dual write of `GA4_CREDENTIALS` & `GA4_CREDENTIALS_JSON`, and `GSC_CREDENTIALS` & `GSC_SERVICE_ACCOUNT_JSON`. Sanitize `GA4_PROPERTY_ID`.

### Task 4: Update `frontend-next/app/connectors/page.tsx` [x]
- In `handleTestGsc`: Inspect `res?.connected`. If true, `showToast(...)`. If false, `setErrorMsg(res?.message || "GSC connection failed.")`.
- In `handleTestGa4`: Inspect `res?.connected`. If true, `showToast(...)`. If false, `setErrorMsg(res?.message || "GA4 connection failed.")`.
- In `handleTestGa4`, `handleTestGa4Stream`, and `handleSaveAll`: Sanitize `ga4PropertyId` by removing leading `properties/` and whitespace.

### Task 5: Add Unit & Integration Tests and Verify [x]
- Added tests in `backend/tests/test_connectors_google.py` covering dynamic credentials testing, error reporting honesty, and dual-env saves.
- Verified backend tests with `pytest` (16 passed, 0 failed).
- Verified frontend type check with `npx tsc --noEmit` (clean, 0 errors).

---

## 3. Verification Criteria Results
- `pytest tests/test_connectors_google.py tests/test_connector_honesty.py -v`: 16 passed, 0 failed.
- `cd frontend-next && npx tsc --noEmit`: Clean, 0 errors.
- Verified live git commit and push to `origin/main` (`67c68bf`).


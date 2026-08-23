import os
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_docker_and_ci_files():
    """Verify Dockerfiles, docker-compose, CI workflow, and relative paths."""
    docker_compose = PROJECT_ROOT / "docker-compose.yml"
    backend_dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
    frontend_dockerfile = PROJECT_ROOT / "frontend-next" / "Dockerfile"
    ci_workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    production_md = PROJECT_ROOT / "PRODUCTION.md"

    assert docker_compose.exists(), "docker-compose.yml missing"
    assert backend_dockerfile.exists(), "backend/Dockerfile missing"
    assert frontend_dockerfile.exists(), "frontend-next/Dockerfile missing"
    assert ci_workflow.exists(), ".github/workflows/ci.yml missing"
    assert production_md.exists(), "PRODUCTION.md missing"

    # Verify no absolute C:\ paths in docker-compose.yml
    dc_text = docker_compose.read_text(encoding="utf-8")
    assert "C:\\" not in dc_text, "Hardcoded C:\\ path found in docker-compose.yml"
    assert "backend/Dockerfile" in dc_text
    assert "frontend-next/Dockerfile" in dc_text

    # Verify Dockerfile base images
    b_df = backend_dockerfile.read_text(encoding="utf-8")
    assert "python:3.11-slim" in b_df
    assert "WORKDIR /app/backend" in b_df

    f_df = frontend_dockerfile.read_text(encoding="utf-8")
    assert "node:18-alpine" in f_df


def test_start_scripts_use_relative_dp0():
    """Verify batch start scripts use %~dp0 instead of hardcoded paths."""
    b_bat = PROJECT_ROOT / "start-backend.bat"
    f_bat = PROJECT_ROOT / "start-frontend.bat"

    if b_bat.exists():
        text = b_bat.read_text(encoding="utf-8")
        assert "%~dp0" in text
        assert "C:\\Users" not in text

    if f_bat.exists():
        text = f_bat.read_text(encoding="utf-8")
        assert "%~dp0" in text
        assert "C:\\Users" not in text


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health monitoring endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/connectors/status")
        assert res.status_code == 200
        data = res.json()
        assert data.get("supabase", {}).get("connected") is True

"""Tests for the mandatory onboarding flow (P1)."""
from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from src.models.models import User


@pytest.mark.asyncio
async def test_status_initially_incomplete(
    client: AsyncClient, auth_headers: dict
):
    response = await client.get("/api/v1/onboarding/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is False
    assert "address" in body["missing"]
    assert "hourly_rate" in body["missing"]
    assert "material_cost_markup" in body["missing"]


@pytest.mark.asyncio
async def test_complete_writes_fields_and_stamps(
    client: AsyncClient, auth_headers: dict, test_session, test_user: User
):
    payload = {
        "company_name": "Maler Müller GmbH",
        "address": "Hauptstraße 1, 1010 Wien",
        "vat_id": "ATU12345678",
        "hourly_rate": 55.0,
        "material_cost_markup": 12.0,
    }
    response = await client.post(
        "/api/v1/onboarding/complete", headers=auth_headers, json=payload
    )
    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "Maler Müller GmbH"
    assert body["hourly_rate"] == 55.0
    assert body["material_cost_markup"] == 12.0
    assert body["vat_id"] == "ATU12345678"
    assert body["onboarding_completed_at"] is not None

    status_response = await client.get(
        "/api/v1/onboarding/status", headers=auth_headers
    )
    assert status_response.json()["completed"] is True


@pytest.mark.asyncio
async def test_complete_is_idempotent(
    client: AsyncClient, auth_headers: dict
):
    payload = {
        "company_name": "Maler X",
        "address": "Foo 1",
        "hourly_rate": 50.0,
        "material_cost_markup": 10.0,
    }
    first = await client.post(
        "/api/v1/onboarding/complete", headers=auth_headers, json=payload
    )
    assert first.status_code == 200

    payload2 = {**payload, "company_name": "Maler Y", "hourly_rate": 60.0}
    second = await client.post(
        "/api/v1/onboarding/complete", headers=auth_headers, json=payload2
    )
    assert second.status_code == 200
    assert second.json()["company_name"] == "Maler Y"
    assert second.json()["hourly_rate"] == 60.0


@pytest.mark.asyncio
async def test_complete_rejects_invalid_hourly_rate(
    client: AsyncClient, auth_headers: dict
):
    response = await client.post(
        "/api/v1/onboarding/complete",
        headers=auth_headers,
        json={
            "company_name": "X",
            "address": "Foo",
            "hourly_rate": -5,
            "material_cost_markup": 10,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_complete_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/onboarding/complete",
        json={
            "company_name": "X",
            "address": "F",
            "hourly_rate": 1,
            "material_cost_markup": 1,
        },
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_logo_upload_rejects_wrong_mime(
    client: AsyncClient, auth_headers: dict
):
    response = await client.post(
        "/api/v1/onboarding/logo",
        headers=auth_headers,
        files={"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_logo_upload_accepts_png(
    client: AsyncClient, auth_headers: dict, tmp_path, monkeypatch
):
    from src.routes import onboarding as onboarding_module

    monkeypatch.setattr(onboarding_module, "_LOGO_DIR", tmp_path)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    response = await client.post(
        "/api/v1/onboarding/logo",
        headers=auth_headers,
        files={"file": ("logo.png", png_bytes, "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["logo_path"]


@pytest.mark.asyncio
async def test_logo_upload_rejects_too_large(
    client: AsyncClient, auth_headers: dict, tmp_path, monkeypatch
):
    from src.routes import onboarding as onboarding_module

    monkeypatch.setattr(onboarding_module, "_LOGO_DIR", tmp_path)
    monkeypatch.setattr(onboarding_module, "_LOGO_MAX_BYTES", 100)

    big = b"\x89PNG\r\n\x1a\n" + b"x" * 200
    response = await client.post(
        "/api/v1/onboarding/logo",
        headers=auth_headers,
        files={"file": ("big.png", big, "image/png")},
    )
    assert response.status_code == 413

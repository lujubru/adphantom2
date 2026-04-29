"""
Tests for CSV-broadcasts foundation (iteration 8 — Deliverable 1):
- Helpers: _norm_e164, is_optout_message
- Endpoints: list/upload audiences, list optouts, list templates (gracefully when no WABA)
- Permissions: cajeros only see/touch their own line_ids
- Webhook auto-optout detection

Run:  cd /app/backend && python tests/test_broadcasts_csv.py
"""
import asyncio
import io
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://7d3700be-cf81-4e00-8415-edcf6298aedc.preview.emergentagent.com")
ADMIN_EMAIL = "admin@maxi.com"
ADMIN_PASS = "admin123"


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    r = await client.post(f"{API_URL}/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


async def test_helpers(db):
    from server import _norm_e164, is_optout_message
    assert _norm_e164("+54 9 11 1234-5678") == "5491112345678"
    assert _norm_e164("11-1234-5678") == "1112345678"
    assert _norm_e164("123") is None  # too short
    assert _norm_e164("") is None
    assert _norm_e164(None) is None

    assert is_optout_message("BAJA") is True
    assert is_optout_message("baja") is True
    assert is_optout_message("  Stop. ") is True
    assert is_optout_message("NO QUIERO MAS!!!") is True
    assert is_optout_message("hola") is False
    assert is_optout_message("") is False
    assert is_optout_message("nope") is False  # not in keyword list
    print("  PASS test_helpers")


async def test_endpoints_e2e(db):
    """End-to-end via the live API: seed line + cajero, login, exercise endpoints."""
    # Seed test line + cajero user
    line_id = "test-bcsv-line-" + uuid.uuid4().hex[:6]
    other_line = "test-bcsv-other-" + uuid.uuid4().hex[:6]
    cajero_email = f"cajero_bcsv_{uuid.uuid4().hex[:6]}@test.com"

    await db.crm_lines.delete_many({"id": {"$in": [line_id, other_line]}})
    await db.users.delete_many({"email": cajero_email})
    await db.broadcast_audiences.delete_many({"line_id": {"$in": [line_id, other_line]}})
    await db.broadcast_contacts.delete_many({"line_id": {"$in": [line_id, other_line]}})
    await db.broadcast_optouts.delete_many({"line_id": {"$in": [line_id, other_line]}})

    await db.crm_lines.insert_many([
        {
            "id": line_id, "name": "BetwinTest VIP", "line_type": "publi",
            "whatsapp_number": "5491100000001",
            "whatsapp_token": "TEST_TOKEN", "phone_number_id": "111",
            "whatsapp_business_account_id": "",  # not configured -> templates endpoint should 400
            "is_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": other_line, "name": "OtherLine", "line_type": "publi",
            "whatsapp_number": "5491100000002",
            "is_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ])

    # Create a cajero scoped to ONLY line_id (not other_line)
    from server import pwd_context
    pw_hash = pwd_context.hash("caje123")
    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "email": cajero_email,
        "hashed_password": pw_hash,
        "name": "Cajero BCSV",
        "role": "cajero",
        "line_ids": [line_id],
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        admin_token = await _login(client, ADMIN_EMAIL, ADMIN_PASS)
        cajero_token = await _login(client, cajero_email, "caje123")

        # ── 1. Templates without WABA configured → 400 ───────────
        r = await client.get(
            f"{API_URL}/api/broadcasts/templates?line_id={line_id}",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert r.status_code == 400, f"templates without WABA must 400, got {r.status_code}"
        assert "WABA" in r.text or "Business Account" in r.text
        print("  PASS templates_400_when_no_waba")

        # ── 2. Cajero forbidden on a line they don't have ────────
        r = await client.get(
            f"{API_URL}/api/broadcasts/templates?line_id={other_line}",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert r.status_code == 403, f"forbidden line must 403, got {r.status_code}"
        print("  PASS cajero_forbidden_on_other_line")

        # ── 3. Upload CSV ────────────────────────────────────────
        csv_text = (
            "phone,name,var1\n"
            "+54 9 11 1234-5678,Juan,oferta1\n"
            "5491155556666,Maria,oferta2\n"
            "5491155556666,Maria DUP,oferta3\n"   # duplicate, will be excluded
            "abc-not-a-phone,Pedro,x\n"           # invalid, will be excluded
            "5491133334444,Optouted,y\n"          # will be excluded by optout (set below)
        )
        # Pre-add an optout so the upload excludes it
        await db.broadcast_optouts.insert_one({
            "id": str(uuid.uuid4()),
            "line_id": line_id, "phone": "5491133334444",
            "reason": "test", "added_by": "test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        files = {"file": ("test.csv", csv_text.encode("utf-8"), "text/csv")}
        data = {"line_id": line_id, "name": "Mi audiencia test"}
        r = await client.post(
            f"{API_URL}/api/broadcasts/audiences/upload",
            headers={"Authorization": f"Bearer {cajero_token}"},
            files=files, data=data,
        )
        assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
        body = r.json()
        aud = body["audience"]
        assert aud["total_contacts"] == 2, f"expected 2 valid contacts, got {aud['total_contacts']}"
        assert aud["stats"]["invalid"] == 1
        assert aud["stats"]["duplicates"] == 1
        assert aud["stats"]["excluded_optouts"] == 1
        assert "var1" in aud["stats"]["var_columns"]
        audience_id = aud["id"]
        print("  PASS upload_csv_dedupe_invalid_optout_filtering")

        # ── 4. Cajero CANNOT upload to other_line ────────────────
        files = {"file": ("test.csv", b"phone\n5491100009999\n", "text/csv")}
        data = {"line_id": other_line, "name": "should fail"}
        r = await client.post(
            f"{API_URL}/api/broadcasts/audiences/upload",
            headers={"Authorization": f"Bearer {cajero_token}"},
            files=files, data=data,
        )
        assert r.status_code == 403, f"cajero upload to other line must 403, got {r.status_code}"
        print("  PASS upload_forbidden_other_line")

        # ── 5. List audiences scoped to user ────────────────────
        r = await client.get(
            f"{API_URL}/api/broadcasts/audiences",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert r.status_code == 200
        ids = [a["id"] for a in r.json()["audiences"]]
        assert audience_id in ids
        # admin sees it too
        r = await client.get(
            f"{API_URL}/api/broadcasts/audiences",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert audience_id in [a["id"] for a in r.json()["audiences"]]
        print("  PASS list_audiences_scoped")

        # ── 6. Get audience detail with sample contacts ─────────
        r = await client.get(
            f"{API_URL}/api/broadcasts/audiences/{audience_id}",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert r.status_code == 200
        d = r.json()
        assert len(d["sample"]) == 2
        # contact phones must be normalized (digits only)
        phones = {c["phone"] for c in d["sample"]}
        assert "5491112345678" in phones
        assert "5491155556666" in phones
        print("  PASS audience_detail_sample")

        # ── 7. Manual optout add + list + delete ────────────────
        r = await client.post(
            f"{API_URL}/api/broadcasts/optouts",
            headers={"Authorization": f"Bearer {cajero_token}"},
            json={"line_id": line_id, "phone": "+54 9 11 5555-0000", "reason": "tested"},
        )
        assert r.status_code == 200
        # Confirm normalization
        oo = await db.broadcast_optouts.find_one({"line_id": line_id, "phone": "5491155550000"})
        assert oo is not None, "optout must be persisted with normalized phone"

        r = await client.get(
            f"{API_URL}/api/broadcasts/optouts?line_id={line_id}",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert r.status_code == 200
        phones = {o["phone"] for o in r.json()["optouts"]}
        assert "5491155550000" in phones
        # Cajero can't list optouts of other line
        r = await client.get(
            f"{API_URL}/api/broadcasts/optouts?line_id={other_line}",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert r.status_code == 403
        print("  PASS optout_crud_and_scoping")

        # ── 8. Delete audience ──────────────────────────────────
        r = await client.delete(
            f"{API_URL}/api/broadcasts/audiences/{audience_id}",
            headers={"Authorization": f"Bearer {cajero_token}"},
        )
        assert r.status_code == 200
        assert (await db.broadcast_audiences.find_one({"id": audience_id})) is None
        assert (await db.broadcast_contacts.count_documents({"audience_id": audience_id})) == 0
        print("  PASS audience_delete")

    # cleanup
    await db.crm_lines.delete_many({"id": {"$in": [line_id, other_line]}})
    await db.users.delete_many({"email": cajero_email})
    await db.broadcast_optouts.delete_many({"line_id": {"$in": [line_id, other_line]}})


async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["traffic_guardian"]
    print("=== CSV broadcasts foundation tests ===")
    failures = 0
    tests = (test_helpers, test_endpoints_e2e)
    for tc in tests:
        try:
            await tc(db)
        except AssertionError as e:
            failures += 1
            print(f"  FAIL {tc.__name__}: {e}")
        except Exception as e:
            failures += 1
            import traceback
            print(f"  ERROR {tc.__name__}: {e}\n{traceback.format_exc()}")
    client.close()
    print(f"=== {len(tests) - failures}/{len(tests)} test groups passed ===")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

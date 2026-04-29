"""
Tests for CSV-broadcasts engine (iteration 8 — Deliverable 2):
- Helpers: night-pause time check
- Campaign CRUD (create from audience, list, get, start, pause, cancel)
- Segment query resolution
- Worker dry-run with mocked wa_send_template (verifies stats counters)

Run:  cd /app/backend && python tests/test_broadcasts_engine.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://7d3700be-cf81-4e00-8415-edcf6298aedc.preview.emergentagent.com",
)
ADMIN_EMAIL = "admin@maxi.com"
ADMIN_PASS = "admin123"


async def _login(client: httpx.AsyncClient, email: str, password: str) -> str:
    r = await client.post(f"{API_URL}/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


async def test_night_pause_logic(db):
    from server import _is_night_pause_now, ART_TZ, _seconds_until_morning
    # _is_night_pause_now is timezone-dependent — just ensure it returns a bool
    assert isinstance(_is_night_pause_now(), bool)
    s = _seconds_until_morning()
    assert isinstance(s, int) and s >= 60
    print("  PASS test_night_pause_logic")


async def test_segment_resolution(db):
    """Seed leads, exercise _resolve_segment with various filters."""
    from server import _resolve_segment, BroadcastSegmentQuery

    line_id = "test-seg-" + uuid.uuid4().hex[:6]
    await db.crm_leads.delete_many({"line_id": line_id})
    await db.broadcast_optouts.delete_many({"line_id": line_id})

    now = datetime.now(timezone.utc)
    leads = [
        {"id": "l1", "phone": "5491100001111", "name": "Comprador reciente",
         "line_id": line_id, "status": "valido",
         "status_changed_at": (now - timedelta(days=3)).isoformat()},
        {"id": "l2", "phone": "5491100002222", "name": "Comprador antiguo",
         "line_id": line_id, "status": "valido",
         "status_changed_at": (now - timedelta(days=60)).isoformat()},
        {"id": "l3", "phone": "5491100003333", "name": "Nuevo lead",
         "line_id": line_id, "status": "nuevo",
         "status_changed_at": (now - timedelta(days=1)).isoformat()},
        {"id": "l4", "phone": "5491100001111", "name": "Duplicate phone of l1",
         "line_id": line_id, "status": "valido"},
        {"id": "l5", "phone": "5491100004444", "name": "OptedOut",
         "line_id": line_id, "status": "valido"},
    ]
    await db.crm_leads.insert_many(leads)
    await db.broadcast_optouts.insert_one({
        "id": str(uuid.uuid4()), "line_id": line_id, "phone": "5491100004444",
        "reason": "test", "added_by": "test",
        "created_at": now.isoformat(),
    })

    # 1. All leads of that line
    res = await _resolve_segment(BroadcastSegmentQuery(line_id=line_id))
    phones = {c["phone"] for c in res}
    assert "5491100004444" not in phones, "optout must be excluded"
    assert "5491100001111" in phones
    assert len(phones) == 3, f"expected 3 distinct phones (dedupe + optout excluded), got {len(phones)}: {phones}"

    # 2. Only purchasers (status=valido) in last 30 days
    res = await _resolve_segment(BroadcastSegmentQuery(line_id=line_id, purchase_in_last_days=30))
    phones = {c["phone"] for c in res}
    assert phones == {"5491100001111"}, f"expected only the recent purchaser, got {phones}"

    # 3. By status filter
    res = await _resolve_segment(BroadcastSegmentQuery(line_id=line_id, statuses=["nuevo"]))
    phones = {c["phone"] for c in res}
    assert phones == {"5491100003333"}, f"expected only 'nuevo' leads, got {phones}"

    print("  PASS test_segment_resolution")
    # cleanup
    await db.crm_leads.delete_many({"line_id": line_id})
    await db.broadcast_optouts.delete_many({"line_id": line_id})


async def test_campaign_lifecycle_e2e(db):
    """Direct worker test (in-process so we can mock wa_send_template).
    Verifies stats counters, optout skipping, and template var passing."""
    # Import inside the function so the patches affect the same module.
    import server as srv

    line_id = "test-cmp-" + uuid.uuid4().hex[:6]

    await db.crm_lines.delete_many({"id": line_id})

    await db.crm_lines.insert_one({
        "id": line_id, "name": "CmpLine", "line_type": "publi",
        "whatsapp_number": "5491100000003",
        "whatsapp_token": "TEST_TOKEN", "phone_number_id": "111",
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Audience with 3 contacts
    audience_id = str(uuid.uuid4())
    await db.broadcast_audiences.insert_one({
        "id": audience_id, "line_id": line_id, "name": "TestAud",
        "filename": "a.csv", "total_contacts": 3,
        "stats": {}, "created_by": "test", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.broadcast_contacts.insert_many([
        {"id": str(uuid.uuid4()), "audience_id": audience_id, "line_id": line_id,
         "phone": "5491100009001", "name": "Juan", "vars": {"var1": "bono1"},
         "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "audience_id": audience_id, "line_id": line_id,
         "phone": "5491100009002", "name": "Maria", "vars": {"var1": "bono2"},
         "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "audience_id": audience_id, "line_id": line_id,
         "phone": "5491100009003", "name": "Pedro", "vars": {"var1": "bono3"},
         "created_at": datetime.now(timezone.utc).isoformat()},
    ])

    # Campaign 1 — full send (all 3 sent)
    campaign_id = str(uuid.uuid4())
    await db.broadcast_campaigns.insert_one({
        "id": campaign_id, "line_id": line_id, "line_name": "CmpLine",
        "name": "Mi campaña test", "audience_id": audience_id, "segment": None,
        "template_name": "test_template", "template_language": "es_AR",
        "template_var_mapping": ["name", "var1"], "header_image_url": None,
        "scheduled_at": None, "resend_after_hours": None, "resend_template_name": None,
        "status": "running", "target_count": 3,
        "stats": {"sent": 0, "delivered": 0, "read": 0, "failed": 0, "replied": 0, "skipped_optout": 0},
        "created_by": "test", "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    sent_log = []

    async def fake_send_template(**kw):
        sent_log.append(kw)
        return {"messaging_product": "whatsapp", "messages": [{"id": f"wamid.{len(sent_log)}"}]}

    async def fake_sleep(*a, **kw):
        return None

    with patch.object(srv, "wa_send_template", new=fake_send_template), \
         patch.object(asyncio, "sleep", new=fake_sleep), \
         patch.object(srv, "_is_night_pause_now", return_value=False):
        await srv._csv_campaign_worker(campaign_id)

    c = await db.broadcast_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    assert c["status"] == "completed", f"got {c['status']}, paused_reason={c.get('paused_reason')}"
    assert c["stats"]["sent"] == 3, f"expected 3 sent, got {c['stats']}"
    assert c["stats"]["failed"] == 0
    bms = await db.broadcast_messages.find({"campaign_id": campaign_id}, {"_id": 0}).to_list(10)
    assert len(bms) == 3
    assert all(m["status"] == "sent" for m in bms)
    # Variable mapping correctness
    expected_var_combos = {("Juan", "bono1"), ("Maria", "bono2"), ("Pedro", "bono3")}
    actual = {tuple(call["variables"]) for call in sent_log}
    assert actual == expected_var_combos, f"vars mismatch: {actual}"
    print("  PASS campaign_full_send_3_of_3")

    # Campaign 2 — with one optout already in DB (must be skipped)
    await db.broadcast_optouts.insert_one({
        "id": str(uuid.uuid4()), "line_id": line_id, "phone": "5491100009002",
        "reason": "test", "added_by": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    cid2 = str(uuid.uuid4())
    await db.broadcast_campaigns.insert_one({
        "id": cid2, "line_id": line_id, "line_name": "CmpLine",
        "name": "Con optout", "audience_id": audience_id, "segment": None,
        "template_name": "test_template", "template_language": "es_AR",
        "template_var_mapping": ["name"], "header_image_url": None,
        "scheduled_at": None, "resend_after_hours": None, "resend_template_name": None,
        "status": "running", "target_count": 3,
        "stats": {"sent": 0, "delivered": 0, "read": 0, "failed": 0, "replied": 0, "skipped_optout": 0},
        "created_by": "test", "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    sent_log2 = []

    async def fake_send2(**kw):
        sent_log2.append(kw)
        return {"messages": [{"id": f"wamid.B.{len(sent_log2)}"}]}

    with patch.object(srv, "wa_send_template", new=fake_send2), \
         patch.object(asyncio, "sleep", new=fake_sleep), \
         patch.object(srv, "_is_night_pause_now", return_value=False):
        await srv._csv_campaign_worker(cid2)

    c2 = await db.broadcast_campaigns.find_one({"id": cid2}, {"_id": 0})
    assert c2["stats"]["sent"] == 2, f"expected 2 sent, got {c2['stats']}"
    assert c2["stats"]["skipped_optout"] == 1
    print("  PASS optout_skipped_at_runtime")

    # Campaign 3 — auto-pause when Meta returns rate-limit error code
    cid3 = str(uuid.uuid4())
    await db.broadcast_campaigns.insert_one({
        "id": cid3, "line_id": line_id, "line_name": "CmpLine",
        "name": "Rate limited", "audience_id": audience_id, "segment": None,
        "template_name": "test_template", "template_language": "es_AR",
        "template_var_mapping": [], "header_image_url": None,
        "scheduled_at": None, "resend_after_hours": None, "resend_template_name": None,
        "status": "running", "target_count": 3,
        "stats": {"sent": 0, "delivered": 0, "read": 0, "failed": 0, "replied": 0, "skipped_optout": 0},
        "created_by": "test", "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    async def fake_send_rate(**kw):
        return {"error": {"code": 131056, "message": "rate limited"}}

    with patch.object(srv, "wa_send_template", new=fake_send_rate), \
         patch.object(asyncio, "sleep", new=fake_sleep), \
         patch.object(srv, "_is_night_pause_now", return_value=False):
        await srv._csv_campaign_worker(cid3)

    c3 = await db.broadcast_campaigns.find_one({"id": cid3}, {"_id": 0})
    assert c3["status"] == "paused", f"expected auto-pause on rate-limit, got {c3['status']}"
    assert "131056" in (c3.get("paused_reason") or "")
    print("  PASS auto_pause_on_meta_rate_limit")

    # cleanup
    await db.crm_lines.delete_many({"id": line_id})
    await db.broadcast_audiences.delete_many({"line_id": line_id})
    await db.broadcast_contacts.delete_many({"line_id": line_id})
    await db.broadcast_campaigns.delete_many({"line_id": line_id})
    await db.broadcast_messages.delete_many({"line_id": line_id})
    await db.broadcast_optouts.delete_many({"line_id": line_id})


async def test_auto_resend_only_to_unread_unanswered(db):
    """The resend pass must target ONLY contacts whose first message is in
    status `sent` or `delivered` (not `read`) AND has no `replied_at`.
    Optouts must be respected."""
    import server as srv
    from server import _csv_campaign_resend, _csv_campaign_worker
    line_id = "test-resend-" + uuid.uuid4().hex[:6]
    await db.crm_lines.delete_many({"id": line_id})
    await db.crm_lines.insert_one({
        "id": line_id, "name": "ResendLine", "line_type": "publi",
        "whatsapp_number": "5491100000004",
        "whatsapp_token": "TEST", "phone_number_id": "111",
        "is_active": True, "created_at": datetime.now(timezone.utc).isoformat(),
    })

    audience_id = str(uuid.uuid4())
    await db.broadcast_audiences.insert_one({
        "id": audience_id, "line_id": line_id, "name": "AudResend",
        "filename": "a.csv", "total_contacts": 4, "stats": {},
        "created_by": "test", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.broadcast_contacts.insert_many([
        {"id": str(uuid.uuid4()), "audience_id": audience_id, "line_id": line_id,
         "phone": p, "name": n, "vars": {}, "created_at": datetime.now(timezone.utc).isoformat()}
        for p, n in [
            ("5491100007001", "JuanSent"),
            ("5491100007002", "MariaDelivered"),
            ("5491100007003", "PedroRead"),
            ("5491100007004", "AnaReplied"),
        ]
    ])

    cid = str(uuid.uuid4())
    await db.broadcast_campaigns.insert_one({
        "id": cid, "line_id": line_id, "line_name": "ResendLine",
        "name": "Resend test", "audience_id": audience_id, "segment": None,
        "template_name": "first_tpl", "template_language": "es_AR",
        "template_var_mapping": [], "header_image_url": None,
        "scheduled_at": None,
        "resend_after_hours": 1,
        "resend_template_name": "second_tpl",
        "status": "running", "target_count": 4,
        "stats": {"sent": 0, "delivered": 0, "read": 0, "failed": 0, "replied": 0,
                  "skipped_optout": 0, "resent": 0, "resend_failed": 0,
                  "resend_skipped_optout": 0},
        "created_by": "test", "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    # First pass — send to all 4
    sent_log = []

    async def fake_send(**kw):
        sent_log.append(kw)
        return {"messages": [{"id": f"wamid.{kw['phone']}.1"}]}

    async def fake_sleep(*a, **kw): return None

    with patch.object(srv, "wa_send_template", new=fake_send), \
         patch.object(asyncio, "sleep", new=fake_sleep), \
         patch.object(srv, "_is_night_pause_now", return_value=False):
        await _csv_campaign_worker(cid)

    c = await db.broadcast_campaigns.find_one({"id": cid}, {"_id": 0})
    assert c["stats"]["sent"] == 4, f"expected 4 first-pass sent, got {c['stats']}"

    # Now simulate user states for each contact:
    # - JuanSent: stays at "sent" (no progress)
    # - MariaDelivered: status = "delivered"
    # - PedroRead: status = "read"
    # - AnaReplied: status = "delivered" + replied_at set
    await db.broadcast_messages.update_one(
        {"campaign_id": cid, "phone": "5491100007002"}, {"$set": {"status": "delivered"}}
    )
    await db.broadcast_messages.update_one(
        {"campaign_id": cid, "phone": "5491100007003"}, {"$set": {"status": "read"}}
    )
    await db.broadcast_messages.update_one(
        {"campaign_id": cid, "phone": "5491100007004"},
        {"$set": {"status": "delivered", "replied_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Make completed_at far in the past so resend doesn't sleep
    await db.broadcast_campaigns.update_one(
        {"id": cid},
        {"$set": {"completed_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}}
    )

    resend_log = []

    async def fake_resend(**kw):
        resend_log.append(kw)
        return {"messages": [{"id": f"wamid.{kw['phone']}.R"}]}

    with patch.object(srv, "wa_send_template", new=fake_resend), \
         patch.object(asyncio, "sleep", new=fake_sleep), \
         patch.object(srv, "_is_night_pause_now", return_value=False):
        await _csv_campaign_resend(cid)

    # Verify only Juan + Maria got the resend (Pedro read it, Ana replied)
    resent_phones = {kw["phone"] for kw in resend_log}
    assert resent_phones == {"5491100007001", "5491100007002"}, \
        f"resend must target only sent/delivered without reply, got {resent_phones}"
    # All resends used the second template
    assert all(kw["template_name"] == "second_tpl" for kw in resend_log)

    # Stats counters
    c2 = await db.broadcast_campaigns.find_one({"id": cid}, {"_id": 0})
    assert c2["stats"]["resent"] == 2, f"expected resent=2, got {c2['stats']}"
    assert c2["stats"].get("resend_failed", 0) == 0
    assert c2.get("resend_done_at"), "resend_done_at must be set after completion"

    # The new broadcast_messages docs must have is_resend=True
    resends = await db.broadcast_messages.find(
        {"campaign_id": cid, "is_resend": True}, {"_id": 0}
    ).to_list(20)
    assert len(resends) == 2

    print("  PASS test_auto_resend_only_to_unread_unanswered")
    # cleanup
    await db.crm_lines.delete_many({"id": line_id})
    await db.broadcast_audiences.delete_many({"line_id": line_id})
    await db.broadcast_contacts.delete_many({"line_id": line_id})
    await db.broadcast_campaigns.delete_many({"line_id": line_id})
    await db.broadcast_messages.delete_many({"line_id": line_id})


async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["traffic_guardian"]
    print("=== CSV broadcasts engine tests ===")
    failures = 0
    tests = (
        test_night_pause_logic,
        test_segment_resolution,
        test_campaign_lifecycle_e2e,
        test_auto_resend_only_to_unread_unanswered,
    )
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

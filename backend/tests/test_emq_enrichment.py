"""
Tests for EMQ enrichment features (iteration 6):
A) Browser fingerprint visitor_id added to external_id array
B) Cross-session signal recovery (fbp/fbc/IP/UA from past wa_clicks by phone or visitor_id)
C) Enriched custom_data on Purchase events (order_id, content_ids, etc.)
E) Persistent geo_cache in MongoDB

Run:  cd /app/backend && python tests/test_emq_enrichment.py
"""
import asyncio
import hashlib
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


TEST_PHONE = "5491199999000"
TEST_VID = "a" * 64


async def _cleanup(db):
    await db.wa_clicks.delete_many({"phone": TEST_PHONE})
    await db.crm_leads.delete_many({"phone": TEST_PHONE})
    await db.crm_lines.delete_many({"id": "test-line-emq"})
    await db.geo_cache.delete_many({"_id": "203.0.113.42"})


def _ok_post_factory(captured):
    async def fake_post(self, url, json=None, **kw):
        captured["url"] = url
        captured["json"] = json

        class R:
            status_code = 200

            def json(self):
                return {"events_received": 1, "fbtrace_id": "test"}

        return R()

    return fake_post


async def test_visitor_id_in_external_id(db):
    """A) visitor_id from wa_clicks must appear in user_data.external_id alongside phone hash."""
    from server import send_meta_conversion_event

    click_id = "click-emq-" + uuid.uuid4().hex[:8]
    await db.wa_clicks.insert_one({
        "id": str(uuid.uuid4()),
        "click_id": click_id,
        "phone": TEST_PHONE,
        "ip": "203.0.113.42",
        "user_agent": "Mozilla/5.0 Test",
        "fbp": "fb.1.1234.5678",
        "fbc": "fb.1.1234.testfbc",
        "visitor_id": TEST_VID,
        "landing_code": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    captured = {}
    with patch("httpx.AsyncClient.post", new=_ok_post_factory(captured)):
        await send_meta_conversion_event(
            event_name="Purchase",
            lead_data={"id": "lead-emq-1", "phone": TEST_PHONE, "click_id": click_id, "line_id": "test-line-emq"},
            custom_data={"value": 1500, "currency": "USD"},
            access_token="EAATEST",
            pixel_id="123456",
            event_id="evt-emq-1",
        )

    user_data = captured["json"]["data"][0]["user_data"]
    ext = user_data.get("external_id") or []
    assert isinstance(ext, list), f"external_id must be a list, got {ext}"
    assert len(ext) == 2, f"expected 2 external_ids, got {len(ext)}: {ext}"
    expected_phone_hash = hashlib.sha256(TEST_PHONE.encode()).hexdigest()
    assert expected_phone_hash in ext
    assert TEST_VID in ext
    print("  PASS test_visitor_id_in_external_id")


async def test_cross_session_signal_recovery_by_phone(db):
    """B) When current click_data lacks fbp/fbc/IP/UA, latest historical click by phone fills the gaps."""
    from server import send_meta_conversion_event

    await db.wa_clicks.insert_one({
        "id": str(uuid.uuid4()),
        "click_id": "old-click-xyz",
        "phone": TEST_PHONE,
        "ip": "198.51.100.7",
        "user_agent": "Mozilla/5.0 OldDevice",
        "fbp": "fb.1.111.222",
        "fbc": "fb.1.111.oldfbc",
        "visitor_id": "b" * 64,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    captured = {}
    with patch("httpx.AsyncClient.post", new=_ok_post_factory(captured)):
        await send_meta_conversion_event(
            event_name="Purchase",
            lead_data={"id": "lead-emq-2", "phone": TEST_PHONE, "line_id": "test-line-emq"},
            custom_data={"value": 500, "currency": "USD"},
            access_token="EAATEST",
            pixel_id="123456",
            event_id="evt-emq-2",
        )

    user_data = captured["json"]["data"][0]["user_data"]
    assert user_data.get("client_ip_address"), "IP must be recovered from history"
    assert user_data.get("client_user_agent"), "UA must be recovered from history"
    assert user_data.get("fbp") == "fb.1.111.222", f"fbp must be recovered: {user_data.get('fbp')}"
    assert user_data.get("fbc") == "fb.1.111.oldfbc", f"fbc must be recovered: {user_data.get('fbc')}"
    ext = user_data.get("external_id") or []
    assert ("b" * 64) in ext, f"recovered visitor_id must be in external_id: {ext}"
    print("  PASS test_cross_session_signal_recovery_by_phone")


async def test_purchase_custom_data_enriched(db):
    """C) Purchase events must include order_id, content_ids, content_name, content_category, num_items, delivery_category."""
    from server import send_meta_conversion_event

    await db.crm_lines.insert_one({
        "id": "test-line-emq",
        "name": "GANAMOSvip",
        "whatsapp_number": "5491100000000",
    })

    captured = {}
    with patch("httpx.AsyncClient.post", new=_ok_post_factory(captured)):
        await send_meta_conversion_event(
            event_name="Purchase",
            lead_data={"id": "lead-emq-3", "phone": TEST_PHONE, "line_id": "test-line-emq"},
            custom_data={"value": 2500, "currency": "USD"},
            access_token="EAATEST",
            pixel_id="123456",
            event_id="evt-emq-3",
        )

    cd = captured["json"]["data"][0]["custom_data"]
    assert cd.get("value") == 2500.0
    assert cd.get("currency") == "USD"
    assert cd.get("content_type") == "product"
    assert cd.get("content_category") == "credits"
    assert cd.get("num_items") == 1
    assert cd.get("delivery_category") == "home_delivery"
    assert cd.get("content_ids") == ["test-line-emq"]
    assert cd.get("content_name") == "GANAMOSvip"
    assert "order_id" in cd
    assert cd["order_id"].startswith("lead-emq-3-"), f"order_id={cd.get('order_id')}"
    print("  PASS test_purchase_custom_data_enriched")


async def test_geo_cache_persisted_to_mongo(db):
    """E) resolve_geo_from_ip persists to db.geo_cache so subsequent calls don't hit the network."""
    from server import resolve_geo_from_ip, _geo_cache

    test_ip = "203.0.113.42"
    _geo_cache.pop(test_ip, None)
    await db.geo_cache.delete_one({"_id": test_ip})

    fake_response = {
        "status": "success",
        "country": "United States",
        "countryCode": "US",
        "regionName": "Virginia",
        "region": "VA",
        "city": "Ashburn",
        "zip": "20149",
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return fake_response

    network_calls = {"n": 0}

    async def fake_get(self, url, **kw):
        network_calls["n"] += 1
        return FakeResp()

    with patch("httpx.AsyncClient.get", new=fake_get):
        result1 = await resolve_geo_from_ip(test_ip)

    assert result1.get("city") == "Ashburn", f"first call result: {result1}"
    assert network_calls["n"] == 1

    cached = await db.geo_cache.find_one({"_id": test_ip})
    assert cached is not None and cached["data"]["city"] == "Ashburn", f"cached={cached}"

    # Clear in-memory only — Mongo should serve the request without a 2nd network call
    _geo_cache.pop(test_ip, None)

    with patch("httpx.AsyncClient.get", new=fake_get):
        result2 = await resolve_geo_from_ip(test_ip)

    assert result2.get("city") == "Ashburn"
    assert network_calls["n"] == 1, f"Mongo cache should prevent 2nd network call (got {network_calls['n']})"
    print("  PASS test_geo_cache_persisted_to_mongo")


async def test_no_synthetic_fbc_from_ctwa_clid(db):
    """REGRESSION: ctwa_clid must NEVER be turned into a synthetic fbc.
    Meta detects this as 'modified fbclid' and shows a warning in Events Manager.
    If only ctwa_clid is available (no real fbclid), the event must be sent
    WITHOUT an fbc field rather than with a fake one."""
    from server import send_meta_conversion_event

    captured = {}
    with patch("httpx.AsyncClient.post", new=_ok_post_factory(captured)):
        await send_meta_conversion_event(
            event_name="Purchase",
            lead_data={
                "id": "lead-no-fake-fbc",
                "phone": TEST_PHONE,
                # ctwa_clid present but NO real fbc/fbp/click_id
                "ctwa_clid": "ARxxYYzzAA1234567890",
                "line_id": "test-line-emq",
            },
            custom_data={"value": 100, "currency": "USD"},
            access_token="EAATEST",
            pixel_id="123456",
            event_id="evt-no-fake-fbc",
        )

    user_data = captured["json"]["data"][0]["user_data"]
    fbc_sent = user_data.get("fbc")
    assert fbc_sent is None, (
        f"fbc must NOT be present when only ctwa_clid is available. "
        f"Got fbc={fbc_sent!r} — Meta would flag this as 'modified fbclid'."
    )
    print("  PASS test_no_synthetic_fbc_from_ctwa_clid")


async def test_malformed_fbc_dropped(db):
    """REGRESSION: if a stored fbc is malformed (e.g. raw fbclid without
    the fb.<n>.<ts>. prefix), drop it before sending to Meta."""
    from server import send_meta_conversion_event

    captured = {}
    with patch("httpx.AsyncClient.post", new=_ok_post_factory(captured)):
        await send_meta_conversion_event(
            event_name="Purchase",
            lead_data={
                "id": "lead-bad-fbc",
                "phone": TEST_PHONE,
                "fbc": "IwAR_just_the_raw_fbclid_no_prefix",  # malformed
                "line_id": "test-line-emq",
            },
            custom_data={"value": 100, "currency": "USD"},
            access_token="EAATEST",
            pixel_id="123456",
            event_id="evt-bad-fbc",
        )

    user_data = captured["json"]["data"][0]["user_data"]
    assert user_data.get("fbc") is None, f"malformed fbc must be dropped, got: {user_data.get('fbc')!r}"
    print("  PASS test_malformed_fbc_dropped")


async def test_valid_fbc_passes_through(db):
    """A correctly-formatted fbc must pass through unchanged."""
    from server import send_meta_conversion_event

    real_fbc = "fb.1.1709136167115.IwAR2F4-dbP0l7Mn1IawQQGCINEz7PYXQvwjNwB_qa2ofrHyiLjcbCRxTDMgk"
    captured = {}
    with patch("httpx.AsyncClient.post", new=_ok_post_factory(captured)):
        await send_meta_conversion_event(
            event_name="Purchase",
            lead_data={
                "id": "lead-good-fbc",
                "phone": TEST_PHONE,
                "fbc": real_fbc,
                "line_id": "test-line-emq",
            },
            custom_data={"value": 100, "currency": "USD"},
            access_token="EAATEST",
            pixel_id="123456",
            event_id="evt-good-fbc",
        )

    user_data = captured["json"]["data"][0]["user_data"]
    assert user_data.get("fbc") == real_fbc, f"valid fbc must pass through unchanged, got: {user_data.get('fbc')!r}"
    print("  PASS test_valid_fbc_passes_through")


async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["traffic_guardian"]
    print("=== EMQ enrichment tests ===")
    failures = 0
    tests = (
        test_visitor_id_in_external_id,
        test_cross_session_signal_recovery_by_phone,
        test_purchase_custom_data_enriched,
        test_geo_cache_persisted_to_mongo,
        test_no_synthetic_fbc_from_ctwa_clid,
        test_malformed_fbc_dropped,
        test_valid_fbc_passes_through,
    )
    for tc in tests:
        await _cleanup(db)
        try:
            await tc(db)
        except Exception as e:
            failures += 1
            print(f"  FAIL {tc.__name__}: {e}")
    await _cleanup(db)
    client.close()
    print(f"=== {len(tests) - failures}/{len(tests)} passed ===")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

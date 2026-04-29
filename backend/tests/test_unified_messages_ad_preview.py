"""
Test suite for:
1. Unified chat history per phone (GET /api/crm/leads/{lead_id}/messages)
2. Ad preview with Meta Ads Library link (GET /api/crm/leads/{lead_id}/ad-preview)

Tests the features requested in iteration 5:
- Unified messages aggregation by phone number
- Ad preview with source_url and ads_library_url
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = "https://7d3700be-cf81-4e00-8415-edcf6298aedc.preview.emergentagent.com"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "traffic_guardian"

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@maxi.com"
ADMIN_PASSWORD = "admin123"


def get_mongo_client():
    """Get MongoDB client"""
    return AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)


class TestUnifiedMessagesWithSeededData:
    """Tests for unified chat history using seeded data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("access_token")
        assert token, "No access token returned"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield

    def test_unified_messages_returns_all_messages_for_shared_phone(self):
        """
        Test: GET /api/crm/leads/{lead_id}/messages returns unified history by default.
        When 2+ leads share the same phone, the endpoint must return ALL their messages.
        Uses seeded data with TEST_LEAD_ prefix.
        """
        # Find a seeded lead with shared phone
        async def get_test_lead():
            client = get_mongo_client()
            db = client[DB_NAME]
            lead = await db.crm_leads.find_one({"id": {"$regex": "^TEST_LEAD_[a-f0-9]+$"}, "phone": "5491100000999"})
            return lead
        
        lead = asyncio.run(get_test_lead())
        if not lead:
            pytest.skip("No seeded test lead found - run seed_test_data.py first")
        
        lead_id = lead["id"]
        
        # GET messages for lead with unified=True (default)
        response = self.session.get(f"{BASE_URL}/api/crm/leads/{lead_id}/messages")
        assert response.status_code == 200, f"Failed to get messages: {response.text}"
        
        data = response.json()
        messages = data.get("messages", [])
        
        # Verify unified flag is True
        assert data.get("unified") == True, f"Expected unified=True, got {data.get('unified')}"
        
        # Verify we get messages from BOTH leads (unified history)
        # Should have at least 3 messages (from both leads)
        assert len(messages) >= 3, f"Expected at least 3 messages (unified), got {len(messages)}"
        
        # Verify messages are sorted by created_at ASC
        if len(messages) >= 2:
            for i in range(len(messages) - 1):
                assert messages[i].get("created_at", "") <= messages[i+1].get("created_at", ""), \
                    "Messages should be sorted by created_at ASC"
        
        # Verify we have messages from different lead_ids (proving unification)
        lead_ids_in_messages = set(m.get("lead_id") for m in messages)
        assert len(lead_ids_in_messages) >= 2, \
            f"Expected messages from at least 2 leads (unified), got {len(lead_ids_in_messages)}"
        
        print(f"✓ Unified messages test passed: {len(messages)} messages from {len(lead_ids_in_messages)} leads, unified={data.get('unified')}")

    def test_unified_false_restricts_to_single_lead(self):
        """
        Test: GET /api/crm/leads/{lead_id}/messages?unified=false restricts to single lead.
        """
        # Find a seeded lead with shared phone
        async def get_test_lead():
            client = get_mongo_client()
            db = client[DB_NAME]
            lead = await db.crm_leads.find_one({"id": {"$regex": "^TEST_LEAD_[a-f0-9]+$"}, "phone": "5491100000999"})
            return lead
        
        lead = asyncio.run(get_test_lead())
        if not lead:
            pytest.skip("No seeded test lead found - run seed_test_data.py first")
        
        lead_id = lead["id"]
        
        # GET messages for lead with unified=false
        response = self.session.get(f"{BASE_URL}/api/crm/leads/{lead_id}/messages?unified=false")
        assert response.status_code == 200, f"Failed to get messages: {response.text}"
        
        data = response.json()
        messages = data.get("messages", [])
        
        # Verify unified flag is False
        assert data.get("unified") == False, f"Expected unified=False, got {data.get('unified')}"
        
        # Verify we only get messages from this specific lead
        for msg in messages:
            assert msg.get("lead_id") == lead_id, \
                f"Expected only lead {lead_id} messages, got message from lead_id={msg.get('lead_id')}"
        
        print(f"✓ Non-unified messages test passed: {len(messages)} messages, unified={data.get('unified')}")


class TestAdPreviewWithSeededData:
    """Tests for ad preview using seeded data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("access_token")
        assert token, "No access token returned"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield

    def test_ad_preview_source_id_only_returns_ads_library_url(self):
        """
        Test: GET /api/crm/leads/{lead_id}/ad-preview for a lead with referral.source_id 
        but NO referral.source_url must return:
        - source_url == ads_library_url == 'https://www.facebook.com/ads/library/?id={source_id}'
        - ads_library_url field present
        """
        # Find the seeded lead with source_id only
        async def get_test_lead():
            client = get_mongo_client()
            db = client[DB_NAME]
            lead = await db.crm_leads.find_one({
                "id": {"$regex": "^TEST_LEAD_AD_"},
                "referral.source_id": "123456789012345"
            })
            return lead
        
        lead = asyncio.run(get_test_lead())
        if not lead:
            pytest.skip("No seeded ad-preview test lead found - run seed_test_data.py first")
        
        lead_id = lead["id"]
        expected_source_id = "123456789012345"
        expected_ads_library_url = f"https://www.facebook.com/ads/library/?id={expected_source_id}"
        
        # GET ad-preview
        response = self.session.get(f"{BASE_URL}/api/crm/leads/{lead_id}/ad-preview")
        assert response.status_code == 200, f"Failed to get ad-preview: {response.text}"
        
        data = response.json()
        
        # Verify has_preview is True
        assert data.get("has_preview") == True, f"Expected has_preview=True, got {data.get('has_preview')}"
        
        # Verify source is meta_ctwa_ad
        assert data.get("source") == "meta_ctwa_ad", f"Expected source=meta_ctwa_ad, got {data.get('source')}"
        
        # Verify ads_library_url is constructed correctly
        assert data.get("ads_library_url") == expected_ads_library_url, \
            f"Expected ads_library_url={expected_ads_library_url}, got {data.get('ads_library_url')}"
        
        # Verify source_url falls back to ads_library_url when no source_url in referral
        assert data.get("source_url") == expected_ads_library_url, \
            f"Expected source_url={expected_ads_library_url}, got {data.get('source_url')}"
        
        # Verify source_id is present
        assert data.get("source_id") == expected_source_id, \
            f"Expected source_id={expected_source_id}, got {data.get('source_id')}"
        
        print(f"✓ Ad preview (source_id only) test passed: ads_library_url={data.get('ads_library_url')}")

    def test_ad_preview_both_urls_returns_separate_links(self):
        """
        Test: GET /api/crm/leads/{lead_id}/ad-preview for a lead with BOTH 
        referral.source_url and referral.source_id must return:
        - source_url == referral.source_url (the real ad post URL)
        - ads_library_url must STILL be present (constructed from source_id)
        """
        # Find the seeded lead with both URLs
        async def get_test_lead():
            client = get_mongo_client()
            db = client[DB_NAME]
            lead = await db.crm_leads.find_one({
                "id": {"$regex": "^TEST_LEAD_AD_"},
                "referral.source_id": "987654321098765"
            })
            return lead
        
        lead = asyncio.run(get_test_lead())
        if not lead:
            pytest.skip("No seeded ad-preview test lead found - run seed_test_data.py first")
        
        lead_id = lead["id"]
        expected_source_id = "987654321098765"
        expected_source_url = "https://www.facebook.com/some-page/posts/12345"
        expected_ads_library_url = f"https://www.facebook.com/ads/library/?id={expected_source_id}"
        
        # GET ad-preview
        response = self.session.get(f"{BASE_URL}/api/crm/leads/{lead_id}/ad-preview")
        assert response.status_code == 200, f"Failed to get ad-preview: {response.text}"
        
        data = response.json()
        
        # Verify has_preview is True
        assert data.get("has_preview") == True, f"Expected has_preview=True"
        
        # Verify source_url is the referral.source_url (NOT the ads_library_url)
        assert data.get("source_url") == expected_source_url, \
            f"Expected source_url={expected_source_url}, got {data.get('source_url')}"
        
        # Verify ads_library_url is STILL present and constructed from source_id
        assert data.get("ads_library_url") == expected_ads_library_url, \
            f"Expected ads_library_url={expected_ads_library_url}, got {data.get('ads_library_url')}"
        
        # Verify source_id is present
        assert data.get("source_id") == expected_source_id, \
            f"Expected source_id={expected_source_id}, got {data.get('source_id')}"
        
        print(f"✓ Ad preview (both URLs) test passed: source_url={data.get('source_url')}, ads_library_url={data.get('ads_library_url')}")

    def test_ad_preview_no_referral_returns_has_preview_false(self):
        """
        Test: ad-preview should return has_preview=false for leads with no referral / 
        landing_code / ad_source / utm_content / ctwa_clid (regression test).
        """
        # Find the seeded lead with no referral
        async def get_test_lead():
            client = get_mongo_client()
            db = client[DB_NAME]
            lead = await db.crm_leads.find_one({
                "id": {"$regex": "^TEST_LEAD_AD_"},
                "name": "TEST_Lead_NoReferral"
            })
            return lead
        
        lead = asyncio.run(get_test_lead())
        if not lead:
            pytest.skip("No seeded no-referral test lead found - run seed_test_data.py first")
        
        lead_id = lead["id"]
        
        # GET ad-preview
        response = self.session.get(f"{BASE_URL}/api/crm/leads/{lead_id}/ad-preview")
        assert response.status_code == 200, f"Failed to get ad-preview: {response.text}"
        
        data = response.json()
        
        # Verify has_preview is False
        assert data.get("has_preview") == False, \
            f"Expected has_preview=False for lead with no referral, got {data.get('has_preview')}"
        
        print(f"✓ Ad preview (no referral) test passed: has_preview={data.get('has_preview')}")


class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Health endpoint test passed")
    
    def test_login_with_valid_credentials(self):
        """Test login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print("✓ Login test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

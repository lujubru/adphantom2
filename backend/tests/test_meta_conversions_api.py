"""
Test Suite for Meta Conversions API Integration in AdPhantom CRM
Tests: Login, Lines, Leads, Classification with Purchase events, Manual conversions, WA Landings
"""
import pytest
import requests
import os
import uuid
import time

# Use the public preview URL for testing
BASE_URL = "https://usd-ars-issue.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "admin@adphantom.com"
ADMIN_PASSWORD = "admin123"


class TestAuthLogin:
    """Test authentication endpoints"""
    
    def test_login_success(self):
        """Test 1: POST /api/auth/login - Login with admin credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("email") == ADMIN_EMAIL
        print(f"✓ Login successful for {ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@email.com", "password": "wrongpass"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for all tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestCRMLines:
    """Test CRM Lines CRUD operations"""
    
    def test_create_line_with_meta_config(self, auth_headers):
        """Test 2: POST /api/crm/lines - Create a line with meta_pixel_id and meta_access_token"""
        unique_id = str(uuid.uuid4())[:8]
        line_data = {
            "name": f"TEST_Line_{unique_id}",
            "line_type": "publi",
            "whatsapp_number": f"+5491155{unique_id[:6]}",
            "meta_access_token": "test_token_123456",
            "meta_pixel_id": "test_pixel_123456",
            "description": "Test line for Meta Conversions API testing"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/crm/lines",
            json=line_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create line failed: {response.text}"
        data = response.json()
        assert "id" in data, "No id in response"
        assert data["name"] == line_data["name"]
        assert data["meta_access_token"] == line_data["meta_access_token"]
        assert data["meta_pixel_id"] == line_data["meta_pixel_id"]
        print(f"✓ Created line with Meta config: {data['id']}")
        return data
    
    def test_get_lines(self, auth_headers):
        """Test GET /api/crm/lines - Get all lines"""
        response = requests.get(
            f"{BASE_URL}/api/crm/lines",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get lines failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Retrieved {len(data)} lines")
        return data


@pytest.fixture(scope="module")
def test_line(auth_headers):
    """Create a test line for lead tests"""
    unique_id = str(uuid.uuid4())[:8]
    line_data = {
        "name": f"TEST_MetaLine_{unique_id}",
        "line_type": "publi",
        "whatsapp_number": f"+5491166{unique_id[:6]}",
        "meta_access_token": "test_token_123456",
        "meta_pixel_id": "test_pixel_123456",
        "description": "Test line for Meta Conversions API"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/crm/lines",
        json=line_data,
        headers=auth_headers
    )
    if response.status_code != 200:
        pytest.skip(f"Failed to create test line: {response.text}")
    return response.json()


class TestCRMLeads:
    """Test CRM Leads CRUD operations"""
    
    def test_create_lead_assigned_to_line(self, auth_headers, test_line):
        """Test 3: POST /api/crm/leads - Create a lead assigned to a line"""
        unique_id = str(uuid.uuid4())[:8]
        lead_data = {
            "name": f"TEST_Lead_{unique_id}",
            "phone": f"+5491177{unique_id[:6]}",
            "email": f"test_{unique_id}@example.com",
            "source": "test",
            "line_id": test_line["id"],
            "notes": "Test lead for Meta Conversions API testing"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/crm/leads",
            json=lead_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create lead failed: {response.text}"
        data = response.json()
        assert "id" in data, "No id in response"
        assert data["name"] == lead_data["name"]
        assert data["line_id"] == test_line["id"]
        print(f"✓ Created lead assigned to line: {data['id']}")
        return data
    
    def test_get_leads(self, auth_headers):
        """Test GET /api/crm/leads - Get all leads"""
        response = requests.get(
            f"{BASE_URL}/api/crm/leads",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get leads failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Retrieved {len(data)} leads")
        return data


@pytest.fixture(scope="module")
def test_lead(auth_headers, test_line):
    """Create a test lead for classification tests"""
    unique_id = str(uuid.uuid4())[:8]
    lead_data = {
        "name": f"TEST_ClassifyLead_{unique_id}",
        "phone": f"+5491188{unique_id[:6]}",
        "email": f"classify_{unique_id}@example.com",
        "source": "test",
        "line_id": test_line["id"],
        "notes": "Test lead for classification testing"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/crm/leads",
        json=lead_data,
        headers=auth_headers
    )
    if response.status_code != 200:
        pytest.skip(f"Failed to create test lead: {response.text}")
    return response.json()


class TestLeadClassification:
    """Test Lead Classification with Meta Conversions API"""
    
    def test_classify_lead_as_valido_with_conversion_value(self, auth_headers, test_lead):
        """
        Test 4: POST /api/crm/leads/{id}/classify - Classify lead as 'valido' with conversion_value
        Verify response includes: charge_amount=2.4, meta_events_sent with value=2.4, event_id not null
        """
        lead_id = test_lead["id"]
        classify_data = {
            "status": "valido",
            "send_to_meta": True,
            "conversion_value": 2.4,
            "currency": "USD"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/crm/leads/{lead_id}/classify",
            json=classify_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Classify lead failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "lead" in data, "No 'lead' in response"
        assert "event_sent" in data, "No 'event_sent' in response"
        assert "meta_result" in data, "No 'meta_result' in response"
        
        lead = data["lead"]
        
        # Verify charge_amount is set
        assert lead.get("charge_amount") == 2.4, f"Expected charge_amount=2.4, got {lead.get('charge_amount')}"
        
        # Verify status is valido
        assert lead.get("status") == "valido", f"Expected status='valido', got {lead.get('status')}"
        
        # Verify meta_events_sent contains the Purchase event
        meta_events = lead.get("meta_events_sent", [])
        assert len(meta_events) > 0, "No meta_events_sent recorded"
        
        # Find the Purchase event
        purchase_event = None
        for event in meta_events:
            if event.get("event") == "Purchase":
                purchase_event = event
                break
        
        assert purchase_event is not None, "No Purchase event in meta_events_sent"
        assert purchase_event.get("value") == 2.4, f"Expected value=2.4, got {purchase_event.get('value')}"
        assert purchase_event.get("currency") == "USD", f"Expected currency=USD, got {purchase_event.get('currency')}"
        assert purchase_event.get("event_id") is not None, "event_id should not be null"
        
        # Verify event_sent is Purchase
        assert data.get("event_sent") == "Purchase", f"Expected event_sent='Purchase', got {data.get('event_sent')}"
        
        # Verify meta_result has event_id (even if API call failed due to fake token)
        meta_result = data.get("meta_result", {})
        assert meta_result.get("event_id") is not None, "meta_result should have event_id"
        
        print(f"✓ Lead classified as 'valido' with conversion_value=2.4")
        print(f"  - charge_amount: {lead.get('charge_amount')}")
        print(f"  - event_id: {purchase_event.get('event_id')}")
        print(f"  - meta_result success: {meta_result.get('success')} (expected False due to fake token)")
        
        return data


@pytest.fixture(scope="module")
def valido_lead(auth_headers, test_line):
    """Create and classify a lead as 'valido' for manual conversion tests"""
    unique_id = str(uuid.uuid4())[:8]
    lead_data = {
        "name": f"TEST_ValidoLead_{unique_id}",
        "phone": f"+5491199{unique_id[:6]}",
        "email": f"valido_{unique_id}@example.com",
        "source": "test",
        "line_id": test_line["id"],
        "notes": "Test lead for manual conversion testing"
    }
    
    # Create lead
    response = requests.post(
        f"{BASE_URL}/api/crm/leads",
        json=lead_data,
        headers=auth_headers
    )
    if response.status_code != 200:
        pytest.skip(f"Failed to create lead: {response.text}")
    lead = response.json()
    
    # Classify as valido
    classify_data = {
        "status": "valido",
        "send_to_meta": True,
        "conversion_value": 1.0,
        "currency": "USD"
    }
    response = requests.post(
        f"{BASE_URL}/api/crm/leads/{lead['id']}/classify",
        json=classify_data,
        headers=auth_headers
    )
    if response.status_code != 200:
        pytest.skip(f"Failed to classify lead: {response.text}")
    
    return response.json()["lead"]


class TestManualConversion:
    """Test Manual Conversion to Meta"""
    
    def test_send_manual_conversion_for_valido_lead(self, auth_headers, valido_lead):
        """
        Test 5: POST /api/crm/leads/{id}/send-conversion?value=15.50&currency=USD
        Manual conversion for a 'valido' lead. Verify response includes event_id
        """
        lead_id = valido_lead["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/crm/leads/{lead_id}/send-conversion",
            params={"value": 15.50, "currency": "USD"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send conversion failed: {response.text}"
        data = response.json()
        
        # Verify event_id is present
        assert "event_id" in data, "No event_id in response"
        assert data["event_id"] is not None, "event_id should not be null"
        
        # The success might be False due to fake token, but event_id should be present
        print(f"✓ Manual conversion sent for valido lead")
        print(f"  - event_id: {data.get('event_id')}")
        print(f"  - success: {data.get('success')} (expected False due to fake token)")
        
        return data
    
    def test_send_conversion_fails_for_non_valido_lead(self, auth_headers, test_line):
        """
        Test 6: POST /api/crm/leads/{id}/send-conversion - Should fail for non-valido leads
        Verify 400 status
        """
        # Create a new lead (status will be 'nuevo' by default)
        unique_id = str(uuid.uuid4())[:8]
        lead_data = {
            "name": f"TEST_NuevoLead_{unique_id}",
            "phone": f"+5491100{unique_id[:6]}",
            "source": "test",
            "line_id": test_line["id"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/crm/leads",
            json=lead_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create lead failed: {response.text}"
        lead = response.json()
        
        # Try to send conversion for non-valido lead
        response = requests.post(
            f"{BASE_URL}/api/crm/leads/{lead['id']}/send-conversion",
            params={"value": 10.0, "currency": "USD"},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "valido" in data.get("detail", "").lower(), f"Error should mention 'valido': {data}"
        
        print(f"✓ Conversion correctly rejected for non-valido lead (status 400)")
        
        return data


class TestWALandings:
    """Test WA Landings with Meta Pixel Events"""
    
    def test_create_landing_with_pixel_config(self, auth_headers):
        """
        Test 7: POST /api/wa-landings - Create landing with pixel_id, meta_access_token, pixel_events
        """
        unique_id = str(uuid.uuid4())[:8]
        landing_data = {
            "name": f"TEST_Landing_{unique_id}",
            "wa_numbers": [f"+5491122{unique_id[:6]}"],
            "pixel_id": "test_pixel_123456",
            "meta_access_token": "test_token_123456",
            "pixel_events": ["PageView", "Lead", "Contact"],
            "headline": "Test Landing Page",
            "description": "Test landing for Meta events"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/wa-landings",
            json=landing_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create landing failed: {response.text}"
        data = response.json()
        
        assert "code" in data, "No code in response"
        assert data.get("pixel_id") == landing_data["pixel_id"]
        assert data.get("meta_access_token") == landing_data["meta_access_token"]
        assert data.get("pixel_events") == landing_data["pixel_events"]
        
        print(f"✓ Created landing with pixel config: {data['code']}")
        return data


@pytest.fixture(scope="module")
def test_landing(auth_headers):
    """Create a test landing for track-wa tests"""
    unique_id = str(uuid.uuid4())[:8]
    landing_data = {
        "name": f"TEST_TrackLanding_{unique_id}",
        "wa_numbers": [f"+5491133{unique_id[:6]}"],
        "pixel_id": "test_pixel_123456",
        "meta_access_token": "test_token_123456",
        "pixel_events": ["PageView", "Lead", "Contact"],
        "headline": "Test Landing for Track WA",
        "description": "Test landing for track-wa testing"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/wa-landings",
        json=landing_data,
        headers=auth_headers
    )
    if response.status_code != 200:
        pytest.skip(f"Failed to create test landing: {response.text}")
    return response.json()


class TestWALandingTrackWA:
    """Test WA Landing Track WA with fbp/fbc"""
    
    def test_track_wa_with_fbp_fbc(self, auth_headers, test_landing):
        """
        Test 8: Insert wa_clicks record with fbp and fbc, then POST /api/wa-landings/track-wa
        Check backend logs for Lead and Contact events with fbp=YES, fbc=YES
        """
        landing_code = test_landing["code"]
        click_id = f"test_click_{str(uuid.uuid4())[:8]}"
        
        # First, track a click to create the wa_clicks record
        # This simulates a user landing on the page
        track_data = {
            "landing_code": landing_code,
            "click_id": click_id,
            "fbp": "fb.1.1234567890.1234567890",
            "fbc": "fb.1.1234567890.AbCdEfGhIjKlMnOpQrStUvWxYz",
            "referrer": "https://facebook.com/ads",
            "utm_content": "test_ad_123",
            "utm_campaign": "test_campaign"
        }
        
        # Track the initial click
        response = requests.post(
            f"{BASE_URL}/api/wa-landings/track",
            json=track_data
        )
        assert response.status_code == 200, f"Track click failed: {response.text}"
        
        # Now track the WhatsApp button click
        track_wa_data = {
            "landing_code": landing_code,
            "click_id": click_id
        }
        
        response = requests.post(
            f"{BASE_URL}/api/wa-landings/track-wa",
            json=track_wa_data
        )
        assert response.status_code == 200, f"Track WA failed: {response.text}"
        data = response.json()
        
        assert data.get("status") == "ok", f"Expected status='ok', got {data}"
        
        print(f"✓ Track WA completed for landing {landing_code}")
        print(f"  - click_id: {click_id}")
        print(f"  - fbp: {track_data['fbp'][:20]}...")
        print(f"  - fbc: {track_data['fbc'][:20]}...")
        print("  - Check backend logs for 'Meta CAPI >>' with fbp=YES fbc=YES")
        
        return data


class TestHealthAndMisc:
    """Test health and miscellaneous endpoints"""
    
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ Health endpoint OK")
    
    def test_meta_integration_status(self, auth_headers):
        """Test /api/crm/meta/status endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/crm/meta/status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Meta status failed: {response.text}"
        data = response.json()
        assert "lines" in data
        assert "total_configured" in data
        assert "total_lines" in data
        print(f"✓ Meta integration status: {data['total_configured']}/{data['total_lines']} lines configured")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_data(self, auth_headers):
        """Clean up TEST_ prefixed data"""
        # Get all leads
        response = requests.get(f"{BASE_URL}/api/crm/leads", headers=auth_headers)
        if response.status_code == 200:
            leads = response.json()
            for lead in leads:
                if lead.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/crm/leads/{lead['id']}", headers=auth_headers)
        
        # Get all lines
        response = requests.get(f"{BASE_URL}/api/crm/lines", headers=auth_headers)
        if response.status_code == 200:
            lines = response.json()
            for line in lines:
                if line.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/crm/lines/{line['id']}", headers=auth_headers)
        
        # Get all landings
        response = requests.get(f"{BASE_URL}/api/wa-landings", headers=auth_headers)
        if response.status_code == 200:
            landings = response.json()
            for landing in landings:
                if landing.get("name", "").startswith("TEST_"):
                    requests.delete(f"{BASE_URL}/api/wa-landings/{landing['code']}", headers=auth_headers)
        
        print("✓ Test data cleanup completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

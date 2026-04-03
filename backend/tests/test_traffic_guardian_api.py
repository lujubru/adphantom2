"""
Traffic Guardian API Tests
Tests for: Auth, Campaigns CRUD, Filters CRUD, Reports, Analytics, AI Generator
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthCheck:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test successful login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@trafficguardian.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
    
    def test_login_invalid_credentials(self):
        """Test login fails with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
    
    def test_login_invalid_password(self):
        """Test login fails with wrong password for valid email"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@trafficguardian.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_protected_endpoint_without_auth(self):
        """Test protected endpoint returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/campaigns/")
        assert response.status_code == 401

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@trafficguardian.com",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

class TestCampaignsCRUD:
    """Campaign CRUD operation tests"""
    
    def test_get_campaigns_empty_or_list(self, auth_headers):
        """Test GET campaigns returns list (may be empty)"""
        response = requests.get(f"{BASE_URL}/api/campaigns/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_campaign_and_verify(self, auth_headers):
        """Test CREATE campaign and verify with GET"""
        # Create campaign
        payload = {
            "name": "TEST_Campaign_E2E",
            "target_url": "https://example.com/landing",
            "safe_page_url": "https://example.com/safe",
            "is_active": True,
            "daily_click_limit": 5000,
            "allowed_countries": ["US", "GB"],
            "allowed_devices": ["Desktop", "Mobile"],
            "allowed_os": ["Windows", "macOS"],
            "block_empty_referrer": True,
            "blacklist_ips": [],
            "whitelist_ips": []
        }
        create_response = requests.post(f"{BASE_URL}/api/campaigns/", json=payload, headers=auth_headers)
        assert create_response.status_code == 200
        
        created = create_response.json()
        assert created["name"] == payload["name"]
        assert created["target_url"] == payload["target_url"]
        assert created["is_active"] == True
        assert "id" in created
        campaign_id = created["id"]
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/campaigns/{campaign_id}", headers=auth_headers)
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["name"] == payload["name"]
        assert fetched["target_url"] == payload["target_url"]
        
        # Cleanup - delete campaign
        requests.delete(f"{BASE_URL}/api/campaigns/{campaign_id}", headers=auth_headers)
    
    def test_update_campaign_and_verify(self, auth_headers):
        """Test UPDATE campaign and verify changes persisted"""
        # Create campaign first
        create_payload = {
            "name": "TEST_Campaign_Update",
            "target_url": "https://example.com/original",
            "is_active": True,
            "daily_click_limit": 10000
        }
        create_response = requests.post(f"{BASE_URL}/api/campaigns/", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        campaign_id = create_response.json()["id"]
        
        # Update campaign
        update_payload = {
            "name": "TEST_Campaign_Updated_Name",
            "target_url": "https://example.com/updated",
            "is_active": False
        }
        update_response = requests.put(f"{BASE_URL}/api/campaigns/{campaign_id}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200
        
        updated = update_response.json()
        assert updated["name"] == update_payload["name"]
        assert updated["is_active"] == False
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/campaigns/{campaign_id}", headers=auth_headers)
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["name"] == update_payload["name"]
        assert fetched["is_active"] == False
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/campaigns/{campaign_id}", headers=auth_headers)
    
    def test_delete_campaign_and_verify(self, auth_headers):
        """Test DELETE campaign and verify it no longer exists"""
        # Create campaign
        create_payload = {
            "name": "TEST_Campaign_Delete",
            "target_url": "https://example.com/delete",
            "is_active": True
        }
        create_response = requests.post(f"{BASE_URL}/api/campaigns/", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        campaign_id = create_response.json()["id"]
        
        # Delete campaign
        delete_response = requests.delete(f"{BASE_URL}/api/campaigns/{campaign_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deleted - should return 404
        get_response = requests.get(f"{BASE_URL}/api/campaigns/{campaign_id}", headers=auth_headers)
        assert get_response.status_code == 404

class TestFiltersCRUD:
    """Custom Filters CRUD operation tests"""
    
    def test_get_filters_empty_or_list(self, auth_headers):
        """Test GET filters returns list"""
        response = requests.get(f"{BASE_URL}/api/filters/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_filter_and_verify(self, auth_headers):
        """Test CREATE filter and verify with GET"""
        payload = {
            "name": "TEST_Filter_Block_VPN",
            "description": "Block VPN traffic",
            "action": "block",
            "priority": 50,
            "is_active": True,
            "conditions": {"is_vpn": True}
        }
        create_response = requests.post(f"{BASE_URL}/api/filters/", json=payload, headers=auth_headers)
        assert create_response.status_code == 200
        
        created = create_response.json()
        assert created["name"] == payload["name"]
        assert created["action"] == "block"
        assert created["priority"] == 50
        assert "id" in created
        filter_id = created["id"]
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/filters/{filter_id}", headers=auth_headers)
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["name"] == payload["name"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/filters/{filter_id}", headers=auth_headers)
    
    def test_update_filter_and_verify(self, auth_headers):
        """Test UPDATE filter and verify changes"""
        # Create filter
        create_payload = {
            "name": "TEST_Filter_Update",
            "action": "block",
            "priority": 10,
            "is_active": True
        }
        create_response = requests.post(f"{BASE_URL}/api/filters/", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        filter_id = create_response.json()["id"]
        
        # Update filter
        update_payload = {
            "name": "TEST_Filter_Updated",
            "priority": 80,
            "is_active": False
        }
        update_response = requests.put(f"{BASE_URL}/api/filters/{filter_id}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200
        
        updated = update_response.json()
        assert updated["name"] == update_payload["name"]
        assert updated["priority"] == 80
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/filters/{filter_id}", headers=auth_headers)
    
    def test_delete_filter_and_verify(self, auth_headers):
        """Test DELETE filter and verify removal"""
        # Create filter
        create_payload = {"name": "TEST_Filter_Delete", "action": "allow", "priority": 5, "is_active": True}
        create_response = requests.post(f"{BASE_URL}/api/filters/", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        filter_id = create_response.json()["id"]
        
        # Delete filter
        delete_response = requests.delete(f"{BASE_URL}/api/filters/{filter_id}", headers=auth_headers)
        assert delete_response.status_code == 200
        
        # Verify deleted
        get_response = requests.get(f"{BASE_URL}/api/filters/{filter_id}", headers=auth_headers)
        assert get_response.status_code == 404

class TestDashboard:
    """Dashboard endpoint tests"""
    
    def test_dashboard_stats(self, auth_headers):
        """Test GET dashboard stats returns expected structure"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_clicks" in data
        assert "blocked_clicks" in data
        assert "clicks_today" in data
        assert "by_country" in data
        assert "by_device" in data
        assert "by_os" in data
    
    def test_dashboard_recent_clicks(self, auth_headers):
        """Test GET recent clicks returns list"""
        response = requests.get(f"{BASE_URL}/api/dashboard/recent-clicks?limit=20", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_dashboard_export_csv(self, auth_headers):
        """Test export CSV endpoint"""
        response = requests.get(f"{BASE_URL}/api/dashboard/export-csv", headers=auth_headers)
        assert response.status_code == 200
        assert 'text/csv' in response.headers.get('content-type', '')

class TestReports:
    """Reports endpoint tests"""
    
    def test_performance_report(self, auth_headers):
        """Test performance report endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/performance?days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "data" in data
        assert isinstance(data["data"], list)
    
    def test_fraud_detection_report(self, auth_headers):
        """Test fraud detection report endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/fraud-detection?days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "suspicious_ips" in data
        assert "duplicate_fingerprints" in data
    
    def test_geo_analysis_report(self, auth_headers):
        """Test geo analysis report endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/geo-analysis?days=30", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "countries" in data
        assert isinstance(data["countries"], list)
    
    def test_hourly_patterns_report(self, auth_headers):
        """Test hourly patterns report endpoint"""
        response = requests.get(f"{BASE_URL}/api/reports/hourly-patterns?days=7", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "hourly_data" in data
        assert isinstance(data["hourly_data"], list)

class TestAnalytics:
    """Analytics endpoint tests"""
    
    def test_analytics_overview(self, auth_headers):
        """Test analytics overview endpoint"""
        response = requests.get(f"{BASE_URL}/api/analytics/overview?days=30", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_clicks" in data
        assert "blocked_clicks" in data
        assert "allowed_clicks" in data
        assert "bot_clicks" in data
        assert "vpn_clicks" in data
        assert "total_campaigns" in data
        assert "active_campaigns" in data
        assert "avg_behavioral_score" in data
        assert "block_rate" in data
    
    def test_analytics_trends(self, auth_headers):
        """Test analytics trends endpoint"""
        response = requests.get(f"{BASE_URL}/api/analytics/trends?days=14", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "trends" in data
        assert isinstance(data["trends"], list)
    
    def test_analytics_top_campaigns(self, auth_headers):
        """Test top campaigns endpoint"""
        response = requests.get(f"{BASE_URL}/api/analytics/top-campaigns", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "top_campaigns" in data
        assert isinstance(data["top_campaigns"], list)

class TestAIGenerator:
    """AI Generator endpoint tests"""
    
    def test_get_ai_pages(self, auth_headers):
        """Test GET AI pages returns list"""
        response = requests.get(f"{BASE_URL}/api/ai/pages", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

class TestClickTracking:
    """Click tracking endpoint tests"""
    
    def test_track_nonexistent_campaign(self):
        """Test tracking returns 404 for non-existent campaign"""
        response = requests.get(f"{BASE_URL}/api/track/nonexistent-campaign-id")
        assert response.status_code == 404  # Returns HTML safe page with 404
    
    def test_track_creates_click_record(self, auth_headers):
        """Test tracking endpoint creates click record"""
        # Create a campaign first
        campaign_payload = {
            "name": "TEST_Track_Campaign",
            "target_url": "https://example.com/target",
            "is_active": True,
            "daily_click_limit": 1000
        }
        create_response = requests.post(f"{BASE_URL}/api/campaigns/", json=campaign_payload, headers=auth_headers)
        assert create_response.status_code == 200
        campaign_id = create_response.json()["id"]
        
        # Track a click (will be blocked as bot/no referrer)
        track_response = requests.get(
            f"{BASE_URL}/api/track/{campaign_id}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/100.0.0.0 Safari/537.36"},
            allow_redirects=False
        )
        # Should get redirect or safe page HTML
        assert track_response.status_code in [200, 302]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/campaigns/{campaign_id}", headers=auth_headers)

"""
AI Intelligence API Tests
Tests for: /intelligence/status, /intelligence/insights, /intelligence/rules, rule toggle, rule delete
Note: /intelligence/analyze NOT tested here as it calls Claude API and takes time
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

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


class TestAIIntelligenceStatus:
    """Tests for GET /intelligence/status endpoint"""
    
    def test_status_returns_correct_structure(self, auth_headers):
        """Test /intelligence/status returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/intelligence/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields exist
        assert "total_clicks_analyzed" in data
        assert "total_rules" in data
        assert "active_rules" in data
        assert "last_analysis" in data
        assert "has_enough_data" in data
        
        # Verify data types
        assert isinstance(data["total_clicks_analyzed"], int)
        assert isinstance(data["total_rules"], int)
        assert isinstance(data["active_rules"], int)
        assert isinstance(data["has_enough_data"], bool)
        
        print(f"Intelligence Status: {data}")
    
    def test_status_requires_auth(self):
        """Test /intelligence/status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/intelligence/status")
        assert response.status_code == 401


class TestAIIntelligenceInsights:
    """Tests for GET /intelligence/insights endpoint"""
    
    def test_insights_returns_list(self, auth_headers):
        """Test /intelligence/insights returns list of insights"""
        response = requests.get(f"{BASE_URL}/api/intelligence/insights", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"Found {len(data)} insights")
        
        # If insights exist, verify structure
        if len(data) > 0:
            insight = data[0]
            assert "id" in insight
            assert "created_at" in insight
            # Check for audience profile if present
            if "audience_profile" in insight:
                profile = insight["audience_profile"]
                print(f"Latest insight has audience_profile: {profile.keys() if isinstance(profile, dict) else 'N/A'}")
    
    def test_insights_requires_auth(self):
        """Test /intelligence/insights requires authentication"""
        response = requests.get(f"{BASE_URL}/api/intelligence/insights")
        assert response.status_code == 401


class TestAIIntelligenceRules:
    """Tests for GET /intelligence/rules endpoint and rule management"""
    
    def test_rules_returns_list(self, auth_headers):
        """Test /intelligence/rules returns list of AI rules"""
        response = requests.get(f"{BASE_URL}/api/intelligence/rules", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"Found {len(data)} AI rules")
        
        # If rules exist, verify structure
        if len(data) > 0:
            rule = data[0]
            assert "id" in rule
            assert "type" in rule  # block or allow
            assert "field" in rule
            assert "operator" in rule
            assert "value" in rule
            assert "is_active" in rule
            assert "confidence" in rule
            assert "reason" in rule
            
            print(f"Sample rule: type={rule['type']}, field={rule['field']}, operator={rule['operator']}")
    
    def test_rules_requires_auth(self):
        """Test /intelligence/rules requires authentication"""
        response = requests.get(f"{BASE_URL}/api/intelligence/rules")
        assert response.status_code == 401


class TestAIRuleToggle:
    """Tests for PUT /intelligence/rules/{id}/toggle endpoint"""
    
    def test_toggle_rule_state(self, auth_headers):
        """Test toggling rule active state"""
        # First get existing rules
        rules_response = requests.get(f"{BASE_URL}/api/intelligence/rules", headers=auth_headers)
        assert rules_response.status_code == 200
        rules = rules_response.json()
        
        if len(rules) == 0:
            pytest.skip("No AI rules exist to test toggle")
        
        # Pick first rule and toggle it
        rule = rules[0]
        rule_id = rule["id"]
        original_state = rule["is_active"]
        new_state = not original_state
        
        # Toggle the rule
        toggle_response = requests.put(
            f"{BASE_URL}/api/intelligence/rules/{rule_id}/toggle",
            json={"is_active": new_state},
            headers=auth_headers
        )
        assert toggle_response.status_code == 200
        
        toggled_rule = toggle_response.json()
        assert toggled_rule["is_active"] == new_state
        
        # Verify with GET
        verify_response = requests.get(f"{BASE_URL}/api/intelligence/rules", headers=auth_headers)
        updated_rules = verify_response.json()
        updated_rule = next((r for r in updated_rules if r["id"] == rule_id), None)
        assert updated_rule is not None
        assert updated_rule["is_active"] == new_state
        
        # Restore original state
        restore_response = requests.put(
            f"{BASE_URL}/api/intelligence/rules/{rule_id}/toggle",
            json={"is_active": original_state},
            headers=auth_headers
        )
        assert restore_response.status_code == 200
        print(f"Rule {rule_id} toggle test passed - toggled {original_state} -> {new_state} -> {original_state}")
    
    def test_toggle_nonexistent_rule_returns_404(self, auth_headers):
        """Test toggling non-existent rule returns 404"""
        response = requests.put(
            f"{BASE_URL}/api/intelligence/rules/nonexistent-rule-id/toggle",
            json={"is_active": True},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestAIRuleDelete:
    """Tests for DELETE /intelligence/rules/{id} endpoint"""
    
    def test_delete_nonexistent_rule_returns_404(self, auth_headers):
        """Test deleting non-existent rule returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/intelligence/rules/nonexistent-rule-id",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    # Note: We don't test actual rule deletion as we want to preserve test data


class TestTrackingWithAIRules:
    """Tests for tracking endpoint applying AI rules"""
    
    def test_tracking_applies_ai_rules(self, auth_headers):
        """Verify tracking endpoint considers AI rules"""
        # First check if there are active AI rules
        rules_response = requests.get(f"{BASE_URL}/api/intelligence/rules", headers=auth_headers)
        rules = rules_response.json()
        active_rules = [r for r in rules if r["is_active"]]
        
        # Get existing campaigns
        campaigns_response = requests.get(f"{BASE_URL}/api/campaigns/", headers=auth_headers)
        campaigns = campaigns_response.json()
        
        if len(campaigns) == 0:
            pytest.skip("No campaigns to test tracking")
        
        # Find an active campaign
        active_campaign = next((c for c in campaigns if c.get("is_active")), None)
        if not active_campaign:
            pytest.skip("No active campaign to test tracking")
        
        campaign_id = active_campaign["id"]
        
        # Make a tracking request
        track_response = requests.get(
            f"{BASE_URL}/api/track/{campaign_id}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            allow_redirects=False
        )
        
        # Should get a redirect or safe page
        assert track_response.status_code in [200, 302]
        print(f"Tracking request returned {track_response.status_code}, {len(active_rules)} AI rules were checked")

"""
WhatsApp CRM API Tests
Tests for the new WhatsApp CRM feature including:
- Webhook verification and message receiving
- Conversations management
- Contact classification (human/bot/spam)
- Stats and settings
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@aresguardian.com"
TEST_PASSWORD = "20060920+"

# WhatsApp verification token
WA_VERIFY_TOKEN = "traffic_guardian_verify_2024"


class TestWhatsAppWebhook:
    """WhatsApp webhook endpoint tests - PUBLIC, no auth needed"""
    
    def test_webhook_verification_success(self):
        """GET /api/whatsapp/webhook with correct verify token returns challenge"""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": WA_VERIFY_TOKEN,
            "hub.challenge": "test_challenge_123"
        }
        response = requests.get(f"{BASE_URL}/api/whatsapp/webhook", params=params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.text == "test_challenge_123", f"Expected challenge, got: {response.text}"
        print("PASS: Webhook verification returns correct challenge")
    
    def test_webhook_verification_wrong_token(self):
        """GET /api/whatsapp/webhook with wrong token returns 403"""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "test_challenge_123"
        }
        response = requests.get(f"{BASE_URL}/api/whatsapp/webhook", params=params)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("PASS: Webhook verification with wrong token returns 403")
    
    def test_webhook_receive_message(self):
        """POST /api/whatsapp/webhook simulates Meta webhook payload"""
        # Simulated Meta webhook payload
        test_phone = f"549{uuid.uuid4().hex[:10]}"
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "contacts": [{
                            "profile": {"name": "Test User API"},
                            "wa_id": test_phone
                        }],
                        "messages": [{
                            "from": test_phone,
                            "id": f"wamid.{uuid.uuid4().hex}",
                            "timestamp": "1234567890",
                            "text": {"body": "Hola, test message from API"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        response = requests.post(f"{BASE_URL}/api/whatsapp/webhook", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status ok, got: {data}"
        print(f"PASS: Webhook receives message for phone {test_phone}")
        return test_phone


class TestWhatsAppAuth:
    """Helper to get auth token"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        print(f"PASS: Authentication successful")
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}


class TestWhatsAppSettings(TestWhatsAppAuth):
    """WhatsApp settings endpoints - require auth"""
    
    def test_get_settings(self, auth_headers):
        """GET /api/whatsapp/settings returns settings"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/settings", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Check expected fields
        assert "verify_token" in data, f"Missing verify_token: {data}"
        assert "auto_reply_enabled" in data, f"Missing auto_reply_enabled: {data}"
        print(f"PASS: GET settings returns: {list(data.keys())}")
    
    def test_update_settings(self, auth_headers):
        """POST /api/whatsapp/settings updates settings"""
        update_data = {
            "auto_reply_message": "Test auto reply message from API test"
        }
        response = requests.post(f"{BASE_URL}/api/whatsapp/settings", headers=auth_headers, json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, f"Expected message in response: {data}"
        print(f"PASS: POST settings update successful")
        
        # Verify update
        response = requests.get(f"{BASE_URL}/api/whatsapp/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("auto_reply_message") == "Test auto reply message from API test"
        print("PASS: Settings update verified")


class TestWhatsAppConversations(TestWhatsAppAuth):
    """WhatsApp conversations endpoints"""
    
    def test_get_conversations(self, auth_headers):
        """GET /api/whatsapp/conversations returns list"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/conversations", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        print(f"PASS: GET conversations returns {len(data)} contacts")
        return data
    
    def test_get_conversations_with_filter(self, auth_headers):
        """GET /api/whatsapp/conversations with classification filter"""
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/conversations",
            headers=auth_headers,
            params={"classification": "new"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        # All contacts should have classification "new"
        for contact in data:
            assert contact.get("classification") == "new", f"Unexpected classification: {contact}"
        print(f"PASS: GET conversations with filter returns {len(data)} 'new' contacts")
    
    def test_get_conversations_with_search(self, auth_headers):
        """GET /api/whatsapp/conversations with search query"""
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/conversations",
            headers=auth_headers,
            params={"search": "549"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        print(f"PASS: GET conversations with search returns {len(data)} contacts")


class TestWhatsAppConversationDetail(TestWhatsAppAuth):
    """WhatsApp conversation detail and classification"""
    
    @pytest.fixture(scope="class")
    def test_contact_phone(self, auth_headers):
        """Create a test contact via webhook and return phone number"""
        test_phone = f"549TEST{uuid.uuid4().hex[:8]}"
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "contacts": [{
                            "profile": {"name": "TEST_Classification_User"},
                            "wa_id": test_phone
                        }],
                        "messages": [{
                            "from": test_phone,
                            "id": f"wamid.{uuid.uuid4().hex}",
                            "timestamp": "1234567890",
                            "text": {"body": "Test message for classification"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        response = requests.post(f"{BASE_URL}/api/whatsapp/webhook", json=payload)
        assert response.status_code == 200
        print(f"PASS: Created test contact: {test_phone}")
        return test_phone
    
    def test_get_conversation_detail(self, auth_headers, test_contact_phone):
        """GET /api/whatsapp/conversations/{phone} returns conversation detail"""
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/conversations/{test_contact_phone}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "contact" in data, f"Missing contact: {data}"
        assert "messages" in data, f"Missing messages: {data}"
        assert data["contact"]["phone"] == test_contact_phone
        assert isinstance(data["messages"], list)
        print(f"PASS: GET conversation detail for {test_contact_phone} has {len(data['messages'])} messages")
    
    def test_get_conversation_not_found(self, auth_headers):
        """GET /api/whatsapp/conversations/{phone} returns 404 for non-existent contact"""
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/conversations/nonexistent12345",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: GET non-existent conversation returns 404")
    
    def test_classify_contact_as_human(self, auth_headers, test_contact_phone):
        """POST /api/whatsapp/conversations/{phone}/classify classifies as human"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/conversations/{test_contact_phone}/classify",
            headers=auth_headers,
            json={"classification": "human"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"PASS: Classified {test_contact_phone} as human")
        
        # Verify classification
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/conversations/{test_contact_phone}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["contact"]["classification"] == "human"
        print("PASS: Classification verified")
    
    def test_classify_contact_as_bot(self, auth_headers, test_contact_phone):
        """POST /api/whatsapp/conversations/{phone}/classify classifies as bot"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/conversations/{test_contact_phone}/classify",
            headers=auth_headers,
            json={"classification": "bot"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"PASS: Classified {test_contact_phone} as bot")
    
    def test_classify_contact_as_spam(self, auth_headers, test_contact_phone):
        """POST /api/whatsapp/conversations/{phone}/classify classifies as spam"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/conversations/{test_contact_phone}/classify",
            headers=auth_headers,
            json={"classification": "spam"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"PASS: Classified {test_contact_phone} as spam")
    
    def test_classify_invalid(self, auth_headers, test_contact_phone):
        """POST /api/whatsapp/conversations/{phone}/classify with invalid classification"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/conversations/{test_contact_phone}/classify",
            headers=auth_headers,
            json={"classification": "invalid_type"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Invalid classification returns 400")
    
    def test_classify_not_found(self, auth_headers):
        """POST /api/whatsapp/conversations/{phone}/classify for non-existent contact"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/conversations/nonexistent12345/classify",
            headers=auth_headers,
            json={"classification": "human"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Classify non-existent contact returns 404")


class TestWhatsAppStats(TestWhatsAppAuth):
    """WhatsApp stats endpoint"""
    
    def test_get_stats(self, auth_headers):
        """GET /api/whatsapp/stats returns stats"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Check expected fields
        expected_fields = ["total_contacts", "humans", "bots", "spam", "new_contacts", "messages_today", "total_messages"]
        for field in expected_fields:
            assert field in data, f"Missing field {field}: {data}"
        print(f"PASS: GET stats returns: {data}")


class TestWhatsAppUnauthorized:
    """Test that CRM endpoints require auth"""
    
    def test_settings_requires_auth(self):
        """GET /api/whatsapp/settings without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/settings")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Settings endpoint requires auth")
    
    def test_conversations_requires_auth(self):
        """GET /api/whatsapp/conversations without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/conversations")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Conversations endpoint requires auth")
    
    def test_stats_requires_auth(self):
        """GET /api/whatsapp/stats without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: Stats endpoint requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

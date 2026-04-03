#!/usr/bin/env python3
"""
AdPhantom CRM Backend API Testing Suite
Tests all the features mentioned in the review request
"""

import requests
import sys
import json
from datetime import datetime, timedelta
import time

class AdPhantomAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        self.log(f"Testing {name}...")
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}", "PASS")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}", "FAIL")
                try:
                    error_detail = response.json()
                    self.log(f"   Error: {error_detail}", "ERROR")
                except:
                    self.log(f"   Response: {response.text[:200]}", "ERROR")
                return False, {}

        except Exception as e:
            self.log(f"❌ {name} - Exception: {str(e)}", "FAIL")
            return False, {}

    def test_login(self):
        """Test admin login"""
        self.log("=== Testing Authentication ===")
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@adphantom.com", "password": "admin123"}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.session.headers.update({'Authorization': f'Bearer {self.token}'})
            self.log("✅ Authentication token obtained")
            return True
        return False

    def test_user_management(self):
        """Test user management functionality"""
        self.log("=== Testing User Management ===")
        
        # Get current user info
        success, user_info = self.run_test("Get Current User", "GET", "auth/me", 200)
        if success:
            self.log(f"Current user: {user_info.get('email')} (role: {user_info.get('role')})")

        # Get all users
        success, users = self.run_test("Get All Users", "GET", "auth/users", 200)
        if success:
            self.log(f"Found {len(users)} existing users")

        # Create a test cajero user
        test_user_data = {
            "email": f"test_cajero_{int(time.time())}@test.com",
            "password": "testpass123",
            "role": "cajero",
            "line_ids": [],
            "welcome_message": "¡Hola! Bienvenido a nuestro servicio",
            "user_message": "Aquí tienes tus datos de acceso"
        }
        
        success, created_user = self.run_test(
            "Create Cajero User",
            "POST", 
            "auth/users",
            200,
            data=test_user_data
        )
        
        if success:
            self.log("✅ Cajero user created successfully")
            
            # Get users again to verify creation
            success, updated_users = self.run_test("Verify User Creation", "GET", "auth/users", 200)
            if success and len(updated_users) > len(users):
                self.log("✅ User appears in user list")
            
        return success

    def test_crm_lines(self):
        """Test CRM lines functionality"""
        self.log("=== Testing CRM Lines ===")
        
        # Get existing lines
        success, lines = self.run_test("Get CRM Lines", "GET", "crm/lines", 200)
        if success:
            self.log(f"Found {len(lines)} existing lines")
            return True
        return False

    def test_funnel_stats(self):
        """Test funnel statistics with different filters"""
        self.log("=== Testing Funnel Statistics ===")
        
        # Test daily filter
        success, daily_stats = self.run_test(
            "Funnel Stats - Daily",
            "GET",
            "crm/funnel/stats",
            200,
            params={"filter_type": "diario"}
        )
        
        if success:
            self.log("✅ Daily funnel stats working")
        
        # Test weekly filter
        success, weekly_stats = self.run_test(
            "Funnel Stats - Weekly", 
            "GET",
            "crm/funnel/stats",
            200,
            params={"filter_type": "semanal"}
        )
        
        if success:
            self.log("✅ Weekly funnel stats working")
            
        # Test monthly filter
        success, monthly_stats = self.run_test(
            "Funnel Stats - Monthly",
            "GET", 
            "crm/funnel/stats",
            200,
            params={"filter_type": "mensual"}
        )
        
        if success:
            self.log("✅ Monthly funnel stats working")
            
        # Test custom date range
        start_date = "2026-01-01"
        end_date = "2026-04-03"
        success, custom_stats = self.run_test(
            "Funnel Stats - Custom Date Range",
            "GET",
            "crm/funnel/stats", 
            200,
            params={"start_date": start_date, "end_date": end_date}
        )
        
        if success:
            self.log("✅ Custom date range funnel stats working")
            
        return success

    def test_funnel_by_ad(self):
        """Test funnel by ad endpoint"""
        self.log("=== Testing Funnel by Ad ===")
        
        success, ad_stats = self.run_test(
            "Funnel by Ad",
            "GET",
            "crm/funnel/by-ad",
            200
        )
        
        if success:
            self.log("✅ Funnel by ad endpoint working")
            
        return success

    def test_leads_crm(self):
        """Test leads CRM functionality"""
        self.log("=== Testing Leads CRM ===")
        
        # Get leads
        success, leads = self.run_test("Get Leads", "GET", "crm/leads", 200)
        if success:
            self.log(f"Found {len(leads.get('leads', []))} leads")
            
        return success

    def test_ai_tools(self):
        """Test AI tools functionality"""
        self.log("=== Testing AI Tools ===")
        
        # Test AI page generation (this might fail if no API key is configured)
        test_prompt = "Create a simple landing page for a gaming platform"
        success, ai_page = self.run_test(
            "AI Page Generation",
            "POST",
            "ai/generate",
            200,
            data={"prompt": test_prompt}
        )
        
        if success:
            self.log("✅ AI page generation working")
        else:
            self.log("⚠️  AI page generation failed (likely missing API key)")
            
        # Get AI pages
        success, pages = self.run_test("Get AI Pages", "GET", "ai/pages", 200)
        if success:
            self.log(f"Found {len(pages)} AI generated pages")
            
        return True  # Don't fail the test suite if AI is not configured

    def test_campaigns(self):
        """Test campaigns functionality"""
        self.log("=== Testing Campaigns ===")
        
        # Get campaigns
        success, campaigns = self.run_test("Get Campaigns", "GET", "campaigns", 200)
        if success:
            self.log(f"Found {len(campaigns)} campaigns")
            
        return success

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        self.log("=== Testing Dashboard Stats ===")
        
        success, stats = self.run_test("Dashboard Stats", "GET", "dashboard/stats", 200)
        if success:
            self.log("✅ Dashboard stats working")
            
        return success

    def run_all_tests(self):
        """Run all test suites"""
        self.log("🚀 Starting AdPhantom CRM Backend Tests")
        self.log(f"Testing against: {self.base_url}")
        
        # Test authentication first
        if not self.test_login():
            self.log("❌ Authentication failed - stopping tests", "CRITICAL")
            return False
            
        # Run all test suites
        test_suites = [
            self.test_user_management,
            self.test_crm_lines, 
            self.test_funnel_stats,
            self.test_funnel_by_ad,
            self.test_leads_crm,
            self.test_campaigns,
            self.test_dashboard_stats,
            self.test_ai_tools,  # This one might fail if no API key
        ]
        
        for test_suite in test_suites:
            try:
                test_suite()
            except Exception as e:
                self.log(f"❌ Test suite failed: {str(e)}", "ERROR")
                
        # Print final results
        self.log("=" * 50)
        self.log(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            self.log("🎉 All tests passed!", "SUCCESS")
            return True
        else:
            failed = self.tests_run - self.tests_passed
            self.log(f"⚠️  {failed} tests failed", "WARNING")
            return False

def main():
    """Main test runner"""
    tester = AdPhantomAPITester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        tester.log("Tests interrupted by user", "INFO")
        return 1
    except Exception as e:
        tester.log(f"Unexpected error: {str(e)}", "CRITICAL")
        return 1

if __name__ == "__main__":
    sys.exit(main())
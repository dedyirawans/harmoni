#!/usr/bin/env python3
"""
Backend Runtime Health Test - Post requirements.txt Dependency Fix
Tests core backend endpoints to verify no import/startup breakage after removing duplicate litellm line
"""

import requests
import json

# Configuration
BASE_URL = "https://github-workflow-14.preview.emergentagent.com/api"

# Super admin credentials from test_credentials.md
SUPER_ADMIN = {"email": "irawandedy185@gmail.com", "password": "Harmoni#Wisata2025"}

# Test results tracking
test_results = []

def log_test(name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "details": details})
    print(f"{status}: {name}")
    if details:
        print(f"   Details: {details}")

def print_section(title):
    """Print section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def main():
    print("\n🧪 Backend Runtime Health Test - Post requirements.txt Fix")
    print("="*70)
    print("Testing backend runtime after removing duplicate litellm line")
    print("="*70)
    
    # Test 1: Server up - GET /api/ returns 200
    print_section("Test 1: Server Health Check")
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        log_test("GET /api/ (server health)", 
                 resp.status_code == 200,
                 f"Status: {resp.status_code}, Response: {resp.text[:100] if resp.text else 'Empty'}")
    except Exception as e:
        log_test("GET /api/ (server health)", False, f"Error: {e}")
    
    # Test 2: Auth - POST /api/auth/login with super admin credentials
    print_section("Test 2: Super Admin Authentication")
    admin_token = None
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json=SUPER_ADMIN, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            admin_token = data.get("token")
            log_test("POST /api/auth/login (super_admin)", 
                     admin_token is not None,
                     f"Status: {resp.status_code}, Token received: {'Yes' if admin_token else 'No'}")
        else:
            log_test("POST /api/auth/login (super_admin)", False,
                     f"Status: {resp.status_code}, Response: {resp.text}")
    except Exception as e:
        log_test("POST /api/auth/login (super_admin)", False, f"Error: {e}")
    
    if not admin_token:
        print("\n❌ Cannot proceed without admin token. Stopping tests.")
        print_summary()
        return
    
    # Test 3: GET /api/users - should return array with one super_admin user
    print_section("Test 3: Users List (should contain one super_admin)")
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/users", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            is_array = isinstance(data, list)
            has_one_user = len(data) == 1 if is_array else False
            super_admin_exists = False
            if has_one_user:
                user = data[0]
                super_admin_exists = (user.get("email") == "irawandedy185@gmail.com" and 
                                     user.get("role") == "super_admin")
            log_test("GET /api/users (super_admin)", 
                     is_array and has_one_user and super_admin_exists,
                     f"Status: {resp.status_code}, Users count: {len(data) if is_array else 'N/A'}, Super admin found: {super_admin_exists}")
        else:
            log_test("GET /api/users (super_admin)", False,
                     f"Status: {resp.status_code}, Response: {resp.text[:200]}")
    except Exception as e:
        log_test("GET /api/users (super_admin)", False, f"Error: {e}")
    
    # Test 4: GET /api/company-settings - should return 200 with company_name "PT Harmoni Wisata Internusa"
    print_section("Test 4: Company Settings")
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/company-settings", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            company_name = data.get("company_name")
            expected_name = "PT Harmoni Wisata Internusa"
            log_test("GET /api/company-settings", 
                     company_name == expected_name,
                     f"Status: {resp.status_code}, company_name: '{company_name}' (expected: '{expected_name}')")
        else:
            log_test("GET /api/company-settings", False,
                     f"Status: {resp.status_code}, Response: {resp.text[:200]}")
    except Exception as e:
        log_test("GET /api/company-settings", False, f"Error: {e}")
    
    # Test 5: GET /api/system-settings - should return 200 with login_page settings
    print_section("Test 5: System Settings (login_page)")
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = requests.get(f"{BASE_URL}/system-settings", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            settings = data.get("settings", {})
            login_page = settings.get("login_page", {})
            has_login_page_keys = all(k in login_page for k in ["heading", "subheading", "background_image"])
            log_test("GET /api/system-settings", 
                     has_login_page_keys,
                     f"Status: {resp.status_code}, login_page keys present: {has_login_page_keys}, keys: {list(login_page.keys())}")
        else:
            log_test("GET /api/system-settings", False,
                     f"Status: {resp.status_code}, Response: {resp.text[:200]}")
    except Exception as e:
        log_test("GET /api/system-settings", False, f"Error: {e}")
    
    # Test 6: Optional - Create temporary sales user
    print_section("Test 6: Create Temporary Sales User (Optional)")
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        sales_user_data = {
            "name": "QA Sales",
            "username": "qa.sales",
            "email": "qa.sales@example.com",
            "role": "sales",
            "branch": "Jakarta",
            "data_scope": "own",
            "password": "Test@12345"
        }
        resp = requests.post(f"{BASE_URL}/users", headers=headers, json=sales_user_data, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            role_correct = data.get("role") == "sales"
            branch_correct = data.get("branch") == "Jakarta"
            log_test("POST /api/users (create sales user)", 
                     role_correct and branch_correct,
                     f"Status: {resp.status_code}, role: {data.get('role')}, branch: {data.get('branch')}")
        elif resp.status_code == 403:
            log_test("POST /api/users (create sales user)", True,
                     f"Status: {resp.status_code} - User creation restricted (acceptable)")
        else:
            log_test("POST /api/users (create sales user)", False,
                     f"Status: {resp.status_code}, Response: {resp.text[:200]}")
    except Exception as e:
        log_test("POST /api/users (create sales user)", False, f"Error: {e}")
    
    print_summary()

def print_summary():
    """Print test summary"""
    print_section("Test Summary")
    total = len(test_results)
    passed = sum(1 for t in test_results if t["passed"])
    failed = total - passed
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%\n")
    
    if failed > 0:
        print("Failed Tests:")
        for t in test_results:
            if not t["passed"]:
                print(f"  ❌ {t['name']}")
                if t["details"]:
                    print(f"     {t['details']}")
    
    print("\n" + "="*70)
    print("🏁 Backend Runtime Health Test Complete")
    print("="*70 + "\n")
    
    # Final verdict
    critical_tests = ["GET /api/ (server health)", "POST /api/auth/login (super_admin)", 
                     "GET /api/users (super_admin)", "GET /api/company-settings", 
                     "GET /api/system-settings"]
    critical_passed = all(t["passed"] for t in test_results if t["name"] in critical_tests)
    
    if critical_passed:
        print("✅ VERDICT: Backend runtime is HEALTHY after requirements.txt fix")
        print("   All core endpoints responding correctly. No import/startup breakage detected.\n")
    else:
        print("❌ VERDICT: Backend runtime has ISSUES after requirements.txt fix")
        print("   Some core endpoints are not responding correctly.\n")

if __name__ == "__main__":
    main()

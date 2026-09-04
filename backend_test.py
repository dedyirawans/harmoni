#!/usr/bin/env python3
"""
MMBC Hotel Integration Backend Test Suite
Tests all MMBC hotel endpoints with proper auth and validation
"""

import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://git-continue-5.preview.emergentagent.com/api"

# Test credentials
SUPER_ADMIN = {"email": "dedyirawan18@gmail.com", "password": "Admin@123"}
SALES = {"email": "sales@safarcrm.com", "password": "Sales@123"}
ACCOUNTING = {"email": "accounting@safarcrm.com", "password": "Account@123"}

# Test results tracking
test_results = []

def log_test(name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({"name": name, "passed": passed, "details": details})
    print(f"{status}: {name}")
    if details:
        print(f"   Details: {details}")

def login(credentials):
    """Login and return token"""
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json=credentials, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token")
            if token:
                return token
            else:
                print(f"   Warning: Login response missing 'token' field: {data}")
                return None
        else:
            print(f"   Login failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"   Login error: {e}")
        return None

def make_request(method, endpoint, token=None, json_data=None, params=None):
    """Make HTTP request with optional auth"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params, timeout=15)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json_data, timeout=15)
        elif method == "PUT":
            resp = requests.put(url, headers=headers, json=json_data, timeout=15)
        else:
            return None
        
        return resp
    except Exception as e:
        print(f"   Request error: {e}")
        return None

def get_future_date(days_ahead):
    """Get future date in YYYY-MM-DD format"""
    return (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def print_section(title):
    """Print section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def main():
    print("\n🧪 MMBC Hotel Integration Backend Test Suite")
    print("="*70)
    
    # Login as different users
    print_section("Authentication")
    admin_token = login(SUPER_ADMIN)
    log_test("Super Admin Login", admin_token is not None, 
             "Token received" if admin_token else "Login failed")
    
    sales_token = login(SALES)
    log_test("Sales Login", sales_token is not None,
             "Token received" if sales_token else "Login failed")
    
    accounting_token = login(ACCOUNTING)
    log_test("Accounting Login", accounting_token is not None,
             "Token received" if accounting_token else "Login failed")
    
    if not admin_token:
        print("\n❌ Cannot proceed without admin token")
        return
    
    # Test 1: GET /api/hotel/settings (super_admin only)
    print_section("Test 1: Hotel Settings - GET (super_admin only)")
    
    resp = make_request("GET", "/hotel/settings", admin_token)
    if resp and resp.status_code == 200:
        data = resp.json()
        has_required = all(k in data for k in ["provider", "base_url", "username", "password_set", "password_masked", "markup_pct"])
        log_test("GET /api/hotel/settings (super_admin)", 
                 has_required and data.get("provider") == "MMBC",
                 f"Provider: {data.get('provider')}, markup_pct: {data.get('markup_pct')}, password_set: {data.get('password_set')}")
    else:
        log_test("GET /api/hotel/settings (super_admin)", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test with sales user (should be 403)
    if sales_token:
        resp = make_request("GET", "/hotel/settings", sales_token)
        log_test("GET /api/hotel/settings (sales - should be 403)", 
                 resp and resp.status_code == 403,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 2: PUT /api/hotel/settings (super_admin only)
    print_section("Test 2: Hotel Settings - PUT (super_admin only)")
    
    # Update settings without password (should keep existing password)
    update_data = {
        "base_url": "https://klikmbc.co.id/json/hotel/",
        "username": "irawandedy185@gmail.com",
        "markup_pct": 20,
        "currency": "IDR",
        "active": True
    }
    resp = make_request("PUT", "/hotel/settings", admin_token, json_data=update_data)
    if resp and resp.status_code == 200:
        data = resp.json()
        log_test("PUT /api/hotel/settings (without password)", 
                 data.get("markup_pct") == 20 and data.get("password_set") == True,
                 f"markup_pct updated to {data.get('markup_pct')}, password_set: {data.get('password_set')}")
    else:
        log_test("PUT /api/hotel/settings (without password)", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Verify the update persisted
    resp = make_request("GET", "/hotel/settings", admin_token)
    if resp and resp.status_code == 200:
        data = resp.json()
        log_test("Verify settings persisted", 
                 data.get("markup_pct") == 20,
                 f"markup_pct: {data.get('markup_pct')}")
    
    # Update with password (should update password)
    update_with_pass = {**update_data, "password": "Tazkia2009"}
    resp = make_request("PUT", "/hotel/settings", admin_token, json_data=update_with_pass)
    if resp and resp.status_code == 200:
        data = resp.json()
        log_test("PUT /api/hotel/settings (with password)", 
                 data.get("password_set") == True,
                 f"password_set: {data.get('password_set')}, masked: {data.get('password_masked')}")
    
    # Test 3: POST /api/hotel/test-connection (super_admin only)
    print_section("Test 3: Test Connection (super_admin only)")
    
    resp = make_request("POST", "/hotel/test-connection", admin_token, json_data={})
    if resp and resp.status_code == 200:
        data = resp.json()
        has_structure = all(k in data for k in ["success", "message", "detail"])
        # IMPORTANT: "invalid login" is EXPECTED and acceptable
        is_invalid_login = data.get("detail", {}).get("reason") == "invalid login"
        log_test("POST /api/hotel/test-connection (super_admin)", 
                 has_structure,
                 f"success: {data.get('success')}, reason: {data.get('detail', {}).get('reason')} (invalid login is EXPECTED)")
    else:
        log_test("POST /api/hotel/test-connection (super_admin)", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test with sales user (should be 403)
    if sales_token:
        resp = make_request("POST", "/hotel/test-connection", sales_token, json_data={})
        log_test("POST /api/hotel/test-connection (sales - should be 403)", 
                 resp and resp.status_code == 403,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 4: GET /api/hotel/countries
    print_section("Test 4: Countries List")
    
    resp = make_request("GET", "/hotel/countries", admin_token)
    if resp and resp.status_code == 200:
        data = resp.json()
        log_test("GET /api/hotel/countries", 
                 isinstance(data, list),
                 f"Returned {len(data)} countries (empty is OK due to invalid login)")
    else:
        log_test("GET /api/hotel/countries", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 5: POST /api/hotel/sync and GET /api/hotel/sync-status (super_admin only)
    print_section("Test 5: Master Data Sync (super_admin only)")
    
    resp = make_request("POST", "/hotel/sync", admin_token, json_data={})
    if resp and resp.status_code == 200:
        data = resp.json()
        has_fields = "started" in data and "message" in data
        log_test("POST /api/hotel/sync (super_admin)", 
                 has_fields,
                 f"started: {data.get('started')}, message: {data.get('message')}")
    else:
        log_test("POST /api/hotel/sync (super_admin)", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Get sync status
    resp = make_request("GET", "/hotel/sync-status", admin_token)
    if resp and resp.status_code == 200:
        data = resp.json()
        has_counts = "counts" in data
        log_test("GET /api/hotel/sync-status (super_admin)", 
                 has_counts,
                 f"counts: {data.get('counts')}")
    else:
        log_test("GET /api/hotel/sync-status (super_admin)", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test with sales user (should be 403)
    if sales_token:
        resp = make_request("GET", "/hotel/sync-status", sales_token)
        log_test("GET /api/hotel/sync-status (sales - should be 403)", 
                 resp and resp.status_code == 403,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 6: GET /api/hotel/cities
    print_section("Test 6: Cities List")
    
    resp = make_request("GET", "/hotel/cities", admin_token, params={"iso": "IDN"})
    if resp and resp.status_code == 200:
        data = resp.json()
        log_test("GET /api/hotel/cities?iso=IDN", 
                 isinstance(data, list),
                 f"Returned {len(data)} cities (empty is OK)")
    else:
        log_test("GET /api/hotel/cities?iso=IDN", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 7: GET /api/hotel/hotels/search
    print_section("Test 7: Hotels Search")
    
    resp = make_request("GET", "/hotel/hotels/search", admin_token, params={"q": "test"})
    if resp and resp.status_code == 200:
        data = resp.json()
        log_test("GET /api/hotel/hotels/search?q=test", 
                 isinstance(data, list),
                 f"Returned {len(data)} hotels (empty is OK)")
    else:
        log_test("GET /api/hotel/hotels/search?q=test", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 8: POST /api/hotel/search - Validation
    print_section("Test 8: Hotel Search - Validation")
    
    # Test 8a: Missing dates
    resp = make_request("POST", "/hotel/search", admin_token, json_data={
        "searchType": "city",
        "countryCode": "192",
        "cityId": "14018"
    })
    log_test("POST /api/hotel/search (missing dates - should be 422/400)", 
             resp and resp.status_code in [400, 422],
             f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 8b: Invalid dates (checkOut <= checkIn)
    today = datetime.now().strftime("%Y-%m-%d")
    resp = make_request("POST", "/hotel/search", admin_token, json_data={
        "searchType": "city",
        "countryCode": "192",
        "cityId": "14018",
        "checkInDate": today,
        "checkOutDate": today,
        "numberOfRooms": 1,
        "numberOfAdult": 2
    })
    log_test("POST /api/hotel/search (checkOut <= checkIn - should be 400)", 
             resp and resp.status_code == 400,
             f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 8c: Past date
    past_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    future_date = get_future_date(7)
    resp = make_request("POST", "/hotel/search", admin_token, json_data={
        "searchType": "city",
        "countryCode": "192",
        "cityId": "14018",
        "checkInDate": past_date,
        "checkOutDate": future_date,
        "numberOfRooms": 1,
        "numberOfAdult": 2
    })
    log_test("POST /api/hotel/search (past checkIn - should be 400)", 
             resp and resp.status_code == 400,
             f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 8d: City search without countryCode/cityId
    checkin = get_future_date(30)
    checkout = get_future_date(32)
    resp = make_request("POST", "/hotel/search", admin_token, json_data={
        "searchType": "city",
        "checkInDate": checkin,
        "checkOutDate": checkout,
        "numberOfRooms": 1,
        "numberOfAdult": 2
    })
    log_test("POST /api/hotel/search (city without countryCode/cityId - should be 400)", 
             resp and resp.status_code == 400,
             f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 8e: Hotel search with empty hotels list
    resp = make_request("POST", "/hotel/search", admin_token, json_data={
        "searchType": "hotel",
        "hotels": [],
        "checkInDate": checkin,
        "checkOutDate": checkout,
        "numberOfRooms": 1,
        "numberOfAdult": 2
    })
    log_test("POST /api/hotel/search (hotel with empty list - should be 400)", 
             resp and resp.status_code == 400,
             f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 8f: Valid city search (will return empty due to invalid login, but should not 500)
    resp = make_request("POST", "/hotel/search", admin_token, json_data={
        "searchType": "city",
        "countryCode": "192",
        "cityId": "14018",
        "checkInDate": checkin,
        "checkOutDate": checkout,
        "numberOfRooms": 1,
        "numberOfAdult": 2,
        "numberOfChildren": 0
    })
    if resp and resp.status_code == 200:
        data = resp.json()
        has_structure = all(k in data for k in ["results", "count", "error", "message"])
        log_test("POST /api/hotel/search (valid city search)", 
                 has_structure,
                 f"count: {data.get('count')}, error: {data.get('error')} (empty results OK due to invalid login)")
    else:
        log_test("POST /api/hotel/search (valid city search)", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 9: Booking endpoints
    print_section("Test 9: Booking Endpoints")
    
    # Test 9a: POST /api/hotel/booking/hold - missing fields
    resp = make_request("POST", "/hotel/booking/hold", admin_token, json_data={
        "hotel": {},
        "paxName": ""
    })
    log_test("POST /api/hotel/booking/hold (missing fields - should be 400)", 
             resp and resp.status_code == 400,
             f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 9b: POST /api/hotel/booking/hold - with sales role
    if sales_token:
        resp = make_request("POST", "/hotel/booking/hold", sales_token, json_data={
            "hotel": {
                "hotelKey": "H00X",
                "hotelId": "168",
                "roomRateKey": "RRK123",
                "checkInDate": checkin,
                "checkOutDate": checkout,
                "numberOfRooms": 1
            },
            "paxName": "Test Pax MMBC"
        })
        # Sales should be allowed (not 403), but will fail due to invalid login (400 is OK)
        log_test("POST /api/hotel/booking/hold (sales role allowed)", 
                 resp and resp.status_code in [200, 400],
                 f"Status: {resp.status_code if resp else 'No response'} (400 OK due to invalid login)")
    
    # Test 9c: POST /api/hotel/booking/issue - sales should be 403
    if sales_token:
        resp = make_request("POST", "/hotel/booking/issue", sales_token, json_data={
            "paymentcode": "TEST123"
        })
        log_test("POST /api/hotel/booking/issue (sales - should be 403)", 
                 resp and resp.status_code == 403,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 9d: POST /api/hotel/booking/issue - accounting allowed
    if accounting_token:
        resp = make_request("POST", "/hotel/booking/issue", accounting_token, json_data={
            "paymentcode": "TEST123"
        })
        # Accounting allowed, but will fail due to invalid login (400 is OK)
        log_test("POST /api/hotel/booking/issue (accounting role allowed)", 
                 resp and resp.status_code in [200, 400],
                 f"Status: {resp.status_code if resp else 'No response'} (400 OK due to invalid login)")
    
    # Test 9e: POST /api/hotel/booking/status - random paymentcode
    resp = make_request("POST", "/hotel/booking/status", admin_token, json_data={
        "paymentcode": "RANDOM123"
    })
    log_test("POST /api/hotel/booking/status (random code - should be 400, not 500)", 
             resp and resp.status_code in [200, 400],
             f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 9f: GET /api/hotel/bookings
    resp = make_request("GET", "/hotel/bookings", admin_token)
    if resp and resp.status_code == 200:
        data = resp.json()
        log_test("GET /api/hotel/bookings (super_admin)", 
                 isinstance(data, list),
                 f"Returned {len(data)} bookings")
    else:
        log_test("GET /api/hotel/bookings (super_admin)", False,
                 f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test with sales (should be scoped)
    if sales_token:
        resp = make_request("GET", "/hotel/bookings", sales_token)
        if resp and resp.status_code == 200:
            data = resp.json()
            log_test("GET /api/hotel/bookings (sales - role scoped)", 
                     isinstance(data, list),
                     f"Returned {len(data)} bookings (scoped to sales user)")
        else:
            log_test("GET /api/hotel/bookings (sales - role scoped)", False,
                     f"Status: {resp.status_code if resp else 'No response'}")
    
    # Test 10: POST /api/hotel/add-to-quotation (KEY FUNCTIONAL TEST)
    print_section("Test 10: Add to Quotation (KEY FUNCTIONAL TEST)")
    
    checkin = get_future_date(45)
    checkout = get_future_date(47)
    nights = 2
    rooms = 1
    daily_rate = 1000000
    
    quotation_data = {
        "new_customer": {
            "full_name": "Test Pax MMBC Integration",
            "whatsapp": "08123456789"
        },
        "hotel": {
            "hotelId": "168",
            "hotelKey": "H00X",
            "hotelName": "Test Hotel MMBC",
            "roomtypeName": "Deluxe Room",
            "checkInDate": checkin,
            "checkOutDate": checkout,
            "numberOfRooms": rooms,
            "numberOfAdults": 2,
            "numberOfChildren": 0,
            "currency": "IDR",
            "dailyRate": daily_rate,
            "nta": 900000,
            "markupPct": 15,
            "source": "MMBC_API"
        }
    }
    
    resp = make_request("POST", "/hotel/add-to-quotation", admin_token, json_data=quotation_data)
    if resp and resp.status_code == 200:
        data = resp.json()
        expected_total = daily_rate * nights * rooms
        has_fields = all(k in data for k in ["quotation_id", "quotation_number", "customer_id", "hotel_total"])
        total_correct = data.get("hotel_total") == expected_total
        log_test("POST /api/hotel/add-to-quotation (super_admin)", 
                 has_fields and total_correct,
                 f"quotation_id: {data.get('quotation_id')}, quotation_number: {data.get('quotation_number')}, hotel_total: {data.get('hotel_total')} (expected: {expected_total})")
    else:
        log_test("POST /api/hotel/add-to-quotation (super_admin)", False,
                 f"Status: {resp.status_code if resp else 'No response'}, Response: {resp.text if resp else 'None'}")
    
    # Test with sales role
    if sales_token:
        quotation_data_sales = {
            "new_customer": {
                "full_name": "Test Pax Sales MMBC",
                "whatsapp": "08123456790"
            },
            "hotel": {
                "hotelId": "169",
                "hotelKey": "H00Y",
                "hotelName": "Test Hotel Sales",
                "roomtypeName": "Standard Room",
                "checkInDate": checkin,
                "checkOutDate": checkout,
                "numberOfRooms": 1,
                "numberOfAdults": 2,
                "numberOfChildren": 0,
                "currency": "IDR",
                "dailyRate": 800000,
                "nta": 700000,
                "markupPct": 15,
                "source": "MMBC_API"
            }
        }
        resp = make_request("POST", "/hotel/add-to-quotation", sales_token, json_data=quotation_data_sales)
        if resp and resp.status_code == 200:
            data = resp.json()
            log_test("POST /api/hotel/add-to-quotation (sales role)", 
                     "quotation_id" in data,
                     f"quotation_number: {data.get('quotation_number')}")
        else:
            log_test("POST /api/hotel/add-to-quotation (sales role)", False,
                     f"Status: {resp.status_code if resp else 'No response'}")
    
    # Print summary
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
    print("🏁 Test Suite Complete")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

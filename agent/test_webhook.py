import hmac
import hashlib
import requests
import json
import sys

# Test configuration
URL = "http://localhost:8001/notify-deployment"
SECRET = "fc196c356797bef4049ea6129ca07a46df32c74ac7cbb8c1cd8cd2a1f587eb0d3"

def send_deployment_notification(secret: str, test_name: str, payload_data: dict, expected_status: list):
    """Sign and send payload indicating expected statuses."""
    print(f"\n--- Testing: {test_name} ---")
    
    # Generate Payload String
    payload_bytes = json.dumps(payload_data, separators=(',', ':')).encode('utf-8')
    
    # Generate signature
    signature = "sha256=" + hmac.new(
        secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'Content-Type': 'application/json',
        'X-Hub-Signature-256': signature
    }
    
    try:
        response = requests.post(URL, data=payload_bytes, headers=headers)
        
        if response.status_code in expected_status:
            print(f"✅ PASSED: Got expected status {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
        else:
            print(f"❌ FAILED: Expected {expected_status}, got {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ FAILED to send request: {e}")

if __name__ == "__main__":
    valid_payload = {
        "service": "api-gateway",
        "commit_sha": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
        "repository": "hitanshuthegr8/OpsTron",
        "environment": "production"
    }
    
    # Test 1: Valid Signature
    send_deployment_notification(SECRET, "Valid Signature", valid_payload, [200])
    
    # Test 2: Invalid Signature (using wrong secret)
    wrong_secret = "invalid_secret_123"
    send_deployment_notification(wrong_secret, "Invalid Signature", valid_payload, [401, 403])
    
    # Test 3: Missing Signature Header
    print(f"\n--- Testing: Missing Signature Header ---")
    response = requests.post(URL, json=valid_payload)
    if response.status_code in [401, 403]:
        print(f"✅ PASSED: Got expected status {response.status_code}")
    else:
        print(f"❌ FAILED: Expected 401/403, got {response.status_code}")

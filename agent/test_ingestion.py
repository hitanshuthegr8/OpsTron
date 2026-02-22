import requests
import json
import uuid

URL = "http://localhost:8001/agent/logs/ingest"

def test_ingestion():
    """Test the Docker agent log ingestion endpoint."""
    print("Sending mock logs to /agent/logs/ingest...")
    
    payload = {
        "container_id": str(uuid.uuid4())[:12],
        "container_name": "test-backend-api",
        "logs": "INFO: Starting application...\nWARNING: Connection slow\nERROR: Could not connect to database connection refused\nFATAL: Unhandled exception in main loop"
    }
    
    try:
        response = requests.post(URL, json=payload)
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("✅ Ingestion endpoint working correctly!")
        else:
            print("❌ Ingestion endpoint failed!")
    except Exception as e:
        print(f"❌ Server unreachable or error occurred: {e}")

if __name__ == "__main__":
    test_ingestion()

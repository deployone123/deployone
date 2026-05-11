import requests
import json

# Using the Nginx Proxy Manager hostname
API_URL = "http://answeb.deployone.test/run-playbook/"

payload = {
    "playbook_name": "hello_world.yml",
    "extra_vars": {
        "custom_message": "Hello from my local website via Nginx Proxy Manager!"
    }
}

print(f"Sending request to: {API_URL}")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(API_URL, json=payload)
    response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)

    result = response.json()
    print("\nAPI Response:")
    print(json.dumps(result, indent=2))

    if "stdout" in result:
        print("\nAnsible Playbook STDOUT:")
        print(result["stdout"])
    if "stderr" in result and result["stderr"]:
        print("\nAnsible Playbook STDERR:")
        print(result["stderr"])

except requests.exceptions.ConnectionError as e:
    # Correctly escaped newlines for print statements
    print(f"\nError: Could not connect to the API server at {API_URL}.")
    print("Please ensure:")
    print("1. The FastAPI app is running on the Ansible VM.")
    print("2. The Nginx Proxy Manager configuration for answeb.deployone.test is correct.")
    print(f"Details: {e}")
except requests.exceptions.RequestException as e:
    print(f"\nAn error occurred during the API request: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response status code: {e.response.status_code}")
        print(f"Response body: {e.response.text}")
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")
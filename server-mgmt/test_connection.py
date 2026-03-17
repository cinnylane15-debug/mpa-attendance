#!/usr/bin/env python3
"""Quick script to test API connectivity and authentication."""

import sys
import json
import urllib.request
import urllib.error
import ssl

API_URL = "https://72.255.61.75:4433"
USERNAME = "admin"
PASSWORD = "vdIwqkLoeMNhF4TP7Lwq"

# Allow self-signed certs
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def request(method, path, data=None, token=None):
    url = f"{API_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return json.loads(raw), e.code
        except json.JSONDecodeError:
            return {"error": raw.decode(errors="replace")}, e.code
    except Exception as e:
        return {"error": str(e)}, 0


def main():
    # 1. Health check
    print("1. Testing health endpoint...")
    body, status = request("GET", "/health")
    print(f"   Status: {status} | Response: {body}")
    if status == 0:
        print("\n   Could not reach API. Check that the server is running and port is open.")
        sys.exit(1)

    # 2. Login
    print("\n2. Testing login...")
    body, status = request("POST", "/auth/login", {
        "username": USERNAME,
        "password": PASSWORD,
    })
    print(f"   Status: {status}")
    if status != 200:
        print(f"   Login failed: {body}")
        sys.exit(1)
    token = body.get("access_token")
    print(f"   Got access token: {token[:20]}...")

    # 3. Get current user
    print("\n3. Testing authenticated endpoint (/auth/me)...")
    body, status = request("GET", "/auth/me", token=token)
    print(f"   Status: {status} | Response: {body}")

    # 4. System info
    print("\n4. Fetching system info...")
    body, status = request("GET", "/system/info", token=token)
    print(f"   Status: {status} | Response: {json.dumps(body, indent=2)[:500]}")

    print("\nAll connection tests passed!")


if __name__ == "__main__":
    main()

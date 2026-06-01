#!/usr/bin/env python3
"""
One-time script to obtain a Google OAuth2 refresh token for the Calendar API.
Works headlessly — prints a URL to open on any device, then asks for the redirect URL.

Usage:
    python scripts/get_google_token.py --client-id YOUR_ID --client-secret YOUR_SECRET

After authorising, your browser will redirect to http://localhost:8080 (which will fail
to load — that's expected). Copy the full URL from the address bar and paste it in.

Then add GOOGLE_REFRESH_TOKEN to your .env file.
"""

import argparse
import json
import urllib.parse
import urllib.request


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
REDIRECT_URI = "http://localhost:8080"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    args = parser.parse_args()

    params = urllib.parse.urlencode({
        "client_id": args.client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })
    url = f"{AUTH_URL}?{params}"

    print("\nOpen this URL in your browser and sign in:\n")
    print(url)
    print()
    print("After approving, your browser will redirect to http://localhost:8080")
    print("It will show 'This site can't be reached' — that's expected.")
    print("Copy the FULL URL from the address bar and paste it here.\n")

    redirect = input("Paste the full redirect URL here: ").strip()
    parsed = urllib.parse.urlparse(redirect)
    code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        print("Error — could not find 'code' in the URL:", redirect)
        return

    data = urllib.parse.urlencode({
        "code": code,
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        tokens = json.loads(resp.read())

    if "refresh_token" not in tokens:
        print("Error — no refresh token returned:")
        print(json.dumps(tokens, indent=2))
        return

    print("\nAdd this to your .env file:")
    print(f"\nGOOGLE_REFRESH_TOKEN={tokens['refresh_token']}\n")


if __name__ == "__main__":
    main()

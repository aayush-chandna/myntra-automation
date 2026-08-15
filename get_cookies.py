import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    try:
        # Connects to your running Chrome debug session
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        # Get all cookies from your logged-in session
        cookies = context.cookies()

        # Save them to myntra_cookies.json
        with open("myntra_cookies.json", "w") as f:
            json.dump(cookies, f, indent=2)

        print(" Success! myntra_cookies.json created.")
    except Exception as e:
        print(f" Error: Make sure Chrome is open on port 9222! Details: {e}")
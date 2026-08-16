"""
myntra_weekly_order.py
========================
Automated Order Service (Mon / Wed / Fri at 12:00 PM)
Navigates Myntra directly for Half-Sleeve Men's T-Shirts, sorted by rating,
filtered under Rs. 1000, and uses Gemini AI to select unseen top-rated items.
"""

import os
import sys
import json
import random
import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Robust import for the google-genai package
try:
    from google import genai
except ImportError:
    try:
        import google.genai as genai
    except ImportError:
        sys.exit(
            "\n[ERROR] Could not import google-genai SDK.\n"
            "Please run: pip install google-genai\n"
        )

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
HISTORY_FILE = Path(os.getenv("HISTORY_FILE_PATH", str(BASE_DIR / "purchased_history.json")))
COOKIE_FILE = BASE_DIR / "myntra_cookies.json"

MAX_PRICE = 1000  # Strictly less than Rs. 1000
PRIMARY_SIZE = "L"
SECONDARY_SIZE = "42"

# Myntra Catalog URL: Men's T-Shirts, Half Sleeve, Price <= 1000, Sorted by Rating
CATALOG_URL = (
    "https://www.myntra.com/men-tshirts"
    "?f=Gender%3Amen%2Cmen%20women%3ASleeve%3AHalf%20Sleeve%3APrice%3A0.0_1000.0_0.0_1000.0"
    "&sort=rating"
)

# Enforces execution strictly on Monday (0), Wednesday (2), and Friday (4)
ENFORCE_SCHEDULE_DAYS = False  

SEL = {
    "search_result_card": "li.product-base",
    "product_link": "a",
    "brand_name": "h3.product-brand",
    "product_title": "h4.product-product",
    "product_rating": "div.product-ratingsContainer",
    "size_out_of_stock_class": "size-buttons-out-of-stock",
    "add_to_bag_btn": "div.pdp-add-to-bag, button:has-text('ADD TO BAG')",
}


def verify_schedule_day():
    """Ensures execution occurs on Monday (0), Wednesday (2), or Friday (4)."""
    today_weekday = datetime.datetime.now().weekday()
    day_names = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
    current_day = day_names[today_weekday]

    print(f"📅 Today is {current_day}.")

    if ENFORCE_SCHEDULE_DAYS and today_weekday not in [0, 2, 4]:
        print("⏸️ Today is not a scheduled buying day (Mon/Wed/Fri). Exiting cleanly.")
        sys.exit(0)


def get_native_chrome_context(playwright):
    """
    Attempts to connect to local Chrome on port 9222 first.
    If unavailable (Cloud/GitHub Actions), launches Chromium under a virtual
    display (e.g. via xvfb-run) and injects saved cookies. Myntra's Akamai bot
    protection blocks headless=True outright regardless of cookie validity, so
    this must run non-headless with a DISPLAY available.
    """
    try:
        browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if len(browser.contexts) > 0 else browser.new_context()
        print("💻 Connected to local Chrome session on port 9222.")
        return browser, context
    except Exception:
        print("☁️ Port 9222 not found. Launching browser (virtual display) with saved cookies...")
        browser = playwright.chromium.launch(headless=False, args=["--no-sandbox"])
        context = browser.new_context()

        if COOKIE_FILE.exists():
            try:
                cookies = json.loads(COOKIE_FILE.read_text())
                context.add_cookies(cookies)
                print("🔑 Successfully injected session cookies into context.")
            except Exception as e:
                print(f"[WARN] Failed to load cookie file: {e}")
        else:
            print("[WARN] No myntra_cookies.json found! Running unauthenticated.")

        return browser, context


def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return {"purchased_products": []}


def save_history(history):
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def pick_best_product_with_ai(candidates, history):
    """Uses Gemini AI (google-genai SDK) to select the best unpurchased T-shirt."""
    recently_bought = history.get("purchased_products", [])

    prompt = f"""You are a personal fashion shopper evaluating live HALF-SLEEVE T-shirts on Myntra (Size L/42, Price < Rs. 1000).
Both polo collars and standard round/V-neck half-sleeve T-shirts are welcome.

CRITICAL INSTRUCTION:
Do NOT select any item that matches or looks identical/very similar to any previously purchased item listed below. Choose a DIFFERENT design, color, or style!

Previously Purchased Items (MUST AVOID REPEATING):
{json.dumps(recently_bought, indent=2)}

Available Unseen Live Options:
{json.dumps(candidates, indent=2)}

Respond STRICTLY with ONLY a JSON object containing the chosen item's index:
{{"chosen_index": 0}}"""

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key) if api_key else genai.Client()
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = resp.text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        return result.get("chosen_index", 0)
    except Exception as e:
        print(f"[WARN] AI decision engine error ({e}). Selecting a random candidate.")
        return random.randint(0, len(candidates) - 1)


def find_and_add_best_tshirt(context, page, history):
    print("\n🌐 Navigating to Myntra Half-Sleeve Men's T-Shirts (Sorted by Rating)...")
    page.goto(CATALOG_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    try:
        page.wait_for_selector(SEL["search_result_card"], timeout=10000)
        cards = page.locator(SEL["search_result_card"])
        total_found = cards.count()
        count = min(total_found, 20)
    except Exception:
        print(f"[FAIL] Could not load Myntra product listings. Page title: {page.title()!r}, URL: {page.url}")
        try:
            debug_path = BASE_DIR / "debug_catalog_failure.png"
            page.screenshot(path=str(debug_path))
            print(f"[DEBUG] Saved screenshot to {debug_path}")
        except Exception as shot_err:
            print(f"[DEBUG] Could not save screenshot: {shot_err}")
        return False, None

    raw_candidates = []
    purchased_titles = [p.get("title", "").lower().strip() for p in history.get("purchased_products", [])]

    print("📊 Scraping top-rated live products from Myntra...")
    for idx in range(count):
        card = cards.nth(idx)
        try:
            brand = card.locator(SEL["brand_name"]).first.inner_text().strip()
            title = card.locator(SEL["product_title"]).first.inner_text().strip()
            full_name = f"{brand} {title}".lower().strip()

            # Strict duplicate filtering against local history
            if any(p_title in full_name or full_name in p_title for p_title in purchased_titles if p_title):
                print(f"  [SKIP BOUGHT] Skipping [{brand}] {title}")
                continue
            
            rating = 0.0
            reviews = "0"
            if card.locator(SEL["product_rating"]).count() > 0:
                raw_text = card.locator(SEL["product_rating"]).first.inner_text()
                parts = [p.strip() for p in raw_text.split('\n') if p.strip()]
                if len(parts) >= 1:
                    try:
                        rating = float(parts[0])
                    except ValueError:
                        pass
                if len(parts) >= 2:
                    reviews = parts[1]

            raw_candidates.append({
                "index": idx,
                "brand": brand,
                "title": title,
                "rating": rating,
                "review_count": reviews
            })
        except Exception:
            continue

    if not raw_candidates:
        print("[FAIL] No new unpurchased candidates found on page 1.")
        return False, None

    # Pick the best candidate using AI
    chosen_idx = pick_best_product_with_ai(raw_candidates, history)
    chosen_item = raw_candidates[chosen_idx]
    print(f"\n⭐ AI Selected: [{chosen_item['brand']}] {chosen_item['title']}")
    print(f"   Rating: {chosen_item['rating']} ★ ({chosen_item['review_count']} reviews)")

    # Open Product Page & Validate
    card = cards.nth(chosen_item["index"])
    product_page = None
    try:
        with context.expect_page() as new_page_info:
            card.locator(SEL["product_link"]).first.click(timeout=5000)
        product_page = new_page_info.value
        product_page.wait_for_load_state("domcontentloaded")

        # Price verification
        price_text = product_page.locator("span.pdp-price strong").first.inner_text(timeout=4000)
        digits = "".join(c for c in price_text if c.isdigit())
        if digits and int(digits) >= MAX_PRICE:
            print(f"  [SKIP] Price Rs.{digits} exceeds limit Rs.{MAX_PRICE}")
            product_page.close()
            return False, None

        # Size L / 42 verification
        size_btn = product_page.locator(
            f"button.size-buttons-size-button:has-text('{PRIMARY_SIZE}'), "
            f"button.size-buttons-size-button:has-text('{SECONDARY_SIZE}')"
        ).first
        
        size_btn.wait_for(timeout=4000)
        if SEL["size_out_of_stock_class"] in (size_btn.get_attribute("class") or ""):
            print(f"  [SKIP] Size {PRIMARY_SIZE}/{SECONDARY_SIZE} out of stock.")
            product_page.close()
            return False, None

        size_btn.click()
        print(f"  [OK] Selected Size {PRIMARY_SIZE}/{SECONDARY_SIZE}")

        # Add item to bag
        product_page.locator(SEL["add_to_bag_btn"]).first.click(timeout=5000)
        product_page.wait_for_timeout(2000)
        print("  [OK] Item added to Bag successfully.")
        product_page.close()
        return True, chosen_item
    except Exception as e:
        print(f"  [ERROR] Page validation error: {e}")
        if product_page:
            product_page.close()
        return False, None


def verify_order_placed(page, bought_item):
    """
    Confirms the order actually completed by checking the real order history
    page, rather than trusting the checkout click sequence to have worked —
    Myntra's UI can silently no-op on an unexpected step (stale selector,
    extra items in cart, etc.) without raising an error.
    """
    print("Verifying order in order history...")
    page.goto("https://www.myntra.com/my/orders", wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(3000)
    text = page.inner_text("body")
    title_words = [w for w in bought_item["title"].split() if len(w) > 3]
    return bought_item["brand"] in text and any(w in text for w in title_words)


def execute_full_checkout(context, page, bought_item):
    print("\n🛒 Navigating to Cart...")
    page.goto("https://www.myntra.com/checkout/cart", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    print("Clicking Place Order...")
    place_order_btn = page.locator("button:has-text('PLACE ORDER'), div:has-text('PLACE ORDER')").last
    place_order_btn.wait_for(state="visible", timeout=10000)
    place_order_btn.click()
    page.wait_for_timeout(3000)

    checkout_page = context.pages[-1]
    checkout_page.bring_to_front()

    if "checkout/address" in checkout_page.url or "address" in checkout_page.url:
        print("Handling Address step...")
        checkout_page.wait_for_load_state("domcontentloaded")
        checkout_page.wait_for_timeout(3000)
        continue_btn = checkout_page.locator(
            "div.addressDesktop-continueBtn, button.address-continueButton, div:has-text('CONTINUE'), button:has-text('CONTINUE')"
        ).last
        continue_btn.wait_for(state="visible", timeout=10000)
        continue_btn.click()
        checkout_page.wait_for_timeout(4000)

    print("Selecting Cash on Delivery (COD)...")
    checkout_page.wait_for_load_state("domcontentloaded")
    checkout_page.wait_for_timeout(3000)

    cod_tab = checkout_page.locator("div:has-text('Cash On Delivery')").first
    if cod_tab.is_visible():
        cod_tab.click()
        checkout_page.wait_for_timeout(2000)

    cod_radio = checkout_page.locator("input[type='radio'], span[class*='radio'], div:has-text('Cash on Delivery (Cash/UPI)')").last
    if cod_radio.is_visible():
        cod_radio.click()
        checkout_page.wait_for_timeout(2000)

    print("Clicking final 'Place Order' button...")
    place_order_btn = checkout_page.locator("div.payment-desktop-placeOrderBtn button, #action-base button, button:has-text('Place Order')").last
    place_order_btn.scroll_into_view_if_needed()
    checkout_page.wait_for_timeout(1000)
    place_order_btn.click()
    checkout_page.wait_for_timeout(5000)

    return verify_order_placed(checkout_page, bought_item)


def run_automation():
    verify_schedule_day()
    history = load_history()

    with sync_playwright() as p:
        browser, context = get_native_chrome_context(p)
        page = context.new_page()

        added, bought_item = find_and_add_best_tshirt(context, page, history)

        if not added:
            print("[ABORT] Could not place order in this run.")
            return

        order_confirmed = False
        try:
            order_confirmed = execute_full_checkout(context, page, bought_item)
        except Exception as e:
            print(f"\n[INFO] Checkout status: {e}")

        if order_confirmed:
            print("\n🎉 Order Placed Successfully!")
            history["purchased_products"].append({
                "date": datetime.date.today().isoformat(),
                "brand": bought_item["brand"],
                "title": bought_item["title"],
                "rating": bought_item["rating"],
            })
            save_history(history)
        else:
            print("\n[FAIL] Could not verify the order in order history. Not marking as purchased.")

        print("\n" + "="*60)
        print("RUN COMPLETE: Order logged and finished.")
        print("="*60)


if __name__ == "__main__":
    run_automation()
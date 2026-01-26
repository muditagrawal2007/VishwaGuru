from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Mock API responses
    page.route("**/api/stats", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"total_issues": 150, "resolved_issues": 100, "pending_issues": 50, "issues_by_category": {"road": 50, "water": 30, "garbage": 20, "streetlight": 50}}'
    ))

    page.route("**/api/issues/recent", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='[]'
    ))

    page.route("**/api/responsibility-map", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{}'
    ))

    # Go to home
    try:
        page.goto("http://localhost:5173/")

        # Click on Community Impact (which is now a button)
        # The text is "Community Impact"
        # Since it might take time to load lazy components
        page.wait_for_selector("text=Community Impact")
        page.get_by_text("Community Impact").click()

        # Wait for StatsView to load
        expect(page.get_by_text("City Statistics")).to_be_visible()

        # Take screenshot
        page.screenshot(path="verification/stats_view.png")
        print("Screenshot taken: verification/stats_view.png")
    except Exception as e:
        print(f"Error: {e}")
        page.screenshot(path="verification/error.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

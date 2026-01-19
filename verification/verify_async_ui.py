import time
from playwright.sync_api import sync_playwright, expect

def run_dynamic(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Mutable state for mock
    responses = {
        "recent": '[]'
    }

    def handle_recent(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=responses["recent"]
        )

    page.route("**/api/issues/recent", handle_recent)

    page.route("**/api/issues", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body='{"id": 123, "message": "success", "action_plan": null}'
    ))

    # Mock detection status to avoid errors on home load if any
    page.route("**/api/ml-status", lambda route: route.fulfill(status=200, body='{"status":"ok"}'))

    print("Navigating...")
    page.goto("http://localhost:5173/report")

    print("Filling form...")
    page.fill('textarea', 'Test issue')
    page.click('button[type="submit"]')

    print("Waiting for Generating state...")
    expect(page.get_by_text("Generating Action Plan...")).to_be_visible(timeout=5000)
    page.screenshot(path="verification/generating_state.png")
    print("Generating state captured")

    # Change mock response to simulate completed AI task
    responses["recent"] = '[{"id": 123, "action_plan": {"whatsapp": "Hello", "email_subject": "Sub", "email_body": "Body", "x_post": "Tweet"}}]'

    print("Waiting for polling update...")
    expect(page.get_by_text("Action Plan Generated!")).to_be_visible(timeout=8000)
    page.screenshot(path="verification/done_state.png")
    print("Done state captured")

    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run_dynamic(playwright)

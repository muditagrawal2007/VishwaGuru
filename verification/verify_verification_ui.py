from playwright.sync_api import sync_playwright, expect
import time

def verify_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to home...")
        # Navigate to home
        try:
            page.goto("http://localhost:5173", timeout=60000)
        except Exception as e:
            print(f"Error navigating: {e}")
            return

        print("Waiting for Community Activity...")
        # Wait for "Recent Activity" or "No recent activity"
        # We expect data, so let's wait for an issue or the verify button
        try:
            page.get_by_text("Community Activity").wait_for(timeout=10000)
        except:
            print("Community Activity header not found")

        # Check if "Verify" button is visible
        # If DB is empty, this might fail.
        try:
            verify_btn = page.get_by_title("Verify Resolution").first
            verify_btn.wait_for(timeout=5000)
            print("Verify button found.")

            # Click verify
            verify_btn.click()
            print("Clicked verify.")

            # Wait for verify page
            page.wait_for_url("**/verify/*")
            print("Navigated to verify page.")

            # Check title
            expect(page.get_by_text("Verify Resolution")).to_be_visible()
            print("Verify Resolution header visible.")

            # Take screenshot
            page.screenshot(path="verification/verify_view.png")
            print("Screenshot taken.")

        except Exception as e:
            print(f"Verify button not found or other error: {e}")
            page.screenshot(path="verification/verify_view_failed.png")

        browser.close()

if __name__ == "__main__":
    verify_ui()

"""Drive a deployed site as a tester would: sign in, ask a question, file a report.

    python frontend/scripts/deployed_smoke.py https://your-site user userpassword

Needs `pip install playwright && playwright install chromium`.

Everything before this was reasoning about the deployment. This is the first check that
exercises the published frontend against a reachable backend, so it covers what only the
real pair can show: the cross-site session cookie surviving login, and no local-network
request on the way.

The answer check counts messages rather than searching the page for a word. "Student master
list" sits in the header, so a body-text check passes whether or not anything was answered
-- which is how the first version of this reported PASS while nothing had been asked.
"""

import sys

from playwright.sync_api import sync_playwright

SITE = sys.argv[1] if len(sys.argv) > 1 else "https://nia-assistant.vercel.app"
USERNAME = sys.argv[2] if len(sys.argv) > 2 else "user"
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "userpassword"
MARKER = sys.argv[4] if len(sys.argv) > 4 else "deployed-e2e"

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{(' :: ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    local_calls: list[str] = []
    page.on(
        "request",
        lambda r: local_calls.append(r.url)
        if ("localhost" in r.url or "127.0.0.1" in r.url)
        else None,
    )

    page.goto(SITE, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    check(
        "reached the sign-in screen",
        "Sign in" in body and "Opening the research desk" not in body,
    )
    check("no 'backend not configured' notice", "no backend configured" not in body)
    check("API reported connected", "API connected" in body)
    check("credentials shown to testers", PASSWORD in body)

    page.get_by_label("Username").fill(USERNAME)
    page.get_by_label("Password").fill(PASSWORD)
    page.get_by_role("button", name="Enter workspace").click()

    page.wait_for_selector("textarea", timeout=45000)
    check("signed in and reached the workspace", True)

    composer = page.locator("textarea").first
    composer.click()
    composer.type("How many students are recorded as deceased?", delay=15)
    page.keyboard.press("Enter")
    # Wait for the placeholder to be replaced, not merely for a message to appear. A message
    # shows the instant the question is sent -- "Understanding your request..." -- so counting
    # messages says the question was asked, never that it was answered.
    try:
        page.wait_for_function(
            """() => {
                const rows = document.querySelectorAll('.nia-message.is-assistant');
                if (!rows.length) return false;
                const text = rows[rows.length - 1].innerText;
                return /[0-9]/.test(text) && !/Understanding your request/i.test(text);
            }""",
            timeout=120000,
        )
        answer = page.locator(".nia-message.is-assistant").last.inner_text()
    except Exception:
        answer = "(never answered) last: " + page.locator(".nia-message.is-assistant").last.inner_text()
    answered = any(ch.isdigit() for ch in answer) and "understanding your request" not in answer.lower()
    check("a question was answered", answered, " ".join(answer.split())[:180])

    page.get_by_role("button", name="Report a problem").click()
    page.wait_for_selector("text=Report a problem", timeout=15000)
    page.get_by_label("Your name").fill("Deployed E2E")
    page.get_by_label("Comments").fill(f"{MARKER}: submitted from the deployed site")
    page.get_by_role("button", name="Submit report").click()
    page.wait_for_timeout(6000)
    check("report submitted", "your report was sent" in page.inner_text("body").lower())

    check(
        "never called the visitor's own machine",
        not local_calls,
        "; ".join(local_calls[:3]),
    )
    browser.close()

print("RESULT:", "PASS" if not failures else "FAIL -> " + "; ".join(failures))
sys.exit(1 if failures else 0)

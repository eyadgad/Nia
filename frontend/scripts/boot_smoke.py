"""Does the sign-in screen actually appear -- from a local origin, and from a public one?

Nothing else covers this. The unit tests never render the page, and curl cannot see it
either: `hydrated` starts false, so the server-rendered HTML is the splash whatever the
client goes on to do. A boot effect that returned early once skipped the only call that
sets `hydrated`, and the deployed build sat on "Opening the research desk..." forever while
every test stayed green.

Needs a running frontend and `pip install playwright && playwright install chromium`:

    python frontend/scripts/boot_smoke.py http://localhost:3000
    python frontend/scripts/boot_smoke.py http://nia.testing.invalid:3000

The second is the deployed shape and the one that matters: a public hostname mapped to the
local server, so window.location.hostname is not local while the API target still is. It
must reach the sign-in screen and say the backend is not configured, rather than hang or
claim a connection it does not have.
"""

import sys

from playwright.sync_api import sync_playwright

origin = sys.argv[1]
local_target = "localhost" in origin or origin.startswith("http://127.")

with sync_playwright() as playwright:
    # A non-local hostname pointed at the local server: window.location.hostname is public
    # while the connection is not, which is the deployed shape without needing a deployment.
    browser = playwright.chromium.launch(
        args=["--host-resolver-rules=MAP nia.testing.invalid 127.0.0.1"]
    )
    page = browser.new_page()
    prompts: list[str] = []
    page.on("console", lambda message: prompts.append(message.text))
    page.goto(origin, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(2500)

    body = page.inner_text("body")
    still_booting = "Opening the research desk" in body
    signed_out_screen = "Sign in" in body and "Still in testing" in body
    notice = "no backend configured" in body
    api_connected = "API connected" in body

    print(f"origin={origin}")
    print(f"  stuck on splash:      {still_booting}")
    print(f"  sign-in screen shown: {signed_out_screen}")
    print(f"  no-backend notice:    {notice}")
    print(f"  API connected shown:  {api_connected}")
    print(f"  credentials rendered: {'userpassword' in body}")

    failures = []
    if still_booting:
        failures.append("page never left the splash")
    if not signed_out_screen:
        failures.append("sign-in screen did not render")
    if local_target and not api_connected:
        failures.append("local origin should report the API connected")
    if not local_target and not notice:
        failures.append("non-local origin should say the backend is not configured")
    if not local_target and api_connected:
        failures.append("non-local origin must not claim the API is connected")

    browser.close()
    print("RESULT:", "PASS" if not failures else "FAIL " + "; ".join(failures))
    sys.exit(1 if failures else 0)

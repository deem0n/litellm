import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("phase", choices=("before", "after"))
parser.add_argument("--url", default="http://127.0.0.1:4002")
parser.add_argument("--chrome", required=True)
parser.add_argument("--output", type=Path, default=Path.cwd())
args = parser.parse_args()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=args.chrome, headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{args.url}/ui/login/", wait_until="networkidle")
    page.locator('input[name="username"]').fill(os.environ.get("UI_USERNAME", "admin"))
    page.locator('input[name="password"]').fill(os.environ["UI_PASSWORD"])
    with page.expect_response(
        lambda response: urlsplit(response.url).path == "/management/v1/users/me", timeout=30000
    ) as identity:
        page.get_by_role("button", name="Login", exact=True).click()
    page.wait_for_timeout(4000)
    print(json.dumps({"phase": args.phase, "url": page.url, "identity_status": identity.value.status}), flush=True)
    if args.phase == "before":
        page.wait_for_url("**/ui/login/**")
        assert identity.value.status == 404
        page.get_by_role("button", name="Login", exact=True).evaluate(
            "element => { element.style.outline = '3px solid red'; element.style.outlineOffset = '5px'; }"
        )
    else:
        assert identity.value.status == 200
        assert "/ui/login" not in page.url
        assert page.get_by_role("button", name="Login", exact=True).count() == 0
        with page.expect_response(
            lambda response: urlsplit(response.url).path == "/management/v1/users/me", timeout=30000
        ) as refreshed:
            page.reload(wait_until="networkidle")
        assert refreshed.value.status == 200
        assert "/ui/login" not in page.url
        print(json.dumps({"reload_url": page.url, "identity_status": refreshed.value.status}), flush=True)
        page.get_by_role("heading", name="Home", exact=True).first.evaluate(
            "element => { element.style.outline = '3px solid red'; element.style.outlineOffset = '5px'; }"
        )
    page.screenshot(path=str(args.output / f"login-{args.phase}.png"))
    browser.close()

#!/usr/bin/env python3
"""
GSC authenticated session setup (LOCAL ONLY)

Run this on your own computer, not in GitHub Actions.

1. Installs/uses Playwright Chromium.
2. Opens the GSC login page.
3. YOU log in manually.
4. Press Enter in the terminal after login succeeds.
5. The script saves Playwright storage state to:
   gsc-auth.json

Do not commit gsc-auth.json to GitHub.
"""
from pathlib import Path
import asyncio

AUTH = Path("gsc-auth.json")
LOGIN_URL = "https://epaymentwebapp.gsc.com.my/login"

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1440, "height": 1000})
        page = await context.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
        print("\\nLog in to GSC manually in the browser window.")
        input("When you are fully logged in, return here and press Enter...")
        await context.storage_state(path=str(AUTH))
        print(f"Saved authenticated browser state to {AUTH.resolve()}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

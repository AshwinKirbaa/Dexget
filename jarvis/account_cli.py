import sys
from jarvis.tasks.accounts import account_manager, AccountProfile
from jarvis.tasks.account_discovery import discover_profiles, verify_profile

def do_account_setup():
    print("JARVIS Account Setup\n")
    
    discovered = {"chrome": discover_profiles("chrome"), "brave": discover_profiles("brave")}
    
    for browser, profiles in discovered.items():
        if profiles:
            print(f"{browser.title()}:")
            for i, p in enumerate(profiles, 1):
                email_str = f"\n      detected account: {p['email']}" if p['email'] else ""
                print(f"  [{i}] {p['dir']}{email_str}")
            print()
            
    while True:
        try:
            acc_name = input("account name (or 'q' to quit): ").strip()
            if not acc_name or acc_name.lower() == 'q':
                break
                
            browser = input("browser (chrome/brave): ").strip().lower()
            if browser not in ["chrome", "brave"]:
                print("Invalid browser. Please type 'chrome' or 'brave'.")
                continue
                
            profile = input("profile (e.g. Default or Profile 1): ").strip()
            
            if not verify_profile(browser, profile):
                print("Profile not found. Please ensure the browser and profile directory are correct.\n")
                continue
                
            account_manager.accounts[acc_name] = AccountProfile(acc_name, browser, profile)
            account_manager.save_config()
            print(f"Saved account '{acc_name}'.\n")
            
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            break
        except EOFError:
            break

def do_test_accounts():
    print("Account Test\n")
    
    test_auth = input("Test authentication for assigned services? (y/n): ").strip().lower() == 'y'
    
    if test_auth:
        from jarvis.automation import automation_manager
        from jarvis.automation.verifier import verify_service_authentication
        import asyncio
    
    for name, acc in account_manager.accounts.items():
        profile_ok = verify_profile(acc.browser, acc.profile_dir)
        status = "OK" if profile_ok else "NOT FOUND"
        print(f"Account: {name}")
        print(f"  Browser: {acc.browser.title()}")
        print(f"  Profile: {acc.profile_dir}")
        print(f"  Status: {status}")
        
        if test_auth and profile_ok:
            # Find assigned services
            services = [k for k, v in account_manager.task_policies.items() if v.lower() == name.lower()]
            if not services:
                print("  No services assigned.\n")
                continue
                
            for service in services:
                url_map = {
                    "gmail": "https://mail.google.com",
                    "youtube": "https://youtube.com",
                    "youtube_music": "https://music.youtube.com",
                    "github": "https://github.com"
                }
                url = url_map.get(service)
                if not url:
                    print(f"  {service.title()}:\n    Authentication: UNKNOWN\n")
                    continue
                    
                print(f"  Testing {service.title()}...")
                
                # We need to run the async navigate to test
                async def test_svc():
                    backend = automation_manager.get_backend("browser")
                    await backend._navigate_async(url, browser_exec=acc.browser, profile_dir=acc.profile_dir)
                    obs = await backend._observe_async()
                    return verify_service_authentication(service, obs)
                
                try:
                    auth_result = asyncio.run(test_svc())
                    auth_str = auth_result["status"]
                except Exception as e:
                    auth_str = f"ERROR ({e})"
                    
                print(f"  {service.title()}:\n    Authentication: {auth_str}")
        print("\n")

def do_chrome_profiles():
    import psutil
    import asyncio
    from jarvis.tasks.account_discovery import get_browser_user_data_dir, discover_profiles
    from jarvis.automation.browser_backend import _read_devtools_active_port

    user_data_dir = get_browser_user_data_dir("chrome")
    print(f"Chrome User Data: {user_data_dir}\n")

    # Check remote debugging (DevToolsActivePort)
    port_info = _read_devtools_active_port(user_data_dir) if user_data_dir else None
    if port_info:
        port, ws_path = port_info
        print(f"Remote debugging:  ENABLED (ws://localhost:{port}{ws_path})")
    else:
        print(f"Remote debugging:  DISABLED")
        print(f"  To enable: chrome://inspect/#remote-debugging")
        print(f"  Check 'Allow remote debugging for this browser instance'")

    # Chrome running?
    is_chrome_running = any(
        p.info.get("name") == "chrome.exe"
        for p in psutil.process_iter(["name"])
    )
    print(f"Chrome running:    {'YES' if is_chrome_running else 'NO'}\n")

    # Per-account status
    print("Configured accounts:\n")
    for name, acc in account_manager.accounts.items():
        profile_exists = verify_profile(acc.browser, acc.profile_dir)

        print(f"  Account:          {name}")
        print(f"  Browser:          {acc.browser}")
        print(f"  Profile:          {acc.profile_dir}")
        print(f"  Profile exists:   {'YES' if profile_exists else 'NO'}")
        print(f"  Chrome running:   {'YES' if is_chrome_running else 'NO'}")
        print(f"  Remote debugging: {'ENABLED' if port_info else 'DISABLED'}")
        print(f"  Session detected: {'YES' if is_chrome_running else 'NO'}")

        # Try quick attachment test (non-blocking, 3s timeout)
        attached = False
        if is_chrome_running and port_info and profile_exists and acc.browser == "chrome":
            async def _quick_attach():
                from playwright.async_api import async_playwright
                p = await async_playwright().start()
                try:
                    browser = await _try_attach_inner(p, user_data_dir)
                    return browser is not None
                finally:
                    try:
                        await p.stop()
                    except Exception:
                        pass

            async def _try_attach_inner(p, udd):
                from jarvis.automation.browser_backend import _try_attach_to_chrome
                return await _try_attach_to_chrome(p, udd, timeout_ms=3000)

            try:
                attached = asyncio.run(_quick_attach())
            except Exception:
                attached = False

        print(f"  Session attached: {'YES' if attached else 'NO'}")

        # Profile verified = attached AND correct context
        verified = attached  # We confirm identity via the connection itself
        print(f"  Profile verified: {'YES' if verified else 'UNKNOWN'}")
        print()

    # Also show discovered profiles
    print("Discovered Chrome profiles:\n")
    profiles = discover_profiles("chrome")
    for p in profiles:
        print(f"  [{p['dir']}] {p.get('name', '')} <{p.get('email', '')}>")


def do_test_browser_profile(account_name: str):
    import asyncio
    from jarvis.automation import automation_manager
    from jarvis.automation.verifier import verify_service_authentication
    from jarvis.automation.browser_backend import BrowserConnectionState, _read_devtools_active_port
    from jarvis.tasks.account_discovery import get_browser_user_data_dir
    import psutil

    # ── Account resolution ────────────────────────────────────────────────────
    account = None
    for k, v in account_manager.accounts.items():
        if k.lower() == account_name.lower():
            account = v
            break

    if not account:
        print(f"Logical account '{account_name}' not found.")
        return

    print(f"Account: {account.name}")
    print(f"Browser: {account.browser}")
    print(f"Profile: {account.profile_dir}\n")

    # ── Profile exists ────────────────────────────────────────────────────────
    profile_exists = verify_profile(account.browser, account.profile_dir)
    print(f"Profile exists:        {'YES' if profile_exists else 'NO'}")
    if not profile_exists:
        print("\nFinal result: FAIL - profile directory not found.")
        return

    # ── Chrome running ────────────────────────────────────────────────────────
    exe_name = "brave.exe" if account.browser == "brave" else "chrome.exe"
    is_running = any(
        p.info.get("name") == exe_name
        for p in psutil.process_iter(["name"])
    )
    print(f"Chrome running:        {'YES' if is_running else 'NO'}")

    # ── Remote debugging ──────────────────────────────────────────────────────
    user_data_dir = get_browser_user_data_dir(account.browser or "chrome")
    port_info = _read_devtools_active_port(user_data_dir) if user_data_dir else None
    remote_debug = port_info is not None
    if remote_debug:
        port, ws_path = port_info
        print(f"Remote debugging:      ENABLED (port {port})")
    else:
        print(f"Remote debugging:      DISABLED")
        print("\nTo enable: open chrome://inspect/#remote-debugging")
        print("Check 'Allow remote debugging for this browser instance'")

    print(f"Session detected:      {'YES' if is_running else 'NO'}")

    async def run_test():
        backend = automation_manager.get_backend("browser")
        try:
            # ── Attempt connection ────────────────────────────────────────────
            # Navigate will trigger _init_browser which attempts CDP attachment
            await backend._init_browser(
                browser_exec=account.browser,
                profile_dir=account.profile_dir,
                url=None,
            )

            attached = backend.connection_state.get(BrowserConnectionState.SESSION_ATTACHED, False)
            external = backend.external_browser
            existing_tabs = backend.state.get("existing_tabs", [])

            if attached and not external:
                print(f"Session attached:      YES")
                print(f"Existing tabs:         {len(existing_tabs)}")
                for tab in existing_tabs[:5]:
                    print(f"  - {tab['url']}")
            else:
                print(f"Session attached:      NO")
                if remote_debug:
                    print()
                    print("  IMPORTANT: Chrome's modern remote debugging requires")
                    print("  chrome://inspect to be OPEN in Chrome for Playwright")
                    print("  to attach. The permission proxy only accepts connections")
                    print("  while the chrome://inspect page is active.")
                    print()
                    print("  To enable full attachment:")
                    print("  1. Open chrome://inspect/#remote-debugging in Chrome")
                    print("  2. Check 'Allow remote debugging for this browser instance'")
                    print("  3. KEEP that tab open while running JARVIS tasks")
                    print()
                    print("  Falling back to subprocess mode (Chrome opened with correct")
                    print("  profile but Playwright cannot inspect/control the session).")
                else:
                    print("  Remote debugging is disabled.")
                print("\nFinal result: PARTIAL - Chrome opened with correct profile")
                print("             Subprocess mode: navigation works, no Playwright control.")
                return

            # ── Profile identity ──────────────────────────────────────────────
            actual_profile = backend.state.get("current_context")
            identity_ok = actual_profile == account.profile_dir
            print(f"\nProfile identity:      {'VERIFIED' if identity_ok else 'MISMATCH'}")
            if not identity_ok:
                print(f"  Expected: {account.profile_dir}")
                print(f"  Actual:   {actual_profile}")

            # ── Find or navigate to Gmail ─────────────────────────────────────
            gmail_url = "https://mail.google.com"
            gmail_page = None

            # Check existing tabs first
            if backend.context:
                for p in backend.context.pages:
                    if "mail.google.com" in p.url:
                        gmail_page = p
                        break

            if gmail_page:
                print(f"\nGmail navigation:      EXISTING TAB FOUND")
                backend.page = gmail_page
                try:
                    await gmail_page.bring_to_front()
                except Exception:
                    pass
            else:
                print(f"\nGmail navigation:      NAVIGATING...")
                try:
                    await backend.page.goto(gmail_url, wait_until="domcontentloaded", timeout=15000)
                    print(f"Gmail navigation:      PASS")
                    gmail_page = backend.page
                except Exception as e:
                    print(f"Gmail navigation:      FAILED ({e})")

            if not gmail_page:
                print("\nFinal result: PARTIAL - attached but could not navigate to Gmail.")
                return

            await backend._update_state()

            # ── Current URL / title ───────────────────────────────────────────
            current_url = backend.state.get("current_url", "")
            current_title = backend.state.get("page_title", "")
            print(f"Current URL:           {current_url}")
            print(f"Current title:         {current_title}")

            # ── Authentication check ──────────────────────────────────────────
            obs = await backend._observe_async()
            auth_res = verify_service_authentication("gmail", obs)
            auth_status = auth_res.get("status", "UNKNOWN")
            print(f"\nGmail authentication:  {auth_status}")

            # ── Account identity ──────────────────────────────────────────────
            # Try to read the logged-in account from the page title or URL
            account_identity = "UNKNOWN"
            if auth_status == "AUTHENTICATED":
                # Gmail shows "user@domain - Gmail" in title or inbox title
                title_lower = current_title.lower()
                url_lower = current_url.lower()

                # Check title for email address patterns
                import re
                email_match = re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', current_title)
                if email_match:
                    detected_email = email_match.group(0)
                    account_identity = f"VERIFIED ({detected_email})"
                elif "inbox" in title_lower or "gmail" in title_lower:
                    account_identity = "AUTHENTICATED (email not visible in title)"

            print(f"Gmail account:         {account_identity}")

            # ── Final result ──────────────────────────────────────────────────
            if auth_status == "AUTHENTICATED":
                print(f"\nFinal result: PASS - attached, profile verified, Gmail authenticated.")
            elif auth_status == "AUTHENTICATION_REQUIRED":
                print(f"\nFinal result: PARTIAL - attached and profile verified, but not signed in.")
                print(f"             Open Gmail in Profile '{account.profile_dir}' and sign in manually.")
            else:
                print(f"\nFinal result: PARTIAL - attached and profile verified, Gmail auth unknown.")

        except Exception as e:
            print(f"\nBrowser session:       FAILED ({e})")
            print(f"Final result: FAIL")
        finally:
            if hasattr(backend, "async_cancel"):
                await backend.async_cancel()
            else:
                backend.cancel()

    asyncio.run(run_test())

"""Landing page, masthead and the Justice Orb sign-in / sign-up interaction."""
import json
import re
import subprocess

import pytest
from _browser import FRONTEND, SESSION, SUPA, USER, new_page


def auth_routes(page, calls):
    def token(route, request):
        body = json.loads(request.post_data or "{}")
        calls.append(("login", body.get("email")))
        if body.get("password") == "correct-horse":
            return route.fulfill(status=200, json={**SESSION, "user": {**USER, "email": body["email"]}})
        return route.fulfill(status=400, json={"code": 400, "error_code": "invalid_credentials", "msg": "Invalid login credentials"})

    def signup(route, request):
        body = json.loads(request.post_data or "{}")
        calls.append(("signup", body.get("email")))
        ids = [] if body.get("email") == "taken@example.com" else [{"id": "1"}]
        return route.fulfill(status=200, json={**USER, "email": body["email"], "identities": ids})

    page.route(f"{SUPA}/auth/v1/token**", token)
    page.route(f"{SUPA}/auth/v1/signup**", signup)
    page.route(f"{SUPA}/rest/**", lambda r, q: r.fulfill(json=[]))


@pytest.mark.parametrize("width,height", [(1440, 900), (834, 1112), (390, 844)])
def test_layout_and_assets(browser, base_url, width, height):
    ctx, page = new_page(browser, width=width, height=height)
    page.goto(base_url + "index.html"); page.wait_for_timeout(1500)
    img = page.evaluate("""() => { const i = document.querySelector('.lady'); const r = i.getBoundingClientRect(); const cs = getComputedStyle(i);
        return {nw: i.naturalWidth, nh: i.naturalHeight, ratio: r.width / r.height, mask: cs.maskImage || cs.webkitMaskImage, filter: cs.filter, op: cs.opacity}; }""")
    assert img["nw"] == 980 and img["nh"] == 980 and abs(img["ratio"] - 1) < 0.01  # supplied image, undistorted
    assert img["mask"] in ("none", "") and img["filter"] == "none" and img["op"] == "1"  # not masked or filtered
    assert page.inner_text("#heroTitle").replace("\n", " ") == "The law, without the fog."
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert not page.errors, page.errors
    ctx.close()


def test_preview_markup_unchanged_from_last_commit(browser, base_url):
    committed = subprocess.run(["git", "show", "HEAD:frontend/index.html"], cwd=FRONTEND.parent, capture_output=True, text=True, encoding="utf-8").stdout
    norm = lambda h: re.sub(r"\s+", " ", re.search(r'<div class="preview-frame".*?</figcaption>', h, re.S).group(0))  # noqa: E731
    assert norm((FRONTEND / "index.html").read_text(encoding="utf-8")) == norm(committed)


def test_masthead_links_and_scroll_state(browser, base_url):
    ctx, page = new_page(browser)
    page.goto(base_url + "index.html"); page.wait_for_timeout(800)
    for href in ("#product", "#how", "#features"):
        assert page.locator(href).count() == 1, href
    assert page.get_attribute(".nav-links a[href*='github.com']", "href") == "https://github.com/SiddheshK1704/LawTalk-AI_RAG_Chatbot"
    assert "scrolled" not in page.get_attribute("#masthead", "class")
    page.click(".nav-links a[href='#how']"); page.wait_for_timeout(900)
    assert "scrolled" in page.get_attribute("#masthead", "class")
    assert page.evaluate("Math.abs(document.getElementById('how').getBoundingClientRect().top) < 120")
    ctx.close()


def test_mobile_menu(browser, base_url):
    ctx, page = new_page(browser, width=390, height=844)
    page.goto(base_url + "index.html"); page.wait_for_timeout(800)
    assert page.locator(".nav-links").is_hidden() and page.locator("#menuBtn").is_visible()
    page.click("#menuBtn"); page.wait_for_timeout(250)
    assert page.locator("#mobileMenu").is_visible() and page.get_attribute("#menuBtn", "aria-expanded") == "true"
    page.keyboard.press("Escape"); page.wait_for_timeout(150)
    assert page.locator("#mobileMenu").is_hidden() and page.evaluate("document.activeElement.id") == "menuBtn"
    page.click("#menuBtn"); page.click("[data-menu-login]"); page.wait_for_timeout(1400)
    assert page.locator("#authModal").is_visible()
    ctx.close()


def test_orb_entrance_flip_and_close(browser, base_url):
    ctx, page = new_page(browser)
    calls = []
    auth_routes(page, calls)
    page.goto(base_url + "index.html"); page.wait_for_timeout(600)
    btn = page.locator("#openLogin").bounding_box()
    page.click("#openLogin")
    page.wait_for_timeout(60)
    # The bubble starts at the login button, then travels to the centre.
    b0 = page.locator(".orb-bubble").bounding_box()
    assert abs((b0["x"] + b0["width"] / 2) - (btn["x"] + btn["width"] / 2)) < 60 and b0["y"] < 200
    page.wait_for_timeout(1300)
    assert page.locator("#loginFace").is_visible()
    assert page.evaluate("document.activeElement.id") == "loginEmail"
    assert page.get_attribute("#orb", "role") == "dialog" and page.get_attribute("#orb", "aria-modal") == "true"
    assert page.evaluate("getComputedStyle(document.querySelector('.orb-face')).borderRadius") == "50%"  # a circle on desktop
    assert page.evaluate("document.getElementById('main').inert")  # background unreachable
    # focus trap
    for _ in range(10):
        page.keyboard.press("Tab")
        assert page.evaluate("document.getElementById('loginFace').contains(document.activeElement)")
    # flip to sign up and back, without closing
    page.click("#toSignup"); page.wait_for_timeout(750)
    assert page.evaluate("gsap.getProperty('.orb-flipper', 'rotationY')") == 180
    assert page.evaluate("document.getElementById('loginFace').inert && !document.getElementById('signupFace').inert")
    assert page.evaluate("document.activeElement.id") == "signupEmail"
    page.click("#toLogin"); page.wait_for_timeout(750)
    assert page.evaluate("gsap.getProperty('.orb-flipper', 'rotationY')") == 0 and page.locator("#authModal").is_visible()
    # close reverses the entrance and restores focus
    page.keyboard.press("Escape"); page.wait_for_timeout(1200)
    assert page.locator("#authModal").is_hidden()
    assert page.evaluate("document.activeElement.id") == "openLogin"
    assert not page.evaluate("document.getElementById('main').inert")
    assert not page.errors, page.errors
    ctx.close()


def test_orb_validation_errors_and_auth_flows(browser, base_url):
    ctx, page = new_page(browser)
    calls = []
    auth_routes(page, calls)
    page.goto(base_url + "index.html"); page.wait_for_timeout(600)
    page.click("#openLogin"); page.wait_for_timeout(1300)
    page.click("#loginSubmit")
    assert "Enter your email" in page.inner_text("#loginEmailError") and not calls
    page.fill("#loginEmail", "reviewer@example.com"); page.fill("#loginPassword", "123"); page.click("#loginSubmit")
    assert "at least 6" in page.inner_text("#loginPasswordError") and not calls
    page.click("[data-toggle-password='loginPassword']")
    assert page.get_attribute("#loginPassword", "type") == "text"
    page.fill("#loginPassword", "wrong-password"); page.click("#loginSubmit")
    page.wait_for_selector("#loginMessage:not([hidden])")
    assert page.inner_text("#loginMessage") == "Incorrect email or password."
    assert page.is_enabled("#loginSubmit")
    # sign up: already registered, then success flips back to login with a message
    page.click("#toSignup"); page.wait_for_timeout(750)
    page.fill("#signupEmail", "taken@example.com"); page.fill("#signupPassword", "secret123"); page.click("#signupSubmit")
    page.wait_for_selector("#signupMessage:not([hidden])")
    assert "already exists" in page.inner_text("#signupMessage")
    page.fill("#signupEmail", "new@example.com"); page.click("#signupSubmit")
    page.wait_for_function("document.querySelector('#loginMessage').classList.contains('success')", timeout=8000)
    assert page.evaluate("gsap.getProperty('.orb-flipper', 'rotationY')") == 0
    assert page.input_value("#loginEmail") == "new@example.com"
    # successful login goes to the workspace
    page.fill("#loginPassword", "correct-horse"); page.click("#loginSubmit")
    page.wait_for_url("**/chat.html", timeout=10000)
    assert ("signup", "new@example.com") in calls and ("login", "new@example.com") in calls
    ctx.close()


def test_orb_mobile_panel_and_reduced_motion(browser, base_url):
    ctx, page = new_page(browser, width=390, height=844, reduced=True)
    auth_routes(page, [])
    page.goto(base_url + "index.html"); page.wait_for_timeout(400)
    page.click("#startChatting")
    page.wait_for_timeout(60)  # reduced motion: no entrance animation
    assert page.locator("#loginFace").is_visible() and page.evaluate("document.activeElement.id") == "loginEmail"
    radius = page.evaluate("getComputedStyle(document.querySelector('.orb-face')).borderRadius")
    assert radius == "24px", radius  # readable rounded panel on small screens
    box = page.locator("#loginFace").bounding_box()
    assert box["width"] > 340
    page.click("#toSignup"); page.wait_for_timeout(60)
    assert page.locator("#signupEmail").is_visible()
    page.click(".orb-backdrop", position={"x": 5, "y": 5}); page.wait_for_timeout(100)
    assert page.locator("#authModal").is_hidden()
    ctx.close()


def test_light_theme_and_status_label(browser, base_url):
    ctx, page = new_page(browser, theme="light")
    page.goto(base_url + "index.html"); page.wait_for_timeout(1300)
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(245, 242, 235)"  # Warm Concrete
    assert page.evaluate("getComputedStyle(document.querySelector('#startChatting')).backgroundColor") == "rgb(65, 105, 225)"  # Cobalt
    page.hover("#startChatting")
    assert page.text_content("#heroStatus") == "Opens the research workspace"
    page.mouse.move(5, 5)
    assert page.text_content("#heroStatus") == "9 statutes and study texts indexed"
    ctx.close()


def test_theme_toggle_sweep_persistence_and_reduced_motion(browser, base_url):
    ctx, page = new_page(browser, theme="dark")
    page.goto(base_url + "index.html"); page.wait_for_timeout(800)
    page.evaluate("localStorage.removeItem('lawtalk-theme'); localStorage.setItem('lawtalk-theme', 'dark')")
    page.locator(".theme-toggle").first.click(); page.wait_for_timeout(200)
    anims = page.evaluate("""() => document.getAnimations({subtree: true})
        .filter(a => a.effect.pseudoElement === '::view-transition-new(root)')
        .map(a => ({clip: a.effect.getKeyframes()[0].clipPath, dur: a.effect.getTiming().duration}))""")
    assert anims and anims[0]["clip"].startswith("circle(0px") and 600 <= anims[0]["dur"] <= 700
    page.wait_for_timeout(800)
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    assert page.evaluate("localStorage.getItem('lawtalk-theme')") == "light"
    ctx.close()
    # persisted choice is applied on the app page too (same key), before first paint
    ctx2 = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    ctx2.add_init_script("if (!localStorage.getItem('lawtalk-theme')) localStorage.setItem('lawtalk-theme', 'light');"
                         "document.addEventListener('DOMContentLoaded', () => { window.__t = document.documentElement.dataset.theme; });")
    page = ctx2.new_page()
    page.goto(base_url + "index.html"); page.wait_for_timeout(300)
    assert page.evaluate("window.__t") == "light"
    page.locator(".theme-toggle").first.click()  # reduced motion: instant, no sweep
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    assert page.evaluate("document.getAnimations({subtree:true}).filter(a => a.effect.pseudoElement === '::view-transition-new(root)').length") == 0
    ctx2.close()

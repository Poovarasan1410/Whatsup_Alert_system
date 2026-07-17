import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from playwright.sync_api import sync_playwright

LISTING_URL = "https://tg10x.com/explore/startup-founders/india"
BASE_URL = "https://tg10x.com"
STATE_FILE = Path("seen_items.json")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def clean_text(value: str) -> str:
    """Remove extra spaces and blank lines."""
    lines: list[str] = []

    for line in value.splitlines():
        cleaned = " ".join(line.split())

        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines)


def shorten_text(value: str, limit: int = 500) -> str:
    """Shorten long text while keeping complete words."""
    value = clean_text(value)

    if len(value) <= limit:
        return value

    shortened = value[:limit].rsplit(" ", 1)[0]
    return shortened + "..."


def escape_html(value: str) -> str:
    """Escape characters used by Telegram HTML formatting."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def create_browser_page(playwright):
    """Create a Playwright browser and page."""
    browser = playwright.chromium.launch(headless=True)

    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 1200,
        },
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    )

    return browser, page


def fetch_founder_urls() -> list[str]:
    """Collect startup founder profile URLs from the TG10X listing page."""
    with sync_playwright() as playwright:
        browser, page = create_browser_page(playwright)

        try:
            page.goto(
                LISTING_URL,
                wait_until="networkidle",
                timeout=90000,
            )

            page.wait_for_timeout(5000)

            # Scroll several times in case profiles are loaded lazily.
            for _ in range(6):
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(1200)

            links = page.locator('a[href^="/u/"]').evaluate_all(
                """
                elements => elements.map(element => element.href)
                """
            )

        finally:
            browser.close()

    unique_urls: list[str] = []
    seen: set[str] = set()

    for link in links:
        profile_url = urljoin(BASE_URL, link).split("?")[0].rstrip("/")

        if profile_url not in seen:
            seen.add(profile_url)
            unique_urls.append(profile_url)

    return unique_urls


def get_first_text(page, selectors: list[str]) -> str:
    """Return the first useful text found from a list of selectors."""
    for selector in selectors:
        locator = page.locator(selector).first

        if locator.count() == 0:
            continue

        try:
            value = clean_text(locator.inner_text())

            if value:
                return value

        except Exception:
            continue

    return ""


def get_social_link(page, domain: str) -> str:
    """Return the first external social-media link matching a domain."""
    locator = page.locator(f'a[href*="{domain}"]').first

    if locator.count() == 0:
        return ""

    try:
        return locator.get_attribute("href") or ""
    except Exception:
        return ""


def extract_field(body_text: str, label: str) -> str:
    """Extract the line immediately following a profile field label."""
    pattern = rf"{re.escape(label)}\s*\n\s*([^\n]+)"
    match = re.search(pattern, body_text, re.IGNORECASE)

    if not match:
        return ""

    value = clean_text(match.group(1))

    excluded_values = {
        "startup details",
        "reviews & testimonials",
        "profile highlights",
        "organizations",
        "quick info",
    }

    if value.lower() in excluded_values:
        return ""

    return value


def extract_location(body_text: str) -> str:
    """Extract a useful location from the profile page."""
    location_patterns = [
        r"([A-Za-z][A-Za-z .'-]+,\s*[A-Za-z][A-Za-z .'-]+,\s*Telangana(?:,\s*\d{6})?)",
        r"([A-Za-z][A-Za-z .'-]+,\s*Telangana(?:,\s*\d{6})?)",
    ]

    for pattern in location_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)

        if match:
            return clean_text(match.group(1))

    if re.search(r"\bTelangana\b", body_text, re.IGNORECASE):
        return "Telangana"

    return ""


def extract_organization(page, body_text: str) -> str:
    """Extract the founder's organization."""
    selectors = [
        'text="Organizations" >> xpath=following::*[1]',
        '[class*="organization"]',
        '[class*="company"]',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first

            if locator.count() > 0:
                candidate = clean_text(locator.inner_text())

                if (
                    candidate
                    and candidate.lower() not in {"startup", "organizations"}
                    and len(candidate) < 150
                ):
                    return candidate
        except Exception:
            continue

    match = re.search(
        r"Organizations?\s*\n\s*([^\n]+)",
        body_text,
        re.IGNORECASE,
    )

    if match:
        candidate = clean_text(match.group(1))

        if candidate.lower() not in {"startup", "organizations"}:
            return candidate

    return ""


def extract_summary(page, name: str, body_text: str) -> str:
    """Extract only the short founder description."""
    summary_selectors = [
        "h1 + p",
        "main h1 ~ p",
        "header p",
        "main section p",
    ]

    for selector in summary_selectors:
        locator = page.locator(selector).first

        if locator.count() == 0:
            continue

        try:
            candidate = clean_text(locator.inner_text())

            if 30 <= len(candidate) <= 700:
                return shorten_text(candidate, 500)

        except Exception:
            continue

    lines = body_text.splitlines()

    ignored_lines = {
        "home",
        "explore",
        "blog",
        "login",
        "apply",
        "back",
        "about",
        "startup",
        "startup details",
        "reviews & testimonials",
        "profile highlights",
        "organizations",
        "quick info",
    }

    try:
        name_index = next(
            index
            for index, line in enumerate(lines)
            if line.strip().lower() == name.strip().lower()
        )
    except StopIteration:
        name_index = -1

    candidates: list[str] = []

    for line in lines[name_index + 1:name_index + 15]:
        candidate = clean_text(line)

        if not candidate:
            continue

        if candidate.lower() in ignored_lines:
            continue

        if candidate.startswith("TG-ST-"):
            continue

        if len(candidate) < 25:
            continue

        candidates.append(candidate)

        if len(" ".join(candidates)) >= 450:
            break

    return shorten_text(" ".join(candidates), 500)


def fetch_profile_details(profile_url: str) -> dict[str, str]:
    """Collect important founder details from one TG10X profile."""
    with sync_playwright() as playwright:
        browser, page = create_browser_page(playwright)

        try:
            page.goto(
                profile_url,
                wait_until="networkidle",
                timeout=90000,
            )

            page.wait_for_timeout(3000)

            name = get_first_text(
                page,
                [
                    "h1",
                    "main h1",
                ],
            )

            if not name:
                name = (
                    profile_url.rstrip("/")
                    .split("/")[-1]
                    .replace("-", " ")
                    .title()
                )

            body_text = clean_text(page.locator("body").inner_text())

            summary = extract_summary(
                page=page,
                name=name,
                body_text=body_text,
            )

            designation = extract_field(
                body_text,
                "DESIGNATION",
            )

            stage = extract_field(
                body_text,
                "STAGE",
            )

            dpiit_number = extract_field(
                body_text,
                "DPIIT NUMBER",
            )

            location = extract_location(body_text)

            organization = extract_organization(
                page,
                body_text,
            )

            linkedin = get_social_link(
                page,
                "linkedin.com",
            )

            instagram = get_social_link(
                page,
                "instagram.com",
            )

        finally:
            browser.close()

    return {
        "name": name,
        "summary": summary,
        "designation": designation,
        "stage": stage,
        "dpiit_number": dpiit_number,
        "organization": organization,
        "location": location,
        "profile_url": profile_url,
        "linkedin": linkedin,
        "instagram": instagram,
    }


def load_seen_profiles() -> set[str]:
    """Load profile URLs that were already processed."""
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            return set(str(item) for item in data)

        return set()

    except (OSError, json.JSONDecodeError):
        return set()


def save_seen_profiles(profile_urls: set[str]) -> None:
    """Save processed profile URLs."""
    STATE_FILE.write_text(
        json.dumps(
            sorted(profile_urls),
            indent=2,
        ),
        encoding="utf-8",
    )


def send_telegram_notification(profile: dict[str, str]) -> None:
    """Send a short and readable Telegram founder notification."""
    name = escape_html(profile["name"])
    summary = escape_html(profile["summary"])
    designation = escape_html(profile["designation"])
    organization = escape_html(profile["organization"])
    location = escape_html(profile["location"])
    stage = escape_html(profile["stage"])
    dpiit_number = escape_html(profile["dpiit_number"])

    profile_url = profile["profile_url"]
    linkedin = profile["linkedin"]
    instagram = profile["instagram"]

    message_parts = [
        "🚀 <b>New TG10X Startup Founder</b>",
        "",
        f"👤 <b>{name}</b>",
    ]

    if designation:
        message_parts.append(
            f"💼 <b>Role:</b> {designation}"
        )

    if organization:
        message_parts.append(
            f"🏢 <b>Company:</b> {organization}"
        )

    if location:
        message_parts.append(
            f"📍 <b>Location:</b> {location}"
        )

    if stage:
        message_parts.append(
            f"📈 <b>Stage:</b> {stage}"
        )

    if dpiit_number:
        message_parts.append(
            f"🪪 <b>DPIIT:</b> {dpiit_number}"
        )

    if summary:
        message_parts.extend(
            [
                "",
                "📝 <b>About</b>",
                summary,
            ]
        )

    message_parts.extend(
        [
            "",
            f'🔗 <a href="{profile_url}">'
            "Open TG10X profile</a>",
        ]
    )

    if linkedin:
        message_parts.append(
            f'💼 <a href="{linkedin}">'
            "Open LinkedIn profile</a>"
        )

    if instagram:
        message_parts.append(
            f'📷 <a href="{instagram}">'
            "Open Instagram profile</a>"
        )

    message = "\n".join(message_parts)

    api_url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        api_url,
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


def main() -> None:
    founder_urls = fetch_founder_urls()
    seen_profiles = load_seen_profiles()

    print(
        f"Founder profiles detected: {len(founder_urls)}"
    )

    if not founder_urls:
        raise RuntimeError(
            "No startup founder profiles were detected."
        )

    # First run records existing profiles and prevents old alerts.
    if not seen_profiles:
        save_seen_profiles(set(founder_urls))

        print(
            "Initial founder state created. "
            "Existing founder profiles were not sent."
        )
        return

    new_profile_urls = [
        profile_url
        for profile_url in founder_urls
        if profile_url not in seen_profiles
    ]

    if not new_profile_urls:
        print(
            "No new TG10X startup founders found."
        )
        return

    successful_profiles: set[str] = set()

    # Process older additions first and newest additions last.
    for profile_url in reversed(new_profile_urls):
        try:
            profile = fetch_profile_details(
                profile_url
            )

            send_telegram_notification(
                profile
            )

            successful_profiles.add(
                profile_url
            )

            print(
                "Telegram notification sent for: "
                f"{profile['name']}"
            )

        except Exception as error:
            print(
                f"Failed to process {profile_url}: "
                f"{error}"
            )

    # Mark only successfully notified profiles as seen.
    seen_profiles.update(successful_profiles)
    save_seen_profiles(seen_profiles)


if __name__ == "__main__":
    main()

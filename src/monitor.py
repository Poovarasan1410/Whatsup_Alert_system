from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.sync_api import (
    Browser,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


@dataclass(frozen=True)
class Profile:
    """Startup or founder profile discovered by the monitor."""

    name: str
    profile_url: str
    description: str = ""
    linkedin_url: str = ""
    website_url: str = ""


def clean_text(value: str | None) -> str:
    """Remove unnecessary whitespace from scraped text."""

    if not value:
        return ""

    return " ".join(value.split())


def normalize_url(url: str) -> str:
    """Remove query strings and fragments from a URL."""

    parsed = urlparse(url)

    normalized = parsed._replace(
        query="",
        fragment="",
    )

    return urlunparse(normalized).rstrip("/")


class StartupMonitor:
    """Monitor a startup directory for founder profiles."""

    def __init__(
        self,
        monitor_url: str,
        base_url: str,
    ) -> None:
        self.monitor_url = monitor_url
        self.base_url = base_url

    def collect_profiles(self) -> list[Profile]:
        """Open the monitoring page and collect profile data."""

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
            )

            try:
                page = browser.new_page(
                    viewport={
                        "width": 1440,
                        "height": 1200,
                    },
                    user_agent=(
                        "Mozilla/5.0 "
                        "(Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/131.0 Safari/537.36"
                    ),
                )

                self._open_page(page)
                self._scroll_page(page)

                profile_links = self._collect_profile_links(page)

                print(
                    f"Unique profile links found: "
                    f"{len(profile_links)}"
                )

                profiles: list[Profile] = []

                for index, profile_url in enumerate(
                    profile_links,
                    start=1,
                ):
                    print(
                        f"Reading profile {index}/"
                        f"{len(profile_links)}: {profile_url}"
                    )

                    profile = self._read_profile(
                        browser=browser,
                        profile_url=profile_url,
                    )

                    profiles.append(profile)

                return profiles

            finally:
                browser.close()

    def _open_page(
        self,
        page: Page,
    ) -> None:
        """Open the monitored website."""

        try:
            page.goto(
                self.monitor_url,
                wait_until="domcontentloaded",
                timeout=90_000,
            )

            page.wait_for_timeout(5_000)

        except PlaywrightTimeoutError as error:
            raise RuntimeError(
                f"Monitoring page timed out: {self.monitor_url}"
            ) from error

    @staticmethod
    def _scroll_page(page: Page) -> None:
        """Scroll the page to load dynamically rendered profiles."""

        previous_height = 0

        for _ in range(10):
            current_height = page.evaluate(
                "document.body.scrollHeight"
            )

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(1_500)

            if current_height == previous_height:
                break

            previous_height = current_height

    def _collect_profile_links(
        self,
        page: Page,
    ) -> list[str]:
        """Collect unique profile links from the listing page."""

        links = page.locator('a[href^="/u/"]')

        collected_urls: list[str] = []
        seen_urls: set[str] = set()

        for index in range(links.count()):
            href = links.nth(index).get_attribute("href")

            if not href:
                continue

            absolute_url = normalize_url(
                urljoin(
                    self.base_url,
                    href,
                )
            )

            if absolute_url in seen_urls:
                continue

            seen_urls.add(absolute_url)
            collected_urls.append(absolute_url)

        return collected_urls

    def _read_profile(
        self,
        browser: Browser,
        profile_url: str,
    ) -> Profile:
        """Read details from an individual profile page."""

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200,
            }
        )

        try:
            page.goto(
                profile_url,
                wait_until="domcontentloaded",
                timeout=90_000,
            )

            page.wait_for_timeout(2_500)

            name = self._first_text(
                page,
                [
                    "h1",
                    "main h2",
                    "[data-testid='profile-name']",
                ],
            )

            description = self._first_text(
                page,
                [
                    "main p",
                    "[data-testid='profile-description']",
                    ".profile-description",
                    ".bio",
                ],
            )

            linkedin_url = self._first_link(
                page,
                [
                    'a[href*="linkedin.com"]',
                ],
            )

            website_url = self._first_external_website(
                page=page,
                excluded_domains={
                    "linkedin.com",
                    "instagram.com",
                    "facebook.com",
                    "twitter.com",
                    "x.com",
                    "youtube.com",
                    "tg10x.com",
                },
            )

            if not name:
                name = (
                    profile_url.split("/")[-1]
                    .replace("-", " ")
                    .replace("_", " ")
                    .title()
                )

            return Profile(
                name=name,
                profile_url=profile_url,
                description=description,
                linkedin_url=linkedin_url,
                website_url=website_url,
            )

        except PlaywrightTimeoutError:
            print(
                f"Warning: profile page timed out: "
                f"{profile_url}"
            )

            fallback_name = (
                profile_url.split("/")[-1]
                .replace("-", " ")
                .replace("_", " ")
                .title()
            )

            return Profile(
                name=fallback_name,
                profile_url=profile_url,
            )

        finally:
            page.close()

    @staticmethod
    def _first_text(
        page: Page,
        selectors: list[str],
    ) -> str:
        """Return the first non-empty text from possible selectors."""

        for selector in selectors:
            locator = page.locator(selector)

            if locator.count() == 0:
                continue

            try:
                text = clean_text(
                    locator.first.inner_text(
                        timeout=3_000,
                    )
                )

                if text:
                    return text

            except PlaywrightTimeoutError:
                continue

        return ""

    @staticmethod
    def _first_link(
        page: Page,
        selectors: list[str],
    ) -> str:
        """Return the first valid URL from possible selectors."""

        for selector in selectors:
            locator = page.locator(selector)

            if locator.count() == 0:
                continue

            href = locator.first.get_attribute("href")

            if href:
                return normalize_url(href)

        return ""

    @staticmethod
    def _first_external_website(
        page: Page,
        excluded_domains: set[str],
    ) -> str:
        """Find the first external website link."""

        links = page.locator('a[href^="http"]')

        for index in range(links.count()):
            href = links.nth(index).get_attribute("href")

            if not href:
                continue

            normalized = normalize_url(href)
            domain = urlparse(normalized).netloc.lower()

            if domain.startswith("www."):
                domain = domain[4:]

            if any(
                excluded_domain in domain
                for excluded_domain in excluded_domains
            ):
                continue

            return normalized

        return ""

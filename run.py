import sys
import time

from src.config import get_settings
from src.monitor import Profile, StartupMonitor
from src.state_manager import (
    load_seen_items,
    save_seen_items,
)
from src.whatsapp import WhatsAppClient


def format_whatsapp_message(
    profile: Profile,
) -> str:
    """Create a structured WhatsApp notification."""

    message_parts = [
        "🚀 *New Startup Founder Detected*",
        "",
        f"👤 *Name:* {profile.name}",
    ]

    if profile.description:
        description = profile.description

        if len(description) > 500:
            description = (
                description[:497].rstrip()
                + "..."
            )

        message_parts.extend(
            [
                "",
                "📝 *About:*",
                description,
            ]
        )

    message_parts.extend(
        [
            "",
            "🔗 *Profile:*",
            profile.profile_url,
        ]
    )

    if profile.linkedin_url:
        message_parts.extend(
            [
                "",
                "💼 *LinkedIn:*",
                profile.linkedin_url,
            ]
        )

    if profile.website_url:
        message_parts.extend(
            [
                "",
                "🌐 *Website:*",
                profile.website_url,
            ]
        )

    message_parts.extend(
        [
            "",
            "⚙️ Startup Monitoring Automation",
        ]
    )

    return "\n".join(message_parts)


def main() -> int:
    """Run the monitoring workflow."""

    settings = get_settings()

    print("Starting startup monitoring workflow.")
    print(f"Monitoring URL: {settings.monitor_url}")
    print(f"State file: {settings.state_file}")

    monitor = StartupMonitor(
        monitor_url=settings.monitor_url,
        base_url=settings.base_url,
    )

    profiles = monitor.collect_profiles()

    if not profiles:
        raise RuntimeError(
            "No profiles were detected. "
            "The website layout or selector may have changed."
        )

    print(f"Profiles collected: {len(profiles)}")

    seen_items = load_seen_items(
        settings.state_file
    )

    current_urls = {
        profile.profile_url
        for profile in profiles
    }

    if not seen_items:
        print("No previous state was found.")

        if not settings.first_run_send_existing:
            save_seen_items(
                settings.state_file,
                current_urls,
            )

            print(
                "Initial baseline created. "
                "Existing profiles were not notified."
            )

            return 0

    new_profiles = [
        profile
        for profile in profiles
        if profile.profile_url not in seen_items
    ]

    if not new_profiles:
        print("No new profiles found.")

        save_seen_items(
            settings.state_file,
            seen_items | current_urls,
        )

        return 0

    new_profiles = new_profiles[
        : settings.max_notifications_per_run
    ]

    print(
        f"New profiles to notify: "
        f"{len(new_profiles)}"
    )

    whatsapp_client = WhatsAppClient(
        api_url=settings.wasender_api_url,
        api_key=settings.wasender_api_key,
        recipient=settings.whatsapp_to_number,
    )

    successfully_sent: set[str] = set()
    failed_profiles: list[str] = []

    for profile in reversed(new_profiles):
        message = format_whatsapp_message(
            profile
        )

        try:
            result = whatsapp_client.send_text_message(
                message
            )

            successfully_sent.add(
                profile.profile_url
            )

            message_data = result.get(
                "data",
                {},
            )

            print(
                "WhatsApp message accepted for "
                f"{profile.name}. "
                f"Message ID: "
                f"{message_data.get('msgId', 'unknown')}"
            )

            time.sleep(3)

        except Exception as error:
            failed_profiles.append(
                profile.profile_url
            )

            print(
                f"Failed to send notification for "
                f"{profile.name}: {error}"
            )

    updated_state = (
        seen_items
        | successfully_sent
    )

    save_seen_items(
        settings.state_file,
        updated_state,
    )

    print(
        f"Successfully notified: "
        f"{len(successfully_sent)}"
    )

    if failed_profiles:
        print(
            f"Failed notifications: "
            f"{len(failed_profiles)}"
        )

        for failed_profile in failed_profiles:
            print(f"- {failed_profile}")

        return 1

    print("Monitoring workflow completed successfully.")

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()

    except Exception as error:
        print(f"FATAL ERROR: {error}")
        exit_code = 1

    sys.exit(exit_code)

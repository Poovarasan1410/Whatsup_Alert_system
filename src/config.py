import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Application configuration."""

    monitor_url: str
    base_url: str
    wasender_api_url: str
    wasender_api_key: str
    whatsapp_to_number: str
    state_file: Path
    first_run_send_existing: bool
    max_notifications_per_run: int


def get_required_environment_variable(name: str) -> str:
    """Read and validate a required environment variable."""

    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is missing."
        )

    return value


def get_boolean_environment_variable(
    name: str,
    default: bool = False,
) -> bool:
    """Convert an environment variable into a boolean value."""

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def get_settings() -> Settings:
    """Load project settings."""

    return Settings(
        monitor_url=os.getenv(
            "MONITOR_URL",
            "https://tg10x.com/explore/startup-founders/india",
        ).strip(),
        base_url=os.getenv(
            "BASE_URL",
            "https://tg10x.com",
        ).strip(),
        wasender_api_url=os.getenv(
            "WASENDER_API_URL",
            "https://www.wasenderapi.com/api/send-message",
        ).strip(),
        wasender_api_key=get_required_environment_variable(
            "WASENDER_API_KEY"
        ),
        whatsapp_to_number=get_required_environment_variable(
            "WHATSAPP_TO_NUMBER"
        ),
        state_file=Path(
            os.getenv(
                "STATE_FILE",
                "data/seen_items.json",
            )
        ),
        first_run_send_existing=get_boolean_environment_variable(
            "FIRST_RUN_SEND_EXISTING",
            default=False,
        ),
        max_notifications_per_run=int(
            os.getenv(
                "MAX_NOTIFICATIONS_PER_RUN",
                "10",
            )
        ),
    )

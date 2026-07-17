from typing import Any

import requests


class WhatsAppClient:
    """Send WhatsApp notifications through WasenderAPI."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        recipient: str,
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.recipient = recipient

    def send_text_message(
        self,
        message: str,
    ) -> dict[str, Any]:
        """Send a text message to the configured recipient."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "to": self.recipient,
            "text": message,
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30,
            )

        except requests.RequestException as error:
            raise RuntimeError(
                f"Unable to connect to WasenderAPI: {error}"
            ) from error

        if not response.ok:
            raise RuntimeError(
                "WasenderAPI request failed. "
                f"HTTP {response.status_code}: {response.text}"
            )

        try:
            result = response.json()

        except ValueError as error:
            raise RuntimeError(
                "WasenderAPI returned an invalid JSON response."
            ) from error

        if not result.get("success"):
            raise RuntimeError(
                f"WasenderAPI rejected the message: {result}"
            )

        return result

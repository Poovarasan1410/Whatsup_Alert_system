
import json
from pathlib import Path


def load_seen_items(state_file: Path) -> set[str]:
    """Load previously processed profile URLs."""

    if not state_file.exists():
        return set()

    try:
        content = state_file.read_text(encoding="utf-8")
        data = json.loads(content)

        if not isinstance(data, list):
            raise ValueError(
                "State file must contain a JSON list."
            )

        return {
            str(item).strip()
            for item in data
            if str(item).strip()
        }

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"State file contains invalid JSON: {state_file}"
        ) from error

    except OSError as error:
        raise RuntimeError(
            f"Unable to read state file: {state_file}"
        ) from error


def save_seen_items(
    state_file: Path,
    seen_items: set[str],
) -> None:
    """Save processed profile URLs."""

    state_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    serialized_data = json.dumps(
        sorted(seen_items),
        indent=2,
        ensure_ascii=False,
    )

    temporary_file = state_file.with_suffix(".tmp")

    try:
        temporary_file.write_text(
            serialized_data,
            encoding="utf-8",
        )

        temporary_file.replace(state_file)

    except OSError as error:
        raise RuntimeError(
            f"Unable to save state file: {state_file}"
        ) from error

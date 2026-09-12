from pathlib import Path

from pydantic import BaseModel, Field


STATE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-external-resources.json"
)


class ExternalResourceState(BaseModel):
    """
    Persisted external resources that the user confirms are available
    for the current walkthrough goal.

    These resources are intentionally kept outside the room-inventory /
    Object DNA system because they were not discovered from the room scan.
    """

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    resources: list[str] = Field(
        default_factory=list
    )


def _normalize_whitespace(
    text: str,
) -> str:
    return " ".join(
        text.strip().split()
    )


def canonicalize_external_resource(
    resource: str,
) -> str:
    """
    Convert casual user wording into a stable canonical label.

    This keeps planning inputs deterministic.
    """

    cleaned = _normalize_whitespace(
        resource
    ).lower()

    if not cleaned:
        raise ValueError(
            "External resource may not be empty."
        )

    smartphone_aliases = {
        "phone",
        "smartphone",
        "cell phone",
        "mobile phone",
        "iphone",
    }

    camera_aliases = {
        "camera",
        "digital camera",
        "action camera",
    }

    if cleaned in smartphone_aliases:
        return "smartphone"

    if "insta360" in cleaned:
        return "insta360 camera"

    if cleaned in camera_aliases:
        return "camera"

    return cleaned


def dedupe_preserve_order(
    values: list[str],
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result


def build_external_resource_state(
    *,
    goal: str,
    resources: list[str],
) -> ExternalResourceState:
    """
    Normalize, validate, and deduplicate confirmed external resources.
    """

    if not goal.strip():
        raise ValueError(
            "Goal may not be empty."
        )

    normalized_resources = [
        canonicalize_external_resource(
            resource
        )
        for resource in resources
    ]

    normalized_resources = (
        dedupe_preserve_order(
            normalized_resources
        )
    )

    return ExternalResourceState(
        goal=_normalize_whitespace(
            goal
        ),
        resources=normalized_resources,
    )


def load_external_resource_state(
    path: Path = STATE_PATH,
) -> ExternalResourceState | None:
    """
    Load the persisted external-resource state if it exists.
    """

    if not path.exists():
        return None

    return ExternalResourceState.model_validate_json(
        path.read_text(
            encoding="utf-8"
        )
    )


def save_external_resource_state(
    state: ExternalResourceState,
    path: Path = STATE_PATH,
) -> None:
    """
    Atomically persist confirmed external resources.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        path.name + ".tmp"
    )

    temporary_path.write_text(
        state.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        path
    )
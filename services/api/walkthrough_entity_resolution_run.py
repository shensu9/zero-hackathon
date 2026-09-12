from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from walkthrough_entity_resolution_schemas import (
    WalkthroughEntityResolution,
)
from walkthrough_entity_resolution_validator import (
    validate_entity_resolution,
)
from walkthrough_entity_resolver import (
    MODEL,
    resolve_walkthrough_entities,
)
from walkthrough_perception import (
    WalkthroughFrameObservation,
)


RUN_VERSION = 1

DEFAULT_WALKTHROUGH_ID = "walkthrough-01"

WALKTHROUGH_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)


REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

PRIVATE_DIR = (
    REPO_ROOT
    / "sample_data"
    / "private"
)

PERCEPTION_PATH = (
    PRIVATE_DIR
    / f"{DEFAULT_WALKTHROUGH_ID}-perception.json"
)

OUTPUT_PATH = (
    PRIVATE_DIR
    / f"{DEFAULT_WALKTHROUGH_ID}-entity-resolution.json"
)

RESOLVER_SOURCE_PATH = (
    REPO_ROOT
    / "services"
    / "api"
    / "walkthrough_entity_resolver.py"
)


def configure_utf8_console() -> None:
    for stream in (
        sys.stdout,
        sys.stderr,
    ):
        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8"
                )
            except Exception:
                pass


def validate_walkthrough_id(
    value: str,
) -> str:
    if not WALKTHROUGH_ID_PATTERN.fullmatch(
        value
    ):
        raise ValueError(
            "walkthrough id may contain only letters, "
            "numbers, hyphens, and underscores"
        )

    return value


def configure_walkthrough_paths(
    walkthrough_id: str,
) -> None:
    global PERCEPTION_PATH
    global OUTPUT_PATH

    walkthrough_id = validate_walkthrough_id(
        walkthrough_id
    )

    PERCEPTION_PATH = (
        PRIVATE_DIR
        / f"{walkthrough_id}-perception.json"
    )

    OUTPUT_PATH = (
        PRIVATE_DIR
        / f"{walkthrough_id}-entity-resolution.json"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run ZERO cross-frame entity resolution "
            "for a namespaced walkthrough."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=DEFAULT_WALKTHROUGH_ID,
        help=(
            "Artifact namespace such as walkthrough-02. "
            "Defaults to walkthrough-01 for backwards "
            "compatibility."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate perception input and matching entity "
            "resolution cache without calling the model "
            "or writing output."
        ),
    )

    return parser.parse_args()


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_frames(
) -> list[
    WalkthroughFrameObservation
]:
    if not PERCEPTION_PATH.exists():
        raise FileNotFoundError(
            "Walkthrough perception file "
            f"does not exist: {PERCEPTION_PATH}"
        )

    payload = json.loads(
        PERCEPTION_PATH.read_text(
            encoding="utf-8"
        )
    )

    if not payload.get(
        "completed"
    ):
        raise RuntimeError(
            "Walkthrough perception is not marked complete."
        )

    frame_payloads = payload.get(
        "frames"
    )

    if not isinstance(
        frame_payloads,
        list,
    ):
        raise RuntimeError(
            "Walkthrough perception contains no frame list."
        )

    return [
        WalkthroughFrameObservation
        .model_validate(
            frame_payload
        )
        for frame_payload
        in frame_payloads
    ]


def source_observation_count(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> int:
    return sum(
        len(
            frame.objects
        )
        for frame
        in frames
    )


def retained_observation_count(
    resolution: WalkthroughEntityResolution,
) -> int:
    return sum(
        len(
            entity.observation_ids
        )
        for entity
        in resolution.entities
    )


def load_cached_resolution(
    *,
    frames: list[
        WalkthroughFrameObservation
    ],
    perception_sha256: str,
    resolver_sha256: str,
) -> WalkthroughEntityResolution | None:
    if not OUTPUT_PATH.exists():
        return None

    try:
        envelope = json.loads(
            OUTPUT_PATH.read_text(
                encoding="utf-8"
            )
        )

        if (
            envelope.get("run_version")
            != RUN_VERSION
        ):
            return None

        if (
            envelope.get("model")
            != MODEL
        ):
            return None

        if (
            envelope.get(
                "perception_sha256"
            )
            != perception_sha256
        ):
            return None

        if (
            envelope.get(
                "resolver_source_sha256"
            )
            != resolver_sha256
        ):
            return None

        payload = envelope.get(
            "resolution"
        )

        resolution = (
            WalkthroughEntityResolution
            .model_validate(
                payload
            )
        )

        return validate_entity_resolution(
            frames=frames,
            resolution=resolution,
        )

    except Exception as exc:
        print(
            "Cached entity resolution could not "
            "be reused; regenerating."
        )

        print(
            "Reason:",
            exc,
        )

        return None


def save_resolution(
    *,
    resolution: WalkthroughEntityResolution,
    perception_sha256: str,
    resolver_sha256: str,
) -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    envelope = {
        "run_version":
            RUN_VERSION,

        "model":
            MODEL,

        "perception_path":
            str(
                PERCEPTION_PATH
            ),

        "perception_sha256":
            perception_sha256,

        "resolver_source_sha256":
            resolver_sha256,

        "resolution":
            resolution.model_dump(
                mode="json"
            ),
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            envelope,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def run_dry_run(
    *,
    walkthrough_id: str,
    frames: list[
        WalkthroughFrameObservation
    ],
    perception_sha256: str,
    resolver_sha256: str,
    raw_count: int,
) -> None:
    resolution = load_cached_resolution(
        frames=frames,
        perception_sha256=(
            perception_sha256
        ),
        resolver_sha256=(
            resolver_sha256
        ),
    )

    cache_hit = (
        resolution is not None
    )

    expected_model_calls = (
        0
        if cache_hit
        else 1
    )

    print()
    print("=" * 72)
    print(
        "ZERO WALKTHROUGH ENTITY RESOLUTION "
        "— DRY RUN"
    )
    print("=" * 72)
    print()

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Model:",
        MODEL,
    )

    print(
        "Perception input:",
        PERCEPTION_PATH,
    )

    print(
        "Output:",
        OUTPUT_PATH,
    )

    print(
        "Frames:",
        len(frames),
    )

    print(
        "Raw observations:",
        raw_count,
    )

    print(
        "Perception SHA-256:",
        perception_sha256,
    )

    print(
        "Resolver fingerprint:",
        resolver_sha256,
    )

    print(
        "Matching cache:",
        cache_hit,
    )

    print(
        "Expected model calls on real run:",
        expected_model_calls,
    )

    print()
    print(
        "Model calls executed by dry run: 0"
    )


def main() -> None:
    configure_utf8_console()

    args = parse_args()

    walkthrough_id = validate_walkthrough_id(
        args.walkthrough_id
    )

    configure_walkthrough_paths(
        walkthrough_id
    )

    frames = load_frames()

    perception_sha256 = (
        sha256_file(
            PERCEPTION_PATH
        )
    )

    resolver_sha256 = (
        sha256_file(
            RESOLVER_SOURCE_PATH
        )
    )

    raw_count = (
        source_observation_count(
            frames
        )
    )

    if args.dry_run:
        run_dry_run(
            walkthrough_id=(
                walkthrough_id
            ),
            frames=frames,
            perception_sha256=(
                perception_sha256
            ),
            resolver_sha256=(
                resolver_sha256
            ),
            raw_count=raw_count,
        )

        return

    print()
    print("=" * 72)
    print(
        "ZERO WALKTHROUGH ENTITY RESOLUTION"
    )
    print("=" * 72)

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Model:",
        MODEL,
    )

    print(
        "Frames:",
        len(frames),
    )

    print(
        "Raw observations:",
        raw_count,
    )

    print(
        "Resolver fingerprint:",
        resolver_sha256[:12],
    )

    print()

    resolution = load_cached_resolution(
        frames=frames,
        perception_sha256=(
            perception_sha256
        ),
        resolver_sha256=(
            resolver_sha256
        ),
    )

    cache_hit = (
        resolution is not None
    )

    model_calls = 0

    if cache_hit:
        print(
            "ENTITY RESOLUTION CACHE HIT"
        )

    else:
        print(
            "Calling Nemotron entity resolver..."
        )

        resolution = (
            resolve_walkthrough_entities(
                frames
            )
        )

        model_calls += 1

        save_resolution(
            resolution=resolution,
            perception_sha256=(
                perception_sha256
            ),
            resolver_sha256=(
                resolver_sha256
            ),
        )

        print(
            "Saved private entity resolution."
        )

    if resolution is None:
        raise RuntimeError(
            "Entity resolution unexpectedly produced "
            "no result."
        )

    retained_count = (
        retained_observation_count(
            resolution
        )
    )

    ignored_count = len(
        resolution.ignored_observations
    )

    print()
    print("=" * 72)
    print(
        "ENTITY RESOLUTION COMPLETE"
    )
    print("=" * 72)

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Cache hit:",
        cache_hit,
    )

    print(
        "Model calls:",
        model_calls,
    )

    print(
        "Raw observations:",
        raw_count,
    )

    print(
        "Physical entities:",
        len(
            resolution.entities
        ),
    )

    print(
        "Retained sightings:",
        retained_count,
    )

    print(
        "Ignored sightings:",
        ignored_count,
    )

    print(
        "Accounted sightings:",
        (
            retained_count
            + ignored_count
        ),
    )

    print()
    print(
        "RESOLVED ENTITIES"
    )

    print(
        "-" * 72
    )

    for index, entity in enumerate(
        resolution.entities,
        start=1,
    ):
        observations = ", ".join(
            entity.observation_ids
        )

        print(
            f"{index:02d}. "
            f"{entity.canonical_name}"
        )

        print(
            "    description:",
            entity.canonical_description,
        )

        print(
            "    location:",
            entity.location_hint,
        )

        print(
            "    sightings:",
            observations,
        )

        print(
            "    confidence:",
            entity.merge_confidence,
        )

        if (
            entity.identity_uncertainty
        ):
            print(
                "    uncertainty:",
                entity.identity_uncertainty,
            )

    if (
        resolution.ignored_observations
    ):
        print()
        print(
            "IGNORED OBSERVATIONS"
        )

        print(
            "-" * 72
        )

        for ignored in (
            resolution.ignored_observations
        ):
            print(
                f"- {ignored.observation_id}: "
                f"{ignored.reason.value} - "
                f"{ignored.explanation}"
            )

    print()
    print(
        "Saved private resolution:"
    )

    print(
        OUTPUT_PATH
    )


if __name__ == "__main__":
    main()
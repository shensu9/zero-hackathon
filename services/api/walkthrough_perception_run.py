from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from walkthrough_perception import (
    MODEL,
    WalkthroughFrameObservation,
    perceive_walkthrough_keyframe,
)


RUN_VERSION = 1
EXPECTED_KEYFRAME_COUNT = 8

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

KEYFRAME_DIR = (
    PRIVATE_DIR
    / f"{DEFAULT_WALKTHROUGH_ID}-keyframes"
)

CACHE_DIR = (
    PRIVATE_DIR
    / f"{DEFAULT_WALKTHROUGH_ID}-perception-cache"
)

OUTPUT_PATH = (
    PRIVATE_DIR
    / f"{DEFAULT_WALKTHROUGH_ID}-perception.json"
)

SERVICE_SOURCE_PATH = (
    REPO_ROOT
    / "services"
    / "api"
    / "walkthrough_perception.py"
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
    global KEYFRAME_DIR
    global CACHE_DIR
    global OUTPUT_PATH

    walkthrough_id = validate_walkthrough_id(
        walkthrough_id
    )

    KEYFRAME_DIR = (
        PRIVATE_DIR
        / f"{walkthrough_id}-keyframes"
    )

    CACHE_DIR = (
        PRIVATE_DIR
        / f"{walkthrough_id}-perception-cache"
    )

    OUTPUT_PATH = (
        PRIVATE_DIR
        / f"{walkthrough_id}-perception.json"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run ZERO walkthrough perception for a "
            "namespaced walkthrough."
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
            "Validate inputs and matching caches without "
            "calling the perception model or writing output."
        ),
    )

    return parser.parse_args()


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def service_fingerprint() -> str:
    """
    Any change to walkthrough_perception.py invalidates old
    frame-perception cache entries automatically.

    This prevents us from silently reusing results generated
    with an older perception prompt or schema.
    """

    if not SERVICE_SOURCE_PATH.exists():
        raise FileNotFoundError(
            "Perception service source was not found: "
            f"{SERVICE_SOURCE_PATH}"
        )

    return sha256_file(
        SERVICE_SOURCE_PATH
    )


def cache_path_for_frame(
    *,
    sample_number: int,
    image_path: Path,
) -> Path:
    return (
        CACHE_DIR
        / (
            f"frame_{sample_number:02d}_"
            f"{image_path.stem}.json"
        )
    )


def load_cached_frame(
    *,
    sample_number: int,
    image_path: Path,
    image_sha256: str,
    perception_sha256: str,
) -> WalkthroughFrameObservation | None:
    cache_path = cache_path_for_frame(
        sample_number=sample_number,
        image_path=image_path,
    )

    if not cache_path.exists():
        return None

    try:
        envelope = json.loads(
            cache_path.read_text(
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
            envelope.get("image_sha256")
            != image_sha256
        ):
            return None

        if (
            envelope.get(
                "perception_service_sha256"
            )
            != perception_sha256
        ):
            return None

        if (
            envelope.get("sample_number")
            != sample_number
        ):
            return None

        payload = envelope.get(
            "observation"
        )

        if not isinstance(
            payload,
            dict,
        ):
            return None

        observation = (
            WalkthroughFrameObservation
            .model_validate(
                payload
            )
        )

        # The cache must correspond to the same actual
        # source frame.
        if (
            Path(
                observation.image_path
            ).resolve()
            != image_path.resolve()
        ):
            return None

        return observation

    except Exception as exc:
        print(
            f"[frame {sample_number:02d}] "
            "Cache could not be reused; "
            f"regenerating. Reason: {exc}"
        )

        return None


def save_cached_frame(
    *,
    observation: WalkthroughFrameObservation,
    image_path: Path,
    image_sha256: str,
    perception_sha256: str,
) -> Path:
    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path = cache_path_for_frame(
        sample_number=(
            observation.sample_number
        ),
        image_path=image_path,
    )

    envelope = {
        "run_version":
            RUN_VERSION,

        "model":
            MODEL,

        "sample_number":
            observation.sample_number,

        "source_image":
            str(
                image_path.resolve()
            ),

        "image_sha256":
            image_sha256,

        "perception_service_sha256":
            perception_sha256,

        "observation":
            observation.model_dump(
                mode="json"
            ),
    }

    cache_path.write_text(
        json.dumps(
            envelope,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return cache_path


def save_progress(
    *,
    results: list[
        WalkthroughFrameObservation
    ],
    perception_sha256: str,
    completed: bool,
) -> None:
    """
    Persist aggregate progress after every successful frame.

    If a later call fails, the successfully completed
    observations are still available for inspection.
    """

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "run_version":
            RUN_VERSION,

        "model":
            MODEL,

        "perception_service_sha256":
            perception_sha256,

        "expected_keyframe_count":
            EXPECTED_KEYFRAME_COUNT,

        "completed_frame_count":
            len(results),

        "completed":
            completed,

        "frames": [
            result.model_dump(
                mode="json"
            )
            for result
            in results
        ],
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def run_dry_run(
    *,
    keyframes: list[Path],
    perception_sha256: str,
    walkthrough_id: str,
) -> None:
    cache_hits = 0

    for sample_number, image_path in enumerate(
        keyframes,
        start=1,
    ):
        image_sha256 = sha256_file(
            image_path
        )

        cached = load_cached_frame(
            sample_number=sample_number,
            image_path=image_path,
            image_sha256=image_sha256,
            perception_sha256=(
                perception_sha256
            ),
        )

        if cached is not None:
            cache_hits += 1

    expected_model_calls = (
        len(keyframes)
        - cache_hits
    )

    print()
    print("=" * 72)
    print("ZERO WALKTHROUGH PERCEPTION — DRY RUN")
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
        "Keyframe directory:",
        KEYFRAME_DIR,
    )
    print(
        "Cache directory:",
        CACHE_DIR,
    )
    print(
        "Output:",
        OUTPUT_PATH,
    )
    print(
        "Keyframes:",
        len(keyframes),
    )
    print(
        "Matching cache entries:",
        cache_hits,
    )
    print(
        "Expected model calls on real run:",
        expected_model_calls,
    )
    print(
        "Perception fingerprint:",
        perception_sha256,
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

    keyframes = sorted(
        KEYFRAME_DIR.glob(
            "keyframe_*.jpg"
        )
    )

    if (
        len(keyframes)
        != EXPECTED_KEYFRAME_COUNT
    ):
        raise RuntimeError(
            "Expected exactly "
            f"{EXPECTED_KEYFRAME_COUNT} keyframes, "
            f"found {len(keyframes)} in "
            f"{KEYFRAME_DIR}"
        )

    perception_sha256 = (
        service_fingerprint()
    )

    if args.dry_run:
        run_dry_run(
            keyframes=keyframes,
            perception_sha256=(
                perception_sha256
            ),
            walkthrough_id=(
                walkthrough_id
            ),
        )

        return

    print()
    print("=" * 72)
    print("ZERO WALKTHROUGH PERCEPTION")
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
        "Keyframes:",
        len(keyframes),
    )

    print(
        "Perception fingerprint:",
        perception_sha256[:12],
    )

    print()

    results: list[
        WalkthroughFrameObservation
    ] = []

    cache_hits = 0
    model_calls = 0

    for sample_number, image_path in enumerate(
        keyframes,
        start=1,
    ):
        image_sha256 = sha256_file(
            image_path
        )

        cached = load_cached_frame(
            sample_number=sample_number,
            image_path=image_path,
            image_sha256=image_sha256,
            perception_sha256=(
                perception_sha256
            ),
        )

        if cached is not None:
            cache_hits += 1

            result = cached

            print(
                f"[frame {sample_number:02d}/"
                f"{EXPECTED_KEYFRAME_COUNT}] "
                "CACHE HIT - "
                f"{image_path.name}"
            )

            print(
                "    objects: "
                f"{len(result.objects)}"
            )

        else:
            print(
                f"[frame {sample_number:02d}/"
                f"{EXPECTED_KEYFRAME_COUNT}] "
                "Calling MiniMax - "
                f"{image_path.name}"
            )

            result = (
                perceive_walkthrough_keyframe(
                    image_path,
                    sample_number=(
                        sample_number
                    ),
                )
            )

            model_calls += 1

            cache_path = save_cached_frame(
                observation=result,
                image_path=image_path,
                image_sha256=image_sha256,
                perception_sha256=(
                    perception_sha256
                ),
            )

            print(
                "    objects: "
                f"{len(result.objects)}"
            )

            print(
                "    cached: "
                f"{cache_path.name}"
            )

        results.append(
            result
        )

        save_progress(
            results=results,
            perception_sha256=(
                perception_sha256
            ),
            completed=False,
        )

    save_progress(
        results=results,
        perception_sha256=(
            perception_sha256
        ),
        completed=True,
    )

    print()
    print("=" * 72)
    print("WALKTHROUGH PERCEPTION COMPLETE")
    print("=" * 72)

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Frames:",
        len(results),
    )

    print(
        "Cache hits:",
        cache_hits,
    )

    print(
        "MiniMax calls:",
        model_calls,
    )

    total_observations = sum(
        len(
            result.objects
        )
        for result
        in results
    )

    print(
        "Raw object observations:",
        total_observations,
    )

    print()

    for result in results:
        names = [
            observation.name
            for observation
            in result.objects
        ]

        print(
            f"Frame {result.sample_number}: "
            + ", ".join(
                names
            )
        )

    print()
    print(
        "Saved aggregate perception:"
    )

    print(
        OUTPUT_PATH
    )


if __name__ == "__main__":
    main()
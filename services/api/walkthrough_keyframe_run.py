from __future__ import annotations

import argparse
import re
from pathlib import Path

from video_keyframe_selector import select_video_keyframes


WALKTHROUGH_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)

EXPECTED_KEYFRAME_COUNT = 8


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_video_path(value: str) -> Path:
    path = Path(value)

    if not path.is_absolute():
        path = repo_root() / path

    return path.resolve()


def validate_walkthrough_id(value: str) -> str:
    if not WALKTHROUGH_ID_PATTERN.fullmatch(value):
        raise ValueError(
            "walkthrough id may contain only letters, "
            "numbers, hyphens, and underscores"
        )

    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract deterministic ZERO walkthrough keyframes "
            "without performing any AI inference."
        )
    )

    parser.add_argument(
        "--video",
        required=True,
        help=(
            "Video path. Relative paths are resolved from "
            "the repository root."
        ),
    )

    parser.add_argument(
        "--walkthrough-id",
        required=True,
        help=(
            "Artifact namespace such as walkthrough-02."
        ),
    )

    args = parser.parse_args()

    walkthrough_id = validate_walkthrough_id(
        args.walkthrough_id
    )

    video_path = resolve_video_path(
        args.video
    )

    private_dir = (
        repo_root()
        / "sample_data"
        / "private"
    )

    output_dir = (
        private_dir
        / f"{walkthrough_id}-keyframes"
    )

    manifest_path = (
        private_dir
        / f"{walkthrough_id}-keyframe-selection.json"
    )

    print("=" * 72)
    print("ZERO WALKTHROUGH KEYFRAME EXTRACTION")
    print("=" * 72)
    print()
    print(f"Walkthrough: {walkthrough_id}")
    print(f"Video:       {video_path}")
    print(f"Output:      {output_dir}")
    print()
    print(
        "AI/model calls: 0 "
        "(local OpenCV processing only)"
    )
    print()

    result = select_video_keyframes(
        video_path=video_path,
        output_dir=output_dir,
        selected_count=EXPECTED_KEYFRAME_COUNT,
        clear_previous=True,
    )

    private_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        result.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    print("=" * 72)
    print("KEYFRAME EXTRACTION COMPLETE")
    print("=" * 72)
    print()
    print(
        f"Expected keyframes: "
        f"{EXPECTED_KEYFRAME_COUNT}"
    )
    print(
        f"Keyframe directory: {output_dir}"
    )
    print(
        f"Selection manifest: {manifest_path}"
    )


if __name__ == "__main__":
    main()
import json
import sys
from pathlib import Path


from walkthrough_perception import (
    perceive_walkthrough_keyframe,
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


def main() -> None:
    configure_utf8_console()

    repo_root = (
        Path(
            __file__
        )
        .resolve()
        .parents[2]
    )

    keyframe_dir = (
        repo_root
        / "sample_data"
        / "private"
        / "walkthrough-01-keyframes"
    )

    keyframes = sorted(
        keyframe_dir.glob(
            "keyframe_*.jpg"
        )
    )

    if len(keyframes) < 8:
        raise RuntimeError(
            "Expected 8 walkthrough keyframes, "
            f"found {len(keyframes)}."
        )

    # Use two different areas of the room:
    #
    # keyframe 2 -> early/bed area
    # keyframe 7 -> later shelving/storage area
    #
    # This is intentionally not all 8 yet.
    preview_indices = (
        1,
        6,
    )

    results = []

    for index in preview_indices:
        path = keyframes[
            index
        ]

        sample_number = (
            index
            + 1
        )

        print()
        print("=" * 72)

        print(
            f"PERCEIVING KEYFRAME "
            f"{sample_number}"
        )

        print("=" * 72)

        print(
            path.name
        )

        result = (
            perceive_walkthrough_keyframe(
                path,
                sample_number=(
                    sample_number
                ),
            )
        )

        results.append(
            result
        )

        print(
            result.model_dump_json(
                indent=2
            )
        )

    output_path = (
        repo_root
        / "sample_data"
        / "private"
        / "walkthrough-01-perception-preview.json"
    )

    output_path.write_text(
        json.dumps(
            [
                result.model_dump(
                    mode="json"
                )
                for result
                in results
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)

    print(
        "WALKTHROUGH PERCEPTION PREVIEW COMPLETE"
    )

    print("=" * 72)

    print(
        "Frames processed:",
        len(results),
    )

    print(
        "Saved private preview:",
        output_path,
    )


if __name__ == "__main__":
    main()
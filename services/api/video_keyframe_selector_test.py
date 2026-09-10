import tempfile
from pathlib import Path

import cv2
import numpy as np

from video_keyframe_selector import (
    select_video_keyframes,
)


FPS = 12.0
TOTAL_FRAMES = 240

WIDTH = 320
HEIGHT = 180

SEGMENT_COUNT = 8
SEGMENT_LENGTH = (
    TOTAL_FRAMES
    // SEGMENT_COUNT
)


def create_test_video(
    path: Path,
) -> None:
    fourcc = cv2.VideoWriter_fourcc(
        *"MJPG"
    )

    writer = cv2.VideoWriter(
        str(
            path
        ),
        fourcc,
        FPS,
        (
            WIDTH,
            HEIGHT,
        ),
    )

    if not writer.isOpened():
        raise RuntimeError(
            "Could not create synthetic video."
        )

    try:
        for frame_index in range(
            TOTAL_FRAMES
        ):
            frame = np.zeros(
                (
                    HEIGHT,
                    WIDTH,
                    3,
                ),
                dtype=np.uint8,
            )

            segment_index = (
                frame_index
                // SEGMENT_LENGTH
            )

            position_in_segment = (
                frame_index
                % SEGMENT_LENGTH
            )

            # First half of every segment is deliberately
            # low-information.
            if (
                position_in_segment
                < SEGMENT_LENGTH // 2
            ):
                frame[:] = (
                    180,
                    180,
                    180,
                )

                cv2.line(
                    frame,
                    (
                        WIDTH // 2,
                        0,
                    ),
                    (
                        WIDTH // 2,
                        HEIGHT,
                    ),
                    (
                        80,
                        80,
                        80,
                    ),
                    2,
                )

            # Second half is richer and slightly different
            # for every temporal segment.
            else:
                offset = (
                    segment_index
                    * 17
                )

                cv2.rectangle(
                    frame,
                    (
                        10
                        + offset
                        % 70,
                        20,
                    ),
                    (
                        130
                        + offset
                        % 40,
                        90,
                    ),
                    (
                        60
                        + (
                            segment_index
                            * 20
                        )
                        % 180,
                        100,
                        180,
                    ),
                    -1,
                )

                cv2.circle(
                    frame,
                    (
                        190,
                        80
                        + (
                            segment_index
                            * 9
                        )
                        % 60,
                    ),
                    30,
                    (
                        200,
                        180,
                        50,
                    ),
                    -1,
                )

                for x in range(
                    0,
                    WIDTH,
                    24,
                ):
                    y = (
                        x
                        + frame_index
                        + segment_index
                        * 13
                    ) % HEIGHT

                    cv2.circle(
                        frame,
                        (
                            x,
                            y,
                        ),
                        3,
                        (
                            255,
                            255,
                            255,
                        ),
                        -1,
                    )

            cv2.putText(
                frame,
                (
                    f"S{segment_index + 1} "
                    f"F{frame_index}"
                ),
                (
                    10,
                    HEIGHT - 15,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (
                    255,
                    255,
                    255,
                ),
                1,
                cv2.LINE_AA,
            )

            writer.write(
                frame
            )

    finally:
        writer.release()


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(
            temp
        )

        video_path = (
            root
            / "selector_test.avi"
        )

        output_dir = (
            root
            / "keyframes"
        )

        create_test_video(
            video_path
        )

        result = select_video_keyframes(
            video_path,
            output_dir,
            candidate_count=32,
            selected_count=8,
            max_long_edge=240,
        )

        assert (
            result.actual_candidate_count
            == 32
        )

        assert (
            result.actual_selected_count
            == 8
        )

        assert (
            [
                frame.segment_number
                for frame
                in result.frames
            ]
            == list(
                range(
                    1,
                    9,
                )
            )
        )

        indices = [
            frame.frame_index
            for frame
            in result.frames
        ]

        assert (
            indices
            == sorted(
                indices
            )
        )

        assert (
            len(
                set(
                    indices
                )
            )
            == 8
        )

        # Every selected frame must belong to its own temporal segment.
        for (
            expected_segment_index,
            frame,
        ) in enumerate(
            result.frames
        ):
            segment_start = int(
                expected_segment_index
                * TOTAL_FRAMES
                / 8
            )

            segment_end = int(
                (
                    expected_segment_index
                    + 1
                )
                * TOTAL_FRAMES
                / 8
            )

            assert (
                segment_start
                <= frame.frame_index
                < segment_end
            )

        # Rich second-half candidates should usually win.
        rich_half_count = 0

        for frame in result.frames:
            position = (
                frame.frame_index
                % SEGMENT_LENGTH
            )

            if (
                position
                >= SEGMENT_LENGTH // 2
            ):
                rich_half_count += 1

        assert (
            rich_half_count
            >= 7
        )

        for frame in result.frames:
            path = Path(
                frame.image_path
            )

            assert path.exists()

            image = cv2.imread(
                str(
                    path
                )
            )

            assert image is not None

            assert (
                max(
                    image.shape[0],
                    image.shape[1],
                )
                <= 240
            )

        print(
            "TEMPORALLY STRATIFIED KEYFRAME TEST: passed"
        )

        print(
            "Candidate count:",
            result.actual_candidate_count,
        )

        print(
            "Selected count:",
            result.actual_selected_count,
        )

        print(
            "Selected indices:",
            indices,
        )

        print(
            "Selected segments:",
            [
                frame.segment_number
                for frame
                in result.frames
            ],
        )

        print(
            "Rich-half selections:",
            f"{rich_half_count}/8",
        )


if __name__ == "__main__":
    main()
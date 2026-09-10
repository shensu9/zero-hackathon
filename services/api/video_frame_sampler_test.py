import tempfile
from pathlib import Path

import cv2
import numpy as np

from video_frame_sampler import (
    sample_video_frames,
)


FPS = 12.0
TOTAL_FRAMES = 120

WIDTH = 320
HEIGHT = 180

SAMPLE_COUNT = 8


def create_test_video(
    path: Path,
) -> None:
    """
    Create a synthetic 10-second video locally.

    No network access and no AI calls are used.
    """

    fourcc = cv2.VideoWriter_fourcc(
        *"MJPG"
    )

    writer = cv2.VideoWriter(
        str(path),
        fourcc,
        FPS,
        (
            WIDTH,
            HEIGHT,
        ),
    )

    if not writer.isOpened():
        raise RuntimeError(
            "OpenCV could not create "
            "the synthetic test video."
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

            # Create visible changing content so every sampled frame
            # is genuinely from a different point in the video.
            x_position = int(
                (
                    frame_index
                    / (
                        TOTAL_FRAMES
                        - 1
                    )
                )
                * (
                    WIDTH
                    - 40
                )
            ) + 20

            cv2.circle(
                frame,
                (
                    x_position,
                    HEIGHT // 2,
                ),
                15,
                (
                    255,
                    255,
                    255,
                ),
                -1,
            )

            cv2.putText(
                frame,
                f"frame {frame_index}",
                (
                    10,
                    30,
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
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
            / "walkthrough_test.avi"
        )

        frames_dir = (
            root
            / "frames"
        )

        create_test_video(
            video_path
        )

        result = sample_video_frames(
            video_path,
            frames_dir,
            sample_count=(
                SAMPLE_COUNT
            ),
        )

        assert (
            result.total_frames
            == TOTAL_FRAMES
        )

        assert abs(
            result.fps
            - FPS
        ) < 0.1

        assert (
            result.width
            == WIDTH
        )

        assert (
            result.height
            == HEIGHT
        )

        assert (
            result.actual_sample_count
            == SAMPLE_COUNT
        )

        indices = [
            frame.frame_index
            for frame
            in result.frames
        ]

        timestamps = [
            frame.timestamp_seconds
            for frame
            in result.frames
        ]

        # Every sample must be unique.
        assert (
            len(
                set(
                    indices
                )
            )
            == SAMPLE_COUNT
        )

        # Samples must move forward through the walkthrough.
        assert (
            indices
            == sorted(
                indices
            )
        )

        assert (
            timestamps
            == sorted(
                timestamps
            )
        )

        # Segment-center sampling should avoid the exact beginning
        # and exact end of this sufficiently long video.
        assert (
            indices[0]
            > 0
        )

        assert (
            indices[-1]
            < TOTAL_FRAMES - 1
        )

        for sampled in result.frames:
            image_path = Path(
                sampled.image_path
            )

            assert (
                image_path.exists()
            )

            image = cv2.imread(
                str(
                    image_path
                )
            )

            assert (
                image is not None
            )

            assert (
                image.shape[1]
                == WIDTH
            )

            assert (
                image.shape[0]
                == HEIGHT
            )

        print(
            "VIDEO FRAME SAMPLER TEST: passed"
        )

        print(
            "Video duration:",
            result.duration_seconds,
            "seconds",
        )

        print(
            "Sample indices:",
            indices,
        )

        print(
            "Sample timestamps:",
            timestamps,
        )

        print(
            "Sample count:",
            result.actual_sample_count,
        )


if __name__ == "__main__":
    main()
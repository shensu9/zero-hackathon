from pathlib import Path

import cv2
from pydantic import BaseModel, Field


DEFAULT_SAMPLE_COUNT = 8
JPEG_QUALITY = 90


class SampledVideoFrame(BaseModel):
    sample_number: int = Field(
        ge=1,
    )

    frame_index: int = Field(
        ge=0,
    )

    timestamp_seconds: float = Field(
        ge=0,
    )

    image_path: str

    width: int = Field(
        gt=0,
    )

    height: int = Field(
        gt=0,
    )


class VideoFrameSampleResult(BaseModel):
    source_video_path: str

    fps: float = Field(
        gt=0,
    )

    total_frames: int = Field(
        gt=0,
    )

    duration_seconds: float = Field(
        gt=0,
    )

    width: int = Field(
        gt=0,
    )

    height: int = Field(
        gt=0,
    )

    requested_sample_count: int = Field(
        gt=0,
    )

    actual_sample_count: int = Field(
        gt=0,
    )

    frames: list[
        SampledVideoFrame
    ]


def _choose_sample_indices(
    *,
    total_frames: int,
    sample_count: int,
) -> list[int]:
    """
    Choose deterministic, evenly distributed frames.

    Samples are taken near the center of equal video segments rather
    than directly from the first/last frame.

    Example:

        800 total frames
        8 requested samples

    roughly becomes:

        frame 50
        frame 150
        frame 250
        ...
        frame 750

    This generally gives better walkthrough coverage than including
    the opening/closing frames, which often contain camera movement.
    """

    if total_frames <= 0:
        raise ValueError(
            "total_frames must be greater than zero."
        )

    if sample_count <= 0:
        raise ValueError(
            "sample_count must be greater than zero."
        )

    actual_count = min(
        sample_count,
        total_frames,
    )

    indices = []

    for sample_index in range(
        actual_count
    ):
        position = (
            (
                sample_index
                + 0.5
            )
            * total_frames
            / actual_count
        )

        frame_index = int(
            position
        )

        frame_index = min(
            frame_index,
            total_frames - 1,
        )

        indices.append(
            frame_index
        )

    # Defensive deduplication.
    #
    # total_frames >= actual_count should already make these unique,
    # but do not allow duplicate sampled frames into perception.
    unique_indices = []

    seen = set()

    for frame_index in indices:
        if frame_index in seen:
            continue

        seen.add(
            frame_index
        )

        unique_indices.append(
            frame_index
        )

    return unique_indices


def _clear_previous_samples(
    output_dir: Path,
) -> None:
    """
    Remove only frames created by this sampler.

    Never delete arbitrary files in the destination directory.
    """

    if not output_dir.exists():
        return

    for path in output_dir.glob(
        "frame_*.jpg"
    ):
        if path.is_file():
            path.unlink()


def sample_video_frames(
    video_path,
    output_dir,
    *,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    clear_previous: bool = True,
) -> VideoFrameSampleResult:
    """
    Extract a small, deterministic set of JPEG frames from a video.

    This function performs no AI inference.

    It is intended to become the first stage of ZERO's walkthrough
    perception pipeline.
    """

    source = Path(
        video_path
    ).resolve()

    destination = Path(
        output_dir
    ).resolve()

    if not source.exists():
        raise FileNotFoundError(
            f"Video does not exist: {source}"
        )

    if not source.is_file():
        raise ValueError(
            f"Video path is not a file: {source}"
        )

    if sample_count <= 0:
        raise ValueError(
            "sample_count must be greater than zero."
        )

    capture = cv2.VideoCapture(
        str(source)
    )

    if not capture.isOpened():
        raise RuntimeError(
            f"OpenCV could not open video: {source}"
        )

    try:
        fps = float(
            capture.get(
                cv2.CAP_PROP_FPS
            )
        )

        total_frames = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )

        width = int(
            capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )

        height = int(
            capture.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
        )

        if fps <= 0:
            raise RuntimeError(
                "Video reported invalid FPS."
            )

        if total_frames <= 0:
            raise RuntimeError(
                "Video reported no readable frames."
            )

        if (
            width <= 0
            or height <= 0
        ):
            raise RuntimeError(
                "Video reported invalid dimensions."
            )

        duration_seconds = (
            total_frames
            / fps
        )

        sample_indices = (
            _choose_sample_indices(
                total_frames=total_frames,
                sample_count=sample_count,
            )
        )

        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        if clear_previous:
            _clear_previous_samples(
                destination
            )

        sampled_frames = []

        for sample_number, frame_index in enumerate(
            sample_indices,
            start=1,
        ):
            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                frame_index,
            )

            success, frame = (
                capture.read()
            )

            if (
                not success
                or frame is None
            ):
                raise RuntimeError(
                    "Failed to read sampled frame "
                    f"{frame_index} from {source}"
                )

            actual_height, actual_width = (
                frame.shape[:2]
            )

            timestamp_seconds = (
                frame_index
                / fps
            )

            filename = (
                f"frame_{sample_number:02d}_"
                f"{frame_index:06d}.jpg"
            )

            output_path = (
                destination
                / filename
            )

            write_success = cv2.imwrite(
                str(output_path),
                frame,
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    JPEG_QUALITY,
                ],
            )

            if not write_success:
                raise RuntimeError(
                    "Failed to write sampled frame: "
                    f"{output_path}"
                )

            sampled_frames.append(
                SampledVideoFrame(
                    sample_number=(
                        sample_number
                    ),

                    frame_index=(
                        frame_index
                    ),

                    timestamp_seconds=(
                        round(
                            timestamp_seconds,
                            3,
                        )
                    ),

                    image_path=(
                        str(
                            output_path
                        )
                    ),

                    width=(
                        actual_width
                    ),

                    height=(
                        actual_height
                    ),
                )
            )

    finally:
        capture.release()

    return VideoFrameSampleResult(
        source_video_path=(
            str(source)
        ),

        fps=(
            round(
                fps,
                3,
            )
        ),

        total_frames=(
            total_frames
        ),

        duration_seconds=(
            round(
                duration_seconds,
                3,
            )
        ),

        width=width,
        height=height,

        requested_sample_count=(
            sample_count
        ),

        actual_sample_count=(
            len(
                sampled_frames
            )
        ),

        frames=(
            sampled_frames
        ),
    )
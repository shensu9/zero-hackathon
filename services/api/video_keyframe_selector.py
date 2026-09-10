import math
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel, Field


DEFAULT_CANDIDATE_COUNT = 32
DEFAULT_SELECTED_COUNT = 8
DEFAULT_MAX_LONG_EDGE = 1080

JPEG_QUALITY = 90

QUALITY_WEIGHT = 0.85
DIVERSITY_WEIGHT = 0.15


class KeyframeCandidateScore(BaseModel):
    segment_number: int = Field(
        ge=1,
    )

    frame_index: int = Field(
        ge=0,
    )

    timestamp_seconds: float = Field(
        ge=0,
    )

    sharpness_score: float = Field(
        ge=0,
        le=1,
    )

    information_score: float = Field(
        ge=0,
        le=1,
    )

    quality_score: float = Field(
        ge=0,
        le=1,
    )

    selected: bool = False


class SelectedVideoKeyframe(BaseModel):
    sample_number: int = Field(
        ge=1,
    )

    segment_number: int = Field(
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

    quality_score: float = Field(
        ge=0,
        le=1,
    )

    diversity_score: float = Field(
        ge=0,
        le=1,
    )

    selection_score: float = Field(
        ge=0,
        le=1,
    )


class VideoKeyframeSelectionResult(BaseModel):
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

    source_width: int = Field(
        gt=0,
    )

    source_height: int = Field(
        gt=0,
    )

    requested_candidate_count: int = Field(
        gt=0,
    )

    actual_candidate_count: int = Field(
        gt=0,
    )

    requested_selected_count: int = Field(
        gt=0,
    )

    actual_selected_count: int = Field(
        gt=0,
    )

    candidates: list[
        KeyframeCandidateScore
    ]

    frames: list[
        SelectedVideoKeyframe
    ]


def _resize_for_analysis(
    frame: np.ndarray,
    max_long_edge: int = 480,
) -> np.ndarray:
    height, width = frame.shape[:2]

    long_edge = max(
        width,
        height,
    )

    if long_edge <= max_long_edge:
        return frame

    scale = (
        max_long_edge
        / long_edge
    )

    new_width = max(
        1,
        int(
            round(
                width
                * scale
            )
        ),
    )

    new_height = max(
        1,
        int(
            round(
                height
                * scale
            )
        ),
    )

    return cv2.resize(
        frame,
        (
            new_width,
            new_height,
        ),
        interpolation=cv2.INTER_AREA,
    )


def _resize_for_output(
    frame: np.ndarray,
    max_long_edge: int,
) -> np.ndarray:
    height, width = frame.shape[:2]

    long_edge = max(
        width,
        height,
    )

    if long_edge <= max_long_edge:
        return frame

    scale = (
        max_long_edge
        / long_edge
    )

    new_width = max(
        1,
        int(
            round(
                width
                * scale
            )
        ),
    )

    new_height = max(
        1,
        int(
            round(
                height
                * scale
            )
        ),
    )

    return cv2.resize(
        frame,
        (
            new_width,
            new_height,
        ),
        interpolation=cv2.INTER_AREA,
    )


def _entropy(
    grayscale: np.ndarray,
) -> float:
    histogram = cv2.calcHist(
        [
            grayscale
        ],
        [
            0
        ],
        None,
        [
            256
        ],
        [
            0,
            256,
        ],
    )

    probabilities = (
        histogram.ravel()
        / max(
            float(
                grayscale.size
            ),
            1.0,
        )
    )

    probabilities = probabilities[
        probabilities > 0
    ]

    if probabilities.size == 0:
        return 0.0

    entropy = -np.sum(
        probabilities
        * np.log2(
            probabilities
        )
    )

    return float(
        entropy
    )


def _build_visual_signature(
    frame: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
]:
    thumbnail = cv2.resize(
        frame,
        (
            48,
            48,
        ),
        interpolation=cv2.INTER_AREA,
    )

    thumbnail_gray = cv2.cvtColor(
        thumbnail,
        cv2.COLOR_BGR2GRAY,
    ).astype(
        np.float32
    )

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2HSV,
    )

    histogram = cv2.calcHist(
        [
            hsv
        ],
        [
            0,
            1,
        ],
        None,
        [
            24,
            24,
        ],
        [
            0,
            180,
            0,
            256,
        ],
    )

    cv2.normalize(
        histogram,
        histogram,
        0,
        1,
        cv2.NORM_MINMAX,
    )

    return (
        thumbnail_gray,
        histogram,
    )


def _visual_distance(
    candidate: dict,
    selected: dict,
) -> float:
    thumbnail_distance = float(
        np.mean(
            np.abs(
                candidate[
                    "thumbnail"
                ]
                - selected[
                    "thumbnail"
                ]
            )
        )
        / 255.0
    )

    histogram_distance = float(
        cv2.compareHist(
            candidate[
                "histogram"
            ],
            selected[
                "histogram"
            ],
            cv2.HISTCMP_BHATTACHARYYA,
        )
    )

    distance = (
        0.35
        * thumbnail_distance
        + 0.65
        * histogram_distance
    )

    return float(
        np.clip(
            distance,
            0.0,
            1.0,
        )
    )


def _min_max_normalize(
    values: list[float],
) -> list[float]:
    if not values:
        return []

    minimum = min(
        values
    )

    maximum = max(
        values
    )

    if math.isclose(
        minimum,
        maximum,
    ):
        return [
            1.0
            for _ in values
        ]

    return [
        (
            value
            - minimum
        )
        / (
            maximum
            - minimum
        )
        for value in values
    ]


def _build_segment_candidate_indices(
    *,
    total_frames: int,
    segment_count: int,
    candidate_count: int,
) -> list[
    tuple[
        int,
        int,
    ]
]:
    """
    Return:

        [
            (segment_number, frame_index),
            ...
        ]

    Every temporal segment receives candidates.

    Example:

        8 selected frames
        32 candidates

    means roughly 4 candidate frames are examined inside each of
    the 8 temporal regions.
    """

    if total_frames <= 0:
        raise ValueError(
            "total_frames must be greater than zero."
        )

    if segment_count <= 0:
        raise ValueError(
            "segment_count must be greater than zero."
        )

    if candidate_count < segment_count:
        candidate_count = (
            segment_count
        )

    actual_segments = min(
        segment_count,
        total_frames,
    )

    base_candidates = (
        candidate_count
        // actual_segments
    )

    remainder = (
        candidate_count
        % actual_segments
    )

    results = []

    for segment_index in range(
        actual_segments
    ):
        segment_number = (
            segment_index
            + 1
        )

        segment_start = int(
            segment_index
            * total_frames
            / actual_segments
        )

        segment_end_exclusive = int(
            (
                segment_index
                + 1
            )
            * total_frames
            / actual_segments
        )

        segment_end_exclusive = max(
            segment_end_exclusive,
            segment_start + 1,
        )

        segment_length = (
            segment_end_exclusive
            - segment_start
        )

        candidates_this_segment = (
            base_candidates
            + (
                1
                if segment_index
                < remainder
                else 0
            )
        )

        candidates_this_segment = min(
            candidates_this_segment,
            segment_length,
        )

        for candidate_index in range(
            candidates_this_segment
        ):
            relative_position = (
                (
                    candidate_index
                    + 0.5
                )
                * segment_length
                / candidates_this_segment
            )

            frame_index = (
                segment_start
                + int(
                    relative_position
                )
            )

            frame_index = min(
                frame_index,
                segment_end_exclusive - 1,
                total_frames - 1,
            )

            results.append(
                (
                    segment_number,
                    frame_index,
                )
            )

    # Defensive deduplication.
    unique = []

    seen = set()

    for record in results:
        if record in seen:
            continue

        seen.add(
            record
        )

        unique.append(
            record
        )

    return unique


def _clear_previous_keyframes(
    output_dir: Path,
) -> None:
    if not output_dir.exists():
        return

    for path in output_dir.glob(
        "keyframe_*.jpg"
    ):
        if path.is_file():
            path.unlink()


def _score_candidates_within_segment(
    candidates: list[dict],
) -> None:
    """
    Scores are normalized independently inside each temporal segment.

    We are not asking:

        "Which eight frames are globally most detailed?"

    We are asking:

        "Which frame best represents each portion of the walkthrough?"
    """

    sharpness_scores = (
        _min_max_normalize(
            [
                candidate[
                    "sharpness_raw"
                ]
                for candidate
                in candidates
            ]
        )
    )

    entropy_scores = (
        _min_max_normalize(
            [
                candidate[
                    "entropy_raw"
                ]
                for candidate
                in candidates
            ]
        )
    )

    edge_scores = (
        _min_max_normalize(
            [
                candidate[
                    "edge_density_raw"
                ]
                for candidate
                in candidates
            ]
        )
    )

    for index, candidate in enumerate(
        candidates
    ):
        sharpness_score = (
            sharpness_scores[
                index
            ]
        )

        information_score = (
            0.65
            * entropy_scores[
                index
            ]
            + 0.35
            * edge_scores[
                index
            ]
        )

        quality_score = (
            0.45
            * sharpness_score
            + 0.55
            * information_score
        )

        candidate[
            "sharpness_score"
        ] = float(
            np.clip(
                sharpness_score,
                0.0,
                1.0,
            )
        )

        candidate[
            "information_score"
        ] = float(
            np.clip(
                information_score,
                0.0,
                1.0,
            )
        )

        candidate[
            "quality_score"
        ] = float(
            np.clip(
                quality_score,
                0.0,
                1.0,
            )
        )


def select_video_keyframes(
    video_path,
    output_dir,
    *,
    candidate_count: int = DEFAULT_CANDIDATE_COUNT,
    selected_count: int = DEFAULT_SELECTED_COUNT,
    max_long_edge: int = DEFAULT_MAX_LONG_EDGE,
    clear_previous: bool = True,
) -> VideoKeyframeSelectionResult:
    """
    Temporally stratified walkthrough keyframe selector.

    Strategy:

        video
            ->
        divide into N temporal segments
            ->
        sample several candidates inside each segment
            ->
        choose best quality/diversity candidate from that segment
            ->
        exactly one representative frame per segment
            ->
        resize for perception

    This guarantees whole-walkthrough coverage while still rejecting
    weak/blurry frames locally.

    No AI inference is performed.
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

    if candidate_count <= 0:
        raise ValueError(
            "candidate_count must be greater than zero."
        )

    if selected_count <= 0:
        raise ValueError(
            "selected_count must be greater than zero."
        )

    if max_long_edge <= 0:
        raise ValueError(
            "max_long_edge must be greater than zero."
        )

    capture = cv2.VideoCapture(
        str(
            source
        )
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

        source_width = int(
            capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )

        source_height = int(
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
            source_width <= 0
            or source_height <= 0
        ):
            raise RuntimeError(
                "Video reported invalid dimensions."
            )

        actual_segment_count = min(
            selected_count,
            total_frames,
        )

        duration_seconds = (
            total_frames
            / fps
        )

        candidate_records = (
            _build_segment_candidate_indices(
                total_frames=(
                    total_frames
                ),
                segment_count=(
                    actual_segment_count
                ),
                candidate_count=(
                    candidate_count
                ),
            )
        )

        candidates = []

        for (
            segment_number,
            frame_index,
        ) in candidate_records:
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
                continue

            analysis_frame = (
                _resize_for_analysis(
                    frame
                )
            )

            grayscale = cv2.cvtColor(
                analysis_frame,
                cv2.COLOR_BGR2GRAY,
            )

            sharpness_raw = float(
                cv2.Laplacian(
                    grayscale,
                    cv2.CV_64F,
                ).var()
            )

            entropy_raw = _entropy(
                grayscale
            )

            edges = cv2.Canny(
                grayscale,
                70,
                160,
            )

            edge_density_raw = float(
                np.count_nonzero(
                    edges
                )
                / edges.size
            )

            (
                thumbnail,
                histogram,
            ) = _build_visual_signature(
                analysis_frame
            )

            candidates.append(
                {
                    "segment_number":
                        segment_number,

                    "frame_index":
                        frame_index,

                    "timestamp_seconds":
                        frame_index
                        / fps,

                    "sharpness_raw":
                        math.log1p(
                            sharpness_raw
                        ),

                    "entropy_raw":
                        entropy_raw,

                    "edge_density_raw":
                        edge_density_raw,

                    "thumbnail":
                        thumbnail,

                    "histogram":
                        histogram,
                }
            )

    finally:
        capture.release()

    if not candidates:
        raise RuntimeError(
            "No readable candidate frames were found."
        )

    candidates_by_segment = {}

    for candidate in candidates:
        candidates_by_segment.setdefault(
            candidate[
                "segment_number"
            ],
            [],
        ).append(
            candidate
        )

    missing_segments = [
        segment_number
        for segment_number in range(
            1,
            actual_segment_count + 1,
        )
        if segment_number
        not in candidates_by_segment
    ]

    if missing_segments:
        raise RuntimeError(
            "No readable candidate frames were found "
            f"for segments: {missing_segments}"
        )

    for segment_candidates in (
        candidates_by_segment.values()
    ):
        _score_candidates_within_segment(
            segment_candidates
        )

    # ------------------------------------------------------------------
    # CHOOSE EXACTLY ONE FRAME PER TEMPORAL SEGMENT
    # ------------------------------------------------------------------

    selected_records = []

    previously_selected = []

    for segment_number in range(
        1,
        actual_segment_count + 1,
    ):
        segment_candidates = (
            candidates_by_segment[
                segment_number
            ]
        )

        best_candidate = None
        best_diversity = 1.0
        best_selection_score = -1.0

        for candidate in segment_candidates:
            if previously_selected:
                diversity_score = min(
                    _visual_distance(
                        candidate,
                        selected,
                    )
                    for selected
                    in previously_selected
                )
            else:
                diversity_score = 1.0

            selection_score = (
                QUALITY_WEIGHT
                * candidate[
                    "quality_score"
                ]
                + DIVERSITY_WEIGHT
                * diversity_score
            )

            if (
                selection_score
                > best_selection_score
            ):
                best_candidate = (
                    candidate
                )

                best_diversity = (
                    diversity_score
                )

                best_selection_score = (
                    selection_score
                )

        if best_candidate is None:
            raise RuntimeError(
                "Could not choose a keyframe for "
                f"segment {segment_number}."
            )

        selected_records.append(
            {
                "candidate":
                    best_candidate,

                "diversity_score":
                    float(
                        np.clip(
                            best_diversity,
                            0.0,
                            1.0,
                        )
                    ),

                "selection_score":
                    float(
                        np.clip(
                            best_selection_score,
                            0.0,
                            1.0,
                        )
                    ),
            }
        )

        previously_selected.append(
            best_candidate
        )

    selected_indices = {
        record[
            "candidate"
        ][
            "frame_index"
        ]
        for record
        in selected_records
    }

    candidate_scores = []

    for candidate in sorted(
        candidates,
        key=lambda item: (
            item[
                "frame_index"
            ]
        ),
    ):
        candidate_scores.append(
            KeyframeCandidateScore(
                segment_number=(
                    candidate[
                        "segment_number"
                    ]
                ),

                frame_index=(
                    candidate[
                        "frame_index"
                    ]
                ),

                timestamp_seconds=(
                    round(
                        candidate[
                            "timestamp_seconds"
                        ],
                        3,
                    )
                ),

                sharpness_score=(
                    round(
                        candidate[
                            "sharpness_score"
                        ],
                        4,
                    )
                ),

                information_score=(
                    round(
                        candidate[
                            "information_score"
                        ],
                        4,
                    )
                ),

                quality_score=(
                    round(
                        candidate[
                            "quality_score"
                        ],
                        4,
                    )
                ),

                selected=(
                    candidate[
                        "frame_index"
                    ]
                    in selected_indices
                ),
            )
        )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    if clear_previous:
        _clear_previous_keyframes(
            destination
        )

    output_capture = cv2.VideoCapture(
        str(
            source
        )
    )

    if not output_capture.isOpened():
        raise RuntimeError(
            "OpenCV could not reopen video "
            "for selected-frame output."
        )

    selected_frames = []

    try:
        for sample_number, record in enumerate(
            selected_records,
            start=1,
        ):
            candidate = (
                record[
                    "candidate"
                ]
            )

            frame_index = (
                candidate[
                    "frame_index"
                ]
            )

            output_capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                frame_index,
            )

            success, frame = (
                output_capture.read()
            )

            if (
                not success
                or frame is None
            ):
                raise RuntimeError(
                    "Failed to reread selected "
                    f"frame {frame_index}."
                )

            frame = _resize_for_output(
                frame,
                max_long_edge=(
                    max_long_edge
                ),
            )

            height, width = (
                frame.shape[:2]
            )

            filename = (
                f"keyframe_{sample_number:02d}_"
                f"{frame_index:06d}.jpg"
            )

            output_path = (
                destination
                / filename
            )

            success = cv2.imwrite(
                str(
                    output_path
                ),
                frame,
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    JPEG_QUALITY,
                ],
            )

            if not success:
                raise RuntimeError(
                    "Failed to write keyframe: "
                    f"{output_path}"
                )

            selected_frames.append(
                SelectedVideoKeyframe(
                    sample_number=(
                        sample_number
                    ),

                    segment_number=(
                        candidate[
                            "segment_number"
                        ]
                    ),

                    frame_index=(
                        frame_index
                    ),

                    timestamp_seconds=(
                        round(
                            frame_index
                            / fps,
                            3,
                        )
                    ),

                    image_path=(
                        str(
                            output_path
                        )
                    ),

                    width=width,
                    height=height,

                    quality_score=(
                        round(
                            candidate[
                                "quality_score"
                            ],
                            4,
                        )
                    ),

                    diversity_score=(
                        round(
                            record[
                                "diversity_score"
                            ],
                            4,
                        )
                    ),

                    selection_score=(
                        round(
                            record[
                                "selection_score"
                            ],
                            4,
                        )
                    ),
                )
            )

    finally:
        output_capture.release()

    return VideoKeyframeSelectionResult(
        source_video_path=(
            str(
                source
            )
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

        source_width=(
            source_width
        ),

        source_height=(
            source_height
        ),

        requested_candidate_count=(
            candidate_count
        ),

        actual_candidate_count=(
            len(
                candidates
            )
        ),

        requested_selected_count=(
            selected_count
        ),

        actual_selected_count=(
            len(
                selected_frames
            )
        ),

        candidates=(
            candidate_scores
        ),

        frames=(
            selected_frames
        ),
    )
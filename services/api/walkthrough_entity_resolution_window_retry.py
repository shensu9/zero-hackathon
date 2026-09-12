from __future__ import annotations

import argparse

import walkthrough_entity_resolution_run as run
import walkthrough_entity_resolver as resolver


BASE_MAX_TOKENS = 8192
DEFAULT_RETRY_MAX_TOKENS = 16384


class _CompletionsProxy:
    def __init__(
        self,
        wrapped,
        retry_max_tokens: int,
    ) -> None:
        self._wrapped = wrapped
        self._retry_max_tokens = (
            retry_max_tokens
        )

    def create(
        self,
        *args,
        **kwargs,
    ):
        original_max_tokens = (
            kwargs.get(
                "max_tokens"
            )
        )

        if (
            original_max_tokens
            != BASE_MAX_TOKENS
        ):
            raise RuntimeError(
                "Entity-resolution retry expected "
                f"the production resolver to request "
                f"max_tokens={BASE_MAX_TOKENS}, "
                f"but received "
                f"{original_max_tokens!r}."
            )

        kwargs["max_tokens"] = (
            self._retry_max_tokens
        )

        print(
            "Transport retry override:"
        )
        print(
            f"  production max_tokens: "
            f"{BASE_MAX_TOKENS}"
        )
        print(
            f"  retry max_tokens:      "
            f"{self._retry_max_tokens}"
        )

        return self._wrapped.create(
            *args,
            **kwargs,
        )


class _ChatProxy:
    def __init__(
        self,
        wrapped,
        retry_max_tokens: int,
    ) -> None:
        self.completions = (
            _CompletionsProxy(
                wrapped.completions,
                retry_max_tokens,
            )
        )


class _ClientProxy:
    def __init__(
        self,
        wrapped,
        retry_max_tokens: int,
    ) -> None:
        self.chat = _ChatProxy(
            wrapped.chat,
            retry_max_tokens,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Retry one missing ZERO entity-resolution "
            "window with a larger transport token budget "
            "without modifying the production resolver."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        required=True,
        help=(
            "Walkthrough namespace such as "
            "walkthrough-02."
        ),
    )

    parser.add_argument(
        "--window",
        required=True,
        type=int,
        help=(
            "1-based identity-window number to retry."
        ),
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_RETRY_MAX_TOKENS,
        help=(
            "Temporary completion budget for this "
            "transport retry."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Inspect the target window/cache without "
            "making a model call."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if (
        args.max_tokens
        <= BASE_MAX_TOKENS
    ):
        raise ValueError(
            "--max-tokens must be greater than "
            f"{BASE_MAX_TOKENS} for a truncation retry."
        )

    walkthrough_id = (
        run.validate_walkthrough_id(
            args.walkthrough_id
        )
    )

    run.configure_walkthrough_paths(
        walkthrough_id
    )

    frames = run.load_frames()

    windows = resolver._frame_windows(
        frames
    )

    if not (
        1
        <= args.window
        <= len(windows)
    ):
        raise ValueError(
            f"--window must be between 1 and "
            f"{len(windows)}."
        )

    window = windows[
        args.window - 1
    ]

    frame_numbers = [
        frame.sample_number
        for frame
        in window
    ]

    observation_text = (
        resolver._window_observation_text(
            window
        )
    )

    cache_path = (
        resolver._cache_path_for_window(
            frames=window,
            observation_text=(
                observation_text
            ),
        )
    )

    cached = (
        resolver._load_cached_window(
            cache_path
        )
    )

    print()
    print("=" * 72)
    print(
        "ZERO ENTITY-RESOLUTION WINDOW "
        "TRANSPORT RETRY"
    )
    print("=" * 72)
    print()

    print(
        "Walkthrough:",
        walkthrough_id,
    )

    print(
        "Window:",
        args.window,
    )

    print(
        "Frames:",
        frame_numbers,
    )

    print(
        "Model:",
        resolver.MODEL,
    )

    print(
        "Cache path:",
        cache_path,
    )

    print(
        "Valid existing cache:",
        cached is not None,
    )

    print(
        "Retry max tokens:",
        args.max_tokens,
    )

    if cached is not None:
        print()
        print(
            "No retry required; this window "
            "already has a valid cache."
        )

        print(
            "Links:",
            len(
                cached.links
            ),
        )

        print(
            "Model calls: 0"
        )

        return

    if args.dry_run:
        print()
        print(
            "Missing window would require "
            "1 model call."
        )

        print(
            "Model calls executed by dry run: 0"
        )

        return

    original_get_client = (
        resolver._get_client
    )

    base_client = (
        original_get_client()
    )

    retry_client = _ClientProxy(
        base_client,
        args.max_tokens,
    )

    resolver._get_client = (
        lambda: retry_client
    )

    try:
        result, cache_hit = (
            resolver._resolve_window(
                window
            )
        )
    finally:
        resolver._get_client = (
            original_get_client
        )

    if cache_hit:
        raise RuntimeError(
            "Retry unexpectedly reported a cache hit "
            "after the preflight cache check reported "
            "the window missing."
        )

    persisted = (
        resolver._load_cached_window(
            cache_path
        )
    )

    if persisted is None:
        raise RuntimeError(
            "Transport retry returned successfully "
            "but did not produce a valid resolver "
            "window cache."
        )

    print()
    print("=" * 72)
    print(
        "WINDOW RETRY COMPLETE"
    )
    print("=" * 72)
    print()

    print(
        "Frames:",
        frame_numbers,
    )

    print(
        "Links:",
        len(
            result.links
        ),
    )

    print(
        "Valid cache persisted:",
        True,
    )

    print(
        "Model calls:",
        1,
    )

    print(
        "Cache:",
        cache_path,
    )


if __name__ == "__main__":
    main()
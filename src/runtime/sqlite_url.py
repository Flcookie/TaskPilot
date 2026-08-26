# Copyright (c) 2025 TaskPilot contributors
# SPDX-License-Identifier: MIT

def parse_sqlite_url(url: str) -> str:
    """Parse sqlite:///relative or sqlite:////absolute URLs into a filesystem path."""
    if url.startswith("sqlite:////"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        raise ValueError(
            "Unsupported SQLite URL. Use sqlite:///relative/path or sqlite:////abs/path."
        )
    return url

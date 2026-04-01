"""Entry point: `ta-web` after `pip install ".[web]"`."""

from __future__ import annotations


def main() -> None:
    import uvicorn

    uvicorn.run(
        "webapp.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )


if __name__ == "__main__":
    main()

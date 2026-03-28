from __future__ import annotations

from .app import create_application


def main() -> int:
    app, window = create_application()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

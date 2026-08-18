from qingbiao.api import app
from qingbiao.config import DEFAULT_HOST, DEFAULT_PORT, ensure_dirs


def main() -> None:
    import uvicorn

    ensure_dirs()
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT, log_level="info")


if __name__ == "__main__":
    main()

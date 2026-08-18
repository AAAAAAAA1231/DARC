from qingbiao.api import app
from qingbiao.config import DEFAULT_HOST, DEFAULT_PORT, ensure_dirs

ensure_dirs()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT, log_level="info")

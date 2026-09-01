from suite.boot import setup_sys_path

setup_sys_path()

from suite.main import main

if __name__ == "__main__":
    raise SystemExit(main())

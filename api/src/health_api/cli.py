"""Start the local health API server."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the health API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args()
    uvicorn.run("health_api.app:app", host=options.host, port=options.port)


if __name__ == "__main__":
    main()

"""Start the local catalog server."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the food catalog API and browser")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args()
    uvicorn.run("health_catalog.app:app", host=options.host, port=options.port)


if __name__ == "__main__":
    main()

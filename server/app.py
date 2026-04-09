# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""FastAPI app exposing the Incident Bridge environment."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from ..models import IncidentBridgeAction, IncidentBridgeObservation
    from .incident_bridge_env_environment import IncidentBridgeEnvironment
except (ImportError, ModuleNotFoundError):
    from models import IncidentBridgeAction, IncidentBridgeObservation
    from server.incident_bridge_env_environment import IncidentBridgeEnvironment

from fastapi import Request
from fastapi.responses import RedirectResponse


# Create the app with web interface and README integration
app = create_app(
    IncidentBridgeEnvironment,
    IncidentBridgeAction,
    IncidentBridgeObservation,
    env_name="incident_bridge_env",
    max_concurrent_envs=4,
)


@app.middleware("http")
async def redirect_root(request: Request, call_next):
    if request.url.path == "/":
        return RedirectResponse(url="/docs", status_code=307)
    return await call_next(request)


def main() -> None:
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run --project . server --port 8001
        python -m incident_bridge_env.server.app

    For production deployments, consider using uvicorn directly with
    multiple workers:
        uvicorn incident_bridge_env.server.app:app --workers 4
    """
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

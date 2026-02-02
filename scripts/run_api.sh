#!/bin/bash
# Run the FastAPI server with correct PYTHONPATH
cd "$(dirname "$0")/.."
PYTHONPATH="$(pwd)/packages:$PYTHONPATH" poetry run uvicorn pool_patrol_api.main:app --reload "$@"

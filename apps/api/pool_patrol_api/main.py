"""FastAPI application entry point."""

import sys
from pathlib import Path

# Project root is 4 levels up from this file
_project_root = Path(__file__).parent.parent.parent.parent

# Load environment variables from project root .env file
from dotenv import load_dotenv
load_dotenv(_project_root / ".env", override=True)

# Add packages directory to Python path (must be before other imports)
# This ensures pool_patrol's packages are found before any conflicting packages
_packages_dir = _project_root / "packages"
if str(_packages_dir) not in sys.path:
    sys.path.insert(0, str(_packages_dir))

# Remove any cached 'tools' module that might be from a different project
# This is needed because another project's 'tools' package may have been imported
for _mod_name in list(sys.modules.keys()):
    if _mod_name == "tools" or _mod_name.startswith("tools."):
        del sys.modules[_mod_name]

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pool_patrol_api.routers import cases, emails, employees, vanpools

app = FastAPI(
    title="Pool Patrol API",
    description="Multi-agent vanpool misuse detection system",
    version="0.1.0",
)

# Mount routers
app.include_router(vanpools.router)
app.include_router(employees.router)
app.include_router(cases.router)
app.include_router(emails.router)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Pool Patrol API", "docs": "/docs"}

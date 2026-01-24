"""Data service for loading and querying mock data."""

import json
from functools import lru_cache
from pathlib import Path

from pool_patrol_core.models import (
    Rider,
    Vanpool,
    VanpoolStatus,
)


class DataService:
    """Service for accessing mock data with query capabilities."""

    def __init__(self, mock_data_path: Path | None = None):
        """Initialize the data service.

        Args:
            mock_data_path: Path to the mock data directory.
                           Defaults to the project's mock/ folder.
        """
        if mock_data_path is None:
            # Navigate from apps/api/pool_patrol_api/services to project root
            self._mock_path = Path(__file__).parent.parent.parent.parent.parent / "mock"
        else:
            self._mock_path = mock_data_path

        # Load data on initialization
        self._vanpools: list[Vanpool] = []
        self._load_vanpools()

    def _load_vanpools(self) -> None:
        """Load vanpools from JSON file."""
        vanpools_file = self._mock_path / "vanpools.json"
        if vanpools_file.exists():
            with open(vanpools_file) as f:
                data = json.load(f)
                self._vanpools = [Vanpool(**item) for item in data]

    # =========================================================================
    # Vanpool Methods
    # =========================================================================

    def get_vanpools(
        self,
        status: VanpoolStatus | None = None,
        work_site: str | None = None,
    ) -> list[Vanpool]:
        """Get all vanpools with optional filtering.

        Args:
            status: Filter by vanpool status
            work_site: Filter by work site name (partial match)

        Returns:
            List of vanpools matching the filters
        """
        result = self._vanpools

        if status is not None:
            result = [v for v in result if v.status == status]

        if work_site is not None:
            work_site_lower = work_site.lower()
            result = [v for v in result if work_site_lower in v.work_site.lower()]

        return result

    def get_vanpool(self, vanpool_id: str) -> Vanpool | None:
        """Get a single vanpool by ID.

        Args:
            vanpool_id: The vanpool ID to look up

        Returns:
            The vanpool if found, None otherwise
        """
        for vanpool in self._vanpools:
            if vanpool.vanpool_id == vanpool_id:
                return vanpool
        return None

    def get_vanpool_riders(self, vanpool_id: str) -> list[Rider] | None:
        """Get riders for a specific vanpool.

        Args:
            vanpool_id: The vanpool ID to look up

        Returns:
            List of riders if vanpool found, None otherwise
        """
        vanpool = self.get_vanpool(vanpool_id)
        if vanpool is None:
            return None
        return vanpool.riders


@lru_cache
def get_data_service() -> DataService:
    """Get a cached instance of the data service.

    Returns:
        Singleton DataService instance
    """
    return DataService()

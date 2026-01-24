"""Dependency injection for Pool Patrol API."""

from typing import Annotated

from fastapi import Depends

from pool_patrol_api.services.data_service import DataService, get_data_service

# Type alias for injecting DataService
DataServiceDep = Annotated[DataService, Depends(get_data_service)]

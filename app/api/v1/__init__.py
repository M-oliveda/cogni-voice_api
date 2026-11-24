# SPDX-License-Identifier: GPL-2.0-or-later
"""Version 1 of the public REST API, mounted under ``/api/v1``."""

from fastapi import APIRouter

from app.api.docs import ApiVersion
from app.core.errors import COMMON_ERROR_RESPONSES

API_V1_PREFIX = "/api/v1"
API_V1 = ApiVersion(major=1, prefix=API_V1_PREFIX)

# Feature routers are included here as their phases land (MASTERPLAN.md §7).
router = APIRouter(prefix=API_V1_PREFIX, responses=COMMON_ERROR_RESPONSES)

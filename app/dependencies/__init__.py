# SPDX-License-Identifier: GPL-2.0-or-later
"""FastAPI dependencies: settings, database sessions, and providers.

Everything is taken from ``app.state`` (built by the application lifespan), so
tests replace any of it with ``app.dependency_overrides``.
"""

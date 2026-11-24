# SPDX-License-Identifier: GPL-2.0-or-later
"""Python 3.14 compatibility smoke tests for the pinned dependency set.

Each test imports a dependency and exercises it briefly. Warnings are errors
(``filterwarnings`` in ``pyproject.toml``), so a dependency that misbehaves on
Python 3.14 fails here first (MASTERPLAN.md §25, Phase 0).
"""

# Imports live inside each test so one broken dependency fails only its own
# test instead of the collection of the whole module.
# pylint: disable=import-outside-toplevel

import secrets
import subprocess
import sys
from typing import TypedDict

import pytest


def test_fastapi_serves_a_request() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    api = FastAPI()

    @api.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(api) as client:
        assert client.get("/ping").json() == {"status": "ok"}


def test_sqlalchemy_async_engine_with_asyncpg_and_pgvector() -> None:
    import asyncpg  # noqa: F401  # pylint: disable=unused-import
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import Column, Integer, MetaData, Table, select
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/db")
    table = Table(
        "vectors",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("embedding", Vector(3)),
    )
    query = select(table.c.embedding.cosine_distance([1.0, 0.0, 0.0]))
    sql = str(query.compile(dialect=engine.dialect))
    assert "<=>" in sql
    assert engine.dialect.driver == "asyncpg"


def test_alembic_config_loads() -> None:
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", "migrations")
    assert config.get_main_option("script_location") == "migrations"


def test_langgraph_compiles_and_runs_a_graph() -> None:
    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        count: int

    def increment(state: State) -> State:
        return {"count": state["count"] + 1}

    builder = StateGraph(State)
    builder.add_node("increment", increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    assert builder.compile().invoke({"count": 1}) == {"count": 2}


def test_langgraph_postgres_checkpointer_imports() -> None:
    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    assert AsyncPostgresSaver.__name__ == "AsyncPostgresSaver"
    # The bundled libpq must load without a system library (slim images).
    assert psycopg.pq.__impl__ == "binary"


def test_provider_integrations_build_models_offline() -> None:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_ollama import ChatOllama

    gemini = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", api_key="test")
    ollama = ChatOllama(model="llama3.2:3b", base_url="http://localhost:11434")
    assert gemini.model.endswith("gemini-2.5-flash-lite")
    assert ollama.model == "llama3.2:3b"


def test_cloud_tasks_client_types_import() -> None:
    from google.cloud import tasks_v2

    task = tasks_v2.Task(http_request=tasks_v2.HttpRequest(url="https://x.test"))
    # proto-plus fields are resolved at runtime, so pylint cannot see them.
    assert task.http_request.url == "https://x.test"  # pylint: disable=no-member


def test_toon_format_round_trip() -> None:
    from toon_format import decode, encode

    data = {"items": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}
    assert decode(encode(data)) == data


def test_opentelemetry_sdk_records_a_span() -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer("smoke").start_as_current_span("span"):
        pass
    assert [span.name for span in exporter.get_finished_spans()] == ["span"]


def test_pyjwt_round_trip() -> None:
    import jwt

    key = secrets.token_urlsafe(32)
    token = jwt.encode({"sub": "user"}, key, "HS256")
    claims = jwt.decode(token, key, ["HS256"])
    assert claims == {"sub": "user"}


def test_test_tooling_imports() -> None:
    import hypothesis
    import respx
    from testcontainers.community.postgres import PostgresContainer

    assert hypothesis.__version__
    assert respx.__version__
    assert PostgresContainer.__name__ == "PostgresContainer"


# Same allowlist as ``filterwarnings`` in pyproject.toml, applied in a fresh
# interpreter.
ISOLATED_IMPORT = """
import importlib, sys, warnings
warnings.simplefilter("error")
for module in ("langsmith", "deepeval"):
    warnings.filterwarnings(
        "ignore",
        message="'asyncio.iscoroutinefunction' is deprecated",
        category=DeprecationWarning,
        module=module + r"\\..*",
    )
importlib.import_module(sys.argv[1])
"""


@pytest.mark.parametrize(
    "module",
    [
        # Locust monkey-patches the process with gevent on import, and DeepEval
        # configures telemetry; both are imported in a separate interpreter.
        "locust",
        "deepeval",
    ],
)
def test_isolated_tool_imports_cleanly(module: str) -> None:
    result = subprocess.run(  # nosec B603 - fixed interpreter and module names
        [sys.executable, "-c", ISOLATED_IMPORT, module],
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
        env={"DEEPEVAL_TELEMETRY_OPT_OUT": "YES", "PATH": ""},
    )
    assert result.returncode == 0, result.stderr

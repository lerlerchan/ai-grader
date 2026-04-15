import os
from typing import Any

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("ai-grader")
    group.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run tests that require a live Ollama server and local model.",
    )
    group.addoption(
        "--ollama-host",
        action="store",
        default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        help="Ollama API host for live integration tests.",
    )
    group.addoption(
        "--ollama-model",
        action="store",
        default=os.environ.get("AI_GRADER_TEST_MODEL", "gemma4:12b"),
        help="Local Ollama model to use for live integration tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires a live Ollama server and local model",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(
        reason="needs --run-integration to run live Ollama tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def ollama_host(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--ollama-host"))


@pytest.fixture(scope="session")
def ollama_model(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--ollama-model"))


@pytest.fixture(scope="session")
def live_ollama_client(ollama_host: str, ollama_model: str) -> Any:
    import ollama

    client = ollama.Client(host=ollama_host)

    try:
        response = client.list()
    except Exception as exc:
        pytest.fail(
            f"Cannot reach Ollama at {ollama_host}: {exc}. "
            "Start it with `ollama serve` before running integration tests."
        )

    if isinstance(response, dict):
        models = response.get("models", [])
    else:
        models = getattr(response, "models", [])

    available_models = set()
    for model in models:
        if isinstance(model, dict):
            name = model.get("model") or model.get("name")
        else:
            name = getattr(model, "model", None) or getattr(model, "name", None)
        if name:
            available_models.add(name)

    if ollama_model not in available_models:
        pytest.fail(
            f"Model '{ollama_model}' is not available in Ollama. "
            f"Available models: {sorted(m for m in available_models if m)}"
        )

    return client

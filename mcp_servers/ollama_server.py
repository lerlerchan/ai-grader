"""
FastMCP server providing tools for interacting with Ollama.

This server wraps the Ollama API and exposes the following tools:
- list_models: List available models on the Ollama instance
- generate_text: Send a prompt and get a response
- chat: Send a chat message with system and user context
- pull_model: Pull/download a model from Ollama
- check_health: Verify Ollama connectivity
"""

import os
from typing import Any, Optional

import ollama
from mcp.server.fastmcp import FastMCP

server = FastMCP("ollama-server")


def _get_ollama_host() -> str:
    """Get Ollama host from environment or use default."""
    return os.getenv("OLLAMA_HOST", "http://localhost:11434")


@server.tool()
def check_health() -> dict[str, Any]:
    """
    Verify Ollama connectivity and health.

    Checks if the Ollama instance is running and accessible at the configured host.

    Returns:
        dict: {"healthy": bool, "host": str, "error": str (optional)}
    """
    host = _get_ollama_host()
    try:
        client = ollama.Client(host=host)
        client.list()
        return {
            "healthy": True,
            "host": host,
        }
    except Exception as e:
        return {
            "healthy": False,
            "host": host,
            "error": str(e),
        }


@server.tool()
def list_models() -> dict[str, Any]:
    """
    List all available models on the Ollama instance.

    Returns:
        dict: {
            "models": [{"name": str, "size": int, "modified": str}, ...],
            "error": str (optional)
        }
    """
    host = _get_ollama_host()
    try:
        client = ollama.Client(host=host)
        response = client.list()
        models = []
        if hasattr(response, "models") and response.models:
            for model in response.models:
                models.append(
                    {
                        "name": model.model,
                        "size": model.size,
                        "modified": model.modified_at,
                    }
                )
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


@server.tool()
def generate_text(
    model: str,
    prompt: str,
    temperature: Optional[float] = None,
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
) -> dict[str, Any]:
    """
    Send a prompt to an Ollama model and get a text response.

    Args:
        model: Name of the model to use (e.g., "gemma4:12b")
        prompt: The input prompt/question
        temperature: Sampling temperature (0.0-1.0, controls randomness)
        top_k: Number of top tokens to consider
        top_p: Nucleus sampling parameter

    Returns:
        dict: {
            "response": str,
            "model": str,
            "done": bool,
            "error": str (optional)
        }
    """
    host = _get_ollama_host()
    try:
        client = ollama.Client(host=host)
        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        if top_k is not None:
            options["top_k"] = top_k
        if top_p is not None:
            options["top_p"] = top_p

        response = client.generate(
            model=model,
            prompt=prompt,
            stream=False,
            options=options if options else None,
        )

        return {
            "response": response["response"],
            "model": response.get("model", model),
            "done": response.get("done", True),
        }
    except Exception as e:
        return {
            "response": "",
            "model": model,
            "done": False,
            "error": str(e),
        }


@server.tool()
def chat(
    model: str,
    system: str,
    user_message: str,
    temperature: Optional[float] = None,
) -> dict[str, Any]:
    """
    Send a chat message with system and user context to an Ollama model.

    Args:
        model: Name of the model to use (e.g., "gemma4:12b")
        system: System prompt that defines the assistant's behavior
        user_message: The user's message/question
        temperature: Sampling temperature (0.0-1.0, controls randomness)

    Returns:
        dict: {
            "response": str,
            "model": str,
            "error": str (optional)
        }
    """
    host = _get_ollama_host()
    try:
        client = ollama.Client(host=host)
        options = {}
        if temperature is not None:
            options["temperature"] = temperature

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]

        response = client.chat(
            model=model,
            messages=messages,
            stream=False,
            options=options if options else None,
        )

        return {
            "response": response["message"]["content"],
            "model": response.get("model", model),
        }
    except Exception as e:
        return {
            "response": "",
            "model": model,
            "error": str(e),
        }


@server.tool()
def pull_model(model: str) -> dict[str, Any]:
    """
    Pull (download) a model from Ollama's registry.

    This downloads the specified model to the local Ollama instance.
    Large models may take several minutes to download.

    Args:
        model: Name of the model to pull (e.g., "gemma4:12b", "llama2:7b")

    Returns:
        dict: {
            "model": str,
            "status": str,
            "success": bool,
            "error": str (optional)
        }
    """
    host = _get_ollama_host()
    try:
        client = ollama.Client(host=host)
        response = client.pull(model)

        return {
            "model": model,
            "status": response.get("status", "completed"),
            "success": True,
        }
    except Exception as e:
        return {
            "model": model,
            "status": "failed",
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    server.run()

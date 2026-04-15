"""
scheme_parser.py — Load a marking scheme from any supported format.

Supported: .md, .txt, .pdf, .docx, .pptx
Falls back to raw text read for .md and .txt.
Uses MarkItDown for .pdf, .docx, .pptx.
"""

import os


def load_scheme(path: str) -> str:
    """Return the marking scheme as plain text."""
    ext = os.path.splitext(path)[1].lower()

    if ext in (".md", ".txt"):
        with open(path, encoding="utf-8") as f:
            return f.read()

    # Use MarkItDown for binary/rich formats
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(path)
        return result.text_content
    except ImportError:
        raise RuntimeError(
            "markitdown is required to read .pdf/.docx/.pptx schemes.\n"
            "Install it: pip install markitdown"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to parse marking scheme '{path}': {e}") from e

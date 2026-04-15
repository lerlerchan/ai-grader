"""
launcher.py — Entry point for packaged GUI launches.
"""

import sys


def _show_error(message: str) -> None:
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("AI Grader", message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)


def main() -> None:
    try:
        from ai_grader.gui import run

        run()
    except Exception as exc:
        _show_error(
            "AI Grader could not start.\n\n"
            f"{exc}\n\n"
            "Please make sure Ollama is installed and try again."
        )
        raise SystemExit(1) from exc

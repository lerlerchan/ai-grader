"""
cli.py — Command-line interface for ai-grader.
"""

import os
import sys

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import click
import ollama

from . import __version__
from .exporter import write_results
from .grader import grade
from .scheme_parser import load_scheme
from .submission_loader import discover, load


@click.group()
@click.version_option(__version__)
def cli():
    """ai-grader — Local AI grading assistant for teachers."""


@cli.command()
@click.option(
    "--scheme", "-s",
    required=True,
    type=click.Path(exists=True),
    help="Path to marking scheme (.md, .txt, .pdf, .docx)",
)
@click.option(
    "--submissions", "-d",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Folder containing student submission files",
)
@click.option(
    "--model", "-m",
    default="gemma4:12b",
    show_default=True,
    help="Ollama model name (must support vision for handwritten PDFs)",
)
@click.option(
    "--output", "-o",
    default="./output",
    show_default=True,
    help="Output directory for results",
)
@click.option(
    "--format", "fmt",
    default="excel,csv",
    show_default=True,
    help="Comma-separated export formats: excel, csv",
)
@click.option(
    "--questions", "-q",
    default="Q1,Q2,Q3,Q4",
    show_default=True,
    help="Comma-separated question labels to mark",
)
@click.option(
    "--ollama-host",
    default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
    show_default=True,
    help="Ollama API host (overrides OLLAMA_HOST env var)",
)
@click.option(
    "--dpi",
    default=150,
    show_default=True,
    help="DPI for PDF-to-image conversion (vision mode)",
)
def mark(scheme, submissions, model, output, fmt, questions, ollama_host, dpi):
    """Mark a folder of student submissions against a marking scheme."""

    formats = [f.strip().lower() for f in fmt.split(",")]
    question_list = [q.strip().upper() for q in questions.split(",")]

    # Verify Ollama
    try:
        client = ollama.Client(host=ollama_host)
        client.list()
    except Exception:
        click.echo(
            f"ERROR: Cannot reach Ollama at {ollama_host}\n"
            "Make sure Ollama is running:  ollama serve\n"
            f"Then pull the model:          ollama pull {model}",
            err=True,
        )
        sys.exit(1)

    # Load scheme
    click.echo(f"Loading marking scheme: {scheme}")
    try:
        scheme_text = load_scheme(scheme)
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    # Discover submissions
    submission_list = discover(submissions)
    if not submission_list:
        click.echo(f"No supported submissions found in: {submissions}")
        sys.exit(0)
    click.echo(f"Found {len(submission_list)} submission(s). Model: {model}\n")

    results = []

    for sub in submission_list:
        click.echo(f"  Marking {sub.student_id} — {sub.name} ...", nl=False)

        # Load file
        try:
            load(sub, dpi=dpi)
        except Exception as e:
            click.echo(f" FAILED (load error: {e})")
            results.append(_error_result(sub, question_list, str(e)))
            continue

        mode_tag = f"[{sub.mode}]"

        # Grade
        try:
            marks = grade(sub, scheme_text, model, ollama_host, question_list)
            q_str = " ".join(f"{q}={marks.get(q, -1)}" for q in question_list)
            total = sum(marks.get(q, -1) for q in question_list)
            click.echo(f" {q_str} → {total}/{len(question_list)*5}  {mode_tag}")
            result = {
                "student_id": sub.student_id,
                "name": sub.name,
                "reasoning": marks.get("reasoning", {}),
            }
            for q in question_list:
                result[q] = marks.get(q, -1)
            results.append(result)
        except Exception as e:
            click.echo(f" FAILED (AI error: {e})  {mode_tag}")
            results.append(_error_result(sub, question_list, str(e)))

    # Export
    written = write_results(results, output, question_list, formats)
    click.echo(f"\nDone. Results saved to:")
    for path in written:
        click.echo(f"  {path}")

    flagged = [r for r in results if any(r.get(q, -1) < 0 for q in question_list)]
    if flagged:
        click.echo(
            f"\nWARNING: {len(flagged)} submission(s) need manual review (marked -1):"
        )
        for r in flagged:
            click.echo(f"  {r['student_id']} — {r['name']}")


def _error_result(sub, questions, error_msg):
    result = {"student_id": sub.student_id, "name": sub.name, "reasoning": {}}
    for q in questions:
        result[q] = -1
        result["reasoning"][q] = error_msg if q == questions[0] else ""
    return result


def main():
    cli()

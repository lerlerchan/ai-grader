Below is a **clean, engineering‑grade `PRD.md`** you can put directly into your repo.  
It is written so that **developers, educators, and future yourself** all understand the intent, scope, and constraints.

I’ve kept it **concise, structured, and practical** — no fluff.

***

# PRD.md

## Local AI‑Assisted Automated Marking Application (Windows 11)

***

## 1. Overview

### 1.1 Product Name (Working)

**LocalMark** (working name)

### 1.2 Problem Statement

Teachers spend significant time manually grading student submissions that:

*   Come in mixed file formats (PDF, Word, text, code)
*   Are graded using marking schemes written in inconsistent, free‑form styles
*   Require repetitive, rule‑based evaluation

Cloud‑based AI grading tools pose **data privacy, compliance, and trust issues**, especially for student data.

### 1.3 Solution Summary

A **fully local, Windows 11 Python desktop application** that:

*   Accepts marking schemes in any common document format
*   Converts marking schemes into structured, machine‑readable rubrics using **Microsoft MarkItDown**
*   Batch‑grades student submissions using **locally hosted Ollama LLMs**
*   Produces transparent, exportable grading results
*   Never uploads data outside the teacher’s machine

***

## 2. Goals & Non‑Goals

### 2.1 Goals

*   ✅ Reduce grading time while preserving teacher control
*   ✅ Support arbitrary marking scheme formats
*   ✅ Ensure privacy via fully local execution
*   ✅ Provide consistent, auditable grading outputs
*   ✅ Be usable via CLI first, desktop GUI later

### 2.2 Non‑Goals

*   ❌ Replace teacher judgment
*   ❌ Provide real‑time collaborative grading
*   ❌ Guarantee “perfect” grading accuracy
*   ❌ Cloud or SaaS functionality

***

## 3. Target Users

### Primary Users

*   Secondary school teachers
*   College / foundation / diploma lecturers
*   Educators handling large volumes of written submissions

### User Constraints

*   Non‑technical or semi‑technical
*   Strong data privacy concerns
*   Windows 11 environment
*   Limited time to learn complex tools

***

## 4. User Workflow (Conceptual)

1.  Teacher inputs a marking scheme (any format)
2.  App converts scheme into normalized text (MarkItDown)
3.  App extracts structured grading rubric using LLM
4.  Teacher selects a folder of student submissions
5.  Teacher selects an Ollama model
6.  Teacher presses **Mark**
7.  App batch‑grades all submissions locally
8.  Teacher exports results (CSV / JSON / feedback files)

***

## 5. Functional Requirements

### 5.1 Marking Scheme Input

*   Accept:
    *   `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`
    *   Raw pasted text
*   Use **Microsoft MarkItDown** for conversion
*   Output normalized Markdown or plain text

***

### 5.2 Rubric Extraction

*   Convert marking scheme text into structured rubric JSON
*   Rubric includes:
    *   Total marks
    *   Criteria list
    *   Marks per criterion
    *   Descriptions (if available)
*   Rubric generation is:
    *   Deterministic
    *   Cached for reuse
    *   Editable (optional future feature)

***

### 5.3 Student Submission Handling

*   Input is a **folder**
*   Each file treated as a single submission
*   Supported formats:
    *   `.pdf`, `.docx`, `.txt`, `.md`
    *   Optional: `.py`, `.java`, `.cpp`
*   Each submission is:
    *   Converted to text using MarkItDown
    *   Associated with filename as student ID

***

### 5.4 Grading Engine

*   Uses locally running **Ollama**
*   Teacher selects model (e.g. `llama3`, `qwen`, `mistral`)
*   For each submission:
    *   Apply rubric criteria
    *   Assign marks per criterion
    *   Produce short qualitative feedback
*   Output must be **strict JSON**
*   Temperature kept low for consistency

***

### 5.5 Export & Reporting

*   Export formats:
    *   ✅ CSV (Excel compatible)
    *   ✅ JSON (full audit trail)
    *   ✅ Individual feedback text files
*   Each result includes:
    *   Student ID
    *   Criterion‑level scores
    *   Total score
    *   Feedback summary

***

## 6. CLI Interface (First‑Class Design)

The application must be fully operable from CLI.

### Example Commands

```bash
marking_app init
marking_app set-scheme ./scheme.pdf
marking_app set-submissions ./submissions/
marking_app set-model llama3:8b
marking_app mark
marking_app export-results --format csv
```

CLI is the **source of truth** even if a GUI exists later.

***

## 7. System Architecture

### 7.1 Core Modules

```text
marking_core/
 ├── cli.py                # Command dispatcher
 ├── scheme_parser.py      # MarkItDown handling
 ├── rubric_builder.py     # LLM rubric extraction
 ├── submission_loader.py # Student file ingestion
 ├── grader.py             # LLM grading logic
 ├── exporter.py           # Result export
 └── config.py             # App state & settings
```

Each module must be independently testable.

***

## 8. Technical Constraints

### Platform

*   ✅ Windows 11 only (initially)

### Runtime

*   Python 3.10+
*   Ollama must be running locally
*   No internet dependency after setup

### Libraries

*   Microsoft MarkItDown
*   Ollama local API
*   Standard Python tooling

***

## 9. Data Privacy & Security

*   ✅ No cloud calls
*   ✅ No telemetry
*   ✅ All data processed locally
*   ✅ No student data retained beyond project folder unless exported

This is a **core value proposition**, not optional.

***

## 10. Risks & Mitigations

### Risk: Ambiguous marking schemes

**Mitigation**

*   Rubric extraction step visible
*   Optional manual review before grading

### Risk: Inconsistent LLM grading

**Mitigation**

*   Low temperature
*   Structured prompts
*   Criterion‑by‑criterion scoring

### Risk: Long submissions exceed context window

**Mitigation**

*   Text chunking with aggregation
*   Per‑criterion evaluation

***

## 11. Success Metrics

*   ⏱️ ≥50% reduction in grading time
*   ✅ Zero cloud data transmission
*   📊 Outputs usable directly in Excel
*   👩‍🏫 Teachers can run without technical assistance after 1–2 uses

***

## 12. Future Enhancements (Out of Scope for MVP)

*   Desktop GUI (Tkinter / PySide)
*   Manual grade adjustment UI
*   Plagiarism detection (local)
*   Rubric templates
*   Multi‑language support

***

## 13. MVP Definition

The MVP is complete when:

*   A teacher can grade a folder of submissions using a PDF marking scheme
*   Using a selectable local Ollama model
*   And export results to CSV on Windows 11

***

If you want, next we can:

*   ✅ Turn this into a **repo structure**
*   ✅ Write **`README.md` for teachers**
*   ✅ Design **rubric extraction prompts**
*   ✅ Define **exact Ollama JSON schemas**

Tell me what to do next 👇

# Examples

This folder contains a sample marking scheme to help you get started.

## Try it

```bash
ai-grader mark \
  --scheme examples/sample_scheme.md \
  --submissions /path/to/your/submissions/ \
  --model gemma4:12b
```

## Marking scheme format

The marking scheme can be in any format:
- **Markdown** (`.md`) — simplest, write it yourself
- **PDF** — scan or export your existing scheme
- **Word** (`.docx`) — paste your existing scheme in

The only requirement: the scheme clearly states marks per question (e.g. "Q1 = 5 marks").

## Submission formats

| Format | Mode | Works for |
|--------|------|-----------|
| `.pdf` (scanned/handwritten) | Vision | Handwritten exams |
| `.pdf` (typed/digital) | Text | Digital submissions |
| `.docx` | Text | Word documents |
| `.txt` / `.md` | Text | Plain text answers |

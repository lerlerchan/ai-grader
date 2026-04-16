# AI Grader Studio — Teacher's Guide

> Grade a full class of submissions in minutes. Choose a local model or a cloud model — your choice.

---

## What is AI Grader?

AI Grader is a free tool that reads student submissions (PDF, Word, or text files) and marks them against your marking scheme automatically. It works with **local AI models** (runs entirely on your computer) or **cloud AI models** via Ollama (processed in the cloud, no setup needed for large models).

---

## Before You Begin

You need two things installed before AI Grader will work:

| Requirement | Why |
|---|---|
| Python 3.10 or newer | Runs AI Grader itself |
| Ollama | Runs the local AI model on your machine |

---

## Step 1 — Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the installer for your operating system (Windows / Mac)
3. Run the installer
   - **Windows:** tick **"Add Python to PATH"** before clicking Install
4. When finished, open a terminal (Windows: press `Win + R`, type `cmd`, press Enter)
5. Type the following and press Enter to confirm Python is installed:

```
python --version
```

You should see something like `Python 3.12.3`. If you see an error, restart your computer and try again.

---

## Step 2 — Install Ollama

1. Go to [ollama.com](https://ollama.com/) and download the installer for your OS
2. Run the installer and follow the prompts
3. Once installed, open a terminal and start the Ollama server:

```
ollama serve
```

Leave this terminal window open — Ollama must keep running while you grade.

4. Open a **second** terminal window and download an AI model:

```
ollama pull gemma3:12b
```

This downloads about 8 GB. Wait for it to finish before continuing.

> **Tip:** You only need to do steps 1–2 once. After that, just run `ollama serve` each time before grading.

> **Low-end computer?** Skip the `ollama pull` step entirely and use a **cloud model** instead (see [Choosing a Model](#choosing-a-model) below). Cloud models run on Ollama's servers — your computer only needs to run Ollama itself, not the full AI.

---

## Step 3 — Install AI Grader

1. Download `ai_grader-0.1.0-py3-none-any.whl` from the [Releases page](https://github.com/lerlerchan/ai-grader/releases/latest)
2. Open a terminal in the folder where you saved it (Windows: hold Shift, right-click the folder, choose "Open PowerShell window here")
3. Run:

```
pip install ai_grader-0.1.0-py3-none-any.whl
```

Wait for it to finish. You should see `Successfully installed ai-grader-0.1.0`.

---

## Step 4 — Launch the GUI

Make sure `ollama serve` is running (Step 2), then open a terminal and type:

```
ai-grader-gui
```

Your browser will automatically open to `http://127.0.0.1:5000`.

---

## Screen Walkthrough

### The main screen

When the app loads you will see two panels:

**Left panel (Status)** shows:
- A coloured dot at the top:
  - 🟢 **Green** — Ollama is running and at least one model is ready
  - 🔴 **Red** — Ollama is not running (go back to Step 2)
- Default settings (questions, DPI, host)

**Right panel (Start a grading run)** is where you fill in your job details.

---

### Filling in the form

#### 1. Marking scheme

Click **Choose File** and select your marking scheme document. Supported formats:

| Format | Notes |
|---|---|
| `.md` / `.txt` | Plain text or Markdown |
| `.pdf` | Text-based PDFs |
| `.docx` | Microsoft Word |
| `.pptx` | PowerPoint |

Write your scheme clearly — list each question, the maximum mark, and what a full-mark answer looks like.

#### 2. Submissions folder

Click **Browse…** to open a folder picker and navigate to the folder containing all your student submissions.

Alternatively, paste the full folder path directly into the text box, for example:
```
C:\Users\YourName\Documents\Class12A\Submissions
```

> **File naming:** AI Grader reads the student name and ID from filenames in this format:
> `FirstnameLastname_CourseCode_Year_AssessmentName_StudentID.pdf`
> Example: `JohnSmith_CS101_2025_Assignment1_12345.pdf`
> Files that don't match this pattern are still processed — the full filename is used as the student name.

#### 3. Ollama model {#choosing-a-model}

Choose a model from the dropdown. The dropdown is populated automatically from your Ollama models (local and cloud).

| Model | Type | Computer needed | Quality |
|---|---|---|---|
| `gemma3:12b` | Local | 8 GB RAM + 8 GB disk | Good |
| `gemma3:27b` | Local | 16 GB RAM + 16 GB disk | Better |
| `gemma4:12b-cloud` | ☁️ Cloud | Any — runs on Ollama servers | Good |
| `gemma4:31b-cloud` | ☁️ Cloud | Any — runs on Ollama servers | Excellent |

**Cloud models** (marked ☁️) do not need to be downloaded. If you select one that is not yet set up, AI Grader will download it automatically and show a progress message before grading starts.

> **Recommended for most teachers:** `gemma4:31b-cloud` — no large download, excellent marking quality.

#### 4. Advanced settings (optional)

Click **Advanced** to expand:

- **Questions** — comma-separated list of question labels, e.g. `Q1,Q2,Q3,Q4`. Must match what is in your marking scheme.
- **PDF DPI** — resolution for rendering scanned PDFs as images. Default 150 is fine for most cases; increase to 200–300 if text is hard to read.

---

### Starting the run

Click **Mark submissions**. The button will grey out and the right panel switches to **Live progress**.

---

### Live progress screen

While grading is running you will see:

- A **progress bar** showing how many submissions have been processed
- A **status message** updating after each student — if a cloud model is being set up for the first time, you will see *"Downloading model from Ollama — this may take a few minutes…"* before grading begins
- A **results table** with one row per student:

| Column | Meaning |
|---|---|
| Student | Student ID and name from the filename |
| Marks | Score per question (e.g. Q1: 8 · Q2: 6) |
| Total | Sum of all question marks |
| Mode | `text` (normal) or `vision` (scanned PDF) |

**Red rows** mean the AI could not parse a valid mark for that student. You should review those submissions manually.

---

### Downloading results

When grading finishes you will see **Download** buttons:

- **Download marks.xlsx** — Excel file with two sheets: Marks and Reasoning. Red cells = failed parse.
- **Download marks.csv** — simple CSV for importing into your gradebook

Click either button to save the file to your Downloads folder.

---

### Grade another batch

Click **Grade another batch** to reset the form and start a new run without restarting the app.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Red dot — "Cannot reach Ollama" | Run `ollama serve` in a terminal, then refresh the page |
| No models in dropdown | Run `ollama pull gemma3:12b` then refresh — or use a cloud model |
| Cloud model download stuck | Check your internet connection; Ollama must be running (`ollama serve`) |
| Browse button does nothing | Tkinter may be missing — type the folder path manually instead |
| Many red rows in results | Check your marking scheme is clear; try `gemma4:31b-cloud` for better accuracy |
| `pip install` fails | Make sure Python is in PATH (re-run installer, tick "Add to PATH") |
| App won't start after install | Close and reopen the terminal, then try `ai-grader-gui` again |

---

## Command-Line Interface (Advanced)

If you prefer the terminal over the GUI:

```
ai-grader mark \
  --scheme marking_scheme.md \
  --submissions ./submissions/ \
  --model gemma3:12b \
  --questions "Q1,Q2,Q3,Q4"
```

Output files (`marks.xlsx` and `marks.csv`) are saved to `./output/` by default. Use `--output` to change the destination.

Full options:

```
ai-grader mark --help
```

---

## Privacy

**Local models:** All processing happens on your own machine. No data leaves your computer.

**Cloud models:** When using a cloud model (e.g. `gemma4:31b-cloud`), submission content is sent to Ollama's cloud servers for processing. Do not use cloud models if your institution's policy prohibits sending student work to external services. For maximum privacy, use a local model.

---

*AI Grader is open-source software released under the MIT licence.*
*Source code: [github.com/lerlerchan/ai-grader](https://github.com/lerlerchan/ai-grader)*

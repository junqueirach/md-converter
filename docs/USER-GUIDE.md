# MD Converter: user guide

This is the full manual. For an overview and download, see the [README](../README.md).

A Windows desktop app that converts documents to Markdown using a choice of locally run, open-source conversion engines ("models"). It was built to prepare clean Markdown for LLM training corpora.

No cloud APIs and no telemetry: the only network calls are the ones you trigger yourself (installing a model, downloading its weights or binaries).

Current version: 0.2.21

## Supported formats and models

| Format | Models (best fit first) |
|---|---|
| PDF, text-native | PyMuPDF4LLM, Docling, marker, MinerU, Unstructured |
| PDF, scanned | marker, MinerU, PaddleOCR, Surya, Unstructured, Docling, Tesseract |
| PNG / JPG | PaddleOCR, marker, Surya, Unstructured, Tesseract |
| DOCX | MarkItDown, Mammoth, Docling, Unstructured |
| PPTX | MarkItDown, Docling, Unstructured |
| XLSX | MarkItDown, Unstructured |
| HTML / HTM | trafilatura, markdownify, html-to-markdown, Docling, Unstructured |
| EPUB | Pandoc |
| SRT / VTT | pysrt / webvtt-py |

The Advisor tab ranks the models for any file type (Best / Good / Usable / Not Recommended), and detects automatically whether a PDF is text-native or scanned. You can override that detection manually.

Light models run inside the app's own Python environment. Heavy models are large ML stacks that each get their own isolated virtual environment:

| Model | Type | Pinned version | License |
|---|---|---|---|
| PyMuPDF4LLM | Light | 1.28.2 | AGPL-3.0 / commercial |
| Tesseract (pytesseract) | Light + binary | 0.3.13 | Apache-2.0 |
| trafilatura | Light | 2.2.0 | Apache-2.0 |
| markdownify | Light | 1.2.3 | MIT |
| html-to-markdown | Light | 3.10.6 | MIT |
| MarkItDown | Light | 0.1.7 | MIT |
| Mammoth | Light | 1.12.1 | BSD-2 |
| Pandoc (pypandoc) | Light + binary | 1.17 | GPL-2.0 |
| pysrt / webvtt-py | Light | 1.1.2 / 0.5.1 | GPL-3.0 / MIT |
| Docling | Heavy | 2.119.0 | MIT |
| Unstructured | Heavy | 0.25.2 | Apache-2.0 |
| marker | Heavy | 1.10.2 | GPL-3.0 |
| MinerU | Heavy | 3.4.4 | MinerU Open Source License (Apache-2.0-based) |
| PaddleOCR | Heavy | 3.7.0 | Apache-2.0 |
| Surya OCR | Heavy | 0.17.1 | GPL-3.0 (weights: modified OpenRAIL-M) |

## Requirements

- Windows 10 or 11
- Python 3.11 or newer to run the app
- For Heavy models: Python 3.10–3.13. If none is installed, the Model Manager can install a private Python 3.12 for you (no admin rights, no changes to your system Python or PATH).
- Disk space: Light models need a few hundred MB in total; each Heavy model needs 1.5–6 GB.

## Running it

```
python md_converter.py
```

No manual `pip install` is needed. On first launch the app installs its own required packages in a small setup window, restarts itself, and asks you to choose a Base Folder for models, settings and logs. If you prefer a manual setup:

```
pip install -r requirements.txt
```

`MD Converter.bat` launches the newest `.py` in the folder with `pythonw` (no console window). Edit the folder path inside it first.

If you use the Windows `.exe` instead, unzip the release, open the `MD Converter` folder and double-click `MD Converter.exe`. Keep the whole folder together.

## How to use it

1. Model Manager: install the models you want, or click "Install all recommended (Primary) models". Every install ends with a smoke test that runs a real sample conversion; a model is only marked Installed if that test passes.
2. Convert: drag and drop files (or click "Add file(s)..."), tick one or more models, and click Convert. Each file and model pair becomes its own row in the queue, so you can compare outputs from different models side by side.
3. Output files are named `<source name> (<model name>).md` and saved next to the source, or in a custom output folder.

Failed rows have Retry and Export Log buttons. Every conversion writes a full log, and Settings has an "Open Logs Folder" button.

## Base Folder layout

```
<Base Folder>\
  envs\<model>\        isolated venv per Heavy model (plus its runner.py)
  models\<model>\      downloaded model weights
  bin\tesseract\       private Tesseract OCR binary
  bin\pandoc\          private Pandoc binary
  runtime\python312\   private Python 3.12 (only if installed from the Model Manager)
  config\settings.json app settings
  logs\                install logs, session logs, conversions\ logs
  temp\                one-time installer downloads, cleaned up automatically
```

The chosen location is remembered in `.mdconverter_location`, next to the app. On every launch the app checks what is actually on disk and updates each model's status to match.

## Timeouts

Heavy models are stopped only when they stop responding, not when they are merely slow:

- Inactivity timeout: the model is stopped if it produces no output at all for this long.
- Max runtime: an absolute safety cap for a process that keeps logging but never finishes.

Both can be changed or switched off per model in Settings. Time spent while Windows is asleep is not counted. Before a batch starts, the app warns you if available RAM looks too low for the Heavy models queued.

## Output notes for LLM corpora

- Pandoc (EPUB) produces GitHub-flavoured Markdown with one paragraph per line (`-t gfm-raw_html --wrap=none`), so it adds no hard line breaks and no Pandoc-only markup.
- Tesseract renders PDF pages at 300 dpi before OCR.
- Subtitle files become timestamped blocks.

## Building a Windows .exe

Use a clean virtual environment with `pip install -r requirements.txt pyinstaller`, then run (PowerShell):

```
pyinstaller --noconfirm --clean --noconsole --onedir --noupx --name "MD Converter" `
  --collect-all trafilatura --collect-all justext `
  --collect-all markitdown --collect-all magika `
  --collect-all customtkinter --collect-all tkinterdnd2 `
  --collect-all pymupdf --collect-all pymupdf4llm `
  md_converter.py
```

The result is the folder `dist\MD Converter\` (about 280 MB, 16 MB exe plus `_internal`). Zip it for distribution. In the .exe, Light models are bundled and cannot be installed or updated with pip. Heavy models still install into their own venvs, using a system Python 3.10–3.13 or the private Python 3.12.

## Architecture

The app is a single file, organised into fixed sections: Bootstrap, Registry, Env Manager, Settings, Advisor, Installer, Converter Runners, one GUI class per tab, and the App entry point.

- `MODEL_REGISTRY` is the single source of truth for every model: supported formats, fit ratings, version pins, license and timeouts.
- The non-GUI classes (`Advisor`, `Installer`, `EnvManager`, `Settings`) never touch a widget and can be tested on their own.
- A Heavy model is never imported by the app itself. Each venv gets a generated `runner.py`, which runs as `<venv python> runner.py <input> <output>`. Its output is streamed live to the log, and the whole process tree is killed on cancel or timeout.
- All subprocesses go through shared helpers that hide console windows and stay safe under `pythonw` or a windowed .exe.
- Every package is pinned to an exact, tested version, and pins are only bumped deliberately. GPU-capable models install CPU wheels unless an NVIDIA GPU is detected.

## Troubleshooting

- Model shows "Failed verification": click Verify or Repair/Reinstall, then Export Log (txt) for the complete output.
- Heavy model fails to build wheels: the venv is using a Python that is too new. Install Python 3.12 from the Model Manager banner and click Repair/Reinstall.
- Tesseract install: the official UB-Mannheim installer needs administrator rights, so a UAC prompt appears. Alternatively, install Tesseract yourself and click Install again; the app detects that copy and copies it into its own Base Folder.
- Files locked during Repair: close Explorer windows on the Base Folder and retry. The app also stops leftover processes running from that environment.
- marker on low-RAM machines: it runs at batch size 1 to keep peak memory down. Close other memory-heavy apps before converting long scanned books.

## Licensing note

Each model keeps its own license (see the table above). The app's own code is MIT. The Windows `.exe` bundles PyMuPDF and PyMuPDF4LLM (AGPL-3.0 unless a commercial license is bought from Artifex) and pysrt (GPL-3.0), so that binary is distributed under those licenses for those parts; the complete source is in this repository. Pandoc, marker and Surya are GPL-licensed and are downloaded by the app, not bundled.

## Changes in 0.2.21

- Fixed: Pandoc and Tesseract conversions failed even though the model showed as Installed, because the app never told the wrappers where its private binaries were.
- Fixed: Tesseract and Pandoc smoke tests now run a real conversion instead of only checking `--version`.
- Fixed: subprocesses in windowed builds (`pythonw` or `--noconsole`) could fail with "The handle is invalid", and showed console windows.
- Improved: Pandoc output (clean GFM, no line wrapping) and Tesseract PDF OCR quality (300 dpi).
- Fixed: Clean Queue now fully resets the Convert tab (files, model ticks, queue, progress, log), so newly added files get a fresh model suggestion. Suggestions also skip remembered models that are a poor fit for the file (e.g. a text-only engine for a scanned PDF).
- Fixed: SRT and VTT conversions failed because the output file name contained the "/" of "pysrt / webvtt-py". Outputs are now named `<source name> (pysrt _ webvtt-py).md`.
- Bootstrap package pins aligned with the Model Manager pins. Conversion logs now rotate, and unused settings were removed.
- Windows build: first official `.exe` release built with PyInstaller 6.22 on Python 3.12 (see "Building a Windows .exe").

## Known issues (0.2.21)

- PPTX and XLSX with MarkItDown need the extras `markitdown[pptx,xlsx]`. The `.exe` includes them. When running from source, install with `pip install -r requirements.txt` (which now lists the extras); the app's own first-launch installer still installs plain `markitdown==0.1.7`. Planned fix in the next version.
- First launch of the unsigned `.exe` can hang or close while antivirus software analyses it. Close it and start it again; later launches are normal.
- Convert tab pre-ticks the top-ranked model even if it is not installed yet (for example Docling for PDFs). Install it first in the Model Manager, or untick it.
- The Model Manager banner "Private Python runtime: Not installed" does not refresh while the app is running.
- The Model Manager button that installs a private Python 3.12 first removes any per-user Python 3.12.10 registered by the same installer. Use it only if you do not rely on that Python.

## Author

Luiz Junqueira & Claude AI, junqueira.ch@gmail.com

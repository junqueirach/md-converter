# Build Prompt: Local File-to-Markdown Converter App

Copy everything below into Claude Code (or Claude in a coding context) to generate the application.

---

## 1. Project Overview

Build a **Windows desktop application** in Python that converts files (PDF, HTML, DOCX/PPTX/XLSX, EPUB, SRT/VTT) into Markdown (`.md`). The app is for **non-technical users**, so the GUI must be simple, guided, and forgiving of errors.

The core idea: multiple conversion engines ("**models**") exist, each with different quality/speed/dependency trade-offs, and **most models can handle more than one file type**. The user can pick any installed model that supports their file — not just the "obvious" one — and an **Advisor tab** tells them, for their specific file, which installed/available model is genuinely the best choice versus merely compatible.

**Special priority for this build: model installation must be rock-solid.** Prior versions of similar apps failed here — installs that silently corrupted the environment, installs that broke other already-working models, installs that froze the GUI, or installs that reported success when the model didn't actually work. Section 6 below is written to prevent each of those specific failure modes; treat it as a hard requirement, not a suggestion.

## 2. Tech Stack & Constraints

- **Language**: Python 3.11+
- **GUI**: CustomTkinter (built on Tkinter) — modern look, still simple/lightweight
- **Platform**: Windows only for this version. No need for cross-platform abstraction.
- **Packaging**: Not required yet — app runs from source in a virtual environment for now, but write it so PyInstaller packaging is a drop-in later step, not a rewrite: never use `Path(__file__).parent`-style assumptions for locating the Base Folder or config (resolve everything through `Settings`/`EnvManager` instead, which should use `sys.executable`'s location or a fixed `%LOCALAPPDATA%`-based default, both of which survive being frozen), and avoid dynamic/string-based imports that PyInstaller's static analyzer can't detect.
- **No cloud APIs, no API keys** — every model must run fully locally.
- **Single-file application**: the entire app (GUI, registry, advisor logic, install engine, env manager, settings, converters glue) lives in **one Python file** (e.g. `md_converter.py`). Do not split into a package of modules — see Section 7 for how to keep this organized and testable despite being one file.
- **App identity** (use exactly, in the About tab and anywhere version info is shown):
  ```python
  APP_NAME = "MD Converter"
  APP_VERSION = "0.1.0"
  APP_AUTHOR = "Luiz Junqueira & Claude AI"
  APP_CONTACT = "USEReira.ch@gmail.com"
  ```

## 3. App Structure (Tabs / Menus)

### Tab 1 — Convert
- File picker (single file and batch/multi-file selection) **plus drag-and-drop**: dropping one or more files onto the Convert tab (via `tkinterdnd2`, add to `requirements.txt`) does the same thing as picking them through the file dialog — this is the single biggest ease-of-use win for a non-technical user, don't leave it out.
- Detects file extension, then shows **every model that supports that extension** (see the matrix in Section 5)
- Each model shows: install status (✅ Installed / ⬇️ Not installed / ⚠️ Installed but failed verification), and a **fit badge** for this specific file type: `Best` / `Good` / `Usable` / `Not Recommended`
- If the user picks a `Not Recommended` model, show a small inline warning explaining why, but still let them proceed
- "Convert" button; disabled if the selected model isn't installed (redirect to Model Manager instead of failing silently)
- Progress bar + live log panel (per-file status: converting / done / failed + reason)
- Output folder picker (default: same folder as source, or configurable in Settings)
- Batch queue view showing per-file status
- For `.pdf`: offer a "scanned or text-based? / detect for me" choice (heuristic: attempt text extraction first; if near-empty, treat as scanned) — changes which fit badges show as `Best`, never hides a model
- **Recent Conversions panel**: a small persisted list (last ~20 — see Section 6.8 Persistence) of source file, output path, model used, and timestamp, each row re-openable (opens the output file's containing folder, or the file itself, in Explorer). This is loaded from and saved to the same persisted state as everything else in Section 6.8 — it must survive closing and reopening the app.

### Tab 2 — Advisor
- Independent tab. User picks a file (auto-detect type + scanned/text-native heuristic for PDFs) or manually selects a file type.
- Shows every model that supports that file type, ranked `Best` → `Good` → `Usable` → `Not Recommended`, each with a one-line rationale and license badge (⚠️ for GPL/AGPL models, explained in plain language).
- A "Use this model" button jumps to Convert with that model pre-selected (routes to Model Manager first if not installed).

### First launch (onboarding sequence)
1. Prompt the user to choose the Base Folder (Section 6.0.1) before anything else happens — suggest the default, let them change it, validate it's writable.
2. Land on the Convert tab, which is empty/instructional (no models installed yet) with a clear nudge: "No models installed yet — go to Model Manager to install one" and a button that jumps straight there.
3. From Model Manager, the user installs whatever they want, one explicit action at a time (Section 6.0) — there is no forced/default install during onboarding.

### Tab 3 — Model Manager (see Section 6 for the install engine behind this tab)
- List of all models (Section 5): install status, approx. install size, license, supported file types, ⚠️-flag notes. **Install size is a static, hand-maintained estimate stored in `MODEL_REGISTRY`** (e.g. `install_size_gb: 4.2`) — never a live network lookup just to display a number before the user has asked to install anything.
- Per model: **Install**, **Cancel** (while installing), **Verify**, **Repair/Reinstall**, and **Uninstall** buttons.
- A **disk space check** before any install that needs more than ~500MB, showing what's required vs. available.
- A **live, step-by-step install log** per model (not just a spinner) — see Section 6 for the exact steps to surface.
- A **global "Install all recommended (Primary) models"** button for users who just want a working default set without picking anything — this must queue installs one at a time, not in parallel (see Section 6).
- "Check for updates" (future version, not required for v1): if built, it must follow the exact same explicit-consent pattern as install — check and report available updates, but never update a model automatically; the user reviews and clicks Update per model, same as a fresh install.

### Tab 4 — About
- Shows `APP_NAME`, `APP_VERSION`, `APP_AUTHOR`, `APP_CONTACT` exactly as defined in Section 2.
- Brief one-paragraph description of what the app does.
- List of open-source models used, with license references (reuse Section 5 data, don't duplicate by hand).

### Menu — Settings
- Default output folder for converted `.md` files
- Appearance mode: Light / Dark / System
- "Open output file automatically after conversion" toggle — when on, this opens the resulting `.md` in the **user's system-associated app** for `.md` files (`os.startfile(path)`), not an in-app preview pane; the app does not render/preview Markdown itself in v1.
- **Base Folder** — see Section 6.0, this is the single location for everything the app stores (environments, downloaded model weights, external binaries, config, logs). Editable at any time, not just on first run.
- Log verbosity (Normal / Verbose)
- **Conversion timeout** (per-file, default 10 minutes) — this is the setting referenced in Sections 6.8 and 8; it must actually appear here, not just be assumed
- Reset to defaults button

Everything the user configures, plus recent-conversion history and window state, must **persist across app restarts** — see Section 6.8 for exactly what's saved and how.

## 4. Non-Goals for v1

- No audio/video transcription support (explicitly dropped).
- No OCR language pack management UI.
- No cloud/remote conversion fallback.
- No auto-update mechanism for the app itself (`md_converter.py` self-updating) — distinct from the per-model "Check for updates" convenience feature described in Section 3, which is about updating installed model packages, not the app.

## 5. Model Capability Matrix (exact scope — do not add or substitute models)

| Model | Supports | Fit rating per type | License | ⚠️ Flag | Install weight |
|---|---|---|---|---|---|
| **Docling** | .pdf (text-native), .pdf (scanned), .docx, .pptx, .html | Best: text-native PDF · Good: DOCX, PPTX, HTML · Usable: scanned PDF | MIT | — | Heavy |
| **PyMuPDF4LLM** | .pdf (text-native) only | Best: text-native PDF · Not Recommended: scanned PDF | AGPL-3.0 / commercial | Yes | Light |
| **Unstructured (OSS)** | .pdf (text-native/scanned), .docx, .pptx, .xlsx, .html, images | Good: all listed types | Apache-2.0 | — | Heavy |
| **marker** | .pdf (scanned), .pdf (text-native), images | Best: scanned PDF · Good: text-native PDF, images | GPL-3.0 | Yes | Heavy |
| **Tesseract (pytesseract)** | .pdf (scanned, via page-image OCR), images | Usable: scanned PDF, images | Apache-2.0 | — | Light (Python) + external binary |
| **MinerU** | .pdf (scanned), .pdf (text-native, math-heavy) | Best: scientific/math-heavy scanned PDFs · Good: text-native academic PDFs | AGPL-3.0 | Yes | Heavy |
| **PaddleOCR** | images, .pdf (scanned, via page-image OCR) | Best: general image OCR, tables, multilingual · Good: scanned PDF | Apache-2.0 | — | Heavy |
| **Surya OCR** | images, .pdf (scanned, via page-image OCR) | Good: layout-aware image/scanned-PDF OCR | GPL-3.0 (open weights) | Yes | Heavy |
| **trafilatura** | .html, .htm | Best: messy/real-world web pages | Apache-2.0 | — | Light |
| **markdownify** | .html, .htm | Best: clean/structured HTML with tables | MIT | — | Light |
| **html-to-markdown** | .html, .htm | Good: spec-compliant alternative | MIT | — | Light |
| **MarkItDown** | .docx, .pptx, .xlsx | Best: all three Office formats | MIT | — | Light |
| **Mammoth** | .docx only | Good: cleaner semantic output than MarkItDown for DOCX | BSD-2 | — | Light |
| **Pandoc** | .epub | Best: only EPUB option | GPL-2.0 | Yes | Light (external binary, auto-installed) |
| **pysrt / webvtt-py + custom MD writer** | .srt, .vtt | Best: only subtitle option | GPL-3.0 / MIT | — | Light |

"Install weight" drives the isolation strategy in Section 6 — **Light** models share the app's main environment; **Heavy** models each get their own isolated environment. Note: for Tesseract and Pandoc, "Light" describes only their **Python-side package** (`pytesseract`, `pypandoc`) going into the main environment — the actual OCR engine binary and the Pandoc binary always go through the separate special-cased install path in Section 6.4, regardless of this weight column.

## 6. Model Installation Engine — Build This Exactly

This is the part prior apps got wrong. Implement every point below; each one exists to prevent a specific, real failure mode.

### 6.0 User control: nothing downloads or installs without an explicit, informed action

- **Nothing is installed automatically.** On first launch the app contains zero models — the Convert tab is empty/instructional until the user installs at least one. Do not bundle, pre-download, or silently fetch anything in the background, ever (including on app startup, on Settings changes, or "helpfully" while the user is idle).
- Every install is triggered **per model**, by the user clicking that specific model's Install button in the Model Manager. The "Install all recommended (Primary) models" convenience action (Section 3) is the *only* multi-model action, and it must show an upfront confirmation listing every model it will install, the combined download size, and the target folder — the user confirms once before anything starts, and can still cancel individual models mid-queue.
- Before starting **any single** install, show a confirmation dialog: model name, approximate download size, exact destination path (inside the Base Folder, Section 6.0.1), and license (with the ⚠️ note if flagged). The user clicks "Install" in that dialog to proceed — a model row's Install button should never kick off a download with zero confirmation step.
- Uninstall is equally explicit and equally scoped: it only ever deletes that one model's own folder under the Base Folder, never touches another model's environment, downloaded weights, or the app's own config.

#### 6.0.1 Base Folder — one root location for everything the app stores

- All app-managed data lives under a single, user-visible **Base Folder**, configurable in Settings (Section 3) and shown at first launch (default suggestion: `%LOCALAPPDATA%\MDConverter`, but let the user pick a different drive/path before installing anything, e.g. if they want models on a drive with more free space).
- Folder layout beneath the Base Folder (use exactly this structure so the Model Manager can reason about it programmatically):
  ```
  <BaseFolder>\
    envs\<model_name>\        # one isolated venv per Heavy model (Section 6.1)
    models\<model_name>\      # downloaded weights / large model files (marker, MinerU, PaddleOCR, Surya, etc.)
    bin\                      # external binaries: tesseract.exe, pandoc.exe
    config\settings.json      # app settings (Section 3)
    logs\                     # install and conversion logs, one file per session
  ```
- The Model Manager must show, per model, exactly where its files live under the Base Folder — this is what lets the user "see" what's installed and reason about disk usage, rather than trusting an opaque status dot.
- **Changing the Base Folder after models are already installed**: never do this silently or destructively. On change, show the user a choice: (a) move existing installed models/binaries to the new location automatically, (b) leave them in the old location and start fresh in the new one (existing models then show as "not installed" until reinstalled there), or (c) cancel the change. Never leave the app in a state where its config points to a Base Folder whose contents don't match what the UI claims is installed.
- Validate the chosen Base Folder before accepting it: must be writable, and warn (don't block) if available free space looks low relative to typical model sizes.
- The global "Install all recommended (Primary) models" and every individual install must always resolve their destination through the *current* Base Folder setting — never hardcode `%LOCALAPPDATA%` elsewhere in the codebase.

### 6.1 Isolation: one environment per Heavy model, not one shared environment for everything

Heavy models (Docling, Unstructured, marker, MinerU, PaddleOCR, Surya) each pull in large, version-sensitive ML stacks (PyTorch, PaddlePaddle, transformers, etc.). Installing them all into a single shared interpreter is the single most common cause of "installing model B silently breaks model A" — different models can require incompatible versions of the same underlying library.

- Give each Heavy model its **own dedicated virtual environment** under `<BaseFolder>\envs\<model_name>\` (Section 6.0.1), e.g. `<BaseFolder>\envs\marker\`, `<BaseFolder>\envs\docling\`, created with `python -m venv`.
- Light models (trafilatura, markdownify, html-to-markdown, MarkItDown, Mammoth, pysrt, webvtt-py, PyMuPDF4LLM, pytesseract, pypandoc) install into the **main app environment** — they're small and low-conflict-risk, and this keeps things simple for the common case. (`pypandoc` here is just the Python wrapper; the Pandoc binary itself is handled separately per Section 6.4.)
- The main app process **never imports** a Heavy model directly, and — since the whole app is one file that also imports `customtkinter` — a Heavy model's isolated venv **cannot simply re-run `md_converter.py`** (that venv won't have `customtkinter`, and shouldn't need it). Instead, at install time the `Installer` writes a small, self-contained **runner script** (e.g. `<BaseFolder>\envs\<model_name>\runner.py`) into that model's venv folder, generated from a string template embedded in `md_converter.py`. This runner imports only that one model's library, exposes a `convert(input_path, output_path)` function, and is invoked as `<venv_python> runner.py <input> <output>` by the main process. Keep each template minimal and dependency-free beyond the target model's own library.
- Design each Heavy model's runner template so it has no dependency on GUI code, other converters, or the rest of `md_converter.py` — it must work if copied out and run completely on its own inside that model's venv.

### 6.2 Never block the GUI thread

- Every install and every conversion runs in a background `threading.Thread` (or `subprocess.Popen` polled from a thread) — never call blocking `pip`/`subprocess` code directly on the Tkinter main thread.
- Stream subprocess stdout/stderr into a thread-safe `queue.Queue`; poll it from the main thread via `root.after(...)` to update the log widget and progress indicator. Do not touch Tkinter widgets from a worker thread.
- Every long operation must be cancellable: keep a handle to the `Popen` object and, on Cancel, terminate the full process tree (`psutil` or `taskkill /T /F /PID <pid>` on Windows) — killing just the parent process leaves orphaned pip/build subprocesses running.

### 6.3 Correct interpreter, correct pip, every time

- Always invoke `<venv_python> -m pip install ...` using the **explicit path** to that environment's `python.exe` (`sys.executable` for Light installs; the specific venv's interpreter for Heavy installs) — never bare `pip install`, which can silently install into the wrong Python if the user has multiple Pythons on PATH. This exact mistake is the most common reason these apps "work on my machine" and fail for the user.
- Before the first install in any environment, run `<venv_python> -m pip install --upgrade pip setuptools wheel` in that same environment (the same explicit-interpreter rule from the line above applies here too — never bare `python`/`pip`). Old pip/setuptools is a frequent, confusing source of build failures on newer packages.
- Default all GPU-capable installs (PyTorch/PaddlePaddle-backed models) to **CPU-only wheels** unless a GPU is detected. Detect GPU by checking for `nvidia-smi` on PATH; if absent, install CPU wheels via the correct index (e.g., `--index-url https://download.pytorch.org/whl/cpu` for Torch-based models, `paddlepaddle` — not `paddlepaddle-gpu` — for PaddleOCR). This keeps installs frictionless for the majority of users without a discrete GPU, and avoids the common failure of a CUDA-linked wheel installing on a machine with no compatible driver.
- Verify current, exact PyPI package names (`marker-pdf` vs `marker`, MinerU's actual current package name, etc.) before hardcoding them — these have changed publisher/name before. Don't assume; check.
- **Pin known-good versions**, don't install "latest" for any model. Fast-moving ML libraries (marker, MinerU, PaddleOCR, Surya, Docling, Unstructured) can ship a breaking change at any time; an app that always installs latest risks working today and silently breaking itself on a future reinstall or repair. Pin an exact, tested version for every package in both `requirements.txt` (Light models) and each Heavy model's runner-install step, and only bump those pins deliberately in a future app version.
- **Locating a usable Python interpreter for `venv` creation**: don't assume a bare `python` command is on PATH — some Windows installs only register the `py` launcher. Try, in order: the same interpreter running the main app (`sys.executable`) → `py -3.11` → `python` → `python3`, and fail with a clear, specific message (not a generic "command not found") if none of these produce a usable Python 3.11+.

### 6.4 Special-cased, non-pip components (do not treat as generic pip installs)

- **Tesseract OCR engine** (not the `pytesseract` wrapper — pip cannot install the actual binary on Windows): download the official UB-Mannheim Windows installer, run it silently (`/S`, Inno Setup-based), then verify with `tesseract --version`. Surface a clear message (not a silent failure) if UAC elevation is declined.
- **Pandoc**: use `pypandoc.download_pandoc()` — fully automatable, no admin needed.
- **marker / MinerU model weights**: first run downloads multi-GB files from Hugging Face after the pip install completes. Treat this as its own tracked step in the install log ("Step 3 of 3: downloading model weights, ~X GB") with real byte-progress where the download library supports it — don't let the UI look "stuck" during a multi-minute download.

### 6.5 Verify, don't just trust the exit code

- `pip install` returning exit code 0 does not mean the model actually works (a missing system dependency, a partially-downloaded wheel cache, or a broken native extension can all still leave a non-functional install).
- After every install (Heavy or Light), run a **smoke test**: import the package (or, for Heavy models, run the isolated venv's runner script with a tiny built-in sample file) and confirm it produces real output. Only mark a model ✅ Installed after this passes. If it fails, mark it ⚠️ Installed but failed verification and show the actual error, with a one-click **Repair/Reinstall** action that removes and recreates that model's environment from scratch.

### 6.6 Resilience & disk/network

- Check available disk space before starting any install that needs more than ~500MB; warn if insufficient rather than failing halfway through a multi-GB download.
- Wrap every network call with retry logic (a few attempts with backoff) for transient failures; give a clear "no internet connection" message when appropriate rather than a raw connection-error traceback.
- Installs must be safely re-runnable: if interrupted (app closed, cancelled, network drop), clicking Install again should detect the partial state and cleanly resume or restart that model's install — never leave the app thinking a model is installed when it isn't, or vice versa.

### 6.7 Queueing

- The "Install all recommended (Primary) models" action, and any case where a user queues multiple installs, must run them **sequentially**, not in parallel. Parallel `pip install` calls (even in separate venvs) can thrash disk/network and produce confusing interleaved logs; do one at a time with a clear "Installing 2 of 5: PaddleOCR..." indicator.

### 6.8 Persistence — the app remembers its state across restarts

Everything below is saved via the `Settings` class to `<BaseFolder>\config\settings.json` and reloaded on the next launch — this is not optional polish, it's required for v1:
- Base Folder path, appearance mode, output-folder preference, auto-open toggle, log verbosity, conversion timeout value
- Recent Conversions list (Tab 1: source file, output path, model used, timestamp) — capped at ~20 entries, oldest dropped first
- Main window size and position
- Last-used model per file category, so the Convert tab defaults to whatever the user picked last time instead of resetting to blank
- **Per-model installed/verified status is not re-run on every launch.** On startup, the app checks the Base Folder's on-disk layout (Section 6.0.1) against a cached verification result in `settings.json` to populate status quickly — it does not re-execute every model's smoke test on every launch (re-verifying stays a manual action via the Model Manager's Verify button). If the cached state and the on-disk folder disagree (e.g. a model's folder has gone missing), fall back to showing "Not Installed" rather than trusting a stale cache.
- Write `settings.json` on every meaningful change, not only on app close, so a crash or forced shutdown doesn't lose state — but debounce rapid-fire changes (e.g. window resize events) rather than writing on every single one.

## 7. Architecture Guidance — Single File, Internally Organized

Everything lives in **one file** (`md_converter.py`), but structure it so the single-file constraint doesn't turn into a tangled mess:

- Use clear, consistently-ordered **comment banner sections** (e.g. `# ===== REGISTRY =====`, `# ===== ADVISOR =====`, `# ===== INSTALLER =====`, `# ===== ENV MANAGER =====`, `# ===== SETTINGS =====`, `# ===== CONVERTER RUNNERS =====`, `# ===== GUI: CONVERT TAB =====`, `# ===== GUI: ADVISOR TAB =====`, `# ===== GUI: MODEL MANAGER TAB =====`, `# ===== GUI: ABOUT TAB =====`, `# ===== GUI: SETTINGS WINDOW =====`, `# ===== APP ENTRY POINT =====`) so the file reads top-to-bottom in the same order a multi-file project would.
- Keep the same **logical separation as classes/functions**, even though they're in one file — this is what keeps it testable and maintainable:
  - `MODEL_REGISTRY` (the Section 5 capability matrix as a Python dict/dataclass structure) + small helper functions (`is_installed()`, `is_verified()`, `get_models_for_extension()`)
  - `Advisor` — pure functions/class, no GUI or subprocess calls, taking a file type (+ scanned/text-native flag) and returning ranked models with rationale
  - `EnvManager` — resolves paths under the current Base Folder, creates/locates per-model venvs
  - `Installer` — the full install engine from Section 6 (venv creation, subprocess management, cancellation, verification, repair, disk/network checks)
  - `Settings` — load/save the JSON config under `<BaseFolder>\config\settings.json`, including recent-conversion history, window geometry, and cached install/verify status (Section 6.8)
  - Converter runner functions — one per model, each a thin wrapper that either calls the model's library directly (Light models, in-process) or shells out to that model's isolated venv (Heavy models, subprocess) — see Section 6.1
  - GUI classes — one CustomTkinter frame/class per tab (`ConvertTab`, `AdvisorTab`, `ModelManagerTab`, `AboutTab`, `SettingsWindow`), instantiated by a top-level `App` class
- None of the non-GUI classes (`Advisor`, `Installer`, `EnvManager`, `Settings`, registry helpers) should import `customtkinter` or reference any widget — this is what lets them be unit-tested and is the main protection against the single-file constraint turning into unmaintainable spaghetti.
- The `if __name__ == "__main__":` block at the bottom is the only entry point; everything above it is class/function definitions only (no top-level side effects like file I/O or network calls at import time).

## 8. Error Handling & UX Details

- If a selected model isn't installed, grey out the option and point to the Model Manager tab — never let "Convert" fail silently.
- If a conversion fails, show the specific error in the batch queue row, and let the user retry with a different model for that file without restarting the batch.
- Every conversion runs with a **timeout** (configurable in Settings, sensible default e.g. 10 minutes) and is cancellable per-file from the batch queue — a hung or broken model venv converting one file must not freeze the rest of the queue or the app.
- **Output file collisions**: before writing, check if the target `.md` already exists. Default behavior: prompt once per batch with a choice (Overwrite / Skip / Auto-rename with a numeric suffix) and a "apply to all remaining conflicts in this batch" checkbox — never silently overwrite, never silently skip.
- **Extracted images/assets**: models that pull out figures/images alongside text (Docling, marker, MinerU, Unstructured) must save them to a sibling `<output_name>_assets/` folder next to the `.md` file, with the Markdown's image links pointing at that folder — never dump loose image files into the output folder unlabeled.
- ⚠️-flagged models show their license badge everywhere they appear (Convert list, Advisor tab, Model Manager) — not just once.
- `Not Recommended` fit badges show a one-line reason on hover/click.
- Every install-related error message must be human-readable (translate common pip/venv/network errors into plain language) with the raw technical detail available behind a "Show details" expander, not shown by default.
- **No telemetry**: the app makes no network calls other than the ones the user explicitly triggers (installing/verifying a model, downloading model weights/binaries). State this explicitly in the About tab and README — nothing phones home, no analytics, no crash reporting.
- **Log rotation**: cap the `logs\` folder (e.g. keep the most recent 20 session logs, or a total size cap like 100MB) and delete the oldest automatically — it must not grow unbounded over time.

## 9. Deliverables

- One file, `md_converter.py`, runnable via `python md_converter.py`, plus a `requirements.txt` for the main environment (CustomTkinter, `tkinterdnd2` for drag-and-drop, and the Light-model libraries only — Heavy models install into their own venvs at runtime, per Section 6)
- A short `README.md` covering: how to run it, the single-file-but-internally-organized structure (Section 7), how per-model environments and the Base Folder work, the Tesseract/Pandoc install caveats, the pinned-versions policy, and an explicit no-telemetry statement
- A separate `test_md_converter.py` (this one file is fine outside the single-file app itself, since it's a dev tool, not part of the shipped app) with unit tests for the registry helpers, `Advisor`, and `Installer` logic (subprocess/network layer mocked) — importable directly from `md_converter.py` since none of that logic depends on the GUI *running*. Note: because the app is single-file, importing `md_converter.py` at all still requires `customtkinter`/`tkinterdnd2` to be installed in the test environment (the module-level imports execute) — no GUI mainloop or display needs to be running, but those packages need to be present.

---

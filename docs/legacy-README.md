# MD Converter

Local, Windows-only desktop app that converts PDF, HTML, DOCX/PPTX/XLSX, EPUB, and SRT/VTT
files to Markdown using a choice of locally-run conversion engines ("models"). No cloud APIs,
no telemetry.

## Running it

```
python md_converter.py
```

That's it - no manual `pip install` needed. The first time you run it, the script
checks for its own required packages and, if any are missing, opens a small
"Setting up MD Converter..." window that installs them automatically (with a
visible progress log) and then restarts itself. After that first run, launching
is instant. `requirements.txt` is still included for anyone who prefers to set up
a venv manually (`pip install -r requirements.txt`).

Requires Python 3.11+ on Windows. (Newer Python versions, e.g. 3.14, work too, as
long as the pinned package versions in `requirements.txt` have prebuilt wheels for
that version - see the PyMuPDF note below if you ever see a pip build error.)

**How the auto-setup works, and why it's split in two:**
- `customtkinter` and `tkinterdnd2` (needed just to open the app's window at all)
  are checked the instant the script starts running, before anything else happens.
- The Light-model libraries (PyMuPDF4LLM, trafilatura, MarkItDown, etc.) are only
  checked right before the main window opens - not merely on import - so that
  importing `md_converter.py` as a library (e.g. from `test_md_converter.py`)
  never triggers a GUI or network call.
- If a Light-model library fails to install (e.g. no internet), the app still
  launches - only that specific model will show a conversion error later, the
  same as any other conversion failure.
- This auto-install is the one deliberate exception to "nothing installs without
  an explicit action" (Section 6.0 of the build spec) - that rule governs the
  Model Manager's Heavy/Light *model* installs; the app can't even show that UI
  without its own base packages present first.

## Single file, internally organized

Everything (GUI, registry, advisor logic, install engine, env manager, settings, converter
glue) lives in `md_converter.py`. It's kept maintainable despite being one file by:

- Clear comment-banner sections in a fixed order (`# ===== REGISTRY =====`,
  `# ===== ADVISOR =====`, `# ===== INSTALLER =====`, `# ===== ENV MANAGER =====`,
  `# ===== SETTINGS =====`, `# ===== CONVERTER RUNNERS =====`, GUI tabs, `# ===== APP ENTRY POINT =====`).
- The non-GUI logic (`Advisor`, `Installer`, `EnvManager`, `Settings`, registry helpers) never
  imports `customtkinter` and never touches a widget, so it's independently unit-testable.
- GUI classes are one CustomTkinter frame per tab, instantiated by a top-level `App` class.
- The `if __name__ == "__main__":` block at the bottom is the only entry point; nothing above
  it performs file I/O or network calls at import time.

`test_md_converter.py` (a separate dev-only file, not shipped with the app) imports
`md_converter.py` directly and unit-tests the registry helpers, `Advisor`, and `Installer`
(subprocess/network layer mocked). Because the app is single-file, importing it still requires
`customtkinter`/`tkinterdnd2` to be installed in the test environment (their module-level
imports execute), but no GUI mainloop or display needs to be running.

## Per-model environments & the Base Folder

Everything the app stores lives under one user-chosen **Base Folder** (suggested on first
run as `MD Converter Data` right next to `md_converter.py` itself, changeable in Settings
at any time):

```
<BaseFolder>\
  envs\<model_name>\        # one isolated venv per Heavy model
  models\<model_name>\      # downloaded weights / large model files
  bin\                      # external binaries: tesseract.exe, pandoc.exe
  temp\                     # scratch space for one-time installer downloads
                             #   (e.g. the Tesseract installer .exe) - deleted
                             #   automatically once that install succeeds or fails
  config\settings.json      # app settings
  logs\                     # install and conversion logs, one file per session
```

**Heavy** models (Docling, Unstructured, marker, MinerU, PaddleOCR, Surya) each get their own
`python -m venv` under `envs\<model>\`, because installing large, version-sensitive ML stacks
into one shared interpreter is the most common cause of "installing model B breaks model A."
The main process never imports a Heavy model directly; instead, at install time a small
self-contained `runner.py` (generated from a template embedded in `md_converter.py`) is written
into that model's venv. It's invoked as `<venv_python> runner.py <input> <output>` from a
background thread, with output streamed to the Model Manager log and the whole process tree
killed on cancel/timeout (`taskkill /T /F /PID`).

**Light** models (trafilatura, markdownify, html-to-markdown, MarkItDown, Mammoth, pysrt,
webvtt-py, PyMuPDF4LLM, pytesseract, pypandoc) install into the main app environment and run
in-process - they're small and low-conflict-risk.

Every install (Light or Heavy) is followed by a smoke test before the model is marked
"Installed" - a successful `pip install` exit code alone is not treated as proof the model
works.

## Base Folder persistence and model detection

The Base Folder you choose on first run is remembered in a tiny pointer file next to
`md_converter.py` itself (`.mdconverter_location`) - this has to live outside the Base
Folder, since the app needs to know where to look *before* it can read anything inside
it. If the setup screen ever appears unexpectedly again, check that this file wasn't
deleted or that the app wasn't moved to a different folder.

Every time the Base Folder is set (first run, or changed later in Settings), the app
scans it and updates each model's status in both directions: models whose files are
genuinely present get marked Installed even if the settings file didn't know about them
yet (e.g. you pointed at a folder you'd already used before), and models whose files are
missing get marked Not Installed. Light-model libraries are detected by checking the
app's own Python environment directly, since they aren't stored under the Base Folder at
all.

The Model Manager tab always shows a persistent "Private Python runtime: ✔/✖" status
line, independent of the compatibility warning banner below it - so you can tell at a
glance whether the app's own Python 3.12 is actually present, even if a system Python
happens to also satisfy Heavy-model compatibility right now.

## Tesseract & Pandoc caveats

These are special-cased, not generic pip installs:

- **Tesseract OCR engine**: `pytesseract` is just a Python wrapper; pip cannot install the
  actual OCR binary on Windows. The app downloads the official UB-Mannheim Windows installer
  and runs it silently (`/S`). If Windows UAC elevation is declined, Tesseract will not work
  and the app will surface that clearly rather than failing silently.
- **Pandoc**: installed automatically via `pypandoc.download_pandoc()` - no admin rights
  needed.

## Fixing "failed verification" on otherwise-successful Heavy model installs

A few of these were long-standing bugs, present since the first version, only fully
diagnosed once real installs on Windows revealed the actual failures:

- **Docling**: the `docling` pin (`2.30.0`) had drifted roughly a year behind its own
  unpinned sub-packages (`docling-core`, `docling-ibm-models`, `docling-parse`, which
  always resolve to their current release). That mismatch broke internal imports.
  Bumped `docling` to `2.118.0`, current at time of writing, so its own dependency
  ranges stay internally consistent with whatever those sub-packages resolve to.
- **MinerU**: the runner called `python -m mineru.cli`, but `mineru.cli` is a package,
  not a runnable module - this always failed with "is a package and cannot be directly
  executed" (confirmed by MinerU's own docs and a matching upstream GitHub issue). Fixed
  to use the documented `mineru` console-script instead (with a `python -m
  mineru.cli.client` fallback if the console-script wasn't generated).
- **PaddleOCR**: 3.x replaced the old `.ocr()` call (returning nested lists of boxes)
  with a `.predict()` call returning structured result objects with a `.rec_texts`
  attribute. The runner now tries `.predict()` first and falls back to the legacy
  `.ocr()` parsing if `.predict()` isn't available, so it works with either API.
- **Smoke-test timeout**: PaddleOCR's (and other Heavy models') first real run
  downloads model weights - visible directly in install logs - which can exceed a
  short timeout on a normal connection. Raised the smoke-test timeout from 300s to
  900s so a working install doesn't get marked "failed verification" just because
  the first-run download was still in progress.
- **PyTorch requiring a C++ compiler on Windows**: after the fixes above, Docling
  still failed verification with `torch._inductor.exc.InductorError: ...Compiler:
  cl is not found`. PyTorch's `torch.compile`/inductor JIT backend needs a real
  MSVC compiler on Windows, which most users don't have installed - this is a
  well-documented PyTorch-on-Windows limitation, not something specific to
  Docling. Fixed by setting `TORCHDYNAMO_DISABLE=1` / `TORCH_COMPILE_DISABLE=1`
  for every Heavy-model subprocess (smoke test and real conversion) - this forces
  eager-mode execution, which needs no compiler and is more than fast enough for
  converting a single document. The same underlying accelerate/torch import
  chain is a documented source of similar crashes in MinerU's own GitHub issues,
  so this fix likely helps there too, though it hasn't been independently
  confirmed to fully resolve MinerU's specific failure.
- **Degenerate smoke-test sample files**: the built-in PDF/PNG samples used to
  verify a Heavy model were an almost-blank stub PDF and a plain white square -
  edge-case inputs that can trip unrelated crashes deep inside a real layout or
  OCR model (e.g. a detection model finding zero regions and dividing by zero
  downstream), producing a false "failed verification" unrelated to whether the
  install itself works. Both samples now contain real, visible text ("Hello
  World 12345"), verified to actually be extractable/visible before shipping.
- **Surya OCR**: `surya.ocr.run_ocr` no longer exists in current surya-ocr
  releases - confirmed against several current usage examples. The runner now
  uses the real current API (`DetectionPredictor` / `RecognitionPredictor` /
  `FoundationPredictor`), with a fallback for the older constructor signature.
  Verified by actually running the new runner against a mocked current-API
  surya package.
- **MinerU (best-effort, not independently confirmed)**: `mineru.cli.common` -
  imported by both the console-script and `mineru.cli.client` - unconditionally
  imports the VLM backend even when only the CPU `pipeline` backend is
  requested, and that specific import chain is broken in this environment
  (matches MinerU's own reported GitHub issues about this exact failure). An
  earlier attempt stubbed out the broken VLM submodules and tried invoking
  MinerU's CLI in-process - see below for why that turned out to be the wrong
  fix, and what actually was.
- **Export Log (txt)**: every model row in Model Manager (and the Python
  runtime install window) now has an "Export Log (txt)" button. Every
  install/verify/repair attempt writes its **complete, untruncated** output to
  `<BaseFolder>\logs\<model_key>_install.log` (reset at the start of each new
  attempt), independent of whatever's practical to show in the small on-screen
  log box. This exists because every prior round of troubleshooting was
  hampered by pasted logs getting cut off at the exact line that mattered -
  exporting the file guarantees the complete text. This immediately paid off:
  full logs revealed three further real bugs below that partial logs couldn't.
- **MinerU missing `cv2`, then `torch`**: the exported log revealed the true
  cause behind the "VLM backend" failure above - `ModuleNotFoundError: No
  module named 'cv2'`. Pinning `opencv-python-headless` fixed that, but
  revealed the *next* undeclared dependency the VLM backend needs (`torch`) -
  confirming that chasing individual missing packages one at a time is the
  wrong approach here (the VLM backend, which we never use, keeps demanding
  more and heavier dependencies). Went back to stubbing out the one module
  `mineru.cli.common` actually imports from the VLM backend, so its real
  (heavy) code never executes at all - and this time, if the in-process
  attempt ever fails again, the real reason is printed and captured in the
  exported log instead of being silently swallowed and masked by a fallback.
- **Surya OCR missing `requests`, then a `transformers` incompatibility**:
  same undeclared-dependency pattern for `requests` - fixed by pinning it.
  That revealed a deeper issue: surya-ocr's own dependency range
  (`transformers>=4.56.1`, no upper bound) lets pip resolve the newest 5.x
  release, which breaks surya's model config code (`AttributeError:
  'SuryaDecoderConfig' object has no attribute 'pad_token_id'`) due to a real
  breaking change in transformers 5.x. Fixed by pinning `transformers` to the
  last 4.x release.
- **PaddleOCR / PaddlePaddle oneDNN bug**: `NotImplementedError:
  ConvertPirAttribute2RuntimeAttribute not support [...DoubleAttribute]`,
  raised from PaddlePaddle's oneDNN (MKLDNN) CPU backend - a real gap in its
  newer PIR execution path for this specific operation. Setting
  `FLAGS_use_mkldnn=0` as a subprocess-inherited environment variable did
  **not** fix this (confirmed by testing - the exact same crash recurred,
  oneDNN still active). Matching a confirmed real-world fix for this exact
  error, the flag now gets set via `os.environ[...]` inside the runner script
  itself, before importing paddle at all - that's what actually works.
- **Tesseract's installer requires admin rights, and the elevated-process
  handle proved unreliable to wait on**: `[WinError 740] The requested
  operation requires elevation` - the official UB-Mannheim Windows installer's
  own manifest requires administrator rights, and plain `subprocess.run` has
  no way to trigger the UAC consent prompt at all. The first attempt at a fix
  used `ShellExecuteExW` and waited on the returned process handle - but that
  handle can represent Windows' UAC broker rather than the real elevated
  process for the `runas` verb specifically, which is consistent with the
  install silently going quiet forever after requesting elevation. Replaced
  that with a fire-and-forget `ShellExecuteW` launch (no handle to
  misinterpret) plus polling the filesystem for the actual expected result
  file, with a 3-minute cap. Also now clears the destination folder before
  each attempt, addressing a reported symptom where the installer appeared to
  "start uninstalling" - caused by leftover files from an earlier attempt.

## Pinned-versions policy

Every model package is pinned to an exact, tested version in `requirements.txt` (Light models)
and in each Heavy model's install step (`MODEL_REGISTRY` in `md_converter.py`) - the app never
installs "latest." Fast-moving ML libraries can ship breaking changes at any time; pinning
means a working install today doesn't silently break on a future reinstall or repair. Pins are
only bumped deliberately in a future app version, after testing. GPU-capable installs
(PyTorch/PaddlePaddle-backed models) default to CPU-only wheels unless an NVIDIA GPU is
detected via `nvidia-smi`.

**Note:** package names and versions for the fast-moving Heavy models (especially `marker-pdf`
and `mineru`, which have had major version churn) were verified against PyPI at the time this
app was generated, but should be re-checked before shipping, since these projects can rename or
re-release with breaking changes.

## No telemetry

The app makes no network calls other than ones the user explicitly triggers (installing or
verifying a model, downloading model weights/binaries). No analytics, no crash reporting,
nothing phones home. This is also stated in the About tab.

## Heavy-model installs and Python version mismatches

**As of this writing, none of the Heavy models (Docling, marker, MinerU, PaddleOCR,
Surya, Unstructured) can install on Python 3.14 at all** - this is confirmed directly
from each project's own PyPI metadata and issue trackers, not a guess:
- Docling depends on `lxml<6.0.0`, and lxml only ships Python 3.14 wheels from 6.0.1
  onward - so this combination has no possible prebuilt wheel.
- marker and Surya depend on `Pillow<11.0.0`, and Pillow only ships 3.14 wheels from
  11.3.0 onward - same problem.
- MinerU's own PyPI releases explicitly declare `Requires-Python <3.14` on every
  version currently published.
- Unstructured's newest published versions cap at `Requires-Python <3.14` too.
- PaddleOCR needs PaddlePaddle, which has an open, unresolved GitHub issue requesting
  3.14 support - no wheel exists yet at all.

None of this is fixable by changing version pins on our side - it requires those
projects to ship new releases. The one thing that **does** fix it today: Heavy model
venvs are created using `py -3.12` / `-3.11` / `-3.13` (via the Windows `py` launcher,
or by probing common install locations like `C:\Python312\` directly if the launcher
isn't registered) if one of those is installed, even if it isn't the Python running
the app itself - falling back to the running interpreter only if none of those exist.

**Model Manager can now install this automatically.** If no compatible Python is
found, a banner appears at the top of the Model Manager tab with an "Install Python
3.12 automatically" button. Clicking it opens a dedicated progress window (not a
cramped inline log) showing each step - looking up the current release, downloading,
installing, verifying - with a "Done"/"Close" button that only becomes clickable once
the install finishes. It downloads the official Python 3.12 installer from python.org
(~25 MB) and installs it silently into `<BaseFolder>\runtime\python312\` - a private,
per-user copy used only by this app, with no admin rights required and no changes to
your system Python, PATH, or registry. Once installed, it's used automatically and
unconditionally for every future Heavy model install (checked before even looking at
the `py` launcher or other system Pythons), and the compatibility warnings disappear.

Note: Python only ships Windows installers for a version's *last* bugfix release with
binaries - later "security-only" patch releases are source-only and have no `.exe` at
all (this bit us once already: 3.12.13 has no Windows installer, only 3.12.12 and
earlier do). The app tries a short list of recent 3.12.x releases in order and uses
whichever one it can actually find a Windows installer for, so a single release going
source-only doesn't break this feature again.

## Packaging (future)

The app is not packaged yet, but is written so PyInstaller packaging is a drop-in step later:
the Base Folder and config paths are resolved through `EnvManager`/`Settings` (using
`sys.argv[0]`'s own folder, which works the same for a plain script or a packaged .exe),
never via `Path(__file__).parent`-style assumptions, and there are no
dynamic/string-based imports that PyInstaller's static analyzer can't detect.

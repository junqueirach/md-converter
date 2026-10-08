"""
MD Converter - Local File-to-Markdown Converter (Windows)

Single-file application. See README.md for architecture notes.
Run with: python md_converter.py
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys

# ===== BOOTSTRAP: auto-install the app's own base environment on first run =====
#
# This block runs BEFORE any third-party import, using only the standard library,
# so it works even on a completely bare Python install. It is the one deliberate
# exception to "nothing installs without an explicit action" (Section 6.0) - that
# rule governs the Model Manager's Heavy/Light *model* installs; the app can't even
# show that UI without its own base packages present, and a non-technical user
# should never have to run `pip install` by hand just to launch the app.
#
# CORE packages (customtkinter, tkinterdnd2) are required for the app to start at
# all - if either fails to install, setup stops with a clear message. OPTIONAL
# packages are the in-process Light-model libraries; if one of those fails, the app
# still launches, and only that specific model will show a conversion error later
# (same graceful failure path as any other conversion error).

_CORE_PACKAGES = [
    ("customtkinter", "customtkinter==5.2.2"),
    ("tkinterdnd2", "tkinterdnd2==0.3.0"),
]
_OPTIONAL_PACKAGES = [
    ("pymupdf4llm", "pymupdf4llm==1.28.0"),
    ("pymupdf", "pymupdf==1.28.0"),
    ("pytesseract", "pytesseract==0.3.13"),
    ("trafilatura", "trafilatura==1.12.2"),
    ("markdownify", "markdownify==0.13.1"),
    ("html_to_markdown", "html-to-markdown==1.4.0"),
    ("markitdown", "markitdown==0.0.1a4"),
    ("mammoth", "mammoth==1.8.0"),
    ("pypandoc", "pypandoc==1.13"),
    ("pysrt", "pysrt==1.1.2"),
    ("webvtt", "webvtt-py==0.5.1"),
    ("PIL", "Pillow==10.4.0"),
]


def _missing(packages: list) -> list:
    return [spec for name, spec in packages if importlib.util.find_spec(name) is None]


def _run_bootstrap_ui(missing_core: list, missing_optional: list) -> bool:
    """Installs missing packages in a plain Tkinter window (stdlib only - no
    customtkinter needed yet). Returns True if all CORE packages are present
    afterward (optional-package failures don't block launch)."""
    import queue as _queue
    import threading
    import tkinter as tk
    from tkinter import messagebox as _messagebox

    to_install = missing_core + missing_optional
    root = tk.Tk()
    root.title("MD Converter - First-time setup")
    root.geometry("580x380")
    root.resizable(False, False)

    tk.Label(root, text="Setting up MD Converter for the first time...",
             font=("Segoe UI", 11, "bold")).pack(pady=(14, 4))
    tk.Label(root, text=f"Installing {len(to_install)} required component(s). "
                        f"This can take a few minutes on first run.",
             wraplength=540, justify="center").pack(pady=(0, 8))

    log_box = tk.Text(root, height=15, width=72, state="disabled")
    log_box.pack(padx=12, pady=6)

    events: "_queue.Queue" = _queue.Queue()
    result = {"failed": []}

    def worker():
        for spec in to_install:
            events.put(f"Installing {spec} ...\n")
            try:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "pip", "install", spec],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                for line in proc.stdout:
                    events.put(line)
                proc.wait()
                if proc.returncode != 0:
                    result["failed"].append(spec)
                    events.put(f"FAILED: {spec}\n")
            except OSError as e:
                result["failed"].append(spec)
                events.put(f"FAILED: {spec} ({e})\n")
        events.put(None)

    def poll():
        try:
            while True:
                item = events.get_nowait()
                if item is None:
                    root.after(400, finish)
                    return
                log_box.configure(state="normal")
                log_box.insert("end", item)
                log_box.see("end")
                log_box.configure(state="disabled")
        except _queue.Empty:
            pass
        root.after(100, poll)

    def finish():
        failed_core = [s for s in missing_core if s in result["failed"]]
        failed_optional = [s for s in missing_optional if s in result["failed"]]
        if failed_core:
            _messagebox.showerror(
                "Setup incomplete",
                "The app couldn't finish setting up because these required "
                "components failed to install:\n\n" + "\n".join(failed_core) +
                "\n\nCheck your internet connection and try running this file again, "
                "or run 'pip install -r requirements.txt' manually.")
        elif failed_optional:
            log_box.configure(state="normal")
            log_box.insert("end", "\nMostly set. These optional components didn't install:\n  "
                                  + "\n  ".join(failed_optional) +
                                  "\nAffected file types will show a conversion error instead of "
                                  "working - re-run this file later to retry them.\n"
                                  "Starting MD Converter...\n")
            log_box.configure(state="disabled")
        else:
            log_box.configure(state="normal")
            log_box.insert("end", "\nAll set. Starting MD Converter...\n")
            log_box.configure(state="disabled")
        root.after(1200 if (failed_core or failed_optional) else 600, root.destroy)

    threading.Thread(target=worker, daemon=True).start()
    root.after(100, poll)
    root.mainloop()
    return not any(s in result["failed"] for s in missing_core)


def _bootstrap_core_only() -> None:
    """Runs unconditionally at import time - CORE packages (customtkinter,
    tkinterdnd2) are needed just to import this module at all. OPTIONAL
    (Light-model) packages are lazily imported inside functions, never at module
    scope, so checking them here would make a plain `import md_converter` (as done
    by test_md_converter.py or any tooling) block on a GUI/network operation -
    that check happens later, only when the app is actually launched (see
    APP ENTRY POINT)."""
    missing_core = _missing(_CORE_PACKAGES)
    if not missing_core:
        return  # fast path: nothing to do, no network calls
    ok = _run_bootstrap_ui(missing_core, [])
    if not ok:
        sys.exit(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)


def bootstrap_optional_packages_if_launching_app() -> None:
    """Called only from the `if __name__ == "__main__":` block - installs the
    Light-model libraries the Convert/Advisor tabs rely on, so a non-technical
    user never has to run `pip install` by hand. Never runs on a plain import."""
    missing_optional = _missing(_OPTIONAL_PACKAGES)
    if not missing_optional:
        return
    _run_bootstrap_ui([], missing_optional)
    # Optional packages are, well, optional: proceed to launch either way. Any
    # that failed will simply make that specific model raise a ConversionError
    # later (same graceful path as any other conversion failure).


_bootstrap_core_only()

# ===== STANDARD IMPORTS (guaranteed present past this point) =====

import json
import queue
import shutil
import string
import textwrap
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox, Canvas

# tkinterdnd2 (all current releases, including 0.3.0) unconditionally does
# `from tkinter import tix` to optionally offer a legacy TixTk base class. Python
# removed tkinter.tix in 3.13+, which makes that import - and therefore all of
# tkinterdnd2 - fail to import at all on newer Python, even though we never use
# TixTk. Stub out tkinter.tix before tkinterdnd2 imports it, only if the real
# module isn't present. This changes nothing on older Python where tix still
# exists; it only unblocks the import on 3.13+.
if "tkinter.tix" not in sys.modules:
    try:
        import tkinter.tix  # noqa: F401 - use the real thing if this Python still has it
    except ImportError:
        import types
        import tkinter as _tkinter_for_stub
        _tix_stub = types.ModuleType("tkinter.tix")
        _tix_stub.Tk = _tkinter_for_stub.Tk  # only attribute tkinterdnd2 touches from tix
        sys.modules["tkinter.tix"] = _tix_stub

from tkinterdnd2 import DND_FILES, TkinterDnD

# ===== APP IDENTITY =====

APP_NAME = "MD Converter"
APP_VERSION = "0.2.8"
APP_AUTHOR = "Luiz Junqueira & Claude AI"
APP_CONTACT = "junqueira.ch@gmail.com"

PYTHON_MIN_VERSION = (3, 11)

# Pinned version of the private, auto-provisioned Python runtime used for Heavy
# model venvs when no compatible system Python (3.10-3.13) is found.
#
# IMPORTANT: Python 3.12 entered "security fixes only" mode after 3.12.10
# (PEP 693) - confirmed directly against python.org's own release notes for
# 3.12.11, 3.12.12, and 3.12.13, which all state verbatim: "Python 3.12 isn't
# receiving regular bug fixes anymore, and binary installers are no longer
# provided for it. Python 3.12.10 was the last full bugfix release of
# Python 3.12 with binary installers." So 3.12.11+ have NO Windows .exe at
# all - a HEAD-request attempt against one is a guaranteed-wasted request.
# 3.12.10 is the correct primary target; the rest are older, pre-EOL bugfix
# releases kept only as a last-resort fallback.
PYTHON_RUNTIME_VERSION = "3.12.10"
PYTHON_RUNTIME_FALLBACK_VERSIONS = ["3.12.10", "3.12.9", "3.12.8", "3.12.7"]


# ===== REGISTRY =====
# The Section 5 capability matrix. Exact scope - do not add or substitute models.

class Weight(Enum):
    LIGHT = "light"
    HEAVY = "heavy"


class InstallStatus(Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    FAILED_VERIFICATION = "failed_verification"
    INSTALLING = "installing"


class FitRating(Enum):
    BEST = "Best"
    GOOD = "Good"
    USABLE = "Usable"
    NOT_RECOMMENDED = "Not Recommended"


@dataclass
class PipPin:
    """A single pip-installable dependency with a pinned version."""
    name: str
    version: str
    index_url: Optional[str] = None

    def spec(self) -> str:
        return f"{self.name}=={self.version}"


@dataclass
class ModelDef:
    key: str
    display_name: str
    weight: Weight
    license: str
    license_flag: bool  # True => show the warning badge (GPL/AGPL etc.)
    install_size_gb: float  # static, hand-maintained estimate
    supported_extensions: list  # e.g. [".pdf", ".docx"]
    fit: dict  # {(ext, variant): FitRating} where variant in {"", "scanned", "text"}
    rationale: dict  # {(ext, variant): str} one-line explanation for the Advisor
    pip_pins: list  # list[PipPin] - main packages for this model (Light: main env, Heavy: model's venv)
    special_case: Optional[str] = None  # "tesseract_binary" / "pandoc_binary" / "hf_weights" / None
    notes: str = ""
    timeout_seconds: int = 300  # inactivity timeout: killed if NO new output for this long
    max_runtime_seconds: int = 1800  # absolute safety cap regardless of activity (very large files)


def _fit_key(ext: str, variant: str = "") -> tuple:
    return (ext.lower(), variant)


MODEL_REGISTRY: dict = {
    "docling": ModelDef(
        key="docling",
        display_name="Docling",
        weight=Weight.HEAVY,
        license="MIT",
        license_flag=False,
        install_size_gb=3.5,
        supported_extensions=[".pdf", ".docx", ".pptx", ".html", ".htm"],
        fit={
            _fit_key(".pdf", "text"): FitRating.BEST,
            _fit_key(".pdf", "scanned"): FitRating.USABLE,
            _fit_key(".docx"): FitRating.GOOD,
            _fit_key(".pptx"): FitRating.GOOD,
            _fit_key(".html"): FitRating.GOOD,
            _fit_key(".htm"): FitRating.GOOD,
        },
        rationale={
            _fit_key(".pdf", "text"): "Strong layout & table understanding for born-digital PDFs.",
            _fit_key(".pdf", "scanned"): "Can handle scanned PDFs via OCR, but not its strong suit.",
            _fit_key(".docx"): "Solid general-purpose DOCX structure extraction.",
            _fit_key(".pptx"): "Solid general-purpose PPTX structure extraction.",
            _fit_key(".html"): "Decent HTML parsing, but dedicated HTML tools are lighter.",
            _fit_key(".htm"): "Decent HTML parsing, but dedicated HTML tools are lighter.",
        },
        pip_pins=[PipPin("docling", "2.118.0")],
        notes="Heavy: pulls in a full document-AI stack (layout + table models).",
        timeout_seconds=600, max_runtime_seconds=7200,
    ),
    "pymupdf4llm": ModelDef(
        key="pymupdf4llm",
        display_name="PyMuPDF4LLM",
        weight=Weight.LIGHT,
        license="AGPL-3.0 / commercial",
        license_flag=True,
        install_size_gb=0.15,
        supported_extensions=[".pdf"],
        fit={
            _fit_key(".pdf", "text"): FitRating.BEST,
            _fit_key(".pdf", "scanned"): FitRating.NOT_RECOMMENDED,
        },
        rationale={
            _fit_key(".pdf", "text"): "Fast, high-fidelity Markdown for text-native PDFs.",
            _fit_key(".pdf", "scanned"): "No OCR - scanned pages will come out blank or garbled.",
        },
        pip_pins=[PipPin("pymupdf4llm", "1.28.0"), PipPin("pymupdf", "1.28.0")],
        notes="AGPL-3.0 unless a commercial license is purchased from Artifex.",
    ),
    "unstructured": ModelDef(
        key="unstructured",
        display_name="Unstructured (OSS)",
        weight=Weight.HEAVY,
        license="Apache-2.0",
        license_flag=False,
        install_size_gb=4.0,
        supported_extensions=[".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm",
                               ".png", ".jpg", ".jpeg"],
        fit={
            _fit_key(".pdf", "text"): FitRating.GOOD,
            _fit_key(".pdf", "scanned"): FitRating.GOOD,
            _fit_key(".docx"): FitRating.GOOD,
            _fit_key(".pptx"): FitRating.GOOD,
            _fit_key(".xlsx"): FitRating.GOOD,
            _fit_key(".html"): FitRating.GOOD,
            _fit_key(".htm"): FitRating.GOOD,
            _fit_key(".png"): FitRating.GOOD,
            _fit_key(".jpg"): FitRating.GOOD,
            _fit_key(".jpeg"): FitRating.GOOD,
        },
        rationale={k: "Broad, reliable, general-purpose extraction across most formats."
                   for k in [
                       _fit_key(".pdf", "text"), _fit_key(".pdf", "scanned"), _fit_key(".docx"),
                       _fit_key(".pptx"), _fit_key(".xlsx"), _fit_key(".html"), _fit_key(".htm"),
                       _fit_key(".png"), _fit_key(".jpg"), _fit_key(".jpeg"),
                   ]},
        pip_pins=[PipPin("unstructured[all-docs]", "0.18.32")],
        notes="Heavy: broad format support pulls many optional dependencies.",
        timeout_seconds=600, max_runtime_seconds=7200,
    ),
    "marker": ModelDef(
        key="marker",
        display_name="marker",
        weight=Weight.HEAVY,
        license="GPL-3.0",
        license_flag=True,
        install_size_gb=5.0,
        supported_extensions=[".pdf", ".png", ".jpg", ".jpeg"],
        fit={
            _fit_key(".pdf", "scanned"): FitRating.BEST,
            _fit_key(".pdf", "text"): FitRating.GOOD,
            _fit_key(".png"): FitRating.GOOD,
            _fit_key(".jpg"): FitRating.GOOD,
            _fit_key(".jpeg"): FitRating.GOOD,
        },
        rationale={
            _fit_key(".pdf", "scanned"): "Purpose-built for high-quality scanned PDF conversion.",
            _fit_key(".pdf", "text"): "Very capable on text-native PDFs too, slower than lighter tools.",
            _fit_key(".png"): "Good image-to-markdown quality via its layout model.",
            _fit_key(".jpg"): "Good image-to-markdown quality via its layout model.",
            _fit_key(".jpeg"): "Good image-to-markdown quality via its layout model.",
        },
        pip_pins=[PipPin("marker-pdf", "1.10.2")],
        special_case="hf_weights",
        notes="GPL-3.0. Downloads multi-GB model weights from Hugging Face on first run. "
              "Runs 5 CPU transformer models per page (layout/detection/recognition/table/"
              "equation) - page count, not file size, drives conversion time.",
        timeout_seconds=900, max_runtime_seconds=21600,
    ),
    "tesseract": ModelDef(
        key="tesseract",
        display_name="Tesseract (pytesseract)",
        weight=Weight.LIGHT,
        license="Apache-2.0",
        license_flag=False,
        install_size_gb=0.3,
        supported_extensions=[".pdf", ".png", ".jpg", ".jpeg"],
        fit={
            _fit_key(".pdf", "scanned"): FitRating.USABLE,
            _fit_key(".png"): FitRating.USABLE,
            _fit_key(".jpg"): FitRating.USABLE,
            _fit_key(".jpeg"): FitRating.USABLE,
        },
        rationale={k: "Reliable, lightweight baseline OCR - not layout-aware."
                   for k in [_fit_key(".pdf", "scanned"), _fit_key(".png"),
                             _fit_key(".jpg"), _fit_key(".jpeg")]},
        pip_pins=[PipPin("pytesseract", "0.3.13")],
        special_case="tesseract_binary",
        notes="Python wrapper is Light; the OCR engine itself is a separate binary install. "
              "If the automatic installer gives you trouble, you can install the official "
              "UB-Mannheim build yourself (github.com/UB-Mannheim/tesseract/wiki) and click "
              "Install or Repair here again - it's detected and copied in automatically, no "
              "need to point at it manually.",
    ),
    "mineru": ModelDef(
        key="mineru",
        display_name="MinerU",
        weight=Weight.HEAVY,
        license="AGPL-3.0",
        license_flag=True,
        install_size_gb=6.0,
        supported_extensions=[".pdf"],
        fit={
            _fit_key(".pdf", "scanned"): FitRating.BEST,
            _fit_key(".pdf", "text"): FitRating.GOOD,
        },
        rationale={
            _fit_key(".pdf", "scanned"): "Best-in-class for scientific/math-heavy scanned PDFs.",
            _fit_key(".pdf", "text"): "Strong for text-native academic PDFs with formulas.",
        },
        pip_pins=[PipPin("mineru[pipeline]", "2.1.0"), PipPin("opencv-python-headless", "4.11.0.86")],
        special_case="hf_weights",
        notes="AGPL-3.0. Downloads large layout/formula model weights on first run.",
        timeout_seconds=900, max_runtime_seconds=21600,
    ),
    "paddleocr": ModelDef(
        key="paddleocr",
        display_name="PaddleOCR",
        weight=Weight.HEAVY,
        license="Apache-2.0",
        license_flag=False,
        install_size_gb=1.5,
        supported_extensions=[".png", ".jpg", ".jpeg", ".pdf"],
        fit={
            _fit_key(".png"): FitRating.BEST,
            _fit_key(".jpg"): FitRating.BEST,
            _fit_key(".jpeg"): FitRating.BEST,
            _fit_key(".pdf", "scanned"): FitRating.GOOD,
        },
        rationale={
            _fit_key(".png"): "Excellent general image OCR with strong table/multilingual support.",
            _fit_key(".jpg"): "Excellent general image OCR with strong table/multilingual support.",
            _fit_key(".jpeg"): "Excellent general image OCR with strong table/multilingual support.",
            _fit_key(".pdf", "scanned"): "Good page-image OCR for scanned PDFs.",
        },
        pip_pins=[PipPin("paddleocr", "3.6.0"), PipPin("paddlepaddle", "3.3.1")],
        notes="CPU wheel (paddlepaddle, not paddlepaddle-gpu) installed unless a GPU is detected.",
        timeout_seconds=600, max_runtime_seconds=10800,
    ),
    "surya": ModelDef(
        key="surya",
        display_name="Surya OCR",
        weight=Weight.HEAVY,
        license="GPL-3.0 (open weights)",
        license_flag=True,
        install_size_gb=2.0,
        supported_extensions=[".png", ".jpg", ".jpeg", ".pdf"],
        fit={
            _fit_key(".png"): FitRating.GOOD,
            _fit_key(".jpg"): FitRating.GOOD,
            _fit_key(".jpeg"): FitRating.GOOD,
            _fit_key(".pdf", "scanned"): FitRating.GOOD,
        },
        rationale={k: "Layout-aware OCR, good reading order on complex pages."
                   for k in [_fit_key(".png"), _fit_key(".jpg"), _fit_key(".jpeg"),
                             _fit_key(".pdf", "scanned")]},
        pip_pins=[PipPin("surya-ocr", "0.17.1"), PipPin("requests", "2.34.2"),
                  PipPin("transformers", "4.57.6")],
        special_case="hf_weights",
        notes="GPL-3.0 code; model weights under a modified OpenRAIL-M license.",
        timeout_seconds=600, max_runtime_seconds=10800,
    ),
    "trafilatura": ModelDef(
        key="trafilatura",
        display_name="trafilatura",
        weight=Weight.LIGHT,
        license="Apache-2.0",
        license_flag=False,
        install_size_gb=0.05,
        supported_extensions=[".html", ".htm"],
        fit={_fit_key(".html"): FitRating.BEST, _fit_key(".htm"): FitRating.BEST},
        rationale={_fit_key(".html"): "Best-in-class for messy, real-world web pages.",
                   _fit_key(".htm"): "Best-in-class for messy, real-world web pages."},
        pip_pins=[PipPin("trafilatura", "1.12.2")],
    ),
    "markdownify": ModelDef(
        key="markdownify",
        display_name="markdownify",
        weight=Weight.LIGHT,
        license="MIT",
        license_flag=False,
        install_size_gb=0.02,
        supported_extensions=[".html", ".htm"],
        fit={_fit_key(".html"): FitRating.BEST, _fit_key(".htm"): FitRating.BEST},
        rationale={_fit_key(".html"): "Best for clean, well-structured HTML with tables.",
                   _fit_key(".htm"): "Best for clean, well-structured HTML with tables."},
        pip_pins=[PipPin("markdownify", "0.13.1")],
    ),
    "html_to_markdown": ModelDef(
        key="html_to_markdown",
        display_name="html-to-markdown",
        weight=Weight.LIGHT,
        license="MIT",
        license_flag=False,
        install_size_gb=0.02,
        supported_extensions=[".html", ".htm"],
        fit={_fit_key(".html"): FitRating.GOOD, _fit_key(".htm"): FitRating.GOOD},
        rationale={_fit_key(".html"): "Solid spec-compliant alternative converter.",
                   _fit_key(".htm"): "Solid spec-compliant alternative converter."},
        pip_pins=[PipPin("html-to-markdown", "1.4.0")],
    ),
    "markitdown": ModelDef(
        key="markitdown",
        display_name="MarkItDown",
        weight=Weight.LIGHT,
        license="MIT",
        license_flag=False,
        install_size_gb=0.1,
        supported_extensions=[".docx", ".pptx", ".xlsx"],
        fit={_fit_key(".docx"): FitRating.BEST, _fit_key(".pptx"): FitRating.BEST,
             _fit_key(".xlsx"): FitRating.BEST},
        rationale={k: "Handles all three Office formats well out of the box."
                   for k in [_fit_key(".docx"), _fit_key(".pptx"), _fit_key(".xlsx")]},
        pip_pins=[PipPin("markitdown", "0.0.1a4")],
    ),
    "mammoth": ModelDef(
        key="mammoth",
        display_name="Mammoth",
        weight=Weight.LIGHT,
        license="BSD-2",
        license_flag=False,
        install_size_gb=0.02,
        supported_extensions=[".docx"],
        fit={_fit_key(".docx"): FitRating.GOOD},
        rationale={_fit_key(".docx"): "Cleaner semantic output than MarkItDown for DOCX."},
        pip_pins=[PipPin("mammoth", "1.8.0")],
    ),
    "pandoc": ModelDef(
        key="pandoc",
        display_name="Pandoc",
        weight=Weight.LIGHT,
        license="GPL-2.0",
        license_flag=True,
        install_size_gb=0.25,
        supported_extensions=[".epub"],
        fit={_fit_key(".epub"): FitRating.BEST},
        rationale={_fit_key(".epub"): "Only EPUB option in this app; mature and reliable."},
        pip_pins=[PipPin("pypandoc", "1.13")],
        special_case="pandoc_binary",
        notes="pypandoc is the Python wrapper only; the Pandoc binary is auto-installed separately.",
    ),
    "subtitles": ModelDef(
        key="subtitles",
        display_name="pysrt / webvtt-py",
        weight=Weight.LIGHT,
        license="GPL-3.0 / MIT",
        license_flag=True,
        install_size_gb=0.01,
        supported_extensions=[".srt", ".vtt"],
        fit={_fit_key(".srt"): FitRating.BEST, _fit_key(".vtt"): FitRating.BEST},
        rationale={_fit_key(".srt"): "Only subtitle option in this app.",
                   _fit_key(".vtt"): "Only subtitle option in this app."},
        pip_pins=[PipPin("pysrt", "1.1.2"), PipPin("webvtt-py", "0.5.1")],
    ),
}


def get_models_for_extension(ext: str) -> list:
    ext = ext.lower()
    return [m for m in MODEL_REGISTRY.values() if ext in m.supported_extensions]


def get_fit(model: ModelDef, ext: str, variant: str = "") -> FitRating:
    ext = ext.lower()
    if _fit_key(ext, variant) in model.fit:
        return model.fit[_fit_key(ext, variant)]
    if _fit_key(ext) in model.fit:
        return model.fit[_fit_key(ext)]
    return FitRating.NOT_RECOMMENDED


def get_rationale(model: ModelDef, ext: str, variant: str = "") -> str:
    ext = ext.lower()
    if _fit_key(ext, variant) in model.rationale:
        return model.rationale[_fit_key(ext, variant)]
    if _fit_key(ext) in model.rationale:
        return model.rationale[_fit_key(ext)]
    return "Supported, but no specific guidance available."


PRIMARY_MODELS = ["markitdown", "trafilatura", "markdownify", "docling", "pandoc", "subtitles", "marker"]


# ===== ENV MANAGER =====

class EnvManager:
    """Resolves all on-disk paths under the current Base Folder. No GUI/network calls."""

    def __init__(self, base_folder: Path):
        self.base_folder = Path(base_folder)

    @staticmethod
    def default_base_folder() -> Path:
        """Suggested on first run: a clearly-named subfolder right next to the app
        itself, so the user can easily find where models/settings live. Works for
        both a plain script (sys.argv[0] is the .py path) and a packaged .exe
        (sys.argv[0] is the .exe path)."""
        try:
            app_dir = Path(sys.argv[0]).resolve().parent
        except (OSError, RuntimeError):
            app_dir = Path.cwd()
        return app_dir / "MD Converter Data"

    @staticmethod
    def pointer_file_path() -> Path:
        """A tiny fixed-location file (next to the app itself) that remembers which
        Base Folder the user chose last time. This has to live OUTSIDE the Base
        Folder itself: settings.json lives inside the Base Folder, so without this
        pointer the app has no way to find a previously-chosen custom folder before
        it has even located it - it would always re-check the default location and
        wrongly conclude onboarding was never completed."""
        try:
            app_dir = Path(sys.argv[0]).resolve().parent
        except (OSError, RuntimeError):
            app_dir = Path.cwd()
        return app_dir / ".mdconverter_location"

    @staticmethod
    def read_remembered_base_folder() -> Optional[Path]:
        try:
            pointer = EnvManager.pointer_file_path()
            if not pointer.exists():
                return None
            text = pointer.read_text(encoding="utf-8").strip()
            return Path(text) if text else None
        except OSError:
            return None

    @staticmethod
    def write_remembered_base_folder(path: Path) -> None:
        try:
            EnvManager.pointer_file_path().write_text(str(path), encoding="utf-8")
        except OSError:
            pass  # best-effort only; worst case the user re-does onboarding once

    def envs_dir(self) -> Path:
        return self.base_folder / "envs"

    def models_dir(self) -> Path:
        return self.base_folder / "models"

    def bin_dir(self) -> Path:
        return self.base_folder / "bin"

    def config_dir(self) -> Path:
        return self.base_folder / "config"

    def logs_dir(self) -> Path:
        return self.base_folder / "logs"

    def model_install_log_path(self, model_key: str) -> Path:
        """Full, never-truncated install/verify log for one model (or the
        special 'python_runtime' pseudo-key) - exportable via the Model
        Manager's 'Export Log (txt)' button, independent of whatever's
        currently visible in the on-screen log box."""
        return self.logs_dir() / f"{model_key}_install.log"

    def conversion_logs_dir(self) -> Path:
        return self.logs_dir() / "conversions"

    def conversion_log_path(self, run_id: str, source_stem: str = "", model_key: str = "") -> Path:
        """Full, never-truncated log for one Convert-tab queue row (one
        file+model attempt). Named with the source file and model - not just
        an opaque id - so every log is findable and identifiable directly
        from the folder (Settings > 'Open Logs Folder', or a file browser)
        even after the app is closed and the Convert tab's queue is gone.
        The run_id suffix keeps retries and same-model-different-file
        conversions from colliding or overwriting each other."""
        if source_stem or model_key:
            safe_stem = re.sub(r'[<>:"/\\|?*]', "_", source_stem)[:80]
            safe_model = re.sub(r'[<>:"/\\|?*]', "_", model_key)
            name = f"{safe_stem}__{safe_model}__{run_id}.log" if safe_stem else f"{safe_model}__{run_id}.log"
            return self.conversion_logs_dir() / name
        return self.conversion_logs_dir() / f"{run_id}.log"

    def temp_dir(self) -> Path:
        """Scratch space for transient downloads (e.g. the Tesseract installer) -
        cleaned up automatically after a successful install; the user never needs
        to keep anything here."""
        return self.base_folder / "temp"

    def python_runtime_dir(self) -> Path:
        """A private, per-user Python 3.12 install, used only to create Heavy
        model venvs when no other 3.10-3.13 interpreter is available. Lives
        entirely inside the Base Folder - doesn't touch the system Python,
        PATH, or registry, and needs no admin rights."""
        return self.base_folder / "runtime" / "python312"

    def python_runtime_exe(self) -> Path:
        return self.python_runtime_dir() / "python.exe"

    def settings_path(self) -> Path:
        return self.config_dir() / "settings.json"

    def model_env_dir(self, model_key: str) -> Path:
        return self.envs_dir() / model_key

    def model_weights_dir(self, model_key: str) -> Path:
        return self.models_dir() / model_key

    def model_python(self, model_key: str) -> Path:
        return self.model_env_dir(model_key) / "Scripts" / "python.exe"

    def model_runner_script(self, model_key: str) -> Path:
        return self.model_env_dir(model_key) / "runner.py"

    def ensure_layout(self) -> None:
        for d in (self.envs_dir(), self.models_dir(), self.bin_dir(),
                  self.config_dir(), self.logs_dir(), self.temp_dir(),
                  self.conversion_logs_dir()):
            d.mkdir(parents=True, exist_ok=True)

    def is_writable(self) -> bool:
        try:
            self.base_folder.mkdir(parents=True, exist_ok=True)
            probe = self.base_folder / f".write_test_{uuid.uuid4().hex}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    def free_space_gb(self) -> float:
        try:
            usage = shutil.disk_usage(str(self.base_folder if self.base_folder.exists() else self.base_folder.parent))
            return usage.free / (1024 ** 3)
        except OSError:
            return 0.0

    def heavy_env_exists(self, model_key: str) -> bool:
        return self.model_python(model_key).exists()

    def tesseract_exe(self) -> Path:
        return self.bin_dir() / "tesseract" / "tesseract.exe"

    def pandoc_exe(self) -> Path:
        return self.bin_dir() / "pandoc" / "pandoc.exe"


# ===== SETTINGS =====

DEFAULT_SETTINGS = {
    "base_folder": str(EnvManager.default_base_folder()),
    "appearance_mode": "System",
    "output_folder_mode": "same_as_source",  # or "custom"
    "custom_output_folder": "",
    "auto_open_after_conversion": False,
    "log_verbosity": "Normal",
    "model_timeout_overrides": {},  # {model_key: seconds} - inactivity timeout override
    "model_max_runtime_overrides": {},  # {model_key: seconds} - absolute safety-cap override
    "model_timeout_enabled": {},  # {model_key: bool} - default True; False disables the inactivity limit
    "model_max_runtime_enabled": {},  # {model_key: bool} - default True; False disables the max-runtime cap
    "model_speed_stats": {},  # {model_key: {"seconds_per_mb": float, "samples": int}}
    "window_geometry": "1100x720+100+100",
    "window_geometry_customized": False,  # becomes True the first time the user manually resizes/moves the window
    "last_used_model_per_category": {},  # {ext: model_key}
    "last_used_models_multi_per_category": {},  # {ext: [model_key, ...]} - checkbox selection
    "model_status_cache": {},  # {model_key: "installed"/"failed_verification"/"not_installed"}
    "onboarding_complete": False,
}


class Settings:
    """Loads/saves JSON config under <BaseFolder>\\config\\settings.json."""

    def __init__(self, env: EnvManager):
        self.env = env
        self._data = dict(DEFAULT_SETTINGS)
        self._lock = threading.Lock()
        self._save_timer: Optional[threading.Timer] = None
        self.load()

    def load(self) -> None:
        path = self.env.settings_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                merged = dict(DEFAULT_SETTINGS)
                merged.update(loaded)
                self._data = merged
            except (OSError, json.JSONDecodeError):
                self._data = dict(DEFAULT_SETTINGS)

    def save_now(self) -> None:
        with self._lock:
            try:
                self.env.config_dir().mkdir(parents=True, exist_ok=True)
                tmp_path = self.env.settings_path().with_suffix(".json.tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                tmp_path.replace(self.env.settings_path())
            except OSError:
                pass

    def save_debounced(self, delay: float = 0.6) -> None:
        if self._save_timer is not None:
            self._save_timer.cancel()
        self._save_timer = threading.Timer(delay, self.save_now)
        self._save_timer.daemon = True
        self._save_timer.start()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value, debounce: bool = True) -> None:
        self._data[key] = value
        if debounce:
            self.save_debounced()
        else:
            self.save_now()

    def set_last_used_model(self, ext: str, model_key: str) -> None:
        mapping = dict(self._data.get("last_used_model_per_category", {}))
        mapping[ext.lower()] = model_key
        self.set("last_used_model_per_category", mapping)

    def get_last_used_model(self, ext: str) -> Optional[str]:
        return self._data.get("last_used_model_per_category", {}).get(ext.lower())

    def set_last_used_models_multi(self, ext: str, model_keys: list) -> None:
        mapping = dict(self._data.get("last_used_models_multi_per_category", {}))
        mapping[ext.lower()] = list(model_keys)
        self.set("last_used_models_multi_per_category", mapping)

    def get_last_used_models_multi(self, ext: str) -> list:
        return list(self._data.get("last_used_models_multi_per_category", {}).get(ext.lower(), []))

    def get_effective_timeout(self, model_key: str) -> Optional[int]:
        """Inactivity timeout: how long the model is allowed to produce
        NO new output before it's considered hung and killed. This is NOT
        a total-runtime cap - a model that keeps producing output (even
        slowly, e.g. one page every 60s on a huge scanned document) is left
        running as long as it keeps making progress. Returns None if the
        person has unticked this limit entirely for the model."""
        if not self.get_timeout_enabled(model_key):
            return None
        override = self._data.get("model_timeout_overrides", {}).get(model_key)
        if override:
            return int(override)
        model = MODEL_REGISTRY.get(model_key)
        return model.timeout_seconds if model else 300

    def set_timeout_override(self, model_key: str, seconds: int) -> None:
        overrides = dict(self._data.get("model_timeout_overrides", {}))
        overrides[model_key] = int(seconds)
        self.set("model_timeout_overrides", overrides)

    def get_timeout_enabled(self, model_key: str) -> bool:
        return self._data.get("model_timeout_enabled", {}).get(model_key, True)

    def set_timeout_enabled(self, model_key: str, enabled: bool) -> None:
        enabled_map = dict(self._data.get("model_timeout_enabled", {}))
        enabled_map[model_key] = bool(enabled)
        self.set("model_timeout_enabled", enabled_map)

    def get_effective_max_runtime(self, model_key: str) -> Optional[int]:
        """Absolute safety cap regardless of activity - only meant to catch
        a genuinely runaway process (e.g. stuck in a real infinite loop while
        still logging), not to cut off a slow-but-working huge file. Returns
        None if the person has unticked this limit entirely for the model."""
        if not self.get_max_runtime_enabled(model_key):
            return None
        override = self._data.get("model_max_runtime_overrides", {}).get(model_key)
        if override:
            return int(override)
        model = MODEL_REGISTRY.get(model_key)
        return model.max_runtime_seconds if model else 1800

    def set_max_runtime_override(self, model_key: str, seconds: int) -> None:
        overrides = dict(self._data.get("model_max_runtime_overrides", {}))
        overrides[model_key] = int(seconds)
        self.set("model_max_runtime_overrides", overrides)

    def get_max_runtime_enabled(self, model_key: str) -> bool:
        return self._data.get("model_max_runtime_enabled", {}).get(model_key, True)

    def set_max_runtime_enabled(self, model_key: str, enabled: bool) -> None:
        enabled_map = dict(self._data.get("model_max_runtime_enabled", {}))
        enabled_map[model_key] = bool(enabled)
        self.set("model_max_runtime_enabled", enabled_map)

    def get_speed_estimate_seconds_per_mb(self, model_key: str) -> Optional[float]:
        stats = self._data.get("model_speed_stats", {}).get(model_key)
        if not stats or not stats.get("samples"):
            return None
        return stats.get("seconds_per_mb")

    def record_speed_sample(self, model_key: str, elapsed_seconds: float, size_mb: float) -> None:
        """Exponential moving average of seconds-per-MB, so the ETA keeps
        adapting to this machine's real speed instead of a single stale sample."""
        if size_mb <= 0:
            return
        rate = elapsed_seconds / size_mb
        stats = dict(self._data.get("model_speed_stats", {}))
        current = dict(stats.get(model_key, {"seconds_per_mb": rate, "samples": 0}))
        prior = current.get("seconds_per_mb", rate)
        samples = current.get("samples", 0)
        alpha = 0.35 if samples > 0 else 1.0
        current["seconds_per_mb"] = alpha * rate + (1 - alpha) * prior
        current["samples"] = samples + 1
        stats[model_key] = current
        self.set("model_speed_stats", stats)

    def get_cached_status(self, model_key: str) -> str:
        return self._data.get("model_status_cache", {}).get(model_key, InstallStatus.NOT_INSTALLED.value)

    def set_cached_status(self, model_key: str, status: str) -> None:
        cache = dict(self._data.get("model_status_cache", {}))
        cache[model_key] = status
        self.set("model_status_cache", cache)

    def output_folder_for(self, source_path: Path) -> Path:
        if self._data.get("output_folder_mode") == "custom" and self._data.get("custom_output_folder"):
            return Path(self._data["custom_output_folder"])
        return source_path.parent


# ===== ADVISOR =====

class Advisor:
    """Pure functions/class - no GUI, no subprocess calls."""

    @staticmethod
    def rank_models(ext: str, variant: str = "") -> list:
        """Returns list of (ModelDef, FitRating, rationale) sorted Best -> Not Recommended."""
        order = {FitRating.BEST: 0, FitRating.GOOD: 1, FitRating.USABLE: 2, FitRating.NOT_RECOMMENDED: 3}
        candidates = get_models_for_extension(ext)
        results = []
        for m in candidates:
            fit = get_fit(m, ext, variant)
            rationale = get_rationale(m, ext, variant)
            results.append((m, fit, rationale))
        results.sort(key=lambda r: (order[r[1]], r[0].display_name))
        return results

    @staticmethod
    def detect_pdf_variant(file_path: Path) -> str:
        """Heuristic: attempt text extraction; if near-empty, treat as scanned.
        Never used to hide a model - only to change which fit badges show as Best."""
        try:
            import pymupdf  # available if PyMuPDF4LLM installed; degrade gracefully otherwise
            doc = pymupdf.open(str(file_path))
            total_chars = 0
            pages_checked = min(len(doc), 5)
            for i in range(pages_checked):
                total_chars += len(doc[i].get_text("text").strip())
            doc.close()
            avg_chars = total_chars / max(pages_checked, 1)
            return "text" if avg_chars > 40 else "scanned"
        except Exception:
            return "text"  # cannot determine; default to text-native assumption


# ===== INSTALLER =====

@dataclass
class InstallEvent:
    model_key: str
    kind: str  # "log" / "progress" / "status" / "error" / "done"
    message: str = ""
    progress: Optional[float] = None
    status: Optional[str] = None


def _heavy_subprocess_env() -> dict:
    """Environment for any Heavy-model runner subprocess (smoke test AND real
    conversion).
    - Disables PyTorch's dynamo/inductor JIT compilation, which requires a real
      C++ compiler (MSVC's cl.exe on Windows) that most users won't have
      installed - confirmed as the exact cause of a "failed verification"
      result on an otherwise-successful Docling install
      (torch._inductor.exc.InductorError: InvalidCxxCompiler: Compiler: cl is
      not found). Forcing eager mode avoids this entirely; a single inference
      pass doesn't need JIT speed optimizations.
    - Sets FLAGS_use_mkldnn=0 as a best-effort global hint to disable
      PaddlePaddle's oneDNN (MKLDNN) CPU backend, which has gaps in its newer
      PIR execution path (NotImplementedError:
      ConvertPirAttribute2RuntimeAttribute not support [...DoubleAttribute],
      raised from onednn_instruction.cc). Confirmed NOT sufficient by itself,
      though - PaddleOCR's own pipeline config defaults enable_mkldnn=True
      regardless of this env var, so the paddleocr runner script below also
      passes enable_mkldnn=False explicitly to PaddleOCR(), which is the part
      that actually disables it. This env var is kept as a harmless belt-
      and-suspenders default for any other Paddle code path. Harmless for
      non-Paddle models - they simply never read this flag."""
    env = os.environ.copy()
    env["TORCHDYNAMO_DISABLE"] = "1"
    env["TORCH_COMPILE_DISABLE"] = "1"
    env["FLAGS_use_mkldnn"] = "0"
    env["PYTHONUNBUFFERED"] = "1"  # so our own print()s and tqdm reach the parent promptly
    return env


RUNNER_TEMPLATES = {
    "docling": textwrap.dedent("""
        import sys
        def convert(input_path, output_path):
            from docling.document_converter import DocumentConverter
            conv = DocumentConverter()
            result = conv.convert(input_path)
            md = result.document.export_to_markdown()
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md)
        if __name__ == "__main__":
            convert(sys.argv[1], sys.argv[2])
    """),
    "unstructured": textwrap.dedent("""
        import sys
        def convert(input_path, output_path):
            from unstructured.partition.auto import partition
            elements = partition(filename=input_path)
            lines = [str(e) for e in elements]
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\\n\\n".join(lines))
        if __name__ == "__main__":
            convert(sys.argv[1], sys.argv[2])
    """),
    "marker": textwrap.dedent("""
        import sys
        def convert(input_path, output_path):
            try:
                import pymupdf
                n = pymupdf.open(input_path).page_count
                print(f"MDCONV_PAGES:{n}", flush=True)
            except Exception:
                pass
            print("MDCONV_STAGE:loading models", flush=True)
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered
            converter = PdfConverter(artifact_dict=create_model_dict())
            print("MDCONV_STAGE:converting", flush=True)
            rendered = converter(input_path)
            text, _, _ = text_from_rendered(rendered)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            print("MDCONV_STAGE:done", flush=True)
        if __name__ == "__main__":
            convert(sys.argv[1], sys.argv[2])
    """),
    "mineru": textwrap.dedent("""
        import sys, subprocess, os, glob, types, traceback, tempfile, shutil
        def convert(input_path, output_path):
            try:
                import pymupdf
                n = pymupdf.open(input_path).page_count
                print(f"MDCONV_PAGES:{n}", flush=True)
            except Exception:
                pass
            # mineru.cli.common (imported by mineru's CLI) unconditionally
            # imports the VLM backend even when only the CPU 'pipeline' backend
            # is requested, and that backend chain has pulled in one undeclared
            # heavy dependency after another (cv2, then torch...) - so instead
            # of chasing each one, stub out the one module mineru.cli.common
            # actually imports from, so its real code never executes at all.
            vlm_mod_name = "mineru.backend.vlm.vlm_analyze"
            if vlm_mod_name not in sys.modules:
                stub = types.ModuleType(vlm_mod_name)
                stub.doc_analyze = lambda *a, **k: None
                stub.aio_doc_analyze = lambda *a, **k: None
                sys.modules[vlm_mod_name] = stub

            # CRITICAL: mineru is given an ISOLATED, empty temp directory as its
            # -o output dir - never the user's real chosen output folder. mineru
            # always writes many files (images/, _layout.pdf, _content_list.json,
            # _model.json, plus the .md) nested under {out}/{stem}/{method}/, and
            # a previous version of this app searched the user's ENTIRE real
            # output folder for "any .md file" to guess which one mineru had
            # just written - which could (and did) silently copy an unrelated
            # pre-existing .md file instead (from another project, or from a
            # different model's output that happened to sort first). Giving
            # mineru a fresh, private directory makes that class of bug
            # structurally impossible: nothing else can ever be in it.
            stem = os.path.splitext(os.path.basename(input_path))[0]
            isolated_out = tempfile.mkdtemp(prefix="mdconv_mineru_")
            try:
                ran_in_process = False
                try:
                    from mineru.cli.client import main as mineru_main
                    mineru_main(args=["-p", input_path, "-o", isolated_out, "-b", "pipeline"],
                                standalone_mode=False)
                    ran_in_process = True
                except SystemExit:
                    ran_in_process = True
                except Exception:
                    # Print (not swallow) the real reason the stub-based in-process
                    # attempt failed, so it's visible in the exported log even
                    # though we fall back to the console-script below.
                    print("In-process invocation with VLM stub failed, "
                          "falling back to the console-script:", file=sys.stderr)
                    traceback.print_exc()
                if not ran_in_process:
                    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
                    mineru_exe = os.path.join(scripts_dir, "mineru.exe")
                    cmd = ([mineru_exe] if os.path.exists(mineru_exe)
                           else [sys.executable, "-m", "mineru.cli.client"])
                    subprocess.run(cmd + ["-p", input_path, "-o", isolated_out, "-b", "pipeline"], check=True)

                # mineru's own deterministic layout (confirmed against its source,
                # mineru/cli/common.py prepare_env()): {out}/{stem}/auto/{stem}.md
                # - "auto" is the literal folder name for the default --method
                # (which this runner always uses), not a placeholder.
                expected = os.path.join(isolated_out, stem, "auto", f"{stem}.md")
                found = expected if os.path.isfile(expected) else None
                if found is None:
                    # Fallback ONLY within this isolated directory - safe, since
                    # nothing else could possibly be in it - in case a future
                    # mineru version renames the method subfolder.
                    candidates = glob.glob(os.path.join(isolated_out, "**", "*.md"), recursive=True)
                    if candidates:
                        found = max(candidates, key=os.path.getsize)
                if found is None:
                    raise RuntimeError(
                        f"mineru finished but produced no .md file under {isolated_out} "
                        f"(expected {expected}). It may have failed silently - check the "
                        f"log above for its own output.")
                with open(found, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
            finally:
                shutil.rmtree(isolated_out, ignore_errors=True)
        if __name__ == "__main__":
            convert(sys.argv[1], sys.argv[2])
    """),
    "paddleocr": textwrap.dedent("""
        import sys, os
        # Belt-and-suspenders global hint, set before importing paddle/paddleocr
        # at all. NOT sufficient by itself, though - see enable_mkldnn=False below.
        os.environ["FLAGS_use_mkldnn"] = "0"
        def convert(input_path, output_path):
            from paddleocr import PaddleOCR
            # PaddleOCR 3.x replaced the old .ocr()-returns-nested-lists API with
            # .predict()-returns-result-objects; support both so this keeps working
            # whether an older or newer PaddleOCR ends up installed.
            # enable_mkldnn=False is the real fix for a PaddlePaddle bug
            # (NotImplementedError: ConvertPirAttribute2RuntimeAttribute not
            # support [...DoubleAttribute], raised from its oneDNN CPU backend
            # in the newer PIR execution path) - confirmed the FLAGS_use_mkldnn
            # env var above is NOT enough on its own, because PaddleOCR's own
            # pipeline config defaults enable_mkldnn=True regardless of it; this
            # constructor argument is the one that actually takes effect.
            # device="cpu" avoids a separate bug where autodetection can report
            # "gpu:0" on a machine with a GPU even though only the CPU wheel
            # (paddlepaddle, not paddlepaddle-gpu) is installed.
            ocr = PaddleOCR(lang="en", device="cpu", enable_mkldnn=False)
            lines = []
            if hasattr(ocr, "predict"):
                for res in ocr.predict(input_path):
                    texts = None
                    if hasattr(res, "rec_texts"):
                        texts = res.rec_texts
                    elif isinstance(res, dict):
                        texts = res.get("rec_texts")
                    elif hasattr(res, "json") and isinstance(getattr(res, "json", None), dict):
                        texts = res.json.get("rec_texts")
                    if texts:
                        lines.extend(texts)
            else:
                result = ocr.ocr(input_path, cls=True)
                for page in result:
                    for box in page:
                        lines.append(box[1][0])
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\\n\\n".join(lines))
        if __name__ == "__main__":
            convert(sys.argv[1], sys.argv[2])
    """),
    "surya": textwrap.dedent("""
        import sys
        def convert(input_path, output_path):
            from PIL import Image
            from surya.detection import DetectionPredictor
            from surya.foundation import FoundationPredictor
            from surya.recognition import RecognitionPredictor
            det_predictor = DetectionPredictor()
            # This surya-ocr release requires a FoundationPredictor passed into
            # RecognitionPredictor - there is no working no-arg fallback for this
            # version, so let any real construction error propagate clearly
            # instead of masking it with a second, unrelated TypeError.
            foundation_predictor = FoundationPredictor()
            rec_predictor = RecognitionPredictor(foundation_predictor)
            image = Image.open(input_path).convert("RGB")
            predictions = rec_predictor([image], det_predictor=det_predictor)
            lines = []
            for pred in predictions:
                for line in (getattr(pred, "text_lines", None) or []):
                    text = getattr(line, "text", None)
                    if text:
                        lines.append(text)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\\n\\n".join(lines))
        if __name__ == "__main__":
            convert(sys.argv[1], sys.argv[2])
    """),
}


class Installer:
    """Install engine: venv creation, subprocess management, cancellation, verification, repair,
    disk/network checks. No customtkinter import, no widget references."""

    def __init__(self, env: EnvManager, settings: Settings, event_queue: "queue.Queue[InstallEvent]"):
        self.env = env
        self.settings = settings
        self.events = event_queue
        self._cancel_flags: dict = {}
        self._active_procs: dict = {}
        self._lock = threading.Lock()

    # ---------- public API ----------

    def install_model_async(self, model_key: str) -> threading.Thread:
        self._cancel_flags[model_key] = False
        t = threading.Thread(target=self._install_model_worker, args=(model_key,), daemon=True)
        t.start()
        return t

    def cancel_install(self, model_key: str) -> None:
        self._cancel_flags[model_key] = True
        proc = self._active_procs.get(model_key)
        if proc is not None:
            self._kill_process_tree(proc.pid)

    def verify_model_async(self, model_key: str) -> threading.Thread:
        self._cancel_flags[model_key] = False
        t = threading.Thread(target=self._verify_model_worker, args=(model_key,), daemon=True)
        t.start()
        return t

    def repair_model_async(self, model_key: str) -> threading.Thread:
        t = threading.Thread(target=self._repair_model_worker, args=(model_key,), daemon=True)
        t.start()
        return t

    def uninstall_model(self, model_key: str) -> None:
        """Only ever deletes that one model's own folders. Never touches other models or config."""
        model = MODEL_REGISTRY[model_key]
        try:
            if model.weight == Weight.HEAVY:
                env_dir = self.env.model_env_dir(model_key)
                if env_dir.exists():
                    shutil.rmtree(env_dir, ignore_errors=True)
            weights_dir = self.env.model_weights_dir(model_key)
            if weights_dir.exists():
                shutil.rmtree(weights_dir, ignore_errors=True)
            if model.special_case == "tesseract_binary":
                d = self.env.tesseract_exe().parent
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
            if model.special_case == "pandoc_binary":
                d = self.env.pandoc_exe().parent
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
        finally:
            self.settings.set_cached_status(model_key, InstallStatus.NOT_INSTALLED.value)
            self._emit(model_key, "status", status=InstallStatus.NOT_INSTALLED.value)

    def check_disk_space(self, model_key: str) -> tuple:
        """Returns (required_gb, available_gb, ok)."""
        model = MODEL_REGISTRY[model_key]
        required = model.install_size_gb
        available = self.env.free_space_gb()
        return required, available, available >= required if required > 0.5 else True

    # ---------- interpreter discovery ----------

    def _registry_python_installs(self) -> dict:
        """Enumerate every Python interpreter Windows itself knows about, via
        the same registry keys the official installer and the `py` launcher
        both read (HKCU and HKLM, Software\\Python\\PythonCore\\<version>\\
        InstallPath). This is the authoritative source - it finds an install
        regardless of which folder the person chose during setup, unlike
        guessing at a handful of default paths. A system Python installed
        normally (the only realistic way to get one on Windows) always
        registers here, even with a fully custom install location. Returns
        {(major, minor): python_exe_path}; HKCU is checked last so a
        per-user install wins over a per-machine one of the same version,
        matching how this app's own provisioned runtime is installed."""
        found = {}
        try:
            import winreg
        except ImportError:
            return found
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY),
            (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
            (winreg.HKEY_CURRENT_USER, 0),
        ]
        for hive, view_flag in roots:
            try:
                core_key = winreg.OpenKey(hive, r"Software\Python\PythonCore", 0,
                                           winreg.KEY_READ | view_flag)
            except OSError:
                continue
            try:
                i = 0
                while True:
                    try:
                        ver_name = winreg.EnumKey(core_key, i)
                    except OSError:
                        break
                    i += 1
                    # ver_name looks like "3.12" or, for a 32-bit build, "3.12-32".
                    parts = ver_name.split("-")[0].split(".")
                    if len(parts) != 2 or not all(p.isdigit() for p in parts):
                        continue
                    version = (int(parts[0]), int(parts[1]))
                    try:
                        install_key = winreg.OpenKey(
                            core_key, f"{ver_name}\\InstallPath", 0, winreg.KEY_READ | view_flag)
                        install_dir, _ = winreg.QueryValueEx(install_key, "")
                        winreg.CloseKey(install_key)
                    except OSError:
                        continue
                    exe_path = Path(install_dir) / "python.exe"
                    if exe_path.exists():
                        found[version] = str(exe_path)
            finally:
                winreg.CloseKey(core_key)
        return found

    def _find_base_python(self) -> Optional[str]:
        """Picks the interpreter used to create a Heavy model's isolated venv.
        Heavy-model dependencies (Pillow, lxml, torch, etc.) are native-compiled
        packages that often lag behind the newest Python release with prebuilt
        Windows wheels - installing them under a brand-new Python (e.g. 3.14)
        can force pip to compile from source and fail without a full C toolchain
        (zlib/libxml2 headers, MSVC). So, in order: prefer a Python runtime this
        app already auto-provisioned for exactly this purpose (see Model Manager's
        "Install Python 3.12" flow); then any already-installed 3.10-3.13 Python
        Windows itself knows about, found via the registry - this is checked
        BEFORE offering to auto-install a private copy, so an existing system
        Python is never missed; then the `py` launcher as a secondary check;
        if the launcher isn't registered either, also probe common Windows
        install locations directly; fall back to whatever is running the app,
        then bare `python`/`python3`, only if none of those are available."""
        provisioned = self.env.python_runtime_exe()
        if provisioned.exists():
            return str(provisioned)

        registry_installs = self._registry_python_installs()
        for version in ((3, 12), (3, 11), (3, 13), (3, 10)):
            if version in registry_installs:
                return registry_installs[version]

        candidates = []
        for cmd in (["py", "-3.12"], ["py", "-3.11"], ["py", "-3.13"], ["py", "-3.10"]):
            try:
                result = subprocess.run(cmd + ["--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    candidates.append(" ".join(cmd))
            except (OSError, subprocess.TimeoutExpired):
                continue
        if not candidates:
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
            for ver in ("312", "311", "313", "310"):
                for candidate_path in (
                    fr"C:\Python{ver}\python.exe",
                    fr"{program_files}\Python{ver}\python.exe",
                    fr"{local_appdata}\Programs\Python\Python{ver}\python.exe",
                ):
                    if candidate_path and Path(candidate_path).exists():
                        candidates.append(candidate_path)
        candidates.append(sys.executable)
        for cmd in (["python"], ["python3"]):
            try:
                result = subprocess.run(cmd + ["--version"], capture_output=True, timeout=5)
                if result.returncode == 0:
                    candidates.append(cmd[0])
            except (OSError, subprocess.TimeoutExpired):
                continue
        for c in candidates:
            if c and (Path(c).exists() or shutil.which(c.split(" ")[0])):
                return c
        return None

    HEAVY_COMPATIBLE_PYTHON_VERSIONS = {(3, 10), (3, 11), (3, 12), (3, 13)}

    def _interpreter_version(self, python_cmd: str) -> Optional[tuple]:
        """Returns (major, minor) for the given interpreter command, or None if
        it couldn't be determined."""
        try:
            cmd = python_cmd.split(" ") + [
                "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"]
            result = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
            if result.returncode == 0:
                major, minor = result.stdout.strip().split(".")
                return (int(major), int(minor))
        except Exception:
            pass
        return None

    def check_heavy_interpreter_compatibility(self) -> dict:
        """What Heavy-model installs will actually use, checked ahead of time so
        the person sees this before three failed pip attempts, not after."""
        python_cmd = self._find_base_python()
        version = self._interpreter_version(python_cmd) if python_cmd else None
        compatible = version in self.HEAVY_COMPATIBLE_PYTHON_VERSIONS if version else None
        return {"python_cmd": python_cmd, "version": version, "compatible": compatible}

    def _gpu_available(self) -> bool:
        return shutil.which("nvidia-smi") is not None

    # ---------- process helpers ----------

    def _run_streamed(self, model_key: str, cmd: list, cwd: Optional[Path] = None,
                       retries: int = 3) -> bool:
        """Run a subprocess, stream output as log events, retry on transient failure.
        Returns True on success."""
        for attempt in range(1, retries + 1):
            if self._cancel_flags.get(model_key):
                self._emit(model_key, "log", message="Install cancelled.")
                return False
            try:
                proc = subprocess.Popen(
                    cmd, cwd=str(cwd) if cwd else None,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                )
                with self._lock:
                    self._active_procs[model_key] = proc
                for line in proc.stdout:
                    if self._cancel_flags.get(model_key):
                        self._kill_process_tree(proc.pid)
                        self._emit(model_key, "log", message="Install cancelled.")
                        return False
                    self._emit(model_key, "log", message=line.rstrip())
                proc.wait()
                with self._lock:
                    self._active_procs.pop(model_key, None)
                if proc.returncode == 0:
                    return True
                self._emit(model_key, "log",
                            message=f"Command exited with code {proc.returncode} (attempt {attempt}/{retries}).")
            except FileNotFoundError:
                self._emit(model_key, "error", message="Required command not found. Check your network settings.")
                return False
            except OSError as e:
                self._emit(model_key, "log", message=f"Transient error: {e} (attempt {attempt}/{retries}).")
            time.sleep(min(2 ** attempt, 10))
        self._emit(model_key, "error", message="No internet connection, or the install failed after retries.")
        return False

    def _kill_process_tree(self, pid: int) -> None:
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _run_cancellable(self, model_key: str, cmd: list, timeout: int):
        """Runs cmd via Popen and polls for completion (instead of a single
        blocking subprocess.run call) so the cancel flag actually has a
        chance to stop it mid-run. Returns an object with .returncode,
        .stdout, .stderr - or None if the run was cancelled. Raises
        subprocess.TimeoutExpired on timeout, matching subprocess.run's
        behavior so callers can keep their existing except clauses."""
        import types
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with self._lock:
            self._active_procs[model_key] = proc
        deadline = time.time() + timeout
        try:
            while True:
                if self._cancel_flags.get(model_key):
                    self._kill_process_tree(proc.pid)
                    self._emit(model_key, "log", message="Install cancelled.")
                    return None
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                    return types.SimpleNamespace(returncode=proc.returncode, stdout=stdout, stderr=stderr)
                except subprocess.TimeoutExpired:
                    if time.time() > deadline:
                        self._kill_process_tree(proc.pid)
                        raise
                    continue
        finally:
            with self._lock:
                self._active_procs.pop(model_key, None)

    def _emit(self, model_key: str, kind: str, message: str = "",
              progress: Optional[float] = None, status: Optional[str] = None) -> None:
        self.events.put(InstallEvent(model_key, kind, message, progress, status))
        if kind in ("log", "error") and message:
            try:
                log_path = self.env.model_install_log_path(model_key)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(message + "\n")
            except OSError:
                pass  # exporting the log is a convenience, never worth failing the install over

    def _start_fresh_log(self, model_key: str) -> None:
        """Called at the start of every install/verify/repair/runtime attempt,
        so 'Export Log' always reflects the most recent attempt cleanly instead
        of several runs concatenated together."""
        try:
            log_path = self.env.model_install_log_path(model_key)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                f"=== Attempt started {datetime.now().isoformat(timespec='seconds')} ===\n",
                encoding="utf-8")
        except OSError:
            pass

    # ---------- install workers ----------

    def _install_model_worker(self, model_key: str, reset_log: bool = True) -> None:
        model = MODEL_REGISTRY[model_key]
        if reset_log:
            self._start_fresh_log(model_key)
        try:
            self._emit(model_key, "status", status=InstallStatus.INSTALLING.value)
            self.env.ensure_layout()

            required, available, ok = self.check_disk_space(model_key)
            if not ok:
                self._emit(model_key, "error",
                            message=f"Not enough disk space: needs ~{required} GB, only {available:.1f} GB free.")
                self._emit(model_key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return

            if model.weight == Weight.LIGHT:
                success = self._install_light(model)
            else:
                success = self._install_heavy(model)

            if not success:
                self._emit(model_key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return

            if model.special_case == "tesseract_binary":
                success = self._install_tesseract_binary(model_key)
                if not success:
                    self._emit(model_key, "status", status=InstallStatus.NOT_INSTALLED.value)
                    return
            elif model.special_case == "pandoc_binary":
                success = self._install_pandoc_binary(model_key)
                if not success:
                    self._emit(model_key, "status", status=InstallStatus.NOT_INSTALLED.value)
                    return
            elif model.special_case == "hf_weights":
                self._emit(model_key, "log", message="Step 3 of 3: downloading model weights (first run).")
                # Weight download is triggered by the model library itself on first real use;
                # the smoke test below performs a minimal first run to trigger and verify it.

            self._verify_model_worker(model_key, from_install=True)
        except Exception as e:
            self._emit(model_key, "error", message=f"Unexpected install error: {e}")
            self._emit(model_key, "status", status=InstallStatus.NOT_INSTALLED.value)
        finally:
            self._cancel_flags[model_key] = False

    def _install_light(self, model: ModelDef) -> bool:
        py = sys.executable
        self._emit(model.key, "log", message="Step 1 of 2: upgrading pip/setuptools/wheel.")
        if not self._run_streamed(model.key, [py, "-m", "pip", "install", "--upgrade",
                                               "pip", "setuptools", "wheel"]):
            return False
        self._emit(model.key, "log", message="Step 2 of 2: installing package(s).")
        specs = [p.spec() for p in model.pip_pins]
        cmd = [py, "-m", "pip", "install"] + specs
        return self._run_streamed(model.key, cmd)

    def _install_heavy(self, model: ModelDef) -> bool:
        env_dir = self.env.model_env_dir(model.key)
        venv_python_exists = self.env.model_python(model.key).exists()

        if not venv_python_exists:
            base_python = self._find_base_python()
            if not base_python:
                self._emit(model.key, "error",
                            message="No usable Python 3.11+ interpreter found (tried sys.executable, "
                                    "'py -3.11', 'python', 'python3').")
                return False
            version = self._interpreter_version(base_python)
            if version and version not in self.HEAVY_COMPATIBLE_PYTHON_VERSIONS:
                self._emit(model.key, "log",
                            message=f"\u26a0\ufe0f Using Python {version[0]}.{version[1]} to build this "
                                    "environment. Heavy models like this one currently need Python "
                                    "3.10-3.13 (their own dependencies don't ship ready-made packages "
                                    "for newer Pythons yet) - this install will likely fail. Installing "
                                    "Python 3.12 from python.org (no need to make it your default) and "
                                    "re-running this install should fix it automatically.")
            self._emit(model.key, "log", message="Step 1 of 4: creating isolated environment.")
            if env_dir.exists():
                shutil.rmtree(env_dir, ignore_errors=True)  # partial state - clean and restart
            cmd = base_python.split(" ") + ["-m", "venv", str(env_dir)]
            if not self._run_streamed(model.key, cmd):
                return False

        venv_python = str(self.env.model_python(model.key))
        self._emit(model.key, "log", message="Step 2 of 4: upgrading pip/setuptools/wheel in isolated env.")
        if not self._run_streamed(model.key, [venv_python, "-m", "pip", "install", "--upgrade",
                                               "pip", "setuptools", "wheel"]):
            return False

        self._emit(model.key, "log", message="Step 3 of 4: installing model package(s) (CPU wheels by default).")
        gpu = self._gpu_available()
        for pin in model.pip_pins:
            cmd = [venv_python, "-m", "pip", "install", pin.spec()]
            if pin.index_url and not gpu:
                cmd += ["--index-url", pin.index_url]
            if not self._run_streamed(model.key, cmd):
                return False

        self._emit(model.key, "log", message="Step 4 of 4: writing runner script.")
        template = RUNNER_TEMPLATES.get(model.key)
        if template:
            runner_path = self.env.model_runner_script(model.key)
            runner_path.parent.mkdir(parents=True, exist_ok=True)
            runner_path.write_text(template, encoding="utf-8")
        return True

    def _resolve_tesseract_installer_url(self) -> Optional[str]:
        """UB-Mannheim's release asset filenames bake in the version (e.g.
        tesseract-ocr-w64-setup-5.5.0.20241111.exe), so a hardcoded URL 404s the
        moment a new version ships. Ask the GitHub API for the current release
        and find the actual 64-bit Windows installer asset by name pattern."""
        import json
        import re
        import urllib.request
        req = urllib.request.Request(
            "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest",
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "MDConverter"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            release = json.loads(resp.read().decode("utf-8"))
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if re.match(r"tesseract-ocr-w64-setup.*\.exe$", name, re.IGNORECASE):
                return asset.get("browser_download_url")
        return None

    def _launch_elevated(self, exe_path: str, params: str) -> None:
        """Launches exe_path requesting UAC elevation (the 'runas' verb),
        fire-and-forget - no attempt to track the elevated process via a
        handle. Needed because installers whose own manifest requires
        administrator rights (confirmed: Tesseract's official UB-Mannheim
        installer, which always failed outright with [WinError 740] The
        requested operation requires elevation under plain subprocess.run,
        which has no way to trigger the UAC prompt at all) can only be
        launched this way - but Windows' UAC broker can make the process
        handle from ShellExecuteEx unreliable to wait on directly for the
        'runas' verb specifically (it can end up representing the broker
        rather than the real elevated process), so callers should poll for
        the actual expected result instead of trying to track completion
        through this call."""
        import ctypes
        SW_HIDE = 0
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_path, params, None, SW_HIDE)
        if result == 5:
            raise OSError("The Windows permission prompt (UAC) was declined or dismissed "
                           "(error code 5 = access denied) - click 'Yes' when it appears, "
                           "then try installing again.")
        if result <= 32:
            raise OSError(f"Could not launch the elevated installer (error code {result}) - "
                          f"the UAC prompt may have been declined.")

    def _remove_stale_tesseract_registry_entries(self, model_key: str) -> None:
        """The UB-Mannheim (NSIS-based) installer decides whether a 'previous
        version' is present by checking the Windows registry Uninstall key,
        NOT by checking the target directory. A prior install/repair of
        Tesseract by this app writes that key, but our own Repair flow only
        deletes the on-disk folder (see below) - it never runs the real
        uninstaller, so the registry key survives pointing at an uninstaller
        .exe that no longer exists. The next installer run detects that
        stale key, silently tries to launch the missing uninstaller as its
        own first step, and that step can never finish - which is exactly
        what looks like the installer 'starts to uninstall, then hangs'.
        Clearing the stale key first means the installer finds nothing to
        react to and goes straight to a clean install.

        This scans every Uninstall subkey's DisplayName instead of guessing
        the exact subkey name (e.g. "Tesseract-OCR") - that guess never
        matched anything in practice (no earlier log ever showed this step
        finding something to remove), and NSIS installers commonly key the
        subkey itself off a GUID or a name that includes the version, not
        the plain product name. Matching on DisplayName instead is robust
        to whatever the real subkey happens to be called."""
        try:
            import winreg
        except ImportError:
            return
        bases = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
             winreg.KEY_WOW64_64KEY),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
             winreg.KEY_WOW64_32KEY),
        ]
        removed_any = False
        for hive, base_path, view_flag in bases:
            try:
                base_key = winreg.OpenKey(hive, base_path, 0, winreg.KEY_READ | view_flag)
            except OSError:
                continue
            try:
                matches = []
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(base_key, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        sub = winreg.OpenKey(base_key, subkey_name, 0, winreg.KEY_READ | view_flag)
                        try:
                            display_name, _ = winreg.QueryValueEx(sub, "DisplayName")
                        except OSError:
                            display_name = ""
                        finally:
                            winreg.CloseKey(sub)
                    except OSError:
                        continue
                    if "tesseract" in str(display_name).lower():
                        matches.append(subkey_name)
                for subkey_name in matches:
                    try:
                        winreg.DeleteKeyEx(hive, f"{base_path}\\{subkey_name}", view_flag, 0)
                        removed_any = True
                    except OSError:
                        continue
            finally:
                winreg.CloseKey(base_key)
        if removed_any:
            self._emit(model_key, "log",
                        message="Cleared a leftover Tesseract registry entry from a previous "
                                "install, so the installer won't try to silently uninstall a "
                                "copy that no longer exists on disk.")

    def _process_running(self, image_name: str) -> bool:
        """Best-effort check via tasklist. Returns True (keep waiting) if the
        check itself fails - safer than wrongly assuming the process is gone."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
                capture_output=True, text=True, timeout=10)
            return image_name.lower() in result.stdout.lower()
        except (OSError, subprocess.TimeoutExpired):
            return True

    def _run_tesseract_installer_once(self, model_key: str, installer_path: Path, params: str) -> bool:
        """Launches the installer elevated and waits for tesseract.exe to
        appear. ShellExecuteW's 'runas' verb returns almost immediately -
        well before the UAC prompt is even shown, let alone approved - so
        the actual installer process may not exist yet for some time after
        this call returns. Checking whether it's 'still running' too early
        reads as 'already exited' and gives up before the person has even
        had a chance to click through the prompt, so that check is skipped
        entirely for an initial grace period."""
        try:
            self._launch_elevated(str(installer_path), params)
        except OSError as e:
            self._emit(model_key, "error", message=f"Could not start the Tesseract installer: {e}")
            return False
        grace_period_end = time.time() + 60
        deadline = time.time() + 240
        next_heartbeat = time.time() + 20
        while time.time() < deadline:
            if self._cancel_flags.get(model_key):
                try:
                    subprocess.run(["taskkill", "/T", "/F", "/IM", installer_path.name],
                                   capture_output=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                self._emit(model_key, "log", message="Install cancelled.")
                return False
            if self.env.tesseract_exe().exists():
                return True
            if time.time() > grace_period_end and not self._process_running(installer_path.name):
                break  # past the grace period and the process has genuinely exited
            if time.time() >= next_heartbeat:
                self._emit(model_key, "log",
                            message="Still waiting... (if a Windows dialog appeared, it "
                                    "may be behind this window - check your taskbar)")
                next_heartbeat = time.time() + 20
            time.sleep(2)
        return self.env.tesseract_exe().exists()

    def _run_existing_tesseract_uninstaller(self, model_key: str, dest_dir: Path) -> None:
        """If a leftover uninstaller from a real previous install is sitting
        in the target folder, run it properly (elevated, waited-for) before
        we touch the folder ourselves. Deleting the folder out from under a
        registered install only clears files, not whatever internal state
        the installer's own .onInit check relies on to decide 'a previous
        version is here, remove it first' - which is the uninstall-then-stop
        behaviour seen on every attempt so far. Going through the real
        uninstaller first is more likely to actually clear that state."""
        if not dest_dir.exists():
            return
        try:
            candidates = list(dest_dir.glob("*ninstall*.exe"))
        except OSError:
            return
        if not candidates:
            return
        uninstaller = candidates[0]
        self._emit(model_key, "log",
                    message=f"Found a leftover uninstaller ({uninstaller.name}) in the Tesseract "
                            "folder from a previous attempt - running it properly first...")
        try:
            self._launch_elevated(str(uninstaller), "/S")
        except OSError as e:
            self._emit(model_key, "log", message=f"Could not run the leftover uninstaller: {e}")
            return
        deadline = time.time() + 60
        while time.time() < deadline and uninstaller.exists():
            time.sleep(2)

    def _ensure_tesseract_dir_truly_clean(self, model_key: str, dest_dir: Path) -> None:
        """shutil.rmtree(..., ignore_errors=True) can silently fail to
        remove a file that's locked (e.g. an antivirus scan holding it open
        right after the uninstaller above touched it) and we'd never know -
        the folder just stays partially there. If a leftover uninstall.exe
        survives that way, the installer sees it on every subsequent
        attempt and repeats the same uninstall-then-stop behaviour no
        matter how many times we retry the installer itself. So this
        verifies the folder is actually empty afterward instead of trusting
        the first attempt, clearing read-only attributes and retrying a
        few times before giving up."""
        for _ in range(4):
            if not dest_dir.exists() or not any(dest_dir.iterdir()):
                return
            try:
                for root, _dirs, files in os.walk(dest_dir):
                    for name in files:
                        try:
                            os.chmod(str(Path(root) / name), 0o666)
                        except OSError:
                            pass
            except OSError:
                pass
            shutil.rmtree(dest_dir, ignore_errors=True)
            time.sleep(1)
        if dest_dir.exists() and any(dest_dir.iterdir()):
            leftover = ", ".join(p.name for p in dest_dir.iterdir())
            self._emit(model_key, "log",
                        message=f"Could not fully clear the old Tesseract folder - these files "
                                f"are still there, possibly locked by another program (like "
                                f"antivirus): {leftover}. This can make the installer think a "
                                f"previous version still needs removing on every attempt.")

    def _find_external_tesseract(self) -> Optional[Path]:
        """Looks for a Tesseract install already on this system - installed
        manually by the person, or pre-existing - by scanning the same
        registry Uninstall entries (matched by DisplayName) used for
        cleanup, then common install locations, then PATH. Used so a manual,
        fully-interactive install (where the person can actually see and
        respond to whatever the installer's UAC/uninstall dance does) can be
        picked up automatically, without this app ever running the
        installer itself."""
        try:
            import winreg
            bases = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall", 0),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                 winreg.KEY_WOW64_64KEY),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                 winreg.KEY_WOW64_32KEY),
            ]
            for hive, base_path, view_flag in bases:
                try:
                    base_key = winreg.OpenKey(hive, base_path, 0, winreg.KEY_READ | view_flag)
                except OSError:
                    continue
                try:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(base_key, i)
                        except OSError:
                            break
                        i += 1
                        try:
                            sub = winreg.OpenKey(base_key, subkey_name, 0, winreg.KEY_READ | view_flag)
                            try:
                                display_name, _ = winreg.QueryValueEx(sub, "DisplayName")
                            except OSError:
                                display_name = ""
                            try:
                                install_location, _ = winreg.QueryValueEx(sub, "InstallLocation")
                            except OSError:
                                install_location = ""
                            winreg.CloseKey(sub)
                        except OSError:
                            continue
                        if "tesseract" in str(display_name).lower() and install_location:
                            candidate = Path(install_location) / "tesseract.exe"
                            if candidate.exists():
                                return candidate
                finally:
                    winreg.CloseKey(base_key)
        except ImportError:
            pass
        for candidate_path in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        ):
            if Path(candidate_path).exists():
                return Path(candidate_path)
        which = shutil.which("tesseract")
        if which:
            return Path(which)
        return None

    def _adopt_external_tesseract(self, model_key: str, source_exe: Path) -> bool:
        """Copies an already-installed Tesseract's files straight into this
        app's own Base Folder - a plain file copy, not an install - so the
        app stays self-contained without ever running an installer itself."""
        source_dir = source_exe.parent
        dest_dir = self.env.tesseract_exe().parent
        self._emit(model_key, "log",
                    message=f"Found an existing Tesseract install at {source_dir} - "
                            "copying it in instead of running the installer...")
        try:
            if dest_dir.exists():
                shutil.rmtree(dest_dir, ignore_errors=True)
            shutil.copytree(str(source_dir), str(dest_dir))
        except OSError as e:
            self._emit(model_key, "log", message=f"Could not copy the existing install: {e}")
            return False
        return self.env.tesseract_exe().exists()

    def _install_tesseract_binary(self, model_key: str) -> bool:
        self._emit(model_key, "log", message="Checking for an already-installed copy of Tesseract...")
        external = self._find_external_tesseract()
        if external and external.resolve() != self.env.tesseract_exe().resolve():
            if self._adopt_external_tesseract(model_key, external):
                self._emit(model_key, "log", message="Done - using the existing installation.")
                return True
            self._emit(model_key, "log",
                        message="Falling back to downloading and running the installer.")
        self._emit(model_key, "log", message="Looking up the latest Tesseract release...")
        dest_dir = self.env.tesseract_exe().parent
        self._remove_stale_tesseract_registry_entries(model_key)
        self._run_existing_tesseract_uninstaller(model_key, dest_dir)
        self._ensure_tesseract_dir_truly_clean(model_key, dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = self.env.temp_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)
        self._emit(model_key, "log",
                    message="Note: the official UB-Mannheim Windows installer's own manifest "
                            "requires administrator rights, so a UAC consent prompt will appear. "
                            "If it's declined, Tesseract will not be usable.")
        installer_path = temp_dir / "tesseract-installer.exe"
        try:
            installer_url = self._resolve_tesseract_installer_url()
            if not installer_url:
                self._emit(model_key, "error",
                            message="Could not find the Windows 64-bit installer in the latest "
                                    "Tesseract release. It may have been renamed upstream.")
                return False
            self._emit(model_key, "log", message="Downloading Tesseract OCR engine installer...")
            import urllib.request
            urllib.request.urlretrieve(installer_url, str(installer_path))
        except Exception as e:
            self._emit(model_key, "error", message=f"Could not download Tesseract installer: {e}")
            return False
        try:
            self._emit(model_key, "log", message="Requesting administrator permission (UAC prompt)...")
            params = f"/S /D={dest_dir}"
            ok = self._run_tesseract_installer_once(model_key, installer_path, params)
            if not ok and self._cancel_flags.get(model_key):
                return False
            if not ok and not self.env.tesseract_exe().exists():
                # Confirmed directly (not just inferred from timing): this
                # installer's first run visibly uninstalls a previously-
                # registered version and then stops, without reinstalling.
                # _run_tesseract_installer_once now only returns after
                # genuinely confirming the first run has finished (see its
                # grace period), so it's safe to launch a second, fresh
                # attempt here - it isn't racing a still-pending first one.
                self._emit(model_key, "log",
                            message="The installer appears to have removed a previously-"
                                    "registered version and stopped there - running it once "
                                    "more to actually install...")
                time.sleep(3)
                self._emit(model_key, "log",
                            message="Requesting administrator permission again (a second "
                                    "UAC prompt may appear - please click 'Yes' when it does)...")
                ok = self._run_tesseract_installer_once(model_key, installer_path, params)
            if ok:
                self._emit(model_key, "log", message="Cleaning up the downloaded installer file.")
            else:
                self._emit(model_key, "error",
                            message="Tesseract installer did not finish within the time limit "
                                    "even after a second attempt (or a UAC prompt may have "
                                    "been declined). Cleaning up any leftover installer process...")
                try:
                    subprocess.run(["taskkill", "/T", "/F", "/IM", installer_path.name],
                                   capture_output=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            return ok
        finally:
            # The installer file is a one-time-use temp artifact - the user never needs it again.
            try:
                if installer_path.exists():
                    installer_path.unlink()
            except OSError:
                pass

    def _install_pandoc_binary(self, model_key: str) -> bool:
        if self._cancel_flags.get(model_key):
            self._emit(model_key, "log", message="Install cancelled.")
            return False
        self._emit(model_key, "log", message="Downloading Pandoc via pypandoc.download_pandoc()...")
        try:
            import pypandoc
            target_dir = self.env.pandoc_exe().parent
            target_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = self.env.temp_dir()
            temp_dir.mkdir(parents=True, exist_ok=True)
            pypandoc.download_pandoc(targetfolder=str(target_dir),
                                      download_folder=str(temp_dir),
                                      delete_installer=True)
        except Exception as e:
            self._emit(model_key, "error", message=f"Pandoc download failed: {e}")
            return False
        if self._cancel_flags.get(model_key):
            self._emit(model_key, "log", message="Install cancelled.")
            return False
        return self.env.pandoc_exe().exists() or shutil.which("pandoc") is not None

    # ---------- python runtime auto-provisioning ----------

    PYTHON_RUNTIME_KEY = "python_runtime"

    def install_python_runtime_async(self) -> threading.Thread:
        t = threading.Thread(target=self._install_python_runtime_worker, daemon=True)
        t.start()
        return t

    def _resolve_python_runtime_download(self) -> tuple:
        """Tries each fallback version in order (HEAD request first, so a 404
        fails fast without downloading anything) and returns (version, url, path)
        for the first one that actually exists, or (None, None, None). Also
        guards against a "soft 404" - some CDNs/edges return HTTP 200 with a
        small HTML error page instead of a real 404 status for a missing file;
        a genuine Windows installer .exe is always tens of MB, so anything
        claiming to be one under ~5 MB is treated as not actually found rather
        than trusted."""
        import urllib.request
        temp_dir = self.env.temp_dir()
        temp_dir.mkdir(parents=True, exist_ok=True)
        min_plausible_installer_bytes = 5 * 1024 * 1024
        for version in PYTHON_RUNTIME_FALLBACK_VERSIONS:
            url = f"https://www.python.org/ftp/python/{version}/python-{version}-amd64.exe"
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status != 200:
                        continue
                    length = resp.headers.get("Content-Length")
                    if length is not None and int(length) < min_plausible_installer_bytes:
                        continue
                    return version, url, temp_dir / f"python-{version}-amd64.exe"
            except Exception:
                continue
        return None, None, None

    @staticmethod
    def _looks_like_valid_windows_installer(path: Path) -> bool:
        """Same "soft 404" guard, applied to what actually landed on disk after
        the download - catches the case where Content-Length was missing or
        lied about, so a corrupt/wrong file never gets silently executed as if
        it were the real installer."""
        try:
            if path.stat().st_size < 5 * 1024 * 1024:
                return False
            with open(path, "rb") as f:
                return f.read(2) == b"MZ"  # standard Windows PE executable header
        except OSError:
            return False

    def _emit_result_banner(self, model_key: str, success: bool, summary: str) -> None:
        """One unmissable, consistently-worded line at the very end of an
        attempt, regardless of which branch got there - so 'did it work or
        not' never depends on the person correctly parsing a wall of
        installer log text to find out."""
        banner = "RESULT: SUCCESS" if success else "RESULT: FAILED"
        self._emit(model_key, "log" if success else "error", message=f"{banner} - {summary}")

    def _install_python_runtime_worker(self) -> None:
        key = self.PYTHON_RUNTIME_KEY
        self._cancel_flags[key] = False
        self._start_fresh_log(key)
        try:
            self._emit(key, "status", status=InstallStatus.INSTALLING.value)
            self.env.ensure_layout()

            free_gb = self.env.free_space_gb()
            if free_gb < 1.0:
                self._emit(key, "error",
                            message=f"Not enough disk space: needs ~0.5 GB, only {free_gb:.1f} GB free.")
                self._emit_result_banner(key, False, "not enough free disk space.")
                self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return

            self._emit(key, "log", message="Looking up the current Python 3.12 release for Windows...")
            version, url, installer_path = self._resolve_python_runtime_download()
            if not version:
                self._emit(key, "error",
                            message="Could not find a downloadable Windows installer for any known "
                                    "Python 3.12 release. Check your internet connection, or install "
                                    "Python 3.12 manually from python.org.")
                self._emit_result_banner(key, False, "no downloadable installer found.")
                self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return
            self._emit(key, "log",
                        message=f"Downloading Python {version} from python.org "
                                "(official installer, ~25 MB)...")
            try:
                import urllib.request
                urllib.request.urlretrieve(url, str(installer_path))
            except Exception as e:
                self._emit(key, "error", message=f"Could not download the Python installer: {e}")
                self._emit_result_banner(key, False, "could not download the installer.")
                self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return
            if not self._looks_like_valid_windows_installer(installer_path):
                size = installer_path.stat().st_size if installer_path.exists() else 0
                self._emit(key, "error",
                            message=f"The download from {url} doesn't look like a real Windows "
                                    f"installer (got {size} bytes) - python.org may have returned "
                                    f"an error page instead of the file. Try again, or install "
                                    f"Python 3.12 manually from python.org.")
                self._emit_result_banner(key, False, "downloaded file was not a valid installer.")
                self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return

            target_dir = self.env.python_runtime_dir()
            target_dir.mkdir(parents=True, exist_ok=True)
            burn_log_path = self.env.temp_dir() / "python_install_burn.log"
            uninstall_log_path = self.env.temp_dir() / "python_uninstall_burn.log"
            # Exit code 1603 ("fatal error during installation") most commonly
            # means Windows Installer already has this exact product
            # registered per-user - which can survive an earlier interrupted
            # or repeated attempt even after the install folder itself was
            # deleted, since that registration lives in the registry/MSI
            # database, not on disk. Best-effort self-uninstall first so a
            # stale registration doesn't conflict with the fresh install below.
            # Matching TargetDir is included since Burn ties per-user feature
            # registration to it.
            self._emit(key, "log", message="Clearing any leftover registration from a previous attempt...")
            try:
                subprocess.run(
                    [str(installer_path), "/uninstall", "/quiet", "/log", str(uninstall_log_path),
                     f"TargetDir={target_dir}"],
                    capture_output=True, timeout=120)
            except (OSError, subprocess.TimeoutExpired):
                pass

            self._emit(key, "log",
                        message="Installing into the Base Folder (per-user, silent, no admin rights "
                                "or changes to your system Python/PATH)...")
            # Deliberately NOT passing Include_doc=0/Include_tcltk=0 here: on a
            # machine where those components are already installed from an
            # earlier attempt, requesting their removal is exactly what has
            # been triggering the repeated 1603 failure (Windows Installer
            # fails to uninstall them for reasons outside this app's control -
            # see the stale-registration hint below). Leaving them alone avoids
            # that specific failure point entirely.
            install_args = ["InstallAllUsers=0", "PrependPath=0", "Include_launcher=0",
                             "Include_test=0", "Include_pip=1", f"TargetDir={target_dir}"]
            try:
                result = self._run_cancellable(
                    key, [str(installer_path), "/quiet", "/log", str(burn_log_path)] + install_args,
                    timeout=600)
                if result is None:
                    self._emit_result_banner(key, False, "cancelled by user.")
                    self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                    return
                if result.returncode != 0:
                    self._emit(key, "error",
                                message=f"Python installer exited with code {result.returncode}.")
                    self._emit_process_output(key, result)
                    self._emit_burn_log_tail(key, burn_log_path)
                    if result.returncode == 1603:
                        self._emit_stale_registration_hint(key, uninstall_log_path, target_dir)
                    self._emit_result_banner(
                        key, False, f"installer exited with code {result.returncode}. "
                                    "See the diagnostic log above for the real reason.")
                    self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                    return
            except subprocess.TimeoutExpired:
                self._emit(key, "error", message="Python installer timed out.")
                self._emit_result_banner(key, False, "installer timed out.")
                self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return
            except OSError as e:
                self._emit(key, "error", message=f"Could not run the Python installer: {e}")
                self._emit_result_banner(key, False, "could not run the installer.")
                self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                return

            ok = self.env.python_runtime_exe().exists()
            if not ok:
                # Confirmed root cause from a prior attempt's log: Windows
                # Installer's own per-feature registration can still say
                # "Present" from an earlier attempt even after we've deleted
                # the target folder ourselves - Burn trusts that cached state
                # rather than checking the disk, so a plain install silently
                # does nothing and still reports success. /repair forces it
                # to re-cache every payload regardless of the cached state,
                # which is exactly what's needed here.
                self._emit(key, "log",
                            message="Installer reported success but python.exe is missing - "
                                    "retrying with /repair, which forces reinstalling files "
                                    "Windows Installer still believes are present...")
                repair_log_path = self.env.temp_dir() / "python_repair_burn.log"
                try:
                    repair_result = self._run_cancellable(
                        key, [str(installer_path), "/repair", "/quiet", "/log", str(repair_log_path)]
                        + install_args, timeout=600)
                    if repair_result is None:
                        self._emit_result_banner(key, False, "cancelled by user.")
                        self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
                        return
                    if repair_result.returncode != 0:
                        self._emit(key, "log",
                                    message=f"Repair pass exited with code {repair_result.returncode}.")
                        self._emit_process_output(key, repair_result)
                except (subprocess.TimeoutExpired, OSError) as e:
                    self._emit(key, "log", message=f"Repair pass could not run: {e}")
                ok = self.env.python_runtime_exe().exists()
                if not ok:
                    self._emit_burn_log_tail(key, repair_log_path)

            try:
                if installer_path.exists():
                    installer_path.unlink()
            except OSError:
                pass

            if ok:
                self._emit(key, "log", message="Verifying the installation...")
                try:
                    verify = subprocess.run([str(self.env.python_runtime_exe()), "--version"],
                                             capture_output=True, timeout=15)
                    ok = verify.returncode == 0
                    if not ok:
                        self._emit_process_output(key, verify)
                except Exception as e:
                    ok = False
                    self._emit(key, "log", message=f"Verification check raised: {e}")

            if ok:
                self._emit(key, "log",
                            message=f"Python {version} is ready. Heavy model installs "
                                    "will use it automatically from now on.")
                self._emit_result_banner(key, True, f"Python {version} installed and verified.")
                self._emit(key, "status", status=InstallStatus.INSTALLED.value)
            else:
                self._emit(key, "error",
                            message="Installation (and a /repair retry) finished without "
                                    "python.exe ending up in the target folder. This official "
                                    "installer needs internet access *during* the install to "
                                    "fetch some components - if a firewall or antivirus blocked "
                                    "that partway through, it can still report success without "
                                    "finishing. See the installer's own log(s) above for the "
                                    "actual reason.")
                self._emit_stale_registration_hint(key, uninstall_log_path, target_dir)
                self._emit_result_banner(
                    key, False, "installer (and repair retry) reported success but python.exe is missing.")
                self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)
        except Exception as e:
            self._emit(key, "error", message=f"Unexpected error: {e}")
            self._emit_result_banner(key, False, f"unexpected error - {e}")
            self._emit(key, "status", status=InstallStatus.NOT_INSTALLED.value)

    def _emit_stale_registration_hint(self, model_key: str, uninstall_log_path: Path, target_dir: Path) -> None:
        """Shown when the pattern strongly suggests our own pre-uninstall
        step didn't fully clear a stale per-user Windows Installer
        registration for a previous attempt - since that lives in the
        registry/MSI database rather than the target folder, deleting the
        Base Folder alone never fixes it, and we can only automate so much
        of MSI's own repair/cleanup from here."""
        self._emit(model_key, "log",
                    message="This looks like Windows Installer still has a leftover per-user "
                            "registration for Python 3.12 from an earlier attempt that our "
                            "own automatic cleanup step couldn't fully remove (see its log "
                            f"below). A couple of things worth trying: open Windows Settings > "
                            "Apps, search for 'Python 3.12', and uninstall it manually if listed; "
                            "or, if this keeps happening, try Settings > Change Base Folder to a "
                            "location outside Downloads (e.g. Documents or directly under C:\\) - "
                            "some antivirus/'Controlled Folder Access' setups specifically "
                            "restrict installers from writing inside Downloads.")
        self._emit_burn_log_tail(model_key, uninstall_log_path, max_lines=60)

    def _emit_process_output(self, model_key: str, result) -> None:
        """Surfaces a finished subprocess's stdout/stderr into the exportable
        log instead of silently discarding it - the whole point of capturing
        output is defeated if it's thrown away on the exact path (failure)
        where it's actually needed."""
        for stream_name, data in (("stdout", result.stdout), ("stderr", result.stderr)):
            if not data:
                continue
            text = data.decode(errors="ignore") if isinstance(data, bytes) else str(data)
            text = text.strip()
            if text:
                self._emit(model_key, "log", message=f"--- installer {stream_name} ---\n{text}")

    @staticmethod
    def _decode_log_bytes(raw: bytes) -> str:
        if raw.startswith(b"\xff\xfe"):
            return raw.decode("utf-16-le", errors="replace")
        if raw.startswith(b"\xfe\xff"):
            return raw.decode("utf-16-be", errors="replace")
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig", errors="replace")
        try:
            text = raw.decode("utf-8")
            # A UTF-16 file with no BOM still decodes as UTF-8 without
            # raising (null bytes are valid UTF-8) but comes out full of
            # NUL characters interleaved with the real text - a real UTF-8
            # log shouldn't look like that, so treat it as a sign to retry
            # rather than trust this result.
            if text.count("\x00") < max(1, len(text) // 4):
                return text
        except UnicodeDecodeError:
            pass
        for encoding in ("utf-16-le", "utf-16-be"):
            try:
                return raw.decode(encoding)
            except UnicodeError:
                continue
        return raw.decode("latin-1", errors="replace")

    def _emit_burn_log_tail(self, model_key: str, burn_log_path: Path, max_lines: int = 120) -> None:
        """python.org's official installer is a WiX Burn bootstrapper; /log
        makes it write a real diagnostic log (HRESULTs, which component
        failed, network errors) that /quiet alone never produces. Without
        this, a failed install gives us nothing more to go on than 'exit
        code 1603, python.exe missing' - not enough to fix anything from an
        exported log alone. Different Burn log files from the same installer
        have been observed with different encodings (plain UTF-8 for one,
        UTF-16 for another), so this detects rather than assumes."""
        try:
            if not burn_log_path.exists():
                self._emit(model_key, "log", message="(No installer diagnostic log was produced.)")
                return
            text = self._decode_log_bytes(burn_log_path.read_bytes())
            lines = text.splitlines()
            tail = lines[-max_lines:]
            prefix = f"... ({len(lines) - len(tail)} earlier lines omitted) ...\n" if len(lines) > max_lines else ""
            self._emit(model_key, "log",
                        message=f"--- installer diagnostic log (tail): {burn_log_path} ---\n"
                                f"{prefix}" + "\n".join(tail))
        except Exception as e:
            self._emit(model_key, "log", message=f"(Could not read installer diagnostic log: {e})")

    # ---------- verify ----------

    def _verify_model_worker(self, model_key: str, from_install: bool = False) -> None:
        model = MODEL_REGISTRY[model_key]
        if not from_install:
            self._start_fresh_log(model_key)
        self._emit(model_key, "log", message="Running smoke test...")
        ok, detail = self._smoke_test(model)
        if ok:
            self.settings.set_cached_status(model_key, InstallStatus.INSTALLED.value)
            self._emit(model_key, "status", status=InstallStatus.INSTALLED.value)
            self._emit(model_key, "log", message="Verified: model works.")
        else:
            self.settings.set_cached_status(model_key, InstallStatus.FAILED_VERIFICATION.value)
            self._emit(model_key, "status", status=InstallStatus.FAILED_VERIFICATION.value)
            self._emit(model_key, "error", message=f"Verification failed: {detail}")

    def _smoke_test(self, model: ModelDef) -> tuple:
        try:
            if model.special_case == "tesseract_binary":
                exe = self.env.tesseract_exe()
                if not exe.exists():
                    return False, "tesseract.exe not found."
                result = subprocess.run([str(exe), "--version"], capture_output=True, timeout=15)
                return result.returncode == 0, result.stderr.decode(errors="ignore")

            if model.special_case == "pandoc_binary":
                exe = self.env.pandoc_exe()
                exe_path = str(exe) if exe.exists() else "pandoc"
                result = subprocess.run([exe_path, "--version"], capture_output=True, timeout=15)
                return result.returncode == 0, result.stderr.decode(errors="ignore")

            if model.weight == Weight.LIGHT:
                py = sys.executable
                import_name = _light_import_name(model.key)
                result = subprocess.run([py, "-c", f"import {import_name}"],
                                         capture_output=True, timeout=30)
                return result.returncode == 0, result.stderr.decode(errors="ignore")

            # Heavy: run the runner script against a tiny built-in sample, reusing
            # the same inactivity-based streaming logic as real conversions
            # (_convert_heavy) instead of a raw blocking subprocess.run(timeout=900).
            # That old approach had two real problems: (1) capture_output=True
            # buffers everything silently until the process ends or times out, so
            # the smoke test gave zero live feedback for up to 15 minutes - the
            # same "is it stuck or just slow?" confusion as a real conversion
            # timeout; (2) a flat 900s total-duration cap kills a model that's
            # still genuinely downloading multi-GB weights on a slower connection,
            # exactly like the old conversion-timeout bug. Reusing _convert_heavy
            # fixes both: live per-line progress reaches the log during install,
            # and the model is only killed after real silence, not just slowness.
            venv_python = self.env.model_python(model.key)
            runner = self.env.model_runner_script(model.key)
            if not venv_python.exists() or not runner.exists():
                return False, "Isolated environment or runner script missing."
            sample_in, sample_out = _write_sample_for_model(model.key)
            try:
                def on_output(text: str, key=model.key) -> None:
                    self._emit(key, "log", message=text)

                cancel_flag = lambda k=model.key: self._cancel_flags.get(k, False)
                try:
                    _convert_heavy(model.key, self.env, sample_in, sample_out,
                                    inactivity_timeout_seconds=900, max_runtime_seconds=3600,
                                    cancel_flag=cancel_flag, logger=_ConversionLogger(None),
                                    on_output=on_output)
                except ConversionError as e:
                    return False, str(e)
                return sample_out.exists() and sample_out.stat().st_size >= 0, ""
            finally:
                for p in (sample_in, sample_out):
                    try:
                        if p.exists():
                            p.unlink()
                    except OSError:
                        pass
        except subprocess.TimeoutExpired:
            return False, "Smoke test timed out."
        except Exception as e:
            return False, str(e)

    def _repair_model_worker(self, model_key: str) -> None:
        self._start_fresh_log(model_key)
        self._emit(model_key, "log", message="Repairing: removing and recreating environment.")
        model = MODEL_REGISTRY[model_key]
        if model.weight == Weight.HEAVY:
            env_dir = self.env.model_env_dir(model_key)
            if env_dir.exists():
                shutil.rmtree(env_dir, ignore_errors=True)
        self._install_model_worker(model_key, reset_log=False)


def _light_import_name(model_key: str) -> str:
    mapping = {
        "pymupdf4llm": "pymupdf4llm",
        "tesseract": "pytesseract",
        "trafilatura": "trafilatura",
        "markdownify": "markdownify",
        "html_to_markdown": "html_to_markdown",
        "markitdown": "markitdown",
        "mammoth": "mammoth",
        "pandoc": "pypandoc",
        "subtitles": "pysrt",
    }
    return mapping.get(model_key, model_key)


def _write_sample_for_model(model_key: str) -> tuple:
    """Writes a tiny built-in sample file appropriate to the model, returns (in_path, out_path)."""
    tmp_dir = Path(os.environ.get("TEMP", ".")) / "mdconverter_smoketest"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stamp = uuid.uuid4().hex[:8]
    if model_key in ("marker", "mineru"):
        # Must be an image-only PDF (no real text layer), not a text-native one -
        # marker/mineru skip their OCR sub-models (detection/recognition/layout/
        # table/equation) entirely when real text is already present, so a
        # text-native smoke sample never downloads or exercises those weights.
        # That gap is exactly what let a "passing" smoke test hide an OCR path
        # that then had to download+load extra models during the user's first
        # real scanned-PDF conversion instead of during install.
        in_path = tmp_dir / f"sample_{stamp}.pdf"
        _write_minimal_scanned_pdf(in_path)
    elif model_key in ("paddleocr", "surya"):
        in_path = tmp_dir / f"sample_{stamp}.png"
        _write_minimal_png(in_path)
    else:
        in_path = tmp_dir / f"sample_{stamp}.pdf"
        _write_minimal_pdf(in_path)
    out_path = tmp_dir / f"sample_{stamp}.md"
    return in_path, out_path


def _write_minimal_pdf(path: Path) -> None:
    """Uses PyMuPDF (already a Light dependency) to build a real one-page PDF
    with actual visible text, rather than a hand-rolled, effectively-blank PDF
    stub - a blank/degenerate page risks tripping edge cases deep inside a
    layout or OCR model (empty-result crashes, division by zero on a zero-area
    detected region, etc.) that have nothing to do with whether the install
    itself is actually working."""
    try:
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=300)
        page.insert_text((40, 100), "MD Converter smoke test.\nHello World 12345.", fontsize=14)
        doc.save(str(path))
        doc.close()
    except Exception:
        minimal_pdf = (
            b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
        )
        path.write_bytes(minimal_pdf)


def _write_minimal_scanned_pdf(path: Path) -> None:
    """Builds a one-page PDF containing only a rasterized image of text (no
    real text layer) - i.e. what a scanned document actually looks like to a
    converter - so OCR-only code paths get exercised during install/smoke
    test rather than the first time the user converts a real scanned file."""
    try:
        from PIL import Image, ImageDraw
        import pymupdf
        img = Image.new("RGB", (600, 300), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((20, 120), "MD Converter smoke test. Hello World 12345.", fill="black")
        img_path = path.with_suffix(".png")
        img.save(img_path)
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=300)
        page.insert_image(pymupdf.Rect(0, 0, 600, 300), filename=str(img_path))
        doc.save(str(path))
        doc.close()
        try:
            img_path.unlink()
        except OSError:
            pass
    except Exception:
        _write_minimal_pdf(path)  # best-effort fallback; still a valid (if less useful) sample


def _write_minimal_png(path: Path) -> None:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (240, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 35), "Hello World 12345", fill="black")
        img.save(path)
    except Exception:
        # 1x1 transparent PNG bytes as a last resort
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c6300010000050001"
            "0d0a2db40000000049454e44ae426082"
        )
        path.write_bytes(png_bytes)


# ===== CONVERTER RUNNERS =====
# Thin wrappers: Light models called in-process, Heavy models shelled out to their venv.

class ConversionError(Exception):
    pass


def convert_file(model_key: str, env: EnvManager, source: Path, output_md: Path,
                  inactivity_timeout_seconds: int, max_runtime_seconds: int,
                  cancel_flag: Callable[[], bool],
                  log_path: Optional[Path] = None,
                  on_output: Optional[Callable[[str], None]] = None) -> None:
    model = MODEL_REGISTRY[model_key]
    output_md.parent.mkdir(parents=True, exist_ok=True)
    logger = _ConversionLogger(log_path)
    logger.write(f"=== {model.display_name} converting {source.name} "
                 f"({source.stat().st_size / (1024 * 1024):.2f} MB) ===")
    try:
        if model.weight == Weight.LIGHT:
            logger.write("Running in-process (Light model).")
            _convert_light(model_key, source, output_md)
        else:
            _convert_heavy(model_key, env, source, output_md,
                            inactivity_timeout_seconds, max_runtime_seconds, cancel_flag,
                            logger, on_output)
        logger.write("=== Done ===")
    except Exception as e:
        logger.write(f"=== FAILED: {e} ===")
        raise
    finally:
        logger.close()


class _ConversionLogger:
    """Writes a full, untruncated per-conversion log to disk in real time, so
    a failed conversion can be exported and diagnosed - not just the last
    2000 characters that fit in the on-screen error message."""

    def __init__(self, log_path: Optional[Path]):
        self.path = log_path
        self._fh = None
        self._lock = threading.Lock()
        if log_path is not None:
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                self._fh = open(log_path, "a", encoding="utf-8")
            except OSError:
                self._fh = None

    def write(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            if self._fh is None:
                return
            try:
                stamp = datetime.now().strftime("%H:%M:%S")
                self._fh.write(f"[{stamp}] {text.rstrip()}\n")
                self._fh.flush()
            except (OSError, ValueError):
                pass  # e.g. writing after close() lost a race - never worth crashing the caller over

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None


def _convert_light(model_key: str, source: Path, output_md: Path) -> None:
    ext = source.suffix.lower()
    try:
        if model_key == "pymupdf4llm":
            import pymupdf4llm
            md = pymupdf4llm.to_markdown(str(source))
            output_md.write_text(md, encoding="utf-8")

        elif model_key == "tesseract":
            import pytesseract
            from PIL import Image
            if ext == ".pdf":
                import pymupdf
                doc = pymupdf.open(str(source))
                texts = []
                for page in doc:
                    pix = page.get_pixmap()
                    img_path = output_md.with_suffix(f".page{page.number}.png")
                    pix.save(str(img_path))
                    texts.append(pytesseract.image_to_string(Image.open(img_path)))
                    img_path.unlink(missing_ok=True)
                output_md.write_text("\n\n".join(texts), encoding="utf-8")
            else:
                text = pytesseract.image_to_string(Image.open(source))
                output_md.write_text(text, encoding="utf-8")

        elif model_key == "trafilatura":
            import trafilatura
            html = source.read_text(encoding="utf-8", errors="ignore")
            md = trafilatura.extract(html, output_format="markdown") or ""
            output_md.write_text(md, encoding="utf-8")

        elif model_key == "markdownify":
            from markdownify import markdownify as md_convert
            html = source.read_text(encoding="utf-8", errors="ignore")
            output_md.write_text(md_convert(html), encoding="utf-8")

        elif model_key == "html_to_markdown":
            from html_to_markdown import convert_to_markdown
            html = source.read_text(encoding="utf-8", errors="ignore")
            output_md.write_text(convert_to_markdown(html), encoding="utf-8")

        elif model_key == "markitdown":
            from markitdown import MarkItDown
            md_engine = MarkItDown()
            result = md_engine.convert(str(source))
            output_md.write_text(result.text_content, encoding="utf-8")

        elif model_key == "mammoth":
            import mammoth
            with open(source, "rb") as f:
                result = mammoth.convert_to_markdown(f)
            output_md.write_text(result.value, encoding="utf-8")

        elif model_key == "pandoc":
            import pypandoc
            pypandoc.convert_file(str(source), "markdown", outputfile=str(output_md))

        elif model_key == "subtitles":
            _convert_subtitles(source, output_md)

        else:
            raise ConversionError(f"No in-process converter defined for '{model_key}'.")
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(str(e)) from e


def _convert_subtitles(source: Path, output_md: Path) -> None:
    ext = source.suffix.lower()
    lines_out = []
    if ext == ".srt":
        import pysrt
        subs = pysrt.open(str(source))
        for sub in subs:
            lines_out.append(f"**{sub.start} --> {sub.end}**\n\n{sub.text}")
    elif ext == ".vtt":
        import webvtt
        for caption in webvtt.read(str(source)):
            lines_out.append(f"**{caption.start} --> {caption.end}**\n\n{caption.text}")
    else:
        raise ConversionError(f"Unsupported subtitle extension: {ext}")
    output_md.write_text("\n\n".join(lines_out), encoding="utf-8")


def _convert_heavy(model_key: str, env: EnvManager, source: Path, output_md: Path,
                    inactivity_timeout_seconds: Optional[int], max_runtime_seconds: Optional[int],
                    cancel_flag: Callable[[], bool],
                    logger: "_ConversionLogger",
                    on_output: Optional[Callable[[str], None]] = None) -> None:
    venv_python = env.model_python(model_key)
    runner = env.model_runner_script(model_key)
    if not venv_python.exists() or not runner.exists():
        raise ConversionError(f"{model_key} is not installed correctly. Reinstall from Model Manager.")
    proc = subprocess.Popen(
        [str(venv_python), str(runner), str(source), str(output_md)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        env=_heavy_subprocess_env(), bufsize=0,
    )

    # Raw-byte reader thread: readline() only returns on '\n', so tqdm's '\r'-only
    # progress updates (model download bars, page progress) previously sat in the
    # pipe invisibly for the entire run. Reading raw chunks and splitting on both
    # '\n' and '\r' means anything the child prints reaches the log/UI promptly.
    captured = []
    cap_lock = threading.Lock()
    last_real_output = {"t": time.time(), "text": ""}

    def _handle(piece: str) -> None:
        if not piece:
            return
        with cap_lock:
            captured.append(piece)
            last_real_output["t"] = time.time()
            last_real_output["text"] = piece
        logger.write(piece)
        if on_output:
            on_output(piece)

    def _reader():
        buf = b""
        while True:
            chunk = proc.stdout.read(256)
            if not chunk:
                break
            buf += chunk
            while True:
                idx_n = buf.find(b"\n")
                idx_r = buf.find(b"\r")
                candidates = [i for i in (idx_n, idx_r) if i != -1]
                if not candidates:
                    break
                idx = min(candidates)
                _handle(buf[:idx].decode(errors="ignore").strip())
                buf = buf[idx + 1:]
        _handle(buf.decode(errors="ignore").strip())

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    # The timeout is inactivity-based, not total-duration: a model that keeps
    # producing output (even one progress line every 60-90s, as marker does
    # per page on a huge scanned book) is left running indefinitely as long
    # as it keeps making progress. Only genuine silence - no new output at
    # all for inactivity_timeout_seconds - is treated as "hung". A separate,
    # much larger max_runtime_seconds is a pure safety net for a process that
    # keeps logging but is truly stuck in a loop and never finishing. Either
    # limit can be disabled entirely (None) from Settings.
    #
    # Startup grace: before the model prints its FIRST real line, it may be
    # silently loading multi-GB weights from disk - this can legitimately take
    # much longer than the steady-state per-page inactivity budget, so the
    # first output is exempted from the inactivity check up to this floor.
    startup_grace_seconds = max(inactivity_timeout_seconds or 0, 900)

    start = time.time()
    last_heartbeat_log = start
    last_ui_update = start
    last_poll = start
    while proc.poll() is None:
        now = time.time()

        # Sleep/wake or severe system-stall guard: if wall-clock jumped far more
        # than this loop could have possibly slept on its own (0.1s), the OS was
        # very likely suspended (laptop lid closed, Windows sleep) or the whole
        # machine was frozen (thermal throttle, disk thrash) for that stretch -
        # neither means the model itself went unresponsive, so pardon the gap
        # instead of counting it against the model's inactivity/runtime budget.
        stall = now - last_poll
        if stall > 20:
            pardon = stall - 0.1
            last_real_output["t"] += pardon
            start += pardon
            logger.write(f"Detected a {int(stall)}s gap in monitoring (system sleep/suspend or "
                         f"severe stall) - not counting it against this model's timeout.")
            now = time.time()
        last_poll = now

        if cancel_flag():
            _kill_pid_tree(proc.pid)
            reader_thread.join(timeout=5)  # let the reader drain/exit before the logger gets closed
            logger.write("Cancelled by user - the process was still running at that point.")
            raise ConversionError("Cancelled by user.")

        with cap_lock:
            since_output = now - last_real_output["t"]
            last_text = last_real_output["text"]
            has_output_yet = bool(captured)
        elapsed = now - start
        effective_inactivity_limit = inactivity_timeout_seconds
        if not has_output_yet and effective_inactivity_limit is not None:
            effective_inactivity_limit = max(effective_inactivity_limit, startup_grace_seconds)

        if effective_inactivity_limit is not None and since_output > effective_inactivity_limit:
            _kill_pid_tree(proc.pid)
            reader_thread.join(timeout=5)
            logger.write(
                f"Killed: no new output for {int(since_output)}s (limit: "
                f"{effective_inactivity_limit}s) - the model appears unresponsive/hung. "
                f"Last output was: \"{last_text[-200:]}\". If this model just goes quiet "
                f"for long stretches on legitimate large files, raise its inactivity "
                f"timeout in Settings, or disable it entirely.")
            raise ConversionError(
                f"No response for {int(since_output)}s (inactivity limit "
                f"{effective_inactivity_limit}s) - treated as hung.")
        if max_runtime_seconds is not None and elapsed > max_runtime_seconds:
            _kill_pid_tree(proc.pid)
            reader_thread.join(timeout=5)
            logger.write(
                f"Killed: exceeded the {max_runtime_seconds}s maximum run time for this "
                f"model, even though it was still producing output (last output {int(since_output)}s "
                f"ago: \"{last_text[-200:]}\"). This is a safety cap for extremely large files - "
                f"raise 'Max total runtime' for this model in Settings, or disable it entirely.")
            raise ConversionError(f"Exceeded maximum run time of {max_runtime_seconds}s.")
        # UI gets a live elapsed timer every ~2s; the on-disk log only gets a
        # heartbeat line every 30s, so hundreds of repetitive "still running"
        # lines don't drown out the model's own real progress output.
        if now - last_ui_update >= 2:
            msg = f"... still running ({int(elapsed)}s elapsed, last output {int(since_output)}s ago)"
            if on_output:
                on_output(msg)
            last_ui_update = now
            if now - last_heartbeat_log >= 30:
                logger.write(msg)
                last_heartbeat_log = now
        time.sleep(0.1)
    reader_thread.join(timeout=5)
    if proc.returncode != 0:
        with cap_lock:
            tail = "\n".join(captured[-80:])
        raise ConversionError(tail or f"Exit code {proc.returncode}")


def _kill_pid_tree(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


ASSET_PRODUCING_MODELS = {"docling", "marker", "mineru", "unstructured"}


def output_paths_for(source: Path, out_dir: Path) -> tuple:
    md_path = out_dir / f"{source.stem}.md"
    assets_dir = out_dir / f"{source.stem}_assets"
    return md_path, assets_dir


# ===== GUI: SHARED HELPERS =====

STATUS_ICON = {
    InstallStatus.INSTALLED.value: "\u2705 Installed",
    InstallStatus.NOT_INSTALLED.value: "\u2b07\ufe0f Not installed",
    InstallStatus.FAILED_VERIFICATION.value: "\u26a0\ufe0f Failed verification",
    InstallStatus.INSTALLING.value: "\u23f3 Installing...",
}

# Model Manager tab: colored glyph + colored text, so status is visible at a glance.
STATUS_DISPLAY = {
    InstallStatus.INSTALLED.value: ("\u2714", "Installed", "#2e9e44"),
    InstallStatus.NOT_INSTALLED.value: ("\u2716", "Not Installed", "#c0392b"),
    InstallStatus.FAILED_VERIFICATION.value: ("\u2716", "Failed verification", "#c0392b"),
    InstallStatus.INSTALLING.value: ("\u23f3", "Installing...", "#b8860b"),
}


def human_pip_error(raw: str) -> str:
    lowered = raw.lower()
    if "could not find a version" in lowered:
        return "That package/version isn't available (name or version may be wrong)."
    if ("failed building wheel" in lowered or "failed-wheel-build-for-install" in lowered
            or "cl.exe' failed" in lowered or "zlib" in lowered or "libxml2" in lowered):
        return ("This model's dependencies don't have ready-made packages for your Python "
                "version yet, so it tried to compile them and failed. Installing Python "
                "3.12 alongside your current Python (from python.org) usually fixes this - "
                "this app will automatically use it for this model's install once it's "
                "available, no other setup needed.")
    if "connection" in lowered or "timed out" in lowered or "network" in lowered:
        return "Network problem while downloading. Check your internet connection."
    if "permission denied" in lowered:
        return "Permission denied writing to the install folder."
    if "no space left" in lowered:
        return "Not enough disk space to finish the install."
    return "The install failed. See details below."


# ===== GUI: CONVERT TAB =====

class PercentProgressBar(Canvas):
    """A progress bar drawn entirely on one canvas - track, fill, and the
    percentage text are all pixels of the SAME drawing surface, so the text
    is genuinely part of the bar rather than a separate widget placed on top
    of it. A CTkLabel's "transparent" fg_color only means "match my parent
    frame's flat color" (Tk has no real alpha compositing between sibling
    widgets), so overlaying a label on a CTkProgressBar always leaves a
    faint mismatched box wherever the label's flat background differs from
    whatever color the bar has at that pixel. Drawing the text with the bar
    avoids that entirely, and a small dark halo behind the white text keeps
    it readable whether it lands on the filled or unfilled portion."""

    _LIGHT_TRACK = "#939BA2"
    _DARK_TRACK = "#4A4D50"
    _LIGHT_FILL = "#3B8ED0"
    _DARK_FILL = "#1F6AA5"

    def __init__(self, master, height: int = 26, **kwargs):
        super().__init__(master, height=height, highlightthickness=0, bd=0, **kwargs)
        self._fraction = 0.0
        self._text_override: Optional[str] = None
        self._bar_height = height
        self.bind("<Configure>", lambda e: self._redraw())
        self._redraw()

    def _colors(self) -> tuple:
        dark = ctk.get_appearance_mode() == "Dark"
        track = self._DARK_TRACK if dark else self._LIGHT_TRACK
        fill = self._DARK_FILL if dark else self._LIGHT_FILL
        bg = self._apply_appearance_mode_bg()
        return track, fill, bg

    def _apply_appearance_mode_bg(self) -> str:
        try:
            parent_color = self.master.cget("fg_color")
            if isinstance(parent_color, (tuple, list)):
                dark = ctk.get_appearance_mode() == "Dark"
                return parent_color[1] if dark else parent_color[0]
            return parent_color
        except Exception:
            return self.cget("bg")

    @staticmethod
    def _stadium(canvas, x0, y0, x1, y1, color) -> None:
        h = y1 - y0
        r = h / 2
        if x1 - x0 < h:
            x1 = x0 + h  # never draw thinner than the rounded caps themselves
        canvas.create_oval(x0, y0, x0 + h, y1, fill=color, outline=color)
        canvas.create_oval(x1 - h, y0, x1, y1, fill=color, outline=color)
        canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline=color)

    def _redraw(self) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 1)
        h = self._bar_height
        track, fill, bg = self._colors()
        try:
            self.configure(bg=bg)
        except Exception:
            pass
        self._stadium(self, 0, 0, w, h, track)
        fill_w = w * self._fraction
        if fill_w > 1:
            self._stadium(self, 0, 0, fill_w, h, fill)
        text = self._text_override or f"{int(round(self._fraction * 100))}%"
        cx, cy = w / 2, h / 2
        font_size = 9 if self._text_override else 11
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.create_text(cx + dx, cy + dy, text=text, fill="black",
                              font=("", font_size, "bold"))
        self.create_text(cx, cy, text=text, fill="white", font=("", font_size, "bold"))

    def set(self, fraction: float, text: Optional[str] = None) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self._text_override = text
        self._redraw()



class ConvertTab(ctk.CTkScrollableFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master)
        self.app = app
        self.file_entries: list = []  # one per added file: source, ext, variant, variant_mode
        self.selected_models: dict = {}  # ext -> set(model_key) - checkbox state, shared across files of that ext
        self.queue_rows: list = []  # one per (file, model): row_id, source, model_key, status, error, ...
        self._cleared_keys: set = set()  # (source_str, model_key) explicitly removed via Clean Queue -
                                          # suppressed from _rebuild_queue_rows until re-ticked or a new batch starts

        self._conversion_active = False
        self._cancel_requested = threading.Event()
        self._current_row_id: Optional[str] = None
        self._current_row_start: Optional[float] = None
        self._current_row_estimate: Optional[float] = None
        self._batch_done_count = 0
        self._batch_total_count = 0
        self._row_widgets: dict = {}  # row_id -> {"label": CTkLabel, "log_btn": CTkButton or None}

        self.grid_columnconfigure(0, weight=1)

        drop_label = ctk.CTkLabel(
            self, text="Add files or Drag & drop here to convert files to MD",
            height=60, fg_color=("gray85", "gray20"), corner_radius=8,
            font=ctk.CTkFont(size=14))
        drop_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        drop_label.drop_target_register(DND_FILES)
        drop_label.dnd_bind("<<Drop>>", self._on_drop)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="ew", padx=10)
        ctk.CTkButton(btn_row, text="Add file(s)...", command=self._pick_files).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Output Folder",
                     command=self._pick_output_folder).pack(side="left", padx=(0, 8))
        self.same_folder_var = ctk.BooleanVar(
            value=(self.app.settings.get("output_folder_mode", "same_as_source") == "same_as_source"))
        ctk.CTkCheckBox(btn_row, text="Same as input folder",
                        variable=self.same_folder_var,
                        command=self._toggle_same_folder).pack(side="left", padx=(0, 12))
        self.output_label = ctk.CTkLabel(btn_row, text="")
        self.output_label.pack(side="left", padx=10)
        self._refresh_output_label()

        self.file_info_panel = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self.file_info_panel.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 0))

        self.model_panel = ctk.CTkScrollableFrame(
            self, label_text="Select the Model(s) for Conversion",
            label_font=ctk.CTkFont(weight="bold"), height=150)
        self.model_panel.grid(row=3, column=0, sticky="ew", padx=10, pady=5)
        self.model_panel.grid_columnconfigure((0, 1), weight=1, uniform="modelcol")

        self.queue_panel = ctk.CTkScrollableFrame(
            self, label_text="Queue", label_font=ctk.CTkFont(weight="bold"), height=335)
        self.queue_panel.grid(row=4, column=0, sticky="ew", padx=10, pady=5)

        bottom_row = ctk.CTkFrame(self, fg_color="transparent")
        bottom_row.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 2))
        self.convert_btn = ctk.CTkButton(bottom_row, text="Convert", command=self._start_conversion,
                                          state="disabled")
        self.convert_btn.pack(side="left")
        self.cancel_btn = ctk.CTkButton(bottom_row, text="Cancel", command=self._cancel_conversion,
                                         state="disabled", fg_color="#B3401D", hover_color="#8f3117")
        self.cancel_btn.pack(side="left", padx=(6, 0))
        self.clean_queue_btn = ctk.CTkButton(bottom_row, text="Clean Queue", command=self._clean_queue)
        self.clean_queue_btn.pack(side="left", padx=(6, 0))

        progress_wrap = ctk.CTkFrame(bottom_row, fg_color="transparent")
        progress_wrap.pack(side="left", fill="x", expand=True, padx=10)
        self.progress = PercentProgressBar(progress_wrap, height=26)
        self.progress.pack(fill="x", expand=True)
        self.progress.set(0)

        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 5))
        self.elapsed_label = ctk.CTkLabel(status_row, text="Elapsed: -")
        self.elapsed_label.pack(side="left", padx=(0, 20))
        self.eta_label = ctk.CTkLabel(status_row, text="Estimated remaining: -")
        self.eta_label.pack(side="left")

        self.log_box = ctk.CTkTextbox(self, height=120)
        self.log_box.grid(row=7, column=0, sticky="ew", padx=10, pady=(0, 10))

        self._selected_model_widgets: dict = {}

    # ---- file intake ----

    def _on_drop(self, event) -> None:
        paths = self.app.parse_dnd_paths(event.data)
        self._add_files(paths)

    def _pick_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Select file(s) to convert")
        if paths:
            self._add_files(list(paths))

    def _pick_output_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.app.settings.set("output_folder_mode", "custom")
            self.app.settings.set("custom_output_folder", folder)
            self.same_folder_var.set(False)
            self._refresh_output_label()

    def _toggle_same_folder(self) -> None:
        if self.same_folder_var.get():
            self.app.settings.set("output_folder_mode", "same_as_source")
            self._refresh_output_label()
        else:
            custom = self.app.settings.get("custom_output_folder", "")
            if custom:
                self.app.settings.set("output_folder_mode", "custom")
                self._refresh_output_label()
            else:
                self._pick_output_folder()
                if self.app.settings.get("output_folder_mode") != "custom":
                    self.same_folder_var.set(True)  # user cancelled the folder picker

    def _refresh_output_label(self) -> None:
        if self.app.settings.get("output_folder_mode") == "custom":
            self.output_label.configure(text=f"Output: {self.app.settings.get('custom_output_folder', '')}")
        else:
            self.output_label.configure(text="Output: same folder as each source file")

    def _add_files(self, paths: list) -> None:
        supported_exts = set()
        for m in MODEL_REGISTRY.values():
            supported_exts.update(m.supported_extensions)
        added_any = False
        for p in paths:
            path = Path(p)
            ext = path.suffix.lower()
            if ext not in supported_exts:
                self._log(f"Skipped unsupported file type: {path.name}")
                continue
            variant = Advisor.detect_pdf_variant(path) if ext == ".pdf" else ""
            self.file_entries.append({"source": path, "ext": ext, "variant": variant, "variant_mode": "auto"})
            added_any = True
            # A fresh add (even re-adding a file removed earlier via Clean Queue)
            # is a new, deliberate request - don't let a stale suppression from
            # an earlier clear silently keep its row from appearing this time.
            self._cleared_keys = {k for k in self._cleared_keys if k[0] != str(path)}
            if ext not in self.selected_models:
                remembered = self.app.settings.get_last_used_models_multi(ext)
                ranked = Advisor.rank_models(ext, variant)
                default_key = remembered[0] if remembered else (ranked[0][0].key if ranked else None)
                self.selected_models[ext] = {default_key} if default_key else set()
        if added_any:
            self._refresh_file_info_panel()
            self._refresh_model_panel()
            self._rebuild_queue_rows()

    def _apply_variant_mode(self, ext: str, mode: str) -> None:
        for entry in self.file_entries:
            if entry["ext"] != ext:
                continue
            entry["variant_mode"] = mode
            entry["variant"] = Advisor.detect_pdf_variant(entry["source"]) if mode == "auto" else mode
        self._refresh_file_info_panel()
        self._refresh_model_panel()
        self._rebuild_queue_rows()

    # ---- model selection panel (double column, tick boxes, multi-select) ----

    def _refresh_file_info_panel(self) -> None:
        for child in self.file_info_panel.winfo_children():
            child.destroy()
        if not self.file_entries:
            return
        by_ext = {}
        for entry in self.file_entries:
            by_ext.setdefault(entry["ext"], entry)
        for ext, sample_entry in by_ext.items():
            ctk.CTkLabel(self.file_info_panel, text=f"Files ({ext}):",
                        font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(6, 0))
            if ext == ".pdf":
                variant_row = ctk.CTkFrame(self.file_info_panel, fg_color="transparent")
                variant_row.pack(anchor="w", pady=(0, 4))
                ctk.CTkLabel(variant_row, text="These PDFs are:").pack(side="left")
                mode_var = ctk.StringVar(value=sample_entry.get("variant_mode", "auto"))
                for label, mode in (("Detect automatically", "auto"), ("Text-native", "text"),
                                    ("Scanned (needs OCR)", "scanned")):
                    ctk.CTkRadioButton(
                        variant_row, text=label, variable=mode_var, value=mode,
                        command=lambda e=ext, mv=mode_var: self._apply_variant_mode(e, mv.get())
                    ).pack(side="left", padx=(6, 0))

    def _refresh_model_panel(self) -> None:
        for child in self.model_panel.winfo_children():
            child.destroy()
        if not self.file_entries:
            self.convert_btn.configure(state="disabled")
            return
        by_ext = {}
        for entry in self.file_entries:
            by_ext.setdefault(entry["ext"], entry)
        row_cursor = 0
        for ext, sample_entry in by_ext.items():
            ranked = Advisor.rank_models(ext, sample_entry["variant"])
            if not ranked:
                ctk.CTkLabel(self.model_panel, text=f"No model supports {ext} files yet.").grid(
                    row=row_cursor, column=0, columnspan=2, sticky="w", pady=(4, 4))
                row_cursor += 1
                continue
            selected = self.selected_models.setdefault(ext, set())
            for i, (model, fit, rationale) in enumerate(ranked):
                status = self._status_for(model.key)
                col = i % 2
                r = row_cursor + i // 2
                cell = ctk.CTkFrame(self.model_panel, fg_color="transparent")
                cell.grid(row=r, column=col, sticky="ew", padx=(0, 10), pady=3)
                var = ctk.BooleanVar(value=model.key in selected)
                cb = ctk.CTkCheckBox(
                    cell, text=f"{model.display_name}  [{fit.value}]  {STATUS_ICON[status]}",
                    variable=var,
                    command=lambda e=ext, k=model.key, v=var: self._toggle_model_choice(e, k, v.get()))
                cb.pack(anchor="w")
            row_cursor += (len(ranked) + 1) // 2
        self._update_convert_button_state()

    def _status_for(self, model_key: str) -> str:
        return self.app.settings.get_cached_status(model_key)

    def _toggle_model_choice(self, ext: str, model_key: str, checked: bool) -> None:
        selected = self.selected_models.setdefault(ext, set())
        if checked:
            selected.add(model_key)
            # A checkbox tick is a deliberate, fresh request for this combo -
            # let it back in even if it was removed by a previous Clean Queue.
            for entry in self.file_entries:
                if entry["ext"] == ext:
                    self._cleared_keys.discard((str(entry["source"]), model_key))
        else:
            selected.discard(model_key)
        self.app.settings.set_last_used_models_multi(ext, list(selected))
        installed = self._status_for(model_key) == InstallStatus.INSTALLED.value
        if checked and not installed:
            self._log(f"Note: '{MODEL_REGISTRY[model_key].display_name}' isn't installed. "
                       f"Go to Model Manager to install it.")
        self._rebuild_queue_rows()
        self._update_convert_button_state()

    def _update_convert_button_state(self) -> None:
        has_runnable = any(row["status"] == "queued" for row in self.queue_rows)
        self.convert_btn.configure(state="normal" if has_runnable and not self._conversion_active else "disabled")
        self.cancel_btn.configure(state="normal" if self._conversion_active else "disabled")
        self.clean_queue_btn.configure(state="disabled" if self._conversion_active else "normal")

    # ---- queue rows: one per (file, model), rebuilt on any selection change ----

    def _rebuild_queue_rows(self) -> None:
        expected_order = []
        for entry in self.file_entries:
            ranked_keys = [m.key for m, _, _ in Advisor.rank_models(entry["ext"], entry["variant"])]
            chosen = self.selected_models.get(entry["ext"], set())
            for key in ranked_keys:
                if key in chosen:
                    expected_order.append((str(entry["source"]), key))
        existing_by_key = {(row["source_str"], row["model_key"]): row for row in self.queue_rows}
        expected_set = set(expected_order)
        new_rows = []
        for key in expected_order:
            if key in existing_by_key:
                new_rows.append(existing_by_key[key])
            elif key in self._cleared_keys:
                continue  # explicitly removed via Clean Queue - stays gone until re-ticked
            else:
                src_str, model_key = key
                source = next(e["source"] for e in self.file_entries if str(e["source"]) == src_str)
                new_rows.append(self._new_row(source, model_key))
        # keep started/finished rows even if the checkbox was since unticked, so
        # history stays visible in the queue (Section 1: queue IS the history)
        for key, row in existing_by_key.items():
            if key not in expected_set and row["status"] != "queued":
                new_rows.append(row)
        self.queue_rows = new_rows
        self._refresh_queue_panel()
        self._update_convert_button_state()

    def _new_row(self, source: Path, model_key: str) -> dict:
        return {
            "row_id": uuid.uuid4().hex[:12],
            "source": source,
            "source_str": str(source),
            "model_key": model_key,
            "status": "queued",
            "error": "",
            "output_path": None,
            "elapsed_seconds": None,
        }

    def _refresh_queue_panel(self) -> None:
        for child in self.queue_panel.winfo_children():
            child.destroy()
        self._row_widgets = {}
        if not self.queue_rows:
            ctk.CTkLabel(self.queue_panel, text="No files queued yet.").pack(anchor="w", padx=4, pady=4)
            return
        for row in self.queue_rows:
            model_name = MODEL_REGISTRY[row["model_key"]].display_name
            text = f"{row['source'].name}  ->  {model_name}  [{row['status']}]"
            if row["status"] == "converting" and row.get("elapsed_seconds") is not None:
                text += f"  ({int(row['elapsed_seconds'])}s)"
            if row["error"]:
                short = row["error"].splitlines()[0][:120]
                text += f"  - {short}"
            rowf = ctk.CTkFrame(self.queue_panel, fg_color="transparent")
            rowf.pack(fill="x", anchor="w")
            label = ctk.CTkLabel(rowf, text=text, anchor="w", justify="left")
            label.pack(side="left", anchor="w", fill="x", expand=True)
            self._row_widgets[row["row_id"]] = {"label": label}
            if row["status"] in ("failed", "cancelled"):
                ctk.CTkButton(rowf, text="Retry", width=90,
                              command=lambda r=row: self._retry_row(r)).pack(side="right", padx=(4, 0))
                ctk.CTkButton(rowf, text="Export Log", width=90,
                              command=lambda r=row: self._export_row_log(r)).pack(side="right", padx=(4, 0))
            elif row["status"] == "done":
                ctk.CTkButton(rowf, text="Open", width=70,
                              command=lambda r=row: self._open_row_output(r)).pack(side="right")

    def _retry_row(self, row: dict) -> None:
        row["status"] = "queued"
        row["error"] = ""
        self._refresh_queue_panel()
        self._update_convert_button_state()

    def _export_row_log(self, row: dict) -> None:
        log_path = self.app.env.conversion_log_path(row["row_id"], row["source"].stem, row["model_key"])
        if not log_path.exists():
            messagebox.showinfo("Export Log", "No log available for this row.")
            return
        default_name = f"{row['source'].stem}_{row['model_key']}_log.txt"
        dest = filedialog.asksaveasfilename(title="Export conversion log", defaultextension=".txt",
                                             initialfile=default_name)
        if not dest:
            return
        try:
            shutil.copyfile(log_path, dest)
            messagebox.showinfo("Export Log", f"Log exported to:\n{dest}")
        except OSError as e:
            messagebox.showerror("Export Log", f"Could not export the log: {e}")

    def _open_row_output(self, row: dict) -> None:
        out_path = row.get("output_path")
        if not out_path:
            return
        target = out_path if Path(out_path).exists() else Path(out_path).parent
        try:
            os.startfile(str(target))
        except OSError:
            pass

    # ---- conversion ----

    def _start_conversion(self) -> None:
        if not any(row["status"] == "queued" for row in self.queue_rows):
            return
        self._conversion_active = True
        self._cancel_requested.clear()
        self._update_convert_button_state()
        collision_policy = {"choice": None, "apply_all": False}
        t = threading.Thread(target=self._conversion_worker, args=(collision_policy,), daemon=True)
        t.start()
        self._after(self._tick_progress)

    def _cancel_conversion(self) -> None:
        self._cancel_requested.set()
        self.cancel_btn.configure(state="disabled")  # takes a moment for the current row to unwind

    def _clean_queue(self) -> None:
        if self._conversion_active:
            return
        self._cleared_keys |= {(row["source_str"], row["model_key"]) for row in self.queue_rows}
        self.queue_rows = []
        self._batch_done_count = 0
        self._batch_total_count = 0
        self._refresh_queue_panel()
        self._set_progress(0.0)
        self._update_convert_button_state()

    def _conversion_worker(self, collision_policy: dict) -> None:
        pending = [r for r in self.queue_rows if r["status"] == "queued"]
        self._batch_total_count = len(pending)
        self._batch_done_count = 0
        self._after(lambda: self._set_progress(0.0))
        for row in pending:
            if self._cancel_requested.is_set():
                break  # leave this and any remaining rows as "queued" - nothing was started
            model_key = row["model_key"]
            source = row["source"]
            if self._status_for(model_key) != InstallStatus.INSTALLED.value:
                row["status"] = "failed"
                row["error"] = "Model not installed."
                self._after(self._refresh_queue_panel)
                self._batch_done_count += 1
                continue
            row["status"] = "converting"
            self._after(self._refresh_queue_panel)

            size_mb = 0.0
            try:
                size_mb = source.stat().st_size / (1024 * 1024)
            except OSError:
                pass
            rate = self.app.settings.get_speed_estimate_seconds_per_mb(model_key)
            self._current_row_id = row["row_id"]
            self._current_row_start = time.time()
            self._current_row_estimate = (rate * size_mb) if rate else None

            try:
                out_dir = self.app.settings.output_folder_for(source)
                model_display = MODEL_REGISTRY[model_key].display_name
                md_path = out_dir / f"{source.stem} ({model_display}).md"
                _, assets_dir = output_paths_for(source, out_dir)
                md_path = self._resolve_collision(md_path, collision_policy)
                if md_path is None:
                    row["status"] = "skipped"
                    self._after(self._refresh_queue_panel)
                    self._batch_done_count += 1
                    continue
                inactivity_timeout_s = self.app.settings.get_effective_timeout(model_key)
                max_runtime_s = self.app.settings.get_effective_max_runtime(model_key)
                log_path = self.app.env.conversion_log_path(row["row_id"], row["source"].stem, row["model_key"])

                def on_output(text, r=row):
                    r["_last_output"] = text
                    self._after(self._refresh_active_row_label)

                convert_file(model_key, self.app.env, source, md_path,
                             inactivity_timeout_s, max_runtime_s, self._cancel_requested.is_set,
                             log_path=log_path, on_output=on_output)
                if model_key in ASSET_PRODUCING_MODELS:
                    assets_dir.mkdir(parents=True, exist_ok=True)
                row["status"] = "done"
                row["output_path"] = str(md_path)
                elapsed = time.time() - self._current_row_start
                row["elapsed_seconds"] = elapsed
                if size_mb > 0:
                    self.app.settings.record_speed_sample(model_key, elapsed, size_mb)
                if self.app.settings.get("auto_open_after_conversion"):
                    try:
                        os.startfile(str(md_path))
                    except OSError:
                        pass
            except ConversionError as e:
                elapsed = time.time() - self._current_row_start
                row["status"] = "cancelled" if "Cancelled by user" in str(e) else "failed"
                row["error"] = str(e)[:2000]
                # Data is data: even a run that didn't finish tells us the model was
                # AT LEAST this slow for this file size, which beats having zero
                # estimate at all for the next attempt's progress bar/ETA.
                if size_mb > 0 and elapsed > 5:
                    self.app.settings.record_speed_sample(model_key, elapsed, size_mb)
            except Exception as e:
                elapsed = time.time() - self._current_row_start
                row["status"] = "failed"
                row["error"] = f"Unexpected error: {e}"[:2000]
                if size_mb > 0 and elapsed > 5:
                    self.app.settings.record_speed_sample(model_key, elapsed, size_mb)
            self._batch_done_count += 1
            self._current_row_id = None
            self._current_row_start = None
            self._current_row_estimate = None
            self._after(self._refresh_queue_panel)
        self._conversion_active = False
        self._cancel_requested.clear()
        self._after(self._on_conversion_finished)

    def _on_conversion_finished(self) -> None:
        self._set_progress(1.0 if self._batch_total_count else 0.0)
        self.elapsed_label.configure(text="Elapsed: -")
        self.eta_label.configure(text="Estimated remaining: -")
        self._update_convert_button_state()

    def _tick_progress(self) -> None:
        if not self._conversion_active:
            return
        done = self._batch_done_count
        total = max(self._batch_total_count, 1)
        row_fraction = 0.0
        learning = False
        if self._current_row_start is not None:
            row_elapsed = time.time() - self._current_row_start
            if self._current_row_estimate and self._current_row_estimate > 0:
                row_fraction = min(row_elapsed / self._current_row_estimate, 0.97)
            else:
                learning = True
            self.elapsed_label.configure(text=f"Elapsed (current file): {self._format_secs(row_elapsed)}")
            if self._current_row_estimate:
                remaining = max(self._current_row_estimate - row_elapsed, 0)
                self.eta_label.configure(text=f"Estimated remaining: ~{self._format_secs(remaining)}")
            else:
                self.eta_label.configure(text="Estimated remaining: estimating... (first run for this model)")
        overall = (done + row_fraction) / total
        if learning:
            self._set_progress(overall, text="First run - learning the model speed...")
        else:
            self._set_progress(overall)
        self.after(400, self._tick_progress)

    def _refresh_active_row_label(self) -> None:
        if self._current_row_id is None:
            return
        row = next((r for r in self.queue_rows if r["row_id"] == self._current_row_id), None)
        widgets = self._row_widgets.get(self._current_row_id)
        if not row or not widgets:
            return
        model_name = MODEL_REGISTRY[row["model_key"]].display_name
        elapsed = int(time.time() - self._current_row_start) if self._current_row_start else 0
        last = row.get("_last_output", "")
        text = f"{row['source'].name}  ->  {model_name}  [converting, {elapsed}s]"
        if last:
            text += f"  - {last[:100]}"
        widgets["label"].configure(text=text)

    @staticmethod
    def _format_secs(seconds: float) -> str:
        seconds = max(int(seconds), 0)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    def _set_progress(self, fraction: float, text: Optional[str] = None) -> None:
        self.progress.set(fraction, text=text)

    def _resolve_collision(self, md_path: Path, policy: dict) -> Optional[Path]:
        if not md_path.exists():
            return md_path
        if policy["apply_all"] and policy["choice"]:
            return self._apply_collision_choice(md_path, policy["choice"])
        choice_holder = {"value": None, "apply_all": False}
        event = threading.Event()

        def ask():
            choice_holder["value"], choice_holder["apply_all"] = self.app.ask_collision_choice(md_path)
            event.set()

        self._after(ask)
        event.wait()
        if choice_holder["apply_all"]:
            policy["choice"] = choice_holder["value"]
            policy["apply_all"] = True
        return self._apply_collision_choice(md_path, choice_holder["value"])

    def _apply_collision_choice(self, md_path: Path, choice: str) -> Optional[Path]:
        if choice == "overwrite":
            return md_path
        if choice == "skip":
            return None
        if choice == "rename":
            i = 1
            candidate = md_path
            while candidate.exists():
                candidate = md_path.with_name(f"{md_path.stem}_{i}{md_path.suffix}")
                i += 1
            return candidate
        return md_path

    def _log(self, message: str) -> None:
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    def _after(self, fn) -> None:
        self.after(0, fn)

    def preselect_model(self, ext: str, model_key: str) -> None:
        self.selected_models[ext] = {model_key}
        self.app.settings.set_last_used_models_multi(ext, [model_key])
        self._refresh_file_info_panel()
        self._refresh_model_panel()
        self._rebuild_queue_rows()

    def refresh_all_model_statuses(self) -> None:
        self._refresh_model_panel()
        self._refresh_file_info_panel()

# ===== GUI: ADVISOR TAB =====

class AdvisorTab(ctk.CTkFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master)
        self.app = app
        self._sample_path: Optional[Path] = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(top, text="Pick a file...", command=self._pick_file).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(top, text="or choose a file type:").pack(side="left", padx=(10, 4))
        self.ext_var = ctk.StringVar(value=".pdf")
        exts = sorted({e for m in MODEL_REGISTRY.values() for e in m.supported_extensions})
        self.ext_menu = ctk.CTkOptionMenu(top, values=exts, variable=self.ext_var,
                                           command=lambda _=None: self._on_ext_changed())
        self.ext_menu.pack(side="left")

        # Manual "scanned or text-native / detect for me" override (Section 3) - shown only
        # for .pdf, and essential when browsing by file type with no file selected, since
        # there's nothing to auto-detect from in that case.
        self.variant_row = ctk.CTkFrame(self, fg_color="transparent")
        self.variant_mode_var = ctk.StringVar(value="auto")
        ctk.CTkLabel(self.variant_row, text="This PDF is:").pack(side="left")
        for label, mode in (("Detect automatically", "auto"), ("Text-native", "text"),
                            ("Scanned (needs OCR)", "scanned")):
            ctk.CTkRadioButton(self.variant_row, text=label, variable=self.variant_mode_var, value=mode,
                              command=lambda: self._refresh()).pack(side="left", padx=(6, 0))
        self.variant_row.grid(row=1, column=0, sticky="w", padx=10)

        self.file_label = ctk.CTkLabel(self, text="No file selected - showing results by file type.")
        self.file_label.grid(row=2, column=0, sticky="w", padx=10)

        self.results_panel = ctk.CTkScrollableFrame(self)
        self.results_panel.grid(row=3, column=0, sticky="nsew", padx=10, pady=10)

        self._refresh()

    def _on_ext_changed(self) -> None:
        self._sample_path = None  # switching file type manually clears any previously picked file
        self.file_label.configure(text="No file selected - showing results by file type.")
        self._refresh()

    def _pick_file(self) -> None:
        path = filedialog.askopenfilename(title="Select a file")
        if path:
            p = Path(path)
            self.file_label.configure(text=f"Selected: {p.name}")
            self.ext_var.set(p.suffix.lower())
            self._sample_path = p
            self.variant_mode_var.set("auto")
            self._refresh()

    def _refresh(self, sample_path: Optional[Path] = None) -> None:
        if sample_path is not None:
            self._sample_path = sample_path
        for child in self.results_panel.winfo_children():
            child.destroy()
        ext = self.ext_var.get()
        if ext == ".pdf":
            self.variant_row.grid()
        else:
            self.variant_row.grid_remove()
        variant = ""
        if ext == ".pdf":
            mode = self.variant_mode_var.get()
            if mode == "auto":
                variant = Advisor.detect_pdf_variant(self._sample_path) if self._sample_path else ""
            else:
                variant = mode
        ranked = Advisor.rank_models(ext, variant)
        if not ranked:
            ctk.CTkLabel(self.results_panel, text="No models support this file type.").pack(anchor="w")
            return
        for model, fit, rationale in ranked:
            status = self.app.settings.get_cached_status(model.key)
            row = ctk.CTkFrame(self.results_panel, fg_color=("gray90", "gray17"), corner_radius=6)
            row.pack(fill="x", pady=4, padx=4)
            header = f"{model.display_name} - {fit.value}  ({STATUS_ICON[status]})"
            ctk.CTkLabel(row, text=header, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(6, 0))
            ctk.CTkLabel(row, text=rationale, wraplength=700, justify="left").pack(anchor="w", padx=8)
            if model.license_flag:
                ctk.CTkLabel(row, text=f"\u26a0\ufe0f License: {model.license}", text_color="orange").pack(
                    anchor="w", padx=8)
            else:
                ctk.CTkLabel(row, text=f"License: {model.license}").pack(anchor="w", padx=8)
            ctk.CTkButton(row, text="Use this model", width=140,
                          command=lambda m=model, e=ext: self._use_model(m, e)).pack(anchor="e", padx=8, pady=6)

    def _use_model(self, model: ModelDef, ext: str) -> None:
        status = self.app.settings.get_cached_status(model.key)
        if status != InstallStatus.INSTALLED.value:
            self.app.goto_model_manager(highlight=model.key)
            return
        self.app.goto_convert_with_model(ext, model.key)


# ===== GUI: PYTHON RUNTIME INSTALL WINDOW =====

class PythonInstallWindow(ctk.CTkToplevel):
    """A dedicated progress window for the Python 3.12 auto-install, so the
    user sees clear, full-size progress instead of a cramped inline log."""

    def __init__(self, app: "App", on_close: Optional[Callable[[], None]] = None):
        super().__init__(app)
        self.title("Installing Python 3.12")
        self.geometry("560x430")
        self.resizable(False, False)
        self._on_close_callback = on_close
        self._app = app
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # block closing until done

        ctk.CTkLabel(self, text=f"Installing Python {PYTHON_RUNTIME_VERSION}...",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(18, 4))
        ctk.CTkLabel(self, text="A private copy for this app's Heavy models only - it won't "
                                 "affect any other Python on your system, doesn't need admin "
                                 "rights, and won't become your system default.",
                     wraplength=500, justify="center", text_color="gray").pack(pady=(0, 8), padx=20)

        self.result_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.result_label.pack(pady=(0, 8))

        self.log_box = ctk.CTkTextbox(self, height=220)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 18))
        ctk.CTkButton(btn_row, text="Export Log (txt)", width=140,
                      command=self._export_log).pack(side="left", padx=(0, 10))
        self.cancel_btn = ctk.CTkButton(btn_row, text="Cancel", width=100,
                                         fg_color="#8b2020", hover_color="#6e1919",
                                         command=self._cancel)
        self.cancel_btn.pack(side="left", padx=(0, 10))
        self.close_btn = ctk.CTkButton(btn_row, text="Please wait...", state="disabled",
                                        width=140, command=self._close)
        self.close_btn.pack(side="left")

        self.grab_set()

    def _cancel(self) -> None:
        self._app.installer.cancel_install(Installer.PYTHON_RUNTIME_KEY)
        self.cancel_btn.configure(state="disabled", text="Cancelling...")

    def _export_log(self) -> None:
        log_path = self._app.env.model_install_log_path(Installer.PYTHON_RUNTIME_KEY)
        if not log_path.exists():
            messagebox.showinfo("Export Log", "No log available yet.")
            return
        dest = filedialog.asksaveasfilename(
            title="Export Python runtime install log",
            defaultextension=".txt",
            initialfile="python_runtime_install_log.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not dest:
            return
        try:
            shutil.copyfile(str(log_path), dest)
            messagebox.showinfo("Export Log", f"Log exported to:\n{dest}")
        except OSError as e:
            messagebox.showerror("Export Log", f"Could not export the log: {e}")

    def append_log(self, message: str) -> None:
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")

    def mark_done(self, success: bool) -> None:
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.cancel_btn.configure(state="disabled")
        self.close_btn.configure(state="normal", text="Done" if success else "Close")
        if success:
            self.result_label.configure(text="\u2714 Python 3.12 installed successfully.",
                                         text_color="#2e7d32")
        else:
            self.result_label.configure(
                text="\u2716 Installation failed - see the log below (or Export Log) for details.",
                text_color="#c62828")

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        callback = self._on_close_callback
        self.destroy()
        if callback:
            callback()


# ===== GUI: BATCH INSTALL WINDOW =====

class BatchInstallWindow(ctk.CTkToplevel):
    """Progress window for 'Install all recommended (Primary) models'. Updates
    itself live as each model finishes - the user never has to click 'Ok' to
    let the next install proceed. Shows the CURRENT model's real-time output
    (previously this window only got an entry once a model's ENTIRE install
    finished, so it sat blank - sometimes for many minutes - during every
    single install, indistinguishable from being stuck), plus a running
    checkmark history of what's completed so far in the batch."""

    def __init__(self, app: "App", model_names: list, on_close: Optional[Callable[[], None]] = None):
        super().__init__(app)
        self.app = app
        self.title("Installing recommended models")
        self.geometry("580x560")
        self.resizable(False, False)
        self._on_close_callback = on_close
        self._current_model_key: Optional[str] = None
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # block closing until done

        self.progress_label = ctk.CTkLabel(
            self, text=f"Preparing to install {len(model_names)} model(s)...",
            font=ctk.CTkFont(size=15, weight="bold"))
        self.progress_label.pack(pady=(18, 8), padx=20)

        ctk.CTkLabel(self, text="Current activity (live):", anchor="w").pack(fill="x", padx=20)
        self.live_log_box = ctk.CTkTextbox(self, height=220)
        self.live_log_box.pack(fill="both", expand=True, padx=20, pady=(2, 10))

        ctk.CTkLabel(self, text="Completed so far:", anchor="w").pack(fill="x", padx=20)
        self.history_box = ctk.CTkTextbox(self, height=90)
        self.history_box.pack(fill="x", padx=20, pady=(2, 12))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 18))
        ctk.CTkButton(btn_row, text="Export Current Log (txt)", width=180,
                      command=self._export_log).pack(side="left", padx=(0, 10))
        self.cancel_btn = ctk.CTkButton(btn_row, text="Cancel", width=100,
                                         fg_color="#8b2020", hover_color="#6e1919",
                                         command=self._cancel_current)
        self.cancel_btn.pack(side="left", padx=(0, 10))
        self.close_btn = ctk.CTkButton(btn_row, text="Please wait...", state="disabled",
                                        width=140, command=self._close)
        self.close_btn.pack(side="left")

        self.grab_set()

    def set_progress(self, idx: int, total: int, name: str, model_key: Optional[str] = None) -> None:
        self.progress_label.configure(text=f"Installing {idx} of {total}: {name}...")
        self._current_model_key = model_key
        self.live_log_box.delete("1.0", "end")  # fresh view for this model, not a growing wall of text
        self.cancel_btn.configure(state="normal", text="Cancel")

    def append_live_log(self, message: str) -> None:
        self.live_log_box.insert("end", message + "\n")
        self.live_log_box.see("end")

    def add_result(self, name: str, success: bool) -> None:
        icon = "\u2714" if success else "\u2716"
        self.history_box.insert("end", f"{icon} {name}\n")
        self.history_box.see("end")

    def mark_done(self) -> None:
        self.progress_label.configure(text="Done.")
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.cancel_btn.configure(state="disabled")
        self.close_btn.configure(state="normal", text="Close")

    def _cancel_current(self) -> None:
        if self._current_model_key:
            self.app.installer.cancel_install(self._current_model_key)
            self.cancel_btn.configure(state="disabled", text="Cancelling...")

    def _export_log(self) -> None:
        if not self._current_model_key:
            messagebox.showinfo("Export Log", "No model is currently installing yet.")
            return
        log_path = self.app.env.model_install_log_path(self._current_model_key)
        if not log_path.exists():
            messagebox.showinfo("Export Log", "No log available yet.")
            return
        dest = filedialog.asksaveasfilename(
            title="Export install log", defaultextension=".txt",
            initialfile=f"{self._current_model_key}_install_log.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not dest:
            return
        try:
            shutil.copyfile(str(log_path), dest)
            messagebox.showinfo("Export Log", f"Log exported to:\n{dest}")
        except OSError as e:
            messagebox.showerror("Export Log", f"Could not export the log: {e}")

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        callback = self._on_close_callback
        self.destroy()
        if callback:
            callback()


# ===== GUI: MODEL MANAGER TAB =====

class ModelManagerTab(ctk.CTkFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master)
        self.app = app
        self.python_install_window: Optional[PythonInstallWindow] = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(top, text="Install all recommended (Primary) models",
                      command=self._install_all_primary).pack(side="left")
        # Persistent, always-visible status of the private Python 3.12 runtime -
        # separate from the compat banner below (which only shows when something
        # is actually wrong), so the user can always tell at a glance whether it's
        # present, regardless of whether a system Python also happens to satisfy
        # Heavy-model compatibility right now.
        self.python_status_label = ctk.CTkLabel(top, text="Private Python runtime: checking...")
        self.python_status_label.pack(side="left", padx=(16, 0))

        # Compatibility banner: only shown when no Python 3.10-3.13 is available
        # for Heavy model venvs. Offers to auto-download and install a private
        # Python 3.12 into the Base Folder - no admin rights, no system changes.
        self.compat_banner = ctk.CTkFrame(self, fg_color=("#fff3cd", "#4d3b00"), corner_radius=8)
        self.compat_banner_label = ctk.CTkLabel(
            self.compat_banner, text="Checking Python compatibility for Heavy models...",
            wraplength=650, justify="left")
        self.compat_banner_label.pack(side="left", padx=10, pady=8, fill="x", expand=True)
        self.compat_banner_btn = ctk.CTkButton(
            self.compat_banner, text="Install Python 3.12 automatically",
            command=self._install_python_runtime, width=210)
        self.compat_banner_btn.pack(side="right", padx=10, pady=8)
        self.compat_banner.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self.compat_banner.grid_remove()  # hidden until we know it's needed

        self.list_panel = ctk.CTkScrollableFrame(self)
        self.list_panel.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.rows: dict = {}
        self._build_rows()
        self._refresh_python_runtime_status()
        threading.Thread(target=self._check_compat_async, daemon=True).start()

    def _refresh_python_runtime_status(self) -> None:
        exe = self.app.env.python_runtime_exe()
        if not exe.exists():
            self.python_status_label.configure(
                text="Private Python runtime: \u2716 Not installed", text_color="#c0392b")
            return
        self.python_status_label.configure(
            text="Private Python runtime: checking version...", text_color="gray")
        threading.Thread(target=self._check_python_runtime_version_async, args=(exe,),
                          daemon=True).start()

    def _check_python_runtime_version_async(self, exe: Path) -> None:
        version = self.app.installer._interpreter_version(str(exe))
        self.after(0, lambda: self._set_python_runtime_status(version))

    def _set_python_runtime_status(self, version: Optional[tuple]) -> None:
        if version:
            self.python_status_label.configure(
                text=f"Private Python runtime: \u2714 Installed (Python {version[0]}.{version[1]})",
                text_color="#2e9e44")
        else:
            self.python_status_label.configure(
                text="Private Python runtime: \u26a0\ufe0f Present but couldn't verify version",
                text_color="orange")

    def _check_compat_async(self) -> None:
        compat = self.app.installer.check_heavy_interpreter_compatibility()
        self.after(0, lambda: self._update_compat_banner(compat))

    def _update_compat_banner(self, compat: dict) -> None:
        if compat.get("compatible") is False:
            v = compat["version"]
            self.compat_banner_label.configure(
                text=f"\u26a0\ufe0f Heavy models (Docling, marker, MinerU, PaddleOCR, Surya, "
                     f"Unstructured) need Python 3.10-3.13. Only Python {v[0]}.{v[1]} was found.")
            self.compat_banner.grid()
        else:
            self.compat_banner.grid_remove()

    def _install_python_runtime(self) -> None:
        fresh_compat = self.app.installer.check_heavy_interpreter_compatibility()
        if fresh_compat.get("compatible"):
            v = fresh_compat["version"]
            if not messagebox.askyesno(
                    "Python already found",
                    f"A compatible Python {v[0]}.{v[1]} was just found at:\n\n"
                    f"{fresh_compat['python_cmd']}\n\n"
                    "Heavy model installs will use it automatically - a separate private "
                    "copy isn't needed.\n\nInstall one anyway?"):
                self._refresh_python_runtime_status()
                self._update_compat_banner(fresh_compat)
                return
        target_dir = self.app.env.python_runtime_dir()
        if not messagebox.askyesno(
                "Install Python 3.12",
                f"This downloads the official Python 3.12 installer from python.org (~25 MB) "
                f"and installs it into:\n\n{target_dir}\n\n"
                "This is a private copy used only by this app for Heavy models - it won't affect "
                "any other Python on your system, doesn't need admin rights, and won't become your "
                "system default.\n\nContinue?"):
            return
        self.compat_banner_btn.configure(state="disabled", text="Installing...")
        self.python_install_window = PythonInstallWindow(
            self.app, on_close=self._on_python_install_window_closed)
        self.app.installer.install_python_runtime_async()
        self.app.watch_install_completion(Installer.PYTHON_RUNTIME_KEY, self._on_python_runtime_done)

    def _on_python_runtime_done(self) -> None:
        success = self.app.env.python_runtime_exe().exists()
        if self.python_install_window is not None:
            self.python_install_window.mark_done(success)
        self.compat_banner_btn.configure(state="normal", text="Install Python 3.12 automatically")
        self._refresh_python_runtime_status()
        threading.Thread(target=self._check_compat_async, daemon=True).start()

    def _on_python_install_window_closed(self) -> None:
        self.python_install_window = None

    def _build_rows(self) -> None:
        for child in self.list_panel.winfo_children():
            child.destroy()
        self.rows = {}
        for key, model in MODEL_REGISTRY.items():
            self.rows[key] = self._build_row(model)

    def _build_row(self, model: ModelDef) -> dict:
        frame = ctk.CTkFrame(self.list_panel, corner_radius=8, fg_color=("gray90", "gray17"))
        frame.pack(fill="x", pady=4, padx=4)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(6, 0))
        status_val = self.app.settings.get_cached_status(model.key)
        glyph, status_text, color = STATUS_DISPLAY[status_val]
        status_label = ctk.CTkLabel(header, text=f"{glyph} {status_text}",
                                     font=ctk.CTkFont(weight="bold"), text_color=color)
        status_label.pack(side="left", padx=(0, 8))
        title = f"{model.display_name}  -  ~{model.install_size_gb} GB  -  {model.license}"
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(weight="bold")).pack(side="left")
        if model.license_flag:
            ctk.CTkLabel(header, text=" \u26a0\ufe0f", text_color="orange").pack(side="left")

        ext_line = ", ".join(model.supported_extensions)
        ctk.CTkLabel(frame, text=f"Supports: {ext_line}").pack(anchor="w", padx=8)
        if model.notes:
            ctk.CTkLabel(frame, text=model.notes, wraplength=700, justify="left",
                         text_color="gray").pack(anchor="w", padx=8)

        location_text = self._location_text(model)
        loc_label = ctk.CTkLabel(frame, text=location_text, text_color="gray")
        loc_label.pack(anchor="w", padx=8)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=(4, 8))
        install_btn = ctk.CTkButton(btn_row, text="Install", width=90,
                                     command=lambda m=model: self._confirm_and_install(m))
        install_btn.pack(side="left", padx=(0, 6))
        cancel_btn = ctk.CTkButton(btn_row, text="Cancel", width=90, state="disabled",
                                    command=lambda m=model: self.app.installer.cancel_install(m.key))
        cancel_btn.pack(side="left", padx=(0, 6))
        verify_btn = ctk.CTkButton(btn_row, text="Verify", width=90,
                                    command=lambda m=model: self._verify(m))
        verify_btn.pack(side="left", padx=(0, 6))
        repair_btn = ctk.CTkButton(btn_row, text="Repair/Reinstall", width=130,
                                    command=lambda m=model: self._repair(m))
        repair_btn.pack(side="left", padx=(0, 6))
        uninstall_btn = ctk.CTkButton(btn_row, text="Uninstall", width=90,
                                       command=lambda m=model: self._confirm_uninstall(m))
        uninstall_btn.pack(side="left", padx=(0, 6))
        export_log_btn = ctk.CTkButton(btn_row, text="Export Log (txt)", width=130,
                                        command=lambda m=model: self._export_log(m))
        export_log_btn.pack(side="left")

        log_box = ctk.CTkTextbox(frame, height=90)
        log_box.pack(fill="x", padx=8, pady=(0, 8))

        self._set_button_states(status_val, install_btn, cancel_btn, verify_btn, repair_btn)

        return {
            "frame": frame, "status_label": status_label, "log_box": log_box,
            "install_btn": install_btn, "cancel_btn": cancel_btn,
            "verify_btn": verify_btn, "repair_btn": repair_btn,
        }

    def _export_log(self, model: ModelDef) -> None:
        log_path = self.app.env.model_install_log_path(model.key)
        if not log_path.exists():
            messagebox.showinfo(
                "Export Log",
                f"No log available yet for {model.display_name}. Install, Verify, or "
                f"Repair it at least once first.")
            return
        dest = filedialog.asksaveasfilename(
            title=f"Export {model.display_name} log",
            defaultextension=".txt",
            initialfile=f"{model.key}_install_log.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not dest:
            return
        try:
            shutil.copyfile(str(log_path), dest)
            messagebox.showinfo("Export Log", f"Log exported to:\n{dest}")
        except OSError as e:
            messagebox.showerror("Export Log", f"Could not export the log: {e}")

    def _location_text(self, model: ModelDef) -> str:
        env = self.app.env
        if model.weight == Weight.HEAVY:
            return f"Location: {env.model_env_dir(model.key)}"
        if model.special_case == "tesseract_binary":
            return f"Location: {env.tesseract_exe().parent}"
        if model.special_case == "pandoc_binary":
            return f"Location: {env.pandoc_exe().parent}"
        return "Location: main app environment"

    def _set_button_states(self, status: str, install_btn, cancel_btn, verify_btn, repair_btn) -> None:
        installing = status == InstallStatus.INSTALLING.value
        install_btn.configure(state="disabled" if installing else "normal")
        cancel_btn.configure(state="normal" if installing else "disabled")
        verify_btn.configure(state="disabled" if installing else "normal")
        repair_btn.configure(state="disabled" if installing else "normal")

    def _confirm_and_install(self, model: ModelDef) -> None:
        required, available, ok = self.app.installer.check_disk_space(model.key)
        dest = self._location_text(model).replace("Location: ", "")
        msg = (f"Install {model.display_name}?\n\n"
               f"Approx. download size: {model.install_size_gb} GB\n"
               f"Destination: {dest}\n"
               f"License: {model.license}" + (" (\u26a0\ufe0f see notes)" if model.license_flag else ""))
        if not ok:
            msg += f"\n\nWarning: only {available:.1f} GB free, needs ~{required} GB."
        if model.weight == Weight.HEAVY:
            compat = self.app.installer.check_heavy_interpreter_compatibility()
            if compat["compatible"] is False:
                v = compat["version"]
                msg += (f"\n\n\u26a0\ufe0f This will build using Python {v[0]}.{v[1]}, which currently "
                        f"lacks ready-made packages for this model's dependencies and will likely "
                        f"fail. Installing Python 3.12 from python.org (no need to make it your "
                        f"default) fixes this automatically - install anyway?")
        if not messagebox.askyesno("Confirm install", msg):
            return
        self._install(model)

    def _install(self, model: ModelDef) -> None:
        row = self.rows[model.key]
        row["log_box"].delete("1.0", "end")
        self._set_button_states(InstallStatus.INSTALLING.value, row["install_btn"], row["cancel_btn"],
                                 row["verify_btn"], row["repair_btn"])
        row["status_label"].configure(
            text=f"{STATUS_DISPLAY[InstallStatus.INSTALLING.value][0]} {STATUS_DISPLAY[InstallStatus.INSTALLING.value][1]}",
            text_color=STATUS_DISPLAY[InstallStatus.INSTALLING.value][2])
        self.app.installer.install_model_async(model.key)

    def _verify(self, model: ModelDef) -> None:
        row = self.rows[model.key]
        row["log_box"].insert("end", "Verifying...\n")
        self.app.installer.verify_model_async(model.key)

    def _repair(self, model: ModelDef) -> None:
        if not messagebox.askyesno("Repair/Reinstall",
                                    f"This removes and recreates {model.display_name}'s environment. Continue?"):
            return
        row = self.rows[model.key]
        row["log_box"].delete("1.0", "end")
        self._set_button_states(InstallStatus.INSTALLING.value, row["install_btn"], row["cancel_btn"],
                                 row["verify_btn"], row["repair_btn"])
        self.app.installer.repair_model_async(model.key)

    def _confirm_uninstall(self, model: ModelDef) -> None:
        if messagebox.askyesno("Uninstall", f"Remove {model.display_name} and its files? This cannot be undone."):
            self.app.installer.uninstall_model(model.key)
            self.refresh_status(model.key, InstallStatus.NOT_INSTALLED.value)

    def _install_all_primary(self) -> None:
        to_install = [MODEL_REGISTRY[k] for k in PRIMARY_MODELS
                      if self.app.settings.get_cached_status(k) != InstallStatus.INSTALLED.value]
        if not to_install:
            messagebox.showinfo("Install all recommended", "All Primary models are already installed.")
            return
        total_size = sum(m.install_size_gb for m in to_install)
        names = "\n".join(f"- {m.display_name} (~{m.install_size_gb} GB)" for m in to_install)
        dest = self.app.env.base_folder
        msg = (f"This will install {len(to_install)} model(s), one at a time:\n\n{names}\n\n"
               f"Combined download size: ~{total_size:.1f} GB\nDestination: {dest}")
        if any(m.weight == Weight.HEAVY for m in to_install):
            compat = self.app.installer.check_heavy_interpreter_compatibility()
            if compat["compatible"] is False:
                v = compat["version"]
                msg += (f"\n\n\u26a0\ufe0f Heavy model(s) in this list will build using Python "
                        f"{v[0]}.{v[1]}, which currently lacks ready-made packages for their "
                        f"dependencies and will likely fail. Installing Python 3.12 from python.org "
                        f"(no need to make it your default) fixes this automatically.")
        msg += "\n\nContinue?"
        if not messagebox.askyesno("Confirm: install all recommended", msg):
            return
        self._queue = list(to_install)
        self._queue_total = len(to_install)
        self._queue_index = 0
        self._batch_window = BatchInstallWindow(
            self.app, [m.display_name for m in to_install],
            on_close=self._on_batch_window_closed)
        self._install_next_in_queue()

    def _on_batch_window_closed(self) -> None:
        self._batch_window = None

    def _install_next_in_queue(self) -> None:
        if not getattr(self, "_queue", None):
            if getattr(self, "_batch_window", None):
                self._batch_window.mark_done()
            return
        model = self._queue.pop(0)
        self._queue_index += 1
        if getattr(self, "_batch_window", None):
            self._batch_window.set_progress(self._queue_index, self._queue_total,
                                             model.display_name, model.key)
        self._install(model)
        self.app.watch_install_completion(model.key, lambda m=model: self._on_queue_item_done(m))

    def _on_queue_item_done(self, model: ModelDef) -> None:
        status = self.app.settings.get_cached_status(model.key)
        success = status == InstallStatus.INSTALLED.value
        if getattr(self, "_batch_window", None):
            self._batch_window.add_result(model.display_name, success)
        self._install_next_in_queue()

    def refresh_status(self, model_key: str, status: str) -> None:
        row = self.rows.get(model_key)
        if not row:
            return
        glyph, status_text, color = STATUS_DISPLAY[status]
        row["status_label"].configure(text=f"{glyph} {status_text}", text_color=color)
        self._set_button_states(status, row["install_btn"], row["cancel_btn"],
                                 row["verify_btn"], row["repair_btn"])

    def append_log(self, model_key: str, message: str) -> None:
        if model_key == Installer.PYTHON_RUNTIME_KEY:
            if self.python_install_window is not None:
                self.python_install_window.append_log(message)
            return
        row = self.rows.get(model_key)
        if row:
            row["log_box"].insert("end", message + "\n")
            row["log_box"].see("end")
        # Also forward to the batch-install window's live view (if a batch is
        # running and this line belongs to the model it's currently showing) -
        # the row's own log_box above is hidden behind that modal window, so
        # without this forward the batch window would show nothing at all
        # for however long each model takes to install.
        batch_window = getattr(self, "_batch_window", None)
        if batch_window is not None and batch_window._current_model_key == model_key:
            batch_window.append_live_log(message)


# ===== GUI: ABOUT TAB =====

class AboutTab(ctk.CTkFrame):
    def __init__(self, master, app: "App"):
        super().__init__(master)
        self.app = app
        ctk.CTkLabel(self, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(20, 4))
        ctk.CTkLabel(self, text=f"Version {APP_VERSION}").pack()
        ctk.CTkLabel(self, text=f"By {APP_AUTHOR}").pack()
        ctk.CTkLabel(self, text=APP_CONTACT).pack(pady=(0, 12))
        ctk.CTkLabel(
            self,
            text="Converts PDF, HTML, DOCX/PPTX/XLSX, EPUB, and SRT/VTT files to Markdown\n"
                 "using a choice of locally-run open-source conversion engines.\n"
                 "No cloud APIs, no telemetry - nothing phones home.",
            justify="center",
        ).pack(pady=(0, 16))

        models_panel = ctk.CTkScrollableFrame(self, label_text="Open-source models used")
        models_panel.pack(fill="both", expand=True, padx=20, pady=10)
        for model in MODEL_REGISTRY.values():
            flag = " \u26a0\ufe0f" if model.license_flag else ""
            ctk.CTkLabel(models_panel, text=f"{model.display_name} - {model.license}{flag}").pack(anchor="w")


# ===== GUI: SETTINGS WINDOW =====

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, app: "App"):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("580x700")
        settings = app.settings

        # A single outer scrollbar for the WHOLE dialog - every section below
        # is packed into this one frame, so nothing (including Save/Reset)
        # can ever end up below the fold with no way to reach it.
        outer = ctk.CTkScrollableFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True)

        ctk.CTkLabel(outer, text="Output folder", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(16, 0))
        self.output_mode = ctk.StringVar(value=settings.get("output_folder_mode", "same_as_source"))
        ctk.CTkRadioButton(outer, text="Same folder as source file", variable=self.output_mode,
                           value="same_as_source").pack(anchor="w", padx=24)
        custom_row = ctk.CTkFrame(outer, fg_color="transparent")
        custom_row.pack(anchor="w", padx=24, fill="x")
        ctk.CTkRadioButton(custom_row, text="Custom folder:", variable=self.output_mode,
                           value="custom").pack(side="left")
        self.custom_folder_var = ctk.StringVar(value=settings.get("custom_output_folder", ""))
        ctk.CTkEntry(custom_row, textvariable=self.custom_folder_var, width=220).pack(side="left", padx=6)
        ctk.CTkButton(custom_row, text="Browse", width=70,
                     command=self._browse_output).pack(side="left")

        ctk.CTkLabel(outer, text="Appearance mode", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(16, 0))
        self.appearance_var = ctk.StringVar(value=settings.get("appearance_mode", "System"))
        ctk.CTkOptionMenu(outer, values=["Light", "Dark", "System"],
                         variable=self.appearance_var).pack(anchor="w", padx=24)

        self.auto_open_var = ctk.BooleanVar(value=settings.get("auto_open_after_conversion", False))
        ctk.CTkCheckBox(outer, text="Open output file automatically after conversion",
                       variable=self.auto_open_var).pack(anchor="w", padx=16, pady=(16, 0))

        ctk.CTkLabel(outer, text="Base Folder", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(16, 0))
        base_row = ctk.CTkFrame(outer, fg_color="transparent")
        base_row.pack(anchor="w", padx=16, fill="x")
        self.base_folder_var = ctk.StringVar(value=str(app.env.base_folder))
        ctk.CTkEntry(base_row, textvariable=self.base_folder_var, width=300).pack(side="left")
        ctk.CTkButton(base_row, text="Browse", width=70, command=self._browse_base_folder).pack(side="left", padx=6)

        ctk.CTkLabel(outer, text="Log verbosity", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=16, pady=(16, 0))
        self.log_verbosity_var = ctk.StringVar(value=settings.get("log_verbosity", "Normal"))
        ctk.CTkOptionMenu(outer, values=["Normal", "Verbose"],
                         variable=self.log_verbosity_var).pack(anchor="w", padx=24)

        ctk.CTkLabel(outer, text="Conversion Logs", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(outer, text="Every conversion attempt writes a full log here, findable by "
                                 "source filename and model even after the app is restarted.",
                    text_color="gray", wraplength=500, justify="left").pack(anchor="w", padx=16)
        ctk.CTkButton(outer, text="Open Logs Folder", width=160,
                     command=self._open_logs_folder).pack(anchor="w", padx=16, pady=(4, 0))

        ctk.CTkLabel(outer, text="Timeouts per model", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 0))
        ctk.CTkLabel(outer,
                     text="Inactivity Timeout:  Kills the model automatically if it goes "
                          "completely silent for that long.\n"
                          "Max. Runtime Timeout:  Kills the model automatically if it gets "
                          "stuck for that long.\n"
                          "Untick a box to remove that limit entirely for a model.",
                    text_color="gray", wraplength=500, justify="left").pack(anchor="w", padx=16)
        # Plain (non-scrolling) frame - the OUTER scrollbar above is now the
        # only scrollbar in this dialog, so this table just grows with the
        # rest of the content instead of clipping itself to a fixed viewport.
        timeout_table = ctk.CTkFrame(outer, fg_color="transparent")
        timeout_table.pack(fill="x", padx=16, pady=(4, 0))
        header = ctk.CTkFrame(timeout_table, fg_color="transparent")
        header.pack(fill="x", anchor="w")
        ctk.CTkLabel(header, text="Model", width=150, anchor="w",
                    font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text="Inactivity (s)", width=130, anchor="w",
                    font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text="Max runtime (s)", width=130, anchor="w",
                    font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.timeout_vars: dict = {}
        self.max_runtime_vars: dict = {}
        self.timeout_enabled_vars: dict = {}
        self.max_runtime_enabled_vars: dict = {}
        for model_key, model in sorted(MODEL_REGISTRY.items(), key=lambda kv: kv[1].display_name):
            row = ctk.CTkFrame(timeout_table, fg_color="transparent")
            row.pack(fill="x", anchor="w", pady=1)
            ctk.CTkLabel(row, text=model.display_name, width=150, anchor="w").pack(side="left")

            inact_cell = ctk.CTkFrame(row, fg_color="transparent", width=130)
            inact_cell.pack(side="left")
            var = ctk.StringVar(value=str(settings.get_effective_timeout(model_key) or model.timeout_seconds))
            entry = ctk.CTkEntry(inact_cell, textvariable=var, width=70)
            enabled = settings.get_timeout_enabled(model_key)
            entry.configure(state="normal" if enabled else "disabled")
            evar = ctk.BooleanVar(value=enabled)

            def _toggle_inact(e=entry, ev=evar):
                e.configure(state="normal" if ev.get() else "disabled")

            ctk.CTkCheckBox(inact_cell, text="", width=20, variable=evar,
                           command=_toggle_inact).pack(side="left")
            entry.pack(side="left", padx=(4, 0))
            self.timeout_vars[model_key] = var
            self.timeout_enabled_vars[model_key] = evar

            max_cell = ctk.CTkFrame(row, fg_color="transparent", width=130)
            max_cell.pack(side="left")
            mvar = ctk.StringVar(value=str(settings.get_effective_max_runtime(model_key) or model.max_runtime_seconds))
            mentry = ctk.CTkEntry(max_cell, textvariable=mvar, width=70)
            menabled = settings.get_max_runtime_enabled(model_key)
            mentry.configure(state="normal" if menabled else "disabled")
            mevar = ctk.BooleanVar(value=menabled)

            def _toggle_max(e=mentry, ev=mevar):
                e.configure(state="normal" if ev.get() else "disabled")

            ctk.CTkCheckBox(max_cell, text="", width=20, variable=mevar,
                           command=_toggle_max).pack(side="left")
            mentry.pack(side="left", padx=(4, 0))
            self.max_runtime_vars[model_key] = mvar
            self.max_runtime_enabled_vars[model_key] = mevar

        btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=20)
        ctk.CTkButton(btn_row, text="Reset to defaults", command=self._reset_defaults).pack(side="left")
        ctk.CTkButton(btn_row, text="Save", command=self._save).pack(side="right")

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(title="Choose default output folder")
        if folder:
            self.custom_folder_var.set(folder)
            self.output_mode.set("custom")

    def _browse_base_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose Base Folder")
        if folder:
            self.base_folder_var.set(folder)

    def _open_logs_folder(self) -> None:
        folder = self.app.env.conversion_logs_dir()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))
        except OSError:
            pass

    def _reset_defaults(self) -> None:
        if messagebox.askyesno("Reset to defaults", "Reset all settings to defaults?"):
            for key, value in DEFAULT_SETTINGS.items():
                if key not in ("model_status_cache", "base_folder"):
                    self.app.settings.set(key, value, debounce=False)
            self.destroy()
            messagebox.showinfo("Reset", "Settings reset. Some changes may need a restart.")

    def _save(self) -> None:
        s = self.app.settings
        s.set("output_folder_mode", self.output_mode.get())
        s.set("custom_output_folder", self.custom_folder_var.get())
        s.set("appearance_mode", self.appearance_var.get())
        ctk.set_appearance_mode(self.appearance_var.get())
        s.set("auto_open_after_conversion", self.auto_open_var.get())
        s.set("log_verbosity", self.log_verbosity_var.get())
        for model_key, var in self.timeout_vars.items():
            try:
                s.set_timeout_override(model_key, int(var.get()))
            except ValueError:
                messagebox.showerror("Invalid timeout",
                                      f"Inactivity timeout for {MODEL_REGISTRY[model_key].display_name} "
                                      f"must be a whole number of seconds.")
                return
            s.set_timeout_enabled(model_key, self.timeout_enabled_vars[model_key].get())
        for model_key, mvar in self.max_runtime_vars.items():
            try:
                s.set_max_runtime_override(model_key, int(mvar.get()))
            except ValueError:
                messagebox.showerror("Invalid timeout",
                                      f"Max runtime for {MODEL_REGISTRY[model_key].display_name} "
                                      f"must be a whole number of seconds.")
                return
            s.set_max_runtime_enabled(model_key, self.max_runtime_enabled_vars[model_key].get())

        new_base = Path(self.base_folder_var.get())
        if str(new_base) != str(self.app.env.base_folder):
            self.app.change_base_folder(new_base)

        s.save_now()
        self.destroy()


# ===== GUI: ONBOARDING =====

class OnboardingWindow(ctk.CTkToplevel):
    def __init__(self, app: "App", on_complete: Callable[[Path], None]):
        super().__init__(app)
        self.app = app
        self.on_complete = on_complete
        self.title(f"Welcome to {APP_NAME}")
        self.geometry("560x260")
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # must choose a folder to proceed

        ctk.CTkLabel(self, text=f"Welcome to {APP_NAME}", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 8))
        ctk.CTkLabel(self, text="Choose a Base Folder where models, environments, and settings will live.",
                     wraplength=500, justify="center").pack(pady=(0, 12))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=8)
        self.folder_var = ctk.StringVar(value=str(EnvManager.default_base_folder()))
        ctk.CTkEntry(row, textvariable=self.folder_var, width=340).pack(side="left")
        ctk.CTkButton(row, text="Browse", command=self._browse).pack(side="left", padx=6)

        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=6)

        ctk.CTkButton(self, text="Continue", command=self._confirm).pack(pady=12)

    def _browse(self) -> None:
        folder = filedialog.askdirectory(title="Choose Base Folder")
        if folder:
            self.folder_var.set(folder)

    def _confirm(self) -> None:
        folder = Path(self.folder_var.get())
        env = EnvManager(folder)
        if not env.is_writable():
            self.status_label.configure(text="That folder isn't writable. Choose another.", text_color="red")
            return
        free_gb = env.free_space_gb()
        if free_gb < 5:
            proceed = messagebox.askyesno(
                "Low disk space",
                f"Only {free_gb:.1f} GB free on that drive. Some models need several GB each. Continue anyway?")
            if not proceed:
                return
        self.destroy()
        self.on_complete(folder)


# ===== APP ENTRY POINT =====

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self.title(f"{APP_NAME} v.{APP_VERSION}")
        remembered_folder = EnvManager.read_remembered_base_folder()
        initial_folder = remembered_folder if remembered_folder else EnvManager.default_base_folder()
        self.env = EnvManager(initial_folder)
        self.settings = Settings(self.env)
        self.installer = None
        self.event_queue: "queue.Queue[InstallEvent]" = queue.Queue()
        self._install_watchers: dict = {}

        geometry = self.settings.get("window_geometry", "1100x720+100+100")
        self._last_programmatic_geometry = geometry
        try:
            self.geometry(geometry)
        except Exception:
            self.geometry("1100x720")
        self.bind("<Configure>", self._on_configure)

        ctk.set_appearance_mode(self.settings.get("appearance_mode", "System"))

        self.tabview: Optional[ctk.CTkTabview] = None
        self.convert_tab: Optional[ConvertTab] = None
        self.advisor_tab: Optional[AdvisorTab] = None
        self.model_manager_tab: Optional[ModelManagerTab] = None
        self.about_tab: Optional[AboutTab] = None

        self._rotate_logs()
        self._session_log_path = self.env.logs_dir() / f"session_{datetime.now():%Y%m%d_%H%M%S}.log"

        if not self.settings.get("onboarding_complete", False):
            self.withdraw()
            OnboardingWindow(self, self._after_onboarding)
        else:
            self._finish_setup()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- onboarding / base folder ----

    def _after_onboarding(self, folder: Path) -> None:
        self.env = EnvManager(folder)
        self.env.ensure_layout()
        self.settings = Settings(self.env)
        self.settings.set("base_folder", str(folder))
        self.settings.set("onboarding_complete", True, debounce=False)
        EnvManager.write_remembered_base_folder(folder)
        self.deiconify()
        self._finish_setup()

    def _finish_setup(self) -> None:
        self.env.ensure_layout()
        self.installer = Installer(self.env, self.settings, self.event_queue)
        self._reconcile_status_cache()
        self._build_tabs()
        self._fit_window_to_convert_tab()
        self.after(200, self._poll_install_events)

    def _build_tabs(self) -> None:
        top_bar = ctk.CTkFrame(self, height=36, fg_color="transparent")
        top_bar.pack(fill="x", side="top", padx=6, pady=(6, 0))
        # Settings lives in a top bar above the tabview (not below tab content) so
        # it's always visible regardless of how tall any given tab's content is -
        # previously it sat at the bottom of the window and got pushed off-screen
        # on taller tabs like Convert.
        ctk.CTkButton(top_bar, text="Settings", width=90,
                      command=lambda: SettingsWindow(self)).pack(side="right")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=6, pady=(6, 0))
        self.tabview.add("Convert")
        self.tabview.add("Advisor")
        self.tabview.add("Model Manager")
        self.tabview.add("About")
        self.tabview._segmented_button.configure(
            font=ctk.CTkFont(size=15, weight="bold"), height=40)

        self.convert_tab = ConvertTab(self.tabview.tab("Convert"), self)
        self.convert_tab.pack(fill="both", expand=True)
        # The Convert tab is a CTkScrollableFrame whose natural content height
        # (all its stacked panels) is well over 1000px. Without this, Tk keeps
        # propagating that full requested size up through the tab frame to the
        # toplevel, silently enforcing it as the window's real minimum height -
        # any attempt to shrink the window below it just snaps back, since the
        # scrollable frame's own internal scrollbar (its actual overflow
        # mechanism) never gets a chance to take over. Disabling propagation
        # here lets the window be freely resized smaller; the Convert tab
        # scrolls internally for whatever no longer fits.
        self.tabview.tab("Convert").pack_propagate(False)
        self.advisor_tab = AdvisorTab(self.tabview.tab("Advisor"), self)
        self.advisor_tab.pack(fill="both", expand=True)
        self.model_manager_tab = ModelManagerTab(self.tabview.tab("Model Manager"), self)
        self.model_manager_tab.pack(fill="both", expand=True)
        self.about_tab = AboutTab(self.tabview.tab("About"), self)
        self.about_tab.pack(fill="both", expand=True)

        if not any(self.settings.get_cached_status(k) == InstallStatus.INSTALLED.value
                   for k in MODEL_REGISTRY):
            messagebox.showinfo(
                "No models installed yet",
                "No models installed yet. Go to Model Manager to install one.")
            self.tabview.set("Model Manager")

    def _fit_window_to_convert_tab(self) -> None:
        """Only on the very first-ever launch (no manually-resized geometry
        saved yet), size the window to fit the Convert tab's own natural
        content size - a sensible starting point instead of an arbitrary
        default. Once the person resizes the window themselves, that choice
        is remembered and respected on every future launch instead of being
        overridden here. Deferred one event-loop turn via after(): measuring
        immediately after building the widgets can read stale (too-small)
        sizes for the nested scrollable panels before Tk has finished
        settling their layout."""
        if self.settings.get("window_geometry_customized", False):
            return
        self.update_idletasks()
        self.after(150, self._apply_fitted_geometry)

    def _apply_fitted_geometry(self) -> None:
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        ct = self.convert_tab

        content_w = ct.winfo_reqwidth()
        width = min(content_w + 60, screen_w - 40)

        # Now that the tab frame has propagation disabled (see _build_tabs),
        # ct.winfo_reqheight() reflects the Convert tab's true full content
        # height directly - no need to reconstruct it from a hand-maintained
        # sum of panel heights that can silently drift out of sync.
        top_overhead = ct.winfo_rooty() - self.winfo_rooty()  # top bar + tab strip + padding
        height = min(top_overhead + ct.winfo_reqheight() + 14, screen_h - 60)

        geometry = self.settings.get("window_geometry", "1100x720+100+100")
        x, y = 100, 100
        if "+" in geometry:
            try:
                _, x_str, y_str = geometry.split("+")
                x, y = int(x_str), int(y_str)
            except ValueError:
                pass
        geom_str = f"{int(width)}x{int(height)}+{x}+{y}"
        self._last_programmatic_geometry = geom_str
        self.geometry(geom_str)

    def _reconcile_status_cache(self) -> None:
        """Runs whenever the Base Folder is set (first-run onboarding, a later
        change, or just relaunching): checks on-disk layout against cached status
        in BOTH directions - promotes a model to Installed if its files are
        genuinely present (even if the cache said otherwise, e.g. a fresh
        settings.json pointed at a folder that already has models in it), and
        demotes to Not Installed if the cache says Installed but the files are
        missing. Does not re-run smoke tests automatically - the user can hit
        Verify for a definitive check."""
        for key, model in MODEL_REGISTRY.items():
            cached = self.settings.get_cached_status(key)
            on_disk_ok = self._on_disk_layout_present(model)
            if on_disk_ok and cached != InstallStatus.INSTALLED.value:
                self.settings.set_cached_status(key, InstallStatus.INSTALLED.value)
            elif not on_disk_ok and cached == InstallStatus.INSTALLED.value:
                self.settings.set_cached_status(key, InstallStatus.NOT_INSTALLED.value)

    def _on_disk_layout_present(self, model: ModelDef) -> bool:
        if model.weight == Weight.HEAVY:
            return self.env.model_python(model.key).exists() and self.env.model_runner_script(model.key).exists()
        if model.special_case == "tesseract_binary":
            return self.env.tesseract_exe().exists() or shutil.which("tesseract") is not None
        if model.special_case == "pandoc_binary":
            return self.env.pandoc_exe().exists() or shutil.which("pandoc") is not None
        # Plain Light package: these install into the main app's own Python
        # environment, not the Base Folder, so check for the real import there -
        # this is independent of which Base Folder is currently selected.
        return importlib.util.find_spec(_light_import_name(model.key)) is not None

    def change_base_folder(self, new_folder: Path) -> None:
        old_env = self.env
        choice = messagebox.askyesnocancel(
            "Change Base Folder",
            "Move existing installed models/binaries to the new location automatically?\n\n"
            "Yes = move them.\nNo = leave them, start fresh at the new location "
            "(existing models show as Not Installed until reinstalled).\nCancel = don't change.")
        if choice is None:
            return
        new_env = EnvManager(new_folder)
        if not new_env.is_writable():
            messagebox.showerror("Not writable", "That folder isn't writable.")
            return
        new_env.ensure_layout()
        if choice:
            for sub in ("envs", "models", "bin"):
                src = old_env.base_folder / sub
                dst = new_env.base_folder / sub
                if src.exists():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.move(str(src), str(dst))
        else:
            for key in MODEL_REGISTRY:
                self.settings.set_cached_status(key, InstallStatus.NOT_INSTALLED.value)
        self.env = new_env
        self.settings.env = new_env
        self.settings.set("base_folder", str(new_folder), debounce=False)
        EnvManager.write_remembered_base_folder(new_folder)
        self._reconcile_status_cache()
        if self.model_manager_tab:
            self.model_manager_tab._build_rows()
        if self.convert_tab:
            self.convert_tab.refresh_all_model_statuses()

    # ---- install event pump ----

    def _poll_install_events(self) -> None:
        try:
            while True:
                event: InstallEvent = self.event_queue.get_nowait()
                self._handle_install_event(event)
        except queue.Empty:
            pass
        self.after(200, self._poll_install_events)

    def _handle_install_event(self, event: InstallEvent) -> None:
        if event.kind == "log" and self.model_manager_tab:
            self.model_manager_tab.append_log(event.model_key, event.message)
        elif event.kind == "error" and self.model_manager_tab:
            self.model_manager_tab.append_log(event.model_key, f"ERROR: {human_pip_error(event.message)}")
            self.model_manager_tab.append_log(
                event.model_key,
                f"[Show details] {event.message[:3000]}"
                + ("... (truncated - use 'Export Log (txt)' for the full text)"
                   if len(event.message) > 3000 else ""))
        elif event.kind == "status" and self.model_manager_tab:
            self.model_manager_tab.refresh_status(event.model_key, event.status)
            if self.convert_tab:
                self.convert_tab.refresh_all_model_statuses()
            if event.status in (InstallStatus.INSTALLED.value, InstallStatus.FAILED_VERIFICATION.value,
                                InstallStatus.NOT_INSTALLED.value):
                watcher = self._install_watchers.pop(event.model_key, None)
                if watcher:
                    watcher()

    def watch_install_completion(self, model_key: str, callback: Callable[[], None]) -> None:
        self._install_watchers[model_key] = callback

    # ---- navigation helpers ----

    def goto_model_manager(self, highlight: Optional[str] = None) -> None:
        if self.tabview:
            self.tabview.set("Model Manager")

    def goto_convert_with_model(self, ext: str, model_key: str) -> None:
        if self.tabview:
            self.tabview.set("Convert")
        if self.convert_tab:
            self.convert_tab.preselect_model(ext, model_key)

    def ask_collision_choice(self, md_path: Path) -> tuple:
        win = ctk.CTkToplevel(self)
        win.title("File already exists")
        win.geometry("420x220")
        result = {"choice": "skip", "apply_all": False}
        ctk.CTkLabel(win, text=f"'{md_path.name}' already exists.", wraplength=380).pack(pady=(16, 8))
        apply_all_var = ctk.BooleanVar(value=False)

        def pick(choice):
            result["choice"] = choice
            result["apply_all"] = apply_all_var.get()
            win.destroy()

        ctk.CTkButton(win, text="Overwrite", command=lambda: pick("overwrite")).pack(pady=4)
        ctk.CTkButton(win, text="Skip", command=lambda: pick("skip")).pack(pady=4)
        ctk.CTkButton(win, text="Auto-rename", command=lambda: pick("rename")).pack(pady=4)
        ctk.CTkCheckBox(win, text="Apply to all remaining conflicts in this batch",
                       variable=apply_all_var).pack(pady=8)
        win.grab_set()
        self.wait_window(win)
        return result["choice"], result["apply_all"]

    def parse_dnd_paths(self, data: str) -> list:
        paths = []
        current = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                current = ""
            elif ch == "}":
                in_brace = False
                paths.append(current)
                current = ""
            elif ch == " " and not in_brace:
                if current:
                    paths.append(current)
                current = ""
            else:
                current += ch
        if current:
            paths.append(current)
        return paths

    # ---- misc ----

    def _rotate_logs(self) -> None:
        logs_dir = self.env.logs_dir()
        if not logs_dir.exists():
            return
        logs = sorted(logs_dir.glob("session_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        total_size = sum(p.stat().st_size for p in logs)
        max_count = 20
        max_bytes = 100 * 1024 * 1024
        while len(logs) > max_count or total_size > max_bytes:
            victim = logs.pop()
            total_size -= victim.stat().st_size
            try:
                victim.unlink()
            except OSError:
                pass

    def _on_configure(self, event) -> None:
        if event.widget is not self:
            return
        current = self.geometry()
        if current == getattr(self, "_last_programmatic_geometry", None):
            return  # our own _apply_fitted_geometry() call, not something the user did
        self.settings.set("window_geometry", current)
        self.settings.set("window_geometry_customized", True)

    def _on_close(self) -> None:
        self.settings.save_now()
        self.destroy()


def _check_python_version() -> None:
    if sys.version_info < PYTHON_MIN_VERSION:
        print(f"{APP_NAME} requires Python {PYTHON_MIN_VERSION[0]}.{PYTHON_MIN_VERSION[1]}+.")
        sys.exit(1)


if __name__ == "__main__":
    _check_python_version()
    bootstrap_optional_packages_if_launching_app()
    app = App()
    app.mainloop()

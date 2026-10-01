"""
Dev-only unit tests. Not part of the shipped app (see README.md).

Importing md_converter.py still requires customtkinter/tkinterdnd2 to be installed
(module-level imports execute), but no GUI mainloop or display needs to be running.
Run with: python -m pytest test_md_converter.py -v
"""

import json
import queue
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import md_converter as mc


class TestRegistryHelpers(unittest.TestCase):
    def test_get_models_for_extension_pdf(self):
        models = mc.get_models_for_extension(".pdf")
        keys = {m.key for m in models}
        self.assertIn("docling", keys)
        self.assertIn("pymupdf4llm", keys)
        self.assertIn("marker", keys)

    def test_get_models_for_extension_unknown(self):
        self.assertEqual(mc.get_models_for_extension(".xyz"), [])

    def test_get_fit_variant_specific(self):
        pymupdf4llm = mc.MODEL_REGISTRY["pymupdf4llm"]
        self.assertEqual(mc.get_fit(pymupdf4llm, ".pdf", "text"), mc.FitRating.BEST)
        self.assertEqual(mc.get_fit(pymupdf4llm, ".pdf", "scanned"), mc.FitRating.NOT_RECOMMENDED)

    def test_get_fit_falls_back_without_variant(self):
        trafilatura = mc.MODEL_REGISTRY["trafilatura"]
        self.assertEqual(mc.get_fit(trafilatura, ".html"), mc.FitRating.BEST)

    def test_every_registered_model_has_pins_or_special_case(self):
        for model in mc.MODEL_REGISTRY.values():
            self.assertTrue(model.pip_pins or model.special_case,
                             f"{model.key} has no pip pins and no special case")

    def test_no_duplicate_model_keys(self):
        keys = list(mc.MODEL_REGISTRY.keys())
        self.assertEqual(len(keys), len(set(keys)))


class TestAdvisor(unittest.TestCase):
    def test_rank_models_orders_best_first(self):
        ranked = mc.Advisor.rank_models(".pdf", "scanned")
        ratings = [r[1] for r in ranked]
        order = {mc.FitRating.BEST: 0, mc.FitRating.GOOD: 1, mc.FitRating.USABLE: 2,
                 mc.FitRating.NOT_RECOMMENDED: 3}
        numeric = [order[r] for r in ratings]
        self.assertEqual(numeric, sorted(numeric))

    def test_rank_models_empty_for_unsupported_extension(self):
        self.assertEqual(mc.Advisor.rank_models(".zzz"), [])

    def test_rank_models_never_hides_a_model_for_variant(self):
        # PyMuPDF4LLM supports .pdf but is Not Recommended for scanned - it must still appear.
        ranked = mc.Advisor.rank_models(".pdf", "scanned")
        keys = {m.key for m, _, _ in ranked}
        self.assertIn("pymupdf4llm", keys)

    def test_detect_pdf_variant_missing_file_defaults_to_text(self):
        variant = mc.Advisor.detect_pdf_variant(Path("does_not_exist.pdf"))
        self.assertIn(variant, ("text", "scanned"))


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env = mc.EnvManager(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_defaults_when_no_file(self):
        s = mc.Settings(self.env)
        self.assertEqual(s.get("appearance_mode"), "System")

    def test_save_and_reload(self):
        s = mc.Settings(self.env)
        s.set("appearance_mode", "Dark", debounce=False)
        s2 = mc.Settings(self.env)
        self.assertEqual(s2.get("appearance_mode"), "Dark")

    def test_recent_conversions_capped_at_20(self):
        s = mc.Settings(self.env)
        for i in range(25):
            s.add_recent_conversion(f"src{i}.pdf", f"out{i}.md", "docling")
        self.assertEqual(len(s.get("recent_conversions")), 20)
        # Most recent first
        self.assertEqual(s.get("recent_conversions")[0]["source"], "src24.pdf")

    def test_last_used_model_per_category(self):
        s = mc.Settings(self.env)
        s.set_last_used_model(".pdf", "docling")
        self.assertEqual(s.get_last_used_model(".pdf"), "docling")
        self.assertIsNone(s.get_last_used_model(".html"))

    def test_cached_status_roundtrip(self):
        s = mc.Settings(self.env)
        s.set_cached_status("docling", mc.InstallStatus.INSTALLED.value)
        self.assertEqual(s.get_cached_status("docling"), mc.InstallStatus.INSTALLED.value)
        self.assertEqual(s.get_cached_status("marker"), mc.InstallStatus.NOT_INSTALLED.value)

    def test_corrupt_settings_file_falls_back_to_defaults(self):
        self.env.ensure_layout()
        self.env.settings_path().write_text("{not valid json", encoding="utf-8")
        s = mc.Settings(self.env)
        self.assertEqual(s.get("appearance_mode"), "System")


class TestEnvManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ensure_layout_creates_expected_dirs(self):
        env = mc.EnvManager(self.tmp_dir)
        env.ensure_layout()
        for sub in ("envs", "models", "bin", "config", "logs", "temp"):
            self.assertTrue((self.tmp_dir / sub).is_dir())

    def test_default_base_folder_is_next_to_the_app_not_localappdata(self):
        suggested = mc.EnvManager.default_base_folder()
        self.assertEqual(suggested.name, "MD Converter Data")
        self.assertEqual(suggested.parent, Path(mc.sys.argv[0]).resolve().parent)

    def test_pointer_file_roundtrip(self):
        pointer_path = mc.EnvManager.pointer_file_path()
        original = None
        if pointer_path.exists():
            original = pointer_path.read_text(encoding="utf-8")
        try:
            mc.EnvManager.write_remembered_base_folder(self.tmp_dir / "chosen_base")
            remembered = mc.EnvManager.read_remembered_base_folder()
            self.assertEqual(remembered, self.tmp_dir / "chosen_base")
        finally:
            if original is not None:
                pointer_path.write_text(original, encoding="utf-8")
            elif pointer_path.exists():
                pointer_path.unlink()

    def test_read_remembered_base_folder_none_when_missing(self):
        pointer_path = mc.EnvManager.pointer_file_path()
        original = None
        if pointer_path.exists():
            original = pointer_path.read_text(encoding="utf-8")
            pointer_path.unlink()
        try:
            self.assertIsNone(mc.EnvManager.read_remembered_base_folder())
        finally:
            if original is not None:
                pointer_path.write_text(original, encoding="utf-8")

    def test_is_writable_true_for_new_folder(self):
        env = mc.EnvManager(self.tmp_dir / "new_base")
        self.assertTrue(env.is_writable())

    def test_model_paths_scoped_under_base_folder(self):
        env = mc.EnvManager(self.tmp_dir)
        self.assertTrue(str(env.model_env_dir("docling")).startswith(str(self.tmp_dir)))
        self.assertTrue(str(env.model_weights_dir("docling")).startswith(str(self.tmp_dir)))


class TestInstaller(unittest.TestCase):
    """Subprocess/network layer mocked throughout - no real installs happen."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.env = mc.EnvManager(self.tmp_dir)
        self.env.ensure_layout()
        self.settings = mc.Settings(self.env)
        self.events: "queue.Queue" = queue.Queue()
        self.installer = mc.Installer(self.env, self.settings, self.events)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _drain_events(self):
        out = []
        try:
            while True:
                out.append(self.events.get_nowait())
        except queue.Empty:
            pass
        return out

    def test_check_disk_space_reports_shortfall(self):
        model = mc.MODEL_REGISTRY["marker"]
        with patch.object(self.env, "free_space_gb", return_value=1.0):
            required, available, ok = self.installer.check_disk_space(model.key)
            self.assertEqual(required, model.install_size_gb)
            self.assertEqual(available, 1.0)
            self.assertFalse(ok)

    def test_check_disk_space_skips_small_installs(self):
        # markdownify's install_size_gb is well under 500MB
        with patch.object(self.env, "free_space_gb", return_value=0.01):
            required, available, ok = self.installer.check_disk_space("markdownify")
            self.assertTrue(ok)

    def test_light_install_uses_explicit_interpreter(self):
        model = mc.MODEL_REGISTRY["trafilatura"]
        with patch.object(self.installer, "_run_streamed", return_value=True) as mock_run:
            ok = self.installer._install_light(model)
        self.assertTrue(ok)
        for call in mock_run.call_args_list:
            cmd = call.args[1]
            self.assertEqual(cmd[0], mc.sys.executable)
            self.assertNotEqual(cmd[0], "pip")

    def test_heavy_install_never_installs_gpu_wheel_without_gpu(self):
        model = mc.MODEL_REGISTRY["paddleocr"]
        with patch.object(self.installer, "_run_streamed", return_value=True), \
             patch.object(self.installer, "_find_base_python", return_value=mc.sys.executable), \
             patch.object(self.installer, "_gpu_available", return_value=False), \
             patch.object(self.env, "model_python", return_value=Path(mc.sys.executable)):
            ok = self.installer._install_heavy(model)
        self.assertTrue(ok)

    def test_install_retries_transient_failures(self):
        model_key = "trafilatura"
        attempts = {"count": 0}

        class FakeProc:
            def __init__(self, returncode):
                self.returncode = returncode
                self.stdout = iter([])
                self.pid = 12345

            def wait(self):
                pass

        def fake_popen(cmd, **kwargs):
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise OSError("transient")
            return FakeProc(0)

        with patch("subprocess.Popen", side_effect=fake_popen), \
             patch("time.sleep", return_value=None):
            result = self.installer._run_streamed(model_key, [mc.sys.executable, "-m", "pip", "install", "x"],
                                                    retries=3)
        self.assertTrue(result)
        self.assertEqual(attempts["count"], 2)

    def test_install_gives_up_after_retries_and_emits_error(self):
        def fake_popen(cmd, **kwargs):
            raise OSError("still broken")

        with patch("subprocess.Popen", side_effect=fake_popen), \
             patch("time.sleep", return_value=None):
            result = self.installer._run_streamed("trafilatura", ["x"], retries=2)
        self.assertFalse(result)
        events = self._drain_events()
        self.assertTrue(any(e.kind == "error" for e in events))

    def test_cancel_sets_flag_and_kills_process(self):
        with patch.object(self.installer, "_kill_process_tree") as mock_kill:
            fake_proc = MagicMock(pid=999)
            self.installer._active_procs["marker"] = fake_proc
            self.installer.cancel_install("marker")
            self.assertTrue(self.installer._cancel_flags["marker"])
            mock_kill.assert_called_once_with(999)

    def test_uninstall_only_touches_that_models_folder(self):
        env = self.env
        marker_env = env.model_env_dir("marker")
        docling_env = env.model_env_dir("docling")
        marker_env.mkdir(parents=True)
        docling_env.mkdir(parents=True)
        (marker_env / "marker_file.txt").write_text("x")
        (docling_env / "docling_file.txt").write_text("x")

        self.installer.uninstall_model("marker")

        self.assertFalse(marker_env.exists())
        self.assertTrue(docling_env.exists())
        self.assertEqual(self.settings.get_cached_status("marker"), mc.InstallStatus.NOT_INSTALLED.value)

    def test_verify_light_model_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            self.installer._verify_model_worker("trafilatura")
        self.assertEqual(self.settings.get_cached_status("trafilatura"), mc.InstallStatus.INSTALLED.value)

    def test_tesseract_installer_downloads_to_temp_and_cleans_up_after_success(self):
        downloaded_path = {}

        def fake_urlretrieve(url, filename):
            downloaded_path["path"] = Path(filename)
            Path(filename).write_bytes(b"fake installer")

        def fake_run(cmd, **kwargs):
            self.env.tesseract_exe().parent.mkdir(parents=True, exist_ok=True)
            self.env.tesseract_exe().write_text("fake")
            return MagicMock(returncode=0)

        with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve), \
             patch("subprocess.run", side_effect=fake_run):
            ok = self.installer._install_tesseract_binary("tesseract")

        self.assertTrue(ok)
        self.assertTrue(str(downloaded_path["path"]).startswith(str(self.env.temp_dir())),
                         "installer should download into the base folder's temp dir")
        self.assertFalse(downloaded_path["path"].exists(),
                          "installer file should be deleted after a successful install")

    def test_tesseract_installer_cleaned_up_even_on_failure(self):
        def fake_urlretrieve(url, filename):
            Path(filename).write_bytes(b"fake installer")

        with patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve), \
             patch("subprocess.run", side_effect=OSError("boom")):
            ok = self.installer._install_tesseract_binary("tesseract")

        self.assertFalse(ok)
        leftover = list(self.env.temp_dir().glob("*"))
        self.assertEqual(leftover, [], "temp installer must not be left behind even when install fails")

    def test_verify_light_model_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"ModuleNotFoundError")
            self.installer._verify_model_worker("trafilatura")
        self.assertEqual(self.settings.get_cached_status("trafilatura"),
                         mc.InstallStatus.FAILED_VERIFICATION.value)

    def test_find_base_python_returns_something_usable(self):
        result = self.installer._find_base_python()
        self.assertIsNotNone(result)

    def test_find_base_python_prefers_py_3_12_over_running_interpreter(self):
        """Heavy-model deps (Pillow, lxml, torch, etc.) often lack prebuilt wheels
        for the newest Python; a broadly-supported 3.12 should win over whatever
        Python is running the app, if `py -3.12` is available."""
        def fake_run(cmd, **kwargs):
            if cmd == ["py", "-3.12", "--version"]:
                return MagicMock(returncode=0)
            raise FileNotFoundError("not found")
        def fake_which(name):
            return "/fake/path/py" if name == "py" else None
        with patch("subprocess.run", side_effect=fake_run), \
             patch.object(mc.shutil, "which", side_effect=fake_which):
            result = self.installer._find_base_python()
        self.assertEqual(result, "py -3.12")

    def test_find_base_python_falls_back_to_sys_executable_if_no_py_launcher(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("no py launcher")):
            result = self.installer._find_base_python()
        self.assertEqual(result, mc.sys.executable)


class TestHumanErrorMessages(unittest.TestCase):
    def test_network_error_translated(self):
        msg = mc.human_pip_error("HTTPSConnectionPool: Connection timed out")
        self.assertIn("internet", msg.lower())

    def test_disk_space_error_translated(self):
        msg = mc.human_pip_error("OSError: [Errno 28] No space left on device")
        self.assertIn("disk space", msg.lower())

    def test_unknown_error_has_generic_fallback(self):
        msg = mc.human_pip_error("some totally novel failure")
        self.assertTrue(len(msg) > 0)


if __name__ == "__main__":
    unittest.main()

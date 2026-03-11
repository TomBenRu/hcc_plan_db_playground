# tests/unit/test_translation_tool_gui.py
import pytest
from tools.translation_tool_gui import TranslationLogic


class TestScanLanguages:
    def test_returns_empty_list_if_no_ts_files(self, tmp_path):
        logic = TranslationLogic(str(tmp_path), str(tmp_path))
        assert logic.scan_languages() == []

    def test_detects_language_from_ts_filename(self, tmp_path):
        (tmp_path / "translations_de.ts").write_text("")
        (tmp_path / "translations_en.ts").write_text("")
        logic = TranslationLogic(str(tmp_path), str(tmp_path))
        assert sorted(logic.scan_languages()) == ["de", "en"]

    def test_ignores_non_ts_files(self, tmp_path):
        (tmp_path / "translations_de.ts").write_text("")
        (tmp_path / "something.qm").write_text("")
        logic = TranslationLogic(str(tmp_path), str(tmp_path))
        assert logic.scan_languages() == ["de"]


class TestFindPythonFiles:
    def test_finds_py_files_recursively(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "main.py").write_text("")
        (sub / "helper.py").write_text("")
        logic = TranslationLogic(str(tmp_path), str(tmp_path))
        files = logic.find_python_files()
        assert any("main.py" in f for f in files)
        assert any("helper.py" in f for f in files)

    def test_skips_venv_directory(self, tmp_path):
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "some_lib.py").write_text("")
        logic = TranslationLogic(str(tmp_path), str(tmp_path))
        files = logic.find_python_files()
        assert not any(".venv" in f for f in files)


class TestCreateTsFile:
    def test_creates_valid_ts_file(self, tmp_path):
        logic = TranslationLogic(str(tmp_path), str(tmp_path))
        ts_path = str(tmp_path / "translations_es.ts")
        logic.create_ts_file(ts_path, "es")
        content = open(ts_path, encoding="utf-8").read()
        assert 'language="es"' in content
        assert "<TS" in content

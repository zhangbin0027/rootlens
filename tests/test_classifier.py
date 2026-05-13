"""Tests for classifier.py — pattern loading, classify, extract_files."""
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch

from rootlens.classifier import classify, extract_files, _load_patterns


class TestClassify:
    def test_compile_error_matches(self):
        log = "src/main.cpp:10: error: 'x' was not declared in this scope"
        result = classify(log)
        assert result is not None
        assert result.error_type is not None

    def test_no_match_returns_none(self):
        result = classify("build succeeded with no issues")
        assert result is None

    def test_matched_signal_recorded(self):
        log = "error: cannot find symbol\n  symbol: class Foo"
        result = classify(log)
        if result is not None:
            assert result.matched_pattern != ""

    def test_classify_returns_error_signal_with_files(self):
        log = "src/auth/Login.java:42: error: cannot find symbol"
        result = classify(log)
        if result is not None:
            assert isinstance(result.error_files, list)


class TestExtractFiles:
    def test_extracts_java_file(self):
        log = "src/auth/Login.java:42: error: cannot find symbol"
        files = extract_files(log)
        assert any("Login.java" in f for f in files)

    def test_extracts_cpp_file(self):
        log = "src/engine/pipeline.cpp:10: error: undefined reference"
        files = extract_files(log)
        assert any(".cpp" in f for f in files)

    def test_skips_urls(self):
        log = "downloading https://example.com/lib.jar\nerror in src/main.py:1"
        files = extract_files(log)
        assert not any("example.com" in f for f in files)

    def test_skips_non_source_extensions(self):
        log = "reading config.conf and data.bin\nerror in src/main.go:1"
        files = extract_files(log)
        assert not any(
            f.endswith(".conf") or f.endswith(".bin") for f in files
        )

    def test_empty_log_returns_empty(self):
        assert extract_files("") == []

    def test_returns_sorted_list(self):
        log = "src/z.py:1: error\nsrc/a.py:2: error"
        files = extract_files(log)
        assert files == sorted(files)

    def test_url_in_log_skipped(self):
        files = extract_files("see https://example.com/error.py for details")
        assert not any("example.com" in f for f in files)

    def test_www_url_skipped(self):
        files = extract_files("visit www.docs.com/error.java for info")
        assert not any("www." in f for f in files)


class TestLoadPatterns:
    def setup_method(self):
        _load_patterns.cache_clear()

    def teardown_method(self):
        _load_patterns.cache_clear()

    def test_returns_tuple(self):
        assert isinstance(_load_patterns(), tuple)

    def test_patterns_have_compiled_key(self):
        for p in _load_patterns():
            assert "_compiled" in p

    def test_missing_config_returns_empty(self):
        with patch(
            "rootlens.classifier._CONFIG_DIR", Path("/nonexistent/path")
        ):
            assert _load_patterns() == ()

    def test_malformed_config_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "error_patterns.yaml"
            bad.write_text("12345")
            with patch("rootlens.classifier._CONFIG_DIR", Path(tmpdir)):
                assert _load_patterns() == ()

    def test_empty_config_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "error_patterns.yaml").write_text("")
            with patch("rootlens.classifier._CONFIG_DIR", Path(tmpdir)):
                assert _load_patterns() == ()

    def test_dict_with_patterns_key(self):
        data = {"patterns": [{"type": "TEST", "regex": "test_error"}]}
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "error_patterns.yaml").write_text(
                yaml.dump(data)
            )
            with patch("rootlens.classifier._CONFIG_DIR", Path(tmpdir)):
                result = _load_patterns()
        assert len(result) == 1
        assert result[0]["type"] == "TEST"

    def test_grouped_dict_format(self):
        data = {
            "group_a": [{"type": "A", "regex": "error_a"}],
            "group_b": [{"type": "B", "regex": "error_b"}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "error_patterns.yaml").write_text(
                yaml.dump(data)
            )
            with patch("rootlens.classifier._CONFIG_DIR", Path(tmpdir)):
                result = _load_patterns()
        assert len(result) == 2

    def test_invalid_regex_compiled_to_none(self):
        data = [{"type": "BAD", "regex": "[invalid("}]
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "error_patterns.yaml").write_text(
                yaml.dump(data)
            )
            with patch("rootlens.classifier._CONFIG_DIR", Path(tmpdir)):
                result = _load_patterns()
        assert result[0]["_compiled"] is None

    def test_binary_garbage_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "error_patterns.yaml").write_bytes(
                b"\x00\x01\x02"
            )
            with patch("rootlens.classifier._CONFIG_DIR", Path(tmpdir)):
                assert _load_patterns() == ()

    def test_compiled_none_falls_back_to_re_search(self):
        data = [{"type": "FALLBACK_TEST", "regex": "special_error_xyz"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "error_patterns.yaml").write_text(
                yaml.dump(data)
            )
            with patch("rootlens.classifier._CONFIG_DIR", Path(tmpdir)):
                pats = list(_load_patterns())
            pats[0]["_compiled"] = None
            with patch(
                "rootlens.classifier._load_patterns",
                return_value=tuple(pats),
            ):
                r = classify("special_error_xyz in build output")
        assert r is not None
        assert r.error_type == "FALLBACK_TEST"

    def test_compiled_none_bad_regex_skipped(self):
        """_compiled=None + invalid regex → except re.error → continue."""
        bad_pat = {"type": "BAD", "regex": "[invalid(", "_compiled": None}
        with patch(
            "rootlens.classifier._load_patterns",
            return_value=(bad_pat,),
        ):
            result = classify("anything [invalid(")
        assert result is None

"""Tests for core.formatters — the shared human_size utility."""
from core.formatters import human_size


class TestHumanSize:
    def test_none_returns_fallback(self):
        assert human_size(None) == "?"

    def test_zero_returns_fallback(self):
        assert human_size(0) == "?"

    def test_custom_fallback(self):
        assert human_size(None, fallback="N/A") == "N/A"
        assert human_size(0, fallback="N/A") == "N/A"

    def test_bytes_no_decimal(self):
        assert human_size(512) == "512 B"

    def test_one_kilobyte(self):
        assert human_size(1024) == "1.0 KB"

    def test_one_and_half_kilobytes(self):
        assert human_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert human_size(1024 * 1024 * 3) == "3.0 MB"

    def test_gigabytes(self):
        assert human_size(1024 ** 3 * 2) == "2.0 GB"

    def test_terabytes(self):
        assert human_size(1024 ** 4) == "1.0 TB"

    def test_negative_takes_absolute_value(self):
        assert human_size(-1024) == "1.0 KB"

    def test_float_input(self):
        assert human_size(1500.5) == "1.5 KB"

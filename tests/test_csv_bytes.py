import pytest

from dips import config, csv_writer, selftest
from dips.csv_writer import BOM


@pytest.fixture(scope="module")
def settings():
    return config.load_settings()


@pytest.fixture(scope="module")
def paths(settings):
    return config.Paths(settings)


@pytest.fixture(scope="module")
def header(paths):
    return csv_writer.read_template_header(paths.dips_template)


def _row(n=17):
    return [f"c{i}" for i in range(n)]


def test_template_has_17_columns(paths):
    names = csv_writer.template_header_names(paths.dips_template)
    assert len(names) == 17
    assert names[0] == "申請ID"
    assert names[6].endswith("無人航空機操縦者身体適性検査証明書番号")


def test_build_bytes_bom_crlf_no_trailing(header):
    data = csv_writer.build_csv_bytes(header, [_row(), _row()])
    assert data.startswith(BOM)
    assert b"\r\n" in data
    assert not data.endswith(b"\n") and not data.endswith(b"\r")
    # 行区切りは CRLF のみ（孤立LFなし）
    body = data[len(BOM):]
    assert body.count(b"\n") == body.count(b"\r\n") == body.count(b"\r")


def test_selftest_passes_on_valid_file(tmp_path, header, paths, settings):
    f = tmp_path / "out.csv"
    csv_writer.write_csv(f, header, [_row(), _row()], trailing_newline=False)
    report = selftest.run_selftest(f, paths.dips_template, settings)
    assert report.passed, [(c.name, c.detail) for c in report.checks if not c.ok]


def test_selftest_detects_header_mismatch(tmp_path, paths, settings):
    f = tmp_path / "bad.csv"
    csv_writer.write_csv(f, "申請ID,ちがう,ヘッダー", [["a", "b", "c"]])
    report = selftest.run_selftest(f, paths.dips_template, settings)
    assert not report.passed
    assert any(c.name == "ヘッダー完全一致" and not c.ok for c in report.checks)


def test_selftest_detects_trailing_newline(tmp_path, header, paths, settings):
    f = tmp_path / "trail.csv"
    csv_writer.write_csv(f, header, [_row()], trailing_newline=True)
    report = selftest.run_selftest(f, paths.dips_template, settings)
    assert not report.passed
    assert any(c.name == "末尾改行なし" and not c.ok for c in report.checks)


def test_selftest_detects_wrong_column_count(tmp_path, header, paths, settings):
    f = tmp_path / "cols.csv"
    csv_writer.write_csv(f, header, [_row(16)])  # 16列しかない
    report = selftest.run_selftest(f, paths.dips_template, settings)
    assert not report.passed
    assert any(c.name.startswith("列数") and not c.ok for c in report.checks)

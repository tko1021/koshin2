from dips.mapper import RowResult
from dips.pipeline import PreparedRow, split_files


def _pr(apply_id, applicant_no):
    # 17列のうち index1=申請ID(値0), index2=申請者番号(値1) のみ意味を持たせる
    values = [apply_id, applicant_no] + ["" for _ in range(15)]
    return PreparedRow(record={}, result=RowResult(values=values))


def test_same_applicant_no_goes_to_separate_files():
    rows = [_pr("ID1", "AAA"), _pr("ID2", "AAA"), _pr("ID3", "BBB")]
    files = split_files(rows, max_rows=500)
    assert len(files) == 2
    # 各ファイル内で申請者番号は一意
    for bucket in files:
        nos = [pr.applicant_no for pr in bucket]
        assert len(nos) == len(set(nos))
    # file1 = AAA,BBB / file2 = AAA
    assert {pr.applicant_no for pr in files[0]} == {"AAA", "BBB"}
    assert [pr.applicant_no for pr in files[1]] == ["AAA"]


def test_max_rows_per_file():
    rows = [_pr(f"ID{i}", f"NO{i}") for i in range(5)]
    files = split_files(rows, max_rows=2)
    assert [len(b) for b in files] == [2, 2, 1]


def test_no_split_when_unique_and_under_limit():
    rows = [_pr(f"ID{i}", f"NO{i}") for i in range(3)]
    files = split_files(rows, max_rows=500)
    assert len(files) == 1
    assert len(files[0]) == 3

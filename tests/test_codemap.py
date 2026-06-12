import pytest

from dips import codemap, config


@pytest.fixture(scope="module")
def cm():
    return config.load_code_map()


def test_kubun(cm):
    assert codemap.apply_map("一等", cm["kubun"]) == "1"
    assert codemap.apply_map("二等", cm["kubun"]) == "2"


def test_kubun_both_holders_prefers_ittou(cm):
    # 一等・二等の両方保有者は "1"
    assert codemap.apply_map("一等・二等", cm["kubun"]) == "1"


def test_teishi_reversed_and_blank(cm):
    # 直感と逆: 無→1 / 有→2、空欄は無扱いで1
    assert codemap.apply_map("無", cm["teishi"]) == "1"
    assert codemap.apply_map("有", cm["teishi"]) == "2"
    assert codemap.apply_map("", cm["teishi"]) == "1"
    assert codemap.apply_map(None, cm["teishi"]) == "1"


def test_jotai_leading_digit(cm):
    assert codemap.apply_map("1：新規", cm["jotai"]) == "1"
    assert codemap.apply_map("2：上書き修正", cm["jotai"]) == "2"
    assert codemap.apply_map("3：無効化", cm["jotai"]) == "3"


def test_koushu_prefix(cm):
    assert codemap.apply_map("UC：更新講習", cm["koushu_prefix"]) == "UC"
    assert codemap.apply_map("EL：失効再交付講習", cm["koushu_prefix"]) == "EL"


def test_unknown_value_raises(cm):
    with pytest.raises(codemap.CodeMapError):
        codemap.apply_map("三等", cm["kubun"])

import pytest

from fonti.domain import PageSpan, page_for_offset

PAGES = [PageSpan(1, 0, 100), PageSpan(2, 102, 200), PageSpan(4, 202, 300)]


@pytest.mark.parametrize(
    ("offset", "page"), [(0, 1), (99, 1), (101, 1), (102, 2), (250, 4), (999, 4)]
)
def test_page_for_offset(offset: int, page: int) -> None:
    assert page_for_offset(PAGES, offset) == page


def test_page_for_offset_without_pages_raises() -> None:
    with pytest.raises(ValueError, match="no pages"):
        page_for_offset([], 0)

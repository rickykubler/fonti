"""PNG previews of PDF pages, with a cited passage highlighted when the page has a text layer."""

import io
from pathlib import Path

import pypdfium2 as pdfium

_WINDOW = 4  # words searched at a time: short enough to stay on one line
_MAX_GAP = 5  # characters between consecutive windows: a space or a line break
_HIGHLIGHT = (255, 214, 0, 96)

Box = tuple[float, float, float, float]  # left, bottom, right, top in PDF points


def render_page(path: Path, page_number: int, passage: str = "", scale: float = 1.6) -> bytes:
    from PIL import ImageDraw

    pdf = pdfium.PdfDocument(path)
    try:
        if not 1 <= page_number <= len(pdf):
            raise ValueError(f"page {page_number} out of range")
        page = pdf[page_number - 1]
        try:
            image = page.render(scale=scale).to_pil().convert("RGB")
            if passage:
                height = page.get_height()
                draw = ImageDraw.Draw(image, "RGBA")
                for left, bottom, right, top in passage_boxes(page, passage):
                    box = (
                        left * scale,
                        (height - top) * scale,
                        right * scale,
                        (height - bottom) * scale,
                    )
                    draw.rectangle(box, fill=_HIGHLIGHT)
        finally:
            page.close()
    finally:
        pdf.close()
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def passage_boxes(page: pdfium.PdfPage, passage: str) -> list[Box]:
    """Rectangles (PDF points) covering the passage, found a few words at a time so that line
    breaks and hyphenation in the PDF do not prevent the match."""
    words = passage.split()
    windows = [" ".join(words[i : i + _WINDOW]) for i in range(0, len(words), _WINDOW)]
    textpage = page.get_textpage()
    boxes: list[Box] = []
    try:
        for index, count in _locate(textpage, windows):
            for i in range(textpage.count_rects(index, count)):
                boxes.append(textpage.get_rect(i))
    finally:
        textpage.close()
    return merge_lines(boxes)


def _locate(textpage: pdfium.PdfTextPage, windows: list[str]) -> list[tuple[int, int]]:
    """Matches (char index, count) of windows that follow one another in the page text.

    Searching each window on its own would match the first occurrence of a repeated phrase,
    such as a heading with the words that open the passage. A window that is not found close
    to the previous one (a word hyphenated across lines, a ligature) is skipped.
    """
    best: list[tuple[int, int]] = []
    for anchor, first_window in enumerate(windows):
        start = 0
        while (first := _find(textpage, first_window, start)) is not None:
            chain = [first]
            slack = 0
            for window in windows[anchor + 1 :]:
                end = chain[-1][0] + chain[-1][1]
                match = _find(textpage, window, end)
                if match is not None and match[0] - end <= _MAX_GAP + slack:
                    chain.append(match)
                    slack = 0
                else:
                    slack += len(window) + 1
            if len(chain) > len(best):
                best = chain
            if len(best) == len(windows) - anchor:
                return best
            start = first[0] + 1
        if best:
            return best
    return best


def _find(textpage: pdfium.PdfTextPage, text: str, start: int) -> tuple[int, int] | None:
    searcher = textpage.search(text, index=start, match_case=False)
    try:
        found: tuple[int, int] | None = searcher.get_next()
    finally:
        searcher.close()
    return found


def merge_lines(boxes: list[Box]) -> list[Box]:
    """Join consecutive rectangles on the same line, so that the spaces between the searched
    windows are highlighted too."""
    merged: list[Box] = []
    for left, bottom, right, top in boxes:
        if merged:
            last_left, last_bottom, last_right, last_top = merged[-1]
            height = min(top - bottom, last_top - last_bottom)
            overlap = min(top, last_top) - max(bottom, last_bottom)
            if overlap >= height / 2 and 0 <= left - last_right <= height:
                merged[-1] = (
                    last_left,
                    min(bottom, last_bottom),
                    max(right, last_right),
                    max(top, last_top),
                )
                continue
        merged.append((left, bottom, right, top))
    return merged

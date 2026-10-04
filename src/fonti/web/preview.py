"""PNG previews of PDF pages, with a cited passage highlighted when the page has a text layer."""

import io
from pathlib import Path

import pypdfium2 as pdfium

_WINDOW = 4  # words searched at a time: short enough to stay on one line
_HIGHLIGHT = (255, 214, 0, 96)


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


def passage_boxes(page: pdfium.PdfPage, passage: str) -> list[tuple[float, float, float, float]]:
    """Rectangles (PDF points) covering the passage, found a few words at a time so that line
    breaks and hyphenation in the PDF do not prevent the match."""
    words = passage.split()
    textpage = page.get_textpage()
    boxes: list[tuple[float, float, float, float]] = []
    try:
        start_index = 0
        for first in range(0, len(words), _WINDOW):
            window = " ".join(words[first : first + _WINDOW])
            searcher = textpage.search(window, index=start_index, match_case=False)
            found = searcher.get_next()
            searcher.close()
            if found is None:
                continue
            index, count = found
            start_index = index + count
            for i in range(textpage.count_rects(index, count)):
                boxes.append(textpage.get_rect(i))
    finally:
        textpage.close()
    return boxes

from random import randint
from time import sleep
from typing import Callable

from pymupdf import Rect, open


def flatten(
    src_path: str, dst_path: str, on_progress: Callable[[float], None] | None = None
) -> str | None:
    src = open(src_path)
    dst = open()

    pages = list(src.pages())
    page_count = src.page_count

    if page_count < 4:
        return "В документе должно быть хотя бы 4 страницы"

    left_rect = pages[-1].rect
    width = left_rect.x1 - left_rect.x0
    height = left_rect.y1 - left_rect.y0

    right_rect = Rect(left_rect)
    right_rect.x0 = width
    right_rect.x1 = width * 2

    order = []
    for i in range(page_count // 4):
        order.append((page_count - 1 - 2 * i, 2 * i))
        order.append((2 * i + 1, page_count - 2 - 2 * i))

    for i, (left_page, right_page) in enumerate(order):
        page = dst.new_page(width=width * 2, height=height)
        page.show_pdf_page(left_rect, src, left_page)
        page.show_pdf_page(right_rect, src, right_page)
        sleep(randint(0, 100) / 1000)
        if on_progress:
            print("progress", i / len(order))
            on_progress(i / len(order))

    dst.save(dst_path)
    dst.close()
    src.close()

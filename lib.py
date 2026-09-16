from base64 import b64encode
from json import dumps, loads
from pathlib import Path
from random import randint
from re import compile
from socket import create_connection
from time import monotonic, sleep
from typing import Callable

import win32con
import win32print
import win32ui
from PIL import Image, ImageWin
from pymupdf import Matrix, Rect, open


def flatten(
    src_path: str, dst_path: str, on_progress: Callable[[float], None] | None = None
) -> str | None:
    try:
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
            sleep(randint(0, 10) / 1000)
            if on_progress:
                print("progress", i / len(order))
                on_progress(i / len(order))

        dst.save(dst_path)
        dst.close()
        src.close()

    except Exception as e:
        return str(e)


def get_page(path: str) -> tuple[str, float, float]:
    src = open(path)
    page = src[10] if src.page_count > 10 else src[-1]
    pix = page.get_pixmap(matrix=Matrix(1, 1))
    return b64encode(pix.tobytes("png")).decode(), float(pix.width), float(pix.height)


def crop_pdf(
    src_path: str, dst_path: str, rel: tuple[float, float, float, float]
) -> str | None:
    x0, y0, x1, y1 = rel
    try:
        src = open(src_path)

        for page in src:
            r = page.rect
            box = Rect(
                r.x0 + r.width * x0,
                r.y0 + r.height * y0,
                r.x0 + r.width * x1,
                r.y0 + r.height * y1
            )
            page.set_cropbox(box)

        src.save(dst_path)
    except Exception as e:
        return str(e)


DPI = 200
SETTINGS = Path.home() / ".flattenpdf"
PROBE_PORTS = (9100, 631, 515)
PROBE_TTL = 15
IPV4 = compile(r"\d{1,3}(?:\.\d{1,3}){3}")

_reachable: dict[str, tuple[float, bool]] = {}

ERROR_FLAGS = (
    (win32print.PRINTER_STATUS_PAPER_JAM, "Замятие"),
    (win32print.PRINTER_STATUS_PAPER_OUT, "Нет бумаги"),
    (win32print.PRINTER_STATUS_OUT_OF_MEMORY, "Нет памяти"),
    (win32print.PRINTER_STATUS_DOOR_OPEN, "Крышка открыта"),
    (win32print.PRINTER_STATUS_USER_INTERVENTION, "Нужно вмешательство"),
    (win32print.PRINTER_STATUS_ERROR, "Ошибка"),
    (win32print.PRINTER_STATUS_NOT_AVAILABLE, "Недоступен")
)


def load_settings() -> dict:
    try:
        return loads((SETTINGS / "printers.json").read_text("utf-8"))
    except Exception:
        return {}


def save_settings(data: dict):
    SETTINGS.mkdir(parents=True, exist_ok=True)
    (SETTINGS / "printers.json").write_text(
        dumps(data, ensure_ascii=False, indent=2), "utf-8"
    )


def get_reversed(name: str) -> bool:
    return bool(load_settings().get(name, {}).get("reversed", False))


def set_reversed(name: str, value: bool):
    data = load_settings()
    data.setdefault(name, {})["reversed"] = value
    save_settings(data)


def _reach(port_name: str) -> bool | None:
    """TCP probe for network printers; None when the port is not an IP one."""
    match = IPV4.search(port_name or "")
    if not match:
        return None
    host = match.group(0)
    cached = _reachable.get(host)
    now = monotonic()
    if cached and now - cached[0] < PROBE_TTL:
        return cached[1]
    alive = False
    for port in PROBE_PORTS:
        try:
            with create_connection((host, port), timeout=0.4):
                alive = True
                break
        except OSError:
            continue
    _reachable[host] = (now, alive)
    return alive


def probe(name: str) -> dict:
    handle = win32print.OpenPrinter(name)
    try:
        info = win32print.GetPrinter(handle, 2)
        # level 6 is refreshed on each call, level 2 Status is cached by the spooler
        status = win32print.GetPrinter(handle, 6)["Status"]
        jobs = win32print.EnumJobs(handle, 0, -1, 1)
    finally:
        win32print.ClosePrinter(handle)

    offline = bool(
        status & win32print.PRINTER_STATUS_OFFLINE
        or info["Attributes"] & win32print.PRINTER_ATTRIBUTE_WORK_OFFLINE
    )
    if _reach(info.get("pPortName", "")) is False:
        offline = True

    error = next((text for flag, text in ERROR_FLAGS if status & flag), None)
    paused = bool(status & win32print.PRINTER_STATUS_PAUSED)
    busy = bool(jobs) or bool(
        status & (win32print.PRINTER_STATUS_PRINTING | win32print.PRINTER_STATUS_BUSY)
    )
    job = ""
    if jobs:
        first = jobs[0]
        job = f"{first['pDocument']} {first['PagesPrinted']}/{first['TotalPages']}"

    if offline:
        label = "Отключен"
    elif error:
        label = error
    elif paused:
        label = "Пауза"
    elif busy:
        label = "Печатает"
    else:
        label = "Готов"

    return {
        "name": name,
        "status": label,
        "job": job,
        "busy": busy,
        "paused": paused,
        "offline": offline,
        "error": bool(error) or offline,
        "reversed": get_reversed(name)
    }


def list_printers() -> list[dict]:
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    result = []
    for entry in win32print.EnumPrinters(flags, None, 1):
        if (
            entry[2] in ("Экспорт в WPS PDF", "Fax", "OneNote for Windows 10")
            or "Adobe" in entry[2]
            or "Microsoft" in entry[2]
        ):
            continue
        try:
            result.append(probe(entry[2]))
        except Exception:
            continue  # printer vanished or access denied
    return result


def toggle_printer(name: str, pause: bool) -> str | None:
    try:
        handle = win32print.OpenPrinter(
            name, {"DesiredAccess": win32print.PRINTER_ALL_ACCESS}
        )
        try:
            control = (
                win32print.PRINTER_CONTROL_PAUSE
                if pause
                else win32print.PRINTER_CONTROL_RESUME
            )
            win32print.SetPrinter(handle, 0, None, control)
        finally:
            win32print.ClosePrinter(handle)
    except Exception as err:
        return str(err)
    return None


def page_indexes(path: str, even: bool, printer: str) -> list[int]:
    with open(path) as doc:
        count = doc.page_count
    indexes = [i for i in range(count) if (i % 2 == 1) == even]
    if even and get_reversed(printer):
        indexes.reverse()
    return indexes


def print_pages(printer: str, path: str, indexes: list[int], title: str) -> str | None:
    """Rasterize selected pages and send them to the printer DC."""
    dc = None
    try:
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(printer)
        area_w = dc.GetDeviceCaps(win32con.HORZRES)
        area_h = dc.GetDeviceCaps(win32con.VERTRES)
        dc.StartDoc(title)
        zoom = DPI / 72
        with open(path) as doc:
            for index in indexes:
                pix = doc[index].get_pixmap(matrix=Matrix(zoom, zoom))
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                scale = min(area_w / img.width, area_h / img.height)
                w, h = int(img.width * scale), int(img.height * scale)
                x, y = (area_w - w) // 2, (area_h - h) // 2
                dc.StartPage()
                ImageWin.Dib(img).draw(dc.GetHandleOutput(), (x, y, x + w, y + h))
                dc.EndPage()
        dc.EndDoc()
    except Exception as err:
        return str(err)
    finally:
        if dc:
            dc.DeleteDC()
    return None

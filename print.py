from asyncio import sleep, to_thread
from functools import partial

from flet import (
    AlertDialog,
    Checkbox,
    Colors,
    Column,
    Control,
    CrossAxisAlignment,
    DataCell,
    DataColumn,
    DataRow,
    DataTable,
    Event,
    FilePicker,
    IconButton,
    Icons,
    MainAxisAlignment,
    Row,
    ScrollMode,
    SnackBar,
    Text,
    TextAlign,
    TextButton
)

from lib import list_printers, page_indexes, print_pages, set_reversed, toggle_printer

POLL = 2


class PrintPage(Column):
    def __init__(self):
        super().__init__()
        self.pdf_path = None
        self.polling = False
        self.printers: list[dict] = []
        self.stage: dict[str, str] = {}  # "" | odd | even_ready | even
        self.file_text = Text(visible=False, text_align=TextAlign.CENTER, size=12)
        self.table = DataTable(
            columns=[
                DataColumn(label=Text("Принтер")),
                DataColumn(label=Text("Статус")),
                DataColumn(label=Text("Задание")),
                DataColumn(label=Text(""))
            ],
            rows=[],
            column_spacing=10,
            heading_row_height=34,
            data_row_max_height=46
        )
        self.controls = [
            Row(
                [
                    TextButton("Печать", icon=Icons.PRINT, on_click=self.dispatch),
                    IconButton(icon=Icons.REFRESH, on_click=self.refresh)
                ],
                alignment=MainAxisAlignment.CENTER
            ),
            self.file_text,
            Column([self.table], scroll=ScrollMode.AUTO, expand=True)
        ]
        self.alignment = MainAxisAlignment.START
        self.horizontal_alignment = CrossAxisAlignment.CENTER
        self.expand = True

    def did_mount(self):
        if not self.polling:
            self.polling = True
            self.page.run_task(self.poll)

    def will_unmount(self):
        self.polling = False

    async def poll(self):
        while self.polling:
            try:
                await self.reload()
            except Exception as err:
                print(f"poll failed: {err}")  # keep the loop alive on transient errors
            await sleep(POLL)

    async def refresh(self, e: Event[IconButton]):
        await self.reload()

    async def reload(self):
        self.printers = await to_thread(list_printers)
        for printer in self.printers:
            name = printer["name"]
            stage = self.stage.get(name, "")
            # the job leaves the queue once spooled, treat that as finished
            if stage == "odd" and not printer["busy"]:
                self.stage[name] = "even_ready"
            elif stage == "even" and not printer["busy"]:
                self.stage[name] = ""
        self.build_rows()
        if self.page:
            self.update()

    def status_text(self, printer: dict) -> str:
        stage = self.stage.get(printer["name"], "")
        if printer["error"] or printer["paused"]:
            return printer["status"]
        if stage == "odd":
            return "Печать нечётных"
        if stage == "even":
            return "Печать чётных"
        if stage == "even_ready":
            return "Ждёт переворота"
        return printer["status"]

    def build_rows(self):
        rows = []
        for printer in self.printers:
            name = printer["name"]
            stage = self.stage.get(name, "")
            actions: list[Control] = []
            if printer["busy"] or printer["paused"]:
                actions.append(
                    IconButton(
                        icon=Icons.PLAY_ARROW if printer["paused"] else Icons.PAUSE,
                        tooltip="Возобновить" if printer["paused"] else "Остановить",
                        on_click=partial(
                            self.toggle, name=name, pause=not printer["paused"]
                        )
                    )
                )
            if stage == "even_ready":
                actions.append(
                    IconButton(
                        icon=Icons.FLIP_TO_BACK,
                        tooltip="Печать чётных — переложите стопку",
                        on_click=partial(self.print_even, name=name)
                    )
                )
            actions.append(
                IconButton(
                    icon=Icons.SWAP_VERT,
                    tooltip="Обратный порядок чётных",
                    selected=printer["reversed"],
                    selected_icon_color=Colors.PRIMARY,
                    on_click=partial(
                        self.flip_order, name=name, value=not printer["reversed"]
                    )
                )
            )
            rows.append(
                DataRow(
                    cells=[
                        DataCell(Text(name, max_lines=2, size=12)),
                        DataCell(
                            Text(
                                self.status_text(printer),
                                size=12,
                                color=Colors.ERROR if printer["error"] else None
                            )
                        ),
                        DataCell(Text(printer["job"] or "—", size=12, max_lines=1)),
                        DataCell(Row(actions, spacing=0, tight=True))
                    ]
                )
            )
        self.table.rows = rows

    def flip_order(self, e: Event[IconButton], name: str, value: bool):
        set_reversed(name, value)
        for printer in self.printers:
            if printer["name"] == name:
                printer["reversed"] = value
        self.build_rows()
        self.update()

    async def toggle(self, e: Event[IconButton], name: str, pause: bool):
        res = await to_thread(toggle_printer, name, pause)
        if res:
            self.notify(res, Colors.ERROR)
        await self.reload()

    async def dispatch(self, e: Event[TextButton]):
        file = await FilePicker().pick_files(allowed_extensions=["pdf"])
        if not file or not file[0].path:
            self.notify("Выбор отменен", Colors.ERROR)
            return
        self.pdf_path = file[0].path
        self.file_text.value = f"Файл: {file[0].name}"
        self.file_text.visible = True
        await self.reload()

        boxes = [
            Checkbox(label=p["name"], value=not p["busy"], disabled=p["error"])
            for p in self.printers
        ]
        if not boxes:
            self.notify("Принтеры не найдены", Colors.ERROR)
            return
        dialog = AlertDialog(
            title=Text("Выберите принтеры"),
            content=Column(boxes, scroll=ScrollMode.AUTO, height=260, tight=True),  # ty: ignore
            actions=[
                TextButton("Отмена", on_click=lambda _: self.page.pop_dialog()),
                TextButton("Печать", on_click=partial(self.start, boxes=boxes))
            ]
        )
        self.page.show_dialog(dialog)

    def start(self, e: Event[TextButton], boxes: list[Checkbox]):
        self.page.pop_dialog()
        chosen = [box.label for box in boxes if box.value]
        if not chosen:
            self.notify("Принтеры не выбраны", Colors.ERROR)
            return
        for name in chosen:
            assert isinstance(name, str)
            self.stage[name] = "odd"
            self.page.run_task(self.send, name, False)
        self.build_rows()
        self.update()
        self.notify(f"Задания отправлены: {len(chosen)}", Colors.PRIMARY)

    def print_even(self, e: Event[IconButton], name: str):
        self.stage[name] = "even"
        self.page.run_task(self.send, name, True)
        self.build_rows()
        self.update()

    async def send(self, name: str, even: bool):
        assert self.pdf_path
        indexes = await to_thread(page_indexes, self.pdf_path, even, name)
        if not indexes:
            self.stage[name] = ""
            self.notify(f"{name}: нет страниц", Colors.ERROR)
            return
        label = "Чётные" if even else "Нечётные"
        res = await to_thread(
            print_pages, name, self.pdf_path, indexes, f"{label} — {name}"
        )
        if res:
            self.stage[name] = ""
            self.notify(f"{name}: {res}", Colors.ERROR)
        await self.reload()

    def notify(self, text: str, color: str):
        self.page.show_dialog(
            SnackBar(Text(text, color=color), bgcolor=Colors.SURFACE_CONTAINER)
        )

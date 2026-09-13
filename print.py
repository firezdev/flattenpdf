from asyncio import sleep, to_thread
from functools import partial

from flet import (
    Button,
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
    Icons,
    MainAxisAlignment,
    Row,
    ScrollMode,
    SnackBar,
    Text,
    TextAlign
)

from lib import list_printers, page_indexes, print_pages, toggle_printer

POLL = 2


class PrintPage(Column):
    def __init__(self):
        super().__init__()
        self.pdf_path = None
        self.polling = False
        self.printers: list[dict] = []
        self.stage: dict[str, str] = {}  # "" | odd | even_ready | even
        self.file_text = Text(visible=False, text_align=TextAlign.CENTER)
        self.table = DataTable(
            columns=[
                DataColumn(label=Text("Принтер")),
                DataColumn(label=Text("Статус")),
                DataColumn(label=Text("Задание")),
                DataColumn(label=Text(""))
            ],
            rows=[],
            column_spacing=12,
            heading_row_height=36,
            data_row_max_height=44
        )
        self.controls = [
            Row(
                [
                    Button("Печать на все", on_click=self.dispatch),
                    Button(icon=Icons.REFRESH, on_click=self.refresh)
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
        self.polling = True
        self.page.run_task(self.poll)

    def will_unmount(self):
        self.polling = False

    async def poll(self):
        while self.polling:
            await self.reload()
            await sleep(POLL)

    async def refresh(self, e: Event[Button]):
        await self.reload()

    async def reload(self):
        self.printers = await to_thread(list_printers)
        for printer in self.printers:
            name = printer["name"]
            stage = self.stage.get(name, "")
            # a job leaves the queue once spooled, treat that as finished
            if stage == "odd" and not printer["busy"]:
                self.stage[name] = "even_ready"
            elif stage == "even" and not printer["busy"]:
                self.stage[name] = ""
        self.build_rows()
        if self.page:
            self.update()

    def build_rows(self):
        rows = []
        for printer in self.printers:
            name = printer["name"]
            stage = self.stage.get(name, "")
            actions: list[Control] = [
                Button(
                    icon=Icons.PLAY_ARROW if printer["paused"] else Icons.PAUSE,
                    tooltip="Возобновить" if printer["paused"] else "Остановить",
                    on_click=partial(
                        self.toggle, name=name, pause=not printer["paused"]
                    )
                )
            ]
            if stage == "even_ready":
                actions.append(
                    Button(
                        "Чётные",
                        tooltip="Переложите нечётные страницы другой стороной",
                        on_click=partial(self.print_even, name=name)
                    )
                )
            rows.append(
                DataRow(
                    cells=[
                        DataCell(Text(name, max_lines=2, size=12)),
                        DataCell(
                            Text(
                                printer["status"],
                                size=12,
                                color=Colors.ERROR if printer["error"] else None
                            )
                        ),
                        DataCell(Text(printer["job"] or "—", size=12)),
                        DataCell(Row(actions, spacing=0))
                    ]
                )
            )
        self.table.rows = rows

    async def toggle(self, e: Event[Button], name: str, pause: bool):
        res = await to_thread(toggle_printer, name, pause)
        if res:
            self.notify(res, Colors.ERROR)
        await self.reload()

    async def dispatch(self, e: Event[Button]):
        file = await FilePicker().pick_files(allowed_extensions=["pdf"])
        if not file or not file[0].path:
            self.notify("Выбор отменен", Colors.ERROR)
            return
        self.pdf_path = file[0].path
        self.file_text.value = f"Файл: {file[0].name}"
        self.file_text.visible = True
        await self.reload()
        free = [
            p["name"]
            for p in self.printers
            if not p["busy"] and not p["paused"] and not p["error"]
        ]
        if not free:
            self.notify("Нет свободных принтеров", Colors.ERROR)
            return
        for name in free:
            self.stage[name] = "odd"
            self.page.run_task(self.send, name, False)
        self.build_rows()
        self.update()
        self.notify(f"Задания отправлены: {len(free)}", Colors.PRIMARY)

    def print_even(self, e: Event[Button], name: str):
        self.stage[name] = "even"
        self.page.run_task(self.send, name, True)
        self.build_rows()
        self.update()

    async def send(self, name: str, even: bool):
        assert self.pdf_path
        indexes = await to_thread(page_indexes, self.pdf_path, even)
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

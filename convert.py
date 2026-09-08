from asyncio import to_thread
from shutil import move

from flet import (
    Button,
    Colors,
    Column,
    CrossAxisAlignment,
    Event,
    FilePicker,
    MainAxisAlignment,
    ProgressBar,
    SnackBar,
    Text,
    TextAlign
)

from lib import flatten


class ConvertPage(Column):
    def __init__(self):
        super().__init__()
        self.selected_file = None
        self.selected_text = Text(visible=False, text_align=TextAlign.CENTER)
        self.saved_text = Text(visible=False, text_align=TextAlign.CENTER)

        self.save_control = Column(
            [
                Text("Выберите путь для сохранения PDF"),
                self.saved_text,
                Button("Сохранить", on_click=self.save)
            ],
            visible=False,
            alignment=MainAxisAlignment.CENTER,
            horizontal_alignment=CrossAxisAlignment.CENTER
        )
        self.bar = ProgressBar(width=350, value=0)

        self.controls = [
            Text("Выберите PDF для конвертации"),
            self.selected_text,
            Button("Выбрать", on_click=self.pick),
            self.bar,
            self.save_control
        ]
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER

    async def save(self, e: Event[Button]):
        file = await FilePicker().save_file(
            file_name=self.selected_file, allowed_extensions=["pdf"]
        )
        if file:
            move("temp.pdf", file)
            self.saved_text.value = f"Сохранено: {file.rsplit('/', maxsplit=1)[-1]}"
            self.saved_text.visible = True
            self.update()
            self.page.show_dialog(
                SnackBar(Text("Файл сохранен", color=Colors.GREEN), bgcolor="#111111")
            )
        else:
            self.page.show_dialog(
                SnackBar(
                    Text("Выбор отменен", color=Colors.ERROR),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

    async def _on_progress(self, value: float):
        self.bar.value = value
        self.page.update()

    async def pick(self, e: Event[Button]):
        file = await FilePicker().pick_files(allowed_extensions=["pdf"])
        if file and file[0].path:
            self.selected_file = file[0].name
            self.bar.value = 0
            self.selected_text.visible = True
            self.selected_text.value = f"Выбрано: {self.selected_file}"
            self.saved_text.visible = False
            self.page.update()

            self.page.show_dialog(
                SnackBar(
                    Text("Конвертация..", color=Colors.PRIMARY),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

            def on_progress(value: float):
                self.page.run_task(self._on_progress, value)

            res = await to_thread(flatten, file[0].path, "temp.pdf", on_progress)
            await self._on_progress(1)
            if res:
                self.bar.visible = False
                self.update()
                self.page.show_dialog(
                    SnackBar(
                        Text(res, color=Colors.ERROR), bgcolor=Colors.SURFACE_CONTAINER
                    )
                )
                return

            self.page.show_dialog(
                SnackBar(
                    Text("Файл конвертирован", color=Colors.GREEN),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )
            self.save_control.visible = True
            self.page.update()
        else:
            self.page.show_dialog(
                SnackBar(
                    Text("Выбор отменен", color=Colors.ERROR),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

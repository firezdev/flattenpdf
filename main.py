from asyncio import to_thread
from shutil import move

from flet import (
    Alignment,
    Button,
    Colors,
    Column,
    Container,
    CrossAxisAlignment,
    Event,
    FilePicker,
    MainAxisAlignment,
    Page,
    ProgressBar,
    SnackBar,
    Text,
    run
)

from lib import flatten


def main(page: Page):
    selected_file = None

    async def handle_save(e: Event[Button]):
        file = await FilePicker().save_file(
            file_name=selected_file, allowed_extensions=["pdf"]
        )
        if file:
            move("temp.pdf", file)
            page.show_dialog(
                SnackBar(Text("Файл сохранен", color=Colors.GREEN), bgcolor="#111111")
            )
        else:
            page.show_dialog(
                SnackBar(
                    Text("Выбор отменен", color=Colors.ERROR),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

    save_control = Column(
        [
            Text("Выберите путь для сохранения PDF"),
            Button("Сохранить", on_click=handle_save)
        ],
        visible=False,
        alignment=MainAxisAlignment.CENTER,
        horizontal_alignment=CrossAxisAlignment.CENTER
    )
    bar = ProgressBar(width=350, value=0, visible=False)

    async def handle_pick(e: Event[Button]):
        nonlocal save_control, selected_file

        file = await FilePicker().pick_files(allowed_extensions=["pdf"])
        if file and file[0].path:
            page.show_dialog(
                SnackBar(
                    Text("Конвертация..", color=Colors.PRIMARY),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

            def on_progress(value: float):
                bar.value = value
                page.update()

            bar.visible = True
            await to_thread(flatten, file[0].path, "temp.pdf", on_progress)

            page.show_dialog(
                SnackBar(
                    Text("Файл конвертирован", color=Colors.GREEN),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )
            save_control.visible = True
            bar.visible = False
            page.update()
        else:
            page.show_dialog(
                SnackBar(
                    Text("Выбор отменен", color=Colors.ERROR),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

    page.window.width = 400
    page.window.height = 500
    page.window.min_width = 400
    page.window.max_width = 400
    page.window.min_height = 500
    page.window.max_height = 500
    page.title = "PDF конвертер"
    page.add(
        Container(
            Column(
                [
                    Text("Выберите PDF для конвертации"),
                    Button("Выбрать", on_click=handle_pick),
                    bar,
                    save_control
                ],
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER
            ),
            expand=True,
            alignment=Alignment.CENTER
        )
    )


run(main)

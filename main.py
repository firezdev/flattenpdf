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
    TextAlign,
    run
)

from lib import flatten


def main(page: Page):
    selected_file = None
    selected_text = Text(visible=False, text_align=TextAlign.CENTER)
    saved_text = Text(visible=False, text_align=TextAlign.CENTER)

    async def handle_save(e: Event[Button]):
        file = await FilePicker().save_file(
            file_name=selected_file, allowed_extensions=["pdf"]
        )
        if file:
            move("temp.pdf", file)
            saved_text.value = f"Сохранено: {file.rsplit('/', maxsplit=1)[-1]}"
            saved_text.visible = True
            page.update()
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
            saved_text,
            Button("Сохранить", on_click=handle_save)
        ],
        visible=False,
        alignment=MainAxisAlignment.CENTER,
        horizontal_alignment=CrossAxisAlignment.CENTER
    )
    bar = ProgressBar(width=350, value=0)

    async def handle_pick(e: Event[Button]):
        nonlocal save_control, selected_file

        file = await FilePicker().pick_files(allowed_extensions=["pdf"])
        if file and file[0].path:
            selected_file = file[0].name
            bar.value = 0
            selected_text.visible = True
            selected_text.value = f"Выбрано: {selected_file}"
            saved_text.visible = False
            page.update()

            page.show_dialog(
                SnackBar(
                    Text("Конвертация..", color=Colors.PRIMARY),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

            async def _on_progress(value: float):
                bar.value = value
                page.update()

            def on_progress(value: float):
                page.run_task(_on_progress, value)

            res = await to_thread(flatten, file[0].path, "temp.pdf", on_progress)
            await _on_progress(1)
            if res:
                bar.visible = False
                page.update()
                page.show_dialog(
                    SnackBar(
                        Text(res, color=Colors.ERROR), bgcolor=Colors.SURFACE_CONTAINER
                    )
                )
                return

            page.show_dialog(
                SnackBar(
                    Text("Файл конвертирован", color=Colors.GREEN),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )
            save_control.visible = True
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
                    selected_text,
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

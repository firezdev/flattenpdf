from asyncio import to_thread
from functools import partial
from shutil import move

from flet import (
    Border,
    Button,
    Colors,
    Column,
    Container,
    CrossAxisAlignment,
    DragUpdateEvent,
    Event,
    FilePicker,
    GestureDetector,
    Image,
    MainAxisAlignment,
    SnackBar,
    Stack,
    Text,
    TextAlign
)

from lib import crop_pdf, get_page

LEFT = ("tl", "bl")
TOP = ("tl", "tr")


class CropPage(Column):
    def __init__(self):
        super().__init__()
        self.selected_file = None
        self.ratio = 297 / 210
        self.img_w = self.img_h = 0.0
        self.x = self.y = self.w = self.h = 0.0
        self.selected_text = Text(visible=False, text_align=TextAlign.CENTER)
        self.saved_text = Text(visible=False, text_align=TextAlign.CENTER)
        self.preview = Image("")
        self.frame = GestureDetector(
            on_pan_update=self.move_frame,
            content=Container(
                border=Border.all(2, Colors.BLUE),
                bgcolor=Colors.with_opacity(0.1, Colors.BLUE)
            )
        )
        self.handles = {
            name: GestureDetector(
                on_pan_update=partial(self.resize_frame, corner=name),
                content=Container(width=10, height=10, bgcolor=Colors.BLUE)
            )
            for name in ("tl", "tr", "bl", "br")
        }
        self.stack = Stack([self.preview, self.frame, *self.handles.values()])
        self.save_control = Column(
            [
                self.stack,
                Text("Выберите путь для сохранения PDF"),
                self.saved_text,
                Button("Сохранить", on_click=self.save)
            ],
            visible=False,
            alignment=MainAxisAlignment.CENTER,
            horizontal_alignment=CrossAxisAlignment.CENTER
        )
        self.controls = [
            Text("Выберите PDF для обрезки"),
            self.selected_text,
            Button("Выбрать", on_click=self.pick),
            self.save_control
        ]
        self.alignment = MainAxisAlignment.CENTER
        self.horizontal_alignment = CrossAxisAlignment.CENTER

    def apply_frame(self):
        """Clamp frame to the page and sync control geometry."""
        self.w = max(40, min(self.w, self.img_w, self.img_h / self.ratio))
        self.h = self.w * self.ratio
        self.x = min(max(0.0, self.x), self.img_w - self.w)
        self.y = min(max(0.0, self.y), self.img_h - self.h)
        self.frame.left, self.frame.top = self.x, self.y
        self.frame.width, self.frame.height = self.w, self.h
        for name, handle in self.handles.items():
            handle.left = (self.x if name in LEFT else self.x + self.w) - 5
            handle.top = (self.y if name in TOP else self.y + self.h) - 5

    def move_frame(self, e: DragUpdateEvent[GestureDetector]):
        assert e.local_delta
        self.x += e.local_delta.x
        self.y += e.local_delta.y
        self.apply_frame()
        self.update()

    def resize_frame(self, e: DragUpdateEvent[GestureDetector], corner: str):
        # width drives height, opposite corner stays anchored
        assert e.local_delta
        right, bottom = self.x + self.w, self.y + self.h
        dx = -e.local_delta.x if corner in LEFT else e.local_delta.x
        limit_x = right if corner in LEFT else self.img_w - self.x
        limit_y = bottom if corner in TOP else self.img_h - self.y
        self.w = max(40, min(self.w + dx, limit_x, limit_y / self.ratio))
        self.h = self.w * self.ratio
        if corner in LEFT:
            self.x = right - self.w
        if corner in TOP:
            self.y = bottom - self.h
        self.apply_frame()
        self.update()

    def reset_frame(self):
        self.w = min(self.img_w, self.img_h / self.ratio) * 0.9
        self.h = self.w * self.ratio
        self.x = (self.img_w - self.w) / 2
        self.y = (self.img_h - self.h) / 2
        self.apply_frame()

    async def pick(self, e: Event[Button]):
        file = await FilePicker().pick_files(allowed_extensions=["pdf"])
        if file and file[0].path:
            self.selected_file = file[0]
            assert self.selected_file.path
            self.selected_text.visible = True
            self.selected_text.value = f"Выбрано: {self.selected_file.name}"
            self.saved_text.visible = False
            self.page.update()
            b64, raw_w, raw_h = await to_thread(get_page, self.selected_file.path)
            aspect = raw_h / raw_w
            self.img_w = 500 / aspect
            self.img_h = self.img_w * aspect
            self.preview.src = b64
            self.preview.width = self.img_w
            self.preview.height = self.img_h
            self.stack.width = self.img_w
            self.stack.height = self.img_h
            self.reset_frame()
            self.save_control.visible = True
            self.page.update()
        else:
            self.page.show_dialog(
                SnackBar(
                    Text("Выбор отменен", color=Colors.ERROR),
                    bgcolor=Colors.SURFACE_CONTAINER
                )
            )

    async def save(self, e: Event[Button]):
        assert self.selected_file
        assert self.selected_file.path
        file = await FilePicker().save_file(
            file_name=self.selected_file.name, allowed_extensions=["pdf"]
        )
        if file:
            rel = (
                self.x / self.img_w,
                self.y / self.img_h,
                (self.x + self.w) / self.img_w,
                (self.y + self.h) / self.img_h
            )
            res = await to_thread(crop_pdf, self.selected_file.path, "temp.pdf", rel)
            if res:
                self.page.show_dialog(
                    SnackBar(
                        Text(res, color=Colors.ERROR), bgcolor=Colors.SURFACE_CONTAINER
                    )
                )
                return
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

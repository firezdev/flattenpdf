from flet import Alignment, Column, Container, Page, Tab, TabBar, TabBarView, Tabs, run

from convert import ConvertPage
from crop import CropPage
from print import PrintPage


def main(page: Page):
    page.window.width = 600
    page.window.height = 800
    page.window.min_width = 600
    page.window.max_width = 600
    page.window.min_height = 800
    page.window.max_height = 800
    page.title = "PDF конвертер"

    page.add(
        Container(
            Tabs(
                length=3,
                expand=True,
                content=Column(
                    [
                        TabBar([Tab("Конвертация"), Tab("Обрезка"), Tab("Печать")]),
                        TabBarView(
                            [ConvertPage(), CropPage(), PrintPage()], expand=True
                        )
                    ],
                    expand=True
                )
            ),
            expand=True,
            alignment=Alignment.CENTER
        )
    )


run(main)

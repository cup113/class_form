Color = tuple[int, int, int]


def color_to_hex(color: Color) -> str:
    return "#{0:02x}{1:02x}{2:02x}".format(color[0], color[1], color[2])


def hex_to_color(color: str) -> Color:
    color = color.lstrip('#')
    return (
        int(color[0:2], 16),
        int(color[2:4], 16),
        int(color[4:6], 16),
    )


class ColorTheme:
    def __init__(self, source: dict[str, str]) -> None:
        self.bg_tuple = hex_to_color(source["背景"])
        self.fg_tuple = hex_to_color(source["文字"])
        self.hint_tuple = hex_to_color(source["提示"])
        self.hover_tuple = hex_to_color(source["悬停"])

    def __repr__(self) -> str:
        return f"{{bg: {self.bg}, fg: {self.fg}, hint: {self.hint}, hover: {self.hover}}}"

    @property
    def bg(self):
        return color_to_hex(self.bg_tuple)

    @property
    def fg(self):
        return color_to_hex(self.fg_tuple)

    @property
    def hint(self):
        return color_to_hex(self.hint_tuple)

    @property
    def hover(self):
        return color_to_hex(self.hover_tuple)

    def gradient(self, ratio: float) -> str:
        """"""
        return color_to_hex((
            int(self.fg_tuple[0] * ratio + self.hint_tuple[0] * (1 - ratio)),
            int(self.fg_tuple[1] * ratio + self.hint_tuple[1] * (1 - ratio)),
            int(self.fg_tuple[2] * ratio + self.hint_tuple[2] * (1 - ratio))
        ))

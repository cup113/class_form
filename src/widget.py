from typing import Callable, Any
from tkinter import Tk, Misc, Label

from states import State
from clock import Clock

AnimationState = tuple[int, int, int, int]  # width height x y


def color_to_hex(color: tuple[int, int, int]) -> str:
    return "#{0:02x}{1:02x}{2:02x}".format(color[0], color[1], color[2])


class Window(Tk):
    """Base Class Customized for this application."""
    ANIMATION_FRAME_MS = 20
    X_PADDING = 10
    Y_PADDING = 5

    def _ease_in_out(self, x: float) -> float:
        """Smoothing function [0, 1] -> [0, 1] whose derivatives at 0.0 and 1.0 are both 0."""
        # return -2.0 * x ** 3 + 3.0 * x ** 2
        return 1.0 / (1.0 + 3.0 ** (3.0 - 6.0 * x)) * (14.0 / 13.0) - (1.0 / 28.0)

    def set_topmost(self, value: bool):
        self.attributes('-topmost', value) # type: ignore

    def geometry_state(self, state: AnimationState):
        """Wrapper of Tk.geometry() and update automatically."""
        self.geometry(f"{state[0]}x{state[1]}+{state[2]}+{state[3]}")
        self.update()

    def animate(self, target: AnimationState, duration_ms: int) -> None:
        """Smoothly move and scale the window (blocked)."""

        clock = Clock(self.ANIMATION_FRAME_MS / 1000)

        frame_total = duration_ms // self.ANIMATION_FRAME_MS
        current: AnimationState = (
            self.winfo_width(), self.winfo_height(),
            self.winfo_x(), self.winfo_y()
        )

        def calc(frame: int, item_index: int) -> int:
            ratio = frame / frame_total
            progress = self._ease_in_out(ratio)
            return max(int(
                current[item_index] * (1 - progress) +
                target[item_index] * progress + 0.5
            ), 0)

        frames: list[AnimationState] = [
            (calc(a, 0), calc(a, 1), calc(a, 2), calc(a, 3))
            for a in range(1, frame_total + 1)
        ]
        for frame in frames:
            self.geometry_state(frame)
            clock.wait()

    def __init__(self, state: State) -> None:
        super().__init__()
        self.state = state
        self.attributes("-alpha", state.alpha)  # type: ignore
        self.overrideredirect(True)
        self.config(bg=state.color_theme.bg)
        self.set_topmost(True)


class ClickableLabel(Label):
    """Customized Tk.Label bound to command when initialized."""

    def __init__(self, master: Misc, text: str, font: tuple[str, int], command: Callable[[Any], Any], state: State):
        super().__init__(master, text=text, fg=state.color_theme.fg,
                         bg=state.color_theme.bg, font=font)
        self.bind("<Double-Button-1>", command)
        self.bind("<Enter>", self.change_color)
        self.bind("<Leave>", self.change_color)
        self.color_theme = state.color_theme

    def change_color(self, _: Any = None):
        if self['bg'] != self.color_theme.bg:
            self['bg'] = self.color_theme.bg
        else:
            self['bg'] = self.color_theme.hover

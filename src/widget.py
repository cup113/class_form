from typing import Callable, Any, Optional, TypeVar, Generic
from tkinter import Tk, Misc, Label
from logging import info

from states import State
from clock import Clock

AnimationState = tuple[int, int, int, int]  # width height x y
T = TypeVar('T')


class Window(Tk):
    """Base Class Customized for this application."""
    ANIMATION_FRAME_MS = 20
    TITLE = "Class Form"

    def _ease_in_out(self, x: float) -> float:
        """Smoothing function [0, 1] -> [0, 1] whose derivatives at 0.0 and 1.0 are both 0."""
        # return -2.0 * x ** 3 + 3.0 * x ** 2
        return 1.0 / (1.0 + 3.0 ** (3.0 - 6.0 * x)) * (14.0 / 13.0) - (1.0 / 28.0)

    def set_topmost(self, value: bool):
        self.attributes('-topmost', value)  # type: ignore

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
        super().__init__(self.TITLE, self.TITLE, self.TITLE)
        self.st = state
        self.attributes("-alpha", state.alpha)  # type: ignore
        self.overrideredirect(True)
        self.config(bg=state.color_theme.bg)
        self.set_topmost(True)


class EditWindow(Tk, Generic[T]):
    """A one-off, blocked window to edit something."""

    TITLE = ""
    LOGGING_NAME = ""

    def __init__(self) -> None:
        super().__init__(self.TITLE, self.TITLE, self.TITLE)
        self.attributes('-topmost', True)  # type: ignore
        self.changed = False

    def ok(self) -> None:
        info(self.LOGGING_NAME + " Edit Window Terminated")
        self.changed = True
        self.destroy()

    def destroy(self) -> None:
        super().destroy()
        self.quit()

    def final_value(self) -> T:
        raise NotImplementedError(
            "final_value() isn't implemented in EditWindow class.")

    def run(self) -> Optional[T]:
        """Get the result of editing in the form of one-day raw schedule."""
        self.mainloop()
        if self.changed:
            return self.final_value()


class ClickableLabel(Label):
    """Customized Tk.Label bound to command when initialized."""

    def __init__(self, master: Misc, text: str, font: tuple[str, int], command: Callable[[Any], Any], state: State):
        super().__init__(master, text=text, fg=state.color_theme.fg,
                         bg=state.color_theme.bg, font=font)
        self.bind("<Double-Button-1>", command)
        self.bind("<Enter>", self.activate_color)
        self.bind("<Leave>", self.deactivate_color)
        self.color_theme = state.color_theme

    def activate_color(self, _: Any = None):
        self['bg'] = self.color_theme.hover

    def deactivate_color(self, _: Any = None):
        self['bg'] = self.color_theme.bg

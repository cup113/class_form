from typing import Any, Optional, Literal, Union
from widget import ClickableLabel, Window, EditWindow
from logging import info
from enum import Enum
from tkinter import Widget, Misc, Label, Button, Frame, Entry, Checkbutton
from tkinter import StringVar, BooleanVar, messagebox

from states import LessonState, State


def to_cn_weekday(weekday: int):
    return "周" + "一二三四五六日"[weekday]


class LessonLine:
    HINT_EMPTY = "<空>"
    HINT_CONTINUE = "<连下一节>"

    def __init__(self, master: Misc, name: str, period: str, has_sep: bool, sep: str, font: tuple[str, int]):
        frame = Frame(master)
        self.var_lesson = StringVar(frame, name)
        self.var_hint = StringVar(frame, "")
        self.var_sep = BooleanVar(frame, has_sep)
        self.entry = Entry(
            frame, textvariable=self.var_lesson, font=font, width=4)
        self.sep = sep
        time_label = Label(frame, text=period, font=font)
        hint_label = Label(frame, textvariable=self.var_hint,
                           font=font, width=12)
        checkbox = Checkbutton(frame, text="分隔", variable=self.var_sep)

        time_label.pack(side='left')
        self.entry.pack(side='left')
        checkbox.pack(side='right')
        hint_label.pack(side='right')
        frame.pack(side='top', fill='x')

        self.var_lesson.trace_add('write', self.change_lesson)
        self.change_lesson()

    def change_lesson(self, *args: Any):
        lesson = self.var_lesson.get()
        if lesson == self.sep:
            self.var_lesson.set("")
            self.var_sep.set(True)
        elif lesson == "":
            self.var_hint.set(self.HINT_EMPTY)
        elif lesson == '~':
            self.var_hint.set(self.HINT_CONTINUE)
        else:
            self.var_hint.set("")


class LessonsEditWindow(EditWindow[list[str]]):
    """A one-off, blocked window to edit the schedule today."""

    TITLE = "换课"
    LOGGING_NAME = "Lessons"

    def __init__(self, state: State) -> None:
        super().__init__()
        self.lines: list[LessonLine] = []
        font = (state.font[0], state.font[1] // 2)
        lessons = state.today_schedule()
        timetable = state.raw_timetable
        i = 0
        for period in timetable:
            if i < len(lessons):
                lesson = lessons[i]
            else:
                lesson = ""
            has_sep = False
            i += 1
            if i < len(lessons) and lessons[i] == state.separator:
                i += 1
                has_sep = True
            self.lines.append(LessonLine(
                self, lesson, period, has_sep, state.separator, font))
        Button(self, text="确认", font=font, command=self.ok).pack(side='top')

    def final_value(self) -> list[str]:
        result: list[str] = []
        for line in self.lines:
            result.append(line.var_lesson.get())
            if line.var_sep.get():
                result.append(line.sep)
        return result


class WeekdayEditWindow(EditWindow[int]):
    """A one-off, blocked window to edit the weekday today."""

    TITLE = "更改星期"
    LOGGING_NAME = "Weekday Edit"

    def __init__(self, state: State) -> None:
        super().__init__()
        self.result = 0
        font = (state.font[0], state.font[1] // 2)
        for i in range(7):
            def command():
                weekday = i

                def inner():
                    self.result = weekday
                    self.ok()
                return inner
            frame = Frame(self)
            frame.pack(side='top', fill='x')
            text = "{0} ({1})".format(
                to_cn_weekday(i),
                " ".join(state.raw_schedule[i])
            )
            Button(frame, text=text, font=font, command=command()).pack()

    def final_value(self) -> int:
        return self.result


class MainPollEnum(Enum):
    """State sent to dispatching center."""
    ShutDown = 0
    ClassAdvance = 1
    HideTemporarily = 2
    Resize = 3
    ChangeClass = 4
    ChangeWeekday = 5


MainPollResult = Union[
    tuple[Literal[MainPollEnum.ShutDown]],
    tuple[Literal[MainPollEnum.ClassAdvance],
          Union[Literal['on'], Literal['off']]],
    tuple[Literal[MainPollEnum.HideTemporarily]],
    tuple[Literal[MainPollEnum.Resize], int],
    tuple[Literal[MainPollEnum.ChangeClass]],
    tuple[Literal[MainPollEnum.ChangeWeekday]],
]

WillClassAdvance = Optional[Union[Literal['on'], Literal['off']]]
WillLoadResize = Optional[int]


class MainWindow(Window):
    """Main window which displays the timetable."""

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self.weekday_label = ClickableLabel(
            self, "", self.st.font, self.change_weekday, state)
        self.class_labels: list[Label] = []
        self.class_advance_label: Label = Label(self)

        self.will_shutdown = False
        self.will_class_advance: WillClassAdvance = None
        self.will_hide_temp = False
        self.will_load_resize: WillLoadResize = None
        self.will_change_class = False
        self.will_change_weekday = False

    def generate_sep(self) -> Label:
        """Generate a separator label."""
        return Label(
            self, text=self.st.separator, font=self.st.font,
            bg=self.st.color_theme.bg, fg=self.st.color_theme.fg)

    def load(self):
        """(Re)Load the window. Generate and place labels and buttons on the window."""
        self.class_labels.clear()
        for child in list(i for i in self.children.values() if i != self.weekday_label):
            child.destroy()
            child.forget()
        self.weekday_label['text'] = to_cn_weekday(self.st.weekday)

        padding_x = self.st.layout.padding_x
        padding_y = self.st.layout.padding_y

        x = padding_x
        height = 0

        def place(w: Widget):
            nonlocal x, height
            w.place(x=x, y=padding_y)
            x += w.winfo_reqwidth()
            height = max(height, w.winfo_reqheight())

        place(self.weekday_label)
        place(self.generate_sep())
        for text in self.st.today_schedule():
            if text == "":
                continue
            if text == self.st.separator:
                place(self.generate_sep())
                continue
            elif text == '~':
                continue
            label = Label(
                self, text=text, font=self.st.font,
                bg=self.st.color_theme.bg, fg=self.st.color_theme.fg
            )
            place(label)
            self.class_labels.append(label)
        place(self.generate_sep())

        buttons = [
            ("隐藏", self.hide_temporarily, "skyblue"),
            ("换课", self.change_class, "yellow"),
            ("上课", self.class_advance, "orange"),
            ("关闭", self.close_destroy, "red")
        ]
        small_font = (self.st.font[0], int(self.st.font[1] * 0.4))

        for i, btn in enumerate(buttons):
            text, func, color = btn
            button = ClickableLabel(self, text, small_font, func, self.st)
            button['fg'] = color
            if text == "上课":
                self.class_advance_label = button
            if i % 2 == 0:
                button.place(x=x, y=padding_y)
            else:
                button.place(x=x, y=(padding_y + height) // 2)
                x += button.winfo_reqwidth()
        x += padding_x
        height += 2 * padding_y
        window_x = (self.winfo_screenwidth() - x) // 2
        self.geometry_state((1, height, window_x, self.st.layout.margin_y))
        self.will_load_resize = x

    def change_weekday(self, _: Any) -> None:
        self.will_change_weekday = True

    def change_class(self, _: Any) -> None:
        self.will_change_class = True

    def class_advance(self, _: Any) -> None:
        """Begin next class in advance."""
        HINT = "此功能只能在下课或预备铃中使用。\n如果想在上课时隐藏窗口，点击课表再点击别处即可。"
        lesson_state = self.st.lesson_state
        info("Class Advance triggers. (lesson_state={0}, current_index={1})".format(
            lesson_state, self.st.current_index))
        if lesson_state in [LessonState.BeforeSchool, LessonState.Break, LessonState.Preparing]:
            name = self.st.current_lesson().name
            hint = f"此操作将会提前进入下一节课: {name}。确定吗？"
            if messagebox.askokcancel("操作确认", hint):  # type: ignore
                self.will_class_advance = 'on'
        elif lesson_state in [LessonState.AtClass]:
            name = self.st.current_lesson().name
            hint = f"此操作会提前下课 (本节为 {name})。确定吗？"
            if messagebox.askokcancel("操作确认", hint):  # type: ignore
                self.will_class_advance = 'off'
        else:
            messagebox.showinfo("提示", HINT)  # type: ignore

    def hide_temporarily(self, _: Any) -> None:
        """Delay the last lesson and cancel topmost."""
        HINT = "此功能只能在下课时使用。\n如果想提前上课，请点击“上课”\n如果想在上课时隐藏窗口，点击课表再点击别处即可。"
        lesson_state = self.st.lesson_state
        current_lesson = self.st.current_index
        info("Class Advance triggers. (lesson_state={0}, current_lesson={1})".format(
            lesson_state, current_lesson))
        if lesson_state in [LessonState.Break, LessonState.AfterSchool]:
            self.will_hide_temp = True
        else:
            messagebox.showinfo("提示", HINT)  # type: ignore

    def close_destroy(self, _: Any) -> None:
        """Close and quit the program."""
        HINT = "确认关闭吗？关闭后需要手动重启课表。\n如果想要 提前 上课，请点击“上课”。\n如果想要 继续 上课，请点击“隐藏”。"
        if messagebox.askokcancel("确认关闭吗", HINT):  # type: ignore
            self.destroy()

    def poll(self) -> Optional[MainPollResult]:
        if self.will_shutdown:
            self.will_shutdown = False
            return (MainPollEnum.ShutDown, )
        if self.will_load_resize is not None:
            width, self.will_load_resize = self.will_load_resize, None
            return (MainPollEnum.Resize, width)
        if self.will_class_advance is not None:
            will_class_advance, self.will_class_advance = self.will_class_advance, None
            return (MainPollEnum.ClassAdvance, will_class_advance)
        if self.will_hide_temp:
            self.will_hide_temp = False
            return (MainPollEnum.HideTemporarily, )
        if self.will_change_class:
            self.will_change_class = False
            return (MainPollEnum.ChangeClass, )
        if self.will_change_weekday:
            self.will_change_weekday = False
            return (MainPollEnum.ChangeWeekday, )

    def destroy(self, quit_program: bool = False) -> None:
        if quit_program:
            self.animate((1, 1, 1, 1), 500)
            super().destroy()
            super().quit()
        else:
            self.will_shutdown = True


class SecondPollResult(Enum):
    ShutDown = 0
    BigChangeResize = 1
    SmallChangeResize = 2


WillSecondResize = Optional[Union[Literal["big"], Literal["small"]]]


class SecondWindow(Window):
    """The window which displays hints like class begins or finishes."""

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self._text = ("", "")
        self.label = Label(
            self, text="", font=self.st.font, bg=self.st.color_theme.bg, fg="yellow")
        self.label.place(x=self.st.layout.padding_x,
                         y=self.st.layout.padding_y)
        self.geometry_state((1, 1, 0, 0))

        self.will_shutdown = False
        self.will_resize: WillSecondResize = None

    def set_text(self, text: tuple[str, str]):
        """Set the text of the window and rerenders or resizes it only when required."""
        if text == self._text:
            return
        big_change = text != ("", "") and text[0] != self._text[0]
        width_original = self.label.winfo_reqwidth()
        self._text = text
        text_display = " ".join(t for t in text if len(t) > 0)
        self.label['text'] = text_display
        self.update()
        info(f"Second Window text changes to {text}")
        if big_change:
            info("Second Window Big-Change Resize")
            self.geometry_state((1, 1, self.winfo_x(), self.winfo_y()))
            self.will_resize = 'big'
        elif self.label.winfo_reqwidth() != width_original:
            info("Second Window Routine Resize")
            self.will_resize = 'small'

    def poll(self) -> Optional[SecondPollResult]:
        if self.will_shutdown:
            return SecondPollResult.ShutDown
        if self.will_resize is not None:
            will_resize, self.will_resize = self.will_resize, None
            if will_resize == 'big':
                return SecondPollResult.BigChangeResize
            elif will_resize == 'small':
                return SecondPollResult.SmallChangeResize
            else:
                assert False, f"unreachable {will_resize}"

    def destroy(self, quit_program: bool = False) -> None:
        if quit_program:
            self.animate((1, 1, 1, 1), 500)
            super().destroy()
            super().quit()
        else:
            self.will_shutdown = True

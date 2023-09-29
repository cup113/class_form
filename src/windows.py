from typing import Any
from widget import ClickableLabel, Window, EditWindow
from tkinter import Widget, Label, Button, Entry, StringVar, Frame, messagebox
from logging import info

from states import LessonState, MessageEnum, State


def to_cn_weekday(weekday: int):
    return "周" + "一二三四五六日"[weekday]


class LessonsEditWindow(EditWindow[list[str]]):
    """A one-off, blocked window to edit the schedule today."""

    TITLE = "换课"
    LOGGING_NAME = "Lessons"

    def __init__(self, state: State) -> None:
        super().__init__()
        self.lines: list[tuple[StringVar, Label, Entry]] = []
        i = 0
        # TODO improve
        for lesson in state.today_schedule():
            text = ""
            if lesson not in ['|', '']:
                text = str(state.raw_timetable[i])
                i += 1
            var = StringVar(self, lesson)
            frame = Frame(self)
            font = (state.font[0], state.font[1] // 2)
            line = (var, Label(frame, text=text, font=font),
                    Entry(frame, textvariable=var, font=font, width=5))
            line[2].pack(side='right')
            line[1].pack(side='right')
            frame.pack(side='top', fill='x')
            self.lines.append(line)
        Button(self, text="确认", command=self._terminate).pack()

    def final_value(self) -> list[str]:
        return [var.get() for var, _, _ in self.lines]


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
                    self._terminate()
                return inner
            frame = Frame(self)
            frame.pack(side='top', fill='x')
            text = "{0} ({1})".format(to_cn_weekday(
                i), " ".join(state.raw_schedule[i]))
            Button(frame, text=text, font=font, command=command()).pack()

    def final_value(self) -> int:
        return self.result


class MainWindow(Window):
    """Main window which displays the timetable."""

    SEP = "|"

    def generate_sep(self) -> Label:
        """Generate a separator label `|`"""
        return Label(
            self, text=self.SEP, font=self.state.font,
            bg=self.state.color_theme.bg, fg=self.state.color_theme.fg)

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self.weekday_label = ClickableLabel(
            self, "", self.state.font, self.change_weekday, state)
        self.class_labels: list[Label] = []

    def load(self):
        """(Re)Load the window. Generate and place labels and buttons on the window."""
        self.class_labels.clear()
        for child in list(i for i in self.children.values() if i != self.weekday_label):
            child.destroy()
            child.forget()
        self.weekday_label['text'] = to_cn_weekday(self.state.weekday)

        padding_x = self.state.layout.padding_x
        padding_y = self.state.layout.padding_y

        x = padding_x
        height = 0

        def place(w: Widget):
            nonlocal x, height
            w.place(x=x, y=padding_y)
            x += w.winfo_reqwidth()
            height = max(height, w.winfo_reqheight())

        place(self.weekday_label)
        place(self.generate_sep())
        for text in self.state.today_schedule():
            if text == self.SEP:
                place(self.generate_sep())
                continue
            elif text == '~':
                continue
            label = Label(
                self, text=text, font=self.state.font,
                bg=self.state.color_theme.bg, fg=self.state.color_theme.fg
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
        small_font = (self.state.font[0], int(self.state.font[1] * 0.4))

        for i, btn in enumerate(buttons):
            text, func, color = btn
            button = ClickableLabel(self, text, small_font, func, self.state)
            button['fg'] = color
            if i % 2 == 0:
                button.place(x=x, y=padding_y)
            else:
                button.place(x=x, y=(padding_y + height) // 2)
                x += button.winfo_reqwidth()
        x += padding_x
        height += 2 * padding_y
        window_x = (self.winfo_screenwidth() - x) // 2
        self.geometry_state((1, height, window_x, self.state.layout.margin_y))
        self.animate((x, height, window_x, self.state.layout.margin_y), 2000)
        self.state.queue.put((MessageEnum.Resize, 2000))

    def change_weekday(self, _: Any) -> None:
        info("Try changing the weekday.")
        weekday = WeekdayEditWindow(self.state).run()
        info(f"Change weekday to: {weekday}")
        if weekday is not None:
            self.state.weekday_map[self.state.now.weekday()] = weekday

    def change_class(self, _: Any) -> None:
        """Change the classes."""
        new_lessons = LessonsEditWindow(self.state).run()
        info(f"Change classes to: {new_lessons}")
        if new_lessons is not None:
            self.state.raw_schedule[self.state.weekday] = new_lessons
            self.state.load_lessons()
            self.load()

    def class_advance(self, _: Any) -> None:
        """Begin next class in advance."""
        HINT = "此功能只能在下课或预备铃中使用。\n如果想在上课时隐藏窗口，点击课表再点击别处即可。"
        lesson_state = self.state.lesson_state
        current_lesson = self.state.current_lesson
        info("Class Advance triggers. (lesson_state={0}, current_lesson={1})".format(
            lesson_state, current_lesson))
        if lesson_state in [LessonState.Break, LessonState.Preparing]:
            name = self.state.i_lesson(current_lesson).name
            hint = f"此操作将会提前进入下一节课: {name}。确定吗？"
            if messagebox.askokcancel("操作确认", hint):  # type: ignore
                self.state.queue.put((MessageEnum.ClassAdvance, ))
        else:
            messagebox.showinfo("提示", HINT)  # type: ignore

    def hide_temporarily(self, _: Any) -> None:
        """Delay the last lesson and cancel topmost."""
        HINT = "此功能只能在下课时使用。\n如果想提前上课，请点击“上课”\n如果想在上课时隐藏窗口，点击课表再点击别处即可。"
        lesson_state = self.state.lesson_state
        current_lesson = self.state.current_lesson
        info("Class Advance triggers. (lesson_state={0}, current_lesson={1})".format(
            lesson_state, current_lesson))
        if lesson_state in [LessonState.Break, LessonState.AfterSchool]:
            self.state.queue.put((MessageEnum.HideTemporarily, ))
        else:
            messagebox.showinfo("提示", HINT)  # type: ignore

    def close_destroy(self, _: Any) -> None:
        """Close and quit the program."""
        HINT = "确认关闭吗？关闭后需要手动重启课表。\n如果想要 提前 上课，请点击“上课”。\n如果想要 继续 上课，请点击“隐藏”。"
        if messagebox.askokcancel("确认关闭吗", HINT):  # type: ignore
            self.animate((1, 1, 1, 1), 500)
            self.destroy()
            self.quit()

    def quit(self, quit_program: bool = True) -> None:
        super().quit()
        if quit_program:
            self.state.queue.put((MessageEnum.ShutDown, ))


class SecondWindow(Window):
    """The window which displays hints like class begins or finishes."""

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self._text = ""
        self.label = Label(
            self, text=self._text, font=self.state.font, bg=self.state.color_theme.bg, fg="yellow")
        self.label.place(x=self.state.layout.padding_x,
                         y=self.state.layout.padding_y)
        self.geometry_state((1, 1, 0, 0))

    def set_text(self, text: str):
        """Set the text of the window and rerenders or resizes it only when required."""
        if text == self._text:
            return
        big_change = self._text != "" and \
            self._text.split(' ')[0] != text.split(' ')[0]
        width_original = self.label.winfo_reqwidth()
        self._text = text
        self.label['text'] = text
        self.update()
        info(f"Second Window text changes to {text}")
        if big_change:
            info("Second Window Big-Change Resize")
            self.geometry_state((1, 1, self.winfo_x(), self.winfo_y()))
            self.state.queue.put((MessageEnum.Resize, 3000))
        elif self.label.winfo_reqwidth() != width_original:
            info("Second Window Routine Resize")
            self.state.queue.put((MessageEnum.Resize, 500))

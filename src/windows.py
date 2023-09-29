from typing import Any
from widget import ClickableLabel, Window, EditWindow
from tkinter import Widget, Misc, Label, Button, Frame, Entry, Checkbutton
from tkinter import StringVar, BooleanVar, messagebox
from logging import info

from states import LessonState, MessageEnum, State


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
            while i < len(lessons):
                if lessons[i] == state.separator:
                    i += 1
                    has_sep = True
                    break
                elif lessons[i] == "":
                    i += 1
                else:
                    break
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
            text = "{0} ({1})".format(to_cn_weekday(
                i), " ".join(state.raw_schedule[i]))
            Button(frame, text=text, font=font, command=command()).pack()

    def final_value(self) -> int:
        return self.result


class MainWindow(Window):
    """Main window which displays the timetable."""

    def generate_sep(self) -> Label:
        """Generate a separator label."""
        return Label(
            self, text=self.st.separator, font=self.st.font,
            bg=self.st.color_theme.bg, fg=self.st.color_theme.fg)

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self.weekday_label = ClickableLabel(
            self, "", self.st.font, self.change_weekday, state)
        self.class_labels: list[Label] = []

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
            if i % 2 == 0:
                button.place(x=x, y=padding_y)
            else:
                button.place(x=x, y=(padding_y + height) // 2)
                x += button.winfo_reqwidth()
        x += padding_x
        height += 2 * padding_y
        window_x = (self.winfo_screenwidth() - x) // 2
        self.geometry_state((1, height, window_x, self.st.layout.margin_y))
        self.animate((x, height, window_x, self.st.layout.margin_y), 2000)
        self.st.queue.put((MessageEnum.Resize, 2000))

    def change_weekday(self, _: Any) -> None:
        info("Try changing the weekday.")
        weekday = WeekdayEditWindow(self.st).run()
        info(f"Change weekday to: {weekday}")
        if weekday is not None:
            self.st.weekday_map[self.st.now.weekday()] = weekday

    def change_class(self, _: Any) -> None:
        """Change the classes."""
        new_lessons = LessonsEditWindow(self.st).run()
        info(f"Change classes to: {new_lessons}")
        if new_lessons is not None:
            self.st.raw_schedule[self.st.weekday] = new_lessons
            self.st.load_lessons()
            self.load()

    def class_advance(self, _: Any) -> None:
        """Begin next class in advance."""
        HINT = "此功能只能在下课或预备铃中使用。\n如果想在上课时隐藏窗口，点击课表再点击别处即可。"
        lesson_state = self.st.lesson_state
        current_lesson = self.st.current_lesson
        info("Class Advance triggers. (lesson_state={0}, current_lesson={1})".format(
            lesson_state, current_lesson))
        if lesson_state in [LessonState.BeforeSchool, LessonState.Break, LessonState.Preparing]:
            name = self.st.i_lesson(current_lesson).name
            hint = f"此操作将会提前进入下一节课: {name}。确定吗？"
            if messagebox.askokcancel("操作确认", hint):  # type: ignore
                self.st.queue.put((MessageEnum.ClassAdvance, ))
        else:
            messagebox.showinfo("提示", HINT)  # type: ignore

    def hide_temporarily(self, _: Any) -> None:
        """Delay the last lesson and cancel topmost."""
        HINT = "此功能只能在下课时使用。\n如果想提前上课，请点击“上课”\n如果想在上课时隐藏窗口，点击课表再点击别处即可。"
        lesson_state = self.st.lesson_state
        current_lesson = self.st.current_lesson
        info("Class Advance triggers. (lesson_state={0}, current_lesson={1})".format(
            lesson_state, current_lesson))
        if lesson_state in [LessonState.Break, LessonState.AfterSchool]:
            self.st.queue.put((MessageEnum.HideTemporarily, ))
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
            self.st.queue.put((MessageEnum.ShutDown, ))


class SecondWindow(Window):
    """The window which displays hints like class begins or finishes."""

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self._text = ""
        self.label = Label(
            self, text=self._text, font=self.st.font, bg=self.st.color_theme.bg, fg="yellow")
        self.label.place(x=self.st.layout.padding_x,
                         y=self.st.layout.padding_y)
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
            self.st.queue.put((MessageEnum.Resize, 3000))
        elif self.label.winfo_reqwidth() != width_original:
            info("Second Window Routine Resize")
            self.st.queue.put((MessageEnum.Resize, 500))

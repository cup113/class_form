from typing import Any
from queue import Empty
from tkinter import Widget, Label, Tk, Button, Entry, StringVar, Frame
from datetime import timedelta
from logging import info
from math import ceil

from states import LessonState, Message, State, PollResult
from clock import Clock
from _logging import init_logger
from widget import ClickableLabel, Window


class EditWindow(Tk):
    def __init__(self, state: State) -> None:
        super().__init__("换课")
        self.attributes('-topmost', True)  # type: ignore
        self.running = True
        self.lines: list[tuple[StringVar, Label, Entry]] = []
        i = 0
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
        Button(self, text="确认", command=self.terminate).pack()

    def terminate(self) -> None:
        info("Terminated")
        self.destroy()

    def destroy(self) -> None:
        super().destroy()
        self.quit()

    def run(self) -> list[str]:
        self.mainloop()
        return [var.get() for var, _, _ in self.lines]


class MainWindow(Window):
    """Main window which displays the timetable."""
    SEP = "|"

    def generate_sep(self) -> Label:
        return Label(self, text=self.SEP, font=self.state.font, bg=self.state.color_theme.bg, fg=self.state.color_theme.fg)

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self.weekday_label = ClickableLabel(
            self, "", self.state.font, print, state)
        self.class_labels: list[ClickableLabel] = []

    def load(self):
        self.class_labels.clear()
        for child in list(i for i in self.children.values() if i != self.weekday_label):
            child.destroy()
            child.forget()
        self.weekday_label['text'] = State.to_cn_weekday(self.state.weekday)

        x = self.X_PADDING
        height = 0

        def place(w: Widget):
            nonlocal x, height
            w.place(x=x, y=self.Y_PADDING)
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
            label = ClickableLabel(
                self, text, self.state.font, print, self.state)
            place(label)
            self.class_labels.append(label)
        place(self.generate_sep())

        buttons = [
            ("隐藏", self.hide_temporarily, "skyblue"),
            ("换课", self.change_class, "yellow"),
            ("上课", self.class_advance, "orange"),
            ("关闭", self.close_destroy, "red")
        ]
        small_font = (self.state.font[0], self.state.font[1] // 3)

        for i, btn in enumerate(buttons):
            text, func, color = btn
            button = ClickableLabel(self, text, small_font, func, self.state)
            button['fg'] = color
            if i % 2 == 0:
                button.place(x=x, y=self.Y_PADDING)
            else:
                button.place(x=x, y=(self.Y_PADDING + height) // 2)
                x += button.winfo_reqwidth()
        x += 10
        height += 2 * self.Y_PADDING
        self.geometry_state((1, height, 250, 16))
        self.animate((x, height, 250, 16), 2000)
        self.state.queue.put(Message.Resize)

    def class_advance(self, _: Any) -> None:
        # TODO 增加确定
        self.state.queue.put(Message.ClassAdvance)

    def hide_temporarily(self, _: Any) -> None:
        self.state.queue.put(Message.HideTemporarily)

    def change_class(self, _: Any) -> None:
        new_lessons = EditWindow(self.state).run()
        info(new_lessons)
        self.state.raw_schedule[self.state.weekday] = new_lessons
        self.state.load_lessons()
        self.load()

    def close_destroy(self, _: Any) -> None:
        self.animate((1, 1, 1, 1), 500)
        self.destroy()
        self.quit()

    def quit(self, quit_program: bool = True) -> None:
        super().quit()
        if quit_program:
            self.state.queue.put(Message.ShutDown)


class SecondWindow(Window):
    @classmethod
    def format_minutes(cls, minute: float, max_limit: float) -> str:
        if minute < max_limit:
            return "{0:.1f}".format(ceil(minute * 10) / 10)
        else:
            return "{0:.0f}".format(ceil(minute))

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self._text = ""
        self.label = Label(
            self, text=self._text, font=self.state.font, bg=self.state.color_theme.bg, fg="yellow")
        self.label.place(x=self.X_PADDING, y=self.Y_PADDING)
        self.geometry("1x1+0+0")

    def set_text(self, text: str):
        if text == self._text:
            return
        width_original = self.label.winfo_reqwidth()
        self._text = text
        self.label['text'] = text
        self.update()
        info(f"Second Window text changes to {text}")
        if self.label.winfo_reqwidth() != width_original:
            info("Second Window Resize")
            self.state.queue.put(Message.Resize)


class Calender:
    WINDOW_GAP = 64

    def __init__(self) -> None:
        self.state = State()
        self.main_window = MainWindow(self.state)
        self.second_window = SecondWindow(self.state)
        self.main_window.load()
        self.running = True

        init_logger()
        info("Initialized\n{}".format(repr(self.state)))

    def mainloop(self) -> None:
        clock = Clock(self.state.inspect_interval)
        while self.running:
            clock.wait()
            poll_results = self.state.poll_all()
            for i, poll_result in enumerate(poll_results):
                self.handle_poll(poll_result, i + 1 == len(poll_results))
            self.poll_update()
            self.main_window.update()
            while True:
                try:
                    event = self.state.queue.get(False)
                    info(f"Event captured: {event}")
                except Empty:
                    break
                self.handle_event(event)

    def handle_event(self, event: Message) -> None:
        if event == Message.ShutDown:
            self.second_window.destroy()
            self.second_window.quit()
            self.running = False
        elif event == Message.Resize:
            w1, h1 = self.main_window.winfo_width(), self.main_window.winfo_height()
            label = self.second_window.label
            w2 = label.winfo_width() + 2 * Window.X_PADDING
            h2 = label.winfo_height() + 2 * Window.Y_PADDING
            w_screen = self.main_window.winfo_screenwidth()
            remaining = max(
                w_screen - (self.WINDOW_GAP if w2 >= 5 else 0) - w1 - w2, 0)
            x1 = remaining // 2
            x2 = w_screen - w2 - remaining // 2
            self.second_window.animate((w2, h2, x2, 16), 500)
            self.main_window.animate((w1, h1, x1, 16), 500)
        elif event == Message.HideTemporarily:
            if self.state.lesson_state in [LessonState.Break, LessonState.AfterSchool]:
                self.main_window.set_topmost(False)
                self.second_window.set_topmost(False)
                self.state.lesson_state = LessonState.AtClass
                self.state.current_lesson -= 1
                lesson = self.state.lessons[self.state.current_lesson]
                lesson.delay = self.state.now - \
                    lesson.finish + timedelta(minutes=3)
        elif event == Message.ClassAdvance:
            if self.state.lesson_state in [LessonState.Break, LessonState.Preparing]:
                self.main_window.set_topmost(False)
                self.second_window.set_topmost(False)
                self.state.lesson_state = LessonState.AtClass
                if self.state.current_lesson > 0:
                    self.main_window.class_labels[
                        self.state.current_lesson - 1]['fg'] = self.state.color_theme.fg
                self.main_window.class_labels[self.state.current_lesson]['fg'] = self.state.color_theme.hint

    def handle_poll(self, event: PollResult, _update: bool):
        if event == PollResult.Reload:
            self.state.load_lessons()
        elif event == PollResult.ClassBegin:
            self.main_window.set_topmost(False)
            self.second_window.set_topmost(False)
        elif event == PollResult.ClassFinish:
            self.main_window.set_topmost(True)
            self.second_window.set_topmost(True)
        elif event == PollResult.ClassPrepare:
            if self.state.current_lesson > 0:
                self.main_window.class_labels[
                    self.state.current_lesson - 1]['fg'] = self.state.color_theme.fg
            # FIXME IndexError
            self.main_window.class_labels[self.state.current_lesson]['fg'] = self.state.color_theme.hint
        else:
            assert False, event

    def poll_update(self):
        text = ""
        if self.state.lesson_state == LessonState.AtClass:
            text = "上课时间"
            lesson = self.state.lessons[self.state.current_lesson]
            if lesson.name in self.state.self_study_lessons:
                total = (lesson.finish + lesson.delay -
                         lesson.start).total_seconds() / 60
                last = (lesson.finish - self.state.now).total_seconds() / 60
                text += " {0}/{1:.0f}".format(
                    SecondWindow.format_minutes(
                        last, min(10, total / 2)), total
                )
        elif self.state.lesson_state == LessonState.Preparing:
            lesson = self.state.lessons[self.state.current_lesson]
            total = self.state.preparation.total_seconds() / 60
            last = (lesson.start - self.state.now).total_seconds() / 60
            text = "预备 {0}/{1:.0f}".format(
                SecondWindow.format_minutes(last, min(10, total / 2)), total
            )
        elif self.state.lesson_state == LessonState.Break:
            lesson = self.state.lessons[self.state.current_lesson]
            total = (lesson.start - self.state.preparation -
                     self.state.lessons[self.state.current_lesson - 1].finish).total_seconds() / 60
            last = (lesson.start - self.state.preparation -
                    self.state.now).total_seconds() / 60
            text = "下课 {0}/{1:.0f}".format(
                SecondWindow.format_minutes(last, min(10, total / 2)), total
            )
            current_lesson = self.state.current_lesson
            if current_lesson > 0:
                self.main_window.class_labels[current_lesson]['fg'] = self.state.color_theme.gradient(
                    last / total / 2)
            self.main_window.class_labels[current_lesson -
                                          1]['fg'] = self.state.color_theme.gradient(1 - last / total / 2)
        elif self.state.lesson_state == LessonState.BeforeSchool:
            first_lesson = self.state.lessons[0]
            text = "{}".format(SecondWindow.format_minutes(
                (first_lesson.start - self.state.preparation - self.state.now).total_seconds() / 60, 10))
        elif self.state.lesson_state == LessonState.AfterSchool:
            self.main_window.class_labels[-1]['fg'] = self.state.color_theme.fg
            last_lesson = self.state.lessons[-1]
            text = "放学 {}".format(
                SecondWindow.format_minutes(
                    (self.state.now - last_lesson.finish).total_seconds() / 60, 10)
            )
        self.second_window.set_text(text)


if __name__ == "__main__":
    calender = Calender()
    calender.mainloop()

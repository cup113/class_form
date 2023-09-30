from queue import Empty
from math import ceil
from logging import info, error
from datetime import timedelta
from traceback import format_exception
from tkinter.messagebox import showerror # type: ignore

from states import LessonState, MessageEnum, Message, State, PollEnum, PollResult
from clock import Clock
from _logging import init_logger
from windows import MainWindow, SecondWindow


class Calender:
    """Main program class."""

    @classmethod
    def format_minutes(cls, minute: float, max_limit: float) -> str:
        """
        >>> cls.format_minutes(11.4, 10.0)
        "12"
        >>> cls.format_minutes(10 / 3, 10.0)
        "3.4"
        >>> cls.format_minutes(4.2, 4)
        "5"
        """

        if minute < max_limit:
            return "{0:.1f}".format(ceil(minute * 10) / 10)
        else:
            return "{0:.0f}".format(ceil(minute))

    @classmethod
    def minute(cls, delta: timedelta) -> float:
        return delta.total_seconds() / 60

    def __init__(self) -> None:
        self.state = State()
        self.main_window = MainWindow(self.state)
        self.second_window = SecondWindow(self.state)
        self.main_window.load()
        self.running = True

        info("Initialized\n{}".format(repr(self.state)))

    def mainloop(self) -> None:
        clock = Clock(self.state.inspect_interval)
        while self.running:
            clock.wait()
            poll_results = self.state.poll_all()
            breaking = False
            for i, poll_result in enumerate(poll_results):
                if self.handle_poll(poll_result, i + 1 == len(poll_results)):
                    breaking = True
            if breaking:
                info("Breaking poll result. Continue.")
            if not breaking:
                self.poll_update()
            self.main_window.update()
            while True:
                try:
                    event = self.state.queue.get(False)
                    info(f"Event captured: {event}")
                except Empty:
                    break
                self.handle_event(event)

    def set_windows_topmost(self, topmost: bool) -> None:
        self.main_window.set_topmost(topmost)
        self.second_window.set_topmost(topmost)

    def handle_event(self, event: Message) -> None:
        """Handle the event sent by windows children."""
        if event[0] == MessageEnum.ShutDown:
            self.second_window.set_topmost(True)
            self.second_window.animate((1, 1, 1, 1), 500)
            self.second_window.destroy()
            self.second_window.quit()
            self.running = False
        elif event[0] == MessageEnum.Resize:
            duration_ms = event[1]
            w1, h1 = self.main_window.winfo_width(), self.main_window.winfo_height()
            label = self.second_window.label
            w2 = label.winfo_width() + 2 * self.state.layout.padding_x
            h2 = label.winfo_height() + 2 * self.state.layout.padding_y
            w_screen = self.main_window.winfo_screenwidth()
            gap = self.state.layout.windows_gap if len(label['text']) else 0
            remaining = max(w_screen - gap - w1 - w2, 0)
            x1 = remaining // 2
            x2 = w_screen - w2 - remaining // 2
            self.second_window.animate(
                (w2, h2, x2, self.state.layout.margin_y), duration_ms)
            self.main_window.animate(
                (w1, h1, x1, self.state.layout.margin_y), duration_ms)
        elif event[0] == MessageEnum.HideTemporarily:
            self.set_windows_topmost(False)
            self.state.lesson_state = LessonState.AtClass
            self.state.current_lesson -= 1
            lesson = self.state.i_lesson(self.state.current_lesson)
            lesson.delay = self.state.now + self.state.temporary_hide - \
                lesson.finish
            next_lesson = self.state.i_lesson_checked(
                self.state.current_lesson + 1)
            if next_lesson is not None:
                lesson.delay = min(
                    lesson.delay,
                    next_lesson.prepare - lesson.finish
                )
        elif event[0] == MessageEnum.ClassAdvance:
            self.set_windows_topmost(False)
            self.state.lesson_state = LessonState.AtClass
            if self.state.current_lesson > 0:
                self.main_window.class_labels[
                    self.state.current_lesson - 1]['fg'] = self.state.color_theme.fg
            self.main_window.class_labels[self.state.current_lesson]['fg'] = self.state.color_theme.hint

        else:
            assert False, event  # unreachable

    def handle_poll(self, event: PollResult, update: bool) -> bool:
        """Handle the polling result."""
        if event[0] == PollEnum.Reload:
            info(f"Select the timetable of weekday {self.state.weekday}")
            self.state.load_lessons()
            self.main_window.load()
            return True
        elif event[0] == PollEnum.ClassBegin:
            self.set_windows_topmost(False)
        elif event[0] == PollEnum.ClassFinish:
            self.set_windows_topmost(True)
        elif event[0] == PollEnum.ClassPrepare:
            if update:
                self.main_window.bell()
            if event[1] > 0:
                label = self.main_window.class_labels[event[1] - 1]
                label['fg'] = self.state.color_theme.fg
            label = self.main_window.class_labels[event[1]]
            label['fg'] = self.state.color_theme.hint
        else:
            assert False, event
        return False

    def poll_update(self):
        """Polling, updating mainly the second window and resizing."""
        text = ""
        if self.state.lesson_state == LessonState.AtClass:
            text = "上课时间"
            lesson = self.state.i_lesson(self.state.current_lesson)
            if lesson.name in self.state.self_study_lessons:
                total = self.minute(
                    lesson.finish + lesson.delay - lesson.start)
                last = self.minute(lesson.finish - self.state.now)
                text += " {0}/{1:.0f}".format(
                    self.format_minutes(last, min(10, total / 2)), total
                )
        elif self.state.lesson_state == LessonState.Preparing:
            lesson = self.state.i_lesson(self.state.current_lesson)
            total = self.minute(self.state.preparation)
            last = self.minute(lesson.start - self.state.now)
            text = "预备铃 {0}/{1:.0f}".format(
                self.format_minutes(last, 10), total
            )
        elif self.state.lesson_state == LessonState.Break:
            lesson = self.state.i_lesson(self.state.current_lesson)
            total = self.minute(
                lesson.prepare -
                self.state.i_lesson(self.state.current_lesson - 1).finish)
            last = self.minute(lesson.prepare - self.state.now)
            text = "下课 {0}/{1:.0f}".format(
                self.format_minutes(last, min(10, total / 2)), total
            )
            current_lesson = self.state.current_lesson
            if current_lesson > 0:
                self.main_window.class_labels[current_lesson]['fg'] = self.state.color_theme.gradient(
                    last / total / 2)
            self.main_window.class_labels[
                current_lesson - 1]['fg'] = self.state.color_theme.gradient(1 - last / total / 2)
        elif self.state.lesson_state == LessonState.BeforeSchool:
            first_lesson = self.state.i_lesson(0)
            text = "{}".format(self.format_minutes(self.minute(
                first_lesson.prepare - self.state.now), 10))
        elif self.state.lesson_state == LessonState.AfterSchool:
            self.main_window.class_labels[-1]['fg'] = self.state.color_theme.fg
            last_lesson = self.state.i_lesson(-1)
            text = "放学 {}".format(self.format_minutes(
                self.minute(self.state.now - last_lesson.finish), 10))
        self.second_window.set_text(text)


if __name__ == "__main__":
    init_logger()
    try:
        calender = Calender()
        calender.mainloop()
    except Exception as e:
        msg = ''.join(format_exception(e))
        error(msg)
        showerror("程序出错", "详见日志\n\n" + msg)

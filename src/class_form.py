from math import ceil
from typing import Optional
from logging import info, error
from datetime import timedelta
from traceback import format_exception
from tkinter.messagebox import showerror  # type: ignore

from states import LessonState, State, StatePollEnum, StatePollResult
from clock import Clock
from _logging import init_logger
from windows import MainWindow, SecondWindow, LessonsEditWindow, WeekdayEditWindow
from windows import MainPollEnum, MainPollResult, SecondPollResult


class Calender:
    """Main program class."""

    MAX_POINT_DISPLAY = 9.9

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

    @classmethod
    def format_progress(cls, remaining: timedelta, total: timedelta, half_limit: bool) -> str:
        total_min = cls.minute(total)
        remaining_min = cls.minute(remaining)
        max_limit = cls.MAX_POINT_DISPLAY
        if half_limit:
            max_limit = min(max_limit, total_min / 2)
        return "{0}/{1:.0f}".format(
            cls.format_minutes(remaining_min, max_limit),
            total_min
        )

    def __init__(self) -> None:
        self.st = State()
        self.main_window = MainWindow(self.st)
        self.second_window = SecondWindow(self.st)
        self.main_window.load()
        self.running = True

        info("Initialized\n{}".format(repr(self.st)))

    def mainloop(self) -> None:
        clock = Clock(self.st.inspect_interval)
        while self.running:
            clock.wait()
            poll_results = self.st.poll_all()
            breaking = False
            for i, poll_result in enumerate(poll_results):
                if self.handle_state_poll(poll_result, i + 1 == len(poll_results)):
                    breaking = True
            if breaking:
                info("Breaking poll result. Continue.")
            if not breaking:
                main_poll_result = self.main_window.poll()
                if main_poll_result is not None:
                    self.handle_main_poll(main_poll_result)
                second_poll_result = self.second_window.poll()
                if second_poll_result is not None:
                    self.handle_second_poll(second_poll_result)
                if not self.running:
                    break
                self.poll_update()
            self.main_window.update()

    def set_windows_topmost(self, topmost: bool) -> None:
        self.main_window.set_topmost(topmost)
        self.second_window.set_topmost(topmost)

    def reload(self) -> None:
        info(f"Select the timetable of weekday (0~7) {self.st.weekday}")
        self.st.load_lessons()
        self.main_window.load()

    def resize(self, duration_ms: int, w1: Optional[int] = None) -> None:
        if w1 is None:
            w1 = self.main_window.winfo_width()
        h1 = self.main_window.winfo_height()
        label = self.second_window.label
        w2 = label.winfo_width() + 2 * self.st.layout.padding_x
        h2 = label.winfo_height() + 2 * self.st.layout.padding_y
        w_screen = self.main_window.winfo_screenwidth()
        gap = self.st.layout.windows_gap if len(label['text']) else 0
        remaining = max(w_screen - gap - w1 - w2, 0)
        x1 = remaining // 2
        x2 = w_screen - w2 - remaining // 2
        self.main_window.animate(
            (w1, h1, x1, self.st.layout.margin_y), duration_ms)
        self.second_window.animate(
            (w2, h2, x2, self.st.layout.margin_y), duration_ms)

    def shutdown(self) -> None:
        self.set_windows_topmost(True)
        self.main_window.destroy(True)
        self.second_window.destroy(True)
        self.running = False

    def class_begin(self, index: int) -> None:
        self.set_windows_topmost(False)
        self.main_window.class_advance_label['text'] = "下课"
        class_labels = self.main_window.class_labels
        if index > 0:
            class_labels[index - 1
                         ]['fg'] = self.st.color_theme.fg
        class_labels[index]['fg'] = self.st.color_theme.hint

    def class_finish(self) -> None:
        self.set_windows_topmost(True)
        self.main_window.class_advance_label['text'] = "上课"

    def class_prepare(self, index: int, bell: bool) -> None:
        if bell:
            self.main_window.bell()
        if index > 0:
            label = self.main_window.class_labels[index - 1]
            label['fg'] = self.st.color_theme.fg
        label = self.main_window.class_labels[index]
        label['fg'] = self.st.color_theme.hint

    def adjust_color(self, pass_ratio: float):
        pass_ratio = min(max(pass_ratio, 0), 1)
        class_labels = self.main_window.class_labels
        i = self.st.current_index
        if i > 0:
            class_labels[i - 1]['fg'] = self.st.color_theme.gradient(
                (1 - pass_ratio) / 1.5)
        if i < len(self.st.lessons):
            class_labels[i]['fg'] = self.st.color_theme.gradient(
                (1 + pass_ratio) / 2)

    def handle_state_poll(self, event: StatePollResult, update: bool) -> bool:
        """Handle the polling result."""
        if event[0] == StatePollEnum.Reload:
            self.reload()
            return True
        elif event[0] == StatePollEnum.ClassBegin:
            self.class_begin(event[1])
        elif event[0] == StatePollEnum.ClassFinish:
            self.class_finish()
        elif event[0] == StatePollEnum.ClassPrepare:
            self.class_prepare(event[1], update)
        else:
            assert False, f"unreachable {event}"
        return False

    def handle_main_poll(self, poll_result: MainPollResult) -> None:
        """Handle the event sent by main window."""
        info(f"Main poll captured: {poll_result}")

        if poll_result[0] == MainPollEnum.ShutDown:
            self.shutdown()
        elif poll_result[0] == MainPollEnum.Resize:
            self.resize(2000, poll_result[1])
        elif poll_result[0] == MainPollEnum.HideTemporarily:
            original_state = self.st.lesson_state
            self.st.lesson_state = LessonState.AtClass
            self.st.current_index -= 1
            lesson = self.st.current_lesson()
            delay = self.st.now + self.st.temporary_hide - lesson.finish
            if original_state != LessonState.AfterSchool:
                delay = min(
                    delay,
                    self.st.next_lesson().prepare - lesson.finish
                )
            lesson.delay = delay
            self.class_begin(self.st.current_index)
        elif poll_result[0] == MainPollEnum.ClassAdvance:
            if poll_result[1] == 'on':
                self.class_begin(self.st.current_index)
                self.st.lesson_state = LessonState.AtClass
            elif poll_result[1] == 'off':
                self.st.current_index += 1
                if self.st.current_index < len(self.st.lessons):
                    self.st.lesson_state = LessonState.Break
                else:
                    self.st.lesson_state = LessonState.AfterSchool
                self.class_finish()
            else:
                assert False, f"unreachable {poll_result[1]}"
        elif poll_result[0] == MainPollEnum.ChangeClass:
            info("Try changing new lessons.")
            new_lessons = LessonsEditWindow(self.st).run()
            info(f"Change classes to: {new_lessons}")
            if new_lessons is not None:
                self.st.raw_schedule[self.st.weekday] = new_lessons
                self.reload()
        elif poll_result[0] == MainPollEnum.ChangeWeekday:
            info("Try changing the weekday.")
            weekday = WeekdayEditWindow(self.st).run()
            info(f"Change weekday to: {weekday}")
            if weekday is not None:
                self.st.weekday_map[self.st.now.weekday()] = weekday

        else:
            assert False, f"unreachable {poll_result}"

    def handle_second_poll(self, poll_result: SecondPollResult) -> None:
        info(f"Second poll captured: {poll_result}")

        if poll_result == SecondPollResult.ShutDown:
            self.shutdown()
        elif poll_result == SecondPollResult.BigChangeResize:
            self.resize(2000)
        elif poll_result == SecondPollResult.SmallChangeResize:
            self.resize(300)
        else:
            assert poll_result is None, f"unreachable {poll_result}"

    def poll_update(self):
        """Polling, updating mainly the second window and resizing."""
        MAX_MIN_OUT_CLASS = 15

        text_prefix = ""
        text_suffix = ""
        if self.st.lesson_state == LessonState.AtClass:
            lesson = self.st.current_lesson()
            text_prefix = "上课时间"
            if lesson.name in self.st.self_study_lessons:
                text_suffix = self.format_progress(
                    lesson.finish - self.st.now,
                    lesson.real_finish() - lesson.start,
                    True
                )
        elif self.st.lesson_state == LessonState.Preparing:
            lesson = self.st.current_lesson()
            text_prefix = "预备铃"
            text_suffix = self.format_progress(
                lesson.start - self.st.now,
                self.st.preparation,
                False
            )
        elif self.st.lesson_state == LessonState.Break:
            lesson = self.st.current_lesson()
            text_prefix = "下课"
            remaining = lesson.prepare - self.st.now
            total = lesson.prepare - self.st.last_lesson().finish
            text_suffix = self.format_progress(remaining, total, True)
            self.adjust_color(1 - remaining / total)
        elif self.st.lesson_state == LessonState.BeforeSchool:
            text_prefix = ""
            remaining_min = self.minute(
                self.st.current_lesson().prepare - self.st.now)
            text_suffix = self.format_minutes(
                remaining_min, self.MAX_POINT_DISPLAY)
            self.adjust_color(1 - remaining_min / MAX_MIN_OUT_CLASS)
        elif self.st.lesson_state == LessonState.AfterSchool:
            text_prefix = "放学"
            last_lesson = self.st.last_lesson()
            past_min = self.minute(self.st.now - last_lesson.finish)
            text_suffix = self.format_minutes(
                past_min, self.MAX_POINT_DISPLAY)
            self.adjust_color(past_min / MAX_MIN_OUT_CLASS)

        self.second_window.set_text((text_prefix, text_suffix))


if __name__ == "__main__":
    init_logger()
    try:
        calender = Calender()
        calender.mainloop()
    except Exception as e:
        msg = ''.join(format_exception(e))
        error(msg)
        showerror("程序出错", "详见日志\n\n" + msg)
    except KeyboardInterrupt:
        info("Quit by KeyboardInterrupt.")

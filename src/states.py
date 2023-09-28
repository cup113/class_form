from enum import Enum
from typing import Optional
from json import load as json_load
from queue import Queue
from datetime import timedelta, datetime
from logging import info

from colors import ColorTheme


class LessonState(Enum):
    BeforeSchool = 0
    AfterSchool = 1
    Break = 2
    Preparing = 3
    AtClass = 4


class Message(Enum):
    ShutDown = 0
    ClassAdvance = 1
    HideTemporarily = 2
    Resize = 3


class PollResult(Enum):
    Reload = 0
    ClassPrepare = 1
    ClassBegin = 2
    ClassFinish = 3


class Lesson:
    @staticmethod
    def parse_period(period: str) -> tuple[timedelta, timedelta]:
        """
        >>> parse_period("10:05-10:40")
        (timedelta(hours=10, minutes=5), time(hours=11, minutes=40))
        """
        begin, end = period.split(State.PERIOD_SEP)
        begin_hour, begin_minute = begin.split(":")
        end_hour, end_minute = end.split(":")
        return (timedelta(hours=int(begin_hour), minutes=int(begin_minute)),
                timedelta(hours=int(end_hour), minutes=int(end_minute)))

    def __init__(self, name: str, start: timedelta, finish: timedelta) -> None:
        now = datetime.now()
        today = datetime(now.year, now.month, now.day)
        self.name = name
        self.start = today + start
        self.finish = today + finish
        self.delay = timedelta(0)

    def __repr__(self) -> str:
        return f"{self.name}: {self.start}-{self.finish}"


class State:
    PERIOD_SEP = "-"
    FILE = "config.json"
    ENCODING = "utf-8"

    @staticmethod
    def to_cn_weekday(weekday: int):
        return "周" + "一二三四五六日"[weekday]

    def __init__(self):
        """Read config from file"""
        with open(self.FILE, 'r', encoding=self.ENCODING) as f:
            config = json_load(f)
        raw_schedule: dict[str, list[str]] = config["日程表"]
        raw_timetable: list[str] = config["课程时间"]
        self_study_lessons: list[str] = config["自主课程"]
        preparation_minutes = float(config["预备铃"])
        font = config["字体"]
        inspect_frequency = float(config["侦测频率"])
        color_theme = ColorTheme(config["颜色主题"])

        self.raw_schedule = [raw_schedule[str(i)] for i in range(1, 8)]
        self.raw_timetable = raw_timetable
        self.timetable = list(map(Lesson.parse_period, raw_timetable))
        self.self_study_lessons = set(self_study_lessons)
        self.preparation = timedelta(minutes=preparation_minutes)
        self.font = (str(font["名称"]), int(font["大小"]))
        self.alpha = float(config["透明度"])
        self.inspect_interval = 1.0 / inspect_frequency
        self.color_theme = color_theme

        self.queue: Queue[Message] = Queue()

        self.now = datetime.now()
        self.weekday = self.now.weekday()
        self.lesson_state = LessonState.BeforeSchool
        self.current_lesson = 0  # index (current/next)
        self.lessons: list[Lesson] = []
        self.load_lessons()

    def __repr__(self) -> str:
        schedule = "\n".join(
            f"{i + 1}: " + " ".join(day)
            for i, day in enumerate(self.raw_schedule)
        )
        timetable = [
            "{0:.0f}~{1:.0f}".format(
                start.total_seconds(), finish.total_seconds())
            for start, finish in self.timetable
        ]
        return f"Schedule:\n{schedule}\n" + \
            f"Timetable: {timetable}\n" + \
            f"Preparation: {self.preparation.total_seconds() / 60:.1f} min\n" + \
            f"Font: {self.font}\n" + \
            f"Alpha: {self.alpha * 100:.1f}%\n" + \
            f"Inspect Interval: {self.inspect_interval:.3f} sec\n" + \
            f"Color Theme: {self.color_theme}"

    def today_schedule(self) -> list[str]:
        return self.raw_schedule[self.weekday]

    def load_lessons(self):
        self.lessons.clear()
        self.current_lesson = 0
        i = 0
        start = None
        for name in self.today_schedule():
            if name == '|' or len(name) == 0:
                continue
            elif name == '~':
                if start is None:
                    start = self.timetable[i][0]
            else:
                if start is None:
                    start = self.timetable[i][0]
                finish = self.timetable[i][1]
                self.lessons.append(Lesson(name, start, finish))
                start = None
            i += 1

    def poll_class_preparation(self, index: int) -> bool:
        return self.lessons[index].start - self.preparation <= self.now

    def poll_class_begin(self, index: int) -> bool:
        return self.lessons[index].start <= self.now

    def poll_class_end(self) -> bool:
        lesson = self.lessons[self.current_lesson]
        return lesson.finish + lesson.delay <= self.now

    def _poll(self) -> Optional[PollResult]:
        self.now = datetime.now()
        # self.now -= timedelta(hours=1, minutes=24)

        if self.now.weekday() != self.weekday:
            self.weekday = self.now.weekday()
            return PollResult.Reload

        elif self.lesson_state == LessonState.BeforeSchool:
            if self.poll_class_preparation(0):
                self.lesson_state = LessonState.Preparing
                return PollResult.ClassBegin

        elif self.lesson_state == LessonState.Preparing:
            if self.poll_class_begin(self.current_lesson):
                self.lesson_state = LessonState.AtClass
                return PollResult.ClassBegin

        elif self.lesson_state == LessonState.AtClass:
            if self.poll_class_end():
                self.current_lesson += 1
                if self.current_lesson < len(self.lessons):
                    self.lesson_state = LessonState.Break
                else:
                    self.lesson_state = LessonState.AfterSchool
                return PollResult.ClassFinish

        elif self.lesson_state == LessonState.Break:
            if self.poll_class_preparation(self.current_lesson):
                self.lesson_state = LessonState.Preparing
                return PollResult.ClassPrepare

        else:
            assert self.lesson_state == LessonState.AfterSchool

    def poll_all(self) -> list[PollResult]:
        result: list[PollResult] = []
        tmp = self._poll()
        while tmp is not None:
            info(
                f"Event captured: {tmp} (current_lesson={self.current_lesson})")
            result.append(tmp)
            tmp = self._poll()
        return result

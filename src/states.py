from enum import Enum
from typing import Optional, Union, Literal, Any
from json import load as json_load
from datetime import timedelta, datetime
from dataclasses import dataclass
from logging import info

from colors import ColorTheme


class LessonState(Enum):
    """The state which describes what the students should be doing."""
    BeforeSchool = 0
    AfterSchool = 1
    Break = 2
    Preparing = 3
    AtClass = 4


class StatePollEnum(Enum):
    """The result of polling"""
    Reload = 0
    ClassPrepare = 1
    ClassBegin = 2
    ClassFinish = 3


StatePollResult = Union[
    tuple[Literal[StatePollEnum.Reload]],
    tuple[Literal[StatePollEnum.ClassPrepare], int],
    tuple[Literal[StatePollEnum.ClassBegin], int],
    tuple[Literal[StatePollEnum.ClassFinish]],
]


@dataclass
class Layout:
    margin_y: int
    windows_gap: int
    padding_y: int
    padding_x: int


class Lesson:
    """A class which stores current time-related information of lesson.
    May get wrong if the program has continuously been running for more than a week."""

    def __init__(
        self, name: str, start: timedelta, finish: timedelta,
        preparation: timedelta, empty_before: int
    ) -> None:
        now = datetime.now()
        today = datetime(now.year, now.month, now.day)
        self.name = name
        self.start = today + start
        self.finish = today + finish
        self.empty_before = empty_before
        self.prepare = self.start - preparation
        self.delay = timedelta(0)

    def real_finish(self):
        return self.finish + self.delay

    def __repr__(self) -> str:
        return f"{self.name}: {self.start}-{self.finish}"


class State:
    """Main data storage. Read from config file."""

    PERIOD_SEP = "-"
    FILES = ["config_special.json", "config_custom.json", "config.json"]
    ENCODING = "utf-8"
    TIME_OFFSET = timedelta(hours=0, minutes=0)  # for development use

    @classmethod
    def parse_period(cls, period: str) -> tuple[timedelta, timedelta]:
        """
        >>> parse_period("10:05-10:40")
        (timedelta(hours=10, minutes=5), time(hours=11, minutes=40))
        """
        begin, end = period.split(State.PERIOD_SEP)
        begin_hour, begin_minute = begin.split(":")
        end_hour, end_minute = end.split(":")
        return (timedelta(hours=int(begin_hour), minutes=int(begin_minute)),
                timedelta(hours=int(end_hour), minutes=int(end_minute)))

    @classmethod
    def load_config(cls) -> dict[str, Any]:
        for i, file in enumerate(cls.FILES):
            try:
                with open(file, 'r', encoding=cls.ENCODING) as f:
                    return json_load(f)
            except Exception as e:
                info(f"Config file #{i} ({file}) not found: {e}")
        raise FileNotFoundError(f"All 3 config files {cls.FILES} not found.")

    def __init__(self):
        """Read config from file"""
        config = self.load_config()
        raw_schedule: dict[str, list[str]] = config["日程表"]
        raw_timetable: list[str] = config["课程时间"]
        self_study_lessons: list[str] = config["自主课程"]
        preparation_minutes = float(config["预备铃"])
        temporary_hide_minutes = float(config["暂时隐藏时间"])
        font = config["字体"]
        inspect_frequency = float(config["侦测频率"])
        color_theme = ColorTheme(config["颜色主题"])
        layout = config["屏幕布局"]

        self.raw_schedule = [raw_schedule[str(i)] for i in range(1, 8)]
        self.raw_timetable = raw_timetable
        self.timetable = list(map(self.parse_period, raw_timetable))
        self.separator = str(config["分隔符"])
        self.self_study_lessons = set(self_study_lessons)
        self.preparation = timedelta(minutes=preparation_minutes)
        self.temporary_hide = timedelta(minutes=temporary_hide_minutes)
        self.font = (str(font["名称"]), int(font["大小"]))
        self.alpha = float(config["透明度"])
        self.inspect_interval = 1.0 / inspect_frequency
        self.color_theme = color_theme
        self.layout = Layout(
            layout["窗口上方"], layout["窗口间隔"],
            layout["窗口内上下"], layout["窗口内左右"]
        )

        self.now = datetime.now()
        self.weekday = self.now.weekday()
        self.weekday_map: dict[int, int] = dict()
        self.lesson_state = LessonState.BeforeSchool
        self.current_index = 0  # index (current/next)
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
        """(Re)Load the lessons to (re-)simulate the lesson."""

        self.lessons.clear()
        self.current_index = 0
        self.lesson_state = LessonState.BeforeSchool
        i = 0
        empty_before = 0
        start = None
        for name in self.today_schedule():
            if name == self.separator:
                continue
            elif name == "":
                empty_before += 1
            elif name == '~':
                if start is None:
                    start = self.timetable[i][0]
            else:
                if start is None:
                    start = self.timetable[i][0]
                finish = self.timetable[i][1]
                self.lessons.append(Lesson(
                    name, start, finish, self.preparation, empty_before))
                start = None
                empty_before = 0
            i += 1

    def current_lesson(self):
        return self.lessons[self.current_index]

    def next_lesson(self):
        return self.lessons[self.current_index + 1]

    def last_lesson(self):
        return self.lessons[self.current_index - 1]

    def poll_class_preparation(self) -> bool:
        """Check if the first bell is ringing."""
        return self.current_lesson().prepare <= self.now

    def poll_class_begin(self) -> bool:
        """Check if the second bell is ringing."""
        return self.current_lesson().start <= self.now

    def poll_class_end(self) -> bool:
        """Check if the class has finished."""
        lesson = self.current_lesson()
        return lesson.finish + lesson.delay <= self.now

    def _poll(self) -> Optional[StatePollResult]:
        """Poll and simulate the progress of schedule."""

        self.now = datetime.now() + self.TIME_OFFSET
        mapped_weekday = self.weekday_map.get(self.now.weekday())

        if mapped_weekday is not None:
            if self.weekday != mapped_weekday:
                self.weekday = mapped_weekday
                return (StatePollEnum.Reload, )
        else:
            if self.now.weekday() != self.weekday:
                self.weekday = self.now.weekday()
                return (StatePollEnum.Reload, )

        if self.lesson_state == LessonState.BeforeSchool:
            if self.poll_class_preparation():
                self.lesson_state = LessonState.Preparing
                return (StatePollEnum.ClassPrepare, self.current_index)

        elif self.lesson_state == LessonState.Preparing:
            if self.poll_class_begin():
                self.lesson_state = LessonState.AtClass
                return (StatePollEnum.ClassBegin, self.current_index)

        elif self.lesson_state == LessonState.AtClass:
            if self.poll_class_end():
                self.current_index += 1
                if self.current_index < len(self.lessons):
                    self.lesson_state = LessonState.Break
                else:
                    self.lesson_state = LessonState.AfterSchool
                return (StatePollEnum.ClassFinish, )

        elif self.lesson_state == LessonState.Break:
            if self.poll_class_preparation():
                self.lesson_state = LessonState.Preparing
                return (StatePollEnum.ClassPrepare, self.current_index)

        else:
            assert self.lesson_state == LessonState.AfterSchool, f"unreachable {self.lesson_state}"

    def poll_all(self) -> list[StatePollResult]:
        """Poll until there is nothing happening."""
        result: list[StatePollResult] = []
        tmp = self._poll()
        while tmp is not None:
            info("State poll captured: {0} (current_lesson={1})".format(
                tmp, self.current_index))
            result.append(tmp)
            tmp = self._poll()
        return result

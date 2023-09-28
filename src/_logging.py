from logging import basicConfig, INFO, DEBUG
from sys import argv
from os import mkdir
from os.path import join, dirname, exists
from datetime import datetime


LOG_DIRNAME = "logs"
FILENAME_PATTERN = "{0:04d}{1:02d}{2:02d}-{3:02d}{4:02d}{5:02d}.log"
FORMATTER = "%(asctime)-12s %(levelname)-8s: %(message)s"


def get_filename():
    now = datetime.now()
    return FILENAME_PATTERN.format(
        now.year, now.month, now.day,
        now.hour, now.minute, now.second
    )


def init_logger():
    log_dir = join(dirname(argv[0]), LOG_DIRNAME)
    if not exists(log_dir):
        mkdir(log_dir)

    basicConfig(
        filename=join(log_dir, get_filename()),
        filemode="a",
        format=FORMATTER,
        level=DEBUG,
        encoding="utf-8"
    )

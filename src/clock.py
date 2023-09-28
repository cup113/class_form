from time import time, sleep

class Clock:
    def __init__(self, interval_second: float) -> None:
        self.interval = interval_second
        self.last_time = time()

    def wait(self):
        this_time = time()
        sleep(max(0.0, self.last_time + self.interval - this_time))
        self.last_time = this_time
"""Gestor de cálculo de posição temporal de cortina RF."""
import time
from enum import Enum


class TravelStatus(Enum):
    STOPPED = 0
    OPENING = 1
    CLOSING = 2


class TravelCalculator:
    def __init__(self, travel_time_down, travel_time_up):
        self.travel_time_down = travel_time_down
        self.travel_time_up = travel_time_up
        self._position = 0
        self._target = 0
        self._start_time = None
        self._direction = TravelStatus.STOPPED

    def start_moving(self, direction, target):
        self._direction = direction
        self._target = target
        self._start_time = time.time()

    def stop(self):
        self._update_position()
        self._direction = TravelStatus.STOPPED
        self._start_time = None

    def _update_position(self):
        if self._direction == TravelStatus.STOPPED or self._start_time is None:
            return

        elapsed = time.time() - self._start_time
        full_time = self.travel_time_up if self._direction == TravelStatus.OPENING else self.travel_time_down
        delta = (elapsed / full_time) * 100

        if self._direction == TravelStatus.OPENING:
            self._position = min(100, self._position + delta)
        else:
            self._position = max(0, self._position - delta)

        if abs(self._position - self._target) < 1:
            self._position = self._target
            self.stop()

    def current_position(self):
        self._update_position()
        return int(self._position)

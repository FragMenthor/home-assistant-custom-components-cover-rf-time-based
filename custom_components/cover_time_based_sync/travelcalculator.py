# custom_components/cover_time_based_sync/travelcalculator.py
"""
TravelCalculator: cálculo preditivo de posição (0–100) para cover baseada em tempo.

- Baseado no conceito do XKNX (travelcalculator) e forks de covers time-based;
- Usa time.monotonic() para robustez a ajustes de relógio;
- Não tem side-effects no método current_position() — leitura pura do estado calculado.
"""
from __future__ import annotations

from enum import Enum
import time
from typing import Optional


class PositionType(Enum):
    """Tipo de posição conhecida/calc."""
    UNKNOWN = 1
    CALCULATED = 2
    CONFIRMED = 3


class TravelStatus(Enum):
    """Estado de deslocação."""
    DIRECTION_UP = 1   # a aumentar posição (→ 100)
    DIRECTION_DOWN = 2 # a diminuir posição (→ 0)
    STOPPED = 3


def _clamp(val: float, low: float, high: float) -> float:
    return max(low, min(high, val))


class TravelCalculator:
    """Calcula a posição corrente de uma cover com base nos tempos de viagem."""

    # 0 = fechado; 100 = totalmente aberto
    POSITION_CLOSED = 0.0
    POSITION_OPEN = 100.0

    def __init__(self, travel_time_down: float, travel_time_up: float) -> None:
        """travel_time_* em segundos."""
        self.position_type: PositionType = PositionType.UNKNOWN
        self.last_known_position: float = float(self.POSITION_CLOSED)
        self.travel_time_down: float = float(travel_time_down)
        self.travel_time_up: float = float(travel_time_up)
        self.travel_to_position: float = float(self.POSITION_CLOSED)
        self.travel_started_time: float = 0.0
        self.travel_direction: TravelStatus = TravelStatus.STOPPED
        self.start_position: float = float(self.POSITION_CLOSED)
        # Quando uma fonte externa define explicitamente a posição
        self.time_set_from_outside: Optional[float] = None

    # ---------- Controlo de estado ----------
    def set_position(self, position: float) -> None:
        """Define posição conhecida (confirma)."""
        pos = _clamp(position, self.POSITION_CLOSED, self.POSITION_OPEN)
        self.last_known_position = pos
        self.start_position = pos
        self.travel_to_position = pos
        self.travel_direction = TravelStatus.STOPPED
        self.position_type = PositionType.CONFIRMED
        self.time_set_from_outside = self.current_time()

    def stop(self) -> None:
        """Interrompe deslocação e fixa a posição corrente como última conhecida."""
        self.last_known_position = self.current_position()
        self.start_position = self.last_known_position
        self.travel_to_position = self.last_known_position
        self.position_type = PositionType.CALCULATED
        self.travel_direction = TravelStatus.STOPPED

    def start_travel(self, travel_to_position: float) -> None:
        """Inicia deslocação até 'travel_to_position' (0–100)."""
        # Normaliza antes de decidir direção
        target = _clamp(travel_to_position, self.POSITION_CLOSED, self.POSITION_OPEN)
        current = self.current_position()

        # Se já estamos no alvo, só garante estado consistente
        if abs(target - current) < 0.0001:
            self.set_position(target)
            return

        # Inicializa deslocação
        self.start_position = current
        self.travel_to_position = target
        self.travel_started_time = self.current_time()
        self.position_type = PositionType.CALCULATED
        self.travel_direction = (
            TravelStatus.DIRECTION_UP if target > current else TravelStatus.DIRECTION_DOWN
        )

    # ---------- Cálculo de posição ----------
    def current_position(self) -> float:
        """Devolve posição atual estimada (0–100). Não tem side-effects."""
        if self.travel_direction is TravelStatus.STOPPED:
            return _clamp(self.last_known_position, self.POSITION_CLOSED, self.POSITION_OPEN)

        elapsed = self.elapsed()
        start = self.start_position
        target = self.travel_to_position

        if self.travel_direction is TravelStatus.DIRECTION_UP:
            # subir → posição aumenta até target (máx. 100)
            duration = max(self.travel_time_up, 0.000001)
            # delta de percentagem em função do tempo transcorrido: 100%/duration * elapsed
            delta = (elapsed / duration) * 100.0
            pos = start + delta
            if pos >= target:
                return float(target)
            return _clamp(pos, self.POSITION_CLOSED, self.POSITION_OPEN)

        # DIRECTION_DOWN
        duration = max(self.travel_time_down, 0.000001)
        delta = (elapsed / duration) * 100.0
        pos = start - delta
        if pos <= target:
            return float(target)
        return _clamp(pos, self.POSITION_CLOSED, self.POSITION_OPEN)

    # ---------- Utilitários ----------
    @staticmethod
    def current_time() -> float:
        """Tempo monotónico (segundos)."""
        return time.monotonic()

    def elapsed(self) -> float:
        """Segundos decorridos desde o início da deslocação (ou 0)."""
        if self.travel_direction is TravelStatus.STOPPED:
            return 0.0
        return max(0.0, self.current_time() - self.travel_started_time)

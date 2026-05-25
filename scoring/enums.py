"""Domain enums shared by the engine and the Django models."""
from __future__ import annotations

from enum import Enum, IntEnum


class Market(str, Enum):
    """The three markets a game offers. A user holds at most one pick per market."""
    TOTALS = "totals"
    SPREAD = "spread"
    MONEYLINE = "moneyline"


class BetType(IntEnum):
    """The 6 bet types, preserving the legacy numeric codes."""
    OVER = 1
    UNDER = 2
    HOME_LINE = 3      # run line / spread, home side
    AWAY_LINE = 4      # run line / spread, away side
    HOME_ML = 5        # money line, home
    AWAY_ML = 6        # money line, away

    @property
    def market(self) -> Market:
        return {
            BetType.OVER: Market.TOTALS,
            BetType.UNDER: Market.TOTALS,
            BetType.HOME_LINE: Market.SPREAD,
            BetType.AWAY_LINE: Market.SPREAD,
            BetType.HOME_ML: Market.MONEYLINE,
            BetType.AWAY_ML: Market.MONEYLINE,
        }[self]

    @property
    def is_home(self) -> bool:
        return self in (BetType.HOME_LINE, BetType.HOME_ML)


class Outcome(str, Enum):
    PENDING = "pending"
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"      # first-class — fixes the legacy "push scored as loss" bug

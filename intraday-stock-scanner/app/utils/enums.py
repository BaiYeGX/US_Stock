from enum import Enum


class _StrEnum(str, Enum):
    pass


class Side(_StrEnum):
    LONG = "long"
    SHORT = "short"


class SetupName(_StrEnum):
    ORB = "ORB"
    VWAP_RECLAIM = "VWAP_RECLAIM"
    HOD_BREAKOUT = "HOD_BREAKOUT"


class Regime(_StrEnum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    CHOPPY = "choppy"

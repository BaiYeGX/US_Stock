from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class WebsocketStats:
    connected: bool = False
    subscribed_count: int = 0
    reconnect_count: int = 0
    last_message_ts: float | None = None
    last_disconnect_ts: float | None = None


@dataclass
class RequestBudgetManager:
    """Track REST and WebSocket usage separately."""

    rest_timestamps: deque[float] = field(default_factory=deque)
    per_second_timestamps: deque[float] = field(default_factory=deque)
    websocket: WebsocketStats = field(default_factory=WebsocketStats)
    throttled: bool = False

    soft_limit_per_min: int = 40
    hard_limit_per_min: int = 60
    max_per_second: int = 5

    def record_rest(self) -> None:
        now = time.time()
        self.rest_timestamps.append(now)
        self.per_second_timestamps.append(now)
        self._gc(now)
        self.throttled = self.rest_per_minute() >= self.soft_limit_per_min

    def _gc(self, now: float) -> None:
        while self.rest_timestamps and now - self.rest_timestamps[0] > 60:
            self.rest_timestamps.popleft()
        while self.per_second_timestamps and now - self.per_second_timestamps[0] > 1:
            self.per_second_timestamps.popleft()

    def can_call_rest(self) -> bool:
        now = time.time()
        self._gc(now)
        if len(self.per_second_timestamps) >= self.max_per_second:
            return False
        if len(self.rest_timestamps) >= self.hard_limit_per_min:
            return False
        return True

    def rest_per_minute(self) -> int:
        self._gc(time.time())
        return len(self.rest_timestamps)

    def rest_per_second(self) -> int:
        self._gc(time.time())
        return len(self.per_second_timestamps)

    def update_ws_connected(self, connected: bool) -> None:
        if not connected:
            self.websocket.last_disconnect_ts = time.time()
        self.websocket.connected = connected

    def update_ws_subscribed(self, count: int) -> None:
        self.websocket.subscribed_count = count

    def record_ws_message(self) -> None:
        self.websocket.last_message_ts = time.time()

    def record_ws_reconnect(self) -> None:
        self.websocket.reconnect_count += 1

    def snapshot(self) -> dict:
        return {
            "rest_per_min": self.rest_per_minute(),
            "rest_per_sec": self.rest_per_second(),
            "throttled": self.throttled,
            "ws_connected": self.websocket.connected,
            "ws_subscribed_count": self.websocket.subscribed_count,
            "ws_reconnect_count": self.websocket.reconnect_count,
            "ws_last_message_ts": self.websocket.last_message_ts,
            "ws_last_disconnect_ts": self.websocket.last_disconnect_ts,
        }

"""Data models for aioharmanluxury."""

from dataclasses import dataclass


@dataclass(slots=True)
class DeviceInfo:
    """Static device identity."""

    serial: str
    model: str
    name: str
    mac: str


@dataclass(slots=True)
class HarmanLuxuryState:
    """A snapshot of the live player state."""

    online: bool
    volume: int
    muted: bool
    play_state: str  # "playing" | "paused" | "stopped" | ...
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    art_url: str | None = None
    duration: float | None = None  # seconds
    position: float | None = None  # seconds
    can_play: bool = False
    can_pause: bool = False
    can_stop: bool = False
    can_next: bool = False
    can_previous: bool = False

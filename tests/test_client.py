"""Tests for the Harman Luxury client."""

from typing import Any

import pytest
from aiohttp import ClientError

from aioharmanluxury import HarmanLuxuryClient, HarmanLuxuryConnectionError

HOST = "1.2.3.4"

GETDATA_RESPONSES: dict[str, Any] = {
    "settings:/system/serialNumber": [{"type": "string_", "string_": "serial-123"}],
    "settings:/system/modelName": [{"type": "string_", "string_": "ARCAM ST5"}],
    "settings:/deviceName": [{"type": "string_", "string_": "Dining Room"}],
    "settings:/system/primaryMacAddress": [
        {"type": "string_", "string_": "02:FE:6C:B7:EB:59"}
    ],
    "powermanager:target": [
        {"type": "powerTarget", "powerTarget": {"target": "online"}}
    ],
    "player:volume": [{"type": "i32_", "i32_": 45}],
    "settings:/mediaPlayer/mute": [{"type": "bool_", "bool_": False}],
    "player:player/data/playTime": [{"type": "i64_", "i64_": 42000}],
    "player:player/data/value": [
        {
            "playLogicData": {
                "state": "playing",
                "trackRoles": {
                    "title": "Necessary Evil",
                    "icon": "http://1.2.3.4/art.jpg",
                    "mediaData": {
                        "metaData": {
                            "artist": "Motionless In White",
                            "album": "Graveyard Shift",
                        },
                        "activeResource": {"duration": 228000},
                    },
                },
                "controls": {"pause": True, "next_": True, "previous": True},
                "status": {"duration": 228000},
            },
            "type": "playLogicData",
        }
    ],
}


class _FakeResponse:
    """Minimal aiohttp response stand-in usable as an async context manager."""

    def __init__(self, payload: Any = None, exc: Exception | None = None) -> None:
        self._payload = payload
        self._exc = exc

    async def __aenter__(self) -> "_FakeResponse":
        if self._exc is not None:
            raise self._exc
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    def raise_for_status(self) -> None:
        """No-op; a real failure is simulated via ``exc``."""

    async def json(self, content_type: str | None = None) -> Any:
        return self._payload


class _FakeSession:
    """A stand-in aiohttp session backed by canned responses."""

    def __init__(
        self,
        get_responses: dict[str, Any] | None = None,
        get_exc: Exception | None = None,
        post_exc: Exception | None = None,
    ) -> None:
        self._get_responses = get_responses or {}
        self._get_exc = get_exc
        self._post_exc = post_exc
        self.posts: list[dict[str, Any]] = []

    def get(
        self, url: str, params: dict[str, str], ssl: bool
    ) -> _FakeResponse:
        if self._get_exc is not None:
            return _FakeResponse(exc=self._get_exc)
        return _FakeResponse(payload=self._get_responses[params["path"]])

    def post(self, url: str, json: dict[str, Any], ssl: bool) -> _FakeResponse:
        self.posts.append(json)
        return _FakeResponse(payload=True, exc=self._post_exc)


def _client(session: _FakeSession) -> HarmanLuxuryClient:
    return HarmanLuxuryClient(HOST, session)  # type: ignore[arg-type]


async def test_async_get_info() -> None:
    """Test reading static device identity."""
    info = await _client(_FakeSession(GETDATA_RESPONSES)).async_get_info()
    assert info.serial == "serial-123"
    assert info.model == "ARCAM ST5"
    assert info.name == "Dining Room"
    assert info.mac == "02:FE:6C:B7:EB:59"


async def test_async_get_state() -> None:
    """Test parsing the live player state."""
    state = await _client(_FakeSession(GETDATA_RESPONSES)).async_get_state()
    assert state.online is True
    assert state.volume == 45
    assert state.muted is False
    assert state.play_state == "playing"
    assert state.title == "Necessary Evil"
    assert state.artist == "Motionless In White"
    assert state.album == "Graveyard Shift"
    assert state.art_url == "http://1.2.3.4/art.jpg"
    assert state.duration == 228
    assert state.position == 42
    assert state.can_pause is True
    assert state.can_next is True
    assert state.can_previous is True


async def test_get_state_standby() -> None:
    """Test that a non-online power target reports offline."""
    responses = dict(GETDATA_RESPONSES)
    responses["powermanager:target"] = [
        {"type": "powerTarget", "powerTarget": {"target": "networkStandby"}}
    ]
    state = await _client(_FakeSession(responses)).async_get_state()
    assert state.online is False


async def test_get_state_stopped() -> None:
    """Test a stopped source yields no metadata."""
    responses = dict(GETDATA_RESPONSES)
    responses["player:player/data/value"] = [
        {"playLogicData": {"state": "stopped"}, "type": "playLogicData"}
    ]
    responses["player:player/data/playTime"] = [{"type": "i64_", "i64_": 0}]
    state = await _client(_FakeSession(responses)).async_get_state()
    assert state.play_state == "stopped"
    assert state.title is None
    assert state.duration is None
    assert state.position is None
    assert state.can_pause is False


@pytest.mark.parametrize(
    ("volume", "expected"),
    [(200, 99), (-5, 0), (40, 40)],
)
async def test_set_volume_clamps(volume: int, expected: int) -> None:
    """Test that setting the volume clamps to the device range."""
    session = _FakeSession()
    await _client(session).async_set_volume(volume)
    assert session.posts == [
        {
            "path": "player:volume",
            "role": "value",
            "value": {"type": "i32_", "i32_": expected},
        }
    ]


async def test_set_mute() -> None:
    """Test muting posts the right payload."""
    session = _FakeSession()
    await _client(session).async_set_mute(True)
    assert session.posts == [
        {
            "path": "settings:/mediaPlayer/mute",
            "role": "value",
            "value": {"type": "bool_", "bool_": True},
        }
    ]


async def test_control_uses_activate_role() -> None:
    """Test transport control posts with the activate role."""
    session = _FakeSession()
    await _client(session).async_control("pause")
    assert session.posts == [
        {
            "path": "player:player/control",
            "role": "activate",
            "value": {"control": "pause"},
        }
    ]


async def test_connection_error() -> None:
    """Test that a transport error is wrapped."""
    session = _FakeSession(get_exc=ClientError("boom"))
    with pytest.raises(HarmanLuxuryConnectionError):
        await _client(session).async_get_info()


async def test_write_error() -> None:
    """Test that a write transport error is wrapped."""
    session = _FakeSession(post_exc=ClientError("boom"))
    with pytest.raises(HarmanLuxuryConnectionError):
        await _client(session).async_set_volume(40)

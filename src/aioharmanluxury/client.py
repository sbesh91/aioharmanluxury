"""Async client for the Harman Luxury / StreamUnlimited StreamSDK local API.

The device serves an unauthenticated JSON API at ``https://<host>/api``:

* ``getData``  read a node (``roles=value`` returns ``[{"type":"X_","X_":val}]``)
* ``setData``  write a node (role ``value`` for typed values, role ``activate``
  for player control actions)

It is served over HTTPS with a device self-signed certificate, so TLS
verification is disabled on every request.
"""

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from . import const
from .exceptions import HarmanLuxuryConnectionError
from .models import DeviceInfo, HarmanLuxuryState

# The device is on the local network and answers promptly; cap every request
# so an unresponsive device cannot stall setup or polling for minutes.
_REQUEST_TIMEOUT = ClientTimeout(total=10)


class HarmanLuxuryClient:
    """Async client for a single Harman Luxury device."""

    def __init__(self, host: str, session: ClientSession) -> None:
        """Initialize the client for ``host`` using the shared ``session``."""
        self._base = f"https://{host}/api"
        self._session = session
        # The device serializes control on a single session; ensure at most one
        # request is in flight at a time regardless of how callers interleave.
        self._lock = asyncio.Lock()

    async def _get(self, path: str) -> Any:
        """Return the raw value object for ``path`` (roles=value)."""
        try:
            async with (
                self._lock,
                self._session.get(
                    f"{self._base}/getData",
                    params={"path": path, "roles": "value", "_nocache": "1"},
                    ssl=False,
                    timeout=_REQUEST_TIMEOUT,
                ) as resp,
            ):
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (ClientError, TimeoutError) as err:
            raise HarmanLuxuryConnectionError(f"Error reading {path}: {err}") from err
        if isinstance(data, list) and data:
            return data[0]
        return data

    async def _post(self, path: str, role: str, value: Any) -> None:
        """Write ``value`` to ``path`` under ``role``."""
        try:
            async with (
                self._lock,
                self._session.post(
                    f"{self._base}/setData",
                    json={"path": path, "role": role, "value": value},
                    ssl=False,
                    timeout=_REQUEST_TIMEOUT,
                ) as resp,
            ):
                resp.raise_for_status()
        except (ClientError, TimeoutError) as err:
            raise HarmanLuxuryConnectionError(f"Error writing {path}: {err}") from err

    @staticmethod
    def _scalar(value: Any, key: str, default: Any = None) -> Any:
        """Pull a typed scalar (e.g. ``i32_``/``bool_``/``string_``) out."""
        if isinstance(value, dict):
            return value.get(key, default)
        return default

    async def async_get_info(self) -> DeviceInfo:
        """Return static device identity."""
        serial = self._scalar(await self._get(const.SERIAL), "string_", "")
        model = self._scalar(await self._get(const.MODEL), "string_", "")
        name = self._scalar(await self._get(const.NAME), "string_", "")
        mac = self._scalar(await self._get(const.MAC), "string_", "")
        return DeviceInfo(serial=serial, model=model, name=name, mac=mac)

    async def async_get_state(self) -> HarmanLuxuryState:
        """Return a fresh snapshot of the live player state."""
        power = await self._get(const.POWER)
        target = None
        if isinstance(power, dict):
            target = (power.get("powerTarget") or {}).get("target")

        volume = int(self._scalar(await self._get(const.VOLUME), "i32_", 0))
        muted = bool(self._scalar(await self._get(const.MUTE), "bool_", False))

        data = await self._get(const.PLAYER_DATA)
        play = data.get("playLogicData", {}) if isinstance(data, dict) else {}
        state = play.get("state", "stopped")

        track = play.get("trackRoles", {}) or {}
        media_data = track.get("mediaData", {}) or {}
        meta = media_data.get("metaData", {}) or {}
        active = media_data.get("activeResource", {}) or {}
        controls = play.get("controls", {}) or {}

        duration_ms = active.get("duration") or (play.get("status", {}) or {}).get(
            "duration"
        )
        position_ms = self._scalar(await self._get(const.PLAY_TIME), "i64_")

        return HarmanLuxuryState(
            online=target == const.POWER_ONLINE,
            volume=volume,
            muted=muted,
            play_state=state,
            title=track.get("title"),
            artist=meta.get("artist"),
            album=meta.get("album"),
            art_url=track.get("icon"),
            duration=duration_ms / 1000 if duration_ms else None,
            position=position_ms / 1000 if position_ms is not None else None,
            can_play=bool(controls.get("play")),
            can_pause=bool(controls.get("pause")),
            can_stop=bool(controls.get("stop")),
            can_next=bool(controls.get("next_")),
            can_previous=bool(controls.get("previous")),
        )

    async def async_set_volume(self, volume: int) -> None:
        """Set absolute volume (0..99)."""
        volume = max(0, min(const.VOLUME_MAX, volume))
        await self._post(const.VOLUME, "value", {"type": "i32_", "i32_": volume})

    async def async_set_mute(self, mute: bool) -> None:
        """Mute or unmute the output."""
        await self._post(const.MUTE, "value", {"type": "bool_", "bool_": mute})

    async def async_control(self, command: str) -> None:
        """Send a transport command (play/pause/stop/next/previous).

        Power is read-only on this platform (``powermanager:target`` rejects
        writes), so on/off cannot be driven over the network.
        """
        await self._post(const.PLAYER_CONTROL, "activate", {"control": command})

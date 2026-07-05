# aioharmanluxury

Async Python client for **Harman Luxury Audio** network streamers built on the
**StreamUnlimited StreamSDK** platform, including the Arcam Radia **ST5**/ST60,
JBL, and Mark Levinson streamers.

It talks to the device's local JSON API (`https://<host>/api`) to read live
player state and drive volume, mute, and transport.

## Install

```bash
pip install aioharmanluxury
```

## Usage

```python
import aiohttp
from aioharmanluxury import HarmanLuxuryClient


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        client = HarmanLuxuryClient("192.168.1.86", session)

        info = await client.async_get_info()
        print(info.model, info.name)  # ARCAM ST5 Dining Room

        state = await client.async_get_state()
        print(state.play_state, state.title, state.artist)

        await client.async_set_volume(40)
        await client.async_set_mute(False)
        await client.async_control("pause")
```

## Notes

- The device uses a self-signed certificate; the client disables TLS
  verification for every request.
- The API is unauthenticated on the local network.
- Power is read-only (`powermanager:target` rejects writes), so on/standby can
  be observed via `state.online` but not driven remotely.
- Transport availability is source-dependent: Spotify Connect and AirPlay are
  sender-controlled, so `state.can_pause` / `can_next` / `can_previous` reflect
  what the active source currently allows.

## License

MIT

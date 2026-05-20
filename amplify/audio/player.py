import io
import logging
from typing import Optional

import httpx
import sounddevice as sd
import soundfile as sf
from threading import Thread

logger = logging.getLogger(__name__)


class AudioPlayer:
    def __init__(self):
        self.current_stream = None
        self.playback_thread = None
        self.is_playing = False

    def play_url(
        self,
        url: str,
        device_id: Optional[int] = None,
        volume: float = 1.0,
    ) -> None:
        if self.is_playing:
            self.stop()

        self.playback_thread = Thread(
            target=self._stream_and_play,
            args=(url, device_id, volume),
            daemon=True,
        )
        self.playback_thread.start()

    def _stream_and_play(
        self,
        url: str,
        device_id: Optional[int],
        volume: float,
    ) -> None:
        try:
            self.is_playing = True
            logger.debug(f"Fetching audio from {url}")

            with httpx.stream("GET", url, timeout=30.0) as response:
                response.raise_for_status()
                audio_data = response.content

            logger.debug("Decoding audio data")
            audio_buffer = io.BytesIO(audio_data)
            data, samplerate = sf.read(audio_buffer)

            data = data * volume

            logger.debug(f"Playing to device {device_id}")
            sd.play(data, samplerate=samplerate, device=device_id, blocking=True)
            logger.debug("Playback complete")

        except Exception as e:
            logger.error(f"Playback error: {e}")
        finally:
            self.is_playing = False

    def stop(self) -> None:
        try:
            sd.stop()
            self.is_playing = False
            logger.debug("Playback stopped")
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")

    def get_output_devices(self) -> list[dict]:
        devices = sd.query_devices()
        output_devices = []

        if isinstance(devices, dict):
            devices = [devices]

        for i, device in enumerate(devices):
            if device.get("max_output_channels", 0) > 0:
                output_devices.append(
                    {
                        "id": i,
                        "name": device.get("name", "Unknown"),
                        "channels": device.get("max_output_channels", 0),
                    }
                )

        return output_devices

    def get_default_output_device(self) -> Optional[int]:
        try:
            return sd.default.device[1]
        except Exception:
            return None

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class AudioRouter:
    SINK_NAME = "amplify_virtual_mic"
    SINK_DESCRIPTION = "Amplify Virtual Microphone"

    def __init__(self):
        self.null_sink_name: Optional[str] = None
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        try:
            subprocess.run(
                ["pactl", "info"],
                capture_output=True,
                timeout=2,
                check=True,
            )
            try:
                subprocess.run(
                    ["pw-cli", "info", "0"],
                    capture_output=True,
                    timeout=2,
                    check=True,
                )
                logger.info("Using PipeWire backend")
                return "pipewire"
            except (FileNotFoundError, subprocess.CalledProcessError):
                logger.info("Using PulseAudio backend")
                return "pulseaudio"
        except (FileNotFoundError, subprocess.CalledProcessError):
            logger.warning("No audio backend detected")
            return "none"

    def create_null_sink(self) -> bool:
        if self._backend == "pipewire":
            return self._create_pipewire_sink()
        elif self._backend == "pulseaudio":
            return self._create_pulseaudio_sink()
        else:
            logger.warning("Cannot create null sink: no audio backend available")
            return False

    def _create_pipewire_sink(self) -> bool:
        try:
            cmd = [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={self.SINK_NAME}",
                f"sink_properties=device.description={self.SINK_DESCRIPTION}",
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.null_sink_name = self.SINK_NAME
            logger.info(f"Created PipeWire null sink: {self.null_sink_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create PipeWire null sink: {e.stderr}")
            return False

    def _create_pulseaudio_sink(self) -> bool:
        try:
            cmd = [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={self.SINK_NAME}",
                f"sink_properties=device.description={self.SINK_DESCRIPTION}",
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.null_sink_name = self.SINK_NAME
            logger.info(f"Created PulseAudio null sink: {self.null_sink_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create PulseAudio null sink: {e.stderr}")
            return False

    def destroy_null_sink(self) -> bool:
        if not self.null_sink_name:
            logger.debug("No null sink to destroy")
            return True

        try:
            cmd = ["pactl", "set-sink-mute", self.SINK_NAME, "true"]
            subprocess.run(cmd, capture_output=True, timeout=5, check=False)

            result = subprocess.run(
                ["pactl", "list", "modules"],
                capture_output=True,
                text=True,
                check=True,
            )

            for line in result.stdout.split("\n"):
                if (
                    "module-null-sink" in line and self.SINK_NAME in result.stdout
                ):
                    if line.startswith("Module #"):
                        module_id = line.split("#")[1].strip()
                        unload_cmd = ["pactl", "unload-module", module_id]
                        subprocess.run(unload_cmd, capture_output=True, check=True)
                        logger.info(f"Destroyed null sink: {self.null_sink_name}")
                        self.null_sink_name = None
                        return True

            logger.warning(f"Could not find null sink module to destroy")
            return False

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to destroy null sink: {e.stderr}")
            return False

    def get_null_sink_id(self) -> Optional[int]:
        if not self.null_sink_name:
            return None

        try:
            import sounddevice as sd

            devices = sd.query_devices()
            if isinstance(devices, dict):
                devices = [devices]

            for i, device in enumerate(devices):
                if self.SINK_NAME in device.get("name", ""):
                    logger.debug(f"Found null sink at device index {i}")
                    return i

            logger.warning(f"Null sink {self.SINK_NAME} not found in device list")
            return None

        except Exception as e:
            logger.error(f"Failed to get null sink ID: {e}")
            return None

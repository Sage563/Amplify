import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)

SOUNDS_URL = "https://cdn.jsdelivr.net/gh/Sage563/Amplify@master/sounds.txt"
BASE_CDN_URL = "https://mathactivities.github.io/sd"


class SoundList:
    def __init__(self):
        self.sounds: List[str] = []
        self.last_error: str = ""

    def fetch(self) -> bool:
        try:
            logger.info(f"Fetching sounds from {SOUNDS_URL}")
            response = httpx.get(SOUNDS_URL, timeout=10.0)
            response.raise_for_status()

            self.sounds = [
                line.strip() for line in response.text.split("\n") if line.strip()
            ]

            logger.info(f"Loaded {len(self.sounds)} sounds")
            return True

        except httpx.RequestError as e:
            self.last_error = f"Network error: {e}"
            logger.error(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"Error fetching sounds: {e}"
            logger.error(self.last_error)
            return False

    def get_sounds(self) -> List[str]:
        return self.sounds.copy()

    def get_sound_url(self, filename: str) -> str:
        return f"{BASE_CDN_URL}/{filename}"

    def search(self, query: str) -> List[str]:
        query_lower = query.lower()
        return [s for s in self.sounds if query_lower in s.lower()]

    def filter_by_extension(self, extension: str) -> List[str]:
        ext = f".{extension.lstrip('.')}"
        return [s for s in self.sounds if s.endswith(ext)]

from __future__ import annotations

from typing import Any

import aiohttp


class HttpPrimer:
    def __init__(self, url: str, timeout_s: float = 5.0):
        self.url = str(url or "").strip()
        self.timeout_s = max(0.5, float(timeout_s or 5.0))
        if not self.url:
            raise ValueError("primer url is required")

    async def __call__(self, session_id: str, frame: dict[str, Any]) -> dict[str, Any]:
        payload = {"session_id": session_id, "frame": frame}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_s)) as session:
            async with session.post(self.url, json=payload) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"primer_status_{resp.status}")
                data = await resp.json()
        return data if isinstance(data, dict) else {"status": "ready"}

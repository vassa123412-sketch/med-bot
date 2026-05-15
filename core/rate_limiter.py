import time
from collections import defaultdict
from typing import Dict, List, Tuple


class RateStats:
    def __init__(self, limit: int = 30, window: int = 60):
        self.limit = limit
        self.window = window
        self._data: Dict[int, List[float]] = defaultdict(list)

    def record(self, user_id: int):
        now = time.time()
        self._data[user_id].append(now)

    def get_count(self, user_id: int, window: int = 60) -> int:
        cutoff = time.time() - window
        return sum(1 for t in self._data.get(user_id, []) if t > cutoff)

    def get_total_requests(self, seconds: int = 3600) -> int:
        cutoff = time.time() - seconds
        return sum(
            sum(1 for t in ts if t > cutoff)
            for ts in self._data.values()
        )

    def get_active_users(self, seconds: int = 300) -> int:
        cutoff = time.time() - seconds
        return sum(
            1 for ts in self._data.values()
            if any(t > cutoff for t in ts)
        )

    def get_top_users(self, n: int = 10, window: int = 3600) -> List[Tuple[int, int]]:
        cutoff = time.time() - window
        counts = []
        for uid, timestamps in self._data.items():
            c = sum(1 for t in timestamps if t > cutoff)
            if c > 0:
                counts.append((uid, c))
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:n]

    def get_all_user_stats(self, window: int = 3600) -> Dict[int, Dict]:
        cutoff = time.time() - window
        stats = {}
        for uid, timestamps in self._data.items():
            recent = [t for t in timestamps if t > cutoff]
            if recent:
                stats[uid] = {
                    "count": len(recent),
                    "first": recent[0],
                    "last": recent[-1],
                }
        return stats

    def cleanup(self, max_age: int = 86400):
        cutoff = time.time() - max_age
        for uid in list(self._data.keys()):
            self._data[uid] = [t for t in self._data[uid] if t > cutoff]
            if not self._data[uid]:
                del self._data[uid]


rate_stats = RateStats()

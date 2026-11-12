"""In-memory metrics registry for lightweight observability."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from prometheus_client import Counter, Histogram

from app.core.config import settings


def _metric_key(name: str, tags: dict[str, str] | None = None) -> str:
    if not tags:
        return name
    serialized = ",".join(f"{key}={tags[key]}" for key in sorted(tags))
    return f"{name}|{serialized}"


@dataclass(slots=True)
class _TimerAggregate:
    count: int = 0
    total: float = 0.0
    maximum: float = 0.0

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.maximum = max(self.maximum, value)

    def snapshot(self) -> dict[str, float | int]:
        average = self.total / self.count if self.count else 0.0
        return {
            "count": self.count,
            "avg": round(average, 4),
            "max": round(self.maximum, 4),
            "sum": round(self.total, 4),
        }


@dataclass(slots=True)
class MetricsRegistry:
    """Thread-safe in-memory metrics."""

    _MAX_KEYS: int = settings.metrics_max_keys

    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    timers: dict[str, _TimerAggregate] = field(default_factory=lambda: defaultdict(_TimerAggregate))
    _lock: Lock = field(default_factory=Lock)

    def increment(self, name: str, value: int = 1, tags: dict[str, str] | None = None) -> None:
        key = _metric_key(name, tags)
        with self._lock:
            if key not in self.counters and len(self.counters) >= self._MAX_KEYS:
                return
            self.counters[key] += value

    def observe(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        key = _metric_key(name, tags)
        with self._lock:
            if key not in self.timers and len(self.timers) >= self._MAX_KEYS:
                return
            self.timers[key].observe(value)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self.counters)
            timers = {key: timer.snapshot() for key, timer in self.timers.items()}
        uptime_seconds = (datetime.now(UTC) - self.started_at).total_seconds()
        return {
            "started_at": self.started_at,
            "uptime_seconds": round(uptime_seconds, 2),
            "counters": counters,
            "timers": timers,
        }


_registry = MetricsRegistry()
_prometheus_lock = Lock()
_prometheus_counters: dict[tuple[str, tuple[str, ...]], Counter] = {}
_prometheus_histograms: dict[tuple[str, tuple[str, ...]], Histogram] = {}


def _sanitize_metric_name(name: str) -> str:
    return name.replace(".", "_").replace("-", "_")


def _prometheus_metric(
    collection: dict[tuple[str, tuple[str, ...]], Counter | Histogram],
    factory,
    name: str,
    tags: dict[str, str] | None,
):
    label_names = tuple(sorted((tags or {}).keys()))
    key = (name, label_names)
    metric = collection.get(key)
    if metric is not None:
        return metric
    with _prometheus_lock:
        metric = collection.get(key)
        if metric is not None:
            return metric
        metric = factory(
            _sanitize_metric_name(name),
            f"VigilWeave metric {name}",
            labelnames=label_names,
        )
        collection[key] = metric
        return metric


def increment_metric(name: str, value: int = 1, tags: dict[str, str] | None = None) -> None:
    """Increment a counter metric."""

    _registry.increment(name, value=value, tags=tags)
    counter = _prometheus_metric(_prometheus_counters, Counter, name, tags)
    if tags:
        counter.labels(**tags).inc(value)
    else:
        counter.inc(value)


def observe_metric(name: str, value: float, tags: dict[str, str] | None = None) -> None:
    """Observe a timer metric value."""

    _registry.observe(name, value=value, tags=tags)
    histogram = _prometheus_metric(_prometheus_histograms, Histogram, name, tags)
    if tags:
        histogram.labels(**tags).observe(value)
    else:
        histogram.observe(value)


def snapshot_metrics() -> dict[str, object]:
    """Return full metric snapshot."""

    return _registry.snapshot()

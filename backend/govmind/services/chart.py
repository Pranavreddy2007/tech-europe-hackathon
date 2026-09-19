import asyncio
import logging
import time
from typing import Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ..config import get_settings  # noqa: E402
from ..schemas import ChartResult  # noqa: E402

log = logging.getLogger(__name__)

COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1"]
ChartType = Literal["bar", "line", "pie", "doughnut"]

# Set from the first inbound request when PUBLIC_BASE_URL isn't configured.
_inferred_base_url = ""


def remember_base_url(url: str) -> None:
    global _inferred_base_url
    if not _inferred_base_url:
        _inferred_base_url = url.rstrip("/")


def base_url() -> str:
    return (get_settings().public_base_url or _inferred_base_url or "http://localhost:8000").rstrip("/")


def _render(path, chart_type: ChartType, title: str, labels: list[str], datasets: list[dict]) -> None:
    labels = [label if len(label) <= 20 else label[:20] + "..." for label in labels]
    fig, ax = plt.subplots(figsize=(8, 5), dpi=100)
    if chart_type in ("pie", "doughnut"):
        data = datasets[0]["data"] if datasets else []
        wedge = {"width": 0.45} if chart_type == "doughnut" else None
        ax.pie(data, labels=labels, colors=COLORS[: len(data)], autopct="%1.0f%%", wedgeprops=wedge)
        ax.axis("equal")
    elif chart_type == "line":
        for i, ds in enumerate(datasets):
            ax.plot(labels, ds["data"], color=COLORS[i % len(COLORS)], linewidth=2, marker="o", label=ds["label"])
    else:
        n = max(len(datasets), 1)
        width = 0.8 / n
        for i, ds in enumerate(datasets):
            xs = [x + (i - (n - 1) / 2) * width for x in range(len(labels))]
            ax.bar(xs, ds["data"], width=width, color=COLORS[i % len(COLORS)], label=ds["label"])
        ax.set_xticks(range(len(labels)), labels, rotation=30 if len(labels) > 5 else 0, ha="right")
    if len(datasets) > 1 and chart_type in ("bar", "line"):
        ax.legend()
    ax.set_title(title, fontsize=16)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


async def generate(chart_type: ChartType, title: str, labels: list[str], datasets: list[dict]) -> ChartResult:
    chart_dir = get_settings().chart_dir
    chart_dir.mkdir(parents=True, exist_ok=True)
    name = f"chart_{int(time.time() * 1000)}.png"
    await asyncio.to_thread(_render, chart_dir / name, chart_type, title, labels, datasets)
    log.info("Chart generated: %s", name)
    return ChartResult(chart_url=f"{base_url()}/charts/{name}", file_name=name)

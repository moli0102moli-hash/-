"""Render simple mathematical and text-based videos."""

from __future__ import annotations

import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from moviepy import ImageClip, TextClip, CompositeVideoClip


def _safe_expression(expr: str) -> bool:
    allowed = set("sin cos tan exp log abs pi x0123456789 +-*/()., ")
    return all(ch in allowed for ch in expr.lower())


def make_math_video(
    expression: str,
    output_path: str | Path,
    duration: float = 6.0,
    fps: int = 24,
    x_min: float = -6.0,
    x_max: float = 6.0,
) -> None:
    if not _safe_expression(expression):
        raise ValueError(f"Unsafe expression: {expression}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames = int(duration * fps)
    x = np.linspace(x_min, x_max, 600)
    y = eval(expression, {"sin": math.sin, "cos": math.cos, "tan": math.tan, "exp": math.exp, "log": math.log, "abs": abs, "pi": math.pi}, {"x": x})

    y_min, y_max = float(np.min(y)), float(np.max(y))
    pad = (y_max - y_min) * 0.15 or 1.0

    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)
    ax.set_facecolor("#0b1020")
    fig.patch.set_facecolor("#0b1020")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min - pad, y_max + pad)
    ax.set_title(f"f(x) = {expression}", color="white", fontsize=18)
    ax.tick_params(colors="lightgray")
    for spine in ax.spines.values():
        spine.set_color("gray")

    line, = ax.plot([], [], color="#7df9ff", linewidth=3)
    point, = ax.plot([], [], marker="o", color="#ff6ec7", markersize=8)

    images = []
    for i in range(frames):
        progress = (i + 1) / frames
        cutoff = int(len(x) * progress)
        line.set_data(x[:cutoff], y[:cutoff])
        if cutoff > 0:
            point.set_data([x[cutoff - 1]], [y[cutoff - 1]])
        else:
            point.set_data([], [])

        frame_path = output_path.parent / f"_frame_{i:04d}.png"
        fig.savefig(frame_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        images.append(str(frame_path))

    plt.close(fig)

    clips = [ImageClip(img, duration=1 / fps) for img in images]
    video = CompositeVideoClip([CompositeVideoClip(clips)])
    video.write_videofile(str(output_path), fps=fps, codec="libx264", audio=False)

    for img in images:
        Path(img).unlink(missing_ok=True)


def make_text_video(text: str, output_path: str | Path, seconds_per_line: float = 2.0) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [line.strip() for line in re.split(r"[|｜]", text) if line.strip()]
    clips = []
    for line in lines:
        clip = TextClip(
            text=line,
            size=(1280, 720),
            color="white",
            font="Noto-Sans-CJK-SC",
            font_size=48,
            method="caption",
            text_align="center",
        ).with_duration(seconds_per_line)
        clips.append(clip)

    video = CompositeVideoClip([CompositeVideoClip(clips)])
    video.write_videofile(str(output_path), fps=24, codec="libx264", audio=False)

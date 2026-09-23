#!/usr/bin/env python3
"""Create a fresh daily video and email it to a recipient."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import smtplib
import ssl
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from email.message import EmailMessage
from pathlib import Path

STATE_PATH = Path("daily_video_state.json")
OUTPUT_DIR = Path("out")

THEMES = [
    "数学像一条发光的河，今天带你看见隐藏在波形里的秩序。",
    "一条曲线从黑暗里生长，像星河把公式慢慢写出来。",
    "今天的视频属于周期、对称和变化：美感来自重复中的细微差别。",
    "把时间交给函数，你会看到普通数字变成会呼吸的图案。",
    "今天让正弦、余弦和指数一起跳舞，画出一段安静的宇宙。",
    "一个公式，一束光，一段不断展开的轨迹。",
    "函数不是冷冰冰的符号，它也可以像音乐一样有节奏。",
    "今天的灵感：从简单规则里长出复杂而温柔的形状。",
]

EXPRESSIONS = [
    "sin(2*x) + 0.35*cos(7*x)",
    "sin(3*x) * cos(0.5*x)",
    "sin(x) + sin(2*x)/2 + sin(5*x)/5",
    "cos(4*x) + 0.25*sin(11*x)",
    "sin(x) * exp(-0.08*abs(x))",
    "sin(5*x) / (1 + 0.15*x*x)",
    "cos(x) + 0.4*cos(3*x) + 0.2*cos(9*x)",
    "sin(2*x) + 0.2*sin(13*x)",
]

TEXT_TEMPLATES = [
    "今天 8 点的灵感|{theme}|愿你下载到一点数学之美",
    "每日一段函数诗|{theme}|重复不会无聊，因为变化藏在细节里",
    "给今天的你|{theme}|这就是公式变成画面的瞬间",
]


@dataclass(frozen=True)
class DailyIdea:
    day: str
    kind: str
    theme: str
    expression: str
    output: Path


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"used_keys": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, object]) -> None:
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def choose_daily_idea(today: date, output_dir: Path, state_path: Path) -> DailyIdea:
    state = load_state(state_path)
    candidates: list[DailyIdea] = []
    for theme_index, theme in enumerate(THEMES):
        for expr_index, expression in enumerate(EXPRESSIONS):
            key = f"{theme_index}-{expr_index}"
            kind = "math" if (theme_index + expr_index + today.day) % 3 else "text"
            output = output_dir / f"daily_video_{today.isoformat()}_{key.replace('-', '_')}.mp4"
            candidates.append(DailyIdea(today.isoformat(), kind, theme, expression, output))

    order = list(range(len(candidates)))
    random.Random("daily-video-maker-v1").shuffle(order)
    day_number = today.toordinal()
    idea = candidates[order[day_number % len(order)]]

    used_keys = set(state.get("used_keys", []))
    used_keys.add(idea_key(idea))
    state["used_keys"] = sorted(used_keys)
    state["last_idea"] = {**asdict(idea), "output": str(idea.output)}
    state["cycle_length_days"] = len(order)
    save_state(state_path, state)
    return idea


def idea_key(idea: DailyIdea) -> str:
    return hashlib.sha1(f"{idea.theme}|{idea.expression}|{idea.kind}".encode("utf-8")).hexdigest()[:16]


def render_daily_video(idea: DailyIdea) -> Path:
    from video_maker import make_math_video, make_text_video

    idea.output.parent.mkdir(parents=True, exist_ok=True)
    if idea.kind == "math":
        make_math_video(idea.expression, idea.output, duration=8.0, x_min=-10.0, x_max=10.0)
    else:
        text = random.Random(idea.day).choice(TEXT_TEMPLATES).format(theme=idea.theme)
        make_text_video(text, idea.output, seconds_per_line=2.8)
    return idea.output


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def send_email(video_path: Path, idea: DailyIdea) -> None:
    smtp_host = require_env("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = require_env("SMTP_USER")
    smtp_password = require_env("SMTP_PASSWORD")
    mail_from = os.getenv("MAIL_FROM", smtp_user)
    mail_to = require_env("MAIL_TO")

    message = EmailMessage()
    message["Subject"] = f"[每日视频] 你的自动生成视频 - {idea.day}"
    message["From"] = mail_from
    message["To"] = mail_to
    message.set_content(
        "你好！\n\n"
        "今天 8 点的视频已经自动生成，见附件下载。\n\n"
        f"主题：{idea.theme}\n"
        f"类型：{idea.kind}\n"
        f"函数：{idea.expression}\n\n"
    )
    message.add_attachment(
        video_path.read_bytes(),
        maintype="video",
        subtype="mp4",
        filename=video_path.name,
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and email today's nonrepeating video.")
    parser.add_argument("--date", default=datetime.now(UTC).date().isoformat(), help="Date seed, format YYYY-MM-DD.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    parser.add_argument("--no-email", action="store_true", help="Only render the video; do not send email.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    today = date.fromisoformat(args.date)
    idea = choose_daily_idea(today, args.output_dir, args.state)
    video_path = render_daily_video(idea)
    if not args.no_email:
        send_email(video_path, idea)
    print(f"Created {video_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一手机推送工具（无硬编码密钥，全部走环境变量）。

支持的渠道（由 PUSH_CHANNEL 选择）：
  · serverchan  —— Server酱（微信）
      PUSH_CHANNEL=serverchan
      SERVERCHAN_KEY=SCT...        （必填）
  · telegram    —— Telegram Bot
      PUSH_CHANNEL=telegram
      TELEGRAM_BOT_TOKEN=123:abc   （必填）
      TELEGRAM_CHAT_ID=123456      （必填）

用法：
  # 推送文件内容
  python scripts/push_notification.py --file docs/watchlist_brief.md --title "Watchlist Brief"

  # 推送一段文本
  python scripts/push_notification.py --text "hello" --title "标题"

  # 只做通道检查（不发送）
  python scripts/push_notification.py --check

约定：
  · 环境变量缺失 ⇒ **打印警告并跳过，退出码 0**（绝不阻塞 workflow ✓）
  · 单条内容超过渠道上限时自动截断（Server酱 32KB / Telegram 4096 字符）✓
  · 仅用标准库（urllib），零第三方依赖 ✓
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

TIMEOUT = 20

SERVERCHAN_LIMIT = 30000
TELEGRAM_LIMIT = 3900


def _post_json(url: str, payload: dict) -> tuple:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return True, r.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _post_form(url: str, fields: dict) -> tuple:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return True, r.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def push_serverchan(send_key: str, title: str, content: str) -> tuple:
    """Server酱（微信推送）。send_key 形如 SCTxxxx。"""
    if not send_key:
        return False, "SERVERCHAN_KEY 缺失"
    if send_key.startswith("SCT"):
        url = f"https://sctapi.ftqq.com/{send_key}.send"
        return _post_form(url, {"title": title[:64], "desp": content[:SERVERCHAN_LIMIT]})
    url = f"https://sc.ftqq.com/{send_key}.send"
    return _post_form(url, {"text": title[:64], "desp": content[:SERVERCHAN_LIMIT]})


def push_telegram(bot_token: str, chat_id: str, content: str,
                  title: str = "") -> tuple:
    """Telegram Bot 推送。"""
    if not bot_token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 缺失"
    text = (f"*{title}*\n\n{content}" if title else content)[:TELEGRAM_LIMIT]
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    return _post_json(url, {"chat_id": chat_id, "text": text,
                            "parse_mode": "Markdown", "disable_web_page_preview": True})


def send(title: str, content: str) -> int:
    """按 PUSH_CHANNEL 分发。返回 0=成功或跳过，1=发送失败。"""
    channel = (os.environ.get("PUSH_CHANNEL") or "").strip().lower()
    if not channel:
        print("[push] ⚠️ 未设置 PUSH_CHANNEL，跳过推送（不算失败）")
        return 0

    if channel == "serverchan":
        key = (os.environ.get("SERVERCHAN_KEY") or "").strip()
        if not key:
            print("[push] ⚠️ PUSH_CHANNEL=serverchan 但 SERVERCHAN_KEY 缺失，跳过")
            return 0
        ok, msg = push_serverchan(key, title, content)
    elif channel == "telegram":
        tok = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        cid = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        if not tok or not cid:
            print("[push] ⚠️ PUSH_CHANNEL=telegram 但 TOKEN/CHAT_ID 缺失，跳过")
            return 0
        ok, msg = push_telegram(tok, cid, content, title)
    else:
        print(f"[push] ⚠️ 未知 PUSH_CHANNEL={channel}，跳过")
        return 0

    if ok:
        print(f"[push] ✅ 已通过 {channel} 发送：{title[:40]}（{len(content)} 字符）")
        return 0
    print(f"[push] ❌ {channel} 发送失败：{msg}")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="统一手机推送（环境变量配置，无硬编码密钥）")
    ap.add_argument("--file", help="要推送的文件路径（读取全文）")
    ap.add_argument("--text", help="要推送的文本")
    ap.add_argument("--title", default="US Terminal 通知")
    ap.add_argument("--check", action="store_true", help="只检查通道配置，不发送")
    args = ap.parse_args(argv)

    if args.check:
        ch = (os.environ.get("PUSH_CHANNEL") or "(未设置)").strip()
        keys = {k: ("已设置" if os.environ.get(k) else "缺失")
                for k in ("SERVERCHAN_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
        print(f"[push] channel = {ch}")
        for k, v in keys.items():
            print(f"[push] {k} = {v}")
        return 0

    content = ""
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"[push] ❌ 文件不存在：{args.file}")
            return 1
        content = p.read_text(encoding="utf-8-sig")
        if not args.title or args.title == "US Terminal 通知":
            args.title = p.stem
    elif args.text:
        content = args.text
    else:
        print("[push] 用法：--file <path> | --text <string> | --check")
        return 0

    return send(args.title, content)


if __name__ == "__main__":
    sys.exit(main())

import asyncio
import re

from telegram import Bot
from telegram.error import NetworkError, TimedOut


class DispatchLayer:
    """调度层：切片发送消息，模拟真人打字节奏"""

    def __init__(self):
        self.max_retries = 3
        self.retry_base_delay = 0.8
        self.segment_char_limit = 60

    def split_message(self, content: str, split_level: int) -> list[str]:
        """将内容切分成多段"""
        normalized = (content or "").strip()
        if not normalized:
            return [""]

        level = max(1, int(split_level or 2))
        if level == 1:
            return [normalized]

        # level 2: 按句号等强分隔符切分；超长句仅在单句内部补切，避免退化成过碎片段。
        strong_parts = self._split_by_delimiters(normalized, r"([。！？!?；;\n])")
        segments: list[str] = []
        for part in strong_parts:
            text = (part or "").strip()
            if not text:
                continue
            if len(text) <= self.segment_char_limit:
                segments.append(text)
                continue
            segments.extend(self._split_by_length(text, self.segment_char_limit))

        if not segments:
            return [normalized]

        # level 3: 目前先沿用 level 2，后续再追加“表情单独切分”。
        return segments

    def _split_by_delimiters(self, content: str, pattern: str) -> list[str]:
        parts = re.split(pattern, content)
        segments: list[str] = []
        current = ""
        delimiters = re.compile(pattern)
        for index, part in enumerate(parts):
            if part is None or part == "":
                continue
            current += part
            if delimiters.fullmatch(part) or index == len(parts) - 1:
                text = current.strip()
                if text:
                    segments.append(text)
                current = ""
        if current.strip():
            segments.append(current.strip())
        return segments

    def _split_by_length(self, content: str, limit: int) -> list[str]:
        text = (content or "").strip()
        if not text:
            return []
        if len(text) <= limit:
            return [text]

        segments: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + limit, len(text))
            if end < len(text):
                split_at = max(
                    text.rfind(mark, start, end)
                    for mark in ("，", "、", ",", "：", ":", " ")
                )
                if split_at > start + 6:
                    end = split_at + 1
            segment = text[start:end].strip()
            if segment:
                segments.append(segment)
            start = end
        return segments
    
    def calc_delay(self, text: str, factor: float) -> float:
        """计算打字延迟（毫秒）"""
        text = (text or "").strip()
        punctuation_bonus = len(re.findall(r"[，。！？、,.!?;；:：~…]", text)) * 100
        base_delay = len(text) * 95 + punctuation_bonus
        delay = base_delay * factor
        return max(1200, min(4200, delay))

    async def _retry_telegram_call(self, operation, *args, **kwargs):
        """对 Telegram 网络超时做轻量重试"""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except (TimedOut, NetworkError) as error:
                last_error = error
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(self.retry_base_delay * attempt)
        raise last_error
    
    async def dispatch(
        self,
        bot: Bot,
        chat_id: str,
        content: str,
        split_level: int,
        typing_delay_factor: float,
    ):
        """执行消息发送"""
        segments = self.split_message(content, split_level)

        for i, segment in enumerate(segments):
            delay_ms = self.calc_delay(segment, typing_delay_factor)
            await self._simulate_typing(
                bot=bot,
                chat_id=chat_id,
                delay_seconds=delay_ms / 1000,
            )

            await self._retry_telegram_call(
                bot.send_message,
                chat_id=chat_id,
                text=segment,
            )

            if i < len(segments) - 1:
                await asyncio.sleep(0.8)

    async def _simulate_typing(self, bot: Bot, chat_id: str, delay_seconds: float) -> None:
        remaining = max(0.0, delay_seconds)
        if remaining <= 0:
            return

        heartbeat = 3.5
        while remaining > 0:
            await self._retry_telegram_call(
                bot.send_chat_action,
                chat_id=chat_id,
                action="typing",
            )
            sleep_seconds = min(heartbeat, remaining)
            await asyncio.sleep(sleep_seconds)
            remaining -= sleep_seconds

dispatch_layer = DispatchLayer()

import argparse
import asyncio
import os
import sys
from typing import Optional

from openai import AsyncOpenAI

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency for simple probing
    load_dotenv = None


DEFAULT_PROMPT = "Reply with exactly: pong"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def mask_secret(value: Optional[str]) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe DeepSeek connectivity through its OpenAI-compatible API."
    )
    parser.add_argument("--api-key", help="DeepSeek API key. Defaults to env/.env.")
    parser.add_argument(
        "--model",
        default=None,
        help=f"Model name. Defaults to env/.env or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"Base URL. Defaults to env/.env or {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt sent to DeepSeek for connectivity validation.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds.",
    )
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> dict:
    if load_dotenv is not None:
        load_dotenv()
    api_key = (
        args.api_key
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("LLM_API_KEY")
    )
    model = args.model or os.getenv("LLM_MODEL") or DEFAULT_MODEL
    base_url = args.base_url or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL
    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
    }


def print_header(config: dict, prompt: str, timeout: float) -> None:
    print("=== DeepSeek Probe ===")
    print(f"DEEPSEEK_API_KEY={mask_secret(config['api_key'])}")
    print(f"LLM_MODEL={config['model']}")
    print(f"LLM_BASE_URL={config['base_url']}")
    print(f"timeout={timeout}")
    print(f"prompt={prompt!r}")
    print()


async def run_probe(config: dict, prompt: str, timeout: float) -> int:
    print("=== HTTP Probe ===")
    client = AsyncOpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"],
        timeout=timeout,
    )
    try:
        response = await client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": "You are a connectivity probe."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=32,
        )
        content = response.choices[0].message.content
        print("http_status=ok")
        print(f"http_response={content!r}")
        return 0
    except Exception as exc:
        print("http_status=error")
        print(f"http_error_type={type(exc).__module__}.{type(exc).__name__}")
        print(f"http_error={exc}")
        response = getattr(exc, "response", None)
        if response is not None:
            print(f"http_status_code={getattr(response, 'status_code', '<unknown>')}")
            try:
                print(f"http_response_text={response.text!r}")
            except Exception:
                pass
        return 1
    finally:
        await client.close()


def main() -> int:
    args = parse_args()
    config = load_config(args)
    if not config["api_key"]:
        print(
            "Missing DEEPSEEK_API_KEY or LLM_API_KEY in environment/.env.",
            file=sys.stderr,
        )
        return 2

    print_header(config, args.prompt, args.timeout)
    status = asyncio.run(run_probe(config, args.prompt, args.timeout))
    print()
    print("=== Summary ===")
    print(f"http_exit_code={status}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())

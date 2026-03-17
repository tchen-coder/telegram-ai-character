import argparse
import asyncio
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

try:
    from xai_sdk import Client as XAIClient
    from xai_sdk.chat import system
    from xai_sdk.chat import user
except ImportError:
    XAIClient = None
    system = None
    user = None


DEFAULT_PROMPT = "Reply with exactly: pong"


def mask_secret(value: Optional[str]) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def load_config() -> dict:
    load_dotenv()
    api_key = os.getenv("XAI_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL") or "grok-4-1-fast-reasoning"
    base_url = os.getenv("LLM_BASE_URL") or "https://api.x.ai/v1"
    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
    }


def print_header(config: dict, prompt: str, timeout: float) -> None:
    print("=== Grok Probe ===")
    print(f"XAI_API_KEY={mask_secret(config['api_key'])}")
    print(f"LLM_MODEL={config['model']}")
    print(f"LLM_BASE_URL={config['base_url']}")
    print(f"timeout={timeout}")
    print(f"prompt={prompt!r}")
    print()


def run_sdk_probe(config: dict, prompt: str) -> int:
    print("=== SDK Probe ===")
    if XAIClient is None:
        print("xai-sdk import failed; install requirements with Python 3.10+.")
        return 2

    try:
        client = XAIClient(api_key=config["api_key"], timeout=60.0)
        chat = client.chat.create(model=config["model"])
        chat.append(system("You are a connectivity probe."))
        chat.append(user(prompt))
        response = chat.sample()
        content = getattr(response, "content", None)
        print("sdk_status=ok")
        print(f"sdk_response={content!r}")
        return 0
    except Exception as exc:
        print("sdk_status=error")
        print(f"sdk_error_type={type(exc).__module__}.{type(exc).__name__}")
        print(f"sdk_error={exc}")
        return 1


async def run_http_probe(config: dict, prompt: str, timeout: float) -> int:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Grok connectivity through both xai-sdk and HTTP API."
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt sent to Grok for connectivity validation.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP request timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    if not config["api_key"]:
        print("Missing XAI_API_KEY or LLM_API_KEY in environment/.env.", file=sys.stderr)
        return 2

    print_header(config, args.prompt, args.timeout)
    sdk_status = run_sdk_probe(config, args.prompt)
    print()
    http_status = asyncio.run(run_http_probe(config, args.prompt, args.timeout))
    print()
    print("=== Summary ===")
    print(f"sdk_exit_code={sdk_status}")
    print(f"http_exit_code={http_status}")
    return 0 if sdk_status == 0 and http_status == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

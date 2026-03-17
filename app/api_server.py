import asyncio
import logging
import os

from app.api.handlers import BotAPIHandler
from app.api.server import BotAPIServer
from app.database.connection import close_database, init_database
from app.generation import generation_layer
from app.state_machine import state_machine

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    host = os.getenv("BOT_API_HOST", "0.0.0.0")
    port = int(os.getenv("BOT_API_PORT", "8090"))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_database())
    loop.run_until_complete(state_machine.connect())
    loop.run_until_complete(generation_layer.init())

    server = BotAPIServer((host, port), BotAPIHandler, loop)
    logger.info("Bot API listening on http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        loop.run_until_complete(generation_layer.close())
        loop.run_until_complete(state_machine.close())
        loop.run_until_complete(close_database())
        loop.close()


if __name__ == "__main__":
    main()

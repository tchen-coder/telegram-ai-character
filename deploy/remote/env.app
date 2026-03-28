# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
#TELEGRAM_PROXY=socks5://127.0.0.1:7890
#TELEGRAM_CONNECTION_POOL_SIZE=32
#TELEGRAM_CONNECT_TIMEOUT=20
#TELEGRAM_READ_TIMEOUT=30
#TELEGRAM_WRITE_TIMEOUT=30
#TELEGRAM_POOL_TIMEOUT=30

# LLM 配置
LLM_PROVIDER=grok
XAI_API_KEY=your_xai_api_key_here
LLM_API_KEY=
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4-1-fast-reasoning

# DeepSeek 配置示例
# LLM_PROVIDER=deepseek
# LLM_API_KEY=your_deepseek_api_key_here
# LLM_BASE_URL=https://api.deepseek.com
# LLM_MODEL=deepseek-chat

# Redis
REDIS_URL=redis://redis:6379/0

# MySQL
DATABASE_URL=mysql://root:password@mysql:3306/telegram_ai_character

# App
DEBUG=false
LOG_LEVEL=INFO

# Outbound proxy for Grok/xAI requests from containers on deploy_default.
HTTP_PROXY=http://172.18.0.1:7890
HTTPS_PROXY=http://172.18.0.1:7890
NO_PROXY=127.0.0.1,localhost,mysql,redis

import os
import sys

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI

load_dotenv()

_api_key = os.environ.get("OPENAI_API_KEY")

if not _api_key or _api_key.strip() == "":
    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  ERROR: OPENAI_API_KEY is not set.                           ║\n"
        "║                                                              ║\n"
        "║  1. Get a key at https://platform.openai.com/api-keys        ║\n"
        "║  2. Add it to api/.env:                                      ║\n"
        '║       OPENAI_API_KEY="sk-..."                                ║\n'
        "║  3. Restart the server.                                      ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n",
        file=sys.stderr,
    )
    sys.exit(1)

client = OpenAI(api_key=_api_key)
aclient = AsyncOpenAI(api_key=_api_key)

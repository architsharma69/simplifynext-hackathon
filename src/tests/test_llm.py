import os

import pytest
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")


@pytest.mark.skipif(not API_KEY, reason="OPENAI_API_KEY not set in .env")
def test_openai_key_is_valid():
    client = OpenAI(api_key=API_KEY)

    models = client.models.list()

    assert len(models.data) > 0


if __name__ == "__main__":
    client = OpenAI(api_key=API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say bye in exactly five words."}],
    )

    print(response)
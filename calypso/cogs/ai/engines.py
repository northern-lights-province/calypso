import os

from kani.engines.openai import OpenAIEngine

from calypso.config import DALLE_ORG_ID

CHAT_HYPERPARAMS = dict(
    model="gpt-4",
    temperature=1,
    top_p=0.95,
    frequency_penalty=0.3,
)

CHAT_4O_HYPERPARAMS = dict(
    model="gpt-4o",
    temperature=1,
    top_p=0.95,
    frequency_penalty=0.1,
)

api_key = os.getenv("OPENAI_API_KEY")
chat_engine = OpenAIEngine(api_key=api_key, **CHAT_HYPERPARAMS)
gpt_4o_engine = OpenAIEngine(api_key=api_key, organization=DALLE_ORG_ID, **CHAT_4O_HYPERPARAMS)
long_engine = OpenAIEngine(api_key=api_key, organization=DALLE_ORG_ID, model="gpt-4-turbo", temperature=0.1)

from kani.engines.openai import OpenAIEngine

from calypso import config

CHAT_4O_HYPERPARAMS = dict(
    model="gpt-4o",
    temperature=1,
    top_p=0.95,
    frequency_penalty=0.1,
)

chat_engine = OpenAIEngine(api_key=config.OPENAI_API_KEY, **CHAT_4O_HYPERPARAMS)

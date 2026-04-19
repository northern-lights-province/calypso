from kani.engines.anthropic import AnthropicEngine

from calypso import config

# CHAT_4O_HYPERPARAMS = dict(
#     model="gpt-4o",
#     temperature=1,
#     top_p=0.95,
#     frequency_penalty=0.1,
# )
#
# chat_engine = OpenAIEngine(api_key=config.OPENAI_API_KEY, **CHAT_4O_HYPERPARAMS)

CHAT_HYPERPARAMS = dict(
    model="claude-opus-4-7",
)

chat_engine = AnthropicEngine(api_key=config.ANTHROPIC_API_KEY, **CHAT_HYPERPARAMS)

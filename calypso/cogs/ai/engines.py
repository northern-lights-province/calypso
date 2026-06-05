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
    model="claude-opus-4-8",
    max_context_size=512000,
    max_tokens=64000,
)


class AnthropicServerToolsEngine(AnthropicEngine):
    def _prepare_request(self, messages, functions, *, intent: str = "create") -> tuple[dict, list]:
        kwargs, prompt_msgs = super()._prepare_request(messages, functions, intent=intent)
        # add server-side tools
        kwargs.setdefault("tools", [])
        kwargs["tools"].extend([
            {"type": "web_search_20250305", "name": "web_search", "max_uses": 5},
            {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 10},
            {"type": "memory_20250818", "name": "memory"},
        ])
        return kwargs, prompt_msgs

    async def prompt_len(self, messages, functions=None, **kwargs) -> int:
        if (cached_len := self.get_cached_prompt_len(messages, functions, **kwargs)) is not None:
            return cached_len

        predict_kwargs, prompt_msgs = self._prepare_request(messages, functions, intent="count_tokens")
        predict_kwargs["max_tokens"] = 0
        predict_kwargs.setdefault("cache_control", {"type": "ephemeral"})
        result = await self._messages_api.create(
            model=self.model,
            messages=prompt_msgs,
            **predict_kwargs,
        )
        self.set_cached_prompt_len(messages, functions, length=result.usage.input_tokens, **kwargs)
        return result.usage.input_tokens


chat_engine = AnthropicServerToolsEngine(api_key=config.ANTHROPIC_API_KEY, **CHAT_HYPERPARAMS)

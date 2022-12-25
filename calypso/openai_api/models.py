from typing import Literal

from pydantic import BaseModel


class CompletionLogProbs(BaseModel):
    tokens: list[str]
    token_logprobs: list[float]
    top_logprobs: list[dict[str, float]]
    text_offset: list[int]


class CompletionChoice(BaseModel):
    text: str
    index: int
    logprobs: CompletionLogProbs | None
    finish_reason: str


class CompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Completion(BaseModel):
    id: str
    object: Literal["text_completion"]
    created: int
    model: str
    choices: list[CompletionChoice]
    usage: CompletionUsage

    @property
    def text(self):
        """The text of the top completion."""
        return self.choices[0].text

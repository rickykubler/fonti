"""Test doubles."""

from collections.abc import Iterator, Sequence

from fonti.generation.llm import Message


class FakeChat:
    """A chat client that returns a scripted answer and records the prompts it received."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[list[Message]] = []

    @property
    def model_id(self) -> str:
        return "fake"

    def complete(self, messages: Sequence[Message]) -> str:
        self.calls.append(list(messages))
        return self.answer

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        self.calls.append(list(messages))
        yield from self.answer.split(" ")

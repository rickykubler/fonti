"""Test doubles."""

from collections.abc import Callable, Iterator, Sequence

from fonti.generation.llm import Message


class ScriptedChat:
    """A chat client whose reply is computed from the last message."""

    def __init__(self, reply: Callable[[str], str]) -> None:
        self.reply = reply

    @property
    def model_id(self) -> str:
        return "scripted"

    def complete(self, messages: Sequence[Message]) -> str:
        return self.reply(messages[-1]["content"])

    def stream(self, messages: Sequence[Message]) -> Iterator[str]:
        yield self.complete(messages)


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

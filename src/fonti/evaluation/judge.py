"""LLM-as-judge for groundedness and correctness, with Italian prompts and one-word verdicts.

The judge is only as good as its model: validate it against human labels before trusting
small differences (see docs/evaluation.md).
"""

from collections.abc import Sequence
from enum import StrEnum

from fonti.generation.llm import ChatClient


class Verdict(StrEnum):
    YES = "yes"
    PARTIAL = "partial"
    NO = "no"

    @property
    def score(self) -> float:
        return {Verdict.YES: 1.0, Verdict.PARTIAL: 0.5, Verdict.NO: 0.0}[self]


_GROUNDED = """\
Valuta se l'AFFERMAZIONE è sostenuta dai PASSAGGI, senza usare altre conoscenze.
Rispondi con una sola parola:
- SUPPORTATA se tutto ciò che l'affermazione dice si trova nei passaggi;
- PARZIALE se solo una parte si trova nei passaggi;
- NON_SUPPORTATA se i passaggi non la sostengono o la contraddicono.

PASSAGGI:
{passages}

AFFERMAZIONE: {claim}"""

_CORRECT = """\
Confronta la RISPOSTA con la RISPOSTA ATTESA alla DOMANDA.
Rispondi con una sola parola:
- CORRETTA se contiene l'informazione attesa e non la contraddice;
- PARZIALE se ne contiene solo una parte;
- ERRATA se manca l'informazione attesa o la contraddice.

DOMANDA: {question}
RISPOSTA ATTESA: {expected}
RISPOSTA: {answer}"""


class Judge:
    def __init__(self, chat: ChatClient) -> None:
        self._chat = chat

    @property
    def model_id(self) -> str:
        return self._chat.model_id

    def grounded(self, claim: str, passages: Sequence[str]) -> Verdict:
        prompt = _GROUNDED.format(passages="\n\n".join(passages), claim=claim)
        reply = self._chat.complete([{"role": "user", "content": prompt}]).upper()
        if "NON_SUPPORTATA" in reply or "NON SUPPORTATA" in reply:
            return Verdict.NO
        if "PARZIALE" in reply:
            return Verdict.PARTIAL
        return Verdict.YES if "SUPPORTATA" in reply else Verdict.NO

    def correct(self, question: str, expected: str, answer: str) -> Verdict:
        prompt = _CORRECT.format(question=question, expected=expected, answer=answer)
        reply = self._chat.complete([{"role": "user", "content": prompt}]).upper()
        if "ERRATA" in reply:
            return Verdict.NO
        if "PARZIALE" in reply:
            return Verdict.PARTIAL
        return Verdict.YES if "CORRETTA" in reply else Verdict.NO

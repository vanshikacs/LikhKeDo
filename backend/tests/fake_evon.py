"""A fake OpenAI-compatible client that answers like a well-behaved Evon, driven by a script."""
from __future__ import annotations

import json
from types import SimpleNamespace


def _resp(content: str):
    msg = SimpleNamespace(content=content, reasoning_content="(hidden reasoning)")
    return SimpleNamespace(id="evon-fake", choices=[SimpleNamespace(message=msg)],
                           usage=SimpleNamespace(completion_tokens=42))


class FakeOpenAI:
    """extract: dict for the extraction reply; verify: fn(promise_en) -> dict; summary: str."""

    def __init__(self, extract: dict, verify, summary: str = "<slow> दो बातें काग़ज़ पर नहीं हैं। <pauses> लिखित में माँगिए।",
                 bad_first: set[str] | None = None):
        self.extract, self.verify, self.summary = extract, verify, summary
        self.bad_first = set(bad_first or ())   # kinds whose first answer is broken JSON
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kw):
        self.requests.append(kw)
        system = kw["messages"][0]["content"]
        last = kw["messages"][-1]["content"]
        first_user = kw["messages"][1]["content"] if len(kw["messages"]) > 1 else ""
        if system.startswith("You extract"):
            kind, out = "extract", json.dumps(self.extract, ensure_ascii=False)
        elif system.startswith("You compare several"):
            results = []
            for line in first_user.split("\n"):
                if line.startswith("[") and "| English: " in line:
                    i = int(line[1:line.index("]")])
                    en = line.split("| English: ", 1)[1].split(" | numbers:", 1)[0]
                    results.append({"id": i, **self.verify(en)})
            kind, out = "verify_batch", json.dumps({"results": results}, ensure_ascii=False)
        elif system.startswith("You compare"):
            promise = (first_user.split("PROMISE (English): ", 1)[1].split("\n", 1)[0]
                       if "PROMISE (English)" in first_user else "")
            kind, out = "verify", json.dumps(self.verify(promise), ensure_ascii=False)
        elif system.startswith("Rewrite"):
            kind, out = "localize", json.dumps({"text": "कृपया लिखित में माँगिए"}, ensure_ascii=False)
        else:
            kind, out = "summary", json.dumps({"text": self.summary}, ensure_ascii=False)
        if kind in self.bad_first and "not valid JSON" not in last:
            self.bad_first.discard(kind)
            return _resp("Sure! Here is the JSON: {claims: [oops")
        return _resp("```json\n" + out + "\n```")

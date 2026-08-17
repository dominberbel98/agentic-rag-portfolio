from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from app.services.agent import AgentLimits, ProfileAgent
from app.services.retrieval import Document, RetrievalIndex

# --- fakes -------------------------------------------------------------------


def _doc(doc_id, category, title, text):
    return Document(id=doc_id, category=category, title=title, text=text, embedding=None)


@pytest.fixture
def index():
    docs = [
        _doc("role:data-equity", "role", "Data Scientist at Data Equity",
             "Domingo Berbel has been Data Scientist at Data Equity since October 2025."),
        _doc("role:suministros-medina", "role", "International Sales Representative",
             "He was International Sales Representative at Suministros Medina until September 2025."),
        _doc("project:portfolio-chatbot", "project", "Portfolio RAG assistant",
             "A retrieval augmented assistant built with FastAPI and React on Azure."),
        _doc("languages:spoken", "languages", "Spoken languages",
             "Spanish native. English professional working proficiency."),
    ]
    return RetrievalIndex(docs, vocabulary=frozenset({"Data Equity", "Suministros Medina", "FastAPI", "React", "Azure"}))


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _message(content=None, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls, role="assistant")


def _completion(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


class FakeClient:
    """Scripted OpenAI client. Each scripted item is one assistant turn.

    When called without `tools` it always returns prose, because a real model
    cannot emit a tool call for a tool it was not offered. Without this the
    agent's final tools-off call would be answered with another tool call.
    """

    FORCED_TEXT = "(answered without tools)"

    def __init__(self, script):
        self._script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if "tools" not in kwargs:
            nxt = self._script.pop(0) if self._script else None
            if nxt is not None and not getattr(nxt, "tool_calls", None):
                return _completion(nxt)
            return _completion(_message(content=self.FORCED_TEXT))
        if not self._script:
            return _completion(_message(content="(script exhausted)"))
        return _completion(self._script.pop(0))


def executed_tool_call_ids(client):
    """Unique tool_call_ids that produced real output.

    The messages list accumulates and is resent on every call, so summing tool
    messages across calls counts each one many times over.
    """
    ids = set()
    for call in client.calls:
        for message in call["messages"]:
            if message.get("role") != "tool":
                continue
            if "budget exhausted" in (message.get("content") or ""):
                continue
            ids.add(message["tool_call_id"])
    return ids


def _agent(index, script, **limit_kwargs):
    limits = AgentLimits(**limit_kwargs) if limit_kwargs else AgentLimits()
    return ProfileAgent(
        client=FakeClient(script),
        model="test-model",
        index=index,
        embedder=lambda _text: None,
        limits=limits,
    )


# --- tool dispatch -----------------------------------------------------------


def test_a_search_tool_call_is_dispatched_and_answered(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "search_profile", {"query": "current job"})]),
            _message(content="He is a Data Scientist at Data Equity."),
        ],
    )
    result = agent.answer("Where does he work?", history=[], language="en")
    assert "Data Equity" in result.answer
    assert result.documents


def test_get_entity_returns_the_addressed_document(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "get_entity", {"id": "project:portfolio-chatbot"})]),
            _message(content="He built a portfolio RAG assistant with FastAPI."),
        ],
    )
    result = agent.answer("Tell me about the chatbot", history=[], language="en")
    assert any(d.id == "project:portfolio-chatbot" for d in result.documents)


def test_list_entities_is_available_to_the_model(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "list_entities", {})]),
            _message(content="He has several roles and projects."),
        ],
    )
    result = agent.answer("What do you know?", history=[], language="en")
    assert result.answer


def test_category_filter_is_passed_through(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "search_profile", {"query": "x", "category": "project"})]),
            _message(content="Only the portfolio project matched."),
        ],
    )
    result = agent.answer("projects?", history=[], language="en")
    assert all(d.category == "project" for d in result.documents)


def test_multi_hop_issues_a_second_search(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "search_profile", {"query": "current role"})]),
            _message(tool_calls=[_tool_call("c2", "search_profile", {"query": "languages"})]),
            _message(content="He works at Data Equity and speaks Spanish and English."),
        ],
    )
    result = agent.answer("Job and languages?", history=[], language="en")
    ids = {d.id for d in result.documents}
    assert len(ids) >= 2


# --- robustness --------------------------------------------------------------


def test_malformed_tool_arguments_are_recoverable(index):
    broken = SimpleNamespace(
        id="c1",
        type="function",
        function=SimpleNamespace(name="search_profile", arguments="{not json"),
    )
    agent = _agent(
        index,
        [_message(tool_calls=[broken]), _message(content="Recovered and answered.")],
    )
    result = agent.answer("anything", history=[], language="en")
    assert "Recovered" in result.answer


def test_unknown_tool_name_is_recoverable(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "delete_everything", {})]),
            _message(content="I could not use that tool, but here is the answer."),
        ],
    )
    result = agent.answer("anything", history=[], language="en")
    assert result.answer


def test_unknown_entity_id_is_recoverable(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "get_entity", {"id": "role:nope"})]),
            _message(content="That entity does not exist; here is what does."),
        ],
    )
    result = agent.answer("anything", history=[], language="en")
    assert result.answer


def test_the_iteration_cap_terminates_a_looping_model(index):
    """A model that only ever calls tools must not spin forever."""
    forever = [
        _message(tool_calls=[_tool_call(f"c{i}", "search_profile", {"query": "x"})])
        for i in range(50)
    ]
    agent = _agent(index, forever, max_iterations=3)
    result = agent.answer("anything", history=[], language="en")
    assert result.answer  # some answer is produced rather than hanging
    assert agent.client.calls, "the model was called"
    assert len(agent.client.calls) <= 4


def test_the_tool_call_cap_is_enforced(index):
    forever = [
        _message(tool_calls=[_tool_call(f"c{i}", "search_profile", {"query": "x"})])
        for i in range(50)
    ]
    agent = _agent(index, forever, max_iterations=20, max_tool_calls=2)
    agent.answer("anything", history=[], language="en")
    assert len(executed_tool_call_ids(agent.client)) == 2


# --- scope and grounding -----------------------------------------------------


def test_out_of_scope_is_detected(index):
    agent = _agent(index, [_message(content="OUT_OF_SCOPE")])
    result = agent.answer("Hala Madrid", history=[], language="en")
    assert result.out_of_scope


def test_a_fabricated_entity_triggers_one_regeneration(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "search_profile", {"query": "stack"})]),
            _message(content="He uses MongoDB in production."),
            _message(content="He uses FastAPI and React on Azure."),
        ],
    )
    result = agent.answer("What does he use?", history=[], language="en")
    assert result.regenerated
    assert "MongoDB" not in result.answer


def test_a_grounded_answer_is_not_regenerated(index):
    agent = _agent(
        index,
        [
            _message(tool_calls=[_tool_call("c1", "search_profile", {"query": "stack"})]),
            _message(content="He uses FastAPI and React on Azure."),
        ],
    )
    result = agent.answer("What does he use?", history=[], language="en")
    assert not result.regenerated


def test_history_is_forwarded_to_the_model(index):
    agent = _agent(index, [_message(content="Yes, as I said.")])
    agent.answer(
        "and that?",
        history=[{"role": "user", "content": "does he know spark"},
                 {"role": "assistant", "content": "yes"}],
        language="en",
    )
    roles = [m["role"] for m in agent.client.calls[0]["messages"]]
    assert roles.count("user") >= 2


def test_language_instruction_reaches_the_system_prompt(index):
    agent = _agent(index, [_message(content="Trabaja en Data Equity.")])
    agent.answer("¿Dónde trabaja?", history=[], language="es")
    system = agent.client.calls[0]["messages"][0]["content"]
    assert "Spanish" in system


def test_the_system_prompt_does_not_hardcode_grades(index):
    """Facts belong in the corpus. The old prompt hardcoded exact scores."""
    agent = _agent(index, [_message(content="ok")])
    agent.answer("grades?", history=[], language="en")
    system = agent.client.calls[0]["messages"][0]["content"]
    for leak in ("9.75", "9.20", "Matrícula", "Apache Spark 9"):
        assert leak not in system

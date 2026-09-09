from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt


class WorkflowState(TypedDict, total=False):
    execution_id: str
    role: str
    area: str
    event: dict[str, Any]
    draft: str
    approval_id: str
    approval_decision: str
    edited_content: str
    source_report_ids: list[str]
    evidence_ids: list[str]
    threat_level: str
    overall_threat_level: str
    summary: str
    priority_areas: list[str]


Runner = Callable[[dict[str, Any], WorkflowState, str], dict[str, Any]]


class LangGraphRuntime:
    """Builder JSON을 실제 checkpoint-backed LangGraph로 컴파일한다."""

    def __init__(self, checkpoint_path: Path):
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(connection)

    def compile(self, definition: dict[str, Any], runner: Runner):
        graph = StateGraph(WorkflowState)
        nodes = {node["id"]: node for node in definition.get("nodes", [])}
        edges = definition.get("edges", [])
        incoming = {node_id: 0 for node_id in nodes}
        outgoing: dict[str, list[str]] = {node_id: [] for node_id in nodes}
        for edge in edges:
            source, target = edge.get("source"), edge.get("target")
            if source in nodes and target in nodes:
                outgoing[source].append(target)
                incoming[target] += 1

        for node_id, node in nodes.items():
            if "approval" in (node.get("type", "") + node_id):
                def approval_step(state: WorkflowState, spec=node):
                    payload = runner(spec, state, "before_interrupt")
                    decision = interrupt(payload)
                    return runner(spec, {**state, **decision}, "after_interrupt")
                graph.add_node(node_id, approval_step)
            else:
                graph.add_node(node_id, lambda state, spec=node: runner(spec, state, "run"))

        starts = [node_id for node_id, count in incoming.items() if count == 0]
        if len(starts) != 1:
            raise ValueError("워크플로에는 연결된 시작 노드가 정확히 하나 필요합니다.")
        graph.set_entry_point(starts[0])

        for source, targets in outgoing.items():
            if "approval" in (nodes[source].get("type", "") + source) and targets:
                target = targets[0]
                graph.add_conditional_edges(
                    source,
                    lambda state: "reject" if state.get("approval_decision") == "REJECT" else "continue",
                    {"reject": END, "continue": target},
                )
            elif not targets:
                graph.add_edge(source, END)
            else:
                for target in targets:
                    graph.add_edge(source, target)
        return graph.compile(checkpointer=self.checkpointer)

    @staticmethod
    def config(execution_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": execution_id}}

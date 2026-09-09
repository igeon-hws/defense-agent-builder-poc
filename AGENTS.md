# Agent Builder Demo - Coding Instructions

Before making implementation decisions, read:

1. docs/PRD.md
2. docs/ARCHITECTURE.md
3. docs/UI_SPEC.md
4. docs/DEMO_SCENARIO.md

This project is a 1-week seminar demo.
Optimize for demo reliability and clarity, not production completeness.

## Priority

1. Agent Builder UX
2. Workflow execution visualization
3. Human-in-the-Loop
4. Role-based experience
5. Analyst → Staff workflow linkage

## Do not over-engineer

Do NOT implement unless explicitly requested:

- Real Data Fabric
- Real sensor integration
- Kafka / message broker
- Kubernetes
- Full RBAC / ABAC
- GIS
- Local model serving
- Production authentication

Use mocks where specified in the docs.

## Important

When requirements are ambiguous:
- Prefer the simplest implementation that satisfies the demo scenario.
- Do not introduce new infrastructure without a clear requirement.
- Preserve the architecture described in docs/ARCHITECTURE.md.

## Implementation contract

- Read all four documents above before implementation, including when continuing existing work. PRD defines scope; ARCHITECTURE defines runtime contracts; UI_SPEC defines layouts/interactions; DEMO_SCENARIO defines acceptance. Planning source and retrieval dates are recorded in PRD.
- Keep the existing README and useful repository documentation. Inspect the current implementation and user changes before editing. Do not replace working features just to match a suggested folder or endpoint name.
- Use React + TypeScript + React Flow for the frontend and FastAPI + LangGraph + SQLite for the backend/runtime.
- Use an external LLM for the actual demo through a Model Gateway/provider interface. Store provider and model ID separately; keep credentials on the backend. Future local providers are an extension point, not a serving task.
- Mock Login/Role Session supports Analyst, Staff and Commander. Apply simple role/area rules to exposed nodes, agents, data and approval actions; Commander is read-only. Role Switch must not rewrite a running execution's initiating context.
- Mock Sensor, Data Fabric and Situation Context. Keep notifications in-app. The Situation Board uses an OpenStreetMap base map for the three named Korean demo regions, plus events and approved reports; advanced military GIS layers remain out of scope.
- Builder changes must compile into actual execution. Keep business-capability JSON definitions separate from LangGraph internals and pin a definition snapshot/version for each run.
- Implement HITL with real interrupt/checkpoint/resume. Edit requires explicit approval; Reject terminates without publishing. Never bypass approval because of a provider failure or demo timing.
- Persist the approved regional report before its event triggers the Staff Agent. Keep report writes and event dispatch idempotent; Commander reports must not recursively trigger Staff runs.
- Preserve the distinction between Agent publication and per-execution approval. Use the minimal draft/publish lifecycle; no separate deployment approval engine is required.
- Prioritize demo reliability throughout, then Builder UX, execution visibility, HITL, role experience and Analyst-to-Staff linkage. Prefer the simplest implementation satisfying the documented demo over new infrastructure.
- Validate meaningful behavior using DEMO_SCENARIO acceptance criteria, especially both approval gates, edit/reject, checkpoint recovery, role checks and duplicate report/event handling. Label deterministic test mode; do not present it as a live external-model result.
- Keep these documents consistent when an explicitly requested scope decision changes. Report changed files, checks performed and remaining limitations; do not claim untested acceptance criteria passed.

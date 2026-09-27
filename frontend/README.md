# Frontend

The laptop interview UI and its design documentation belong in this folder.

Start with the [reduced v1 proposal](docs/interview_ui_v1.md): Query & Evidence,
Metrics & Evaluations, Architecture with HLD/LLD, and one curated J&J historical comparison.
The [extended design](docs/interview_ui_design.md) is retained as a longer-term reference.

The UI is currently **design-only**. Streamlit is preferred for v1; the framework choice
remains open until the demo step. There is no frontend application or build command yet.

```text
frontend/
├── README.md
└── docs/
    ├── interview_ui_v1.md
    └── interview_ui_design.md
```

When implementation begins, frontend source, assets, and UI tests will live here,
including Python presentation code if Streamlit is chosen. The UI displays backend
evidence and evaluation reports. Data access, model calls, and financial calculations belong in
[`backend/`](../backend/README.md). API keys remain in the backend environment.

Frontend design and implementation plans live in `frontend/docs/`. Shared project status,
roadmap, production architecture, and learning material remain in root `docs/`; link to
them rather than maintain duplicate copies.

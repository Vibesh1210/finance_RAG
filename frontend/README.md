# Frontend

The laptop interview UI and its design documentation belong in this folder.

Start with the [interview UI design](docs/interview_ui_design.md): Query & Evidence,
Metrics & Evaluations, Architecture with HLD/LLD, and proposed Data Explorer and Time
Travel views.

The UI is currently **design-only**. React/TypeScript and a local Python adapter are
proposed; there is no frontend application or frontend build command yet.

```text
frontend/
├── README.md
└── docs/
    └── interview_ui_design.md
```

When implementation begins, frontend source, assets, tests, and package configuration
will live here. Presentation code renders backend evidence and recorded demo artifacts.
The Python adapter, data access, model calls, and financial calculations belong in
[`backend/`](../backend/README.md). API keys remain in the backend environment.

Frontend design and implementation plans live in `frontend/docs/`. Shared project status,
roadmap, production architecture, and learning material remain in root `docs/`; link to
them rather than maintain duplicate copies.

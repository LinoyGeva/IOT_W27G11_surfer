# Repository guidance

The team will implement the project themselves. Keep preparation separate from working code.

- Follow [Architecture](Documentation/ARCHITECTURE.md) for source locations and [Development](Documentation/DEVELOPMENT.md) for verification.
- The hub runs Android directly on Raspberry Pi 4. Keep each device directly under `raspberry_pi_hub/<device_name>/` and shared hub code in `main/`; do not reintroduce the older separate Linux/Android bridge.
- Add a document only when it has a distinct purpose. Maintain each fact in one place and link to it elsewhere.
- Preserve credentials outside Git and distinguish live, replay and synthetic data in code and evidence.
- Treat proposal/course documents as references; current user decisions take precedence. Do not claim a successful build, hardware result or course compliance without evidence.
- Preserve the existing ignore rule for `agent_docs/`. Its optional local context is [AGENT.md](agent_docs/AGENT.md).

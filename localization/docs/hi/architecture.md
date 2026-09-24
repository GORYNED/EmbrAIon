# वास्तुकला

## परतें

1. **Core (केंद्र)** — models और specific providers से स्वतंत्र rules, agents, skills, workflows, routing और knowledge।
2. **Adapters (एडाप्टर)** — AI hosts, transports और portable packages के लिए projections।
3. **Tools (उपकरण)** — state, learning, security, MCP, Git worktrees, validation, sync, install, diagnostics और CLI के deterministic tools।
4. **Project Overlay** — project-specific knowledge, constraints और optional routing overrides।
5. **External Capabilities** — recommended या optional companion systems और integrations।
6. **Evidence** — tests, behavioral evals, reference results और reports।

## एजेंट मॉडल

Core agents role names उपयोग करते हैं: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher और Steward। Role चुनना concrete model नहीं चुनता।

## Model selection का ownership

Core task-oriented route classes से काम classify करता है। EmbrAIon global model catalog, pricing या lifecycle नहीं रखता। AI host model availability और default/automatic selection का मालिक है। Project आवश्यकता होने पर केवल अपने host-specific overrides `.embraion/routing.yaml` में रखता है।

## State और Learning

Execution state privacy-safe records में normalize होता है। Repeated evidence improvement candidates बना सकता है, लेकिन Core change के लिए review और explicit approval चाहिए।

## Spec Kit

Spec Kit external capability है; यह Core rules, project truth या validation evidence को replace नहीं करता।

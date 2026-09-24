# अवलोकन

EmbrAIon एक पुन: उपयोग योग्य **AI-First Engineering System (AI-प्रथम इंजीनियरिंग सिस्टम)** है।

**Core (केंद्र)** भूमिका-आधारित agents, capability-typed rules, task-oriented model-agnostic routing और deterministic tools का उपयोग करता है। EmbrAIon वर्तमान model names का मालिक नहीं है: AI host model availability और default/automatic selection का मालिक है, जबकि project आवश्यकता होने पर केवल अपने host-specific overrides रखता है।

इससे EmbrAIon Codex, GitHub Copilot, Claude Code, किसी एक provider या किसी एक model generation से बँधे बिना विकसित हो सकता है।

Spec Kit उन महत्वपूर्ण कार्यों के लिए अनुशंसित बाहरी सहायक है जहाँ औपचारिक specification उपयोगी हो।

EmbrAIon उपयोग करने वाला repository अपना domain knowledge, constraints और optional routing overrides **Project Overlay** के माध्यम से जोड़ता है।

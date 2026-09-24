# क्षमता मॉडल

**Capability (क्षमता)** EmbrAIon का ऐसा स्वतंत्र भाग है जिसकी ज़िम्मेदारी स्पष्ट होती है।

EmbrAIon स्पष्ट capability types का उपयोग करता है ताकि नियम, ज़िम्मेदारी, प्रक्रिया, execution order और तथ्यात्मक ज्ञान आपस में न मिलें।

| प्रकार | उद्देश्य |
| --- | --- |
| **Rule (नियम)** | अनिवार्य, निषिद्ध या संरक्षित व्यवहार |
| **Agent (एजेंट)** | ज़िम्मेदारी और स्वामित्व क्षेत्र |
| **Skill (कौशल)** | दोहराई जा सकने वाली प्रक्रिया |
| **Workflow (कार्यप्रवाह)** | क्रमबद्ध निष्पादन |
| **Routing (रूटिंग)** | task/risk classification, execution constraints, host resolution और optional project overrides |
| **Tool (उपकरण)** | निर्धारक ऑपरेशन |
| **Adapter (एडाप्टर)** | host/transport integration और projection |
| **Knowledge (ज्ञान)** | तथ्य और वास्तु संबंधी जानकारी |

हर canonical capability का एक मुख्य प्रकार होना चाहिए। आपस में जुड़ी capabilities के लिए सामग्री दोहराने के बजाय cross-reference बेहतर है।

Routing जानबूझकर model-agnostic है। Model names, pricing, lifecycle और availability canonical EmbrAIon capabilities नहीं हैं।

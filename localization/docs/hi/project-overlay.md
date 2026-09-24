# Project Overlay (प्रोजेक्ट ओवरले)

EmbrAIon उपयोग करने वाली रिपॉजिटरी अपनी configuration `.embraion/` में रखती है।

फ़ाइलों की जिम्मेदारी:

- `project.yaml` — EmbrAIon repository/version, project identity और `capabilities`;
- `knowledge.yaml` — project knowledge references और context-selection metadata;
- `policy.yaml` — source classes, review policy और privacy;
- `routing.yaml` — optional model/effort/options overrides;
- `validation.yaml` — validation profiles;
- `agents.yaml` — project-specific agents.

प्रोजेक्ट ओवरले अधिक कठोर नियम जोड़ सकता है, लेकिन Core की अनिवार्य सीमाओं को चुपचाप कमज़ोर नहीं कर सकता।

## स्वचालित संस्करण चयन

सामान्य कमांड के लिए वैश्विक launcher निकटतम `.embraion/project.yaml` खोजता है, `framework.version` पढ़ता है और अपनी संस्करण संख्या से तुलना करता है। अंतर होने पर EmbrAIon `~/.embraion/versions/<version>/` में अलग runtime तैयार करता है और PyPI से ठीक `embraion==<version>` वितरण स्थापित करता है।

इसके बाद कमांड उसी cached संस्करण से चलती है। इस प्रकार एक मशीन पर एक वैश्विक launcher रह सकता है और अलग-अलग रिपॉजिटरी अलग EmbrAIon रिलीज़ पर बनी रह सकती हैं।

`embraion init` और `embraion update` जानबूझकर project runtime delegation को छोड़ते हैं:

- `init` modular configuration बनाता है और global launcher version लिखता है;
- `update` केवल वर्तमान repository का pin बदलता है;
- `--framework-version` से किसी खास प्रकाशित version को स्पष्ट रूप से चुना जा सकता है।

`EMBRAION_HOME` विकास के लिए स्पष्ट override है और उस process में automatic version delegation बंद करता है।

प्रोजेक्ट रिपॉजिटरी स्वयं उत्पाद विनिर्देशन, वास्तुकला, संगतता अनुबंध, सत्यापन प्रमाण और डोमेन ज्ञान का मानक स्रोत बनी रहती है।

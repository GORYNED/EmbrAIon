# Routing (रूटिंग)

EmbrAIon की रूटिंग पूरी तरह model-agnostic है।

Core काम को `bounded-read`, `bounded-write`, `ordinary`, `substantial`, `complex` और `critical` route classes में वर्गीकृत करता है। ये classes काम और जोखिम का वर्णन करती हैं, किसी मॉडल की शक्ति, कीमत, प्रदाता या नाम का नहीं।

यदि प्रोजेक्ट कोई override नहीं देता, तो चुना हुआ AI host अपनी default/automatic model selection का उपयोग करता है। स्पष्ट चयन की आवश्यकता होने पर प्रोजेक्ट host-specific `model`, `effort` और `options` को `.embraion/project.yaml` → `routing.overrides` में रख सकता है।

उपयोगकर्ता repository में काम कर रहे AI से उपलब्ध मॉडलों के अनुसार EmbrAIon configure करने के लिए कह सकता है। इंस्टॉल की गई `routing-configuration` skill AI को बताती है कि override कहाँ लिखना है और किन policies को कमजोर नहीं करना है।

EmbrAIon कोई canonical model catalog नहीं रखता। Privacy, access, ownership, validation और review model selection से स्वतंत्र रहते हैं।

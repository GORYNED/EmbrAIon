<p align="center">
  <img src="../brand/assets/readme/hero-dark.png" alt="EmbrAIon — GORYNED का AI-First Engineering System" width="100%">
</p>

<p align="center">
  <a href="../README.md">अंग्रेज़ी</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.es.md">Español</a> ·
  <strong>हिन्दी</strong>
</p>

# EmbrAIon

**AI-First Engineering System [by GORYNED](https://goryned.com)**

> Where sparks become AI-built products *(जहाँ चिंगारियाँ AI द्वारा बनाए गए उत्पादों में बदलती हैं)*

EmbrAIon एक पोर्टेबल AI-First Engineering System है, जो AI-सहायित सॉफ़्टवेयर इंजीनियरिंग को स्पष्ट भूमिकाओं, पुन: उपयोग योग्य कौशलों, कार्यप्रवाहों, मॉडल रूटिंग, पहुँच नियंत्रण, सत्यापन, स्वतंत्र समीक्षा, सुरक्षा, सिस्टम सीखने और प्रोजेक्ट-विशिष्ट परतों के आधार पर व्यवस्थित करता है।

यह किसी एक प्रोग्रामिंग भाषा या सिस्टम ढाँचे से बँधा नहीं है। Unity/C# प्रोजेक्ट, Python सेवा, वेब अनुप्रयोग या कोई अन्य सॉफ़्टवेयर रिपॉजिटरी एक ही EmbrAIon Core का उपयोग कर सकती है और केवल अपने प्रोजेक्ट-विशिष्ट ज्ञान व नियम जोड़ सकती है।

## EmbrAIon क्या करता है

EmbrAIon इंजीनियरिंग सिस्टम को स्वतंत्र भागों में विभाजित करता है:

- **[Agent (एजेंट)](../core/agents/)** — काम की ज़िम्मेदारी किसकी है: Lead, Worker, Reviewer, Architect, Analyst, Validator, Researcher या Steward।
- **[Skill (कौशल)](../core/skills/)** — किसी दोहराए जाने वाले काम को कैसे किया जाए।
- **[Rule (नियम)](../core/rules/)** — क्या अनिवार्य, निषिद्ध या संरक्षित है।
- **[Workflow (कार्यप्रवाह)](../core/workflows/)** — क्षमताएँ किस क्रम में मिलकर काम करती हैं।
- **[Routing (रूटिंग)](../core/routing/)** — कौन-सा पहुँच प्रोफ़ाइल, मॉडल स्तर, क्लाइंट और प्रदाता किसी कार्य को चला सकते हैं।
- **[Adapter (एडाप्टर)](../adapters/)** — EmbrAIon की मानक क्षमताओं को Codex, GitHub Copilot, Claude Code, API प्रदाताओं या Portable पैकेज में कैसे प्रस्तुत किया जाए।
- **[Tool (उपकरण)](../tools/)** — निर्धारक निष्पादन तर्क, जैसे सत्यापन, सुरक्षा जाँच, Git कार्य-वृक्ष प्रबंधन, समन्वयन और निदान।
- **[Eval (व्यवहार मूल्यांकन)](../evals/)** — यह जाँचना कि AI अपेक्षित इंजीनियरिंग अनुबंध का वास्तव में पालन करता है या नहीं।

`core/catalog.yaml` क्षमताओं का खोज-सूचकांक है। हर कार्य के लिए पूरा EmbrAIon लोड करने के बजाय केवल वही नियम, भूमिकाएँ, कौशल और कार्यप्रवाह लोड किए जा सकते हैं जो वर्तमान काम से संबंधित हों।

## डेटा वर्ग

EmbrAIon तीन मानक डेटा वर्ग उपयोग करता है:

| वर्ग | अर्थ |
| --- | --- |
| `PUBLIC` | सार्वजनिक जानकारी, जिसे अनुमत बाहरी सिस्टमों को भेजा जा सकता है |
| `PRIVATE` | आंतरिक या स्वामित्व वाली प्रोजेक्ट जानकारी; बाहरी उपयोग के लिए स्पष्ट रूप से अनुमत मार्ग आवश्यक है |
| `CONFIDENTIAL` | सबसे अधिक संरक्षित स्तर; बाहरी भेजना तब तक निषिद्ध है जब तक कोई मार्ग इसे स्पष्ट रूप से अनुमति न दे |

अज्ञात या अस्पष्ट वर्गीकरण सुरक्षित अस्वीकृति पर समाप्त होता है। अधिक शक्तिशाली मॉडल चुनना कभी भी डेटा पहुँच या गोपनीयता अनुमति नहीं बढ़ाता।

## समर्थित एडाप्टर

- **[Codex](https://openai.com/codex/)** — मॉडल सूची, मॉडल और तर्क स्तर का मार्ग से मिलान, तथा प्रोजेक्ट एजेंट और कॉन्फ़िगरेशन निर्माण।
- **[GitHub Copilot](https://github.com/features/copilot)** — समर्थित मॉडल सूची, अनुशंसित मार्ग और कस्टम एजेंट निर्माण।
- **[Claude Code](https://code.claude.com/docs/en/overview)** — Claude मॉडल सूची, मार्ग और अधीनस्थ एजेंट निर्माण।
- **[Portable](../adapters/portable/)** — किसी एक AI क्लाइंट से न बँधा पोर्टेबल क्षमता पैकेज।
- **[API प्रदाता](../adapters/providers/)** — [OpenAI](https://openai.com/), [Anthropic](https://www.anthropic.com/), [Google](https://ai.google.dev/) और [DeepSeek](https://www.deepseek.com/) की प्रत्यक्ष मॉडल सूचियाँ तथा कनेक्शन संबंधी जानकारी।

Core विशिष्ट मॉडलों से स्वतंत्र रहता है। वर्तमान मॉडल पहचान और क्लाइंट-विशिष्ट चयन केवल `adapters/` में रखे जाते हैं।

## स्थापना

### हर मशीन पर एक बार स्थापित करें

> **रिलीज़ नोट:** PyPI पर वर्तमान सार्वजनिक रिलीज़ `v0.1.0` है। हर प्रोजेक्ट के लिए EmbrAIon संस्करण का स्वचालित चयन `main` में लागू हो चुका है और अगले रिलीज़ में आएगा।

EmbrAIon [PyPI](https://pypi.org/project/embraion/) के माध्यम से वितरित होता है। सामान्य उपयोग के लिए Windows या macOS मशीन पर CLI को `pipx` से केवल एक बार स्थापित करें। रिपॉजिटरी क्लोन करने या `git clone` चलाने की आवश्यकता नहीं है।

यदि आप Python वातावरण स्वयं प्रबंधित करते हैं तो सामान्य `pip` स्थापना भी समर्थित है, लेकिन CLI के लिए `pipx` अनुशंसित तरीका है।

#### Windows

EmbrAIon के लिए Python 3.11 या नया संस्करण आवश्यक है।

1. Python जाँचें:

```powershell
py --version
```

यदि `py` उपलब्ध नहीं है या संस्करण 3.11 से पुराना है, तो [Windows के लिए आधिकारिक Python डाउनलोड](https://www.python.org/downloads/windows/) से वर्तमान Python 3 स्थापित करें और PowerShell दोबारा खोलें।

2. [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html) स्थापित करें और उसके कमांड पथ को `PATH` में जोड़ें:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

3. PowerShell बंद करके दोबारा खोलें और EmbrAIon स्थापित करें:

```powershell
pipx install embraion
```

यदि आप जानबूझकर अपना प्रबंधित Python वातावरण उपयोग करते हैं, तो यह भी समर्थित है:

```powershell
py -m pip install embraion
```

#### macOS

यदि [Homebrew](https://brew.sh/) पहले से स्थापित है, तो सबसे सरल तरीका है:

```bash
brew install pipx
pipx ensurepath
```

नई Terminal विंडो खोलें और EmbrAIon स्थापित करें:

```bash
pipx install embraion
```

Homebrew के बिना पहले Python जाँचें:

```bash
python3 --version
```

यदि Python उपलब्ध नहीं है या संस्करण 3.11 से पुराना है, तो [macOS के लिए आधिकारिक Python डाउनलोड](https://www.python.org/downloads/macos/) से वर्तमान Python 3 स्थापित करें। फिर `pipx` स्थापित करें:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

नई Terminal विंडो खोलें और चलाएँ:

```bash
pipx install embraion
```

यदि आप Python वातावरण स्वयं प्रबंधित करते हैं तो `python3 -m pip install embraion` भी समर्थित है।

#### जाँच

```bash
embraion --version
embraion validate
embraion doctor
```

`embraion validate` सक्रिय EmbrAIon स्थापना के साथ आए सिस्टम डेटा की जाँच करता है। `embraion doctor` वर्तमान प्रोजेक्ट या Git worktree संदर्भ भी जाँचता है, इसलिए इसे उस रिपॉजिटरी से चलाएँ जिसे आप जाँचना चाहते हैं या स्थापना परीक्षण के लिए किसी खाली परीक्षण फ़ोल्डर से चलाएँ।

#### अपडेट

```bash
pipx upgrade embraion
```

`pipx` की वैश्विक स्थापना उस मशीन के किसी भी प्रोजेक्ट से `embraion` कमांड उपलब्ध कराती है। यह **हर रिपॉजिटरी में EmbrAIon को अपने आप सक्रिय नहीं करती** और न ही उन्हें पृष्ठभूमि में बदलती है।

## EmbrAIon को हर प्रोजेक्ट में जोड़ना

हर रिपॉजिटरी स्पष्ट रूप से EmbrAIon से जुड़ती है। प्रोजेक्ट की जड़ से चलाएँ:

```bash
cd /path/to/your/project
embraion init
```

सामान्य रूप से `init` फ़ोल्डर के नाम को प्रोजेक्ट नाम मानता है। केवल अलग नाम चाहिए तो `--name MyProject` उपयोग करें।

यह बनाता है:

```text
.embraion/
└── project.yaml
```

Project Overlay (प्रोजेक्ट ओवरले) Git में घोषित EmbrAIon संस्करण और प्रोजेक्ट-विशिष्ट कॉन्फ़िगरेशन दर्ज करता है।

### आवश्यक क्लाइंट के लिए प्रस्तुति स्थापित करें

रिपॉजिटरी द्वारा उपयोग किए जाने वाले हर AI क्लाइंट के लिए प्रस्तुति स्थापित करें।

[Codex](https://openai.com/codex/):

```bash
embraion install --host codex --destination .
```

[GitHub Copilot](https://github.com/features/copilot):

```bash
embraion install --host copilot --destination .
```

[Claude Code](https://code.claude.com/docs/en/overview):

```bash
embraion install --host claude-code --destination .
```

Portable पैकेज:

```bash
embraion install --host portable --destination ./vendor/embraion
```

यदि प्रोजेक्ट कई क्लाइंट उपयोग करता है, तो हर क्लाइंट के लिए संबंधित `install` कमांड एक बार चलाएँ। मौजूदा जनित फ़ाइलें सामान्य रूप से ओवरराइट से सुरक्षित रहती हैं; `--force` केवल जानबूझकर बदलने के लिए उपयोग करें।

### प्रोजेक्ट संस्करण का स्वचालित चयन

वर्तमान `main` का लक्ष्य `v0.2.0` है और यह हर प्रोजेक्ट के लिए EmbrAIon संस्करण का स्वचालित चयन जोड़ता है।

सामान्य कमांड के लिए वैश्विक `embraion` वर्तमान फ़ोल्डर से ऊपर की ओर निकटतम `.embraion/project.yaml` खोजता है और `framework.version` पढ़ता है। यदि प्रोजेक्ट का निश्चित संस्करण वैश्विक launcher से अलग है, तो EmbrAIon PyPI से ठीक वही पैकेज संस्करण एक अलग कैश में स्थापित करता है:

```text
~/.embraion/versions/<version>/
```

किसी संस्करण के पहले उपयोग पर PyPI से डाउनलोड आवश्यक हो सकता है। बाद की कमांड उसी कैश का उपयोग करती हैं। इसलिए एक ही Windows PC या Mac पर एक वैश्विक CLI रखते हुए अलग-अलग प्रोजेक्ट अलग EmbrAIon संस्करण उपयोग कर सकते हैं।

`v0.1.0` से बने पुराने Project Overlay (प्रोजेक्ट ओवरले) में `0.1.0-dev` हो सकता है। नया resolver इस पुराने pin को प्रकाशित `0.1.0` पैकेज से जोड़ता है।

`embraion init` और `embraion update` जानबूझकर वैश्विक launcher में चलते हैं और पुराने प्रोजेक्ट runtime को नहीं दिए जाते:

- `embraion init` नए रिपॉजिटरी को वर्तमान वैश्विक launcher संस्करण से जोड़ता है;
- `pipx upgrade embraion` के बाद `embraion update` केवल वर्तमान प्रोजेक्ट को नए संस्करण पर ले जाता है;
- `embraion update --framework-version X.Y.Z` किसी चुने हुए प्रकाशित संस्करण को स्पष्ट रूप से निश्चित करता है, जिसे अगली सामान्य कमांड अपने आप resolve करेगी।

EmbrAIon के विकास के लिए `EMBRAION_HOME` किसी चुने हुए framework checkout का स्पष्ट override बना रहता है। `EMBRAION_DISABLE_VERSION_RESOLUTION=1` से स्वचालित resolver को भी स्पष्ट रूप से बंद किया जा सकता है।

## कार्य EmbrAIon से कैसे गुजरता है

```text
उपयोगकर्ता का लक्ष्य
  ↓
Project Overlay + Core सूची
  ↓
आवश्यक नियम / एजेंट / कौशल / कार्यप्रवाह
  ↓
डेटा वर्ग + पहुँच प्रोफ़ाइल + जटिलता
  ↓
क्लाइंट एडाप्टर + मॉडल मार्ग
  ↓
कार्यान्वयन
  ↓
सत्यापन
  ↓
स्वतंत्र समीक्षा
  ↓
अंतिम जाँच
  ↓
परिणाम सौंपना / मानव द्वारा merge
```

जहाँ औपचारिक विनिर्देशन उपयोगी हो, वहाँ [Spec Kit](https://github.com/github/spec-kit) को स्वतंत्र सहायक के रूप में उपयोग करने की सलाह दी जाती है। यह योजना और विनिर्देशन को बेहतर बनाता है, लेकिन Core के नियम, प्रोजेक्ट की तथ्य-स्रोत सामग्री, संगतता अनुबंध या सत्यापन प्रमाण को नहीं बदलता।

## CLI

मुख्य कमांड:

```text
embraion init
embraion install
embraion update
embraion sync
embraion validate
embraion doctor
```

### Routing (रूटिंग)

```bash
embraion route --host codex --route-class strong --data PRIVATE
```

### सीमित निष्पादन योजना

```bash
embraion dispatch \
  --task "Implement feature" \
  --role worker \
  --host codex \
  --route-class economy-write \
  --data PRIVATE \
  --access write \
  --owned-path "src/**"
```

लिखने की अनुमति वाली योजना के लिए `--owned-path` देना आवश्यक है और इसे स्थिर `main`/`master` शाखा से नहीं चलाया जा सकता।

### Session (सत्र)

```bash
embraion session start --session-id task-001 --task "Implement feature" --role lead --host codex --access plan
embraion session show
embraion session set --state review --validation passed
```

### Security (सुरक्षा)

```bash
embraion security scan --path .
```

### MCP सूची

```bash
embraion mcp inventory
```

सूची `.embraion/state/` में सुरक्षित रूप से रखी जाती है। पर्यावरण चर के नाम रखे जा सकते हैं, लेकिन गुप्त मान जानबूझकर नहीं लिखे जाते।

### Git कार्य-वृक्ष

```bash
embraion worktree list
embraion worktree create ai/my-task
embraion worktree gc
embraion worktree salvage /path/to/worktree
```

`gc` सामान्य रूप से केवल पूर्वावलोकन करता है। वास्तविक हटाने के लिए `--apply` देना आवश्यक है।

### Learning (सिस्टम सीखना)

```bash
embraion learning observe \
  --id repeated-review-gap \
  --kind repeated-failure \
  --target-type skill \
  --target-id review \
  --summary "Repeated review gap"
```

नई जानकारी का प्रवाह:

```text
अवलोकन → प्रमाण संचय → प्रस्ताव → स्वीकृति → उन्नयन
```

उन्नयन Core को अपने आप नहीं बदलता। अंतिम परिवर्तन फिर भी सामान्य इंजीनियरिंग, समीक्षा और सत्यापन प्रक्रिया से गुजरता है।

### Eval (व्यवहार मूल्यांकन)

```bash
embraion eval run --case reviewer-readonly --record path/to/execution-record.json
embraion eval baseline --reports build/evals --output baseline.json
embraion eval compare --baseline baseline.json --reports build/evals
```

## एडाप्टर प्रस्तुतियाँ बनाना

```bash
embraion sync --host all --output build/generated --force
```

जनित फ़ाइलें व्युत्पन्न प्रस्तुतियाँ हैं और किसी भी समय दोबारा बनाई जा सकती हैं। मानक नियम हमेशा `core/` में रहते हैं।

## रिपॉजिटरी संरचना

```text
brand/         ब्रांड और README सामग्री
core/          मानक नियम, एजेंट, कौशल, कार्यप्रवाह, रूटिंग और ज्ञान
adapters/      Codex, Copilot, Claude Code, Portable और API प्रदाता एकीकरण
tools/         CLI, निष्पादन, सीखना, सुरक्षा, MCP, कार्य-वृक्ष, सत्यापन और समन्वयन
schemas/       मशीन-पठनीय अनुबंध
templates/     Project Overlay टेम्पलेट
docs/          मानक अंग्रेज़ी दस्तावेज़
localization/  स्थानीयकृत दस्तावेज़
tests/         निर्धारक इकाई और एकीकरण परीक्षण
evals/         व्यवहार परिदृश्य, आधार परिणाम, मूल्यांकनकर्ता, नमूने और रिपोर्ट
examples/      एकीकरण उदाहरण
```

## सत्यापन और CI

हर push और pull request में योजनाबद्ध रूप से स्कीमा व सूची सत्यापन, स्थानीयकरण पूर्णता, इकाई/एकीकरण परीक्षण, सुरक्षा जाँच, सभी क्लाइंट प्रस्तुतियों का निर्माण और मूल व्यवहार मूल्यांकन चलाए जाते हैं।

Git tag वाले रिलीज़ स्रोत, Codex, Copilot, Claude Code और Portable संग्रह बनाते हैं।

## दस्तावेज़

मानक अंग्रेज़ी दस्तावेज़: [docs/](../docs/README.md)

हिन्दी दस्तावेज़: [localization/docs/hi/](docs/hi/README.md)

## लाइसेंस और ब्रांड

EmbrAIon का स्रोत कोड और दस्तावेज़ [MIT License](../LICENSE) के अंतर्गत हैं, जब तक किसी फ़ाइल या निर्देशिका में अलग से न कहा गया हो।

**EmbrAIon** और **GORYNED** नाम, लोगो, शब्द-चिह्न, दृश्य-चिह्न और `brand/assets/` की फ़ाइलें MIT के अंतर्गत लाइसेंस नहीं हैं। मानक नीति: [TRADEMARKS.md](../TRADEMARKS.md)।

## वर्तमान स्थिति

EmbrAIon अभी **पूर्व-स्थिर** अवस्था में है। वास्तुकला और पहला निष्पादन योग्य CLI उपलब्ध हैं, लेकिन सार्वजनिक संगतता अनुबंध अभी स्थिर नहीं किया गया है।

पहले स्थिर रिलीज़ से पहले मॉडल सूचियाँ, जनित क्लाइंट प्रस्तुतियाँ, सत्यापन कवरेज, सुरक्षा नियम, स्थापना और रिलीज़ पैकेजिंग बदल सकती हैं।

---

**EmbrAIon** · **AI-FIRST ENGINEERING SYSTEM** · **[by GORYNED](https://goryned.com)**

<sub>अंतिम अपडेट: 2026-09-23 22:00 UTC</sub>

# Multi-Language Learning System — Architecture & Content Pipeline

## Vision
Build a **language-agnostic learning engine** where English is the reference implementation. German, Spanish, and future languages plug into the same interfaces with language-specific data and grammar engines.

---

## 1. Core Data Model (Language-Agnostic)

### 1.1 Word Entry (Canonical Schema)
```python
@dataclass
class WordEntry:
    # Identity
    slug: str                 # "laufen_v", "casa_n_f", "run_v"
    lemma: str                # "laufen", "casa", "run"
    pos: str                  # "verb", "noun", "adjective", "adverb", "pronoun", "preposition", "conjunction"
    language: str             # "de", "es", "en"

    # CEFR & Frequency
    cefr_level: str           # "A1", "A2", "B1", "B2", "C1", "C2"
    frequency_rank: int       # Corpus frequency (1 = most frequent)
    frequency_band: str       # "top-1000", "top-3000", "top-10000", "top-20000"

    # Translations (multi-target)
    translations: dict[str, list[str]]  # {"ru": ["бежать", "бегать"], "en": ["run", "operate"]}

    # Morphology (language-specific, extensible)
    morphology: MorphologyBundle

    # Examples (sourced + curated)
    examples: list[ExampleSentence]

    # Audio
    audio_urls: dict[str, str]  # {"tts_azure": "...", "tts_piper": "...", "forvo": "..."}

    # Metadata
    tags: set[str]              # {"irregular", "separable", "reflexive", "medical", "business"}
    source: str                 # "DWDS", "Cervantes", "COERLL", "tatoeba", "manual"
    verified: bool              # Human-verified quality
```

### 1.2 Morphology Bundle (Per-Language Extension)
```python
@dataclass
class MorphologyBundle:
    # Common
    gender: str | None          # "m", "f", "n" (DE/ES), None (EN)
    number: str | None          # "sg", "pl"

    # German-specific
    german: GermanMorphology | None = None

    # Spanish-specific
    spanish: SpanishMorphology | None = None

    # English-specific
    english: EnglishMorphology | None = None


@dataclass
class GermanMorphology:
    # Nouns
    nominative_sg: str
    genitive_sg: str
    dative_sg: str
    accusative_sg: str
    nominative_pl: str
    genitive_pl: str
    dative_pl: str
    accusative_pl: str
    article_sg: str             # "der", "die", "das"
    article_pl: str             # "die"
    plural_rule: str            # "-e", "-er", "-n", "-s", "umlaut+e", "none"

    # Verbs
    infinitive: str
    praesens_ich: str
    praesens_du: str
    praesens_er: str
    praesens_wir: str
    praesens_ihr: str
    praesens_sie: str
    prateritum_ich: str
    partizip_ii: str
    aux_verb: str               # "haben" | "sein"
    is_separable: bool
    prefix: str | None          # "ab", "an", "auf", etc.
    is_strong: bool
    is_modal: bool
    is_reflexive: bool

    # Adjectives
    comparative: str
    superlative: str


@dataclass
class SpanishMorphology:
    # Nouns
    gender: str                 # "m", "f"
    singular: str
    plural: str

    # Verbs
    infinitive: str
    gerundio: str               # "corriendo"
    participio: str             # "corrido"

    # Present indicative
    pres_yo: str
    pres_tu: str
    pres_el: str
    pres_nosotros: str
    pres_vosotros: str
    pres_ellos: str

    # Preterite
    pret_yo: str
    pret_tu: str
    pret_el: str
    pret_nosotros: str
    pret_vosotros: str
    pret_ellos: str

    # Imperfect
    imperf_yo: str
    # ... (all forms)

    # Subjunctive present
    subj_pres_yo: str
    # ... (all forms)

    # Subjunctive imperfect
    subj_imperf_yo: str
    # ... (all forms)

    # Imperative
    imper_tu: str
    imper_el: str
    imper_nosotros: str
    imper_vosotros: str
    imper_ellos: str

    # Classification
    conjugation_group: int      # 1 (-ar), 2 (-er), 3 (-ir)
    is_irregular: bool
    is_reflexive: bool
    is_stem_changing: bool      # e→ie, o→ue, e→i
    stem_change_type: str | None


@dataclass
class EnglishMorphology:
    # Verbs
    base: str
    past: str
    past_participle: str
    gerund: str
    third_person_sg: str
    is_irregular: bool
    is_phrasal: bool
    phrasal_particles: list[str]  # ["up", "down", "out", ...]

    # Nouns
    singular: str
    plural: str
    is_countable: bool

    # Adjectives
    comparative: str
    superlative: str
```

### 1.3 Example Sentence
```python
@dataclass
class ExampleSentence:
    id: str
    text: str                   # "Ich laufe jeden Morgen im Park."
    translation: str            # "Я бегаю каждое утро в парке."
    source: str                 # "tatoeba", "DW", "COERLL", "manual"
    cefr_level: str             # "A1", "A2", ...
    audio_url: str | None
    tags: set[str]              # {"daily_routine", "separable_verb", "preposition_in"}
    word_slugs: list[str]       # Words this sentence illustrates
```

---

## 2. Content Pipeline (ETL: Extract → Transform → Load)

### 2.1 Sources by Language

| Language | Primary Sources | Secondary Sources | Enrichment |
|---|---|---|---|
| **DE** | DWDS (CEFR freq), Goethe Wortschatz, COERLL "Deutsch im Blick" | Tatoeba (DE sentences), OpenSubtitles, Wiktionary | LanguageTool (grammar check), spaCy (POS/lemma), Azure TTS |
| **ES** | Cervantes Plan Curricular, COERLL Spanish, RAE freq | Tatoeba (ES), OpenSubtitles, Wiktionary, Radio Ambulante transcripts | LanguageTool, spaCy, Azure TTS |
| **EN** | English Vocabulary Profile, COERLL, BNC/COCA freq | Tatoeba, OpenSubtitles, Wiktionary | Existing pipeline |

### 2.2 Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTENT PIPELINE                                │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────┤
│   EXTRACT   │  TRANSFORM  │   ENRICH    │  VALIDATE   │    PUBLISH     │
├─────────────┼─────────────┼─────────────┼─────────────┼────────────────┤
│             │             │             │             │                │
│ • DWDS CSV  │ • Normalize │ • spaCy     │ • CEFR      │ • vocab.json   │
│ • Goethe    │   lemmas    │   POS/DEP   │   alignment │   (lazy chunks)│
│   PDF/Excel │ • Map POS   │ • Language  │ • Duplicate │ • morphology.  │
│ • COERLL    │   to UD     │   Tool      │   detection │   json         │
│ • Tatoeba   │ • Generate  │   grammar   │ • Example   │ • example      │
│   API       │   full      │   check     │   quality   │   .json        │
│ • Wiktionary│   paradigm  │ • TTS audio │   (human)   │ • audio manifest│
│   API       │ • CEFR tag  │   (Piper)   │             │                │
│             │             │             │             │                │
└─────────────┴─────────────┴─────────────┴─────────────┴────────────────┘
```

### 2.3 Automation Scripts (per language)
```
tools/
├── build_vocab_de.py      # DWDS → vocab_de.json + morphology_de.json
├── build_vocab_es.py      # Cervantes/COERLL → vocab_es.json + morphology_es.json
├── build_vocab_en.py      # Existing → vocab_en.json (refactor)
├── enrich_examples.py     # Tatoeba + OpenSubtitles → examples_{lang}.json
├── generate_audio.py      # Piper/Azure → audio/{lang}/
├── validate_cefr.py       # Cross-check CEFR tags against profiles
└── package_language.py    # Creates plugin zip for distribution
```

---

## 3. Learning System (Language-Agnostic Engine)

### 3.1 Core Components (Reused from English)
```python
# stamina/languages/core/
├── progress.py        # LanguageProgress — SM-2, XP, streaks, achievements (per lang)
├── scheduler.py       # SM-2 algorithm (interval, ease factor, due dates)
├── practice.py        # Mission generation (new words + reviews)
├── review.py          # Quality review system (4-grade self-assessment)
├── warehouse.py       # Flashcard mode (flip, type, speak, listen)
├── access.py          # CEFR unlock rules (sequential, unlock_pct%)
├── hooks.py           # Terraformer rewards (energy, blueprints, cosmetics)
└── tts_asr.py         # Voice abstraction (Azure, Piper, Vosk, Whisper)
```

### 3.2 Per-Language Plugin Interface
```python
# stamina/languages/plugins/{lang}/__init__.py
class LanguagePlugin(ABC):
    code: str
    name_native: str
    name_target: str
    flag_emoji: str
    cefr_levels: list[str]
    freq_sets: list[FreqSet]
    thematic_sets: dict[str, ThematicSet]

    @abstractmethod
    def load_vocab(self) -> VocabSource: ...
    @abstractmethod
    def get_grammar_engine(self) -> GrammarEngine: ...
    @abstractmethod
    def get_best_practices(self) -> BestPractices: ...
    @abstractmethod
    def get_voices(self) -> VoicesConfig: ...
```

### 3.3 Grammar Engine (Language-Specific Exercise Generation)
```python
class GrammarEngine(ABC):
    @abstractmethod
    def get_topics(self, cefr: str) -> list[GrammarTopic]: ...

    @abstractmethod
    def generate_exercise(self, topic: str, difficulty: str, seed: int) -> Exercise: ...

    @abstractmethod
    def validate_answer(self, exercise: Exercise, answer: str) -> ValidationResult: ...

    @abstractmethod
    def get_explanation(self, topic: str, learner_lang: str) -> str: ...
```

**Exercise Types by Language:**

| Type | EN | DE | ES |
|---|---|---|---|
| `conjugation` | ✓ (tense) | ✓ (Präsens, Präteritum, Perfekt, Konjunktiv) | ✓ (Presente, Pretérito, Imperfecto, Subjuntivo) |
| `declension` | — | ✓ (Artikel, Adjektiv, Nomen 4 Fälle) | ✓ (Artículo, Sustantivo, Adjetivo) |
| `word_order` | — | ✓ (V2, Tekamolo, Nebensatz) | — |
| `separable_verbs` | ✓ (phrasal) | ✓ (trennbare Verben) | — |
| `gender_patterns` | — | ✓ (Suffixregeln) | ✓ (-ción/-dad = f, -o/-ma = m) |
| `preposition_case` | — | ✓ (Wechselpräpositionen Akk/Dat) | ✓ (por/para, a/de) |
| `subjunctive_triggers` | — | ✓ (Konjunktiv II) | ✓ (WEIRDO, Ojalá, Es que) |
| `ser_vs_estar` | — | — | ✓ |
| `aspect` | ✓ (simple/prog/perf) | — | — |
| `articles` | ✓ (a/an/the) | ✓ (der/die/das, null) | ✓ (el/la/los/las, un/una) |

---

## 4. Language-Specific Specifications

### 4.1 German Plugin (`plugins/de/`)

#### Vocab Source
- **Primary:** DWDS Grundwortschatz (CEFR-tagged A1–C2) + Goethe-Zertifikat lists
- **Thematic sets:** `goethe-a1`, `goethe-a2`, `goethe-b1`, `goethe-b2`, `dtz`, `testdaf`, `business-de`, `medical-de`, `pflege-de` (from pflege.jaeckels.net)
- **Size targets:** A1: 600, A2: 1200, B1: 2500, B2: 5000, C1: 10000, C2: 20000

#### Grammar Engine Topics (from plan + pflege.jaeckels.net)
```python
DE_GRAMMAR_TOPICS = {
    "A1": [
        "gender_patterns", "nominative_accusative", "present_weak", "present_strong",
        "separable_verbs", "modal_verbs", "perfekt_haben_sein",
        "prepositions_acc", "prepositions_dat", "wechselfral_prep",
        "word_order_v2", "questions", "negation", "possessive_articles",
        "plural_nouns", "adjective_declination_weak"
    ],
    "A2": [
        "dative_case", "genitive_case", "prateritum", "perfekt_vs_prateritum",
        "reflexive_verbs", "adjective_declination_strong_mixed",
        "comparative", "subordinate_clauses", "tekamolo", "prepositions_gen",
        "relative_clauses", "infinitive_zu", "passive_present",
        "n_declension", "partizip_ii_adjective", "prepositional_verbs"
    ],
    "B1": [
        "konjunktiv_ii_present", "konjunktiv_ii_past", "passive_alternatives",
        "partizip_i_adjective", "partizip_ii_adjective",       # ← NEW from pflege.jaeckels.net
        "partizipialattribute", "partizipialattribute_extended",
        "prepositional_objects", "da_wo_compounds",
        "conditional", "indirect_questions", "modal_particles"
    ],
    "B2": [
        "konjunktiv_i", "passive_prateritum", "participle_clauses",
        "nominalization", "prepositional_adverbs", "concessive", "final"
    ],
    "C1": ["sophisticated_syntax", "academic_register"],
    "C2": ["near_native_nuance"]
}
```

#### Special: Pflege-Deutsch Module (B1-B2)
```python
PFLEGE_TOPICS = {
    "partizipialattribute_pflege": {
        "source": "https://pflege.jaeckels.net/partizipialattribute",
        "exercises": ["choose_partizip", "identify_partizip", "transform_pflegebericht"],
        "vocab": ["der Bewohner", "die Pflegekraft", "stürzen", "versorgen", "mobilisieren",
                  "die Vitalzeichen", "der Sturzsensor", "neurologische Beobachtung"]
    },
    "pferfebericht_schreiben": {
        "template": "Sturzbericht, Wundversorgung, Übergabe",
        "exercises": ["fill_report", "convert_to_partizip"]
    }
}
```

#### Voices
- **Piper (local):** thorsten (male), eva_k (female), karlsson (male)
- **Azure (cloud):** de-DE-Conrad (male), de-DE-Katja (female), de-DE-Florian, de-DE-Seraphina
- **Vosk ASR:** vosk-model-de-0.21 (1.9GB), small (45MB)

---

### 4.2 Spanish Plugin (`plugins/es/`)

#### Vocab Source
- **Primary:** Instituto Cervantes Plan Curricular (A1–C2) + COERLL SpinTX + RAE frequency
- **Thematic sets:** `dele-a1`, `dele-a2`, `dele-b1`, `dele-b2`, `dele-c1`, `business-es`, `medical-es`, `latam-es`, `spanish-for-english-speakers`
- **Variants:** Peninsular (ES) + Latin American (MX/AR/CO) — tagged per entry

#### Grammar Engine Topics
```python
ES_GRAMMAR_TOPICS = {
    "A1": [
        "gender_patterns", "articles", "present_regular_ar", "present_regular_er_ir",
        "present_irregular_core", "ser_vs_estar", "gustar_structure",
        "question_words", "negation", "present_progressive",
        "prepositions_a_de_en_con_por_para", "possessive_adjectives",
        "adjective_agreement", "demonstratives", "numbers_time"
    ],
    "A2": [
        "preterite_regular", "preterite_irregular", "imperfect_regular",
        "imperfect_irregular", "preterite_vs_imperfect", "future_ir_voy_a",
        "direct_object_pronouns", "indirect_object_pronouns", "double_object",
        "reflexive_verbs", "comparatives_superlatives", "por_vs_para",
        "commands_tu", "present_subjunctive_regular", "subjunctive_trigger_weirdo"
    ],
    "B1": [
        "present_subjunctive_irregular", "subjunctive_noun_clauses",
        "subjunctive_adj_clauses", "subjunctive_adv_clauses",
        "imperfect_subjunctive", "conditional", "conditional_perfect",
        "past_subjunctive_si_clauses", "relative_pronouns", "passive_voice",
        "se_impersonal", "se_unplanned", "future_perfect", "present_perfect_subj"
    ],
    "B2": [
        "subjunctive_vs_indicative_nuance", "past_subjunctive_alt_forms",
        "sequence_of_tenses", "nominalization", "cleft_sentences",
        "advanced_por_para", "verbal_periphrases", "discourse_markers"
    ],
    "C1": ["subjunctive_in_adverbial_clauses", "hypothetical_past", "literary_tenses"],
    "C2": ["native_idiomatic_range", "register_variation"]
}
```

#### Voices
- **Piper:** carlfm (es-ES), davefx (es-ES), ald (es-MX), daniela (es-AR)
- **Azure:** es-ES-Alvaro, es-ES-Elvira, es-MX-Jorge, es-MX-Dalia
- **Vosk:** vosk-model-es-0.42 (1.4GB), small (39MB)

---

### 4.3 English Plugin (`plugins/en/`) — Reference Implementation
*Already exists in `stamina/english/` — migrate to plugin structure*

#### Grammar Topics
```python
EN_GRAMMAR_TOPICS = {
    "A1": ["present_simple", "present_continuous", "past_simple", "future_will_going_to",
           "present_perfect", "articles", "prepositions_time_place", "modal_can_must",
           "comparatives", "question_formation", "phrasal_verbs_basic"],
    "A2": ["past_continuous", "present_perfect_continuous", "past_perfect",
           "future_continuous", "modal_should_might", "passive_voice", "reported_speech",
           "relative_clauses", "conditionals_0_1", "phrasal_verbs_intermediate"],
    "B1": ["perfect_tenses_review", "conditionals_2_3", "wish_if_only", "modal_perfect",
           "passive_all_tenses", "reported_speech_advanced", "gerund_infinitive",
           "causative", "phrasal_verbs_advanced", "collocations"],
    "B2": ["mixed_conditionals", "inversion", "subjunctive", "ellipsis_substitution",
           "advanced_modals", "cohesion_devices", "academic_vocab"],
    "C1": ["nuanced_modals", "complex_sentence_structure", "register_style"],
    "C2": ["near_native_precision", "idiomatic_density"]
}
```

---

## 5. User-Facing Features (Per Language)

### 5.1 Vocabulary Cards (Warehouse)
| Side | Content |
|---|---|
| Front | Lemma + POS + Audio 🔊 + Image (optional) |
| Back | Translations (user language), Full morphology table, 3 curated examples, CEFR badge, Tags |

**Morphology Table Rendering:**
- **DE Noun:** 4-case table (SG/PL) + Article + Plural rule badge
- **DE Verb:** Full conjugation (Präsens, Präteritum, Perfekt, Konjunktiv II, Imperativ) + Separable prefix highlight
- **ES Noun:** Gender + SG/PL + Article
- **ES Verb:** Full paradigm (Indicative: Pres, Pret, Imperf, Fut, Cond; Subjunctive: Pres, Imperf; Imperative) + Stem-change highlight
- **EN Verb:** 5-form table + Phrasal variants

### 5.2 Practice Missions (SM-2)
- **New words:** 5–7 per session (configurable)
- **Reviews:** Due cards prioritized by SM-2 interval
- **Modes:** Multiple choice, Type answer, Speak answer (ASR), Listen & type (ASR+TTS), Translate
- **Quality grades:** Again (0), Hard (3), Good (4), Easy (5) → SM-2 ease factor adjustment

### 5.3 Grammar Gym (New)
- **Topic browser** by CEFR level
- **Exercise generator** (infinite variations via seed)
- **Immediate feedback** with explanation in learner's language
- **Progress tracking** per topic (mastery %)

### 5.4 Cross-Language Pairs (L1→L2)
```python
# Enabled when pilot has B1+ in L1
CROSS_PAIRS = {
    "en→es": {"contrastive": ["ser_vs_estar", "por_vs_para", "subjunctive_triggers", "gustar"]},
    "es→en": {"contrastive": ["phrasal_verbs", "perfect_tenses", "articles", "conditionals"]},
    "en→de": {"contrastive": ["cases", "word_order", "separable_verbs", "gender"]},
    "de→en": {"contrastive": ["tenses", "articles", "phrasal_verbs", "continuous_aspect"]},
    "es→de": {...},
    "de→es": {...}
}
```

---

## 6. Terraformer Integration (Gamification)

### 6.1 Reward Events (from any language)
```python
TERRAFORMER_REWARDS = {
    "daily_goal_met": {"energy": 50, "xp": 10},
    "streak_3": {"energy": 100, "blueprint": "pipe_t1"},
    "streak_7": {"energy": 200, "blueprint": "pump_t1"},
    "streak_30": {"energy": 500, "robot_skin": "linguist_bot"},
    "level_up_A2": {"energy": 300, "unlock": "robot_A2"},
    "level_up_B1": {"energy": 500, "unlock": "robot_B1", "blueprint": "smart_network"},
    "level_up_B2": {"energy": 800, "unlock": "robot_B2"},
    "level_up_C1": {"energy": 1200, "unlock": "robot_C1", "blueprint": "quantum_link"},
    "level_up_C2": {"energy": 2000, "unlock": "robot_C2", "skin": "polyglot_commander"},
    "achievement_first_100": {"energy": 150},
    "achievement_1000_words": {"energy": 500, "blueprint": "maglev_t1"},
    "cross_pair_session": {"energy": 75, "bonus": "double_xp"},
}
```

### 6.2 Energy → Terraformer Effect
```
Total Energy = Σ(language_rewards) across all active languages
→ Accelerates trainer tick_extraction() multiplier
→ Unlocks pipeline tiers (T1 pipes → T4 quantum)
→ Purchases drone repair, blueprint slots, cosmetic skins
```

---

## 7. Technical Implementation Plan

### Phase 1: Core + English Migration (Week 1-2)
- [ ] Create `stamina/languages/core/` with all ABCs
- [ ] Implement `LanguageRegistry`, `LanguageProgress`, `SM2Scheduler`
- [ ] Migrate `stamina/english/` → `plugins/en/`
- [ ] Build `languages_hook.py` + `languages/screen.py` (language selector)
- [ ] Migration script: `english.json` → `lang_en.json`
- [ ] Tests: registry, progress, migration

### Phase 2: German Plugin (Week 3)
- [ ] `plugins/de/vocab.json` from DWDS/Goethe (A1–B2 first)
- [ ] `plugins/de/morphology.json` (full paradigms)
- [ ] `plugins/de/grammar.py` with all A1–B2 topics + Pflege module
- [ ] `plugins/de/examples.json` from Tatoeba + COERLL
- [ ] `plugins/de/voices.json` (Piper + Azure)
- [ ] `plugins/de/best_practices.md`
- [ ] Register plugin, test unlock flow

### Phase 3: Spanish Plugin (Week 4)
- [ ] `plugins/es/vocab.json` from Cervantes/COERLL
- [ ] `plugins/es/morphology.json`
- [ ] `plugins/es/grammar.py` (subjunctive focus)
- [ ] `plugins/es/examples.json`
- [ ] `plugins/es/voices.json`
- [ ] Cross-pair `en→es` contrastive module

### Phase 4: Content Pipeline Automation (Week 5)
- [ ] `tools/build_vocab_de.py` (DWDS CSV → JSON)
- [ ] `tools/build_vocab_es.py` (Cervantes PDF/Excel → JSON)
- [ ] `tools/enrich_examples.py` (Tatoeba API → examples)
- [ ] `tools/generate_audio.py` (Piper batch TTS)
- [ ] `tools/validate_cefr.py` (cross-check)
- [ ] CI pipeline for vocab updates

### Phase 5: Advanced Features (Week 6+)
- [ ] Grammar Gym UI (exercise generator)
- [ ] Cross-pair learning mode
- [ ] Terraformer reward integration
- [ ] Offline ASR (Vosk) + local TTS (Piper) bundling
- [ ] Community content submission workflow

---

## 8. File Structure (Final)

```
stamina/
├── languages/
│   ├── __init__.py                 # exports: registry, progress, hooks
│   ├── core/
│   │   ├── __init__.py
│   │   ├── base.py                 # LanguagePlugin, VocabSource, GrammarEngine ABCs
│   │   ├── registry.py             # LanguageRegistry (folder + entry_points)
│   │   ├── progress.py             # LanguageProgress (SM-2, XP, achievements)
│   │   ├── scheduler.py            # SM2Scheduler (pure algorithm)
│   │   ├── practice.py             # MissionGenerator
│   │   ├── review.py               # QualityReview
│   │   ├── warehouse.py            # FlashcardEngine
│   │   ├── access.py               # CEFR unlock rules
│   │   ├── hooks.py                # TerraformerRewards
│   │   └── tts_asr.py              # VoiceManager (Azure/Piper/Vosk/Whisper)
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── en/
│   │   │   ├── __init__.py         # EnglishPlugin
│   │   │   ├── vocab.json          # Lazy-loaded chunks
│   │   │   ├── morphology.json     # Full paradigms
│   │   │   ├── examples.json       # Curated sentences
│   │   │   ├── grammar.py          # EnglishGrammarEngine
│   │   │   ├── voices.json         # TTS/ASR config
│   │   │   └── best_practices.md
│   │   ├── de/
│   │   │   ├── __init__.py         # GermanPlugin
│   │   │   ├── vocab.json
│   │   │   ├── morphology.json
│   │   │   ├── examples.json
│   │   │   ├── grammar.py          # GermanGrammarEngine
│   │   │   ├── voices.json
│   │   │   ├── best_practices.md
│   │   │   └── pflege_module.py    # B1-B2 Pflege-Deutsch
│   │   └── es/
│   │       ├── __init__.py         # SpanishPlugin
│   │       ├── vocab.json
│   │       ├── morphology.json
│   │       ├── examples.json
│   │       ├── grammar.py          # SpanishGrammarEngine
│   │       ├── voices.json
│   │       └── best_practices.md
│   ├── migrate.py                  # english.json → lang_en.json
│   ├── hook.py                     # languages_hook.py (compartment entry)
│   └── screen.py                   # LanguagesScreen (selector + subpages)
├── tools/
│   ├── build_vocab_de.py
│   ├── build_vocab_es.py
│   ├── enrich_examples.py
│   ├── generate_audio.py
│   ├── validate_cefr.py
│   └── package_language.py
└── data/
    └── vocab_sources/              # Raw downloads (gitignored)
        ├── dwds/
        ├── goethe/
        ├── cervantes/
        ├── coerll/
        └── tatoeba/
```

---

## 9. Data Acquisition Checklist

### German
- [ ] DWDS Grundwortschatz CSV (CEFR bands) — https://www.dwds.de/r/ (download)
- [ ] Goethe-Zertifikat Wortschatz A1–C2 (PDF → parse)
- [ ] COERLL "Deutsch im Blick" vocab lists
- [ ] Tatoeba DE sentences (API bulk download)
- [ ] OpenSubtitles DE (frequency-filtered)
- [ ] Wiktionary DE audio (for pronunciation reference)
- [ ] Pflege.jaeckels.net vocab (manual curation)

### Spanish
- [ ] Instituto Cervantes Plan Curricular (PDF per level)
- [ ] COERLL Spanish textbooks vocab
- [ ] RAE frequency lists (CREA corpus)
- [ ] DELE exam vocab lists (A1–C2)
- [ ] Tatoeba ES sentences
- [ ] OpenSubtitles ES
- [ ] Radio Ambulante transcripts (vocab extraction)
- [ ] Notes in Spanish worksheets

### English (verify existing)
- [ ] English Vocabulary Profile (A1–C2 wordlists)
- [ ] BNC/COCA frequency
- [ ] COERLL materials
- [ ] Existing `stamina/english/vocab.json` audit

---

## 10. Definition of Done (Per Language)

| Criterion | DE | ES | EN |
|---|---|---|---|
| Vocab JSON (A1–C2, CEFR-tagged) | ✓ | ✓ | ✓ |
| Morphology JSON (full paradigms) | ✓ | ✓ | ✓ |
| Examples JSON (3+ per word, sourced) | ✓ | ✓ | ✓ |
| Grammar Engine (all CEFR topics) | ✓ | ✓ | ✓ |
| TTS Voices (local + cloud) | ✓ | ✓ | ✓ |
| ASR Models (local Vosk) | ✓ | ✓ | ✓ |
| Best Practices doc | ✓ | ✓ | ✓ |
| Plugin loads & registers | ✓ | ✓ | ✓ |
| Sub-pages work (Sets, Missions, Review, Warehouse, Book) | ✓ | ✓ | ✓ |
| Terraformer hooks fire | ✓ | ✓ | ✓ |
| Cross-pair (if L1≥B1) | en→de, es→de | en→es, de→es | de→en, es→en |
| Automated build script | ✓ | ✓ | ✓ |
| CI validation passes | ✓ | ✓ | ✓ |

---

## Next Steps
1. **Approve this spec** → Create branch `agent/orion/multilang-core`
2. **Snapshot** current state
3. **Start Phase 1** implementation
4. **Parallel:** Download DWDS/Cervantes/COERLL source data to `data/vocab_sources/`

Ready to start when you say «старт».
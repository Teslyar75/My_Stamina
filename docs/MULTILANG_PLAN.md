# Multi-Language Platform — Implementation Plan

## Overview
Transform "English" compartment into "Foreign Languages" with plugin architecture.
Phase 1: Core + English plugin (2 weeks)
Phase 2: German plugin (1 week)
Phase 3: Cross-pairs EN↔ES (1 week)
Phase 4: Spanish plugin + others

---

## Phase 1: Core Architecture + English Migration (Sprint 1-2)

### 1.1 Create Core Package Structure
```
stamina/languages/
├── __init__.py              # exports: LanguagePlugin, registry, progress, access, hooks
├── core/
│   ├── __init__.py
│   ├── base.py              # Abstract base classes
│   ├── registry.py          # Plugin discovery & loading
│   ├── progress.py          # LanguageProgress (per-language SM-2, XP, achievements)
│   ├── access.py            # Universal unlock rules (CEFR + custom)
│   ├── cross.py             # L1→L2 pair definitions
│   ├── tts_asr.py           # Voice/recognition abstraction
│   └── hooks.py             # Terraformer integration
└── plugins/
    ├── __init__.py
    ├── en/                  # English plugin (migrated)
    │   ├── __init__.py
    │   ├── vocab.json       # CEFR A1-C2 + freq sets + thematic
    │   ├── grammar.py       # Tenses, phrasal verbs, articles
    │   ├── best_practices.md
    │   └── voices.json
    ├── de/                  # German plugin (Phase 2)
    └── es/                  # Spanish plugin (Phase 4)
```

### 1.2 Core Base Classes (`core/base.py`)
```python
class LanguagePlugin(ABC):
    """Every language implements this."""
    code: str                    # "en", "de", "es"
    name_native: str             # "English", "Deutsch", "Español"
    name_target: str             # "Английский", "Немецкий", "Испанский"
    flag_emoji: str              # "🇬🇧", "🇩🇪", "🇪🇸"
    cefr_levels: list[str]       # ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets: list[FreqSet]     # [("top-1000", 1000, "Essential"), ...]
    thematic_sets: dict[str, ThematicSet]  # {"dev-interview": {...}}

    @abstractmethod
    def load_vocab(self) -> VocabSource: ...
    @abstractmethod
    def get_grammar_engine(self) -> GrammarEngine: ...
    @abstractmethod
    def get_best_practices(self) -> BestPractices: ...
    @abstractmethod
    def get_voices(self) -> VoicesConfig: ...

class VocabSource(ABC):
    """Abstract vocab loading (lazy/full, local/remote)."""
    @abstractmethod
    def get_word(self, slug: str) -> WordEntry: ...
    @abstractmethod
    def search(self, query: str, filters: dict) -> list[WordEntry]: ...
    @abstractmethod
    def get_set(self, set_id: str) -> list[WordEntry]: ...

class GrammarEngine(ABC):
    """Grammar exercises generation & validation."""
    @abstractmethod
    def get_topics(self, cefr: str) -> list[GrammarTopic]: ...
    @abstractmethod
    def generate_exercise(self, topic: str, difficulty: str) -> Exercise: ...
    @abstractmethod
    def validate_answer(self, exercise: Exercise, answer: str) -> ValidationResult: ...
    @abstractmethod
    def get_explanation(self, topic: str, lang: str) -> str: ...  # L1 explanation
```

### 1.3 Registry (`core/registry.py`)
```python
class LanguageRegistry:
    def __init__(self): self._plugins: dict[str, LanguagePlugin] = {}
    def discover(self, plugins_dir: Path) -> None: ...  # importlib.metadata entry_points or folder scan
    def get(self, code: str) -> LanguagePlugin | None: ...
    def all(self) -> list[LanguagePlugin]: ...
    def get_cross_pair(self, l1: str, l2: str) -> CrossPair | None: ...
```

### 1.4 Per-Language Progress (`core/progress.py`)
```python
class LanguageProgress:
    """Isolated per-language progress, shares only total XP with Terraformer."""
    def __init__(self, pilot_dir: Path, lang_code: str):
        self.path = pilot_dir / f"lang_{lang_code}.json"
        self.lang_code = lang_code
        self.data = self._load()

    # SM-2, XP, achievements, streaks, quality reviews — identical to English Progress
    # but scoped to one language. Settings per-language.
```

### 1.5 Universal Access Rules (`core/access.py`)
```python
def level_open(progress: LanguageProgress, level: str, plugin: LanguagePlugin) -> bool:
    """Captain = all open. Else: sequential CEFR, unlock_pct % of prev level."""
    # Same logic as english/access.py but generic

def cross_pair_unlocked(pilot_dir: Path, l1: str, l2: str) -> bool:
    """Cross-pair unlock: need B1 in L1 OR captain."""
```

### 1.6 Terraformer Hooks (`core/hooks.py`)
```python
def on_language_event(event: LanguageEvent, pilot_dir: Path) -> TerraformerReward:
    """Events: level_up, daily_goal, streak, achievement, session_complete.
    Rewards: energy, blueprints, cosmetics, robot unlocks.
    Aggregates across ALL languages."""
```

---

## 1.7 English Plugin Migration (`plugins/en/`)

### Files to Move/Adapt
| From | To | Changes |
|---|---|---|
| `english/vocab.py` + `vocab_lazy.py` | `plugins/en/vocab.py` | Implement `VocabSource` ABC |
| `english/grammar.py` (new) | `plugins/en/grammar.py` | Extract from tasks/check pages |
| `english/cefr.py` | `plugins/en/cefr.py` | Keep CEFR→slugs mapping |
| `english/access.py` | remove | Use core/access.py |
| `english/progress.py` | remove | Use core/progress.py |
| `english/tts.py`, `asr.py` | `plugins/en/voices.json` + core/tts_asr | Voice mapping |
| `english/verbs.py` | `plugins/en/verbs.py` | Grammar topic: phrasal verbs |
| `english/vocab.json` | `plugins/en/vocab.json` | Same data, validate schema |
| `english/best_practices.md` | `plugins/en/best_practices.md` | Document methods |

### English Plugin `__init__.py`
```python
from stamina.languages.core.base import LanguagePlugin, VocabSource, GrammarEngine
from .vocab import EnglishVocabSource
from .grammar import EnglishGrammarEngine

class EnglishPlugin(LanguagePlugin):
    code = "en"
    name_native = "English"
    name_target = "Английский"
    flag_emoji = "🇬🇧"
    cefr_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    freq_sets = [("top-1000", 1000, "Essential 1000", "ФУНДАМЕНТ", "S-1000"),
                 ("top-3000", 3000, "Core 3000", "РАЗГОВОРНЫЙ", "S-3000"),
                 ("top-10000", 10000, "Advanced 10K", "СВОБОДНЫЙ", "S-10K"),
                 ("top-20000", 20000, "Master 20K", "КАК НОСИТЕЛЬ", "S-20K"),
                 ("dev-interview", 0, "IT Interview", "СОБЕСЕДОВАНИЕ", "S-DEV")]

    def load_vocab(self) -> VocabSource:
        return EnglishVocabSource()

    def get_grammar_engine(self) -> GrammarEngine:
        return EnglishGrammarEngine()

    def get_best_practices(self) -> BestPractices:
        return BestPractices.from_file(Path(__file__).parent / "best_practices.md")

    def get_voices(self) -> VoicesConfig:
        return VoicesConfig.from_json(Path(__file__).parent / "voices.json")
```

---

## 1.8 New Compartment: "ИНОСТРАННЫЕ ЯЗЫКИ" (`languages_hook.py` + `languages/screen.py`)

### UI Flow
```
┌─────────────────────────────────────────────┐
│  ИНОСТРАННЫЕ ЯЗЫКИ                          │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │
│  │ 🇬🇧 │ │ 🇩🇪 │ │ 🇪🇸 │ │ +   │  ← language cards
│  │ EN  │ │ DE  │ │ ES  │      │           │
│  │ A2  │ │ 🔒  │ │ 🔒  │      │           │
│  └─────┘ └─────┘ └─────┘ └─────┘           │
│  [Мой прогресс: 1,247 XP  |  A2  |  14 д.] │
└─────────────────────────────────────────────┘
Click card → open language sub-pages (Sets, Missions, Review, Warehouse, Book, Log, Settings)
```

### Sub-pages (reused from English, now generic)
- `OverviewPage` → language dashboard (XP, streak, next unlock)
- `SetsPage` → freq + thematic sets for this language
- `PracticePage` → missions (SM-2 review + new words)
- `ReviewPage` → system check (quality reviews)
- `WarehousePage` → flashcards (same UI)
- `BookPage` → sentences from books (unlock at B1+)
- `ListsPage` → custom lists
- `LogPage` → session history
- `SettingsPage` → per-language settings + TTS/ASR voices

---

## 1.9 Migration Script (run once per pilot)
```python
# stamina/languages/migrate.py
def migrate_english_progress(pilot_dir: Path) -> None:
    """Move english.json → lang_en.json, preserve all data."""
    old = pilot_dir / "english.json"
    new = pilot_dir / "lang_en.json"
    if old.exists() and not new.exists():
        data = json.loads(old.read_text(encoding="utf-8"))
        # Add language code marker
        data["_lang"] = "en"
        new.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        old.rename(pilot_dir / "english.json.migrated")
```

---

## Phase 2: German Plugin (Sprint 3)

### 2.1 Vocab Data (`plugins/de/vocab.json`)
- **Source:** DW Wortschatz + Goethe-Zertifikat lists + OpenSubtitles frequency
- **Structure:** Same schema as English vocab.json
- **CEFR mapping:** A1 (500), A2 (1000), B1 (2000), B2 (4000), C1 (8000), C2 (15000)
- **Thematic sets:** `goethe-a1`, `goethe-a2`, `goethe-b1`, `goethe-b2`, `dtz`, `testdaf`, `business-de`, `medical-de`

### 2.2 Grammar Engine (`plugins/de/grammar.py`)
```python
class GermanGrammarEngine(GrammarEngine):
    TOPICS = {
        "A1": [
            "gender_patterns",           # der/die/das + suffix rules
            "nominative_accusative",     # articles, pronouns
            "present_weak_verbs",        # regular conjugation
            "present_strong_verbs",      # vowel change (e→ie, a→ä)
            "separable_verbs",           # aufstehen, ankommen
            "modal_verbs",               # können, müssen, wollen
            "perfekt_haben_sein",        # auxiliary selection
            "prepositions_accusative",   # durch, für, gegen, ohne, um
            "prepositions_dative",       # aus, bei, mit, nach, seit, von, zu
            "wechselfral_prepositions",  # in, an, auf, über, unter, vor, hinter, neben, zwischen
            "word_order_v2",             # verb second
            "questions_yes_no",          # verb-first
            "questions_w",               # wer, was, wo, wann, wie, warum
            "negation_kein_nicht",       # kein + noun, nicht + verb/adj
            "possessive_articles",       # mein, dein, sein, ihr
        ],
        "A2": [
            "dative_case",               # articles, pronouns, prepositions
            "genitive_case",             # articles, pronouns, prepositions
            "prateritum_weak_strong",    # simple past
            "perfekt_vs_prateritum",     # spoken vs written
            "separable_in_perfekt",      # aufgestanden, angekommen
            "reflexive_verbs",           # sich waschen, sich freuen
            "adjective_declination",     # strong/weak/mixed
            "comparative_superlative",   # größer, am größten
            "subordinate_clauses",       # dass, weil, wenn, als
            "word_order_tekamolo",       # temporal-kausal-modal-lokal
            "prepositions_genitive",     # während, wegen, statt, trotz
            "relative_clauses",          # der, die, das, welcher
            "infinitive_with_zu",        # um ... zu, ohne ... zu
            "passive_present",           # wird + Partizip II
        ],
        "B1": [
            "konjunktiv_ii_present",     # würde + inf, wäre, hätte
            "konjunktiv_ii_past",        # wäre gewesen, hätte gemacht
            "passive_alternatives",      # sich lassen, man, reflexive
            "n_declension",              # der Herr, des Herrn
            "partizip_ii_as_adjective",  # das gekochte Wasser
            "prepositional_verbs",       # warten auf, denken an
            "verbs_with_prepositional_objects",
            "da_compounds",              # darauf, daran, damit
            "wo_compounds",              # worauf, woran, womit
            "conditional_sätze",         # wenn ich reich wäre...
            "indirect_questions",        # ich weiß nicht, ob...
        ],
        "B2": [
            "konjunktiv_i",              # reported speech
            "passive_prateritum",        # wurde + Partizip II
            "partizip_i_ii_clauses",     # verkürzte Nebensätze
            "nominalization",            # das Lesen, das Gelesene
            "prepositional_adverbs",     # darauf hin, damit einverstanden
            "modal_particles",           # ja, doch, mal, schon, eben, halt, nur
            "concessive_clauses",        # obwohl, selbst wenn
            "final_clauses",             # damit, um ... zu, sodass
        ],
        "C1": [
            "konjunktiv_i_ii_mixed",
            "participle_constructions",
            "nominal_style",
            "idiomatic_prepositions",
        ],
        "C2": [
            "sophisticated_syntax",
            "academic_register",
        ],
    }

    def generate_exercise(self, topic: str, difficulty: str) -> Exercise:
        # Exercise types per topic:
        # - gender: "choose_article", "color_code_noun"
        # - cases: "fill_article", "transform_sentence"
        # - verbs: "conjugate", "separable_split", "auxiliary_select"
        # - word_order: "reorder_words", "place_verb"
        # - prepositions: "choose_preposition", "choose_case"
        # - particles: "choose_particle", "explain_nuance"
```

### 2.3 Best Practices (`plugins/de/best_practices.md`)
```markdown
# German Best Practices

## 1. Gender-First Learning
- Every noun card shows colored article: 🔵 der | 🔴 die | 🟢 das
- Suffix patterns: -ung/-heit/-keit → ♀ | -chen/-lein/-ment → ⚪ | -ismus/-or/-ent → ♂
- Compound nouns: gender = gender of last component (der Handschuh)

## 2. Verb Prefix System
Group by meaning:
- ab- (away): abfahren, abnehmen
- an- (on/start): anfangen, anrufen
- auf- (open/up): aufmachen, aufstehen
- aus- (out/complete): ausgeben, aussehen
- ein- (in): einladen, einkaufen
- los- (start): losfahren, loslegen
- mit- (with): mitkommen, mitbringen
- nach- (after): nachdenken, nachmachen
- vor- (before/forward): vorstellen, vorkommen
- zu- (closed/toward): zumachen, zuhören

## 3. Preposition + Case Blocks
- Accusative only: durch, für, gegen, ohne, um (DOGFU)
- Dative only: aus, bei, mit, nach, seit, von, zu (ABMSVZ)
- Genitive only: während, wegen, statt, trotz (WWST)
- Two-way (Wechsel): in, an, auf, über, unter, vor, hinter, neben, zwischen
  → Accusative = movement TO (wohin?)
  → Dative = location (wo?)

## 4. Tekamolo Word Order
**T**emporal (wann?) → **Ka**usal (warum?) → **Mo**dal (wie?) → **Lo**kal (wo?/wohin?)
Example: *Ich fahre morgen mit dem Auto nach Berlin.*
         (Temp)    (Mod)       (Lok)

## 5. Perfekt vs Präteritum
- Spoken: Perfekt (ich bin gegangen) — except sein, haben, modals
- Written: Präteritum (ich ging)
- Southern Germany: Präteritum more common in speech

## 6. Modal Particles (Pragmatics)
- ja: shared knowledge ("Das ist ja klar")
- doch: contradiction ("Das ist doch falsch")
- mal: softener ("Wart mal")
- schon: reassurance ("Wird schon")
- eben: resignation ("Ist eben so")
- halt: colloquial resignation ("Ist halt so")
```
```

### 2.4 Voices (`plugins/de/voices.json`)
```json
{
  "tts": {
    "windows_oncore": ["Stefan", "Katja"],
    "azure": ["de-DE-Conrad", "de-DE-Katja", "de-DE-Florian", "de-DE-Seraphina"],
    "piper": ["de_DE/thorsten/low", "de_DE/karlsson/low"]
  },
  "asr": {
    "vosk_model": "vosk-model-de-0.21",
    "azure_locale": "de-DE"
  }
}
```

---

## Phase 3: Cross-Pairs EN↔ES (Sprint 4)

### 3.1 Data Structure (`core/cross.py`)
```python
@dataclass
class CrossPair:
    l1: str                    # "en"
    l2: str                    # "es"
    name: str                  # "English → Spanish"
    contrastive_grammar: list[ContrastiveTopic]
    false_friends: list[FalseFriend]
    cognates: list[Cognate]
    cultural_notes: list[CulturalNote]
    translation_exercises: list[TranslationExercise]
```

### 3.2 Contrastive Topics (EN→ES)
| Topic | English Speaker Error | Correction |
|---|---|---|
| Ser vs Estar | "I am boring" → *Soy aburrido* | *Estoy aburrido* (temporary state) |
| Por vs Para | "Thanks for the gift" → *Gracias por el regalo* | ✓ |
| Subjunctive triggers | "I want that he comes" → *Quiero que viene* | *Quiero que venga* |
| Gustar structure | "I like the book" → *Yo gusto el libro* | *Me gusta el libro* |
| Gender patterns | -tion → -ción (fem), -ty → -dad (fem) | Systematic mapping |

### 3.3 UI: Language Pair Selector
```
┌────────────────────────────────────┐
│  Я говорю на:  [🇬🇧 English ▼]     │
│  Учу:          [🇪🇸 Español ▼]     │
│  ┌──────────────────────────────┐  │
│  │ Контрастивные уроки          │  │
│  │ • Ser vs Estar      [Начать] │  │
│  │ • Por vs Para       [▶]      │  │
│  │ • Subjuntivo        [🔒 B1]  │  │
│  └──────────────────────────────┘  │
└────────────────────────────────────┘
```

---

## Technical Tasks Checklist

### Phase 1 Core
- [ ] Create `stamina/languages/core/` package with ABCs
- [ ] Implement `LanguageRegistry` with folder-based discovery
- [ ] Implement `LanguageProgress` (copy from English Progress, add lang_code)
- [ ] Implement universal `access.py` (CEFR sequential + captain)
- [ ] Implement `hooks.py` (Terraformer rewards aggregation)
- [ ] Implement `tts_asr.py` abstraction
- [ ] Create `plugins/en/` with migrated code
- [ ] Write migration script `migrate_english_progress()`
- [ ] Build `languages_hook.py` + `languages/screen.py` (language selector + sub-pages)
- [ ] Update `app.py` to register languages compartment
- [ ] Test: existing pilot keeps all progress, English works identically

### Phase 2 German
- [ ] Create `plugins/de/` structure
- [ ] Build `vocab.json` (CEFR A1-C2 + thematic sets)
- [ ] Implement `GermanGrammarEngine` with all A1-B2 topics
- [ ] Write `best_practices.md`
- [ ] Create `voices.json`
- [ ] Register plugin, test unlock flow

### Phase 3 Cross-Pairs
- [ ] Design `CrossPair` schema
- [ ] Create `en→es.json` and `es→en.json`
- [ ] Build contrastive exercise generator
- [ ] Add pair selector UI in languages screen
- [ ] Test with English pilot learning Spanish

### Phase 4 Spanish
- [ ] `plugins/es/vocab.json` (CEFR + DELE + LatAm variants)
- [ ] `plugins/es/grammar.py` (subjunctive, ser/estar, por/para, gustar)
- [ ] `plugins/es/best_practices.md`
- [ ] `plugins/es/voices.json`

---

## Integration Points

### Terraformer Energy Calculation
```python
# core/hooks.py
def calculate_terraformer_energy(pilot_dir: Path) -> int:
    total = 0
    for lang_dir in pilot_dir.glob("lang_*.json"):
        prog = LanguageProgress(pilot_dir, lang_dir.stem[5:])  # lang_en → en
        # Daily goal bonus
        if prog.daily_goal_met_today():
            total += 50
        # Streak bonus
        total += min(prog.current_streak * 5, 200)
        # Level up bonus (one-time per level)
        total += prog.xp_total // 1000 * 100
    return total
```

### Pilot Data Structure (after migration)
```
%APPDATA%\Stamina\pilots\<pilot_id>\
├── pilot.json                    # pilot metadata (name, github_login, role)
├── lang_en.json                  # English progress (migrated from english.json)
├── lang_de.json                  # German progress (created on first open)
├── lang_es.json                  # Spanish progress
├── terraformer_trainer.json      # Trainer state (shared)
├── lounge.json                   # Arcade scores
├── english.json.migrated         # Backup (kept)
└── settings.json                 # Global UI settings
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Migration breaks existing pilots | Run migration lazily on first open; keep backup `.migrated` |
| Grammar engine too complex for MVP | Phase 1: only vocab (SM-2). Grammar exercises → Phase 2+ |
| Voice support inconsistent across OS | Abstract TTS/ASR; fall back to web APIs (Azure) if local missing |
| Cross-pair content creation bottleneck | Start with EN↔ES only; community-contributed pairs later |
| Vocab.json size for multiple languages | Lazy loading (already in vocab_lazy); per-language cache |

---

## Definition of Done (Phase 1)
1. ✅ `stamina/languages/` package imports without errors
2. ✅ Existing pilot opens app → migration runs → English progress intact
3. ✅ "ИНОСТРАННЫЕ ЯЗЫКИ" compartment shows 🇬🇧 English card with correct CEFR level
4. ✅ Click English → all sub-pages work (Sets, Missions, Review, Warehouse, Book, Log, Settings)
5. ✅ Terraformer receives energy from English progress events
6. ✅ Captain sees all languages unlocked; regular pilot sees only English (others 🔒)
7. ✅ No regression in existing English functionality
8. ✅ Tests pass: `pytest tests/ -q` (add tests for registry, progress, migration)

---

## Next Steps
1. **Approve plan** → I create branch `agent/orion/multilang-core`
2. **Snapshot** current state: `powershell -ExecutionPolicy Bypass -File tools/snapshot.ps1`
3. **Start Phase 1** implementation (core + English migration)
4. **Daily sync** on progress blockers
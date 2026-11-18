"""Cross-language pairs (L1 → L2) for contrastive learning."""
from __future__ import annotations

from dataclasses import dataclass

from .base import LanguagePlugin, WordEntry


@dataclass
class ContrastiveItem:
    id: str
    l1_word: WordEntry
    l2_word: WordEntry
    type: str
    l1_explanation: str
    l2_explanation: str
    false_friend: bool = False
    cognate: bool = False
    cultural_note: str = ""


class CrossPairEngine:
    PAIRS = {
        ("de", "en"): "de_en",
        ("en", "de"): "en_de",
        ("es", "en"): "es_en",
        ("en", "es"): "en_es",
        ("de", "es"): "de_es",
        ("es", "de"): "es_de",
    }

    DE_EN_FALSE_FRIENDS = [
        ("bekommen", "become", "bekommen = receive, become = werden"),
        ("aktuell", "actual", "aktuell = current, actual = tatsächlich"),
        ("eventuell", "eventual", "eventuell = possible, eventual = endgültige"),
        ("konsequent", "consequent", "konsequent = consistent, consequent = folgend"),
        ("sensibel", "sensible", "sensibel = sensitive, sensible = vernünftig"),
        ("sympathisch", "sympathetic", "sympathisch = likeable, sympathetic = mitfühlend"),
        ("ordinär", "ordinary", "ordinär = vulgar, ordinary = gewöhnlich"),
        ("realisieren", "realize", "realisieren = implement, realize = bemerken"),
        ("kontrollieren", "control", "kontrollieren = check, control = steuern"),
        ("akademisch", "academic", "akademisch = scholarly, academic = universitären"),
    ]

    EN_DE_COGNATES = [
        ("water", "Wasser", "Germanic cognate"),
        ("father", "Vater", "Germanic cognate"),
        ("mother", "Mutter", "Germanic cognate"),
        ("brother", "Bruder", "Germanic cognate"),
        ("house", "Haus", "Germanic cognate"),
        ("book", "Buch", "Germanic cognate"),
        ("hand", "Hand", "Germanic cognate"),
        ("finger", "Finger", "Germanic cognate"),
        ("night", "Nacht", "Germanic cognate"),
        ("sun", "Sonne", "Germanic cognate"),
    ]

    ES_EN_FALSE_FRIENDS = [
        ("embarazada", "embarrassed", "embarazada = pregnant, embarrassed = avergonzado"),
        ("actual", "actual", "actual = current, actual = real/verdadero"),
        ("asistir", "assist", "asistir = attend, assist = ayudar"),
        ("realizar", "realize", "realizar = carry out, realize = darse cuenta"),
        ("éxito", "exit", "éxito = success, exit = salida"),
        ("largo", "large", "largo = long, large = grande"),
        ("fábrica", "fabric", "fábrica = factory, fabric = tela"),
        ("sopa", "soap", "sopa = soup, soap = jabón"),
        ("robar", "rob", "robar = steal, rob = asaltar"),
        ("pretender", "pretend", "pretender = intend/try, pretend = fingir"),
    ]

    EN_ES_COGNATES = [
        ("information", "información", "Latin cognate -ción"),
        ("nation", "nación", "Latin cognate -ción"),
        ("education", "educación", "Latin cognate -ción"),
        ("family", "familia", "Latin cognate"),
        ("animal", "animal", "Identical"),
        ("hospital", "hospital", "Identical"),
        ("hotel", "hotel", "Identical"),
        ("doctor", "doctor", "Identical"),
        ("color", "color", "Identical"),
        ("natural", "natural", "Identical"),
    ]

    DE_ES_FALSE_FRIENDS = [
        ("Gift", "gift", "Gift = poison (veneno), gift = regalo"),
        ("Rat", "rat", "Rat = advice (consejo), rat = rata"),
        ("Hund", "hund", "Hund = dog (perro), hund = hundred (cien)"),
        ("Mann", "man", "Mann = man (hombre), man = man (uno/hombre)"),
    ]

    ES_DE_COGNATES = [
        ("padre", "Vater", "Latin pater"),
        ("madre", "Mutter", "Latin mater"),
        ("hermano", "Bruder", "Germanic *brōþar"),
        ("casa", "Haus", "No direct cognate"),
        ("libro", "Buch", "No direct cognate"),
    ]

    GRAMMAR_CONTRASTS = {
        ("de", "en"): [
            ("cases", "4 Fälle vs kein Kasus", "Nominativ/Genitiv/Dativ/Akkusativ vs word order"),
            ("gender", "3 Genera vs natural gender", "der/die/das vs he/she/it"),
            ("verb_position", "V2 / Verb-final vs SVO", "Main: V2, Sub: verb-final"),
            ("perfect", "Perfekt/Präteritum distinction", "Present perfect / simple past"),
            ("separable", "Trennbare Verben", "Phrasal verbs (particles post-verbal)"),
        ],
        ("en", "de"): [
            ("cases", "Kein Kasus vs 4 Fälle", "Word order vs Nominativ/Genitiv/Dativ/Akkusativ"),
            ("gender", "Natural gender vs 3 Genera", "he/she/it vs der/die/das"),
            ("verb_position", "SVO vs V2/Verb-final", "Fixed position vs flexible"),
        ],
        ("es", "en"): [
            ("ser_estar", "Ser vs Estar", "To be (single verb)"),
            ("subjunctive", "Subjuntivo (WEIRDO)", "Limited subjunctive"),
            ("gender", "2 Genera (m/f)", "Natural gender"),
            ("adjective_order", "Noun-Adj (casa blanca)", "Adj-Noun (white house)"),
            ("null_subject", "Pro-drop (hablo)", "Subject required (I speak)"),
        ],
        ("en", "es"): [
            ("ser_estar", "To be → Ser/Estar", "Two verbs for 'to be'"),
            ("subjunctive", "Limited → Full system", "WEIRDO triggers, si-clauses"),
            ("adjective_order", "Adj-Noun → Noun-Adj", "Post-nominal adjectives"),
        ],
        ("de", "es"): [
            ("cases", "4 Fälle → 0 Fälle", "Prepositions replace cases"),
            ("gender", "3 Genera → 2 Genera", "Neuter → masculine/feminine"),
            ("verb_position", "V2/Verb-final → SVO", "More rigid word order"),
        ],
        ("es", "de"): [
            ("cases", "0 → 4 Fälle", "Prepositions → case system"),
            ("gender", "2 → 3 Genera", "Neuter added"),
            ("verb_position", "SVO → V2/Verb-final", "Flexible position"),
        ],
    }

    def __init__(self, l1_plugin: LanguagePlugin, l2_plugin: LanguagePlugin, learner_lang: str = "ru"):
        self.l1 = l1_plugin
        self.l2 = l2_plugin
        self.learner_lang = learner_lang
        self.pair_key = (l1_plugin.code, l2_plugin.code)

    def get_false_friends(self, limit: int = 20) -> list[ContrastiveItem]:
        items = []
        if self.pair_key == ("de", "en"):
            data = self.DE_EN_FALSE_FRIENDS
        elif self.pair_key == ("en", "de"):
            data = [(en, de, note) for de, en, note in self.DE_EN_FALSE_FRIENDS]
        elif self.pair_key == ("es", "en"):
            data = self.ES_EN_FALSE_FRIENDS
        elif self.pair_key == ("en", "es"):
            data = [(en, es, note) for es, en, note in self.ES_EN_FALSE_FRIENDS]
        elif self.pair_key == ("de", "es"):
            data = self.DE_ES_FALSE_FRIENDS
        elif self.pair_key == ("es", "de"):
            data = [(es, de, note) for de, es, note in self.DE_ES_FALSE_FRIENDS]
        else:
            data = []

        for l1_lemma, l2_lemma, note in data[:limit]:
            l1_word = self.l1.load_vocab().search(l1_lemma)
            l2_word = self.l2.load_vocab().search(l2_lemma)
            l1_w = l1_word[0] if l1_word else None
            l2_w = l2_word[0] if l2_word else None
            if l1_w and l2_w:
                items.append(ContrastiveItem(
                    id=f"ff_{l1_w.slug}_{l2_w.slug}",
                    l1_word=l1_w,
                    l2_word=l2_w,
                    type="false_friend",
                    l1_explanation=note,
                    l2_explanation=note,
                    false_friend=True,
                ))
        return items

    def get_cognates(self, limit: int = 20) -> list[ContrastiveItem]:
        items = []
        if self.pair_key == ("de", "en"):
            data = self.EN_DE_COGNATES
        elif self.pair_key == ("en", "de"):
            data = [(de, en, note) for en, de, note in self.EN_DE_COGNATES]
        elif self.pair_key == ("es", "en"):
            data = self.EN_ES_COGNATES
        elif self.pair_key == ("en", "es"):
            data = [(es, en, note) for en, es, note in self.EN_ES_COGNATES]
        elif self.pair_key == ("de", "es"):
            data = self.ES_DE_COGNATES
        elif self.pair_key == ("es", "de"):
            data = [(de, es, note) for es, de, note in self.ES_DE_COGNATES]
        else:
            data = []

        for l1_lemma, l2_lemma, note in data[:limit]:
            l1_word = self.l1.load_vocab().search(l1_lemma)
            l2_word = self.l2.load_vocab().search(l2_lemma)
            l1_w = l1_word[0] if l1_word else None
            l2_w = l2_word[0] if l2_word else None
            if l1_w and l2_w:
                items.append(ContrastiveItem(
                    id=f"cog_{l1_w.slug}_{l2_w.slug}",
                    l1_word=l1_w,
                    l2_word=l2_w,
                    type="cognate",
                    l1_explanation=note,
                    l2_explanation=note,
                    cognate=True,
                ))
        return items

    def get_grammar_contrasts(self) -> list[dict]:
        return self.GRAMMAR_CONTRASTS.get(self.pair_key, [])

    def is_unlocked(self, l1_progress) -> bool:
        xp = l1_progress.data.get("xp", {}).get("total", 0)
        return xp >= 1500
"""Languages core package."""
from __future__ import annotations

from .base import LanguagePlugin, VocabSource, GrammarEngine, MorphologyBundle, WordEntry, ExampleSentence
from .registry import LanguageRegistry, get_registry
from .progress import LanguageProgress
from .scheduler import SM2Scheduler, SM2Card
from .access import level_open, unlock_pct, cross_pair_unlocked
from .hooks import TerraformerRewards, calculate_terraformer_energy
from .tts_asr import VoiceManager, TTSProvider, ASRProvider

__all__ = [
    "LanguagePlugin",
    "VocabSource",
    "GrammarEngine",
    "MorphologyBundle",
    "WordEntry",
    "ExampleSentence",
    "LanguageRegistry",
    "get_registry",
    "LanguageProgress",
    "SM2Scheduler",
    "SM2Card",
    "level_open",
    "unlock_pct",
    "cross_pair_unlocked",
    "TerraformerRewards",
    "calculate_terraformer_energy",
    "VoiceManager",
    "TTSProvider",
    "ASRProvider",
]
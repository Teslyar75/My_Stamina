#!/usr/bin/env python3
from stamina.english.grammar import grammar_engine
for l in grammar_engine.list_available_levels():
    g = grammar_engine.load_grammar(l)
    print(f'{l}: {g["total_exercises"]} exercises, {len(g["topics"])} topics')
print("\nAll grammar levels loaded successfully - no hanging")
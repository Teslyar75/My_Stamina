#!/usr/bin/env python3
"""Quick smoke test for English module imports and basic functionality."""
import sys
import time

start = time.time()

try:
    from stamina.english import EnglishScreen
    print(f"[OK] EnglishScreen imported in {time.time()-start:.2f}s")
except Exception as e:
    print(f"[FAIL] EnglishScreen import: {e}")
    sys.exit(1)

try:
    from stamina.english.grammar import grammar_engine
    print(f"[OK] grammar_engine imported in {time.time()-start:.2f}s")
except Exception as e:
    print(f"[FAIL] grammar_engine import: {e}")
    sys.exit(1)

levels = grammar_engine.list_available_levels()
print(f"[OK] Levels: {levels}")

start_gen = time.time()
ex = grammar_engine.generate_exercise('a1', 'Present Simple')
print(f"[OK] Exercise generated in {time.time()-start_gen:.2f}s: {ex['topic']}")

try:
    from stamina.english.pages_grammar import init_grammar_tab
    print(f"[OK] pages_grammar imported in {time.time()-start:.2f}s")
except Exception as e:
    print(f"[FAIL] pages_grammar import: {e}")
    sys.exit(1)

print(f"\nTotal import time: {time.time()-start:.2f}s")
print("All imports OK - no hanging detected")
# Orchestrator config - read by orch-plan / orch-delegate / orch-entropy
code_repo: .
main_branch: master
gate: python -m unittest discover -s tests
worktree_dir: ../.wt
link_dirs:
executor: export PYTHONUTF8=1 PYTHONIOENCODING=utf-8 OPENAI_API_BASE=http://127.0.0.1:31415/v1 OPENAI_API_KEY="$FREELLMAPI_API_KEY"; echo "{}" > "$USAGE"; cd "$WT" && aider --model openai/auto:fast --yes-always --no-auto-lint --no-show-model-warnings --no-check-update --no-analytics --no-gitignore --no-pretty --no-stream --message "$PROMPT"
chat_language: Russian
file_language: English
glossary:
plans_dir: plans
ops_dir: ops
archive_dir: archive
core_docs: AGENTS.md, README.md, CHANGELOG.md
known_flakes:
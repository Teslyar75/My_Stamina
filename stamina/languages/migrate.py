"""Migration script: english.json -> lang_en.json"""
from __future__ import annotations

import json
import shutil
from pathlib import Path


def migrate_english_progress(pilot_dir: Path) -> bool:
    old_file = pilot_dir / "english.json"
    new_file = pilot_dir / "lang_en.json"
    backup_file = pilot_dir / "english.json.migrated"

    if not old_file.exists():
        return False

    if new_file.exists():
        return False

    try:
        data = json.loads(old_file.read_text(encoding="utf-8"))
        data["_lang"] = "en"
        data["_migrated_from"] = "english.json"
        new_file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.move(str(old_file), str(backup_file))
        return True
    except Exception as e:
        print(f"Migration failed: {e}")
        return False


def migrate_all_pilots(root_dir: Path) -> int:
    count = 0
    pilots_dir = root_dir / "pilots"
    if not pilots_dir.exists():
        return 0

    for pilot_dir in pilots_dir.iterdir():
        if pilot_dir.is_dir():
            if migrate_english_progress(pilot_dir):
                count += 1
                print(f"Migrated: {pilot_dir.name}")
    return count


if __name__ == "__main__":
    import sys
    from stamina import pilots
    if len(sys.argv) > 1:
        pilot_id = sys.argv[1]
        pilot_dir = pilots.pilot_dir(pilot_id)
        if migrate_english_progress(pilot_dir):
            print(f"Migrated pilot {pilot_id}")
        else:
            print(f"No migration needed for {pilot_id}")
    else:
        root = pilots.ROOT_DIR
        count = migrate_all_pilots(root)
        print(f"Migrated {count} pilots")
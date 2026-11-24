Исправлены все 7 падающих тестов в CI:

1. **Alt UI** — добавлен глиф 🌐 и обои languages.jpg/languages_2.jpg для профилей starship и zen_garden
2. **test_languages_sqlite.py** — убран хардкодный Windows путь
3. **Spanish A1 vocab** — 458 слов (требуется ≥300)
4. **Orion profiles** — PROFILES[commander] возвращает ("orion-recon", "orion-commander")
5. **requirements.txt** — 4 зависимости (edge-tts закомментирован)
6. **Terraformer bay** — подсказка включает A1 и порог процента
7. **TrainerGame.do_unload()** — добавлен метод

**i18n:** добавлены переводы для 5 новых строк в ru/en/uk/de

✅ Все 183 теста проходят
✅ Quality gates зелёные
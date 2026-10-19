"""Движки озвучки: выбор языка и голоса, доступность, поведение без движка.

Тесты ничего не произносят вслух: движки создаются, но фразы им не отправляются.
"""

import sys
import unittest

from stamina.voice import engine as eng


class GuessLangTests(unittest.TestCase):
    def test_russian(self):
        self.assertEqual(eng.guess_lang("Привет, мир"), "ru")

    def test_english(self):
        self.assertEqual(eng.guess_lang("Hello, world"), "en")

    def test_empty(self):
        self.assertEqual(eng.guess_lang(""), "")
        self.assertEqual(eng.guess_lang("123 : — …"), "")

    def test_patterns(self):
        self.assertEqual(eng.voice_pattern("ru"), "ru-*")
        self.assertEqual(eng.voice_pattern("en"), "en-*")
        self.assertEqual(eng.voice_pattern(""), "*")
        self.assertEqual(eng.voice_pattern("Microsoft Irina"), "Microsoft Irina")


class MakeEngineTests(unittest.TestCase):
    def test_auto_returns_engine(self):
        e = eng.make_engine("auto")
        self.assertIsInstance(e, eng.Engine)
        self.assertIn(e.name, ("onecore", "sapi", "espeak"))

    def test_auto_prefers_onecore_on_windows(self):
        """Современные голоса (мужской русский Павел) живут только в OneCore."""
        if sys.platform != "win32":
            self.skipTest("Windows-only")
        self.assertEqual(eng.make_engine("auto").name, "onecore")

    def test_named_and_cached(self):
        a = eng.make_engine("espeak")
        b = eng.make_engine("espeak")
        self.assertIs(a, b)
        self.assertIsNot(a, eng.make_engine("espeak", fresh=True))

    def test_unknown_name_falls_back(self):
        self.assertIsInstance(eng.make_engine("нет такого"), eng.Engine)

    def test_available_engines_is_a_list(self):
        self.assertIsInstance(eng.available_engines(), list)


class UnavailableEngineTests(unittest.TestCase):
    """Движок, которого нет на этой машине: speak → 0 и событие error, интерфейс не падает."""

    def test_espeak_on_windows(self):
        if sys.platform == "win32":
            e = eng.EspeakEngine()
            self.assertFalse(e.available)
            self.assertEqual(e.speak("текст"), 0)
            kinds = [k for k, _, _ in e.poll()]
            self.assertIn("error", kinds)
            self.assertTrue(e.why_unavailable())
        else:
            self.skipTest("Linux: espeak проверяется вручную")

    def test_empty_text_is_ignored(self):
        e = eng.EspeakEngine()
        self.assertEqual(e.speak("   "), 0)
        self.assertEqual(e.poll(), [])

    def test_stop_on_dead_engine_is_safe(self):
        e = eng.EspeakEngine()
        e.stop()
        e.close()


class WindowsEngineTests(unittest.TestCase):
    def test_sapi_available_on_windows(self):
        if sys.platform != "win32":
            self.skipTest("Windows-only")
        e = eng.SapiEngine()
        self.assertTrue(e.available)
        self.assertIsInstance(e.voices(), list)
        self.assertEqual(e.name, "sapi")

    def test_windows_voices_shape(self):
        if sys.platform != "win32":
            self.skipTest("Windows-only")
        for item in eng.windows_voices():
            self.assertEqual(len(item), 3)
            self.assertTrue(item[0])


class VoiceScriptTests(unittest.TestCase):
    """Скрипт голоса Ориона: современные голоса OneCore (там есть мужской русский)."""

    def setUp(self):
        from stamina.voice import tts
        self.tts = tts
        self.script = tts.say_script()

    def test_script_is_ascii(self):
        """PowerShell 5.1 читает .ps1 без BOM как ANSI — кириллица сломала бы разбор."""
        raw = self.script.read_bytes()
        self.assertEqual([b for b in raw if b > 127], [])

    def test_uses_onecore_store(self):
        text = self.script.read_text(encoding="utf-8")
        self.assertIn("Windows.Media.SpeechSynthesis", text)
        self.assertIn("SoundPlayer", text)

    def test_keeps_system_speech_fallback(self):
        """Нет WinRT (серверные сборки) — корабль всё равно должен говорить."""
        text = self.script.read_text(encoding="utf-8")
        self.assertIn("System.Speech", text)

    def test_prefers_male_russian_voice(self):
        text = self.script.read_text(encoding="utf-8")
        self.assertIn("'Male'", text)
        self.assertIn("ru*", text)


class MaleVoiceTests(unittest.TestCase):
    """Выбор мужского голоса: Павел из OneCore, иначе русский из System.Speech."""

    def _with_rows(self, rows):
        from stamina.voice import tts
        real = tts.voices
        tts.voices = lambda: rows
        try:
            return tts.male_voice()
        finally:
            tts.voices = real

    def test_picks_onecore_male(self):
        rows = ["OneCore|Microsoft Irina|ru-RU|Female",
                "OneCore|Microsoft Pavel|ru-RU|Male",
                "SAPI|Microsoft Zira Desktop|en-US|Female"]
        self.assertEqual(self._with_rows(rows), "Microsoft Pavel")

    def test_falls_back_to_russian(self):
        self.assertEqual(self._with_rows(["SAPI|Microsoft Irina Desktop|ru-RU|Female"]),
                         "Microsoft Irina Desktop")

    def test_empty_when_no_voices(self):
        self.assertEqual(self._with_rows([]), "")


class SpeechTextTests(unittest.TestCase):
    def test_limit_is_generous(self):
        """У движка лимита нет: режем только ради терпения пилота."""
        from stamina.voice import tts
        self.assertGreaterEqual(tts.SPEECH_LIMIT, 900)

    def test_long_report_is_cut_by_sentence(self):
        from stamina.voice import tts
        text = ("Первое предложение о курсе. " * 80).strip()
        out = tts.speech_text(text)
        self.assertLessEqual(len(out), tts.SPEECH_LIMIT + 1)
        self.assertTrue(out.endswith(".") or out.endswith("…"), out[-20:])

    def test_markers_are_not_read(self):
        from stamina.voice import tts
        out = tts.speech_text("⟦ТРЕБУЕТСЯ РАЗРЕШЕНИЕ⟧ починить нос")
        self.assertNotIn("ТРЕБУЕТСЯ", out)


class PickVoiceTests(unittest.TestCase):
    """Выбор голоса по языку текста: английскую книгу не читает русский голос."""

    VOICES = [("Microsoft Irina", "ru-RU", "Female"),
              ("Microsoft Pavel", "ru-RU", "Male"),
              ("Microsoft Zira Desktop", "en-US", "Female"),
              ("Microsoft Guy", "en-US", "Male")]

    def test_russian_prefers_male(self):
        self.assertEqual(eng.pick_voice(self.VOICES, "ru"), "Microsoft Pavel")

    def test_english_prefers_english_male(self):
        self.assertEqual(eng.pick_voice(self.VOICES, "en"), "Microsoft Guy")

    def test_english_never_takes_russian(self):
        only_ru = [v for v in self.VOICES if v[1].startswith("ru")]
        self.assertEqual(eng.pick_voice(only_ru, "en"), "")

    def test_unknown_language_returns_empty(self):
        """Голоса такого языка нет — пусть решает вызывающий (фолбэк), а не чужой язык."""
        self.assertEqual(eng.pick_voice(self.VOICES, "ja"), "")

    def test_explicit_name_wins(self):
        self.assertEqual(eng.pick_voice(self.VOICES, "ru", "Zira"), "Microsoft Zira Desktop")

    def test_explicit_language_code(self):
        self.assertEqual(eng.pick_voice(self.VOICES, "", "en-us"), "Microsoft Zira Desktop")

    def test_empty_list(self):
        self.assertEqual(eng.pick_voice([], "ru"), "")


class VoiceOptionsTests(unittest.TestCase):
    """Список голосов для выбора в читалке: «по языку текста» плюс оба хранилища."""

    def test_first_option_is_automatic(self):
        opts = eng.voice_options()
        self.assertTrue(opts)
        self.assertEqual(opts[0][1], "")

    def test_specs_carry_store(self):
        for label, spec in eng.voice_options()[1:]:
            self.assertIn(":", spec, label)
            self.assertIn(spec.split(":", 1)[0], ("onecore", "sapi"), label)

    def test_engine_for_spec(self):
        if sys.platform != "win32":
            self.skipTest("Windows-only")
        e, voice = eng.make_engine_for("sapi:Microsoft Zira Desktop")
        self.assertEqual((e.name, voice), ("sapi", "Microsoft Zira Desktop"))
        e, voice = eng.make_engine_for("onecore:Microsoft Pavel")
        self.assertEqual((e.name, voice), ("onecore", "Microsoft Pavel"))
        e, voice = eng.make_engine_for("")
        self.assertEqual(voice, "")

    def test_engine_for_unknown_spec_falls_back(self):
        e, voice = eng.make_engine_for("нет-такого:голос")
        self.assertIsInstance(e, eng.Engine)


if __name__ == "__main__":
    unittest.main()

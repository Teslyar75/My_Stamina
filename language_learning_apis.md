# Language Learning APIs & Services for German & Spanish

Comprehensive directory of online services and APIs providing German (DE) and Spanish (ES) language learning materials.

---

## Category 1: Official / Corporate APIs

| Service | API Docs | Auth | Free Tier | DE Coverage | ES Coverage | CEFR-aligned | Best For |
|---------|----------|------|-----------|-------------|-------------|--------------|----------|
| **DeepL API** | https://developers.deepl.com/docs | API Key | Free: 500K chars/mo; Pro: pay-per-char | Full (DE) with glossaries, formality | Full (ES) with glossaries, formality | No | High-quality translation, glossary enforcement |
| **Microsoft Translator** | https://learn.microsoft.com/azure/ai-services/translator/ | API Key / Azure AD | Free: 2M chars/mo; Pay-as-you-go | Full (DE) with Dictionary, transliteration | Full (ES) with Dictionary, transliteration | No | Enterprise translation, real-time, document translation |
| **Google Cloud Translation** | https://cloud.google.com/translate/docs | API Key / OAuth | Free: 500K chars/mo (Basic); pay-per-char (Advanced) | Full (DE) AutoML, glossaries | Full (ES) AutoML, glossaries | No | Scalable cloud translation, custom models |
| **Amazon Translate** | https://docs.aws.amazon.com/translate/ | AWS SigV4 / IAM | Free: 2M chars/mo (12 mo); then /M chars | Full (DE) custom terminology | Full (ES) custom terminology | No | AWS ecosystem integration, batch translation |

---

## Category 2: Open / Public APIs

| Service | API Docs | Auth | Free Tier | DE Coverage | ES Coverage | CEFR-aligned | Best For |
|---------|----------|------|-----------|-------------|-------------|--------------|----------|
| **Tatoeba API** | https://api.tatoeba.org (OpenAPI: /openapi.json) | None | Unlimited free | 1M+ DE sentences, translations | 500K+ ES sentences, translations | No | Sentence pairs, translations, corpus linguistics |
| **Wiktionary / MediaWiki API** | https://en.wiktionary.org/w/api.php | None (OAuth optional) | Unlimited free | Full definitions, etymology, examples, pronunciations | Full definitions, etymology, examples, pronunciations | Partial (some CEFR tags) | Dictionary data, multilingual definitions, audio |
| **LibreTranslate** | https://docs.libretranslate.com | API Key (managed) / None (self-hosted) | Free self-hosted; managed: tiered | Full (DE) via Argos Translate | Full (ES) via Argos Translate | No | Privacy-focused, self-hostable translation |
| **LanguageTool API** | https://api.languagetool.org/v2/check | None (API key for higher limits) | Free: 20 req/IP/min, 75KB/min | DE grammar, style, spell check | ES grammar, style, spell check | No | Grammar checking, writing assistance |
| **OpenSubtitles API** | https://api.opensubtitles.com/api/v1/docs | API Key | Free tier limited | DE subtitles | ES subtitles | No | Subtitle corpus, alignment data |

---

## Category 3: NLP / Linguistic APIs

| Service | API Docs | Auth | Free Tier | DE Coverage | ES Coverage | CEFR-aligned | Best For |
|---------|----------|------|-----------|-------------|-------------|--------------|----------|
| **spaCy (models)** | https://spacy.io/models | pip install | Open source (MIT) | de_core_news_sm/md/lg, de_dep_news_trf (POS, NER, DEP) | es_core_news_sm/md/lg, es_dep_news_trf (POS, NER, DEP) | No | POS tagging, NER, dependency parsing, lemmatization |
| **Universal Dependencies** | https://universaldependencies.org | Direct download | Open source | GSD, HDT, PUD, LIT treebanks | GSD, AnCora, PUD, AnCora treebanks | No | Training parsers, linguistic research |
| **Hugging Face Transformers** | https://huggingface.co/models | API Key (Inference API) / None (local) | Free inference API (rate limited) | 1000+ DE models (BERT, XLM-R, etc.) | 1000+ ES models (BETO, XLM-R, etc.) | No | Classification, NER, QA, embeddings, fine-tuning |
| **Stanford CoreNLP** | https://stanfordnlp.github.io/CoreNLP/ | Java lib | Open source (GPL) | German models (POS, NER, parse) | Spanish models (POS, NER, parse) | No | Full pipeline, research, education |
| **NLTK** | https://www.nltk.org/ | pip install | Open source | German corpora (Tiger, etc.) | Spanish corpora (CESS, etc.) | No | Teaching, prototyping, corpus access |

---

## Category 4: CEFR-Aligned Content Sources

| Service | API Docs | Auth | Free Tier | DE Coverage | ES Coverage | CEFR-aligned | Best For |
|---------|----------|------|-----------|-------------|-------------|--------------|----------|
| **COERLL (UT Austin)** | https://coerll.utexas.edu/coerll/materials/ | None | All OER (CC BY) | Deutsch im Blick, Grimm Grammar, textbooks | Spanish textbooks, SpinTX video corpus | Yes (curriculum aligned) | Open textbooks, curricula, video corpus |
| **CEFR-J Resources** | https://cefr-j.org/download.html | None | Free download | — | — | Yes (English wordlists, grammar profiles, CAN-DO) | CEFR reference levels, wordlists, descriptors |
| **English Vocabulary Profile** | https://www.englishprofile.org/wordlists | Registration | Free (research) | — | — | Yes (A1-C2 wordlists) | CEFR-level vocabulary benchmarking |
| **German Vocabulary Profile (DWDS)** | https://www.dwds.de/ | None | Free | Yes (frequency lists, CEFR tags via DWDS) | — | Yes (A1-C2 frequency bands) | German corpus linguistics, vocab profiling |
| **Instituto Cervantes / CEFR** | https://cvc.cervantes.es/ | None | Free | — | Yes (Plan Curricular, levels A1-C2) | Yes (official CEFR Spanish curricula) | Spanish CEFR reference, syllabi |
| **Goethe-Institut** | https://www.goethe.de/ | None (site blocks bots) | Free materials | Yes (practice materials, exams) | — | Yes (exam-aligned A1-C2) | Exam prep, official German materials |

---

## Category 5: TTS / ASR APIs

| Service | API Docs | Auth | Free Tier | DE Voices/Models | ES Voices/Models | CEFR-aligned | Best For |
|---------|----------|------|-----------|------------------|------------------|--------------|----------|
| **Azure Speech (TTS/ASR)** | https://learn.microsoft.com/azure/ai-services/speech-service/ | API Key / Azure AD | Free: 5h audio/mo (TTS), 5h/mo (ASR) | Neural: de-DE (Katja, Conrad, etc.), HD, multilingual | Neural: es-ES (Elvira, Alvaro), es-MX (Dalia, Jorge), HD | No | Enterprise TTS/ASR, custom voice, real-time |
| **Google Cloud TTS** | https://cloud.google.com/text-to-speech/docs | API Key / OAuth | Free: 1M chars/mo (Standard), 1M chars/mo (Neural2) | Neural2: de-DE (G, H); Studio: B, C; Chirp3-HD: 20+ voices | Neural2: es-ES (G, H); Studio; Chirp3-HD: 20+ voices | No | High-quality neural TTS, SSML, voice cloning |
| **Amazon Polly** | https://docs.aws.amazon.com/polly/latest/dg/ | AWS SigV4 | Free: 5M chars/mo (12 mo) | Neural: Marlene, Vicki, Hans, Daniel, Lennart, Tina; Generative: Vicki, Daniel, Lennart, Tina | Neural: Lucia, Alba, Enrique, Sergio, Raul; Generative: Lucia, Sergio | No | AWS integration, SSML, newscaster style |
| **Amazon Transcribe** | https://docs.aws.amazon.com/transcribe/ | AWS SigV4 | Free: 60 min/mo (12 mo) | de-DE, de-CH (batch + streaming, custom LM) | es-ES, es-MX, es-US (batch + streaming, custom LM) | No | AWS ecosystem, streaming, custom vocab |
| **Coqui TTS (XTTS v2)** | https://github.com/coqui-ai/TTS | pip install / local | Open source (MPL-2.0) | DE supported (xtts_v2, VITS, YourTTS, Fairseq VITS 1100+ langs) | ES supported (xtts_v2, YourTTS, Fairseq VITS) | No | Voice cloning, multilingual, local inference |
| **Piper TTS** | https://github.com/rhasspy/piper | pip install / binary | Open source (MIT) | DE: eva_k, karlsson, kerstin, mls, pavoque, ramona, thorsten (x_low/high) | ES: carlfm, davefx, mls_10246, mls_9972, sharvard (es-ES); ald, claude (es-MX); daniela (es-AR) | No | Fast local neural TTS, ONNX, Raspberry Pi |
| **Vosk ASR** | https://alphacephei.com/vosk/models | Direct download | Open source (Apache 2.0) | DE: vosk-model-de-0.21 (1.9G), vosk-model-de-tuda-0.6-900k (4.4G), small (45M) | ES: vosk-model-es-0.42 (1.4G), small (39M) | No | Offline ASR, mobile/embedded, streaming |
| **Whisper (OpenAI)** | https://github.com/openai/whisper | pip install / local | Open source (MIT) | DE (de): tiny to large-v3, turbo; WER ~5-10% | ES (es): tiny to large-v3, turbo; WER ~5-10% | No | High-accuracy multilingual ASR, translation, language ID |
| **ElevenLabs API** | https://elevenlabs.io/docs/api-reference | API Key | Free: 10K chars/mo | DE: 20+ voices (multilingual v2) | ES: 20+ voices (multilingual v2) | No | Ultra-realistic TTS, voice cloning, dubbing |

---

## Category 6: Exercise / Quiz Generation APIs

| Service | API Docs | Auth | Free Tier | DE Coverage | ES Coverage | CEFR-aligned | Best For |
|---------|----------|------|-----------|-------------|-------------|--------------|----------|
| **AnkiConnect** | https://github.com/FooSoft/anki-connect | Local (port 8765) | Free (local plugin) | Any (user-created decks) | Any (user-created decks) | User-defined | Flashcard automation, spaced repetition |
| **H5P** | https://h5p.org/documentation/api | LTI / REST (varies) | Open source (MIT) | Content types: Fill in Blanks, Drag & Drop, Quiz, etc. | Content types: Fill in Blanks, Drag & Drop, Quiz, etc. | Content-dependent | Interactive content, LMS integration (Moodle, WP) |
| **Quizlet API** | https://quizlet.com/guide/api (deprecated v2.0) | OAuth 2.0 | Limited (terms apply) | User sets, classes | User sets, classes | User-defined | Flashcard access, study modes (API access restricted) |
| **Moodle Web Services** | https://docs.moodle.org/dev/Web_services | Token / OAuth | Free (self-hosted) | Quiz, Lesson, H5P activities | Quiz, Lesson, H5P activities | Course-dependent | LMS-based exercise delivery, grading |

---

## Category 7: Authentic Content Feeds (RSS / Podcast)

| Service | Feed URL | Format | DE Coverage | ES Coverage | CEFR-aligned | Best For |
|---------|----------|--------|-------------|-------------|--------------|----------|
| **Radio Ambulante** | https://radioambulante.org/feed | RSS 2.0 | — | Full (Latin American Spanish, transcripts, translations) | No | Authentic listening, transcripts, cultural content |
| **Notes in Spanish** | https://www.notesinspanish.com/feed/ | RSS 2.0 | — | Full (Peninsular Spanish, video + audio, worksheets) | No | Conversational Spanish, slang, grammar |
| **Slow German** | https://slowgerman.com/feed/ | RSS 2.0 + iTunes | Full (slow German, PDF transcripts, premium materials) | — | Approx. A2-B1 | Graded listening, cultural topics, PDF transcripts |
| **DW Top-Thema** | https://rss.dw.com/xml/DKpodcast_topthema_de | RSS (JS-blocked) | Full (news, simplified, exercises) | — | Yes (A2-B1) | News-based learning, exercises (site blocks bots) |
| **DW Nicos Weg** | (No public RSS found) | — | Full (video course A1-B1) | — | Yes (A1-B1) | Structured video course (no API) |
| **Deutsche Welle (general)** | https://rss.dw.com/ | RSS (requires JS) | Multiple feeds | Multiple feeds | Varies | News, culture (site blocks automated access) |

---

## Summary: Recommended Stack by Use Case

| Use Case | Recommended Services |
|----------|---------------------|
| **Translation + Glossaries** | DeepL API (best quality), Microsoft Translator (enterprise), LibreTranslate (self-hosted) |
| **Grammar Checking** | LanguageTool API (free tier generous) |
| **Sentence Corpus / Translations** | Tatoeba API (open, no auth), OpenSubtitles (subtitles) |
| **Dictionary / Definitions** | Wiktionary API (MediaWiki), DWDS (German) |
| **NLP Pipeline (POS, NER, DEP)** | spaCy (production), Stanza/HuggingFace (research) |
| **CEFR-Aligned Curricula** | COERLL (open textbooks), Goethe/Cervantes (official), English/German/Spanish Vocabulary Profiles |
| **TTS (Cloud, High Quality)** | Google Cloud TTS (Neural2/Studio/Chirp3), Azure Speech (HD), ElevenLabs (cloning) |
| **TTS (Local, Fast, Free)** | Piper TTS (ONNX, Raspberry Pi), Coqui XTTS v2 (voice cloning) |
| **ASR (Cloud, Streaming)** | Azure Speech, Amazon Transcribe, Google Speech-to-Text |
| **ASR (Local, Offline)** | Whisper (best accuracy), Vosk (mobile/embedded, streaming) |
| **Flashcards / SRS** | AnkiConnect (local automation) |
| **Interactive Exercises** | H5P (open content types), Moodle (LMS) |
| **Authentic Listening (DE)** | Slow German (RSS, graded, transcripts) |
| **Authentic Listening (ES)** | Radio Ambulante (RSS, transcripts, translations), Notes in Spanish (RSS, video) |

---

## Notes on Blocked / Unavailable Services

| Service | Status | Notes |
|---------|--------|-------|
| **Deutsche Welle API** | No public API | Site requires JavaScript; RSS endpoints return 404 or require JS |
| **Goethe-Institut API** | Blocks bots (403) | No discoverable public API; materials behind login |
| **Instituto Cervantes API** | Unreachable / blocks | No public API found |
| **Duolingo / Babbel / Busuu / Memrise / Rosetta Stone** | No public APIs | Proprietary platforms, no developer access |
| **Quizlet API v2.0** | Deprecated / 403 | OAuth flow unclear; developer portal inaccessible |
| **H5P REST API** | 403 on docs | LTI integration primary; REST varies by host |
| **OpenSubtitles API** | 403/404 on docs | Requires registration; API access unclear |
| **Cambridge / Oxford / AQA** | No public APIs | Exam boards; materials behind paywalls |
| **WordReference / Linguee / Glosbe / Yandex Dictionary** | API access unclear | Some offer widgets; no documented REST APIs |

---

*Last updated: 2026-11-14*
*Sources verified via direct HTTP fetch of documentation pages and RSS feeds.*

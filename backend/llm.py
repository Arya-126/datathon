"""NL→SQL over the FIR schema — rotating provider chain:

  1. Catalyst QuickML (LLM serving) — primary once an endpoint is deployed
     (set CATALYST_QUICKML_ENDPOINT_KEY; requires a Catalyst request context).
  2. Hosted LLMs, tried in order, each key skipped while on cooldown after a
     429/quota error so the next key/provider takes over automatically:
       - Google Gemini      GEMINI_API_KEY / GEMINI_API_KEYS (comma pool)
       - Groq               GROQ_API_KEY   (OpenAI-compatible)
       - OpenRouter         OPENROUTER_API_KEY (OpenAI-compatible)
       - OpenAI             OPENAI_API_KEY
       - Anthropic          ANTHROPIC_API_KEY (raw HTTP, no SDK)
     All called over plain HTTP — no per-provider SDK dependencies.
  3. Local keyword rules — deterministic offline demo (fully bilingual).
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass

import requests

import catalyst
from db import LLM_SCHEMA_DOC

LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT",
                                   os.environ.get("GEMINI_TIMEOUT", "30")))
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

# provider id -> unix timestamp until which it is skipped (quota cooldown)
_COOLDOWN: dict[str, float] = {}

# API keys must never appear in error messages/logs shown to the frontend.
_KEY_URL_RE = re.compile(r"[?&]key=[^&\s]+")


def _providers() -> list[dict]:
    """Build the hosted-LLM chain from env. Re-read per call so keys added
    to the AppSail env after boot are picked up without a restart."""
    out: list[dict] = []
    pool: list[str] = []
    if os.environ.get("GEMINI_API_KEY"):
        pool.append(os.environ["GEMINI_API_KEY"].strip())
    pool += [k.strip() for k in
             os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]
    seen: set[str] = set()
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    n = 0
    for key in pool:
        if key in seen:
            continue
        seen.add(key)
        n += 1
        out.append({"id": "gemini" if n == 1 else f"gemini#{n}",
                    "kind": "gemini", "key": key, "model": gemini_model})
    if os.environ.get("GROQ_API_KEY"):
        out.append({"id": "groq", "kind": "openai",
                    "key": os.environ["GROQ_API_KEY"].strip(),
                    "model": os.environ.get("GROQ_MODEL",
                                            "llama-3.3-70b-versatile"),
                    "base": "https://api.groq.com/openai/v1"})
    if os.environ.get("OPENROUTER_API_KEY"):
        out.append({"id": "openrouter", "kind": "openai",
                    "key": os.environ["OPENROUTER_API_KEY"].strip(),
                    "model": os.environ.get(
                        "OPENROUTER_MODEL",
                        "meta-llama/llama-3.3-70b-instruct:free"),
                    "base": "https://openrouter.ai/api/v1"})
    if os.environ.get("OPENAI_API_KEY"):
        out.append({"id": "openai", "kind": "openai",
                    "key": os.environ["OPENAI_API_KEY"].strip(),
                    "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                    "base": "https://api.openai.com/v1"})
    if os.environ.get("ANTHROPIC_API_KEY"):
        out.append({"id": "anthropic", "kind": "anthropic",
                    "key": os.environ["ANTHROPIC_API_KEY"].strip(),
                    "model": os.environ.get("ANTHROPIC_MODEL",
                                            "claude-haiku-4-5-20251001")})
    return out


def configured_providers() -> list[str]:
    """Provider ids with a key present — surfaced on /health."""
    return [p["id"] for p in _providers()]


def _sanitize_error(msg: str) -> str:
    """Strip ?key=… query params and every configured key string so a raw
    exception is safe to echo to the user."""
    msg = _KEY_URL_RE.sub("?key=REDACTED", msg)
    for p in _providers():
        if len(p["key"]) > 6:
            msg = msg.replace(p["key"], "REDACTED")
    return msg

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|"
    r"replace|truncate|vacuum)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------- prompt
SYSTEM_PROMPT = f"""You are the query engine for the Karnataka State Police
Crime Records conversational AI. Investigators ask questions in English or
Kannada; you translate them into a safe SQLite SELECT against this schema:

{LLM_SCHEMA_DOC}

Rules:
1. Reply ONLY with a JSON object matching this schema:
   {{
     "language": "en" | "kn",
     "sql": "SELECT ... LIMIT 200",
     "explanation_en": "one plain-English sentence describing what the SQL does",
     "explanation_kn": "the same sentence in Kannada — ALWAYS provide this, regardless of the question's language",
     "chart_hint": "table" | "bar" | "line" | "map" | "network",
     "answer_prefix_en": "one-sentence natural-language lead-in for the result",
     "answer_prefix_kn": "the same lead-in in Kannada — ALWAYS provide this, regardless of the question's language"
   }}
2. SQL MUST be a single SELECT (no INSERT/UPDATE/DELETE/DDL, no ';').
3. Always add LIMIT 200 unless the question is an aggregate.
3b. District.DistrictName values are EXACTLY these 15 — always map
    colloquial/anglicized/Kannada names to them before filtering:
      Bengaluru Urban, Bengaluru Rural, Mysuru, Mangaluru,
      Hubballi-Dharwad, Belagavi, Kalaburagi, Ballari, Vijayapura,
      Shivamogga, Tumakuru, Davanagere, Udupi, Chitradurga, Raichur
    Mappings:
      Bangalore/Bengaluru/ಬೆಂಗಳೂರು → 'Bengaluru Urban' (add 'Bengaluru Rural' too if metro);
      Mysore/Mysuru/ಮೈಸೂರು → Mysuru;
      Mangalore/Mangaluru/ಮಂಗಳೂರು → Mangaluru;
      Hubli/Dharwad/Hubballi/ಹುಬ್ಬಳ್ಳಿ/ಧಾರವಾಡ → Hubballi-Dharwad;
      Gulbarga/Kalaburagi/ಕಲಬುರಗಿ → Kalaburagi;
      Bellary/Ballari/ಬಳ್ಳಾರಿ → Ballari;
      Bijapur/Vijayapura/ವಿಜಯಪುರ → Vijayapura;
      Shimoga/Shivamogga/ಶಿವಮೊಗ್ಗ → Shivamogga;
      Tumkur/Tumakuru/ತುಮಕೂರು → Tumakuru;
      Belgaum/Belagavi/ಬೆಳಗಾವಿ → Belagavi;
      Udupi/ಉಡುಪಿ → Udupi; Chitradurga/ಚಿತ್ರದುರ್ಗ → Chitradurga; Raichur/ರಾಯಚೂರು → Raichur.
    Never emit a district literal outside this list.
3c. Kannada Queries & Vocabulary Mapping:
    - User questions may be written in Kannada script (e.g. 'ಬೆಂಗಳೂರಿನಲ್ಲಿ ಎಷ್ಟು ಕೊಲೆ ಪ್ರಕರಣಗಳು?', 'ಯಾವ ಜಿಲ್ಲೆಯಲ್ಲಿ ಅತಿ ಹೆಚ್ಚು ಅಪರಾಧಗಳಿವೆ?', 'ಸೈಬರ್ ಅಪರಾಧಗಳ ಪಟ್ಟಿ').
    - Translate Kannada terms to schema entities:
      കൊലെ / ಕೊಲೆ / ಹತ್ಯೆ → Murder / IPC 302
      ಸೈಬರ್ / ಆನ್‌ಲೈನ್ → Cyber Crimes
      ಕಳ್ಳತನ / ದರೋಡೆ / ಮನೆ ಕಳ್ಳತನ → Theft / Robbery / Burglary
      ಅಪರಾಧಗಳು / ಪ್ರಕರಣಗಳು / ಎಫ್‌ಐಆರ್ → Cases / CaseMaster
      ಠಾಣೆ / ಪೋಲೀಸ್ ಠಾಣೆ / ಪ್ರದೇಶ → Unit (Police Station)
      ಜಿಲ್ಲೆ / ಜಿಲ್ಲೆಗಳು → District
      ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿ → Repeat offenders (PersonAlias)
      ಮಾದಕ ವಸ್ತು / ಗಾಂಜಾ → NDPS
      ಮಹಿಳೆ / ವರದಕ್ಷಿಣೆ / ಅತ್ಯಾಚಾರ → Crimes against women
    - Set "language": "kn" whenever the input query is in Kannada.
    - ALWAYS populate both explanation_kn and answer_prefix_kn in fluent, natural Kannada.

4. Never SELECT columns from ComplainantDetails, Victim, or Accused unless
   the query is an aggregate (COUNT/GROUP BY). Row-level projections of
   caste_master_name / ReligionName / OccupationName are forbidden — those
   are sensitive demographic fields.
5. For "hotspot" / "top district" style questions across districts → chart_hint="bar", group by District.DistrictName.
5b. For "which areas" / "police station" / "sub-district" hotspot questions within a specific city or district (e.g. 'which areas in Bangalore have the most murder cases'), filter by that district (e.g. `District.DistrictName IN ('Bengaluru Urban', 'Bengaluru Rural')`), join `Unit u ON u.UnitID = c.PoliceStationID`, group by `u.UnitName` (and `d.DistrictName`), count cases (`COUNT(c.CaseMasterID) AS cases`), order by `cases DESC`, and set `chart_hint="bar"`.
6. For "trend over time" / "monthly" → chart_hint="line", group by
   strftime('%Y-%m', c.CrimeRegisteredDate) and CrimeHead.CrimeGroupName.
7. For "co-accused" / "network" / "gang" → chart_hint="network"; return
   columns (a_id, a_name, b_id, b_name, shared_cases). Use PersonAlias for
   cross-case identity.
8. For act/section questions ("cases under IPC 302"), join
   ActSectionAssociation → Act / Section.
9. For chargesheet-rate questions, use ChargesheetDetails.cstype = 'A'.
10. If a previous assistant turn contains "[SQL] ..." context, treat
    follow-up questions ("only Mysuru", "just last month") as refinements
    of that SQL.
11. If the question can't be answered from this schema, set sql="" and
    put the reason in explanation_en.
"""


@dataclass
class LLMResult:
    language: str = "en"
    sql: str = ""
    explanation_en: str = ""
    explanation_kn: str = ""
    chart_hint: str = "table"
    answer_prefix_en: str = ""
    answer_prefix_kn: str = ""
    raw: str = ""
    used_fallback: bool = False
    provider: str = "fallback"  # "quickml" | "gemini" | "fallback"


@dataclass
class ChatTurn:
    role: str  # 'user' | 'assistant'
    content: str


# ---------------------------------------------------------------- SQL guardrail
def is_safe_sql(sql: str) -> tuple[bool, str]:
    s = sql.strip().rstrip(";")
    if not s:
        return False, "empty SQL"
    if ";" in s:
        return False, "multiple statements not allowed"
    if not re.match(r"^\s*select\b|^\s*with\b", s, re.IGNORECASE):
        return False, "only SELECT/WITH allowed"
    if FORBIDDEN_SQL.search(s):
        return False, "forbidden keyword"
    return True, ""


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    """Convert chat-style messages (role: user|assistant) to Gemini's
    contents shape (role: user|model, parts: [{text}])."""
    out: list[dict] = []
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        out.append({"role": role, "parts": [{"text": str(m.get("content", ""))}]})
    return out


def _call_gemini(p: dict, system_prompt: str, messages: list[dict]) -> str:
    url = GEMINI_ENDPOINT.format(model=p["model"])
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": _to_gemini_contents(messages),
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 1024,
        },
    }
    # Key as header, not query param — never lands in request.url /
    # HTTPError messages / server access logs.
    r = requests.post(url, headers={"x-goog-api-key": p["key"]}, json=body,
                      timeout=LLM_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(f"no candidates: {data}")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise ValueError("empty text")
    return text


def _call_openai(p: dict, system_prompt: str, messages: list[dict]) -> str:
    """OpenAI-compatible chat completions — covers Groq, OpenRouter, OpenAI."""
    r = requests.post(
        f"{p['base']}/chat/completions",
        headers={"Authorization": f"Bearer {p['key']}"},
        json={
            "model": p["model"],
            "messages": [{"role": "system", "content": system_prompt},
                         *messages],
            "temperature": 0.2,
            "max_tokens": 1024,
        },
        timeout=LLM_TIMEOUT,
    )
    r.raise_for_status()
    text = (r.json()["choices"][0]["message"]["content"] or "").strip()
    if not text:
        raise ValueError("empty text")
    return text


def _call_anthropic(p: dict, system_prompt: str, messages: list[dict]) -> str:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": p["key"], "anthropic-version": "2023-06-01"},
        json={"model": p["model"], "max_tokens": 1024,
              "system": system_prompt, "messages": messages},
        timeout=LLM_TIMEOUT,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "")
                   for b in r.json().get("content", [])).strip()
    if not text:
        raise ValueError("empty text")
    return text


_CALLERS = {"gemini": _call_gemini, "openai": _call_openai,
            "anthropic": _call_anthropic}


def _sarvam_tts(text: str, lang: str) -> tuple[bytes, str] | None:
    """Sarvam AI TTS (bulbul) — Indian-language specialist with first-class
    kn-IN. Free API key with starter credits, no card:
    dashboard.sarvam.ai → API Keys → SARVAM_API_KEY. Returns WAV."""
    key = os.environ.get("SARVAM_API_KEY")
    if not key:
        return None
    try:
        r = requests.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={"api-subscription-key": key},
            json={"inputs": [text[:500]],
                  "target_language_code": lang if lang.endswith("-IN")
                  else "en-IN",
                  "speaker": os.environ.get("SARVAM_TTS_SPEAKER", "anushka"),
                  "model": os.environ.get("SARVAM_TTS_MODEL", "bulbul:v2")},
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        audios = r.json().get("audios") or []
        if not audios:
            return None
        import base64
        return base64.b64decode(audios[0]), "audio/wav"
    except Exception:  # noqa: BLE001
        return None


def _google_tts(text: str, lang: str) -> bytes | None:
    """Google Cloud Text-to-Speech — the only mainstream API with real
    kn-IN voices (browsers/Windows ship none). Free tier: 1M chars/month.
    Key: console.cloud.google.com → enable 'Cloud Text-to-Speech API' →
    Credentials → API key → GOOGLE_TTS_API_KEY."""
    key = os.environ.get("GOOGLE_TTS_API_KEY")
    if not key:
        return None
    try:
        r = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            headers={"X-Goog-Api-Key": key},
            json={"input": {"text": text[:500]},
                  "voice": {"languageCode": lang},
                  "audioConfig": {"audioEncoding": "MP3"}},
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        b64 = r.json().get("audioContent")
        return __import__("base64").b64decode(b64) if b64 else None
    except Exception:  # noqa: BLE001
        return None


def _openai_tts(text: str) -> bytes | None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    try:
        r = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": os.environ.get("OPENAI_TTS_MODEL",
                                          "gpt-4o-mini-tts"),
                  "voice": os.environ.get("OPENAI_TTS_VOICE", "alloy"),
                  "input": text[:500], "response_format": "mp3"},
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        return r.content
    except Exception:  # noqa: BLE001
        return None


def tts(text: str, lang: str = "en-IN") -> tuple[bytes, str] | None:
    """Server-side TTS chain: Sarvam (Indian languages, free key, no card)
    → Google Cloud TTS (needs billing account) → OpenAI TTS (needs paid
    quota). Returns (audio bytes, mime type) or None."""
    if not text:
        return None
    out = _sarvam_tts(text, lang)
    if out:
        return out
    audio = _google_tts(text, lang) or _openai_tts(text)
    return (audio, "audio/mpeg") if audio else None


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object found in LLM output")
    return json.loads(m.group(0))


# ---------------------------------------------------------------- fallback
def _fb(is_kannada: bool, sql: str, en: str, kn: str, chart: str,
        prefix_en: str, prefix_kn: str) -> LLMResult:
    # Always populate BOTH language variants — the frontend picks based on
    # state.lang, not the query language. Previously kn fields were empty
    # when the question was in English, so the UI couldn't display Kannada
    # even when the user had flipped the language switch.
    return LLMResult(
        language="kn" if is_kannada else "en", sql=sql,
        explanation_en=en, explanation_kn=kn,
        chart_hint=chart,
        answer_prefix_en=prefix_en,
        answer_prefix_kn=prefix_kn,
        used_fallback=True,
    )


def _fallback(query: str) -> LLMResult:
    """Deterministic keyword→SQL for offline demo continuity — bilingual.

    Every query targets the real FIR tables so results stay coherent even
    when the LLM path is offline.
    """
    q = query.lower()
    is_kn = any("ಀ" <= c <= "೿" for c in query)

    # Greeting / no-content guard: don't answer "hi" with Recent FIRs.
    words = re.findall(r"[\wಀ-೿]+", q)
    greetings = {"hi", "hello", "hey", "hai", "namaste", "ok", "okay",
                 "thanks", "thank", "you", "yo", "test", "ನಮಸ್ಕಾರ", "ಹಲೋ",
                 "ಧನ್ಯವಾದ"}
    if not words or (len(words) <= 2 and all(w in greetings for w in words)):
        return LLMResult(
            language="kn" if is_kn else "en", sql="",
            explanation_en=("No crime-data question detected — ask about "
                            "districts, trends, networks, sections, or a "
                            "specific FIR."),
            explanation_kn=("ಅಪರಾಧ-ದತ್ತಾಂಶ ಪ್ರಶ್ನೆ ಪತ್ತೆಯಾಗಿಲ್ಲ — ಜಿಲ್ಲೆಗಳು, "
                            "ಟ್ರೆಂಡ್‌ಗಳು, ಜಾಲಗಳು ಅಥವಾ ನಿರ್ದಿಷ್ಟ ಎಫ್‌ಐಆರ್ ಬಗ್ಗೆ ಕೇಳಿ."),
            answer_prefix_en=("Namaste! Ask me about Karnataka crime data — "
                              "e.g. 'Which districts had the most cyber "
                              "crime?'"),
            answer_prefix_kn=("ನಮಸ್ಕಾರ! ಕರ್ನಾಟಕ ಅಪರಾಧ ದತ್ತಾಂಶದ ಬಗ್ಗೆ ಕೇಳಿ — "
                              "ಉದಾ. 'ಯಾವ ಜಿಲ್ಲೆಗಳಲ್ಲಿ ಹೆಚ್ಚು ಸೈಬರ್ ಅಪರಾಧ?'"),
            used_fallback=True,
        )

    # Location context extraction
    dist_filter = None
    dist_label_en = None
    dist_label_kn = None

    if any(k in q for k in ("bangalore", "bengaluru", "ಬೆಂಗಳೂರು")):
        dist_filter = "d.DistrictName IN ('Bengaluru Urban', 'Bengaluru Rural')"
        dist_label_en = "Bengaluru"
        dist_label_kn = "ಬೆಂಗಳೂರು"
    elif any(k in q for k in ("mysore", "mysuru", "ಮೈಸೂರು")):
        dist_filter = "d.DistrictName = 'Mysuru'"
        dist_label_en = "Mysuru"
        dist_label_kn = "ಮೈಸೂರು"
    elif any(k in q for k in ("mangalore", "mangaluru", "ಮಂಗಳೂರು")):
        dist_filter = "d.DistrictName = 'Mangaluru'"
        dist_label_en = "Mangaluru"
        dist_label_kn = "ಮಂಗಳೂರು"
    elif any(k in q for k in ("hubli", "dharwad", "hubballi", "ಹುಬ್ಬಳ್ಳಿ")):
        dist_filter = "d.DistrictName = 'Hubballi-Dharwad'"
        dist_label_en = "Hubballi-Dharwad"
        dist_label_kn = "ಹುಬ್ಬಳ್ಳಿ-ಧಾರವಾಡ"
    elif any(k in q for k in ("belagavi", "belgaum", "ಬೆಳಗಾವಿ")):
        dist_filter = "d.DistrictName = 'Belagavi'"
        dist_label_en = "Belagavi"
        dist_label_kn = "ಬೆಳಗಾವಿ"
    elif any(k in q for k in ("kalaburagi", "gulbarga", "ಕಲಬುರಗಿ")):
        dist_filter = "d.DistrictName = 'Kalaburagi'"
        dist_label_en = "Kalaburagi"
        dist_label_kn = "ಕಲಬುರಗಿ"
    elif any(k in q for k in ("ballari", "bellary", "ಬಳ್ಳಾರಿ")):
        dist_filter = "d.DistrictName = 'Ballari'"
        dist_label_en = "Ballari"
        dist_label_kn = "ಬಳ್ಳಾರಿ"
    elif any(k in q for k in ("shivamogga", "shimoga", "ಶಿವಮೊಗ್ಗ")):
        dist_filter = "d.DistrictName = 'Shivamogga'"
        dist_label_en = "Shivamogga"
        dist_label_kn = "ಶಿವಮೊಗ್ಗ"
    elif any(k in q for k in ("tumakuru", "tumkur", "ತುಮಕೂರು")):
        dist_filter = "d.DistrictName = 'Tumakuru'"
        dist_label_en = "Tumakuru"
        dist_label_kn = "ತುಮಕೂರು"
    elif any(k in q for k in ("udupi", "ಉಡುಪಿ")):
        dist_filter = "d.DistrictName = 'Udupi'"
        dist_label_en = "Udupi"
        dist_label_kn = "ಉಡುಪಿ"
    elif any(k in q for k in ("chitradurga", "ಚಿತ್ರದುರ್ಗ")):
        dist_filter = "d.DistrictName = 'Chitradurga'"
        dist_label_en = "Chitradurga"
        dist_label_kn = "ಚಿತ್ರದುರ್ಗ"
    elif any(k in q for k in ("raichur", "ರಾಯಚೂರು")):
        dist_filter = "d.DistrictName = 'Raichur'"
        dist_label_en = "Raichur"
        dist_label_kn = "ರಾಯಚೂರು"

    # Aggregation vs Raw List intent
    is_ranking = any(k in q for k in (
        "most", "highest", "top", "which area", "which station", "which police station",
        "which district", "number of", "count", "volume", "hotspot", "pradesh",
        "ಪ್ರದೇಶ", "ಅಗ್ರ", "ಹೆಚ್ಚು", "ಯಾವ"
    ))

    # Murder queries
    if any(k in q for k in ("murder", "ipc 302", "heinous", "ಕೊಲೆ")):
        where_conds = ["asa.ActID = 'IPC'", "asa.SectionID = '302'"]
        if dist_filter:
            where_conds.append(dist_filter)
        where_sql = "WHERE " + " AND ".join(where_conds)

        loc_suffix_en = f" in {dist_label_en}" if dist_label_en else ""
        loc_prefix_kn = f"{dist_label_kn}ಯಲ್ಲಿ " if dist_label_kn else ""

        if is_ranking or "area" in q or "station" in q:
            sql = (
                "SELECT u.UnitName AS area, d.DistrictName AS district, "
                "       COUNT(c.CaseMasterID) AS murder_cases "
                "FROM CaseMaster c "
                "JOIN Unit u ON u.UnitID = c.PoliceStationID "
                "JOIN District d ON d.DistrictID = u.DistrictID "
                "JOIN ActSectionAssociation asa ON asa.CaseMasterID = c.CaseMasterID "
                f"{where_sql} "
                "GROUP BY u.UnitName, d.DistrictName "
                "ORDER BY murder_cases DESC LIMIT 15"
            )
            return _fb(is_kn, sql,
                       f"Murder cases aggregated by police station area{loc_suffix_en}.",
                       f"{loc_prefix_kn}ಪೋಲಿಸ್ ಠಾಣೆ ಪ್ರದೇಶವಾರು ಕೊಲೆ ಪ್ರಕರಣಗಳ ಎಣಿಕೆ.",
                       "bar",
                       f"Top police station areas{loc_suffix_en} by murder cases:",
                       f"ಕೊಲೆ ಪ್ರಕರಣಗಳ ಸಂಖ್ಯೆಯ ಪ್ರಕಾರ ಅಗ್ರ ಪ್ರದೇಶಗಳು ({dist_label_kn or 'ಕರ್ನಾಟಕ'}):")
        else:
            sql = (
                "SELECT c.CrimeNo AS crime_no, u.UnitName AS station, d.DistrictName AS district, "
                "       csh.CrimeHeadName AS subhead, c.CrimeRegisteredDate AS date, "
                "       csm.CaseStatusName AS status "
                "FROM CaseMaster c "
                "JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = c.CrimeMinorHeadID "
                "JOIN Unit u ON u.UnitID = c.PoliceStationID "
                "JOIN District d ON d.DistrictID = u.DistrictID "
                "JOIN CaseStatusMaster csm ON csm.CaseStatusID = c.CaseStatusID "
                "JOIN ActSectionAssociation asa ON asa.CaseMasterID = c.CaseMasterID "
                f"{where_sql} "
                "ORDER BY c.CrimeRegisteredDate DESC LIMIT 25"
            )
            return _fb(is_kn, sql,
                       f"Cases invoked under IPC 302 (murder){loc_suffix_en}, most recent first.",
                       f"{loc_prefix_kn}ಐಪಿಸಿ 302 (ಕೊಲೆ) ಅಡಿಯಲ್ಲಿ ದಾಖಲಾದ ಪ್ರಕರಣಗಳು, ಇತ್ತೀಚಿನವು ಮೊದಲು.",
                       "table",
                       f"Recent murder cases{loc_suffix_en}:",
                       f"ಇತ್ತೀಚಿನ ಕೊಲೆ ಪ್ರಕರಣಗಳು ({dist_label_kn or 'ಕರ್ನಾಟಕ'}):")

    if dist_filter and is_ranking:
        sql = (
            "SELECT u.UnitName AS area, d.DistrictName AS district, "
            "       COUNT(c.CaseMasterID) AS total_cases "
            "FROM CaseMaster c "
            "JOIN Unit u ON u.UnitID = c.PoliceStationID "
            "JOIN District d ON d.DistrictID = u.DistrictID "
            f"WHERE {dist_filter} "
            "GROUP BY u.UnitName, d.DistrictName "
            "ORDER BY total_cases DESC LIMIT 15"
        )
        return _fb(is_kn, sql,
                   f"FIR volume by police station area in {dist_label_en}.",
                   f"{dist_label_kn}ಯಲ್ಲಿ ಪೊಲೀಸ್ ಠಾಣೆ ಪ್ರದೇಶವಾರು ಎಫ್‌ಐಆರ್ ಸಂಖ್ಯೆ.",
                   "bar",
                   f"Top police station areas in {dist_label_en} by crime volume:",
                   f"{dist_label_kn}ಯಲ್ಲಿ ಎಫ್‌ಐಆರ್ ಸಂಖ್ಯೆಯ ಪ್ರಕಾರ ಅಗ್ರ ಪ್ರದೇಶಗಳು:")

    if any(k in q for k in (
        "hotspot", "top district", "most crime", "highest", "which district",
        "ಹಾಟ್", "ಜಿಲ್ಲೆ",
    )):
        sql = (
            "SELECT d.DistrictName AS district, COUNT(c.CaseMasterID) AS crimes "
            "FROM CaseMaster c "
            "JOIN Unit u ON u.UnitID = c.PoliceStationID "
            "JOIN District d ON d.DistrictID = u.DistrictID "
            "GROUP BY d.DistrictName ORDER BY crimes DESC LIMIT 15"
        )
        return _fb(is_kn, sql,
                   "Districts ranked by total crime volume.",
                   "ಒಟ್ಟು ಅಪರಾಧಗಳ ಸಂಖ್ಯೆಯ ಪ್ರಕಾರ ಜಿಲ್ಲೆಗಳ ಪಟ್ಟಿ.",
                   "bar",
                   "Top districts by crime volume:",
                   "ಅಪರಾಧಗಳ ಸಂಖ್ಯೆಯ ಪ್ರಕಾರ ಅಗ್ರ ಜಿಲ್ಲೆಗಳು:")

    if any(k in q for k in (
        "chargesheet", "conviction rate", "csr", "b report", "undetected",
    )):
        sql = (
            "SELECT csm.CaseStatusName AS status, "
            "       COALESCE(cs.cstype, '-') AS final_report, "
            "       COUNT(*) AS n "
            "FROM CaseMaster c "
            "JOIN CaseStatusMaster csm ON csm.CaseStatusID = c.CaseStatusID "
            "LEFT JOIN ChargesheetDetails cs ON cs.CaseMasterID = c.CaseMasterID "
            "GROUP BY csm.CaseStatusName, cs.cstype "
            "ORDER BY n DESC LIMIT 25"
        )
        return _fb(is_kn, sql,
                   "Case status × chargesheet final-report breakdown.",
                   "ಪ್ರಕರಣ ಸ್ಥಿತಿ ಮತ್ತು ದೋಷಾರೋಪ ಪಟ್ಟಿಯ ಅಂತಿಮ ವರದಿ ವಿಭಜನೆ.",
                   "table",
                   "Status vs chargesheet outcome:",
                   "ಸ್ಥಿತಿ ಮತ್ತು ದೋಷಾರೋಪ ಪಟ್ಟಿ ಫಲಿತಾಂಶ:")

    if any(k in q for k in ("ndps", "ganja", "narcotic", "ಮಾದಕ")):
        sql = (
            "SELECT d.DistrictName AS district, "
            "       COUNT(c.CaseMasterID) AS ndps_cases "
            "FROM CaseMaster c "
            "JOIN ActSectionAssociation asa ON asa.CaseMasterID = c.CaseMasterID "
            "JOIN Unit u ON u.UnitID = c.PoliceStationID "
            "JOIN District d ON d.DistrictID = u.DistrictID "
            "WHERE asa.ActID = 'NDPS' "
            "GROUP BY d.DistrictName ORDER BY ndps_cases DESC LIMIT 10"
        )
        return _fb(is_kn, sql,
                   "NDPS cases by district.",
                   "ಜಿಲ್ಲಾವಾರು ಎನ್‌ಡಿಪಿಎಸ್ ಪ್ರಕರಣಗಳು.",
                   "bar",
                   "Narcotic cases by district:",
                   "ಜಿಲ್ಲಾವಾರು ಮಾದಕ ವಸ್ತು ಪ್ರಕರಣಗಳು:")

    # Socio-demographic insights (focus area) — aggregate-only.
    if any(k in q for k in (
        "religion", "caste", "occupation", "demographic", "socio",
        "age group", "age band", "gender", "ಧರ್ಮ", "ಜಾತಿ", "ಉದ್ಯೋಗ",
    )):
        if "religion" in q or "ಧರ್ಮ" in q:
            group, join, label, label_kn = (
                "rm.ReligionName",
                "JOIN ComplainantDetails cd ON cd.CaseMasterID = c.CaseMasterID "
                "JOIN ReligionMaster rm ON rm.ReligionID = cd.ReligionID",
                "Complainants by religion", "ಧರ್ಮದ ಪ್ರಕಾರ ದೂರುದಾರರು")
        elif "occupation" in q or "ಉದ್ಯೋಗ" in q:
            group, join, label, label_kn = (
                "om.OccupationName",
                "JOIN ComplainantDetails cd ON cd.CaseMasterID = c.CaseMasterID "
                "JOIN OccupationMaster om ON om.OccupationID = cd.OccupationID",
                "Complainants by occupation", "ಉದ್ಯೋಗದ ಪ್ರಕಾರ ದೂರುದಾರರು")
        elif "caste" in q or "ಜಾತಿ" in q:
            group, join, label, label_kn = (
                "cm.caste_master_name",
                "JOIN ComplainantDetails cd ON cd.CaseMasterID = c.CaseMasterID "
                "JOIN CasteMaster cm ON cm.caste_master_id = cd.CasteID",
                "Complainants by caste category", "ಜಾತಿ ವರ್ಗದ ಪ್ರಕಾರ ದೂರುದಾರರು")
        else:
            group, join, label, label_kn = (
                "CASE a.GenderID WHEN 1 THEN 'Male' WHEN 2 THEN 'Female' "
                "ELSE 'Other' END",
                "JOIN Accused a ON a.CaseMasterID = c.CaseMasterID",
                "Accused by gender", "ಲಿಂಗದ ಪ್ರಕಾರ ಆರೋಪಿಗಳು")
        sql = (
            f"SELECT {group} AS category, COUNT(*) AS n "
            f"FROM CaseMaster c {join} "
            f"GROUP BY category ORDER BY n DESC LIMIT 20"
        )
        return _fb(is_kn, sql,
                   f"Socio-demographic aggregate: {label}.",
                   f"ಸಾಮಾಜಿಕ-ಜನಸಂಖ್ಯಾ ಒಟ್ಟುಗೂಡಿಕೆ: {label_kn}.",
                   "bar", f"{label}:", f"{label_kn}:")

    # Behavioural profiling (focus area) — repeat offenders / recidivism.
    if any(k in q for k in (
        "repeat offender", "recidiv", "habitual", "reoffend", "most active",
        "profiling", "prolific",
    )):
        sql = (
            "WITH accused_c AS ("
            "  SELECT a.AccusedMasterID, a.CaseMasterID, a.AccusedName, "
            "         COALESCE(pa.ClusterID, -a.AccusedMasterID) AS cluster "
            "  FROM Accused a "
            "  LEFT JOIN PersonAlias pa ON pa.AccusedMasterID = a.AccusedMasterID"
            ") "
            "SELECT MAX(ac.AccusedName) AS offender, "
            "       COUNT(DISTINCT ac.CaseMasterID) AS cases, "
            "       COUNT(DISTINCT c.CrimeMajorHeadID) AS crime_types, "
            "       SUM(CASE WHEN c.GravityOffenceID=1 THEN 1 ELSE 0 END) AS heinous "
            "FROM accused_c ac "
            "JOIN CaseMaster c ON c.CaseMasterID = ac.CaseMasterID "
            "GROUP BY ac.cluster HAVING cases >= 2 "
            "ORDER BY cases DESC, heinous DESC LIMIT 25"
        )
        return _fb(is_kn, sql,
                   "Repeat offenders (>=2 FIRs) via PersonAlias clusters.",
                   "ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳು (2+ ಎಫ್‌ಐಆರ್), PersonAlias ಮೂಲಕ.",
                   "table",
                   "Repeat offenders by case count:",
                   "ಪ್ರಕರಣಗಳ ಸಂಖ್ಯೆಯ ಪ್ರಕಾರ ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳು:")

    # Temporal pattern — time-of-day distribution.
    if any(k in q for k in (
        "time of day", "hour", "what time", "night", "peak time", "when do",
    )):
        sql = (
            "SELECT strftime('%H', c.IncidentFromDate) AS hour, "
            "       COUNT(*) AS crimes "
            "FROM CaseMaster c "
            "WHERE c.IncidentFromDate IS NOT NULL "
            "GROUP BY hour ORDER BY hour LIMIT 24"
        )
        return _fb(is_kn, sql,
                   "Incidents grouped by hour of day.",
                   "ದಿನದ ಗಂಟೆಯ ಪ್ರಕಾರ ಘಟನೆಗಳ ಗುಂಪು.",
                   "bar",
                   "Crime distribution by hour of day:",
                   "ದಿನದ ಗಂಟೆಯ ಪ್ರಕಾರ ಅಪರಾಧ ಹಂಚಿಕೆ:")

    # Act/Section pattern discovery.
    if any(k in q for k in (
        "section", "act ", "under ipc", "ipc ", "which sections", "legal",
    )):
        sql = (
            "SELECT asa.ActID AS act, asa.SectionID AS section, "
            "       s.SectionDescription AS description, COUNT(*) AS cases "
            "FROM ActSectionAssociation asa "
            "JOIN CaseMaster c ON c.CaseMasterID = asa.CaseMasterID "
            "LEFT JOIN Section s ON s.ActCode = asa.ActID "
            "                   AND s.SectionCode = asa.SectionID "
            "GROUP BY asa.ActID, asa.SectionID "
            "ORDER BY cases DESC LIMIT 20"
        )
        return _fb(is_kn, sql,
                   "Most-invoked Act/Section combinations.",
                   "ಹೆಚ್ಚು ಅನ್ವಯಿಸಲಾದ ಕಾಯ್ದೆ/ಕಲಂ ಸಂಯೋಜನೆಗಳು.",
                   "bar",
                   "Most frequently applied sections:",
                   "ಹೆಚ್ಚು ಬಳಸಲಾದ ಕಾಯ್ದೆ/ಕಲಂಗಳು:")

    # Default: recent FIRs
    sql = (
        "SELECT c.CrimeNo AS crime_no, csh.CrimeHeadName AS crime_type, "
        "       d.DistrictName AS district, u.UnitName AS station, "
        "       c.CrimeRegisteredDate AS date, csm.CaseStatusName AS status "
        "FROM CaseMaster c "
        "JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = c.CrimeMinorHeadID "
        "JOIN Unit u ON u.UnitID = c.PoliceStationID "
        "JOIN District d ON d.DistrictID = u.DistrictID "
        "JOIN CaseStatusMaster csm ON csm.CaseStatusID = c.CaseStatusID "
        "ORDER BY c.CrimeRegisteredDate DESC LIMIT 25"
    )
    return _fb(is_kn, sql,
               "Most recent FIRs across all districts.",
               "ಎಲ್ಲಾ ಜಿಲ್ಲೆಗಳ ಇತ್ತೀಚಿನ ಎಫ್‌ಐಆರ್‌ಗಳು.",
               "table",
               "Recent FIRs:",
               "ಇತ್ತೀಚಿನ ಎಫ್‌ಐಆರ್‌ಗಳು:")


def clear_cooldowns() -> None:
    """Clear all provider cooldowns so fresh API requests are attempted."""
    _COOLDOWN.clear()


# ---------------------------------------------------------------- entry point
def nl_to_sql(query: str, history: list[ChatTurn] | None = None,
              capp=None) -> LLMResult:
    """NL question → validated SQL.

    Chain: QuickML → hosted providers in _providers() order → keyword
    fallback. A provider that errors goes on cooldown (long for auth
    failures, short for rate limits) so the next key/provider is tried
    immediately and quota exhaustion degrades seamlessly.
    """
    is_kn = any("\u0c80" <= c <= "\u0cff" for c in query)
    messages = _messages_from_history(query, history)

    # 1. Catalyst QuickML (LLM serving)
    try:
        data = catalyst.quickml_generate(SYSTEM_PROMPT, messages, capp=capp)
        r = _result_from_json(data, is_kn)
        r.provider = "quickml"
        return r
    except Exception:  # noqa: BLE001
        pass  # unconfigured or errored — fall through

    # 2. Hosted providers, skipping any on cooldown
    errors: list[str] = []
    now = time.time()
    for p in _providers():
        if _COOLDOWN.get(p["id"], 0) > now:
            continue
        try:
            text = _CALLERS[p["kind"]](p, SYSTEM_PROMPT, messages)
            data = _extract_json(text)
            r = _result_from_json(data, is_kn)
            r.raw = text
            r.provider = p["id"]
            return r
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p['id']}: {_sanitize_error(str(e))}")
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code == 429:          # rate limit / quota — brief cooldown
                cooldown = 120
            elif code in (401, 403):  # bad/revoked key — 5m cooldown
                cooldown = 300
            else:                     # transient / parse error
                cooldown = 30
            _COOLDOWN[p["id"]] = now + cooldown

    # 3. Fallback
    fb = _fallback(query)
    if errors:
        fb.explanation_en = (
            "All LLM providers unavailable; used keyword fallback. "
            + " | ".join(errors[:3])
        )
    return fb


def _messages_from_history(query: str,
                            history: list[ChatTurn] | None) -> list[dict]:
    msgs: list[dict] = []
    if history:
        for turn in history[-6:]:
            msgs.append({"role": turn.role, "content": turn.content})
    msgs.append({"role": "user", "content": query})
    return msgs


def _result_from_json(data: dict, is_kn: bool = False) -> LLMResult:
    lang = "kn" if is_kn else data.get("language", "en")
    return LLMResult(
        language=lang,
        sql=data.get("sql", "").strip().rstrip(";"),
        explanation_en=data.get("explanation_en", ""),
        explanation_kn=data.get("explanation_kn", ""),
        chart_hint=data.get("chart_hint", "table"),
        answer_prefix_en=data.get("answer_prefix_en", ""),
        answer_prefix_kn=data.get("answer_prefix_kn", ""),
    )


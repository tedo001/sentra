"""Which language a report is written in - from its own letters, not a setting.

The Ingest page's OCR-language box tells the OCR engine which recogniser to
load for a scanned page; it says nothing about a text file or a pasted
narrative, and a Hindi report must not be labelled "English" because the box
was left on English. This module reads the text itself:

1. **The script**, from the Unicode block most of the letters sit in -
   Devanagari, Bengali/Assamese, Gurmukhi, Gujarati, Odia, Tamil, Telugu,
   Kannada, Malayalam, Arabic (Urdu) or Latin. Field reports mix scripts
   ("11 kV", "LOTO", "PTW 4471" inside a Tamil narrative), so it is the share
   of letters that decides, not any single character.
2. **The language within a shared script**: Devanagari is Hindi or Marathi
   (or Nepali), Bengali script is Bengali or Assamese, Arabic script is Urdu
   or Arabic - told apart by letters one language uses and the other does not
   (Marathi ळ, Assamese ৰ and ৱ, Urdu ٹ ڈ ڑ ں ے) and by their commonest
   words.

No model, no network, no dependency: a few hundred characters are enough to
name the language of a field report reliably, and a report too short or too
mixed to tell is said to be so rather than guessed.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Tuple

__all__ = ["Detected", "detect_language", "SCRIPTS", "language_label"]

#: (first code point, last code point, script name)
SCRIPTS: Tuple[Tuple[int, int, str], ...] = (
    (0x0900, 0x097F, "Devanagari"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Odia"),
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0750, 0x077F, "Arabic"),
    (0xFB50, 0xFDFF, "Arabic"),
    (0xFE70, 0xFEFF, "Arabic"),
)

#: A script with one language: its name, native name and ISO 639-1 code.
SINGLE: Dict[str, Tuple[str, str, str]] = {
    "Gurmukhi": ("Punjabi", "ਪੰਜਾਬੀ", "pa"),
    "Gujarati": ("Gujarati", "ગુજરાતી", "gu"),
    "Odia": ("Odia", "ଓଡ଼ିଆ", "or"),
    "Tamil": ("Tamil", "தமிழ்", "ta"),
    "Telugu": ("Telugu", "తెలుగు", "te"),
    "Kannada": ("Kannada", "ಕನ್ನಡ", "kn"),
    "Malayalam": ("Malayalam", "മലയാളം", "ml"),
    "Latin": ("English", "English", "en"),
}

#: Languages sharing a script: marker letters and common words for each. The
#: first of each script is the one reported when nothing tells them apart.
SHARED: Dict[str, Tuple[Tuple[str, str, str, str, Tuple[str, ...]], ...]] = {
    "Devanagari": (
        ("Hindi", "हिन्दी", "hi", "",
         ("है", "हैं", "और", "था", "थी", "थे", "में", "की", "के", "का", "नहीं", "गया", "गई",
          "किया", "पर", "से", "को", "लिए", "हुआ", "कर", "रहा")),
        ("Marathi", "मराठी", "mr", "ळ",
         ("आहे", "आणि", "होते", "झाले", "केले", "नाही", "मध्ये", "आला", "आली", "करण्यासाठी",
          "च्या", "ची", "चा", "चे", "हे", "तो", "ती", "होता", "होती", "नव्हते", "असे")),
        ("Nepali", "नेपाली", "ne", "",
         ("छ", "थियो", "गरेको", "भएको", "र", "पनि", "हुन्छ", "गर्न")),
    ),
    "Bengali": (
        ("Bengali", "বাংলা", "bn", "",
         ("ছিল", "করা", "এবং", "হয়", "না", "এই", "করেছিল", "থেকে")),
        ("Assamese", "অসমীয়া", "as", "ৰৱ",
         ("আছিল", "কৰা", "হয়", "আৰু", "নাছিল", "এই", "কৰিছিল")),
    ),
    "Arabic": (
        ("Urdu", "اردو", "ur", "ٹڈڑںےۓھگچپژک",
         ("ہے", "اور", "کی", "کے", "میں", "تھا", "تھی", "نہیں", "سے", "کو")),
        ("Arabic", "العربية", "ar", "",
         ("في", "من", "على", "إلى", "كان", "هذا", "التي", "الذي")),
    ),
}


@dataclass(frozen=True)
class Detected:
    """The language of a text, and how sure the reading is."""

    name: str                 # "Hindi", "English", "Unknown"
    native: str               # "हिन्दी"
    code: str                 # ISO 639-1, "hi"
    script: str               # "Devanagari"
    share: float              # the script's share of the letters, 0-1
    sure: bool                # False when the text is too short or too mixed

    @property
    def english(self) -> bool:
        return self.code == "en"

    @property
    def label(self) -> str:
        """'Hindi / हिन्दी' - how the console names a language."""
        if self.native and self.native != self.name:
            return f"{self.name} / {self.native}"
        return self.name


UNKNOWN = Detected("Unknown", "", "", "", 0.0, False)


def _script_of(char: str) -> str:
    point = ord(char)
    if point < 0x0250:
        return "Latin"
    for first, last, name in SCRIPTS:
        if first <= point <= last:
            return name
    return "Other"


#: Word breaks: spaces, digits and punctuation, including the danda (। ॥). Not
#: \W - Indic vowel signs are not "word characters" to Python, and splitting
#: on them breaks every word into letters.
_BREAKS = re.compile(r"[\s\d.,;:!?()\[\]{}\"'`/\\|<>=+*&%#@~^\u0964\u0965\u2013\u2014-]+")


def _words(text: str) -> Counter:
    return Counter(word for word in _BREAKS.split(text) if word)


def detect_language(text: str, minimum_letters: int = 12) -> Detected:
    """Name the language ``text`` is written in.

    English is reported for Latin-script text - SENTRA's reports are English
    or an Indian language, and telling French from English is not a problem
    the console has.
    """
    letters = [char for char in str(text or "") if char.isalpha()]
    if not letters:
        return UNKNOWN
    counts = Counter(_script_of(char) for char in letters)
    total = len(letters)
    non_latin = {name: count for name, count in counts.items() if name not in ("Latin", "Other")}
    if non_latin and sum(non_latin.values()) / total >= 0.20:
        script, count = max(non_latin.items(), key=lambda item: item[1])
    else:
        script, count = "Latin", counts.get("Latin", 0)
    share = count / total
    sure = total >= minimum_letters and share >= 0.5 or (script != "Latin" and share >= 0.35)

    if script in SINGLE:
        name, native, code = SINGLE[script]
        return Detected(name, native, code, script, share, sure)
    if script in SHARED:
        words = _words(text)
        best, best_score = None, -1.0
        for name, native, code, markers, common in SHARED[script]:
            score = sum(words[word] for word in common)
            score += 3 * sum(text.count(marker) for marker in markers)
            if score > best_score:
                best, best_score = (name, native, code), score
        name, native, code = best
        # The first listed (commonest) language of the script when nothing
        # distinguishes - Hindi for Devanagari, Bengali, Urdu.
        return Detected(name, native, code, script, share, sure and best_score > 0)
    return Detected("Unknown", "", "", script, share, False)


def language_label(text: str) -> str:
    """'Hindi / हिन्दी', 'English' or 'Unknown' - for tables and logs."""
    return detect_language(text).label

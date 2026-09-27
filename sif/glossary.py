"""An English keyword gloss of a report written in an Indian language.

SENTRA's engines read English. With Ollama running, a non-English report is
translated by ``gemma2:latest`` first; without it, a Hindi report that says
the crew worked "बिना एलओटीओ" (without LOTO) on an 11 kV feeder was analysed
as written, matched nothing, and was filed as thin evidence at risk 0 - a
missed SIF precursor.

:func:`keyword_gloss` closes that gap. It looks for the safety concepts the
engines score - the high-energy sources (height, 11 kV, a suspended load, hot
work beside LPG, H2S) and the failed barriers (no LOTO, no gas test, an
expired permit, a lanyard on a handrail, nobody standing clear of the load) -
in Hindi, Marathi, Assamese, Bengali, Tamil, Telugu, Kannada and Urdu, and
writes each concept found as the English phrase the rule engine knows.

It is a **gloss, not a translation**: a list of the concepts found, in
English, for the engines. The console labels it so - "English keyword gloss,
not a translation" - keeps the original as the record, and a person reads the
original to decide. With the LLM available the real translation is used
instead.

A failed barrier is only glossed when the barrier word sits next to a
negation in the same sentence ("गैस परीक्षण नहीं किया", "LOTO பூட்டு
போடாமல்"), so a report that says the permit was valid and the gas test done
does not read as a failure.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Pattern, Sequence, Tuple

__all__ = ["keyword_gloss", "gloss_concepts", "site_in", "GLOSS_PREFIX"]

#: How a gloss begins, so the console and the audit trail can tell it apart
#: from a translation at a glance.
GLOSS_PREFIX = "Keyword gloss (not a translation):"


def normalise(text: str) -> str:
    """One spelling per word: NFC, no zero-width joiners, spaces collapsed.

    The same Bengali ড় or Devanagari क़ can be typed as one code point or as
    a letter and a nukta, and ZWNJ (ಓವರ್‌ಟೇಕ್) is optional in most keyboards.
    Text and vocabulary are both put through this before they meet.
    """
    text = unicodedata.normalize("NFC", str(text or "")).replace("\u200c", "").replace("\u200d", "")
    return re.sub(r"\s+", " ", text)


#: Not inside another word: "লটো" (LOTO) is not the "-লটো" of "কেবলটো" (the cable).
_WORD_START = r"(?<![\w\u0900-\u0DFF\u0600-\u06FF\u0750-\u077F])"


def _any(*words: str, start: bool = True) -> str:
    """Any of the words, each at the start of a word unless ``start`` is False."""
    lead = _WORD_START if start else ""
    return "(?:" + "|".join(lead + re.escape(normalise(word)) if not word.startswith("re:")
                           else word[3:] for word in words) + ")"


#: Negation and absence, in every language the gloss reads.
NEGATION = _any(
    # Hindi, Marathi
    "बिना", "नहीं", "नही", "गायब", "नाही", "नव्हत", "विना", "शिवाय", "नसता", "न करता", "न लावता", "न घेता",
    "अनुपस्थित",
    # Assamese, Bengali
    "নকৰাকৈ", "নোহোৱাকৈ", "নাছিল", "নাই", "বিনা", "অবিহনে", "ছাড়া", "নেই", "হয়নি",
    "করেনি", "নহ'ল", "নহল", "অনুপস্থিত", "নোহোৱা",
    # Tamil
    "இல்லாமல்", "இல்லாம", "இல்லை", "இன்றி", "வில்லை", "டாமல்", "யாமல்",
    # Telugu
    "లేకుండా", "లేదు", "కుండా",
    # Kannada
    "ಇಲ್ಲದೆ", "ಇಲ್ಲ", "ಇರಲಿಲ್ಲ", "ಲಿಲ್ಲ", "ಮಾಡದೆ",
    # Urdu
    "بغیر", "نہیں", "بنا",
    # Negation is often a verb ending ("-வில்லை", "-కుండా"), so not anchored.
    start=False,
)

#: "Without", written before the noun: बिना गैस परीक्षण, বিনা অনুমতিত, بغیر پرمٹ.
#: Every other negation follows the verb, after the noun it negates - these
#: languages put the verb last - so only these are read backwards.
PRE_NEGATION = _any("बिना", "विना", "বিনা", "بغیر", "بنا", "re:\\bwithout\\b", "re:\\bno\\b")

#: A sentence's end - a negation is never read across one.
_SAME_SENTENCE = r"[^।॥.۔!?;]"


def _without(nouns: str, before: int = 24, after: int = 40) -> str:
    """The noun negated in either word order: 'बिना गैस परीक्षण', 'गैस परीक्षण नहीं'."""
    return (f"{PRE_NEGATION}{_SAME_SENTENCE}{{0,{before}}}{nouns}"
            f"|{nouns}{_SAME_SENTENCE}{{0,{after}}}{NEGATION}")


def _near(first: str, second: str, gap: int = 60) -> str:
    """Both, in either order, within one sentence."""
    return f"{first}{_SAME_SENTENCE}{{0,{gap}}}{second}|{second}{_SAME_SENTENCE}{{0,{gap}}}{first}"


# -- vocabulary: loanwords and native terms as field reports write them ------------

LOTO = _any("LOTO", "लोटो", "एलओटीओ", "लॉकआउट", "लॉक आउट", "आइसोलेशन", "आयसोलेशन",
            "অলঅ'টিঅ'", "লটো", "লক আউট", "লক-আউট", "আইছোলেচন", "আইসোলেশন",
            "லோட்டோ", "பூட்டு", "தனிமைப்படுத்த", "లోటో", "లాక్ అవుట్", "ఐసోలేషన్",
            "ಲೋಟೋ", "ಲಾಕ್ ಔಟ್", "ಐಸೋಲೇಶನ್", "لاک آؤٹ", "آئسولیشن")
EARTHING = _any("अर्थिंग", "आर्थिंग", "আৰ্থিং", "আর্থিং", "এর্থিং", "எர்த்",
                "ఎర్తింగ్", "ఎర్త్", "ಅರ್ಥಿಂಗ್", "ಅರ್ತಿಂಗ್", "ارتھنگ", "ارتھ")
ISOLATION_CERT = _any("आइसोलेशन प्रमाणपत्र", "पृथक्करण प्रमाणपत्र", "আইছোলেচন প্ৰমাণপত্ৰ",
                      "தனிமைப்படுத்தல் சான்றிதழ்", "ఐసోలేషన్ సర్టిఫికేట్")
GAS_TEST = _any("गैस परीक्षण", "वायू चाचणी", "वायु परीक्षण", "गैस जांच", "गैस जाँच", "गैस टेस्ट", "गॅस चाचणी", "गॅस तपासणी",
                "গেছ পৰীক্ষা", "গেছ পৰীক্ষণ", "গ্যাস পরীক্ষা", "গ্যাস টেস্ট",
                "வாயு பரிசோதனை", "வாயு சோதனை", "கேஸ் டெஸ்ட்", "గ్యాస్ పరీక్ష",
                "ಅನಿಲ ಪರೀಕ್ಷೆ", "ಗ್ಯಾಸ್ ಪರೀಕ್ಷೆ", "گیس ٹیسٹ", "گیس کی جانچ")
VENTILATION = _any("वेंटिलेशन", "वायुवीजन", "वायुविजन", "হাৱা চলাচল", "বায়ু চলাচল",
                   "ভেণ্টিলেচন", "ভেন্টিলেশন", "காற்றோட்டம்", "వెంటిలేషన్", "గాలి ప్రసరణ",
                   "ಗಾಳಿ ಸಂಚಾರ", "ವೆಂಟಿಲೇಶನ್", "وینٹیلیشن")
PERMIT = _any("परमिट", "अनुमति पत्र", "कार्य अनुमति", "परवाना", "परवानगी", "पाळी परवाना",
              "পাৰমিট", "পারমিট", "অনুমতি পত্ৰ", "অনুমতিপত্র", "কাৰ্য অনুমতি",
              "அனுமதிச் சீட்டு", "அனுமதி", "பெர்மிட்", "అనుమతి", "పర్మిట్", "ಅನುಮತಿ",
              "ಪರವಾನಗಿ", "ಪರ್ಮಿಟ್", "پرمٹ", "اجازت نامہ")
EXPIRED = _any("समाप्त", "खत्म", "ख़त्म", "कालबाह्य", "मुदत संपली", "संपला", "संपली", "संपले", "ম্যাদ উকলি", "ম্যাদ পাৰ",
               "মেয়াদ উত্তীর্ণ", "মেয়াদোত্তীর্ণ", "মেয়াদ শেষ", "காலாவதி", "గడువు ముగి",
               "ಅವಧಿ ಮುಗಿ", "ಅವಧಿ ಮೀರಿ", "میعاد ختم", "ختم ہو")
HANDRAIL = _any("हैंडरेल", "रेलिंग", "रेलिंगला", "হেণ্ডৰেইল", "হ্যান্ডরেল", "ৰেলিং", "রেলিং",
                "கைப்பிடி", "ரெயிலிங்", "హ్యాండ్‌రైల్", "రెయిలింగ్", "ಕೈಪಿಡಿ", "ರೇಲಿಂಗ್",
                "ہینڈ ریل", "ریلنگ")
HARNESS = _any("हार्नेस", "लैनयार्ड", "लॅनयार्ड", "হাৰনেছ", "হার্নেস", "লেনিয়াৰ্ড", "ল্যানইয়ার্ড",
               "ஹார்னஸ்", "லேன்யார்டு", "హార్నెస్", "లాన్యార్డ్", "ಹಾರ್ನೆಸ್", "ಲ್ಯಾನ್ಯಾರ್ಡ್",
               "ہارنس", "لینیارڈ")
ANCHOR = _any("एंकर", "अँकर", "এংকৰ", "অ্যাঙ্কর", "ஆங்கர்", "యాంకర్", "ಆಂಕರ್", "اینکر")
FIRE_WATCH = _any("फायर वॉच", "फायर वॉचर", "अग्नि प्रहरी", "अग्नि रक्षक", "अग्नी रक्षक",
                  "ফায়াৰ ৱাচ", "অগ্নি প্ৰহৰী", "ফায়ার ওয়াচ", "অগ্নি প্রহরী",
                  "தீ கண்காணிப்பாளர்", "தீ காவலர்", "ఫైర్ వాచ్", "అగ్ని కాపలాదారు",
                  "ಅಗ್ನಿ ಕಾವಲುಗಾರ", "ಫೈರ್ ವಾಚ್", "فائر واچ")
BARRICADE = _any("बैरिकेड", "बॅरिकेड", "घेराबंदी", "प्रतिबंधित क्षेत्र", "বেৰিকেড", "ব্যারিকেড",
                 "নিষিদ্ধ এলেকা", "নিষিদ্ধ এলাকা", "தடுப்பு", "தடை மண்டலம்", "బారికేడ్",
                 "నిషేధిత ప్రాంతం", "ನಿಷೇಧಿತ ಪ್ರದೇಶ", "ಬ್ಯಾರಿಕೇಡ್", "بیریکیڈ")
LIFT_PLAN = _any("लिफ्ट प्लान", "लिफ्ट योजना", "উত্তোলন পৰিকল্পনা", "লিফ্ট প্লেন", "লিফট প্ল্যান",
                 "தூக்கும் திட்டம்", "லிஃப்ட் திட்டம்", "లిఫ్ట్ ప్లాన్", "ಲಿಫ್ಟ್ ಯೋಜನೆ")
RESCUE_PLAN = _any("बचाव योजना", "सुटका योजना", "बचाव योजनेवर", "উদ্ধাৰ পৰিকল্পনা",
                   "উদ্ধার পরিকল্পনা", "மீட்புத் திட்டம்", "மீட்பு திட்டம்", "రెస్క్యూ ప్లాన్",
                   "ರಕ್ಷಣಾ ಯೋಜನೆ")
UNDER = _any("नीचे", "खाली", "তলত", "তলেদি", "নিচে", "নীচে", "கீழே", "அடியில்", "కింద",
             "ಕೆಳಗೆ", "نیچے")
LOAD = _any("भार", "लोड", "ओझे", "मॉड्यूल", "ওজন", "বোজা", "লোড", "ভার", "মডিউল", "சுமை",
            "லோடு", "மாட்யூல்", "లోడ్", "బరువు", "మాడ్యూల్", "ಭಾರ", "ಲೋಡ್", "ಮಾಡ್ಯೂಲ್", "بوجھ",
            "لوڈ")
HOLE_WATCH = _any("होल वॉच", "होल वाच", "হোল ৱাচ", "হোল ওয়াচ", "ஹோல் வாட்ச்", "హోల్ వాచ్",
                  "ಹೋಲ್ ವಾಚ್", "ہول واچ", "re:\\bhole watch\\b")
BANKSMAN = _any("बैंकसमैन", "बँकसमन", "বেংকছমেন", "ব্যাংকসম্যান", "பேங்க்ஸ்மேன்", "బ్యాంక్స్‌మన్",
                "ಬ್ಯಾಂಕ್ಸ್‌ಮನ್", "بینکس مین", "re:\\bbanks?man\\b")
ANOTHER = _any("दूसरे", "दूसरी", "दुसऱ्या", "অন্য", "আন এটা", "আন", "வேறு", "వేరే", "ಬೇರೆ",
               "دوسرے", "دوسری")
HELMET = _any("हेलमेट", "हेल्मेट", "হেলমেট", "ஹெல்மெட்", "హెల్మెట్", "ಹೆಲ್ಮೆಟ್", "ہیلمٹ")


@dataclass(frozen=True)
class Concept:
    english: str
    pattern: Pattern[str]


def _concept(english: str, *patterns: str) -> Concept:
    return Concept(english, re.compile("|".join(f"(?:{p})" for p in patterns)))


#: What the gloss looks for, in the order it writes them.
CONCEPTS: Tuple[Concept, ...] = (
    # -- high-energy sources and activities --------------------------------------------
    _concept("working at height",
             _any("ऊँचाई", "ऊंचाई", "उंचीवर", "उंचावर", "उंचीवरील", "ওখত", "ওখ ঠাইত",
                  "উচ্চতাত", "উঁচুতে", "উচ্চতায়", "உயரத்தில்", "ఎత్తులో", "ಎತ್ತರದಲ್ಲಿ",
                  "اونچائی")),
    _concept("scaffold platform",
             _any("मचान", "मचाण", "ভাৰা", "মাচা", "স্কেফল্ড", "ভারা", "சாரம்",
                  "పరంజా", "ಅಟ್ಟಣಿಗೆ", "ಸ್ಕ್ಯಾಫೋಲ್ಡ್", "سہاروں", "اسکیفولڈ")),
    _concept("derrick monkey board",
             _any("डेरिक", "मंकी बोर्ड", "ডেৰিক", "ডেরিক", "டெரிக்", "డెరిక్", "ಡೆರಿಕ್")),
    _concept("high voltage feeder cable and breaker",
             _any("केवी", "के.वी.", "किलोवोल्ट", "কেভি", "কে.ভি.", "কিলো ভল্ট", "কিলোভল্ট",
                  "கிலோ வோல்ட்", "கே.வி", "కేవీ", "కిలో వోల్ట్", "ಕೆವಿ", "ಕಿಲೋ ವೋಲ್ಟ್",
                  "کے وی", "کلو وولٹ", "re:\\b(?:11|33|66)\\s?kV\\b")),
    _concept("feeder cable",
             _any("फीडर", "ফিডাৰ", "ফিডার", "ஃபீடர்", "ఫీడర్", "ಫೀಡರ್", "فیڈر")),
    _concept("breaker left closed",
             _any("ब्रेकर रैक आउट नहीं", "ब्रेकर चालू", "ব্ৰেকাৰ অন", "ব্রেকার চালু",
                  "பிரேக்கர் ராக் அவுட் செய்யப்படவில்லை", "బ్రేకర్ ఆన్", "ಬ್ರೇಕರ್ ಆನ್")),
    _concept("confined space tank entry",
             _any("सीमित स्थान", "बंदिस्त जागा", "टैंक के अंदर", "टाकीत", "टाकीमध्ये",
                  "আবদ্ধ স্থান", "বদ্ধ স্থান", "টেংকীৰ ভিতৰত", "ট্যাংকের ভেতরে",
                  "தொட்டிக்குள்", "அடைப்பு இடம்", "ట్యాంక్ లోపల", "పరిమిత స్థలం",
                  "ಟ್ಯಾಂಕ್ ಒಳಗೆ", "ಸೀಮಿತ ಸ್ಥಳ", "ٹینک کے اندر")),
    _concept("H2S toxic gas",
             _any("H2S", "एच2एस", "एचटूएस", "हाइड्रोजन सल्फाइड", "হাইড্ৰজেন ছালফাইড",
                  "হাইড্রোজেন সালফাইড", "ஹைட்ரஜன் சல்பைடு", "హైడ్రోజన్ సల్ఫైడ్",
                  "ಹೈಡ್ರೋಜನ್ ಸಲ್ಫೈಡ್")),
    _concept("crane lifting",
             _any("क्रेन", "ক্ৰেন", "ক্রেন", "கிரேன்", "క్రేన్", "ಕ್ರೇನ್", "کرین")),
    _concept("hot work grinding sparks",
             _any("वेल्डिंग", "ग्राइंडर", "ग्राइंडिंग", "ग्राइंडरने", "ৱেল্ডিং", "গ্ৰাইণ্ডাৰ",
                  "ওয়েল্ডিং", "গ্রাইন্ডার", "வெல்டிங்", "கிரைண்டர்", "வெல்டர்",
                  "వెల్డింగ్", "గ్రైండర్", "ವೆಲ್ಡಿಂಗ್", "ಗ್ರೈಂಡರ್", "ویلڈنگ", "گرائنڈر")),
    _concept("flammable gas cylinder",
             _any("एलपीजी", "सिलेंडर", "सिलिंडर", "এলপিজি", "চিলিণ্ডাৰ", "সিলিন্ডার", "எல்பிஜி",
                  "சிலிண்டர்", "ఎల్పీజీ", "సిలిండర్", "ಎಲ್‌ಪಿಜಿ", "ಸಿಲಿಂಡರ್", "ایل پی جی",
                  "سلنڈر", "re:\\bLPG\\b")),
    _concept("gas leak",
             _any("गैस रिसाव", "गॅस गळती", "গেছ লিক", "গেছ নিৰ্গমন", "গ্যাস লিক", "গ্যাস ফুটো",
                  "வாயு கசிவு", "గ్యాస్ లీక్", "ಅನಿಲ ಸೋರಿಕೆ", "گیس کا اخراج")),
    _concept("pressurised line",
             _any("दबाव में", "दाबाखाली", "হেঁচাত", "চাপযুক্ত", "அழுத்தத்தில்", "ఒత్తిడిలో",
                  "ಒತ್ತಡದಲ್ಲಿ", "دباؤ میں")),
    _concept("tanker vehicle",
             _any("टैंकर", "ট্যাংকাৰ", "টেংকাৰ", "ট্যাংকার", "டேங்கர்", "ట్యాంకర్", "ಟ್ಯಾಂಕರ್",
                  "ٹینکر")),
    _concept("driver",
             _any("ड्राइवर", "चालक", "ড্ৰাইভাৰ", "চালক", "ড্রাইভার", "ஓட்டுநர்", "డ్రైవర్",
                  "ಚಾಲಕ", "ڈرائیور")),
    # -- failed barriers ------------------------------------------------------------------
    _concept("without LOTO, not isolated", _without(LOTO)),
    _concept("no earthing, not earthed", _without(EARTHING)),
    _concept("no isolation certificate", _without(ISOLATION_CERT)),
    _concept("no gas test", _without(GAS_TEST)),
    _concept("without ventilation", _without(VENTILATION)),
    _concept("permit expired", _near(PERMIT, EXPIRED)),
    _concept("without a permit", _without(PERMIT, after=24)),
    _concept("lanyard clipped to the handrail instead of the anchor point",
             _near(HARNESS, HANDRAIL, 80), _near(ANCHOR, HANDRAIL, 40)),
    _concept("without harness", _without(HARNESS, after=24)),
    _concept("no fire watch", _without(FIRE_WATCH)),
    _concept("no barricading, no exclusion zone", _without(BARRICADE)),
    _concept("personnel stood under the suspended load", _near(UNDER, LOAD, 110)),
    _concept("no lift plan", _without(LIFT_PLAN)),
    _concept("no rescue plan", _without(RESCUE_PLAN)),
    _concept("scaffold tag expired",
             _near(_any("मचान", "मचाण", "ভাৰা", "ভারা", "স্কেফল্ড", "சாரம்", "పరంజా", "ಅಟ್ಟಣಿಗೆ"),
                   EXPIRED, 60)),
    _concept("no hole watch", _without(HOLE_WATCH)),
    _concept("banksman attending another lift", _near(BANKSMAN, ANOTHER, 30)),
    _concept("without hot work permit",
             _near(_any("ಬಿಸಿ ಕೆಲಸ", "हॉट वर्क", "गरम काम", "হট ৱৰ্ক", "হট ওয়ার্ক",
                        "சூடான வேலை", "హాట్ వర్క్", "ہاٹ ورک"),
                   f"{PERMIT}{_SAME_SENTENCE}{{0,20}}{ANOTHER}", 20)),
    _concept("without helmet", _without(HELMET, after=24)),
    _concept("overtook in fog",
             _near(_any("ओवरटेक", "ওভাৰটেক", "ওভারটেক", "முந்தி", "ఓవర్‌టేక్", "ಓವರ್‌ಟೇಕ್",
                        "اوور ٹیک"),
                   _any("कोहरे", "धुंध", "धुके", "কুঁৱলী", "কুয়াশা", "மூடுபனி", "పొగమంచు",
                        "ಮಂಜ", "دھند"), 80)),
    _concept("driver fatigued after eleven hours of driving",
             _any("re:(?:1[0-9]|ग्यारह|बारह|अकरा|बारा|এঘাৰ|বাৰ|এগারো|বারো|பதினொரு|పదకొండు|"
                  "ಹನ್ನೊಂದು|گیارہ|بارہ)\\s*(?:घंटे|तास|ঘণ্টা|மணி|గంట|ಗಂಟೆ|گھنٹے)")),
)

#: Heights and voltages carry their numbers across: "18 m", "11 kV".
_METRES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:मीटर|মিটাৰ|মিটার|மீட்டர்|మీటర్|ಮೀಟರ್|میٹر)")
_KV = re.compile(r"(\d+)\s*(?:केवी|के\.वी\.|কেভি|কে\.ভি\.|কিলো ভল্ট|கிலோ வோல்ட்|కేవీ|ಕೆವಿ|کے وی)")
_BAR = re.compile(r"(\d{2,})\s*(?:बार|বাৰ|বার|பார்|బార్|ಬಾರ್|بار)")


def gloss_concepts(text: str) -> List[str]:
    """The English phrases for the safety concepts found in ``text``, in order."""
    flat = normalise(text)
    found: List[str] = []
    for concept in CONCEPTS:
        if concept.pattern.search(flat):
            found.append(concept.english)
    for pattern, unit in ((_METRES, "m"), (_KV, "kV"), (_BAR, "bar")):
        for match in pattern.finditer(flat):
            # Indian digits (१८, ১১, ௧௧) become 18 and 11 for the engines.
            number = match.group(1)
            try:
                number = str(float(number)).rstrip("0").rstrip(".") if "." in number \
                    else str(int(number))
            except ValueError:
                pass
            phrase = f"{number} {unit}"
            if phrase not in found:
                found.append(phrase)
    return found


def keyword_gloss(text: str, concepts: Sequence[str] = ()) -> str:
    """'Keyword gloss (not a translation): working at height. no rescue plan.'

    Empty when nothing the engines score was found - an empty gloss is not
    evidence of anything, and the report is then analysed as written.
    """
    found = list(concepts) or gloss_concepts(text)
    if not found:
        return ""
    return GLOSS_PREFIX + " " + ". ".join(found) + "."


#: Oil India's sites as reports in Indian scripts write them, and the English
#: name the gazetteer and the risk map know them by.
SITES: Tuple[Tuple[str, str], ...] = (
    ("Duliajan", _any("दुलियाजान", "दुलियाजन", "দুলীয়াজান", "দুলিয়াজান", "துலியாஜான்",
                      "దులియాజాన్", "దులియాజన్", "ದುಲಿಯಾಜನ್", "ದುಲಿಯಾಜಾನ್", "دولیاجان")),
    ("Naharkatiya", _any("नहरकटिया", "नाहरकटिया", "नहरकटिया", "নাহৰকটীয়া", "নাহারকাটিয়া",
                         "நஹர்கட்டியா", "నహర్‌కటియా", "నహర్కటియా", "ನಹರ್‌ಕಟಿಯಾ", "نہرکٹیا")),
    ("Moran", _any("मोरान", "মৰাণ", "মরান", "மோரான்", "మోరాన్", "ಮೋರಾನ್", "مورن", "موران")),
    ("Digboi", _any("डिगबोई", "ডিগবৈ", "டிக்பாய்", "డిగ్బోయ్", "ಡಿಗ್ಬೋಯ್", "ڈگبوئی")),
    ("Tengakhat", _any("टेंगाखाट", "টেঙাখাট", "டெங்காகாட்")),
    ("Lakwa", _any("लकवा", "লাকুৱা", "লাকোয়া")),
    ("Hapjan", _any("हापजान", "হাপজান")),
    ("Sivasagar", _any("शिवसागर", "শিৱসাগৰ", "শিবসাগর")),
    ("Tinsukia", _any("तिनसुकिया", "তিনিচুকীয়া", "তিনসুকিয়া")),
    ("Dibrugarh", _any("डिब्रूगढ़", "डिब्रुगढ़", "ডিব্ৰুগড়", "ডিব্রুগড়")),
)
_RIG = re.compile(r"(?:रिग|রিগ|ৰিগ|ரிக்|రిగ్|ರಿಗ್|رگ|\bRig)\s*[-‐–]?\s*(\d+)")
_INSTALLATION = re.compile(r"\b(OCS|GCS|GGS|CTF|FCS)\s*[-‐–]?\s*(\d+)\b")


def site_in(text: str) -> str:
    """'Naharkatiya Rig-12' from 'नहरकटिया रिग-12' - the site a report names, in English."""
    flat = normalise(text)
    for english, pattern in SITES:
        if re.search(pattern, flat):
            parts = [english]
            rig = _RIG.search(flat)
            if rig:
                parts.append(f"Rig-{int(rig.group(1))}")
            installation = _INSTALLATION.search(flat)
            if installation:
                parts.append(f"{installation.group(1)}-{installation.group(2)}")
            return " ".join(parts)
    return ""

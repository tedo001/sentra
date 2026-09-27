"""Reports in Indian languages: which language, where one report ends, and
what the engines read when no LLM translates.

Run:  SIF_ENCODER=hashing python -m unittest test_languages -v

A Hindi report used to be labelled "English → English" because its label came
from the OCR-language box, and a report form was cut into three "reports" on
its blank lines. Without Ollama, every non-English precursor scored 0.
"""

from __future__ import annotations

import glob
import os
import unittest

from sif.glossary import GLOSS_PREFIX, gloss_concepts, keyword_gloss, site_in
from sif.langdetect import detect_language
from sif.segment import is_follow_on, is_heading, split_reports

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples")
LANGUAGES = os.path.join(SAMPLES, "languages")
REPORTS = os.path.join(SAMPLES, "reports")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestLanguageDetection(unittest.TestCase):

    def test_every_language_sample_is_named_from_its_own_text(self) -> None:
        expected = {"hindi": "Hindi", "marathi": "Marathi", "tamil": "Tamil",
                    "telugu": "Telugu", "kannada": "Kannada", "urdu": "Urdu"}
        for stem, name in expected.items():
            with self.subTest(stem):
                detected = detect_language(_read(os.path.join(LANGUAGES, f"{stem}_report.txt")))
                self.assertEqual(detected.name, name)
                self.assertTrue(detected.sure)
                self.assertFalse(detected.english)

    def test_hindi_is_not_marathi_or_nepali(self) -> None:
        self.assertEqual(detect_language("दूसरा हुक गायब था और बचाव योजना पर चर्चा नहीं हुई थी।").name,
                         "Hindi")
        self.assertEqual(detect_language("मचाणाची तपासणी चिठ्ठी कालबाह्य झाली होती आणि काम सुरू होते.").name,
                         "Marathi")

    def test_a_letterhead_with_no_common_words_is_hindi_not_marathi(self) -> None:
        """Nothing tells Devanagari languages apart here: the commoner is reported."""
        self.assertEqual(detect_language("ऑयल इंडिया लिमिटेड - असुरक्षित कार्य / स्थिति रिपोर्ट").name,
                         "Hindi")

    def test_assamese_and_bengali_are_told_apart(self) -> None:
        self.assertEqual(detect_language("কেবলটো আৰ্থিং নকৰাকৈ এৰি থোৱা হৈছিল আৰু কাম আৰম্ভ কৰিছিল।").name,
                         "Assamese")
        self.assertEqual(detect_language("দুজন শ্রমিক ঝুলন্ত লোডের নিচে কাজ করছিলেন এবং এলাকা চিহ্নিত করা হয়নি।").name,
                         "Bengali")

    def test_english_with_site_codes_is_english(self) -> None:
        detected = detect_language("Harness not clipped at 18 m on the derrick, Rig NHK-12.")
        self.assertTrue(detected.english)
        self.assertEqual(detected.label, "English")

    def test_a_tamil_report_full_of_english_codes_is_still_tamil(self) -> None:
        self.assertEqual(detect_language("மின் தொழிலாளி LOTO பூட்டு போடாமல் 11 kV PTW 4471 கேபிள் "
                                         "இணைப்புப் பணியைத் தொடங்கினார்").name, "Tamil")

    def test_the_label_carries_the_native_name(self) -> None:
        self.assertEqual(detect_language("यह रिपोर्ट हिंदी में है और काम रोका गया था").label,
                         "Hindi / हिन्दी")

    def test_nothing_to_read_is_unknown(self) -> None:
        self.assertEqual(detect_language("  12-09-2026  ").name, "Unknown")


class TestReportSplitting(unittest.TestCase):

    def test_a_report_form_is_one_report_not_three(self) -> None:
        for path in sorted(glob.glob(os.path.join(LANGUAGES, "*_report.txt"))):
            with self.subTest(os.path.basename(path)):
                reports = split_reports(_read(path))
                self.assertEqual(len(reports), 1)
                self.assertIn("UAUC/", reports[0], "the letterhead stays with its report")

    def test_a_shift_log_is_one_report_per_entry_without_its_title(self) -> None:
        reports = split_reports(_read(os.path.join(SAMPLES, "shift_log.txt")))
        self.assertEqual(len(reports), 5)
        self.assertTrue(all(report[:4].isdigit() for report in reports))

    def test_labelled_separators_divide_and_drop_the_preamble(self) -> None:
        reports = split_reports(_read(os.path.join(SAMPLES, "multilingual_report.txt")))
        self.assertEqual([detect_language(report).name for report in reports],
                         ["Hindi", "Marathi", "Tamil", "Telugu", "Kannada"])
        self.assertFalse(any("Use this file" in report for report in reports))

    def test_separate_paragraphs_stay_separate_reports(self) -> None:
        self.assertEqual(split_reports("No harness worn on the scaffold at 6 m.\n\n"
                                       "Breaker left closed during maintenance of the pump."),
                         ["No harness worn on the scaffold at 6 m.",
                          "Breaker left closed during maintenance of the pump."])

    def test_an_immediate_action_paragraph_joins_its_report(self) -> None:
        reports = split_reports("Crew entered the tank with no gas test.\n\n"
                                "Immediate action: crew withdrawn, permit cancelled.")
        self.assertEqual(len(reports), 1)
        self.assertTrue(is_follow_on("तत्काल कार्रवाई: काम रोका गया।"))
        self.assertFalse(is_follow_on("Report 2: second incident at the manifold."))

    def test_headings_are_short_and_not_sentences(self) -> None:
        self.assertTrue(is_heading("OIL INDIA LIMITED - DULIAJAN FIELD\nNIGHT SHIFT LOG"))
        self.assertFalse(is_heading("The crew entered the tank. Nobody tested the air."))

    def test_a_short_note_is_still_a_report(self) -> None:
        self.assertEqual(split_reports("Scaffold tag expired at OCS-4 platform"),
                         ["Scaffold tag expired at OCS-4 platform"])
        self.assertEqual(split_reports("   "), [])


class TestReportDate(unittest.TestCase):

    def test_the_date_on_the_form_is_read_in_any_language(self) -> None:
        from sif.segment import report_date

        self.assertEqual(report_date("स्थल: मोरान    दिनांक: 18-09-2026"), "2026-09-18")
        self.assertEqual(report_date("তাৰিখ: ১৬-০৯-২০২৬"), "2026-09-16")
        self.assertEqual(report_date("நாள்: 22-09-2026"), "2026-09-22")
        self.assertEqual(report_date("Date: 2026-09-14"), "2026-09-14")

    def test_no_label_an_impossible_day_or_the_future_is_no_date(self) -> None:
        from sif.segment import report_date

        self.assertEqual(report_date("found on 12-09-2026 at the pad"), "")
        self.assertEqual(report_date("Date: 31-02-2026"), "")
        self.assertEqual(report_date("Date: 01-01-2099"), "")


class TestKeywordGloss(unittest.TestCase):

    def test_each_language_sample_is_glossed_into_its_precursor(self) -> None:
        expected = {
            "hindi": ("working at height", "lanyard clipped to the handrail"),
            "marathi": ("H2S toxic gas", "no gas test", "permit expired"),
            "tamil": ("without LOTO", "no earthing", "11 kV"),
            "telugu": ("crane lifting", "personnel stood under the suspended load"),
            "kannada": ("hot work grinding sparks", "no fire watch"),
            "urdu": ("overtook in fog", "driver fatigued"),
        }
        for stem, phrases in expected.items():
            with self.subTest(stem):
                gloss = keyword_gloss(_read(os.path.join(LANGUAGES, f"{stem}_report.txt")))
                self.assertTrue(gloss.startswith(GLOSS_PREFIX))
                for phrase in phrases:
                    self.assertIn(phrase, gloss)

    def test_a_barrier_in_place_is_not_glossed_as_failed(self) -> None:
        concepts = gloss_concepts("वैध हॉट वर्क परवान्यासह वेल्डिंग काम झाले. गॅस चाचणी केली होती, "
                                  "अग्निशामक आणि फायर वॉचर उपस्थित होते.")
        self.assertIn("hot work grinding sparks", concepts)
        self.assertNotIn("no gas test", concepts)
        self.assertNotIn("no fire watch", concepts)

    def test_a_word_inside_another_word_is_not_matched(self) -> None:
        """'লটো' is LOTO; the '-লটো' of 'কেবলটো' (the cable) is not."""
        self.assertNotIn("without LOTO, not isolated",
                         gloss_concepts("ফিডাৰ কেবলটো আৰ্থিং নকৰাকৈ এৰি থোৱা হৈছিল।"))

    def test_negation_does_not_reach_back_across_a_conjunction(self) -> None:
        """Kannada: 'no fire watch, and the gas test was six hours old'."""
        concepts = gloss_concepts("ಅಗ್ನಿ ಕಾವಲುಗಾರ ಇರಲಿಲ್ಲ ಮತ್ತು ಅನಿಲ ಪರೀಕ್ಷೆ ಆರು ಗಂಟೆಗಳ ಹಿಂದಿನದಾಗಿತ್ತು.")
        self.assertIn("no fire watch", concepts)
        self.assertNotIn("no gas test", concepts)

    def test_indian_digits_and_spellings_are_normalised(self) -> None:
        self.assertIn("11 kV", gloss_concepts("১১ কেভি ফিডাৰ"))
        self.assertIn("9 m", gloss_concepts("सुमारे ९ मीटर उंचीवर"))
        joined = gloss_concepts("ಚಾಲಕ ದಟ್ಟ ಮಂಜಿನಲ್ಲಿ ಓವರ್‌ಟೇಕ್ ಮಾಡಿದರು")
        plain = gloss_concepts("ಚಾಲಕ ದಟ್ಟ ಮಂಜಿನಲ್ಲಿ ಓವರ್ಟೇಕ್ ಮಾಡಿದರು")
        self.assertEqual(joined, plain)
        self.assertIn("overtook in fog", plain)

    def test_nothing_the_engines_score_gives_no_gloss(self) -> None:
        self.assertEqual(keyword_gloss("কেণ্টিনৰ ওচৰৰ খোজকঢ়া পথত বৰষুণৰ পানী জমা হৈছিল।"), "")

    def test_sites_written_in_indian_scripts_are_named_in_english(self) -> None:
        self.assertEqual(site_in("स्थल: नहरकटिया रिग-12"), "Naharkatiya Rig-12")
        self.assertEqual(site_in("நிலையம்: துலியாஜான் OCS-4"), "Duliajan OCS-4")
        self.assertEqual(site_in("মরান গ্যাস কম্প্রেসর স্টেশন"), "Moran")
        self.assertEqual(site_in("no site here"), "")

    def test_without_translation_the_samples_are_flagged(self) -> None:
        from sif.encoders import HashingEncoder
        from sif.pipeline import SIFPipeline

        pipeline = SIFPipeline(encoder=HashingEncoder())
        for path in sorted(glob.glob(os.path.join(LANGUAGES, "*_report.txt"))):
            with self.subTest(os.path.basename(path)):
                text = split_reports(_read(path))[0]
                result = pipeline.analyze(text, translated=keyword_gloss(text))
                self.assertTrue(result.sif_potential)
                self.assertGreaterEqual(result.risk_score, 60)
                self.assertLess(result.risk_score, 96)


class TestMockPdfReports(unittest.TestCase):
    """samples/reports: a SIF and a non-SIF report in seven languages."""

    @classmethod
    def setUpClass(cls) -> None:
        from sif.encoders import HashingEncoder
        from sif.ocr import DocumentExtractor
        from sif.pipeline import SIFPipeline

        cls.extractor = DocumentExtractor()
        cls.pipeline = SIFPipeline(encoder=HashingEncoder())
        cls.paths = sorted(glob.glob(os.path.join(REPORTS, "*.pdf")))

    def test_there_is_a_sif_and_a_non_sif_report_in_seven_languages(self) -> None:
        names = [os.path.basename(path) for path in self.paths]
        self.assertEqual(len(names), 14)
        for language in ("english", "assamese", "hindi", "bengali", "tamil", "marathi",
                         "kannada"):
            with self.subTest(language):
                self.assertIn(1, [name.count(f"{language}_sif_") for name in names])
                self.assertIn(1, [name.count(f"{language}_non_sif_") for name in names])

    def test_each_pdf_is_read_as_one_report_in_its_language_with_the_right_verdict(self) -> None:
        for path in self.paths:
            name = os.path.basename(path)
            with self.subTest(name):
                document = self.extractor.extract(path)
                self.assertEqual(document.backend, "pdf-text", "read without OCR")
                reports = document.blocks()
                self.assertEqual(len(reports), 1)
                text = reports[0]
                language = name.split("_")[0].title()
                detected = detect_language(text)
                self.assertEqual(detected.name, language)
                gloss = "" if detected.english else keyword_gloss(text)
                result = self.pipeline.analyze(text, translated=gloss)
                expected = "_non_sif_" not in name
                self.assertEqual(result.sif_potential, expected,
                                 f"{name}: {result.explanation}")
                self.assertLess(result.risk_score, 96)


if __name__ == "__main__":
    unittest.main()

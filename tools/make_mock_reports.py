"""Build the mock PDF reports in samples/reports/.

Fourteen one-page UA/UC report forms - a SIF precursor and a non-SIF report
in each of English, Assamese, Hindi, Bengali, Tamil, Marathi and Kannada - to
test SENTRA end to end: PDF reading, report splitting, language detection,
translation (or the keyword gloss without Ollama), and the SIF verdict.

Nothing here is a real Oil India record. Every form says "MOCK" at the top.

How the PDFs are made
---------------------
* **English** is an ordinary digital PDF with a text layer, written by Qt.
* **Indian-language** pages are drawn by Qt (which shapes Indic scripts
  correctly) into an image, and carry an invisible text layer with the exact
  Unicode, the way a searchable scan does. A PDF's own text of shaped Indic
  glyphs comes back scrambled from every PDF reader - conjuncts and the
  pre-base ि/ে vowel signs are stored in visual order - so a text layer
  written that way would test the PDF format's weakness, not SENTRA.

Run from the project folder (needs PyQt6 and PyMuPDF, and the FreeSerif font
from GNU FreeFont - ``apt install fonts-freefont-ttf`` - or any font with the
scripts, given with --font)::

    pip install pymupdf
    python tools/make_mock_reports.py
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "samples", "reports")
FONT = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"


@dataclass(frozen=True)
class MockReport:
    file: str
    language: str
    sif: bool
    #: What the report is about, in English, for the README.
    summary: str
    title: str
    fields: str
    narrative: str
    action: str


MOCK_LINE = "MOCK REPORT - SENTRA TEST DATA - NOT A REAL RECORD"

REPORTS: Tuple[MockReport, ...] = (
    # -- English -------------------------------------------------------------------------
    MockReport(
        "english_sif_flowline_pressure.pdf", "English", True,
        "Flange opened on a live 18 bar flow line, no permit",
        "OIL INDIA LIMITED - UNSAFE ACT / UNSAFE CONDITION REPORT",
        "Site: Naharkatiya Well Pad NHK-212    Date: 14-09-2026    Report no: UAUC/EN/0201",
        "While replacing a leaking gasket on the 6-inch flow line, the contract crew\n"
        "opened the flange without depressurising the line. The pressure gauge still\n"
        "read 18 bar and the fitter stood in line with the flange. There was no valid\n"
        "permit for line breaking and the wing valve was not locked out.",
        "Immediate action: work stopped, line isolated and bled down, permit raised.",
    ),
    MockReport(
        "english_non_sif_housekeeping.pdf", "English", False,
        "Cartons and cable ties on a store walkway, cleared",
        "OIL INDIA LIMITED - UNSAFE ACT / UNSAFE CONDITION REPORT",
        "Site: Duliajan Central Stores    Date: 15-09-2026    Report no: UAUC/EN/0202",
        "Empty cartons and loose cable ties were left on the walkway beside the\n"
        "racking in the central store after a delivery. The storekeeper cleared the\n"
        "walkway within the hour and reminded the team to use the scrap bin.",
        "Immediate action: walkway cleared; no injury.",
    ),
    # -- Assamese ------------------------------------------------------------------------
    MockReport(
        "assamese_sif_feeder_no_loto.pdf", "Assamese", True,
        "11 kV feeder left unearthed, cable jointing without LOTO",
        "অইল ইণ্ডিয়া লিমিটেড - অসুৰক্ষিত কাৰ্য / অৱস্থাৰ প্ৰতিবেদন",
        "স্থান: দুলীয়াজান OCS-4    তাৰিখ: 16-09-2026    প্ৰতিবেদন নং: UAUC/AS/0203",
        "পাম্পৰ মটৰ মেৰামতিৰ সময়ত 11 কেভি ফিডাৰ কেবলটো আৰ্থিং নকৰাকৈ এৰি\n"
        "থোৱা হৈছিল। ইলেক্ট্ৰিচিয়ানে লটো নকৰাকৈ কেবল জোৰা দিবলৈ আৰম্ভ কৰিছিল\n"
        "আৰু আইছোলেচন প্ৰমাণপত্ৰ দিয়া হোৱা নাছিল।",
        "তাৎক্ষণিক ব্যৱস্থা: কাম বন্ধ কৰা হ'ল; ফিডাৰ আইছোলেট কৰি আৰ্থিং কৰা হ'ল।",
    ),
    MockReport(
        "assamese_non_sif_wet_walkway.pdf", "Assamese", False,
        "Rainwater on an office walkway, mopped and signed",
        "অইল ইণ্ডিয়া লিমিটেড - অসুৰক্ষিত কাৰ্য / অৱস্থাৰ প্ৰতিবেদন",
        "স্থান: নাহৰকটীয়া কাৰ্যালয়    তাৰিখ: 17-09-2026    প্ৰতিবেদন নং: UAUC/AS/0204",
        "কেণ্টিনৰ ওচৰৰ খোজকঢ়া পথত বৰষুণৰ পানী জমা হৈ পিচল হৈছিল।\n"
        "হাউচকিপিং দলে পানী আঁতৰাই সতৰ্কবাণী ফলক লগালে।",
        "তাৎক্ষণিক ব্যৱস্থা: পথ চাফা কৰা হ'ল; কোনো আঘাত পোৱা নাই।",
    ),
    # -- Hindi ---------------------------------------------------------------------------
    MockReport(
        "hindi_sif_hot_work_expired_permit.pdf", "Hindi", True,
        "Welding beside a condensate tank on an expired permit, no gas test, no fire watch",
        "ऑयल इंडिया लिमिटेड - असुरक्षित कार्य / स्थिति रिपोर्ट",
        "स्थल: मोरान जीजीएस    दिनांक: 18-09-2026    रिपोर्ट संख्या: UAUC/HI/0205",
        "कंडेनसेट टैंक के पास वेल्डर ने परमिट समाप्त होने के बाद भी वेल्डिंग जारी रखी।\n"
        "गैस परीक्षण नहीं किया गया और फायर वॉचर मौजूद नहीं था।\n"
        "चिंगारियाँ ड्रेन पिट की ओर गिर रही थीं।",
        "तत्काल कार्रवाई: काम रोका गया; क्षेत्र खाली कराया गया।",
    ),
    MockReport(
        "hindi_non_sif_controlled_lift.pdf", "Hindi", False,
        "Crane lift done to plan; a worn tag line replaced",
        "ऑयल इंडिया लिमिटेड - असुरक्षित कार्य / स्थिति रिपोर्ट",
        "स्थल: दुलियाजान पाइप यार्ड    दिनांक: 19-09-2026    रिपोर्ट संख्या: UAUC/HI/0206",
        "क्रेन से पाइप उतारते समय क्षेत्र की घेराबंदी की गई थी, बैंकसमैन मौजूद था\n"
        "और लिफ्ट प्लान स्वीकृत था। एक टैग लाइन घिसी हुई पाई गई और तुरंत बदली गई।",
        "तत्काल कार्रवाई: टैग लाइन बदली गई; कोई चोट नहीं हुई।",
    ),
    # -- Bengali -------------------------------------------------------------------------
    MockReport(
        "bengali_sif_under_suspended_load.pdf", "Bengali", True,
        "Two workers under a 4 t module on the crane, no lift plan",
        "অয়েল ইন্ডিয়া লিমিটেড - অনিরাপদ কাজ / অবস্থা প্রতিবেদন",
        "স্থান: মরান গ্যাস কম্প্রেসর স্টেশন    তারিখ: 20-09-2026    প্রতিবেদন নং: UAUC/BN/0207",
        "ক্রেন দিয়ে চার টনের মডিউল তোলার সময় দুজন শ্রমিক ঝুলন্ত লোডের নিচে কাজ\n"
        "করছিলেন। লিফট প্ল্যান ছাড়াই কাজ শুরু হয়েছিল এবং নিষিদ্ধ এলাকা চিহ্নিত\n"
        "করা হয়নি।",
        "তাৎক্ষণিক ব্যবস্থা: উত্তোলন বন্ধ করা হয়েছে; এলাকা খালি করা হয়েছে।",
    ),
    MockReport(
        "bengali_non_sif_store_walkway.pdf", "Bengali", False,
        "Packing material on a warehouse walkway, cleared",
        "অয়েল ইন্ডিয়া লিমিটেড - অনিরাপদ কাজ / অবস্থা প্রতিবেদন",
        "স্থান: দুলিয়াজান স্টোর গুদাম    তারিখ: 21-09-2026    প্রতিবেদন নং: UAUC/BN/0208",
        "গুদামে কার্টন ও প্লাস্টিকের মোড়ক হাঁটার পথে পড়ে ছিল।\n"
        "স্টোরকিপার জায়গাটি পরিষ্কার করেন।",
        "তাৎক্ষণিক ব্যবস্থা: পথ পরিষ্কার করা হয়েছে; কেউ আহত হননি।",
    ),
    # -- Tamil ---------------------------------------------------------------------------
    MockReport(
        "tamil_sif_confined_space.pdf", "Tamil", True,
        "Separator tank entry with no gas test or ventilation, expired permit, H2S",
        "ஆயில் இந்தியா லிமிடெட் - பாதுகாப்பற்ற செயல் / நிலை அறிக்கை",
        "நிலையம்: மோரான் எரிவாயு நிலையம்    நாள்: 22-09-2026    அறிக்கை எண்: UAUC/TA/0209",
        "இரண்டு பணியாளர்கள் வாயு பரிசோதனை இல்லாமல் பிரிப்பான் தொட்டிக்குள்\n"
        "நுழைந்தனர். காற்றோட்டம் வழங்கப்படவில்லை மற்றும் நுழைவு அனுமதிச் சீட்டு\n"
        "காலாவதியாகிவிட்டது. பின்னர் H2S கண்டறியப்பட்டது.",
        "உடனடி நடவடிக்கை: இருவரும் வெளியேற்றப்பட்டனர்; பணி நிறுத்தப்பட்டது.",
    ),
    MockReport(
        "tamil_non_sif_parking_water.pdf", "Tamil", False,
        "Standing rainwater in an office car park, cleared",
        "ஆயில் இந்தியா லிமிடெட் - பாதுகாப்பற்ற செயல் / நிலை அறிக்கை",
        "நிலையம்: நஹர்கட்டியா அலுவலகம்    நாள்: 23-09-2026    அறிக்கை எண்: UAUC/TA/0210",
        "அலுவலக வாகன நிறுத்துமிடத்தில் மழைநீர் தேங்கி நடைபாதை வழுக்கலாக இருந்தது.\n"
        "பராமரிப்புக் குழு நீரை அகற்றி எச்சரிக்கை பலகை வைத்தது.",
        "உடனடி நடவடிக்கை: நீர் அகற்றப்பட்டது; யாருக்கும் காயம் இல்லை.",
    ),
    # -- Marathi -------------------------------------------------------------------------
    MockReport(
        "marathi_sif_work_at_height.pdf", "Marathi", True,
        "Harness clipped to a railing at 9 m, scaffold tag expired",
        "ऑइल इंडिया लिमिटेड - असुरक्षित कृती / स्थिती अहवाल",
        "ठिकाण: दुलियाजान पाईप रॅक    दिनांक: 24-09-2026    अहवाल क्रमांक: UAUC/MR/0211",
        "सुमारे 9 मीटर उंचीवर काम करताना कामगाराचा हार्नेस लॅनयार्ड अँकर पॉइंटऐवजी\n"
        "रेलिंगला अडकवलेला आढळला. मचाणाचा तपासणी टॅग कालबाह्य झाला होता.",
        "तत्काळ कृती: काम थांबवले; कामगाराला खाली उतरवले.",
    ),
    MockReport(
        "marathi_non_sif_controlled_hot_work.pdf", "Marathi", False,
        "Welding on a valid permit, gas test done, fire watch present",
        "ऑइल इंडिया लिमिटेड - असुरक्षित कृती / स्थिती अहवाल",
        "ठिकाण: मोरान कार्यशाळा    दिनांक: 25-09-2026    अहवाल क्रमांक: UAUC/MR/0212",
        "वैध हॉट वर्क परवान्यासह वेल्डिंग काम झाले. गॅस चाचणी केली होती,\n"
        "अग्निशामक आणि फायर वॉचर उपस्थित होते. वेल्डिंग केबलचे एक आवरण\n"
        "घासलेले आढळले आणि ते बदलले.",
        "तत्काळ कृती: केबल बदलली; परिसर स्वच्छ केला.",
    ),
    # -- Kannada -------------------------------------------------------------------------
    MockReport(
        "kannada_sif_tanker_fatigue_fog.pdf", "Kannada", True,
        "Crude tanker driver 11 hours at the wheel, overtook in fog",
        "ಆಯಿಲ್ ಇಂಡಿಯಾ ಲಿಮಿಟೆಡ್ - ಅಸುರಕ್ಷಿತ ಕೃತ್ಯ / ಸ್ಥಿತಿ ವರದಿ",
        "ಸ್ಥಳ: ದುಲಿಯಾಜನ್ - ಮೋರಾನ್ ರಸ್ತೆ    ದಿನಾಂಕ: 26-09-2026    ವರದಿ ಸಂಖ್ಯೆ: UAUC/KA/0213",
        "ಕಚ್ಚಾ ತೈಲ ಟ್ಯಾಂಕರ್ ಚಾಲಕ ಹನ್ನೊಂದು ಗಂಟೆಗಳಿಂದ ನಿರಂತರವಾಗಿ ವಾಹನ\n"
        "ಚಲಾಯಿಸುತ್ತಿದ್ದರು ಮತ್ತು ದಟ್ಟ ಮಂಜಿನಲ್ಲಿ ಓವರ್‌ಟೇಕ್ ಮಾಡಿದರು.\n"
        "ಎದುರಿನಿಂದ ಬಂದ ಬಸ್ ಕೊನೆಯ ಕ್ಷಣದಲ್ಲಿ ಬ್ರೇಕ್ ಹಾಕಿತು.",
        "ತಕ್ಷಣದ ಕ್ರಮ: ವಾಹನ ನಿಲ್ಲಿಸಲಾಯಿತು; ಬದಲಿ ಚಾಲಕನನ್ನು ಕರೆಸಲಾಯಿತು.",
    ),
    MockReport(
        "kannada_non_sif_first_aid_box.pdf", "Kannada", False,
        "First-aid box short of bandages, refilled",
        "ಆಯಿಲ್ ಇಂಡಿಯಾ ಲಿಮಿಟೆಡ್ - ಅಸುರಕ್ಷಿತ ಕೃತ್ಯ / ಸ್ಥಿತಿ ವರದಿ",
        "ಸ್ಥಳ: ನಹರ್‌ಕಟಿಯಾ ಕಚೇರಿ    ದಿನಾಂಕ: 27-09-2026    ವರದಿ ಸಂಖ್ಯೆ: UAUC/KA/0214",
        "ಕಚೇರಿಯ ಪ್ರಥಮ ಚಿಕಿತ್ಸಾ ಪೆಟ್ಟಿಗೆಯಲ್ಲಿ ಬ್ಯಾಂಡೇಜ್ ಮತ್ತು ಆಂಟಿಸೆಪ್ಟಿಕ್\n"
        "ಖಾಲಿಯಾಗಿದ್ದವು. ಸುರಕ್ಷತಾ ಅಧಿಕಾರಿ ಅವುಗಳನ್ನು ತಕ್ಷಣ ಮರುಪೂರಣ ಮಾಡಿದರು.",
        "ತಕ್ಷಣದ ಕ್ರಮ: ಪೆಟ್ಟಿಗೆ ಮರುಪೂರಣ ಮಾಡಲಾಯಿತು; ಯಾರಿಗೂ ಗಾಯವಾಗಿಲ್ಲ.",
    ),
)


def report_text(report: MockReport) -> str:
    """The report as SENTRA should read it back: heading, narrative, action."""
    return "\n".join((report.title, MOCK_LINE, report.fields)) + "\n\n" + \
        report.narrative + "\n\n" + report.action


def _html(report: MockReport, family: str) -> str:
    def lines(text: str) -> str:
        return "<br/>".join(line for line in text.splitlines())

    # FreeSerif's bold face has no Bengali/Assamese: a bold line would fall
    # back to a font that cannot join the letters. Colour and size mark
    # emphasis in the Indian-language forms instead.
    bold = "bold" if report.language == "English" else "normal"
    stamp = ("<span style='color:#B42318'>SIF precursor</span>" if report.sif
             else "<span style='color:#1F7A4D'>non-SIF</span>")
    return f"""
    <div style="font-family:'{family}'; color:#10213A">
      <table width="100%" cellspacing="0" cellpadding="8"
             style="background:#0F2742; color:#FFFFFF">
        <tr><td style="font-size:19pt; font-weight:{bold}">{report.title}</td></tr>
        <tr><td style="font-size:10pt; color:#F2C94C; letter-spacing:1px">{MOCK_LINE}
            &nbsp;·&nbsp; {report.language} &nbsp;·&nbsp; expected: {stamp}</td></tr>
      </table>
      <p style="font-size:12pt; margin-top:14px; padding:8px; background:#EEF2F7">
        {report.fields.replace('    ', ' &nbsp;&nbsp;|&nbsp;&nbsp; ')}</p>
      <p style="font-size:14pt; line-height:150%; margin-top:18px">{lines(report.narrative)}</p>
      <p style="font-size:14pt; line-height:150%; margin-top:14px; font-weight:{bold};
         color:#0F2742; border-left:4px solid #0F2742; padding-left:8px">{lines(report.action)}</p>
      <p style="font-size:9pt; color:#6B7A90; margin-top:40px">
        Synthetic test document made by tools/make_mock_reports.py for SENTRA
        (SIH PS 26165). It describes no real person, event or record.</p>
    </div>"""


def _page_image(report: MockReport, family: str, dpi: int = 150):
    from PyQt6.QtCore import QRectF, QSizeF
    from PyQt6.QtGui import QColor, QImage, QPainter, QTextDocument

    width, height = int(8.27 * dpi), int(11.69 * dpi)
    margin = int(0.7 * dpi)
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#FFFFFF"))
    document = QTextDocument()
    document.setDocumentMargin(0)
    document.setPageSize(QSizeF(width - 2 * margin, height - 2 * margin))
    document.setHtml(_html(report, family))
    # The HTML is sized in points; the page is drawn at `dpi`.
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.translate(margin, margin)
    scale = dpi / 96.0
    painter.scale(scale, scale)
    document.setTextWidth((width - 2 * margin) / scale)
    document.drawContents(painter, QRectF(0, 0, (width - 2 * margin) / scale,
                                          (height - 2 * margin) / scale))
    painter.end()
    return image


def _write_scanned_style(report: MockReport, family: str, font: str, path: str) -> None:
    """A page image plus an invisible text layer holding the exact Unicode."""
    import pymupdf
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice

    image = _page_image(report, family)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "JPG", 70)
    buffer.close()

    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=bytes(data))
    # Line by line, top to bottom, with a blank line between the heading, the
    # narrative and the action - the layout a reader keeps as paragraphs.
    y = 60.0
    for block in report_text(report).split("\n\n"):
        for line in block.splitlines():
            page.insert_text((50, y), line, fontfile=font, fontname="F0", fontsize=10,
                             render_mode=3)
            y += 16
        y += 22
    pdf.set_metadata({"title": f"MOCK - {report.summary}", "author": "SENTRA test data",
                      "subject": f"{report.language} UA/UC report (mock)",
                      "creator": "tools/make_mock_reports.py"})
    pdf.subset_fonts()          # the invisible layer needs a few hundred glyphs, not 2 MB
    pdf.save(path, garbage=4, deflate=True)
    pdf.close()


def _write_digital(report: MockReport, family: str, path: str) -> None:
    """An ordinary text PDF (English)."""
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter)
    writer.setResolution(96)
    writer.setTitle(f"MOCK - {report.summary}")
    writer.setCreator("tools/make_mock_reports.py")
    document = QTextDocument()
    document.setPageSize(writer.pageLayout().paintRectPixels(96).size().toSizeF())
    document.setHtml(_html(report, family))
    document.print(writer)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--font", default=FONT, help="a TTF with the Indic scripts")
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args(argv)
    if not os.path.exists(args.font):
        parser.error(f"font not found: {args.font}")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtGui import QFontDatabase, QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - Qt needs it
    font_id = QFontDatabase.addApplicationFont(args.font)
    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    os.makedirs(args.out, exist_ok=True)
    for report in REPORTS:
        path = os.path.join(args.out, report.file)
        if report.language == "English":
            _write_digital(report, family, path)
        else:
            _write_scanned_style(report, family, args.font, path)
        print(f"{report.file:45s} {os.path.getsize(path) // 1024:4d} KB  "
              f"{'SIF' if report.sif else 'non-SIF'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

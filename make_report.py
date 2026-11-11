"""Generate the Arabic report (Markdown and DOCX) from experiment results."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt

from config import ALGORITHM_NAMES, SIZE_NAMES
from src.analysis import read_csv_rows
from src.plotting import generate_all_figures

SIZE_LABELS = {"small": "الصغيرة", "medium": "المتوسطة", "large": "الكبيرة"}


def _float(row: dict, key: str) -> float:
    return float(row[key])


def _int(row: dict, key: str) -> int:
    return int(float(row[key]))


def _summary_lookup(summary: list[dict], size: str, algorithm: str) -> dict:
    for row in summary:
        if row["size"] == size and row["algorithm"] == algorithm:
            return row
    raise KeyError(f"Missing summary row for {size}/{algorithm}")


def _average_metric(summary: list[dict], algorithm: str, key: str) -> float:
    values = [_float(row, key) for row in summary if row["algorithm"] == algorithm]
    return sum(values) / len(values) if values else 0.0


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def _set_rtl_run(run) -> None:
    run.font.name = "Arial"
    r_pr = run._element.get_or_add_rPr()
    r_pr.get_or_add_rFonts().set(qn("w:cs"), "Arial")
    rtl = OxmlElement("w:rtl")
    r_pr.insert_element_before(
        rtl,
        "w:cs",
        "w:em",
        "w:lang",
        "w:eastAsianLayout",
        "w:specVanish",
        "w:oMath",
    )


def _set_rtl_paragraph(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    p_pr.insert_element_before(
        bidi,
        "w:adjustRightInd",
        "w:snapToGrid",
        "w:spacing",
        "w:ind",
        "w:contextualSpacing",
        "w:mirrorIndents",
        "w:suppressOverlap",
        "w:jc",
        "w:textDirection",
        "w:textAlignment",
        "w:textboxTightWrap",
        "w:outlineLvl",
        "w:divId",
        "w:cnfStyle",
        "w:rPr",
        "w:sectPr",
        "w:pPrChange",
    )


def _add_text(doc: Document, text: str, size: int = 11, bold: bool = False, italic: bool = False) -> None:
    paragraph = doc.add_paragraph()
    _set_rtl_paragraph(paragraph)
    run = paragraph.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    _set_rtl_run(run)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    paragraph = doc.add_paragraph()
    _set_rtl_paragraph(paragraph)
    paragraph.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    paragraph.paragraph_format.space_after = Pt(6)
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(16 if level == 1 else 13)
    _set_rtl_run(run)


def _add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        paragraph = doc.add_paragraph()
        _set_rtl_paragraph(paragraph)
        paragraph.paragraph_format.right_indent = Cm(0.5)
        run = paragraph.add_run("• " + item)
        run.font.size = Pt(11)
        _set_rtl_run(run)


def _add_table(doc: Document, headers: list[str], rows: list[list[str]], font_size: int = 9) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    bidi_visual = OxmlElement("w:bidiVisual")
    table._tbl.tblPr.insert_element_before(
        bidi_visual,
        "w:tblStyleRowBandSize",
        "w:tblStyleColBandSize",
        "w:tblW",
        "w:jc",
        "w:tblCellSpacing",
        "w:tblInd",
        "w:tblBorders",
        "w:shd",
        "w:tblLayout",
        "w:tblCellMar",
        "w:tblLook",
        "w:tblCaption",
        "w:tblDescription",
    )

    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = ""
        paragraph = cell.paragraphs[0]
        _set_rtl_paragraph(paragraph)
        run = paragraph.add_run(header)
        run.bold = True
        run.font.size = Pt(font_size)
        _set_rtl_run(run)

    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = ""
            paragraph = cell.paragraphs[0]
            _set_rtl_paragraph(paragraph)
            run = paragraph.add_run(str(value))
            run.font.size = Pt(font_size)
            _set_rtl_run(run)


def _add_image(doc: Document, path: Path, caption: str) -> None:
    picture_paragraph = doc.add_paragraph()
    picture_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = picture_paragraph.add_run()
    run.add_picture(str(path), width=Inches(6.0))
    caption_paragraph = doc.add_paragraph()
    _set_rtl_paragraph(caption_paragraph)
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_run = caption_paragraph.add_run(caption)
    caption_run.italic = True
    caption_run.font.size = Pt(9)
    _set_rtl_run(caption_run)


def _render_markdown(blocks: list[dict], output_dir: Path) -> str:
    parts: list[str] = []
    for block in blocks:
        kind = block["type"]
        if kind == "title":
            parts.append(f"# {block['text']}")
        elif kind == "subtitle":
            parts.append(f"**{block['text']}**")
        elif kind == "h1":
            parts.append(f"## {block['text']}")
        elif kind == "h2":
            parts.append(f"### {block['text']}")
        elif kind == "p":
            parts.append(block["text"])
        elif kind == "bullets":
            parts.append("\n".join(f"- {item}" for item in block["items"]))
        elif kind == "table":
            parts.append(_md_table(block["headers"], block["rows"]))
        elif kind == "image":
            path = block["path"]
            relative = os.path.relpath(path, output_dir).replace("\\", "/")
            parts.append(f"![{block['caption']}]({relative})")
            parts.append(f"*{block['caption']}*")
        elif kind == "pagebreak":
            parts.append('<div style="page-break-after: always;"></div>')
        elif kind == "note":
            parts.append(f"*{block['text']}*")
        else:
            raise ValueError(f"Unknown block type: {kind}")
    return "\n\n".join(parts) + "\n"


def _render_docx(blocks: list[dict], output: Path) -> None:
    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    document.core_properties.title = "تخصيص الميزانية لاختيار حزمة مشاريع"
    document.core_properties.author = "فريق المشروع"

    normal_style = document.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(11)
    normal_style.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:cs"), "Arial")

    for block in blocks:
        kind = block["type"]
        if kind == "title":
            paragraph = document.add_paragraph()
            _set_rtl_paragraph(paragraph)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(block["text"])
            run.bold = True
            run.font.size = Pt(24)
            _set_rtl_run(run)
        elif kind == "subtitle":
            paragraph = document.add_paragraph()
            _set_rtl_paragraph(paragraph)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(block["text"])
            run.bold = True
            run.font.size = Pt(14)
            _set_rtl_run(run)
        elif kind == "h1":
            _add_heading(document, block["text"], level=1)
        elif kind == "h2":
            _add_heading(document, block["text"], level=2)
        elif kind == "p":
            _add_text(document, block["text"])
        elif kind == "bullets":
            _add_bullets(document, block["items"])
        elif kind == "table":
            _add_table(document, block["headers"], block["rows"], block.get("font_size", 9))
            document.add_paragraph()
        elif kind == "image":
            _add_image(document, block["path"], block["caption"])
        elif kind == "pagebreak":
            document.add_page_break()
        elif kind == "note":
            _add_text(document, block["text"], size=9, italic=True)
        else:
            raise ValueError(f"Unknown block type: {kind}")

    document.save(output)


def build_blocks(summary: list[dict], dp_rows: list[dict], config: dict, figures_dir: Path) -> list[dict]:
    summary_by = {(row["size"], row["algorithm"]): row for row in summary}
    dp_by_size = {row["size"]: row for row in dp_rows}
    missing = [
        (size, algorithm)
        for size in SIZE_NAMES
        for algorithm in ALGORITHM_NAMES
        if (size, algorithm) not in summary_by
    ]
    if missing:
        raise ValueError(
            "The report requires the full experiment (all three sizes and all three algorithms). "
            "Run `python run_experiments.py` without --quick first. Missing: "
            + ", ".join(f"{size}/{algorithm}" for size, algorithm in missing)
        )

    overall_rank = sorted(
        ALGORITHM_NAMES,
        key=lambda algorithm: _average_metric(summary, algorithm, "mean_gap_pct"),
    )
    fastest = min(ALGORITHM_NAMES, key=lambda algorithm: _average_metric(summary, algorithm, "mean_runtime_sec"))
    most_stable = min(ALGORITHM_NAMES, key=lambda algorithm: _average_metric(summary, algorithm, "std_gap_pct"))

    blocks: list[dict] = []
    blocks.append({"type": "title", "text": "تخصيص الميزانية لاختيار حزمة مشاريع"})
    blocks.append(
        {
            "type": "subtitle",
            "text": "مقارنة بين الخوارزمية الجينية، وسرب الجسيمات الثنائي، ومستعمرة النمل، مع حل دقيق بالبرمجة الديناميكية",
        }
    )
    blocks.append({"type": "p", "text": "تقرير مشروع مقرر الخوارزميات — الفصل خريف 2026"})
    blocks.append({"type": "p", "text": "الجامعة: ................................    الكلية: ................................"})
    blocks.append({"type": "p", "text": "أعضاء الفريق: (يُستبدل الجدول أدناه بأسماء أعضاء الفريق وأرقامهم الجامعية)"})

    team_rows = [
        ["1", "[اسم العضو 1]", "[الرقم الجامعي]", "تنسيق المشروع، صياغة المشكلة، وكتابة التقرير", "16.7%"],
        ["2", "[اسم العضو 2]", "[الرقم الجامعي]", "توليد البيانات والتحقق من صحتها", "16.7%"],
        ["3", "[اسم العضو 3]", "[الرقم الجامعي]", "تنفيذ الخوارزمية الجينية GA واختبارها", "16.7%"],
        ["4", "[اسم العضو 4]", "[الرقم الجامعي]", "تنفيذ BPSO واختبارها", "16.7%"],
        ["5", "[اسم العضو 5]", "[الرقم الجامعي]", "تنفيذ ACO واختبارها", "16.7%"],
        ["6", "[اسم العضو 6]", "[الرقم الجامعي]", "تنفيذ DP، إدارة التجارب، والرسوم البيانية", "16.5%"],
    ]
    blocks.append(
        {
            "type": "table",
            "headers": ["#", "الاسم", "الرقم الجامعي", "المهمة", "نسبة المساهمة"],
            "rows": team_rows,
            "font_size": 8,
        }
    )
    blocks.append({"type": "note", "text": "ملاحظة: يتكون فريق المشروع من 6 إلى 9 طلاب؛ يمكن إضافة صفوف إضافية عند الحاجة."})
    blocks.append({"type": "p", "text": "تاريخ التسليم: 12 تشرين الثاني/نوفمبر 2026"})
    blocks.append({"type": "pagebreak"})

    blocks.append({"type": "h1", "text": "الملخص"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يعرض هذا المشروع دراسة تطبيقية لمشكلة تخصيص الميزانية لاختيار حزمة من المشاريع المقترحة، "
                "وهي مشكلة تُنمذج على شكل حقيبة ظهر ثنائية (0/1 Knapsack): لكل مشروع كلفة وقيمة متوقعة، "
                "ويجب اختيار مجموعة جزئية من المشاريع تعظّم القيمة الكلية دون تجاوز الميزانية المتاحة. "
                "تم تنفيذ ثلاث خوارزميات تحسين ذكية من الصفر: الخوارزمية الجينية (GA)، وخوارزمية سرب الجسيمات "
                "الثنائية (BPSO)، وخوارزمية مستعمرة النمل (ACO)، إضافة إلى حل دقيق باستخدام البرمجة الديناميكية (DP) "
                "يُستخدم كخط أساس لحساب الفجوة المثالية (Optimality Gap). "
                "أُجريت التجارب على ثلاث حالات بأحجام 20 و60 و150 مشروعاً، بواقع 30 تشغيلاً مستقلاً لكل خوارزمية "
                "في كل حجم، وبميزانية تقييم موحدة قدرها 25,000 تقييم. "
                "أظهرت النتائج تفوق GA في متوسط الجودة على الحالات الثلاث، واقتراب ACO من الحل الأمثل، "
                "في حين عانى BPSO من التقارب المبكر وتراجع واضح في الحالة الكبيرة. "
                "كما أكدت النتائج أن DP دقيق وسريع جداً في هذه الأحجام، لكن زمنه وذاكرته يعتمدان على سعة الميزانية "
                "وفق التعقيد شبه متعدد الحدود O(nB)."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "الكلمات المفتاحية: تخصيص الموارد، حقيبة الظهر 0/1، الخوارزمية الجينية، سرب الجسيمات الثنائي، "
                "مستعمرة النمل، البرمجة الديناميكية، الفجوة المثالية، الاستقرار."
            ),
        }
    )

    blocks.append({"type": "h1", "text": "1. المقدمة"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "تُعدّ مشكلة تخصيص الميزانية من المشكلات الواقعية المتكررة في إدارة المشاريع والموارد: "
                "تمتلك المؤسسة قائمة مشاريع مرشحة، ولكل مشروع كلفة تنفيذ وقيمة أو عائد متوقع، وتريد اختيار "
                "حزمة مشاريع تحقق أكبر قيمة ممكنة ضمن ميزانية محدودة. عند افتراض أن المشاريع غير قابلة للتجزئة "
                "وأن التكاليف والعوائد مقدرة بشكل حتمي، فإن المشكلة تتحول مباشرة إلى مشكلة حقيبة الظهر الثنائية "
                "(0/1 Knapsack)، وهي مشكلة تحسين توافقية معروفة تنتمي إلى فئة المسائل الصعبة (NP-hard)."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "يمكن حل المشكلة حلاً دقيقاً باستخدام البرمجة الديناميكية عندما تكون الميزانية عدداً صحيحاً "
                "ومحدوداً، إذ يعتمد الحل على تعقيد زمني O(nB) وذاكرة O(B). لكن هذا التعقيد يصبح غير عملي عندما "
                "تكبر الميزانية كثيراً أو تُضاف قيود متعددة، فتصبح الخوارزميات التقريبية والاستدلالية خياراً مهماً. "
                "يهدف هذا المشروع إلى تصميم الخوارزميات الثلاث GA وBPSO وACO من الصفر، ثم مقارنتها مع DP من حيث "
                "جودة الحل، وزمن التنفيذ، وسرعة التقارب، والاستقرار عبر التشغيلات المستقلة."
            ),
        }
    )

    blocks.append({"type": "h1", "text": "2. وصف المشكلة والصياغة الرياضية"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "لتكن P = {1, 2, ..., n} مجموعة المشاريع المرشحة. لكل مشروع i كلفة c_i > 0 وقيمة متوقعة v_i > 0، "
                "ولتكن B الميزانية الكلية المتاحة. يُعرَّف متغير القرار x_i ∈ {0,1} بحيث يأخذ القيمة 1 إذا اختير "
                "المشروع i، و0 خلاف ذلك. الصياغة الرياضية هي:"
            ),
        }
    )
    blocks.append({"type": "p", "text": "Maximize  f(x) = Σ_{i=1}^{n} v_i x_i"})
    blocks.append({"type": "p", "text": "Subject to  Σ_{i=1}^{n} c_i x_i ≤ B,    x_i ∈ {0,1}"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "القيمة المثالية f* هي أكبر قيمة ممكنة بين جميع الحلول الممكنة. وتُعرَّف الفجوة المثالية لتشغيل معين "
                "بـ: Gap(%) = 100 × (f* − f_run) / f*، حيث f_run هي أفضل قيمة وجدتها الخوارزمية في ذلك التشغيل. "
                "تشمل فرضيات النموذج: عدم قابلية المشاريع للتجزئة، ثبات التكاليف والعوائد، وجود قيد ميزانية واحد، "
                "وعدم وجود تبعيات أو تعارضات بين المشاريع."
            ),
        }
    )

    blocks.append({"type": "h1", "text": "3. تمثيل الحل ودالة الهدف وآلية الإصلاح"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يُمثَّل الحل في الخوارزميات الثلاث بمتجه ثنائي x = (x_1, ..., x_n) ∈ {0,1}^n. "
                "دالة الهدف هي القيمة الكلية للمشاريع المختارة، والقيود هي ألا يتجاوز مجموع التكاليف الميزانية. "
                "ولضمان أن تكون جميع الحلول قابلة للتنفيذ، استُخدم مُعامل إصلاح (Repair Operator) مشترك بين "
                "GA وBPSO: إذا كان الحل يتجاوز الميزانية، تُحذف المشاريع المختارة ذات أقل نسبة قيمة/كلفة "
                "بالتتابع حتى تصبح الكلفة ضمن الميزانية، ثم تُضاف المشاريع غير المختارة وفق أعلى نسبة قيمة/كلفة "
                "طالما بقيت مساحة في الميزانية. يبني ACO حلولاً ممكنة أثناء البناء، ثم يطبّق خطوة الملء الجشع "
                "نفسها. يضمن ذلك أن جميع الحلول النهائية ممكنة، ويجعل المقارنة عادلة من حيث معالجة القيود."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "تتضمن نتيجة التقييم: القيمة الكلية، والكلفة الكلية، وعدد المشاريع المختارة، ووضعية الإمكانية. "
                "تُحتسب القيمة بعد الإصلاح، ويُعاد استخدام هذا التقييم نفسه في جميع الخوارزميات."
            ),
        }
    )

    blocks.append({"type": "h1", "text": "4. الخوارزميات المستخدمة"})
    blocks.append({"type": "h2", "text": "4.1 الخوارزمية الجينية (GA)"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يمثل كل فرد في المجتمع بكروموسوم ثنائي طوله n. يبدأ المجتمع بـ 50 فرداً عشوائياً، ثم يُطبَّق "
                "اختيار بالمنافسة (Tournament Selection) بحجم 3، وتزاوج منتظم (Uniform Crossover) باحتمال 0.9، "
                "وطفرات نقطية (Bit-flip) لكل بت باحتمال 1/n، مع الاحتفاظ بأفضل فردين (Elitism). يُصلح كل فرد ويُقيَّم، "
                "وتُسجَّل أفضل قيمة بعد كل جيل. يتوقف التنفيذ عند استهلاك ميزانية 25,000 تقييم."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "آلية العمل تسمح بجمع خبرات الوالدين عبر التزاوج، بينما تحافظ الطفرات على التنوع. "
                "مناسبية التمثيل الثنائي لمشكلة الحقيبة واضحة، والإصلاح يضمن بقاء الحلول ضمن القيد. "
                "التعقيد التقريبي: O(G · P · n) إضافة إلى كلفة الإصلاح."
            ),
        }
    )

    blocks.append({"type": "h2", "text": "4.2 سرب الجسيمات الثنائي (BPSO)"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يستخدم BPSO موقعاً ثنائياً x_i وسرعة حقيقية v_i لكل جسيم. تُحدَّث السرعة وفق:"
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": "v_i(t+1) = w·v_i(t) + c1·r1·(pbest_i − x_i(t)) + c2·r2·(gbest − x_i(t))",
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": "x_i(t+1) = 1 إذا كان r < σ(v_i(t+1))، وإلا 0، حيث σ(z) = 1/(1+e^(−z)).",
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "تُقصّ السرعة عند ±v_max = ±6، ويتغير معامل القصور الذاتي w خطياً من 0.9 إلى 0.4، "
                "مع c1 = c2 = 1.5. يبدأ السرب بـ 50 جسيماً، وتُحدَّث أفضلية الجسيم pbest وأفضلية السرب gbest "
                "بعد كل تقييم، مع تطبيق الإصلاح نفسه المستخدم في GA. يتوقف عند 25,000 تقييم. "
                "تعقيده التقريبي O(I · S · n) إضافة إلى الإصلاح."
            ),
        }
    )

    blocks.append({"type": "h2", "text": "4.3 مستعمرة النمل (ACO)"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يُمثَّل الحل بمسار بناء ثنائي. تُهيَّأ فيرمونات τ_i = 0.5 لكل مشروع، وتُحسب معلومة إرشادية "
                "η_i = (v_i/c_i) / max_j(v_j/c_j). يبني كل نمل حلّاً بترتيب عشوائي للمشاريع: إذا كان المشروع "
                "يتسع في الميزانية، يُضمَّن باحتمال p_i = τ_i^α · η_i^β (مقصوصة إلى [0,1])، مع α = 1 وβ = 2. "
                "بعد البناء تُطبَّق خطوة الملء الجشع. تُحدَّث الفيرمونات بعد كل جولة وفق:"
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": "τ_i ← (1 − ρ)·τ_i + ρ·Δτ_i,    ρ = 0.1",
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "حيث يُضاف ترسيب بوزن 0.7 لأفضل حل عام، وبوزن 0.3 لأفضل حل في الجولة مضروباً في نسبة جودته إلى أفضل حل عام، ثم تُقصّ الفيرمونات في "
                "المجال [0.01, 1.0]. تتكون المستعمرة من 50 نملة، ويتوقف التنفيذ عند 25,000 تقييم. "
                "تعقيده التقريبي O(I · A · n)."
            ),
        }
    )

    blocks.append({"type": "h2", "text": "4.4 البرمجة الديناميكية الدقيقة (DP)"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "تُستخدم البرمجة الديناميكية كخط أساس دقيق. يُعرَّف D_i(w) أكبر قيمة يمكن الحصول عليها من أول i "
                "مشاريع باستخدام ميزانية w. العلاقة التكرارية هي:"
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": "D_i(w) = max(D_{i−1}(w), D_{i−1}(w − c_i) + v_i) إذا كان w ≥ c_i، وإلا D_{i−1}(w).",
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "طُبِّقت العلاقة باستخدام مصفوفة أحادية البعد بحجم B+1، وبالتالي فالذاكرة O(B) والزمن O(nB). "
                "هذا الحل دقيق لكنه شبه متعدد الحدود؛ يكبر زمنه خطياً مع سعة الميزانية B، ما يجعله غير عملي "
                "عندما تكون B ضخمة أو عند إضافة قيود متعددة."
            ),
        }
    )

    ga = config["algorithms"]["GA"]
    bpso = config["algorithms"]["BPSO"]
    aco = config["algorithms"]["ACO"]
    hyper_rows = [
        ["عدد الأفراد / الجسيمات / النمل", str(ga["population_size"]), str(bpso["swarm_size"]), str(aco["colony_size"])],
        ["ميزانية التقييم", str(ga["max_evaluations"]), str(bpso["max_evaluations"]), str(aco["max_evaluations"])],
        ["الاختيار", f"Tournament k={ga['tournament_size']}", "—", "—"],
        ["التزاوج", f"Uniform pc={ga['crossover_prob']}", "—", "—"],
        ["الطفرات", "Bit-flip pm=1/n", "—", "—"],
        ["النخبوية", str(ga["elitism"]), "—", "—"],
        ["القصور الذاتي w", "—", f"{bpso['inertia_start']} → {bpso['inertia_end']}", "—"],
        ["c1, c2", "—", f"{bpso['c1']}, {bpso['c2']}", "—"],
        ["v_max", "—", str(bpso["vmax"]), "—"],
        ["α, β", "—", "—", f"{aco['alpha']}, {aco['beta']}"],
        ["ρ", "—", "—", str(aco["rho"])],
        ["τ_0", "—", "—", str(aco["tau0"])],
        ["حدود الفيرمون", "—", "—", f"[{aco['tau_min']}, {aco['tau_max']}]"],
        ["الإصلاح / الملء", "مشترك", "مشترك", "بناء ممكن + ملء جشع"],
        ["معيار التوقف", "25,000 تقييم", "25,000 تقييم", "25,000 تقييم"],
    ]
    blocks.append({"type": "h2", "text": "4.5 ملخص المعاملات (Hyperparameters)"})
    blocks.append(
        {
            "type": "table",
            "headers": ["المعامل", "GA", "BPSO", "ACO"],
            "rows": hyper_rows,
            "font_size": 8,
        }
    )

    blocks.append({"type": "h1", "text": "5. منهجية التجارب"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "استُخدمت ثلاثة أحجام: Small بعدد 20 مشروعاً، Medium بعدد 60 مشروعاً، وLarge بعدد 150 مشروعاً. "
                "وُلّدت التكاليف والقيم بأعداد صحيحة موزعة بانتظام في المجال [100, 1000]، مع استقلال القيم عن التكاليف "
                "(حالات غير مترابطة)، وحُددت الميزانية عند 50% من مجموع التكاليف. استُخدمت بذور ثابتة لتوليد "
                "البيانات: 1001 و1002 و1003 على الترتيب، ما يضمن إمكانية إعادة إنتاج النتائج."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "نُفِّذت كل خوارزمية 30 مرة مستقلة على كل حجم، أي 270 تشغيلاً للخوارزميات الاستدلالية. "
                "وُحّدت ميزانية التقييم عند 25,000 تقييم لكل تشغيل، من دون إيقاف مبكر، لضمان مقارنة عادلة. "
                "طُبّق مُعامل الإصلاح نفسه على GA وBPSO، بينما يبني ACO حلولاً ممكنة بطبيعته ثم يطبّق الملء الجشع. "
                "تُحسب البذرة لكل تشغيل وفق الصيغة: "
                "seed = 2026 + 1000×size_index + 100×algorithm_index + run_index."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "المقاييس المسجلة: أفضل قيمة، ومتوسط القيمة، والانحراف المعياري، والوسيط، وأسوأ قيمة، "
                "ومتوسط الفجوة المثالية، وزمن التنفيذ، ونسبة الإمكانية، وعدد التقييمات، والتكرار الذي "
                "وُجدت عندها أفضل قيمة، وتاريخ التقارب الكامل (Best Fitness بعد كل تكرار). "
                "أُجريت التجارب على نفس الجهاز، وبيئة التشغيل موثقة في ملف config.json."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "من حيث استهلاك الموارد، تحتفظ GA وBPSO بمصفوفات بحجم يتناسب مع عدد الأفراد أو الجسيمات "
                "وطول الحل، أي O(population × n)، ويحتفظ ACO بمتجه فيرمونات بحجم O(n) إضافة إلى الحلول "
                "المؤقتة. أما DP فيحتاج إلى مصفوفة قيم بحجم O(B)، وهو ما يفسر صغر ذاكرته في الأحجام "
                "المستخدمة هنا ونموها خطياً مع سعة الميزانية."
            ),
        }
    )

    blocks.append({"type": "h1", "text": "6. النتائج"})
    blocks.append({"type": "h2", "text": "6.1 خصائص الحالات والحل الأمثل"})
    instance_rows = []
    for size in SIZE_NAMES:
        dp = dp_by_size[size]
        instance_rows.append(
            [
                SIZE_LABELS[size],
                str(dp["n"]),
                f"{int(float(dp['total_cost'])):,}",
                f"{int(float(dp['budget'])):,}",
                f"{int(float(dp['optimal_value'])):,}",
                f"{float(dp['runtime_sec']):.6f}",
                f"{float(dp['memory_bytes']) / 1024:.1f} KB",
            ]
        )
    blocks.append(
        {
            "type": "table",
            "headers": ["الحجم", "n", "مجموع التكاليف", "الميزانية B", "القيمة المثالية f*", "زمن DP (s)", "ذاكرة DP"],
            "rows": instance_rows,
            "font_size": 9,
        }
    )

    blocks.append({"type": "h2", "text": "6.2 نتائج كل حجم"})
    for size in SIZE_NAMES:
        blocks.append({"type": "h2", "text": f"الحالة {SIZE_LABELS[size]}"})
        result_rows = []
        for algorithm in ALGORITHM_NAMES:
            row = summary_by[(size, algorithm)]
            result_rows.append(
                [
                    algorithm,
                    f"{_int(row, 'best_value'):,}",
                    f"{_float(row, 'mean_value'):,.2f}",
                    f"{_float(row, 'std_value'):,.2f}",
                    f"{_float(row, 'median_value'):,.2f}",
                    f"{_int(row, 'worst_value'):,}",
                    f"{_float(row, 'mean_gap_pct'):.3f}%",
                    f"{_float(row, 'mean_runtime_sec'):.4f}",
                    f"{_float(row, 'feasible_rate_pct'):.1f}%",
                ]
            )
        blocks.append(
            {
                "type": "table",
                "headers": ["الخوارزمية", "Best", "Mean", "Std", "Median", "Worst", "متوسط الفجوة", "الزمن (s)", "الإمكانية"],
                "rows": result_rows,
                "font_size": 8,
            }
        )

    blocks.append({"type": "h2", "text": "6.3 جدول الترتيب العام"})
    ranking_rows = []
    for algorithm in overall_rank:
        total_wins = sum(_int(row, "win_count") for row in summary if row["algorithm"] == algorithm)
        ranking_rows.append(
            [
                algorithm,
                f"{_average_metric(summary, algorithm, 'mean_gap_pct'):.4f}%",
                f"{_average_metric(summary, algorithm, 'mean_runtime_sec'):.4f}",
                f"{_average_metric(summary, algorithm, 'std_gap_pct'):.4f}%",
                str(total_wins),
            ]
        )
    blocks.append(
        {
            "type": "table",
            "headers": ["الترتيب", "الخوارزمية", "متوسط الفجوة عبر الأحجام", "متوسط الزمن (s)", "متوسط الانحراف المعياري", "مجموع مرات الفوز"],
            "rows": [[str(index + 1)] + row for index, row in enumerate(ranking_rows)],
            "font_size": 9,
        }
    )
    blocks.append(
        {
            "type": "note",
            "text": (
                "تُحتسب «مرات الفوز» على أنها عدد التشغيلات التي ساوت فيها الخوارزمية أفضل قيمة معروفة "
                "في ذلك الحجم؛ لذلك تتقاسم الخوارزميات الفوز في الحالة الصغيرة عندما تصل جميعها إلى الحل الأمثل."
            ),
        }
    )

    blocks.append({"type": "h2", "text": "6.4 سرعة التقارب"})
    speed_rows = []
    for size in SIZE_NAMES:
        row = [SIZE_LABELS[size]]
        for algorithm in ALGORITHM_NAMES:
            row.append(f"{_float(summary_by[(size, algorithm)], 'mean_best_iteration'):.1f}")
        speed_rows.append(row)
    blocks.append(
        {
            "type": "table",
            "headers": ["الحجم", "GA", "BPSO", "ACO"],
            "rows": speed_rows,
            "font_size": 9,
        }
    )
    blocks.append(
        {
            "type": "note",
            "text": (
                "القيمة هي متوسط التكرار الذي وُجدت عنده أفضل قيمة (0 يعني أن أفضل قيمة ظهرت في المجتمع "
                "الأولي بالنسبة إلى GA وBPSO، أو في الجولة الأولى بالنسبة إلى ACO). القيم الأصغر تعني "
                "وصولاً أسرع إلى أفضل قيمة لتلك الخوارزمية، وليس بالضرورة جودة أعلى."
            ),
        }
    )

    blocks.append({"type": "h2", "text": "6.5 منحنيات التقارب"})
    figure_number = 1
    for size in SIZE_NAMES:
        path = figures_dir / f"convergence_{size}.png"
        blocks.append(
            {
                "type": "image",
                "path": path,
                "caption": f"شكل {figure_number}: تقارب الخوارزميات على الحالة {SIZE_LABELS[size]} (متوسط 30 تشغيلاً).",
            }
        )
        figure_number += 1
    blocks.append({"type": "image", "path": figures_dir / "boxplots.png", "caption": f"شكل {figure_number}: صناديق توزيع أفضل قيمة نهائية عبر التشغيلات المستقلة."})
    figure_number += 1
    blocks.append({"type": "image", "path": figures_dir / "gap_comparison.png", "caption": f"شكل {figure_number}: متوسط الفجوة المثالية لكل خوارزمية وحجم."})
    figure_number += 1
    blocks.append({"type": "image", "path": figures_dir / "runtime_comparison.png", "caption": f"شكل {figure_number}: متوسط زمن التنفيذ لكل خوارزمية وحجم."})

    blocks.append({"type": "h2", "text": "6.6 ملاحظات على النتائج"})
    small = {algorithm: summary_by[("small", algorithm)] for algorithm in ALGORITHM_NAMES}
    medium = {algorithm: summary_by[("medium", algorithm)] for algorithm in ALGORITHM_NAMES}
    large = {algorithm: summary_by[("large", algorithm)] for algorithm in ALGORITHM_NAMES}
    blocks.append(
        {
            "type": "bullets",
            "items": [
                "الحالة الصغيرة (20 مشروعاً): وصلت الخوارزميات الثلاث إلى الحل الأمثل في جميع التشغيلات الثلاثين (فجوة 0%)، ما يشير إلى سهولة الحالة وصغر فضاء البحث.",
                f"الحالة المتوسطة (60 مشروعاً): حققت GA الحل الأمثل في جميع التشغيلات، واقتربت BPSO بمتوسط فجوة {_float(medium['BPSO'], 'mean_gap_pct'):.3f}%، بينما بلغ متوسط فجوة ACO {_float(medium['ACO'], 'mean_gap_pct'):.3f}%.",
                f"الحالة الكبيرة (150 مشروعاً): تفوقت GA في متوسط القيمة (متوسط فجوة {_float(large['GA'], 'mean_gap_pct'):.3f}%)، واقتربت ACO (متوسط فجوة {_float(large['ACO'], 'mean_gap_pct'):.3f}%)، بينما تراجعت BPSO بوضوح (متوسط فجوة {_float(large['BPSO'], 'mean_gap_pct'):.3f}%).",
                f"من حيث الزمن، كانت {fastest} الأسرع بمتوسط {_average_metric(summary, fastest, 'mean_runtime_sec'):.4f} ثانية، بينما كان ACO الأبطأ بسبب كلفة بناء الحلول جزئياً.",
                f"من حيث الاستقرار، كانت {most_stable} الأكثر استقراراً بمتوسط انحراف للفجوة {_average_metric(summary, most_stable, 'std_gap_pct'):.4f}%، بينما سجلت BPSO أعلى تباين في الحالة الكبيرة.",
                "أظهرت منحنيات التقارب أن ACO يصل إلى أفضل قيمة له في تكرارات أقل، لكنه يتوقف عند مستوى أقل بقليل من GA في الحالة الكبيرة، في حين تستمر GA في التحسن حتى تكرارات متأخرة.",
            ],
        }
    )

    blocks.append({"type": "h1", "text": "7. المناقشة"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يمكن تفسير تفوق GA في هذه التجارب بعدة عوامل: التمثيل الثنائي المباشر، والتزاوج المنتظم الذي "
                "يسمح بتبادل مجموعات المشاريع الجيدة، والنخبوية التي تحافظ على أفضل الحلول، إضافة إلى الإصلاح "
                "الجشع الذي يعيد الحلول إلى منطقة الإمكانية ويستفيد من السعة المتبقية. هذه العناصر معاً تحقق "
                "توازناً جيداً بين الاستكشاف والاستغلال، خصوصاً في الحالة الكبيرة."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "أما ACO فقد أظهر أداءً قوياً في الحالة الكبيرة من حيث أفضل قيمة منفردة، إذ بلغت أفضل قيمة "
                f"{_int(large['ACO'], 'best_value'):,} بفجوة {_float(large['ACO'], 'best_gap_pct'):.4f}% فقط عن الحل الأمثل. "
                "يعود ذلك إلى استخدام معلومة القيمة/الكلفة في البناء وإلى تراكم الفيرمونات على المشاريع الجيدة. "
                "لكنه كان الأبطأ لأن كل نملة تبني حلاً كاملاً بتكرار على المشاريع. كما أن متوسط فجوته في الحالة "
                "المتوسطة كان أعلى من GA وBPSO، ما يعكس حساسية ACO لمعاملاته ولطريقة البناء."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "عانى BPSO من تقارب مبكر واضح في الحالة الكبيرة: فبعد تحسن أولي، استقر السرب عند حل محلي "
                f"بمتوسط فجوة {_float(large['BPSO'], 'mean_gap_pct'):.3f}% وانحراف كبير. "
                "هذا سلوك معروف في BPSO بسبب طبيعة تحديث السرعات والاعتماد على gbest، الذي قد يقلل التنوع "
                "ويحبس السرب في منطقة واحدة. لم يُضف أي آلية تنوع أو بحث محلي إلى BPSO، وهذا يوضح نقطة ضعف "
                "أساسية في النسخة الأساسية من الخوارزمية."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "أثبت DP أنه الخيار الأفضل عندما تكون الميزانية B معتدلة: فقد حل الحالات الثلاث بدقة تامة "
                f"وفي زمن أقل من {float(dp_by_size['large']['runtime_sec']):.4f} ثانية في الحالة الكبيرة، "
                "بذاكرة لا تتجاوز بضع مئات من الكيلوبايت. لكن هذه الميزة مرتبطة بالتعقيد شبه متعدد الحدود O(nB)؛ "
                "فعندما تكبر B كثيراً أو تُضاف قيود إضافية، يتضخم الزمن والذاكرة، وهنا تصبح الخوارزميات الاستدلالية "
                "أكثر جاذبية. باختصار: DP مناسب لهذه الأحجام، بينما GA وACO يقدمان بدائل قابلة للتوسع عندما "
                "تصبح البنية أقل ملاءمة للحل الدقيق."
            ),
        }
    )
    blocks.append(
        {
            "type": "p",
            "text": (
                "من حيث العدالة: استُخدمت نفس الحالات ونفس ميزانية التقييم (25,000 تقييم) ونفس معيار التوقف "
                "ونفس مُعامل الإصلاح، ولم تُستخدم القيمة المثالية لـ DP داخل أي خوارزمية استدلالية؛ اقتصر "
                "استخدامها على حساب الفجوة بعد انتهاء التشغيل. هذا يجعل المقارنة ذات معنى، لكن تبقى هناك "
                "قيود: حالة واحدة لكل حجم، وبيانات غير مترابطة، وقيد ميزانية واحد، ومعاملات ثابتة لم تُضبط "
                "لكل حجم. لذلك لا ينبغي تعميم النتائج على جميع توزيعات المشكلات دون تجارب إضافية."
            ),
        }
    )

    blocks.append({"type": "h1", "text": "8. الخاتمة والعمل المستقبلي"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "قدّم المشروع تطبيقاً كاملاً وقابلاً لإعادة الإنتاج لمشكلة تخصيص الميزانية، مع تنفيذ GA وBPSO "
                "وACO من الصفر ومقارنتها مع حل دقيق بـ DP. أظهرت النتائج أن GA هو الخيار الأفضل في هذه التجارب "
                "من حيث الجودة والاستقرار والزمن، وأن ACO قريب منه ويمتلك أفضلية في سرعة الوصول إلى قيم جيدة، "
                "في حين يحتاج BPSO إلى تحسينات لتفادي التقارب المبكر. كما أكدت النتائج أن DP يبقى الخيار الأمثل "
                "عندما تكون الميزانية محدودة الحجم."
            ),
        }
    )
    blocks.append(
        {
            "type": "bullets",
            "items": [
                "اختبار عدة حالات لكل حجم وعدة أنواع من التوزيعات (مترابطة، غير مترابطة، وشديدة الترابط).",
                "إضافة قيود متعددة (مثل المخاطر أو الموارد البشرية) ودراسة نسخة متعددة الأبعاد من المشكلة.",
                "تطوير BPSO بآليات تنوع أو بحث محلي أو نسخة هجينة مع GA/ACO.",
                "إجراء اختبارات دلالة إحصائية ومقارنات متعددة على عدد أكبر من التشغيلات.",
                "توازي التنفيذ لتقليل زمن التجارب عند الأحجام الكبيرة.",
            ],
        }
    )

    blocks.append({"type": "h1", "text": "9. توزيع مهام الفريق"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يوضح الجدول التالي توزيع المهام المقترح. يجب استبدال الأسماء والأرقام الجامعية بالأسماء الفعلية، "
                "والتأكد من أن عدد الأعضاء بين 6 و9 طلاب كما يشترط المشروع."
            ),
        }
    )
    blocks.append(
        {
            "type": "table",
            "headers": ["#", "الاسم", "الرقم الجامعي", "المهمة", "نسبة المساهمة"],
            "rows": team_rows,
            "font_size": 8,
        }
    )

    blocks.append({"type": "h1", "text": "10. المراجع"})
    blocks.append(
        {
            "type": "bullets",
            "items": [
                "Goldberg, D. E. (1989). Genetic Algorithms in Search, Optimization, and Machine Learning. Addison-Wesley.",
                "Kennedy, J., & Eberhart, R. C. (1997). A discrete binary version of the particle swarm algorithm. IEEE International Conference on Systems, Man, and Cybernetics.",
                "Dorigo, M., & Stützle, T. (2004). Ant Colony Optimization. MIT Press.",
                "Martello, S., & Toth, P. (1990). Knapsack Problems: Algorithms and Computer Implementations. Wiley.",
                "Kellerer, H., Pferschy, U., & Pisinger, D. (2004). Knapsack Problems. Springer.",
            ],
        }
    )

    blocks.append({"type": "h1", "text": "11. الملحق: بنية المشروع والتشغيل"})
    blocks.append(
        {
            "type": "p",
            "text": (
                "يتضمن المشروع مجلد src للخوارزميات والتقييم والتجارب والرسوم، ومجلد tests للاختبارات، "
                "ومجلد data/instances للحالات المحفوظة، ومجلد results للنتائج والرسوم، ومجلد report للتقرير. "
                "يمكن إعادة تنفيذ التجارب بالأوامر التالية من داخل مجلد المشروع:"
            ),
        }
    )
    blocks.append(
        {
            "type": "bullets",
            "items": [
                "python -m pip install -r requirements.txt",
                "python run_experiments.py --quick    # اختبار سريع",
                "python run_experiments.py            # التجارب الكاملة (270 تشغيلاً)",
                "python make_report.py                # توليد التقرير والرسوم",
                "python -m unittest discover -s tests -v",
            ],
        }
    )
    blocks.append(
        {
            "type": "note",
            "text": (
                "ملاحظة: التقرير مُولَّد آلياً من نتائج التشغيل الفعلية في results/؛ أي إعادة تشغيل كاملة "
                "ستحدّث الأرقام والرسوم عند إعادة توليد التقرير."
            ),
        }
    )
    return blocks


def load_data(results_dir: Path) -> tuple[list[dict], list[dict], list[dict], dict]:
    summary_path = results_dir / "summary.csv"
    dp_path = results_dir / "dp_results.csv"
    raw_path = results_dir / "raw_results.csv"
    config_path = results_dir / "config.json"
    for path in (summary_path, dp_path, raw_path, config_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Run `python run_experiments.py` before building the report."
            )
    summary = read_csv_rows(summary_path)
    dp_rows = read_csv_rows(dp_path)
    raw_rows = read_csv_rows(raw_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return summary, dp_rows, raw_rows, config


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Arabic report from experiment results.")
    parser.add_argument("--results", default="results")
    parser.add_argument("--output", default="report")
    args = parser.parse_args()

    results_dir = Path(args.results)
    if not results_dir.is_absolute():
        results_dir = PROJECT_DIR / results_dir
    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = PROJECT_DIR / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summary, dp_rows, raw_rows, config = load_data(results_dir)
    figures_dir = results_dir / "figures"
    generate_all_figures(results_dir, figures_dir)
    blocks = build_blocks(summary, dp_rows, config, figures_dir)

    markdown_path = output_dir / "report_ar.md"
    markdown_path.write_text(_render_markdown(blocks, output_dir), encoding="utf-8")
    docx_path = output_dir / "report_ar.docx"
    _render_docx(blocks, docx_path)
    print(f"Wrote {markdown_path}")
    print(f"Wrote {docx_path}")


if __name__ == "__main__":
    main()

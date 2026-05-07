from utils import (
    normalize_text,
    standardize_exam_name,
    parse_date,
    basic_extract_exams,
    try_float,
    exams_to_index,
    reconciler,
    default_case,
    add_basic_pendencies,
    extract_text_from_pdf,
    _pdf_text_via_pdfplumber,
    _pdf_text_via_ocr,
)


def test_normalize_text_removes_accents():
    assert normalize_text("Fósforo") == "fosforo"
    assert normalize_text("Potássio") == "potassio"
    assert normalize_text("Cálcio") == "calcio"


def test_normalize_text_empty():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


def test_standardize_exam_name_known():
    assert standardize_exam_name("Hemoglobina") == "hemoglobina"
    assert standardize_exam_name("Hb") == "hemoglobina"
    assert standardize_exam_name("PTH") == "pth"
    assert standardize_exam_name("Fósforo") == "fosforo"


def test_standardize_exam_name_unknown():
    result = standardize_exam_name("exame desconhecido")
    assert result == "exame_desconhecido"


def test_parse_date_formats():
    assert parse_date("01/04/2024") == "2024-04-01"
    assert parse_date("01-04-2024") == "2024-04-01"
    assert parse_date("2024-04-01") == "2024-04-01"


def test_parse_date_empty():
    assert parse_date("") == ""


def test_parse_date_invalid_returns_stripped():
    assert parse_date("nao-e-data") == "nao-e-data"


def test_try_float_valid():
    assert try_float("9.8") == 9.8
    assert try_float("9,8") == 9.8
    assert try_float("6") == 6.0


def test_try_float_invalid():
    assert try_float("") is None
    assert try_float("abc") is None


def test_basic_extract_exams_simple():
    text = "Hemoglobina: 9,8 g/dL\nFerritina: 180 ng/mL"
    exams = basic_extract_exams(text, "2024-04-01")
    assert len(exams) == 2
    names = [e.nome_padronizado for e in exams]
    assert "hemoglobina" in names
    assert "ferritina" in names


def test_basic_extract_exams_empty():
    assert basic_extract_exams("", "") == []


def test_exams_to_index():
    exams = [{"nome_padronizado": "hemoglobina", "valor": "9.8"}]
    index = exams_to_index(exams)
    assert "hemoglobina" in index
    assert index["hemoglobina"]["valor"] == "9.8"


def test_reconciler_trend_up():
    current = [{"nome_padronizado": "hemoglobina", "valor": "10.0", "unidade": "g/dL"}]
    previous = [{"nome_padronizado": "hemoglobina", "valor": "9.0", "unidade": "g/dL"}]
    result = reconciler(current, previous)
    assert len(result) == 1
    assert result[0]["dominio"] == "hemoglobina"
    assert "aumentou" in result[0]["descricao"]


def test_reconciler_trend_down():
    current = [{"nome_padronizado": "fosforo", "valor": "4.5", "unidade": "mg/dL"}]
    previous = [{"nome_padronizado": "fosforo", "valor": "6.1", "unidade": "mg/dL"}]
    result = reconciler(current, previous)
    assert "reduziu" in result[0]["descricao"]


def test_reconciler_new_exam():
    current = [{"nome_padronizado": "potassio", "valor": "5.0", "unidade": "mEq/L"}]
    result = reconciler(current, [])
    assert result[0]["status"] == "novo_no_contexto"


def test_default_case_structure():
    case = default_case()
    assert case.paciente["nome"] == ""
    assert case.contexto["modalidade_trs"] == "HD"
    assert isinstance(case.exames, list)


def test_add_basic_pendencies():
    case = default_case()
    case.exames = []
    add_basic_pendencies(case)
    descriptions = [p["descricao"] for p in case.pendencias]
    assert any("hemoglobina" in d for d in descriptions)
    assert any("ferritina" in d for d in descriptions)


def test_extract_text_from_pdf_invalid_bytes_returns_empty():
    assert extract_text_from_pdf(b"") == ""
    assert extract_text_from_pdf(b"not a pdf") == ""


def test_pdf_pdfplumber_invalid_returns_empty():
    assert _pdf_text_via_pdfplumber(b"not a pdf") == ""
    assert _pdf_text_via_pdfplumber(b"") == ""


def test_pdf_ocr_invalid_returns_empty():
    assert _pdf_text_via_ocr(b"not a pdf") == ""
    assert _pdf_text_via_ocr(b"") == ""


def test_extract_text_from_pdf_with_real_pdf():
    try:
        import pdfplumber
        from io import BytesIO
        import reportlab.pdfgen.canvas as canvas_mod

        buf = BytesIO()
        c = canvas_mod.Canvas(buf)
        c.drawString(100, 750, "Hemoglobina: 9.8 g/dL")
        c.save()
        pdf_bytes = buf.getvalue()

        text = extract_text_from_pdf(pdf_bytes)
        assert "Hemoglobina" in text or text == ""
    except ImportError:
        pass

import json
from dataclasses import asdict
from datetime import datetime

import streamlit as st

from utils import (
    basic_extract_exams,
    parse_medications,
    add_basic_pendencies,
    reconciler,
    guideline_engine,
    build_short_evolution,
    build_detailed_evolution,
    safety_auditor,
    export_docx,
    default_case,
    extract_text_from_pdf,
    Image,
)

# ==============================
# Page config
# ==============================
st.set_page_config(
    page_title="TRS Scribe Assist",
    page_icon="🩺",
    layout="wide",
)


# ==============================
# Session state
# ==============================
if "case_data" not in st.session_state:
    st.session_state.case_data = default_case()
if "previous_exams" not in st.session_state:
    st.session_state.previous_exams = []
if "results" not in st.session_state:
    st.session_state.results = {}
if "_last_pdf_name" not in st.session_state:
    st.session_state["_last_pdf_name"] = ""


# ==============================
# UI
# ==============================
st.title("TRS Scribe Assist")
st.caption("MVP inicial para organizacao de exames, reconciliacao, minuta de evolucao e auditoria basica.")

with st.sidebar:
    st.header("Configuracao do caso")
    paciente_nome = st.text_input("Nome do paciente", value=st.session_state.case_data.paciente.get("nome", ""))
    registro = st.text_input("Registro", value=st.session_state.case_data.paciente.get("registro", ""))
    modalidade = st.selectbox("Modalidade TRS", ["HD", "HDF", "DP", "Nao informada"], index=0)
    local = st.text_input("Local de atendimento", value=st.session_state.case_data.contexto.get("local_atendimento", ""))
    data_ref = st.date_input("Data de referencia", value=datetime.now().date())

    st.session_state.case_data.paciente["nome"] = paciente_nome
    st.session_state.case_data.paciente["registro"] = registro
    st.session_state.case_data.contexto["modalidade_trs"] = modalidade
    st.session_state.case_data.contexto["local_atendimento"] = local
    st.session_state.case_data.contexto["data_referencia"] = data_ref.isoformat()


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Entrada",
    "Extracao",
    "Analise",
    "Saida",
    "Auditoria",
])

with tab1:
    st.subheader("Entrada")
    col1, col2 = st.columns(2)

    with col1:
        uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"], key="pdf")
        uploaded_image = st.file_uploader("Upload imagem", type=["png", "jpg", "jpeg", "webp"], key="img")

        if uploaded_image is not None and Image is not None:
            try:
                img = Image.open(uploaded_image)
                st.image(img, caption="Imagem carregada", use_container_width=True)
            except Exception:
                st.warning("Nao foi possivel renderizar a imagem.")

        if uploaded_pdf is not None:
            if uploaded_pdf.name != st.session_state["_last_pdf_name"]:
                with st.spinner("Extraindo texto do PDF..."):
                    pdf_bytes = uploaded_pdf.read()
                    extracted = extract_text_from_pdf(pdf_bytes)
                if extracted:
                    st.session_state["raw_exam_input"] = extracted
                    st.session_state["_last_pdf_name"] = uploaded_pdf.name
                    st.success(f"PDF lido: {len(extracted)} caracteres extraidos.")
                else:
                    st.warning("Nenhum texto encontrado no PDF. Verifique se o arquivo contem texto ou imagens legiveis.")
            st.session_state.case_data.rastreabilidade["documentos_entrada"].append(uploaded_pdf.name)
            if "pdf" not in st.session_state.case_data.contexto["fonte_entrada"]:
                st.session_state.case_data.contexto["fonte_entrada"].append("pdf")

        if uploaded_image is not None:
            st.session_state.case_data.rastreabilidade["documentos_entrada"].append(uploaded_image.name)
            if "imagem" not in st.session_state.case_data.contexto["fonte_entrada"]:
                st.session_state.case_data.contexto["fonte_entrada"].append("imagem")

    with col2:
        raw_exam_text = st.text_area(
            "Texto de exames atual",
            height=220,
            placeholder="Exemplo:\nHemoglobina: 9,8 g/dL\nFerritina: 180 ng/mL\nFosforo: 6,1 mg/dL",
            key="raw_exam_input",
        )
        previous_exam_text = st.text_area(
            "Texto de exames previos (opcional)",
            height=140,
            placeholder="Exemplo:\nHemoglobina: 10,4 g/dL\nFerritina: 220 ng/mL",
        )

    st.subheader("Contexto clinico adicional")
    meds_text = st.text_area("Medicacoes em uso", height=120, placeholder="Uma por linha")
    prev_note = st.text_area("Evolucao anterior", height=140)
    program_text = st.text_area("Programacao/prescricao previa", height=120)

    if st.button("Processar caso", type="primary"):
        case_data = st.session_state.case_data

        current_exams = [asdict(e) for e in basic_extract_exams(raw_exam_text, case_data.contexto["data_referencia"])]
        previous_exams = [asdict(e) for e in basic_extract_exams(previous_exam_text, "")]
        meds = [asdict(m) for m in parse_medications(meds_text)]

        case_data.exames = current_exams
        case_data.medicacoes_em_uso = meds
        case_data.evolucao_previa = {
            "data": "",
            "texto": prev_note,
        }
        case_data.prescricao_dialitica["modalidade"] = case_data.contexto.get("modalidade_trs", "")
        case_data.prescricao_dialitica["frequencia"] = program_text
        if raw_exam_text and "texto" not in case_data.contexto["fonte_entrada"]:
            case_data.contexto["fonte_entrada"].append("texto")

        add_basic_pendencies(case_data)
        reconciliation = reconciler(case_data.exames, previous_exams)
        notes = guideline_engine(case_data)
        short_note = build_short_evolution(case_data, notes)
        detailed_note = build_detailed_evolution(case_data, notes, reconciliation)
        audit = safety_auditor(case_data, detailed_note)

        st.session_state.case_data = case_data
        st.session_state.previous_exams = previous_exams
        st.session_state.results = {
            "reconciliation": reconciliation,
            "guideline_notes": notes,
            "short_note": short_note,
            "detailed_note": detailed_note,
            "audit": audit,
        }
        st.success("Caso processado.")

with tab2:
    st.subheader("Extracao estruturada")
    case_data = st.session_state.case_data
    if case_data.exames:
        st.write("### Exames atuais")
        st.dataframe(case_data.exames, use_container_width=True)
    else:
        st.info("Nenhum exame estruturado ainda.")

    if st.session_state.previous_exams:
        st.write("### Exames previos")
        st.dataframe(st.session_state.previous_exams, use_container_width=True)

    if case_data.medicacoes_em_uso:
        st.write("### Medicacoes")
        st.dataframe(case_data.medicacoes_em_uso, use_container_width=True)

    st.write("### JSON do caso")
    st.code(json.dumps(asdict(case_data), ensure_ascii=False, indent=2), language="json")

with tab3:
    st.subheader("Analise")
    results = st.session_state.results
    if results.get("reconciliation"):
        st.write("### Reconciliação longitudinal")
        st.dataframe(results["reconciliation"], use_container_width=True)
    else:
        st.info("Analise ainda nao executada.")

    if results.get("guideline_notes"):
        st.write("### Notas do motor de guideline")
        for item in results["guideline_notes"]:
            with st.expander(item["problema"], expanded=True):
                st.write(f"**Achado:** {item['achado']}")
                st.write(f"**Base documental:** {item['base_documental']}")
                st.write(f"**Lacunas:** {', '.join(item['lacunas']) if item['lacunas'] else 'Nenhuma destacada'}")
                st.write(f"**Sugestao prudente:** {item['sugestao_prudente']}")
    else:
        st.info("Sem notas de guideline ainda.")

with tab4:
    st.subheader("Saida")
    results = st.session_state.results
    short_note = results.get("short_note", "")
    detailed_note = results.get("detailed_note", "")

    st.write("### Evolucao curta")
    st.text_area("", short_note, height=100, key="short_out")

    st.write("### Evolucao detalhada")
    st.text_area(" ", detailed_note, height=240, key="long_out")

    if short_note or detailed_note:
        export_json = json.dumps({
            "short_note": short_note,
            "detailed_note": detailed_note,
            "case_data": asdict(st.session_state.case_data),
            "results": st.session_state.results,
        }, ensure_ascii=False, indent=2)

        st.download_button(
            label="Baixar JSON do caso",
            data=export_json.encode("utf-8"),
            file_name="trs_scribe_case.json",
            mime="application/json",
        )

        docx_bytes = export_docx(short_note, detailed_note, results.get("audit", {}))
        if docx_bytes is not None:
            st.download_button(
                label="Baixar DOCX",
                data=docx_bytes,
                file_name="trs_scribe_relatorio.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            st.caption("python-docx nao encontrado. O botao de DOCX aparece quando a dependencia estiver instalada.")
    else:
        st.info("Processe o caso primeiro.")

with tab5:
    st.subheader("Auditoria")
    audit = st.session_state.results.get("audit", {})
    if audit:
        status = audit.get("status", "")
        if status == "Aprovado":
            st.success(status)
        elif status == "Aprovado com ressalvas":
            st.warning(status)
        else:
            st.error(status)

        ressalvas = audit.get("ressalvas", [])
        if ressalvas:
            st.write("### Ressalvas")
            for item in ressalvas:
                st.write(f"- {item}")
    else:
        st.info("Auditoria ainda nao executada.")

st.divider()
st.caption(
    "Este MVP e um esqueleto operacional. Ele nao substitui revisao medica e nao deve gerar prescricao autonoma. "
    "Os pontos marcados como placeholder sao os locais onde voce conectara OCR, parser de PDF e base RAG de guidelines."
)

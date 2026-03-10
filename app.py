# app.py
import streamlit as st
from collections import defaultdict, Counter
import unicodedata

try:
    import regex as re
    HAS_REGEX = True
except Exception:
    import re
    HAS_REGEX = False


st.set_page_config(page_title="Contador de Dracoins", layout="centered")
st.title("🪙 Contador de Dracoins")

st.markdown("### Formato de entrada")
st.code(
"""Dinámica Ejemplo          <- nombre (opcional)

1. 🥇🥈🥉🏅
🎖️(🏵️🎗️)🐾🌸

2. 🐽🐝(🐶🐭)🕷
(👑🐺)🥋🪅(🎈🪼)
> DOBLES

3. 🥥☣️🦄🐞
🐱🐼🧟‍♂️🌹🍧
> TRIPLES

- Primera línea de cada ronda: top 4
- Segunda línea: todos los demás
- Tercera línea (opcional): > DOBLES o > TRIPLES
- Paréntesis = ese conjunto es 1 solo participante""",
    language="text"
)

st.divider()

PUNTOS_TOP4 = [30, 25, 20, 15]
PUNTOS_OTROS = 10

INVISIBLE_CODEPOINTS = {
    0x2060, 0x200B, 0xFEFF, 0x200E, 0x200F,
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
}


def normalize_participant(token):
    if not token:
        return token
    return "".join(ch for ch in token if ord(ch) not in INVISIBLE_CODEPOINTS)


def is_invisible_cluster(g):
    if not g:
        return True
    for ch in g:
        cat = unicodedata.category(ch)
        if cat.startswith(("L", "N", "S", "P")):
            return False
    return True


def graphemes(s):
    if not s:
        return []
    if HAS_REGEX:
        return re.findall(r"\X", s)
    return list(s)


def parse_participants_from_line(line):
    if not line:
        return []
    s = line.strip()
    if re.match(r"^\s*\d+\s*\.", s):
        _, s = s.split(".", 1)
        s = s.strip()
    participants = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            j = s.find(")", i + 1)
            if j == -1:
                rest = s[i:].replace(" ", "")
                for g in graphemes(rest):
                    g = normalize_participant(g)
                    if g and not is_invisible_cluster(g):
                        participants.append(g)
                break
            inside = normalize_participant(s[i + 1:j].replace(" ", "").strip())
            if inside and not is_invisible_cluster(inside):
                participants.append(inside)
            i = j + 1
            continue
        if HAS_REGEX:
            m = re.match(r"\X", s[i:])
            g = normalize_participant(m.group(0))
            if g and not is_invisible_cluster(g):
                participants.append(g)
            i += len(m.group(0))
        else:
            cat = unicodedata.category(ch)
            if not ch.isspace() and not cat.startswith(("C", "Z")):
                ch_norm = normalize_participant(ch)
                if ch_norm:
                    participants.append(ch_norm)
            i += 1
    participants = [normalize_participant(p) for p in participants]
    return [p for p in participants if p and p != "."]


def detect_multiplier(text):
    t = text.upper()
    if any(k in t for k in ["TRIPLE", "TRIPLES", "X3", "*3"]):
        return 3
    if any(k in t for k in ["DOBLE", "DOBLES", "X2", "*2"]):
        return 2
    return 1


def is_round_start_line(line):
    return bool(re.match(r"^\s*\d+\s*[\.\-\)]\s*", line))


def is_meta_line(line):
    s = line.strip()
    if s.startswith((">", "-", "*", "•")):
        return True
    upper = s.upper()
    return any(kw in upper for kw in ["DOBLE", "TRIPLE", "NORMAL"])


def parse_full_input(raw):
    raw = normalize_participant(raw or "")
    non_empty = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not non_empty:
        return "", []

    nombre = ""
    start_idx = 0
    if not is_round_start_line(non_empty[0]):
        nombre = non_empty[0]
        start_idx = 1

    blocks = []
    current_block = None
    for line in non_empty[start_idx:]:
        if is_round_start_line(line):
            if current_block is not None:
                blocks.append(current_block)
            current_block = [line]
        else:
            if current_block is None:
                continue
            current_block.append(line)
    if current_block is not None:
        blocks.append(current_block)

    rondas = []
    for block in blocks:
        if not block:
            continue
        line1 = block[0]
        line2 = ""
        extra_lines = []
        mult_auto = 1

        emoji_lines, meta_lines = [], []
        for ln in block[1:]:
            (meta_lines if is_meta_line(ln) else emoji_lines).append(ln)

        if emoji_lines:
            line2 = emoji_lines[0]
            extra_lines = emoji_lines[1:] + meta_lines
        else:
            extra_lines = meta_lines

        for ln in block:
            m = detect_multiplier(ln)
            if m > 1:
                mult_auto = m
                break

        m_num = re.match(r"^\s*(\d+)\s*[\.\-\)]", line1)
        num = int(m_num.group(1)) if m_num else len(rondas) + 1

        rondas.append({
            "num": num, "line1": line1, "line2": line2,
            "mult_auto": mult_auto, "extra_lines": extra_lines,
        })
    return nombre, rondas


def compute_round_scores(line1, line2, multiplier):
    top4 = parse_participants_from_line(line1)
    others_raw = parse_participants_from_line(line2)
    top4_set = set(top4[:4])
    others = [p for p in others_raw if p not in top4_set]
    scores = defaultdict(int)
    for idx, p in enumerate(top4[:4]):
        scores[p] += PUNTOS_TOP4[idx] * multiplier
    for p in others:
        scores[p] += PUNTOS_OTROS * multiplier
    return dict(scores), top4, others, others_raw


def copy_button_html(text, btn_id):
    escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    return f"""
    <button id="{btn_id}" onclick="
        navigator.clipboard.writeText(`{escaped}`)
          .then(() => {{ this.innerText='✅ Copiado!'; setTimeout(()=>this.innerText='📋 Copiar',2000); }})
          .catch(() => {{
            var ta=document.createElement('textarea'); ta.value=`{escaped}`;
            document.body.appendChild(ta); ta.select(); document.execCommand('copy');
            document.body.removeChild(ta);
            this.innerText='✅ Copiado!'; setTimeout(()=>this.innerText='📋 Copiar',2000);
          }});
    " style="background:#5865F2;color:white;border:none;padding:7px 16px;
             border-radius:6px;cursor:pointer;font-size:13px;margin-top:2px;">
    📋 Copiar</button>
    """


# ── UI ──────────────────────────────────────────────────────────────────────

# Estado de sesión para controlar el flujo de dos pasos
if "analizado" not in st.session_state:
    st.session_state.analizado = False
if "raw_analizado" not in st.session_state:
    st.session_state.raw_analizado = ""

raw_input = st.text_area(
    "Pega aquí el mensaje completo de la dinámica",
    height=300,
    placeholder="Dinámica Ejemplo\n1. 🥇🥈🥉🏅\n🎖️🐾🌸\n2. 🐽🐝🕷\n🥋🪅\n> DOBLES",
)

# Si el texto cambia, resetear el estado analizado
if raw_input != st.session_state.raw_analizado:
    st.session_state.analizado = False

if st.button("🔍 Analizar dinámica", type="primary", use_container_width=True):
    if not raw_input.strip():
        st.warning("Pega el mensaje de la dinámica antes de analizar.")
        st.stop()
    st.session_state.analizado = True
    st.session_state.raw_analizado = raw_input

if not st.session_state.analizado:
    st.stop()

nombre_detectado, rondas_detectadas = parse_full_input(st.session_state.raw_analizado)

st.divider()
st.markdown("### Vista previa y ajustes")

col_n1, col_n2 = st.columns([1, 2])
with col_n1:
    st.markdown("**Nombre detectado:**")
with col_n2:
    nombre_final = st.text_input(
        "Nombre de la dinámica",
        value=nombre_detectado,
        label_visibility="collapsed",
        placeholder="Sin nombre detectado",
    )

if not rondas_detectadas:
    st.warning("No se detectaron rondas. Verifica el formato.")
    st.stop()

# Advertir rondas no correlativas
nums = [r["num"] for r in rondas_detectadas]
expected = list(range(nums[0], nums[0] + len(nums)))
if nums != expected:
    faltantes = sorted(set(expected) - set(nums))
    st.warning(
        f"⚠️ Los números de ronda no son correlativos. Detectados: {nums}."
        + (f" Posibles faltantes: {faltantes}." if faltantes else "")
    )

st.markdown(f"**Rondas detectadas:** {len(rondas_detectadas)}")

mult_overrides = {}
for ronda in rondas_detectadas:
    r = ronda["num"]
    auto_label = {1: "Normal", 2: "Doble", 3: "Triple"}[ronda["mult_auto"]]
    with st.expander(f"Ronda {r} — detectado: **{auto_label}**", expanded=False):
        st.caption(f"Línea top 4: `{ronda['line1']}`")
        st.caption(f"Línea otros: `{ronda['line2']}`" if ronda['line2'] else "Línea otros: *(vacía)*")
        if ronda["extra_lines"]:
            st.caption("Notas del admin: " + " | ".join(f"`{l}`" for l in ronda["extra_lines"]))
        options = ["Normal", "Doble", "Triple"]
        override = st.radio(
            f"Multiplicador ronda {r}", options=options,
            index=options.index(auto_label),
            key=f"mult_override_{r}", horizontal=True,
            help="Cambia si la detección automática fue incorrecta.",
        )
        mult_overrides[r] = {"Normal": 1, "Doble": 2, "Triple": 3}[override]

st.divider()

if st.button("🧮 Contar dinámica", type="primary"):
    nombre_uso = nombre_final.strip() or "Sin nombre"
    total_global = defaultdict(int)
    st.markdown(f"## Resultados — **{nombre_uso}**")

    for ronda in rondas_detectadas:
        r = ronda["num"]
        multiplier = mult_overrides.get(r, ronda["mult_auto"])
        line1, line2 = ronda["line1"], ronda["line2"]

        if not line2:
            st.warning(f"Ronda {r}: No se detectó la segunda línea (participantes restantes).")

        scores, top4_list, others_list, others_raw = compute_round_scores(line1, line2, multiplier)

        # Top 4 incompleto
        if len(top4_list) < 4:
            st.warning(f"Ronda {r}: Solo se detectaron **{len(top4_list)} de 4** en el top.")

        # Participantes ignorados en "otros" por ya estar en top 4
        ignored = [p for p in others_raw if p in set(top4_list[:4])]
        if ignored:
            st.info(
                f"Ronda {r}: {', '.join(ignored)} "
                f"{'aparece' if len(ignored)==1 else 'aparecen'} en top 4 y en 'otros' "
                f"— se contó solo el puntaje de top 4."
            )

        # Duplicados dentro de la misma línea
        all_dups = [p for p, c in Counter(top4_list + others_list).items() if c > 1]
        if all_dups:
            st.warning(f"Ronda {r}: Repetidos en la misma línea: {', '.join(all_dups)}")

        for p, pts in scores.items():
            total_global[p] += pts

        sorted_round = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        mult_label = {1: "x1 Normal", 2: "x2 Doble", 3: "x3 Triple"}[multiplier]

        st.markdown(f"### Ronda {r} — {mult_label}")
        if not sorted_round:
            st.info("Sin participantes detectados.")
        else:
            lines_out = "\n".join([f"{p} {pts}" for p, pts in sorted_round])
            st.code(lines_out, language="text")
            st.components.v1.html(copy_button_html(lines_out, f"btn_r{r}"), height=45)

    st.divider()
    st.markdown("## Total de toda la dinámica")
    sorted_total = sorted(total_global.items(), key=lambda x: (-x[1], x[0]))
    if not sorted_total:
        st.info("No se detectaron participantes en ninguna ronda.")
    else:
        lines_out = "\n".join([f"{p} {pts}" for p, pts in sorted_total])
        st.code(lines_out, language="text")
        st.components.v1.html(copy_button_html(lines_out, "btn_total"), height=45)

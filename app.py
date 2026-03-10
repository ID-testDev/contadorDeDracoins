# app.py
import streamlit as st
from collections import defaultdict, Counter
import unicodedata

# Intentamos usar "regex" (mejor para emojis compuestos). Si no existe, caemos a un fallback.
try:
    import regex as re  # pip install regex
    HAS_REGEX = True
except Exception:
    import re
    HAS_REGEX = False


st.set_page_config(page_title="Contador de Dracoins", layout="centered")

st.title("🪙 Contador de Dracoins")

st.markdown("### Formato de entrada")
st.code(
"""Dinámica Ejemplo          ← nombre (opcional, si la 1ra línea no empieza con número)

1. 🥇🥈🥉🏅
🎖️(🏵️🎗️)🐾🌸

2. 🐽🐝(🐶🐭)🕷
(👑🐺)🥋🪅(🎈🪼)
> DOBLES

3. 🥥☣️🦄🐞
🐱🐼🧟‍♂️🌹🍧
> TRIPLES

- Primera línea de cada ronda: top 4 (1°, 2°, 3°, 4°)
- Segunda línea: todos los demás
- Líneas con '>' son notas del admin (se usan para detectar DOBLES/TRIPLES, luego se ignoran)
- Paréntesis = ese conjunto es 1 solo participante""",
    language="text"
)

st.divider()

# ─────────────────────────────────────────────
# Constantes de puntos
# ─────────────────────────────────────────────
PUNTOS_TOP4 = [30, 25, 20, 15]
PUNTOS_OTROS = 10

# ─────────────────────────────────────────────
# Invisibles a limpiar (sin tocar ZWJ ni VS16)
# ─────────────────────────────────────────────
INVISIBLE_CODEPOINTS = {
    0x2060,  # WORD JOINER
    0x200B,  # ZERO WIDTH SPACE
    0xFEFF,  # BOM
    0x200E,  # LRM
    0x200F,  # RLM
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
}


def normalize_participant(token: str) -> str:
    if not token:
        return token
    return "".join(ch for ch in token if ord(ch) not in INVISIBLE_CODEPOINTS)


def is_invisible_cluster(g: str) -> bool:
    if not g:
        return True
    for ch in g:
        cat = unicodedata.category(ch)
        if cat.startswith(("L", "N", "S", "P")):
            return False
    return True


def graphemes(s: str):
    if not s:
        return []
    if HAS_REGEX:
        return re.findall(r"\X", s)
    return list(s)


def parse_participants_from_line(line: str):
    if not line:
        return []

    s = line.strip()

    # Quitar "N." al inicio
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
            inside = s[i + 1: j].replace(" ", "").strip()
            inside = normalize_participant(inside)
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
    participants = [p for p in participants if p and p != "."]
    return participants


def detect_multiplier_from_text(text: str) -> int:
    """Detecta si el texto menciona DOBLES o TRIPLES."""
    t = text.upper()
    if "TRIPLE" in t:
        return 3
    if "DOBLE" in t:
        return 2
    return 1


def is_round_start_line(line: str) -> bool:
    """True si la línea empieza con 'N.' (inicio de ronda)."""
    return bool(re.match(r"^\s*\d+\s*[\.\-\)]\s*", line))


def is_meta_line(line: str) -> bool:
    """
    True si la línea es una anotación/nota del admin.
    Empieza con '>', '-', '*', '•' o contiene palabras clave.
    """
    s = line.strip()
    if s.startswith((">", "-", "*", "•")):
        return True
    upper = s.upper()
    if any(kw in upper for kw in ["DOBLE", "TRIPLE", "NORMAL"]):
        return True
    return False


# ─────────────────────────────────────────────
# Parser principal: texto completo → rondas
# ─────────────────────────────────────────────
def parse_full_input(raw: str):
    """
    Parsea el bloque completo de texto y devuelve:
      - nombre: str
      - rondas: list of dict
      - warnings_global: list of str (advertencias de estructura global)
    """
    raw = normalize_participant(raw or "")
    non_empty = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    if not non_empty:
        return "", [], []

    # ¿Primera línea es nombre?
    nombre = ""
    start_idx = 0
    if non_empty and not is_round_start_line(non_empty[0]):
        nombre = non_empty[0]
        start_idx = 1

    # Agrupar en bloques por inicio de ronda
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
        mult_auto = 1

        rest = block[1:]
        emoji_lines = []

        for ln in rest:
            # Primero revisar multiplicador en TODAS las líneas (incluyendo meta)
            m = detect_multiplier_from_text(ln)
            if m > 1:
                mult_auto = m

            # Solo agregar a emoji_lines si NO es meta
            if not is_meta_line(ln):
                emoji_lines.append(ln)

        if emoji_lines:
            line2 = emoji_lines[0]
            # líneas de emojis adicionales se ignoran (raro, pero posible)

        m_num = re.match(r"^\s*(\d+)\s*[\.\-\)]", line1)
        num = int(m_num.group(1)) if m_num else len(rondas) + 1

        rondas.append({
            "num": num,
            "line1": line1,
            "line2": line2,
            "mult_auto": mult_auto,
        })

    # ── Advertencias globales de correlatividad ──
    warnings_global = []
    nums = [r["num"] for r in rondas]

    if nums:
        # Escenario A: saltos en la secuencia
        expected = list(range(nums[0], nums[0] + len(nums)))
        for exp, got in zip(expected, nums):
            if exp != got:
                # Hay un salto — detectar cuáles faltan
                break
        missing = sorted(set(expected) - set(nums))
        if missing:
            faltantes = ", ".join(str(n) for n in missing)
            warnings_global.append(f"⚠️ Parece que falta(n) la(s) ronda(s): **{faltantes}**. Verifica que pegaste el mensaje completo.")

        # Escenario B: número incorrecto según posición
        for pos, ronda in enumerate(rondas, start=nums[0]):
            if ronda["num"] != pos:
                warnings_global.append(
                    f"⚠️ La ronda en posición {pos} está numerada como **{ronda['num']}** en el texto."
                )

    return nombre, rondas, warnings_global


def compute_round_scores(line1: str, line2: str, multiplier: int):
    top4 = parse_participants_from_line(line1)
    others_raw = parse_participants_from_line(line2)

    # ✅ Ignorar en "otros" a quienes ya están en top 4
    top4_set = set(top4[:4])
    others = [p for p in others_raw if p not in top4_set]
    ignored = [p for p in others_raw if p in top4_set]

    scores = defaultdict(int)
    for idx, participant in enumerate(top4[:4]):
        scores[participant] += PUNTOS_TOP4[idx] * multiplier
    for participant in others:
        scores[participant] += PUNTOS_OTROS * multiplier

    return dict(scores), top4, others, ignored


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

raw_input = st.text_area(
    "Pega aquí el mensaje completo de la dinámica",
    height=300,
    placeholder="Dinámica Ejemplo\n1. 🥇🥈🥉🏅\n🎖️🐾🌸\n2. 🐽🐝🕷\n🥋🪅\n> DOBLES",
)

nombre_detectado, rondas_detectadas, warnings_global = parse_full_input(raw_input)

if raw_input.strip():
    st.divider()
    st.markdown("### Vista previa y ajustes")

    # Advertencias globales
    for w in warnings_global:
        st.warning(w)

    # Nombre
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
    else:
        st.markdown(f"**Rondas detectadas:** {len(rondas_detectadas)}")

        mult_overrides = {}

        for ronda in rondas_detectadas:
            r = ronda["num"]
            mult_auto = ronda["mult_auto"]
            auto_label = {1: "Normal", 2: "Doble", 3: "Triple"}[mult_auto]

            # Advertencia top 4 incompleto (preview)
            top4_preview = parse_participants_from_line(ronda["line1"])
            top4_count = len(top4_preview[:4])

            label_expander = f"Ronda {r} — {auto_label}"
            if top4_count < 4:
                label_expander += f" ⚠️ top {top4_count}/4"

            with st.expander(label_expander, expanded=False):
                st.caption(f"Línea top 4: `{ronda['line1']}`")
                st.caption(f"Línea otros: `{ronda['line2']}`" if ronda['line2'] else "Línea otros: *(vacía)*")

                options = ["Normal", "Doble", "Triple"]
                default_idx = options.index(auto_label)
                override = st.radio(
                    f"Multiplicador ronda {r}",
                    options=options,
                    index=default_idx,
                    key=f"mult_override_{r}",
                    horizontal=True,
                )
                mult_overrides[r] = 1 if override == "Normal" else (2 if override == "Doble" else 3)

        st.divider()

        if st.button("Contar dinámica", type="primary"):
            nombre_uso = nombre_final.strip() or "Sin nombre"
            total_global = defaultdict(int)

            st.markdown(f"## Resultados — **{nombre_uso}**")

            for ronda in rondas_detectadas:
                r = ronda["num"]
                multiplier = mult_overrides.get(r, ronda["mult_auto"])
                line1 = ronda["line1"]
                line2 = ronda["line2"]

                if not line2:
                    st.warning(f"Ronda {r}: No se detectó la segunda línea.")

                scores, top4_list, others_list, ignored_list = compute_round_scores(line1, line2, multiplier)

                # Advertencia top 4 incompleto
                if len(top4_list) < 4:
                    st.warning(
                        f"Ronda {r}: Solo se detectaron **{len(top4_list)}** participante(s) en el top 4 "
                        f"(se esperaban 4). Se asignaron puntos a los que hay."
                    )

                # Advertencia ignorados en "otros"
                if ignored_list:
                    st.info(
                        f"Ronda {r}: {', '.join(ignored_list)} aparecen en top 4 y en 'otros' — "
                        f"se ignoraron en la segunda línea."
                    )

                # Duplicados dentro de la misma línea
                all_participants = top4_list + others_list
                counts = Counter(all_participants)
                duplicates = [p for p, c in counts.items() if c > 1]
                if duplicates:
                    st.warning(
                        f"Ronda {r}: Participantes repetidos en la misma línea: "
                        + ", ".join(duplicates)
                    )

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

            st.divider()
            st.markdown("## Total de toda la dinámica")
            sorted_total = sorted(total_global.items(), key=lambda x: (-x[1], x[0]))

            if not sorted_total:
                st.info("No se detectaron participantes en ninguna ronda.")
            else:
                lines_out = "\n".join([f"{p} {pts}" for p, pts in sorted_total])
                st.code(lines_out, language="text")

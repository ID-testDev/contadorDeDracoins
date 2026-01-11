# app.py
import streamlit as st
from collections import defaultdict, Counter

# Intentamos usar "regex" (mejor para emojis compuestos). Si no existe, caemos a un fallback.
try:
    import regex as re  # pip install regex
    HAS_REGEX = True
except Exception:
    import re
    HAS_REGEX = False


st.set_page_config(page_title="Contador de Dracoins", layout="centered")

st.title("🪙 Contador de Dracoins")

st.markdown("### Formato de entrada (ejemplo)")
st.code(
"""7. 🐽🐝(🐶🐭)🕷
(👑🐺)🥋🪅(🎈🪼)(⭐🌸)(💫🐥)

- En la **primera línea** van los **primeros 4 lugares** (1°, 2°, 3°, 4°).
- En la **segunda línea** van **todos los demás**.
- **Paréntesis** = ese conjunto de emojis es **1 solo participante**.
- Sin paréntesis = **cada emoji** es **1 participante**.""",
    language="text"
)

st.divider()

nombre = st.text_input("Nombre de la dinámica", placeholder="Ej. Dracoins - Torneo de Enero")
num_rondas = st.number_input("¿Cuántas rondas hubo?", min_value=1, max_value=100, value=1, step=1)

PUNTOS_TOP4 = [30, 25, 20, 15]
PUNTOS_OTROS = 10


def graphemes(s: str):
    """Devuelve clusters (mejor para emojis compuestos)."""
    if not s:
        return []
    if HAS_REGEX:
        return re.findall(r"\X", s)
    # Fallback: por codepoint (puede partir algunos emojis compuestos)
    return list(s)


def parse_participants_from_line(line: str):
    """
    Parsea una línea de emojis con reglas:
    - (🐶🐭) => 1 participante "🐶🐭"
    - 🐽🐝🕷 => cada emoji = 1 participante
    - También soporta grupos pegados: (🎈🪼)(⭐🌸)
    """
    if not line:
        return []

    s = line.strip()

    # Si trae "N." al inicio, recortamos a la derecha del punto
    if "." in s:
        left, right = s.split(".", 1)
        s = right.strip()

    participants = []
    i = 0
    while i < len(s):
        ch = s[i]

        if ch.isspace():
            i += 1
            continue

        # Grupo entre paréntesis
        if ch == "(":
            j = s.find(")", i + 1)
            if j == -1:
                # Paréntesis sin cerrar: no tronamos, parseamos lo que quede como clusters
                rest = s[i:].replace(" ", "")
                participants.extend([g for g in graphemes(rest) if not g.isspace()])
                break
            inside = s[i + 1 : j].replace(" ", "").strip()
            if inside:
                participants.append(inside)
            i = j + 1
            continue

        # No paréntesis: 1 cluster = 1 participante
        if HAS_REGEX:
            m = re.match(r"\X", s[i:])
            g = m.group(0)
            if not g.isspace():
                participants.append(g)
            i += len(g)
        else:
            participants.append(ch)
            i += 1

    # Quitamos basura mínima
    participants = [p for p in participants if p and p != "."]
    return participants


def extract_round_number(first_line: str):
    """Extrae el número antes del punto: '7. ...' => 7; si no, None."""
    if not first_line:
        return None
    s = first_line.strip()
    m = re.match(r"^\s*(\d+)\s*\.", s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def normalize_lines(raw_text: str):
    """
    Devuelve:
      - lines_all: líneas no vacías (strip) en orden
      - first_two: (line1, line2) (pueden ser "" si faltan)
    """
    raw = raw_text or ""
    lines_all = [ln.strip() for ln in raw.splitlines() if ln.strip() != ""]
    line1 = lines_all[0] if len(lines_all) >= 1 else ""
    line2 = lines_all[1] if len(lines_all) >= 2 else ""
    return lines_all, (line1, line2)


def compute_round_scores(line1: str, line2: str, multiplier: int):
    top4 = parse_participants_from_line(line1)
    others = parse_participants_from_line(line2)

    scores = defaultdict(int)

    # Top 4 (solo primeros 4)
    for idx, participant in enumerate(top4[:4]):
        scores[participant] += PUNTOS_TOP4[idx] * multiplier

    # Otros (todos en 2da línea)
    for participant in others:
        scores[participant] += PUNTOS_OTROS * multiplier

    return dict(scores), top4, others


# Guardamos inputs por ronda
round_inputs = []
round_multipliers = []

st.markdown("### Captura por rondas")

for r in range(1, int(num_rondas) + 1):
    st.subheader(f"Ronda {r}")

    colA, colB = st.columns([2, 1])
    with colB:
        mult_label = st.radio(
            "Tipo de ronda",
            options=["Normal", "Doble", "Triple"],
            index=0,
            key=f"mult_{r}",
            horizontal=False
        )
        multiplier = 1 if mult_label == "Normal" else (2 if mult_label == "Doble" else 3)

    with colA:
        raw = st.text_area(
            "Pega aquí la ronda (2 líneas)",
            height=110,
            placeholder=f"""{r}. 🥇🥈🥉🏅
🎖️(🏵️🎗️)""",
            key=f"txt_{r}",
        )

    round_inputs.append(raw)
    round_multipliers.append(multiplier)

st.divider()

if st.button("Contar dinámica", type="primary"):
    if not nombre.strip():
        st.error("Ponle un nombre a la dinámica.")
        st.stop()

    total_global = defaultdict(int)

    st.markdown(f"## Resultados — **{nombre.strip()}**")

    for r in range(1, int(num_rondas) + 1):
        raw = round_inputs[r - 1]
        multiplier = round_multipliers[r - 1]

        lines_all, (line1, line2) = normalize_lines(raw)

        # ✅ Validación: exactamente 2 líneas
        if len(lines_all) != 2:
            if len(lines_all) == 0:
                st.warning(f"Ronda {r}: No hay contenido.")
            elif len(lines_all) == 1:
                st.warning(f"Ronda {r}: Solo hay **1 línea**. Deben ser **2 líneas** (top 4 y otros).")
            else:
                st.warning(
                    f"Ronda {r}: Hay **{len(lines_all)} líneas**. Deben ser **2 líneas**. "
                    f"Voy a usar **solo las primeras 2** para contar."
                )

        # Validación del número de ronda (se revisa en la 1ra línea)
        detected = extract_round_number(line1)
        if detected is None:
            st.warning(f"Ronda {r}: No encontré el número al inicio (ej. `{r}. ...`).")
        elif detected != r:
            st.warning(f"Ronda {r}: El número escrito es `{detected}.` pero debería ser `{r}.`.")

        # Conteo
        scores, top4_list, others_list = compute_round_scores(line1, line2, multiplier)

        # ✅ Duplicados (considerando ambas líneas)
        all_participants = top4_list + others_list
        counts = Counter(all_participants)
        duplicates = [p for p, c in counts.items() if c > 1]
        if duplicates:
            dup_text = ", ".join(duplicates)
            st.warning(f"Ronda {r}: Participantes repetidos detectados (se contaron tal cual aparecen): {dup_text}")

        # Sumamos al total global
        for p, pts in scores.items():
            total_global[p] += pts

        # Orden por puntos desc, luego por nombre
        sorted_round = sorted(scores.items(), key=lambda x: (-x[1], x[0]))

        st.markdown(f"### Total Ronda {r} (x{multiplier})")
        if not sorted_round:
            st.info("Sin participantes detectados en esta ronda.")
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

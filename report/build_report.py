# -*- coding: utf-8 -*-
"""Build the Q-TRACE technical project report as a .docx.

Every technical claim is grounded in the repository source of truth
(C:\\Users\\gaura\\SIH26141). Numbers are taken verbatim from the committed
benchmark artifact benchmarks/m5-reference.json. No performance number,
test count, or capability is invented.
"""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
OUT = os.path.join(HERE, "Q-TRACE_Technical_Report.docx")

INK = RGBColor(0x1B, 0x24, 0x30)
ACCENT = RGBColor(0x1F, 0x6F, 0x8B)
MUTED = RGBColor(0x6B, 0x77, 0x87)
DANGER = RGBColor(0xA3, 0x3A, 0x3A)

doc = Document()


st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(10.5)
st.font.color.rgb = INK
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.12

for name, size, color, before, after in [
    ("Heading 1", 16, ACCENT, 18, 8),
    ("Heading 2", 13, ACCENT, 14, 6),
    ("Heading 3", 11.5, INK, 10, 4),
]:
    s = doc.styles[name]
    s.font.name = "Calibri"
    s.font.size = Pt(size)
    s.font.bold = True
    s.font.color.rgb = color
    s.paragraph_format.space_before = Pt(before)
    s.paragraph_format.space_after = Pt(after)
    s.paragraph_format.keep_with_next = True

for sec in doc.sections:
    sec.top_margin = Inches(0.9)
    sec.bottom_margin = Inches(0.9)
    sec.left_margin = Inches(0.95)
    sec.right_margin = Inches(0.95)



def H1(t):
    doc.add_heading(t, level=1)


def H2(t):
    doc.add_heading(t, level=2)


def H3(t):
    doc.add_heading(t, level=3)


def P(t, size=10.5, italic=False, color=None, align=None, space_after=6):
    p = doc.add_paragraph()
    r = p.add_run(t)
    r.font.size = Pt(size)
    r.italic = italic
    if color is not None:
        r.font.color.rgb = color
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    return p


def B(t, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.3 + 0.25 * level)
    r = p.add_run(t)
    r.font.size = Pt(10.5)
    p.paragraph_format.space_after = Pt(3)
    return p


def CITE(t):
    p = doc.add_paragraph()
    r = p.add_run(t)
    r.font.name = "Consolas"
    r.font.size = Pt(8.5)
    r.font.color.rgb = MUTED
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.left_indent = Inches(0.3)
    return p


def EQ(text, num):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text + "      (" + num + ")")
    r.italic = True
    r.font.name = "Cambria"
    r.font.size = Pt(11)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(6)
    return p


def FIGURE(fname, caption, width=6.4):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(os.path.join(FIG, fname), width=Inches(width))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = c.add_run(caption)
    r.font.size = Pt(8.5)
    r.italic = True
    r.font.color.rgb = MUTED
    c.paragraph_format.space_after = Pt(10)


def TBL(headers, rows, widths=None, font=8.5, header_fill="1F6F8B"):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        pr = hdr[i].paragraphs[0]
        run = pr.add_run(h)
        run.bold = True
        run.font.size = Pt(font)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), header_fill)
        hdr[i]._tc.get_or_add_tcPr().append(shd)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            pr = cells[i].paragraphs[0]
            run = pr.add_run(str(val))
            run.font.size = Pt(font)
            pr.paragraph_format.space_after = Pt(2)
    if widths:
        for r_ in t.rows:
            for i, w in enumerate(widths):
                r_.cells[i].width = Inches(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def NOTE(t):
    p = doc.add_paragraph()
    r = p.add_run(t)
    r.font.size = Pt(9)
    r.italic = True
    r.font.color.rgb = DANGER
    p.paragraph_format.space_after = Pt(8)
    return p


def PAGEBREAK():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def add_toc():
    p = doc.add_paragraph()
    run = p.add_run()
    fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
    it.text = 'TOC \\o "1-3" \\h \\z \\u'
    fc2 = OxmlElement("w:fldChar"); fc2.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t")
    t.text = ("[Table of contents — in Microsoft Word, right-click here and "
              "choose “Update Field” to populate.]")
    fc3 = OxmlElement("w:fldChar"); fc3.set(qn("w:fldCharType"), "end")
    run._r.append(fc); run._r.append(it); run._r.append(fc2)
    run._r.append(t); run._r.append(fc3)


def add_header_footer():
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]
    hr = hp.add_run("Q-TRACE — Technical Project Report   ·   SIH26141   ·   Smart India Hackathon 2026")
    hr.font.size = Pt(8)
    hr.font.color.rgb = MUTED
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = fp.add_run("Page ")
    r1.font.size = Pt(8); r1.font.color.rgb = MUTED
    run = fp.add_run()
    fc = OxmlElement("w:fldChar"); fc.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = "PAGE"
    fc2 = OxmlElement("w:fldChar"); fc2.set(qn("w:fldCharType"), "end")
    run._r.append(fc); run._r.append(it); run._r.append(fc2)
    run.font.size = Pt(8); run.font.color.rgb = MUTED
    r2 = fp.add_run("  of  ")
    r2.font.size = Pt(8); r2.font.color.rgb = MUTED
    run2 = fp.add_run()
    fc3 = OxmlElement("w:fldChar"); fc3.set(qn("w:fldCharType"), "begin")
    it2 = OxmlElement("w:instrText"); it2.set(qn("xml:space"), "preserve"); it2.text = "NUMPAGES"
    fc4 = OxmlElement("w:fldChar"); fc4.set(qn("w:fldCharType"), "end")
    run2._r.append(fc3); run2._r.append(it2); run2._r.append(fc4)
    run2.font.size = Pt(8); run2.font.color.rgb = MUTED



for _ in range(3):
    doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Q-TRACE"); r.bold = True; r.font.size = Pt(44); r.font.color.rgb = ACCENT
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Quantum Threat & Reliability Analysis\nfor Cryptographic Evidence")
r.font.size = Pt(18); r.font.color.rgb = INK
doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Technical Project Report"); r.font.size = Pt(14); r.bold = True
doc.add_paragraph()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("SIH26141 — Quantum-Inspired Cyber Threat Detection\nfor Digital Signature Security")
r.font.size = Pt(12); r.font.color.rgb = MUTED
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Smart India Hackathon 2026"); r.font.size = Pt(12); r.font.color.rgb = MUTED
doc.add_paragraph(); doc.add_paragraph()
TBL(["Item", "Value"], [
    ["Project name", "Q-TRACE"],
    ["Full name", "Quantum Threat & Reliability Analysis for Cryptographic Evidence"],
    ["Problem statement", "SIH26141 — Quantum-Inspired Cyber Threat Detection for Digital Signature Security"],
    ["Hackathon", "Smart India Hackathon 2026"],
    ["Reference protocol version", "RQDS-TP-1.0 (project reference construction — not a standard)"],
    ["API version", "v1 (mounted at /api/v1)"],
    ["Report date", "2026-09-25"],
    ["Source of truth", "Repository at the project root; benchmark artifact benchmarks/m5-reference.json"],
    ["Team identification present in source", "Git author “Gaurav Singh”; contributor branch namespace “sarkarhrit5-ops”. No formal team-roster file exists in the repository."],
], widths=[2.0, 4.6], font=9)
P("Detection in this project is quantum-simulation-backed, model-based statistical "
  "threat detection. It is not machine learning: no neural network, random forest, "
  "SVM, deep-learning model or trained classifier exists anywhere in the codebase.",
  size=9.5, italic=True, color=DANGER)
PAGEBREAK()


H1("Table of Contents")
add_toc()
PAGEBREAK()


H1("Executive Summary")

H2("The problem")
P("SIH26141 asks for quantum-inspired cyber-threat detection that protects digital "
  "signature security. Classical signature schemes (RSA, DSA, ECDSA) rest on hardness "
  "assumptions that a sufficiently large fault-tolerant quantum computer running Shor's "
  "algorithm would break. Quantum Digital Signatures (QDS) offer an alternative whose "
  "security rests on quantum mechanics rather than computational hardness, but practical "
  "QDS is hard to deploy and hard to evaluate. The problem statement therefore calls for a "
  "framework that can model quantum signature behaviour, model the threats against it, and "
  "detect tampering from observable evidence.")

H2("The approach actually implemented")
P("Q-TRACE is a simulation-and-evidence platform, not a deployed cryptographic library and "
  "not a machine-learning system. It builds a small, fully-simulated teleportation-based "
  "reference protocol; subjects the simulated quantum channel to honest noise and to six "
  "modelled attacks; extracts only the evidence a real verifier could observe; and applies "
  "finite-sample statistics (exact Clopper–Pearson binomial intervals and an honest-null "
  "threshold) to decide whether an observed session is inconsistent with honest behaviour. "
  "A FastAPI backend exposes every stage, and a React web console (branded Q-TRACE) lets a "
  "judge drive the whole workflow.")

H2("What was actually implemented (verified against source)")
B("A verified quantum core: six Pauli eigenstates, the |Φ+⟩ Bell state, three-qubit "
  "teleportation with classical Bell-bit feed-forward Pauli correction, density-matrix "
  "representation, and projective measurement via the Born rule — executed on Qiskit 2.5.2 / "
  "Qiskit-Aer 0.17.2 and reproducibility-tested.")
B("A reference QDS-style protocol construction: SHA-256 canonical message binding, "
  "CSPRNG session id and nonce, a deterministic public state-sequence derivation over the "
  "six-state alphabet, single-shot teleportation per state, and a hash-sealed canonical "
  "transcript with an independent-reconstruction verifier.")
B("Five honest Pauli noise channels (identity, depolarizing, bit-flip, phase-flip, "
  "bit-phase-flip) and six attack models (forgery, impersonation, unauthorized verification, "
  "replay, intercept–resend, channel tampering), each with an explicit observable/ground-truth split.")
B("A detection engine that consumes observable evidence only, computes a mismatch rate with "
  "an exact Clopper–Pearson interval, and emits categorical findings with no security score.")
B("A calibration layer deriving a sample-size-specific threshold from honest-only data, an "
  "evaluation layer producing FAR/FRR/detection metrics and eight reference curves, and a "
  "security-interpretation layer with an assumption register, observability matrix, "
  "composition assessment and a claim checker that rejects forbidden security claims.")
B("A FastAPI backend (24 endpoints under /api/v1 plus three operational endpoints) and a "
  "React/TypeScript/Vite console with seven workflow pages.")

H2("Major capabilities")
B("Reproducible quantum-channel experiments: identical (circuit, shots, seed) triples give identical counts.")
B("Honest, label-free detection: the detector is structurally, statically and behaviourally "
  "prevented from seeing attack labels; two scenarios with identical observables but different "
  "ground truth produce identical detector output.")
B("Finite-sample statistical rigour: exact Clopper–Pearson intervals, an honest-null "
  "threshold with a split alpha budget, a Hoeffding cross-check, and an explicit "
  "primary-vs-diagnostic statistic policy.")
B("Transparent security posture: every forbidden over-claim (information-theoretic security, "
  "forgery bound, universal detection, optimality) is rejected by an in-repo claim checker.")

H2("Major limitations (stated plainly)")
B("Simulation-only. No quantum hardware is used or validated; all quantum behaviour is simulated.")
B("No secret signing key exists, therefore no unforgeability. A keyless full forgery verifies "
  "successfully; this is demonstrated, not hidden.")
B("No formal security proof, no forgery bound, no composability theorem, no information-theoretic guarantee.")
B("The quantum statistic detects only the two channel attacks (intercept–resend, channel "
  "tampering). The four protocol-layer attacks (forgery, impersonation, unauthorized "
  "verification, replay) are detected — if at all — by classical controls, and measured "
  "detection by the quantum statistic is 0.0 with FAR 1.0.")
B("No coherent/multi-qubit/adaptive adversary; individual attacks only, no quantum memory.")
B("Thresholds are sample-size and configuration specific and are not cryptographic security parameters.")

H2("Plain-English explanation")
P("Imagine two people who want to check that a signed message really travelled untouched. "
  "Instead of trusting a secret password, the sender encodes the message into a short list of "
  "tiny quantum objects (qubits) chosen from six well-known states, and teleports each one to "
  "the receiver using a shared entangled pair. Anyone who secretly measures or tampers with a "
  "qubit in transit inevitably disturbs it in a way the receiver can notice when they measure "
  "it in the basis the protocol says to use. Q-TRACE simulates this whole conversation on a "
  "classical computer, deliberately adds honest noise and simulated attackers, and then asks a "
  "very careful question: “is the amount of disturbance we see bigger than what honest noise "
  "alone would produce?” It answers using plain statistics on counts — not AI — and it is "
  "honest about what that answer does and does not prove.")
PAGEBREAK()


H1("1. Problem Statement and Motivation")
H2("1.1 SIH26141 problem context")
P("The Smart India Hackathon 2026 problem statement SIH26141, “Quantum-Inspired Cyber Threat "
  "Detection for Digital Signature Security” (repository file docs/research/SIH26141.pdf), asks "
  "for a framework that uses quantum-inspired techniques to detect cyber threats against "
  "digital signature security. The repository's own research synthesis "
  "(docs/research/consensus-research.md) recommends a non-machine-learning, threshold-based "
  "detection approach built on mismatch statistics, disturbance, projective verification and "
  "finite-size reasoning. Q-TRACE is the implementation of that recommendation.")

H2("1.2 Cybersecurity context")
P("Digital signatures provide authenticity, integrity and non-repudiation. Nearly all deployed "
  "schemes are classical public-key constructions whose security is computational: an adversary "
  "with enough compute breaks them. This is the motivation for post-quantum and quantum "
  "cryptographic research, and the reason a threat-detection layer for signature infrastructure "
  "is valuable.")

H2("1.3 Why quantum computing matters — Shor's algorithm as background only")
P("Shor's algorithm (1994) solves integer factorisation and discrete logarithms in polynomial "
  "time on a fault-tolerant quantum computer, which would break RSA, DSA and ECDSA. In this "
  "report Shor's algorithm appears strictly as background motivation for why quantum-resistant "
  "signature research matters.")
NOTE("Q-TRACE does NOT implement Shor's algorithm. There is no factorisation or discrete-log "
     "code anywhere in the repository (verified by search). Shor's algorithm is context, not a component.")

H2("1.4 Why RSA / DSA / ECDSA matter as context — and that Q-TRACE does not implement them")
P("RSA, DSA and ECDSA are the incumbent schemes whose vulnerability motivates quantum signature "
  "research. They are discussed here only to frame the threat.")
NOTE("Q-TRACE does NOT implement RSA, DSA or ECDSA. No classical public-key cryptography, key "
     "generation, or signing with a private key exists in the codebase. The reference protocol "
     "holds no key material at all (backend/protocol/models.py:L188-190).")

H2("1.5 The role of QDS")
P("Quantum Digital Signatures derive security from quantum mechanics (no-cloning, measurement "
  "disturbance) rather than computational hardness. Foundational and memory-free QDS literature "
  "(Bennett et al. 1993 teleportation; Dunjko–Wallden–Andersson 2014; Collins et al. 2014; "
  "Wallden et al. 2015) informs the design. Q-TRACE implements a project-specific reference "
  "construction inspired by these ideas for simulation and detection research — it is not an "
  "implementation of any named or standardised QDS protocol.")
PAGEBREAK()


H1("2. Project Objectives Mapped to the Implementation")
P("The table maps each SIH-style objective to what the repository actually implements, with the "
  "code/test evidence and an honest status.")
TBL(["Requirement", "How Q-TRACE addresses it", "Evidence in code / tests", "Status"], [
    ["Quantum-inspired signature substrate",
     "Six Pauli eigenstates, |Φ+⟩ Bell pair, teleportation with Pauli feed-forward, density-matrix simulation",
     "backend/quantum/states.py:L95-104; bell.py:L31-53; teleport.py:L85-127; correction.py:L74-79; density.py:L87-117; tests/quantum/*",
     "Implemented"],
    ["Message binding to quantum states",
     "SHA-256 canonical binding → counter-mode nibble-rejection state sequence over the six-state alphabet",
     "backend/protocol/binding.py:L56-99; encoding.py:L130-174; tests/protocol/test_encoding.py",
     "Implemented (engineering choice, not a standard)"],
    ["Threat modelling",
     "Six attack models with explicit attacker capability and observable/ground-truth split",
     "backend/attacks/*.py; tests/security/test_attacks.py",
     "Implemented (individual attacks only)"],
    ["Channel noise modelling",
     "Five Pauli channels applied analytically to density matrices",
     "backend/noise/base.py:L189-206; depolarizing/bit_flip/phase_flip/bit_phase_flip.py; tests/security/test_channels.py",
     "Implemented"],
    ["Threat detection from observable evidence",
     "Mismatch rate + exact Clopper–Pearson interval; categorical findings; label-free by construction",
     "backend/detection/{mismatch,statistics,engine,evidence}.py; tests/detection/test_separation.py",
     "Implemented"],
    ["Statistical calibration with finite samples",
     "Honest-only calibration, honest-null quantile threshold, split alpha, Hoeffding cross-check",
     "backend/calibration/{baseline,confidence,thresholds}.py; backend/security/finite_size.py; tests/calibration/*",
     "Implemented"],
    ["Evaluation / benchmarking",
     "Benchmark harness with calibration/evaluation split, FAR/FRR, curves, robustness, discrimination, sample-size study",
     "backend/evaluation/*; benchmarks/m5-reference.json; tests/evaluation/*",
     "Implemented"],
    ["Transparent security analysis",
     "Assumption register, observability matrix, composition assessment, claim checker",
     "backend/security/{assumptions,observability,composition,interpretation}.py; tests/security/*",
     "Implemented"],
    ["Serviceable API",
     "FastAPI app factory, /api/v1 routes, Pydantic validation, in-memory store, error envelope",
     "backend/api/app.py:L82-123; routes/*; tests/api/*",
     "Implemented"],
    ["Judge-facing console",
     "React/TS/Vite console, seven workflow pages, observable-only handoff",
     "frontend/src/pages/*; frontend/src/api/client.ts",
     "Implemented"],
    ["Unforgeability / formal QDS security",
     "Not attempted: no secret key, no forgery game, no proof",
     "backend/protocol/models.py:L188-190; backend/security/composition.py:L96-113; backend/attacks/forgery.py:L22-45",
     "Not implemented (by design)"],
    ["Hardware validation",
     "Not present; all quantum behaviour is simulated",
     "backend/quantum/measure.py:L105-132 (Aer simulator only)",
     "Not implemented"],
], widths=[1.5, 2.1, 2.1, 1.1], font=7.6)
PAGEBREAK()


H1("3. High-Level System Architecture")
P("Q-TRACE is organised as a strict one-way dependency stack. Lower layers never import higher "
  "layers, and this direction is enforced by architecture tests. The declared order is "
  "backend.quantum → backend.protocol → backend.noise → backend.attacks → backend.simulation, "
  "with backend.detection, backend.calibration, backend.evaluation and backend.security layered "
  "above, and backend.api as the outermost application boundary.")
CITE("backend/attacks/__init__.py:L19 ; backend/quantum/__init__.py:L15-18 ; tests/*/test_architecture.py")
FIGURE("01_architecture.png",
       "Figure 3.1 — Q-TRACE end-to-end pipeline and the five component layers. The dotted line "
       "separates quantum-channel stages from the statistical stages that consume only observable evidence.")

H2("3.1 The pipeline, stage by stage (simple language)")
TBL(["Stage", "What happens (simple)", "Layer"], [
    ["Message", "A plain-text message is supplied (e.g. “transfer 100 units to account 7”).", "Classical"],
    ["Session / Binding", "A session id and nonce are drawn from the OS CSPRNG; a SHA-256 binding ties message+session+nonce+version together.", "Classical"],
    ["Quantum State Generation", "The binding deterministically expands (counter-mode SHA-256 + unbiased nibble rejection) into a sequence of six Pauli eigenstates.", "Classical→Quantum"],
    ["Bell-State Teleportation", "Each state is teleported over a simulated |Φ+⟩ pair; the signer records the two public Bell bits per state.", "Quantum"],
    ["Noise / Attack Simulation", "An honest Pauli channel and/or a modelled attack acts on the qubits the channel carries.", "Quantum"],
    ["Measurement", "The verifier measures each received qubit in the basis the protocol derived; the Born rule gives P(expected).", "Quantum"],
    ["Observable Evidence", "Only what a real verifier could see is kept: per-state probabilities/matches, counts, verification flags, authorization observations.", "Statistical input"],
    ["Detection", "Consistency, authorization and replay checks plus a mismatch rate with a Clopper–Pearson interval produce categorical findings.", "Statistical"],
    ["Calibration / Statistics", "Honest-only data yields a one-sided upper bound and a sample-size-specific rejection count k_crit(N).", "Statistical"],
    ["Evaluation", "Disjoint-seed populations give FAR / FRR / detection rates, curves, robustness and discrimination results.", "Statistical"],
    ["Security Interpretation", "Assumptions, observability, composition and a claim checker state what is and is not established.", "Statistical/Policy"],
], widths=[1.4, 4.2, 1.2], font=8.2)

H2("3.2 Component classification")
B("Quantum: states, Bell pair, teleportation, correction, density matrices, measurement, noise channels.")
B("Classical protocol controls: binding, session/nonce, state-sequence derivation, transcript, authorization membership, replay ledger.")
B("Statistical: mismatch rate, intervals, thresholds, metrics, evaluation.")
B("API / infrastructure: FastAPI app, routes, schemas, store, CORS, errors, logging.")
B("Frontend / presentation: React console pages and charts.")
PAGEBREAK()


H1("4. Quantum Model")
P("This section states the quantum mathematics exactly as implemented, identifies the source "
  "location, and explains each equation's role. All linear algebra for channels and measurement "
  "is closed-form NumPy; Qiskit supplies circuit construction, Statevector/DensityMatrix "
  "coercion, and the Aer shot simulator.")

H2("4.1 Qubit states and the six Pauli eigenstates")
P("A single qubit is a unit vector in C². The protocol's alphabet is the six eigenstates of the "
  "three Pauli operators. The Pauli matrices are defined at backend/quantum/states.py:L60-65 and "
  "the eigenstate table at L95-104.")
TBL(["Index", "Label", "Basis", "Eigenvalue", "State vector", "Protocol id"], [
    ["0", "|0⟩", "Z", "+1", "(1, 0)", "Z+"],
    ["1", "|1⟩", "Z", "−1", "(0, 1)", "Z−"],
    ["2", "|+⟩", "X", "+1", "(1/√2, 1/√2)", "X+"],
    ["3", "|−⟩", "X", "−1", "(1/√2, −1/√2)", "X−"],
    ["4", "|+i⟩", "Y", "+1", "(1/√2, i/√2)", "Y+"],
    ["5", "|−i⟩", "Y", "−1", "(1/√2, −i/√2)", "Y−"],
], widths=[0.5, 0.7, 0.6, 0.8, 1.6, 0.9], font=8.5)
CITE("backend/quantum/states.py:L60-65 (PAULI_MATRICES), L95-104 (_DEFINITIONS), L104 (EIGENSTATE_LABELS)")
P("Each row satisfies P|ψ⟩ = λ|ψ⟩ exactly (verified numerically). The alphabet used by the "
  "protocol is derived from this table so it cannot drift from the quantum core "
  "(backend/protocol/encoding.py:L78-84).")

H2("4.2 Bloch-sphere interpretation")
P("The six states are the six axis points of the Bloch sphere (±x, ±y, ±z). The implementation "
  "does not require a Bloch-sphere object; the eigenstate table plus the basis-rotation "
  "measurement (Section 4.6) is the operational content. Where a geometric reading is useful: a "
  "Pauli channel shrinks or rotates the Bloch vector, and measurement in the wrong basis yields "
  "the uniform 0.5 probability.")

H2("4.3 The Bell state and entanglement")
P("The shared entangled resource is the first Bell state |Φ+⟩, produced by H on q1 then CX(q1→q2):")
EQ("|Φ+⟩ = (|00⟩ + |11⟩)/√2", "4.1")
CITE("backend/quantum/bell.py:L31-53 (bell_circuit), L56-58 (bell_amplitudes_exact), L66-68 (bell_density_matrix)")
P("The circuit-produced statevector equals [1/√2, 0, 0, 1/√2] exactly; the density matrix "
  "|Φ+⟩⟨Φ+| has diagonal [0.5,0,0,0.5]. Entanglement here is the resource that makes "
  "teleportation possible; it carries no secret and provides no security by itself.")

H2("4.4 Teleportation and the Bell measurement")
P("Teleportation uses three qubits: q0 the signature state, q1 Alice's half, q2 Bob's half. The "
  "exact gate sequence (backend/quantum/teleport.py:L85-127) is: initialise q0; compose the Bell "
  "circuit on (q1,q2); CX(q0,q1); H(q0); measure q0→m1 and q1→m0; conditionally correct q2; "
  "optionally rotate and measure q2.")
FIGURE("02_teleportation.png",
       "Figure 4.1 — Teleportation of one signature state with the verified four-branch table. "
       "The two classical Bell bits are public; the Pauli feed-forward is load-bearing.")
P("The Bell measurement is the CX+H followed by computational-basis measurement of (q0,q1); it "
  "projects onto the four Bell outcomes, each with probability 1/4. The pre-measurement state "
  "factorises so that Bob's qubit is a Pauli image of |ψ⟩ per branch "
  "(backend/quantum/teleport.py:L148-168).")

H2("4.5 Classical correction bits and Pauli correction")
P("The two measurement bits select a by-product Pauli; applying its inverse recovers |ψ⟩. The "
  "convention is U(m0,m1) = Z^m0 · X^m1 with Z on the left, so circuit order appends X first then "
  "Z (backend/quantum/correction.py:L7-19, L74-79, L107-137):")
EQ("U(m0,m1) = Z^{m0} · X^{m1},   CORRECTION_TABLE = {(0,0):I, (0,1):X, (1,0):Z, (1,1):ZX}", "4.2")
CITE("backend/quantum/correction.py:L74-79 (CORRECTION_TABLE), L95-104 (correction_unitary), L122-137 (append_conditional_correction)")
P("The correction is implemented as genuine Qiskit classical feed-forward (if_test on the "
  "clbits), not as post-hoc relabelling. Empirically, without correction Bob's bit is wrong in "
  "two of four branches; with correction it is correct in all four.")

H2("4.6 Density-matrix representation and projective measurement")
P("Mixed states (post-noise) are density matrices ρ with Tr ρ = 1. The projective measurement "
  "probability of the expected pure state is the Born rule with projector P_ψ = |ψ⟩⟨ψ|:")
EQ("p_match = Tr(P_ψ · ρ),   P_ψ = |ψ⟩⟨ψ|", "4.3")
EQ("F = ⟨ψ| ρ |ψ⟩", "4.4")
CITE("backend/quantum/density.py:L75-78 (projector), L87-98 (p_match), L106-117 (fidelity_pure)")
NOTE("Equations 4.3 and 4.4 are the SAME quantity for a pure expected state — p_match ≡ F, "
     "identically, not approximately. The code states this explicitly and forbids reporting them "
     "as two independent pieces of evidence (backend/quantum/density.py:L14-23; "
     "backend/detection/fidelity.py:L37-51; backend/detection/features.py:L446-461).")
P("Measurement in Pauli basis P is implemented by rotating P to Z (R_P P R_P† = Z) then measuring "
  "computationally; the measured bit b corresponds to eigenvalue (−1)^b. Rotations: Z→(), "
  "X→(H), Y→(S†,H) (backend/quantum/measure.py:L56-60). A state measured in the wrong basis gives "
  "probability exactly 0.5.")

H2("4.7 Role of each equation in the system")
TBL(["Equation", "Meaning", "Implementation", "Role"], [
    ["4.1", "Maximally entangled resource", "bell.py:L31-53", "Enables teleportation of each signature state"],
    ["4.2", "By-product Pauli per Bell outcome", "correction.py:L74-137", "Makes teleportation exact; load-bearing feed-forward"],
    ["4.3", "Born-rule projective match probability", "density.py:L87-98", "The per-state observable probability_expected"],
    ["4.4", "Fidelity of ρ against pure ψ", "density.py:L106-117", "Identical to 4.3; aggregated as mean fidelity (diagnostic)"],
], widths=[0.7, 2.0, 1.6, 2.5], font=8.2)
PAGEBREAK()


H1("5. Message Binding and the Reference QDS Protocol")
H2("5.1 Message hashing")
P("The message hash is SHA-256 over the UTF-8 encoding of the NFC-normalised message text and "
  "nothing else. The algorithm is pinned to sha256 and any other algorithm raises.")
EQ("message_hash = SHA256( utf8( NFC(message) ) )", "5.1")
CITE("backend/protocol/binding.py:L56-58 ; backend/protocol/canonical.py:L57, L142-157")

H2("5.2 Session id, nonce and the binding")
P("session_id (128-bit) and nonce (256-bit) come from the OS CSPRNG via secrets; they are "
  "unpredictable, unique, never derived from the message, and not reproducible. The simulator "
  "seed is a separate, reproducible, security-meaningless integer and is never mixed into them.")
EQ("message_binding = SHA256( canonical{ domain, protocol_version, session_id, nonce, message } )", "5.2")
CITE("backend/protocol/session.py:L57-64, L3-21 ; backend/protocol/binding.py:L61-99 ; backend/protocol/models.py:L77-78")
P("The binding uses a canonical named-field encoding (not concatenation) with a domain-separation "
  "tag, so different field tuples cannot collide and arguments cannot be silently swapped.")

H2("5.3 Deterministic state sequence and the state alphabet")
P("The binding digest seeds a counter-mode SHA-256 stream; nibbles are rejection-sampled to "
  "unbiased indices over the six-state alphabet:")
EQ("block_k = SHA256( seed ‖ domain  uint32_be(k) );  accept nibble < 12;  index = nibble mod 6", "5.3")
CITE("backend/protocol/encoding.py:L130-143 (nibble_stream), L146-166 (derive_alphabet_indices), L169-174 (derive_state_sequence)")
P("Because 12 = 2×6, each residue class appears exactly twice in the accepted range, so the "
  "mapping is unbiased over the six states (unlike a naive byte mod 6). The derivation is a pure "
  "function of (binding, count): no clock, no randomness, no global state.")
NOTE("ENGINEERING DESIGN CHOICE: the hash→state mapping is explicitly an engineering choice for "
     "the reference prototype, not a security construction and not a standardised QDS encoding. "
     "The code says so verbatim (backend/protocol/encoding.py:L9-10) and the docs repeat it "
     "(docs/protocol/reference-qds.md:L175-177, L474-477). It is a public deterministic PRF with "
     "no keyed/secret component.")

H2("5.4 Transcript generation and the signing lifecycle")
P("Signing derives the state sequence, teleports each state (recording the two public Bell bits "
  "per state), and seals a 15-field canonical transcript whose hash is SHA-256 over every field "
  "except the hash itself. The session lifecycle in the protocol layer is exactly CREATED → SIGNED.")
CITE("backend/protocol/signer.py:L119-160 ; backend/protocol/transcript.py:L81-99, L124-165 ; backend/protocol/models.py:L104-108")
P("The transcript records states symbolically (which of the six eigenstates), never amplitudes; "
  "floats are structurally impossible in the canonical encoding.")

H2("5.5 Verification")
P("The verifier never trusts the signer. It recomputes the hash and the binding, independently "
  "re-derives the state sequence, compares against the declared states, and per state applies the "
  "branch correction and measures in the derived basis. Acceptance requires all structural and "
  "measurement flags true. Every verification also appends the caveat that reference verification "
  "is structural: binding and consistency, not unforgeability.")
CITE("backend/protocol/verifier.py:L188-380 (six checks), L353-356 (caveat), L3-15 (never-trust principle)")

H2("5.6 Cryptographic limitations (explicit)")
B("No secret signing key. Session and transcript hold no key material; sign() takes no key. "
  "(backend/protocol/models.py:L188-190; backend/attacks/forgery.py:L36-38)")
B("No formal forgery game and no adversary-advantage computation anywhere.")
B("No unforgeability. Because every ingredient is public and deterministic, a keyless full "
  "forgery verifies successfully — demonstrated by backend/attacks/forgery.py and verified by "
  "execution (accepted=True with arbitrary branch bits under the M2 reconstruction seam).")
B("No information-theoretic security proof. describe_protocol() returns formal_security_claim: "
  "false and standardized: false (backend/protocol/reference_qds.py:L187-200).")
B("Not an official Egreen Quanta or any named/standardised protocol "
  "(backend/protocol/reference_qds.py:L7-22).")
PAGEBREAK()


H1("6. Quantum Channel and Noise Model")
P("Every honest noise model is a single-qubit Pauli channel applied analytically to a density "
  "matrix (never a sampled trajectory):")
EQ("E(ρ) = p_I·ρ + p_X·XρX + p_Y·YρY + p_Z·ZρZ,   p_I+p_X+p_Y+p_Z = 1", "6.1")
CITE("backend/noise/base.py:L20-29 (generic form), L189-206 (QuantumChannel.apply)")
TBL(["Channel", "Probability table (p = strength)", "p is an error prob.?", "Physical reading", "Effect / limitation"], [
    ["identity (none)", "p_I=1", "—", "no noise", "E(ρ)=ρ"],
    ["depolarizing", "p_I=1−3p/4, p_X=p_Y=p_Z=p/4", "No (error prob = 3p/4)", "blend toward I/2", "state-independent; T = p/2; p=1 → I/2"],
    ["bit_flip", "p_I=1−p, p_X=p", "Yes", "random X", "invisible on X eigenstates"],
    ["phase_flip", "p_I=1−p, p_Z=p", "Yes", "random Z", "invisible on Z eigenstates (and to Z-basis measurement)"],
    ["bit_phase_flip", "p_I=1−p, p_Y=p", "Yes", "random Y", "invisible on Y eigenstates"],
], widths=[1.1, 1.9, 1.1, 1.2, 1.6], font=8.0)
CITE("backend/noise/depolarizing.py:L57-94 ; bit_flip.py:L40-60 ; phase_flip.py:L44-64 ; bit_phase_flip.py:L53-73")
P("Depolarizing deliberately rejects p>1 (the coefficient of ρ would go negative). The three flip "
  "channels use require_unit_probability. The raw disturbance statistic is the trace distance:")
EQ("T(ρ,σ) = ½ · Tr|ρ−σ| = ½ · Σ |eig(ρ−σ)|", "6.2")
CITE("backend/noise/base.py:L331-342 (trace_distance)")

H2("6.1 Noise strength → measurement probability → mismatch probability")
P("For depolarizing strength η, every reference state has projective match probability 1 − η/2, "
  "so a single projective measurement mismatches with probability η/2. This is the honest null's "
  "non-zero mean and is the bridge from a physical parameter to the statistic the detector uses.")
EQ("p_match(honest, depolarizing η) = 1 − η/2 ;  p_mismatch = η/2", "6.3")
CITE("backend/calibration/baseline.py:L13-18 ; verified: depolarizing p=0.02 → all states read probability_expected 0.99")
P("For flip channels the match probability depends on whether the state's basis is the channel's "
  "fixed point (e.g. phase_flip leaves Z eigenstates untouched for every p), so the honest null is "
  "a Poisson-binomial mixture rather than a single binomial — the calibration layer detects this "
  "via a homogeneity diagnostic.")
PAGEBREAK()


H1("7. Attack Models")
P("Six attacks are implemented. For each we state capability, what is modified, what is "
  "unchanged, the expected observable effect, the detection mechanism, whether the evidence is "
  "quantum-channel or classical-protocol, and a known limitation. Verified runner outputs are "
  "given where they are the honest summary.")
FIGURE("03_threat_taxonomy.png",
       "Figure 7.1 — Threat taxonomy. Four attacks are caught only by classical protocol controls; "
       "two produce quantum-channel disturbance.")

H2("7.1 Forgery (classical protocol evidence)")
B("Capability: the public canonicalisation and public state-sequence derivation; an obtained transcript (rebind mode). No key — none exists.")
B("Modified: message_hash/message_binding (rebind_only) or the entire transcript incl. invented branch bits (full_forge).")
B("Unchanged: the quantum channel (received states pass through) in rebind mode.")
B("Observable effect: binding/sequence inconsistency; under the runner, message_valid=False and (full_forge) state_sequence_valid=False.")
B("Detection: verifier's independent recomputation of binding and state sequence; detector consistency findings.")
B("Evidence type: classical protocol integrity — NOT quantum measurement.")
B("Limitation: full_forge verifies successfully against the reconstruction-based verifier (M2 seam); the protocol offers binding/integrity, not unforgeability.")
CITE("backend/attacks/forgery.py:L78-213 ; L22-27, L36-45 (no key, no quantum forgery)")

H2("7.2 Impersonation (classical authorization evidence)")
B("Capability: present an unauthorized signer_id; re-seal the transcript.")
B("Modified: transcript.signer_id only.")
B("Unchanged: the quantum channel, verifier context, authorization context.")
B("Observable effect: none in the quantum evidence (mismatch 0, disturbance 0); only authorization.signer_authorized = False.")
B("Detection: authorization membership test on declared identifiers.")
B("Evidence type: classical authorization — a quantum measurement alone cannot detect this (backend/attacks/impersonation.py:L28-33).")
B("Limitation: no authentication/credential/certificate exists; signer_id is a name.")

H2("7.3 Unauthorized verification (classical authorization evidence)")
B("Capability: present an unauthorized verifier_id and rewrite both transcript and verifier context so addressing checks pass.")
B("Modified: transcript.verifier_id and verifier_context.verifier_id.")
B("Unchanged: quantum channel.")
B("Observable effect: authorization.verifier_authorized = False; quantum evidence clean.")
B("Detection: authorization membership test.")
B("Evidence type: classical authorization.")
B("Limitation: identities are modelled, not authenticated.")

H2("7.4 Replay (classical cross-event evidence)")
B("Capability: re-present an identical, valid transcript and nonce.")
B("Modified: nothing — the transcript is returned unchanged on purpose.")
B("Unchanged: everything; a single replayed event is indistinguishable from a fresh one on quantum evidence.")
B("Observable effect: the same nonce/session/created_at appearing in two events (a temporal, cross-event signal).")
B("Detection: in-memory ReplayRegistry ledger (nonce/session/transcript sets) in backend/detection/replay.py.")
B("Evidence type: classical protocol control requiring cross-event state — explicitly NOT quantum disturbance.")
B("Limitation: ledger is in-memory, single-process, not persisted; the attack layer deliberately does not implement a consumed-nonce store.")
CITE("backend/attacks/replay.py:L13-28 ; backend/detection/replay.py:L3-13, L102-235")

H2("7.5 Intercept–resend (quantum-channel evidence)")
B("Capability: measure each intercepted qubit in a chosen/random basis and re-prepare the obtained eigenstate (genuine measure-and-reprepare).")
B("Modified: the received density matrices at the selected indices.")
B("Unchanged: transcript, verifier context, authorization.")
B("Observable effect: wrong-basis guesses give probability_expected = 0.5 (a coin flip); correct guesses give 1.0; mismatch rate rises.")
B("Detection: elevated mismatch rate D_m / disturbance; quantum measurement anomaly findings.")
B("Evidence type: quantum-channel disturbance.")
B("Limitation: individual (one-qubit) attack, single copy, no quantum memory, no coherent/adaptive strategy; a correct guess is physically indistinguishable from an honest channel for that state.")
CITE("backend/attacks/intercept_resend.py:L98-183 ; L123-142 (Born-rule measure-and-reprepare)")

H2("7.6 Channel tampering (quantum-channel evidence)")
B("Capability: apply a coherent single Pauli P ρ P† to a fraction of the states in transit.")
B("Modified: the received density matrices at the selected indices.")
B("Unchanged: transcript, verifier context, authorization.")
B("Observable effect: an anticommuting Pauli drives probability_expected to 0 for that state; mismatch and disturbance rise with fraction.")
B("Detection: elevated mismatch rate D_m / disturbance.")
B("Evidence type: quantum-channel disturbance.")
B("Limitation: attacker applies a Pauli but does not measure; no partial/weak measurement, no multi-state coherent attack. Note the “XZ” option is operationally Y (global phase cancels).")
CITE("backend/attacks/channel_tampering.py:L70-137 ; L112 (P ρ P†)")

H2("7.7 Verified end-to-end runner outputs (one fixed scenario)")
TBL(["Scenario", "accepted", "mismatch_count / 16", "mean_channel_disturbance", "Authorized (signer/verifier)"], [
    ["honest baseline", "True", "0", "0.0", "True / True"],
    ["depolarizing p=0.02", "False", "16", "0.01 (= p/2)", "True / True"],
    ["bit_flip p=0.02", "False", "10", "0.0125", "True / True"],
    ["channel_tampering f=0.20, X", "False", "3", "0.1875 (=3/16)", "True / True"],
    ["intercept_resend f=0.50, random", "False", "5", "0.2209708691", "True / True"],
    ["impersonation (eve)", "True", "0", "0.0", "False / True"],
    ["unauthorized_verification (mallory)", "True", "0", "0.0", "True / False"],
    ["replay (both modes)", "True", "0", "0.0", "True / True"],
    ["forgery rebind_only", "False", "0", "0.0", "True / True"],
    ["forgery full_forge", "False", "11", "0.0", "True / True"],
], widths=[2.2, 0.8, 1.3, 1.6, 1.5], font=8.0)
P("These are execution-verified values for state_count=16, seed 7, pinned identifiers. They show "
  "the clean split: channel attacks disturb the quantum evidence; protocol attacks do not.",
  size=9.5, italic=True)
PAGEBREAK()


H1("8. Observable Evidence Model")
H2("8.1 Ground truth vs observable evidence")
P("Every experiment produces two separate objects. ObservableExperimentData is what a detector "
  "may consume; GroundTruthMetadata (is_malicious, attack_type, attack_fraction, noise settings, "
  "seed) is what only the evaluation layer may read. The observable carries no attack type, no "
  "attack parameter, no noise strength and no is_malicious flag, and has no field referencing the "
  "ground truth.")
CITE("backend/simulation/results.py:L5-31, L114-174 ; backend/attacks/base.py:L4-25")
FIGURE("04_evidence_pipeline.png",
       "Figure 8.1 — The anti-leakage boundary. Ground truth is produced but blocked from the detector.")

H2("8.2 Why the detector must not receive labels")
B("attack_type / attack_fraction: reading them would let the detector “cheat”; the point is to infer from evidence.")
B("Hidden simulator labels and simulator-only metadata: scenario_id encodes the attack fraction "
  "(“a label leak in disguise”), simulator_seed and mean_channel_disturbance are simulator-only; "
  "a real verifier holds none of these. The engine instead derives disturbance from "
  "probability_expected, which the verifier itself computes and which is observable.")
CITE("backend/detection/models.py:L33-56, L444-447")

H2("8.3 The anti-leakage architecture and how it is tested")
B("Structural: ObservableDetectionInput has no forbidden field; duck-typed from_observable avoids importing backend.simulation (which would pull in backend.attacks).")
B("Static: an AST scan of backend/detection forbids importing backend.attacks / backend.noise / backend.simulation and forbids naming GroundTruthMetadata or attack labels; a no-ML check forbids sklearn/tensorflow/torch/keras.")
B("Runtime: a fresh interpreter importing backend.detection must leave those modules unloaded.")
B("Behavioural: two scenarios with byte-identical observables but different ground truth must yield JSON-identical detect() results.")
CITE("tests/detection/test_separation.py:L48-63, L166-228, L236-300 ; tests/evaluation/test_leakage.py")
PAGEBREAK()


H1("9. Detection Engine")
H2("9.1 Feature extraction")
P("The engine computes each quantity exactly once and shares it, so no two components disagree. "
  "The feature catalogue declares 14 features; there is deliberately no composite security score "
  "and no weighted sum.")
CITE("backend/detection/features.py:L91-237 (catalogue), L375-489 (extract_features), L23-28 (no score)")

H2("9.2 Mismatch rate (the primary statistic)")
EQ("D_m = N_mismatch / N_valid", "9.1")
P("Malformed records are excluded from the denominator (folding them in either way “is not "
  "honest”); if N_valid = 0 the rate is undefined, not zero. Each reported rate carries an exact "
  "Clopper–Pearson interval.")
CITE("backend/detection/mismatch.py:L5-8, L89-153 ; backend/detection/statistics.py:L67-104")

H2("9.3 Projective match probability and fidelity are one quantity")
P("Per state, F_i = p_match_i = probability_expected_i. The mean analytic fidelity is therefore "
  "the mean projective match probability — one number, not two. The code declares this redundancy "
  "explicitly and the report must not present them as independent quantum evidence.")
EQ("F = ⟨ψ|ρ|ψ⟩ = Tr(P_ψ ρ) = p_match   (per state, pure expected state)", "9.2")
CITE("backend/detection/fidelity.py:L5-17, L37-51, L144-146 ; backend/quantum/density.py:L14-23 ; backend/detection/features.py:L446-461, L475-478")

H2("9.4 Disturbance and basis-wise statistics")
EQ("D_v = N_disturbed / N_verification_states,   disturbed ⟺ probability_expected < 1 − tolerance (1e-9)", "9.3")
P("Because the reference is exact, D_v is a detection indicator (any nonzero deviation gives 1), "
  "while the magnitude is carried continuously by the fidelity. In the default projective-analytic "
  "mode D_v and D_m coincide and the engine emits a single quantum finding. Basis-wise statistics "
  "report per-basis counts, distributions and mismatch rates as diagnostics.")
CITE("backend/detection/disturbance.py:L17-41, L109-120 ; backend/detection/features.py:L271-317")

H2("9.5 Integrity, replay and authorization evidence (classical)")
B("Integrity/consistency: the detector recomputes the transcript hash, the message binding, the "
  "protocol version, session addressing, state counts and the declared-vs-derived state sequence; "
  "it trusts none of them from the transcript.")
B("Replay: a pure membership test against an in-memory ledger of consumed session ids, nonces and "
  "transcript hashes; side-effect free unless consume is requested.")
B("Authorization: a membership test of presented signer/verifier ids against authorized sets; "
  "explicitly “not proof of identity”.")
CITE("backend/detection/consistency.py:L123-405 ; backend/detection/replay.py:L102-235 ; backend/detection/authorization.py:L96-158")

H2("9.6 Decision logic and evidence generation")
P("The Milestone-4 decision is categorical, not threshold-based: findings are grouped into "
  "families (integrity / authorization / quantum) and the overall status is CLEAR, a single-family "
  "violation, or MULTIPLE_FINDINGS. There is no security score and no p-value at this layer. "
  "Findings never attribute a cause (“noise and undetectable manipulation produce identical "
  "observations”). Statistical findings are non-blocking until calibrated.")
CITE("backend/detection/decision.py:L161-197, L12-17, L200-233 ; backend/detection/evidence.py:L17-27, L135-162")
P("PRIMARY vs DIAGNOSTIC is defined in the calibration layer: exactly one statistic is tested — "
  "the empirical verification mismatch rate D_m against the calibrated threshold; every other "
  "quantity is diagnostic, “reported, never adjudicated.”")
CITE("backend/calibration/multiple_testing.py:L14-27, L61, L66-83")
PAGEBREAK()


H1("10. Statistical Calibration")
FIGURE("05_calibration_flow.png",
       "Figure 10.1 — Calibration → detection → evaluation. The honest null yields a one-sided "
       "upper bound, which yields a sample-size-specific rejection count; the detector tests the "
       "single primary statistic D_m against it, and evaluation and security interpretation follow.")
H2("10.1 Honest calibration dataset and the null hypothesis")
P("Calibration consumes honest-only sessions (role enforced at the config type). The null "
  "hypothesis H0 is that the observed verification statistic is consistent with an authorised "
  "honest session under the specified channel; the statistical model is binomial:")
EQ("H0:  N_mismatch ~ Binomial(N, p0),   p0 = η/2 for depolarizing η", "10.1")
CITE("backend/calibration/baseline.py:L3-24, L204-302")

H2("10.2 Confidence intervals — Clopper–Pearson (implemented)")
EQ("L = Beta⁻¹(α/2; k, n−k+1)  (0 if k=0);   U = Beta⁻¹(1−α/2; k+1, n−k)  (1 if k=n)", "10.2")
P("Implemented exactly via scipy.stats.beta.ppf, shared by detection and calibration; coverage is "
  "at least the stated confidence (conservative, never anti-conservative). One-sided upper and "
  "lower variants are also implemented.")
CITE("backend/calibration/confidence.py:L19-30, L95-179 ; backend/detection/statistics.py:L67-104")

H2("10.3 Hoeffding (implemented as a cross-check only)")
EQ("ε = sqrt( ln(m/α) / (2n) ),   m = 2 (two-sided) or 1 (one-sided)", "10.3")
P("Hoeffding is implemented but used only as a cross-check because it is uniformly looser than "
  "Clopper–Pearson; it never sets the threshold.")
CITE("backend/security/finite_size.py:L212-231, L17-21, L243-246")

H2("10.4 Alpha and the calibration/evaluation split")
P("The reference alpha is 0.05, split evenly: calibration_alpha = 0.025 (spent on the one-sided "
  "upper confidence bound) and evaluation_alpha = 0.025 (spent on the binomial quantile). The "
  "budget is split, not doubled. Calibration and evaluation use disjoint seed blocks "
  "(SEED_BLOCK_SIZE = 1,000,000) with an explicit disjointness assertion.")
CITE("backend/calibration/models.py:L349-399 ; backend/calibration/operating_points.py:L52 ; backend/evaluation/datasets.py:L61-64, L189-206")

H2("10.5 Threshold derivation and sample-size dependence")
EQ("p_upper = Beta⁻¹(1−α_cal; K+1, T−K);   k_crit(N) = min{k : P[Binom(N,p_upper) ≤ k] ≥ 1−α_eval};   θ(N) = k_crit/N", "10.4")
P("Rejection occurs when N_mismatch > k_crit. The threshold is stored with full provenance "
  "(calibration fingerprint, counts, config) and is sample-size specific by construction: applying "
  "it at another N raises rather than silently accepting. There is no default threshold anywhere.")
CITE("backend/calibration/thresholds.py:L8-21, L96-120, L196-218, L221-237 ; backend/calibration/models.py:L402-453")

H2("10.6 Multiple-comparison policy")
P("The reference policy is SINGLE_PRIMARY_WITH_DIAGNOSTICS: exactly one hypothesis test at level "
  "alpha; family_wise_alpha = None and correction = None. Holm–Bonferroni and Bonferroni are "
  "implemented but explicitly not used by the reference operating point (“with one test there is "
  "no family to correct for”). The family-wise error growth 1−(1−α)^k motivates the single-test rule.")
CITE("backend/calibration/multiple_testing.py:L5-9, L61, L187-255")

H2("10.7 The reference operating point")
TBL(["Parameter", "Value (committed artifact)"], [
    ["name", "m5-reference"],
    ["statistic", "mismatch_rate"],
    ["state_count N", "500"],
    ["measurement_mode / shot_count", "sampled / 1"],
    ["reference noise", "depolarizing η = 0.02"],
    ["alpha", "0.05"],
    ["calibration sessions / seeds", "120 / [0, 119]"],
    ["pooled_rate", "0.010 (600 / 60000)"],
    ["p_upper", "0.010828629491245854"],
    ["critical_count k_crit", "10"],
    ["threshold_rate θ", "0.02"],
    ["observed calibration FRR", "0.0"],
], widths=[2.2, 3.4], font=8.6)
CITE("benchmarks/m5-reference.json → operating_point, calibration")
PAGEBREAK()


H1("11. Threshold Interpretation")
H2("11.1 What the threshold means")
P("θ(N) = k_crit/N is the mismatch-rate level above which an observed session is judged "
  "inconsistent with the honest null at the calibrated channel, sample size, measurement mode and "
  "shot count. It is a classification boundary for a finite-sample statistical test.")
H2("11.2 What the threshold does NOT mean")
B("It is not a cryptographic security parameter. The code refuses to label any finite-size bound "
  "as a security bound (constructing one with is_cryptographic_security_bound=True raises).")
B("It is not a forgery probability. FAR is the empirical share of malicious trials the rule "
  "accepted on this dataset — not a forgery bound.")
B("It is not optimal. No objective function was maximised; the operating point is “specified, not optimised”.")
B("It does not transfer across sample sizes or configurations.")
CITE("backend/security/models.py:L109-117 ; backend/security/interpretation.py:L101-152 ; backend/calibration/operating_points.py:L1-6")
H2("11.3 False rejection / false acceptance and high noise")
P("False rejection (FRR) is an honest session rejected; false acceptance (FAR) is a malicious "
  "trial accepted. Because the honest null mean is η/2, raising the honest noise beyond the "
  "calibrated channel pushes honest sessions above the threshold: measured honest FRR is 0.0 at "
  "η=0.02 but 0.5833 at η=0.05 and 1.0 at η=0.10. High noise therefore causes honest rejection — "
  "the operating point is conditional on its calibrated channel.")
CITE("benchmarks/m5-reference.json → robustness.honest_frr_by_noise ; docs/security/M6_SECURITY_ANALYSIS.md (limitation 7)")
H2("11.4 Sample-size dependence (actual threshold table)")
TBL(["N", "k_crit", "θ(N)", "expected FRR", "simulated at this N?"], [
    ["100", "3", "0.03", "0.02374892785243765", "true"],
    ["250", "6", "0.024", "0.020179355262698317", "true"],
    ["500", "10", "0.02", "0.022232768329606634", "true"],
    ["1000", "18", "0.018", "0.01483141553276468", "true"],
    ["2500", "38", "0.0152", "0.017578190585915365", "true"],
    ["5000", "69", "0.0138", "0.021089611519193974", "false (>4096 protocol cap)"],
    ["10000", "129", "0.0129", "0.02255099652565451", "false (>4096 protocol cap)"],
], widths=[0.7, 0.8, 0.8, 1.8, 2.0], font=8.4)
CITE("benchmarks/m5-reference.json → threshold table (single reference calibration, p_upper = 0.010828629491245854)")
PAGEBREAK()


H1("12. Evaluation and Benchmarking")
H2("12.1 Profiles and architecture")
P("Two profiles exist: smoke (fast, “every number is too small to interpret”) and reference. The "
  "reference profile uses N=500, 120 calibration sessions, 12 evaluation trials per attack, "
  "sampled mode with 1 shot/state, depolarizing η=0.02, six attack types, and a sample-size design "
  "of 100…10000 (5000/10000 declared but not simulated because they exceed the protocol's "
  "MAX_STATE_COUNT=4096). The benchmark is reproduced by benchmarks/run_reference_benchmark.py, "
  "which writes the committed JSON/MD artifacts; nothing is read from a stored result or extrapolated.")
CITE("backend/evaluation/benchmark.py:L337-436 ; benchmarks/run_reference_benchmark.py:L20-34")
H2("12.2 Metrics and the positive class")
P("The positive class is “the verification decision rejected the session”. Hence tp = malicious "
  "rejected, fn = malicious accepted, fp = honest rejected, tn = honest accepted; under this "
  "convention FPR = FRR and FNR = FAR as identities of the convention (FAR and FPR are not the "
  "same underlying quantity). Undefined rates return None, never 0.0. ROC and PR curves are "
  "deliberately not produced.")
CITE("backend/evaluation/models.py:L8-32 ; backend/evaluation/metrics.py:L53-66 ; backend/evaluation/curves.py:L24-31")
H2("12.3 Reproducibility and runtime")
P("Session ids, nonces and timestamps are deterministically derived from each trial seed; seed "
  "blocks are disjoint with gaps; the transpile cache (compiled circuits only, never outcomes) is "
  "enabled during the run and reported in provenance. Reference run: runtime 1504.8553420000244 s "
  "(≈25.1 min), 479 scenarios, Python 3.13.5, cache hit_rate 0.9999842146803473.")
CITE("backend/evaluation/harness.py:L91-102, L179-194 ; benchmarks/m5-reference.json → provenance")

H2("12.4 Attack-population results (actual, 12 trials each)")
TBL(["Attack", "fraction", "detection_rate", "FAR", "precision/recall/f1/accuracy"], [
    ["forgery", "0.0", "0.0", "1.0", "None / 0.0 / None / 0.0"],
    ["impersonation", "0.0", "0.0", "1.0", "None / 0.0 / None / 0.0"],
    ["unauthorized_verification", "0.0", "0.0", "1.0", "None / 0.0 / None / 0.0"],
    ["replay", "0.0", "0.0", "1.0", "None / 0.0 / None / 0.0"],
    ["intercept_resend", "0.2", "1.0", "0.0", "1.0 / 1.0 / 1.0 / 1.0"],
    ["channel_tampering", "0.2", "1.0", "0.0", "1.0 / 1.0 / 1.0 / 1.0"],
], widths=[1.8, 0.8, 1.2, 0.7, 2.1], font=8.4)
CITE("benchmarks/m5-reference.json → attack_evaluation.by_attack_type")
NOTE("Read this table honestly: the quantum statistic detects the two channel attacks perfectly "
     "and detects none of the four protocol-layer attacks. The latter are the responsibility of "
     "classical controls (authorization / replay ledger / integrity), not of the quantum statistic.")

H2("12.5 Robustness (honest FRR by noise; detection by noise×attack)")
TBL(["Noise level (η)", "honest FRR", "detection intercept_resend", "detection channel_tampering"], [
    ["none (0.0)", "0.0", "1.0", "1.0"],
    ["low (0.005)", "0.0", "1.0", "1.0"],
    ["medium (0.02)", "0.0", "1.0", "1.0"],
    ["high (0.10)", "1.0", "1.0", "1.0"],
], widths=[1.4, 1.1, 1.8, 1.8], font=8.4)
CITE("benchmarks/m5-reference.json → robustness.honest_frr_by_noise, robustness.detection_by_noise_and_attack")
P("At η=0.10 the honest FRR is 1.0: that operating point is unusable for honest traffic. The "
  "usable calibrated levels are none/low/medium.")

H2("12.6 Sample-size study (fresh calibration + threshold per size)")
TBL(["N", "calibration sessions (states)", "k_crit", "θ", "p_upper", "honest FRR", "detection"], [
    ["100", "24 (2400)", "5", "0.05", "0.016817738931232163", "0.0", "1.0"],
    ["250", "24 (6000)", "7", "0.028", "0.011726921713202328", "0.0", "1.0"],
    ["500", "12 (6000)", "13", "0.026", "0.014717439098661031", "0.0", "1.0"],
    ["1000", "6 (6000)", "20", "0.02", "0.012478702978778226", "0.0", "1.0"],
    ["2500", "3 (7500)", "48", "0.0192", "0.01428914228363267", "0.0", "1.0"],
], widths=[0.6, 1.6, 0.7, 0.7, 1.7, 0.9, 0.9], font=8.2)
CITE("benchmarks/m5-reference.json → sample_size")

H2("12.7 Discrimination experiment (noise vs attack at matched marginals)")
TBL(["Population pair", "honest marginal D_m", "malicious marginal D_m", "matched?", "distinguishable?", "verdict"], [
    ["channel_tampering @0.05 vs honest η=0.05", "0.02316666666666667", "0.03383333333333333", "False", "True", "separated by basis-mismatch dispersion (rate 1.0)"],
    ["intercept_resend @0.05 vs honest η=0.05", "0.02316666666666667", "0.0195", "True", "False", "“Not distinguishable under the current observable model.”"],
], widths=[2.0, 1.2, 1.2, 0.7, 0.9, 1.6], font=7.8)
CITE("benchmarks/m5-reference.json → discrimination")
P("The second row is an honest negative result the project reports verbatim: at matched marginal "
  "mismatch rates, intercept–resend at fraction 0.05 is not separable from honest noise using the "
  "current structural descriptor.")
PAGEBREAK()


H1("13. Security Interpretation")
H2("13.1 Assumptions")
P("The assumption register lists 14 assumptions, each with a status of exact / satisfied / "
  "approximate / not-verified / violated and a consequence-if-violated. Homogeneity is exact for "
  "depolarizing (match probability 1−p/2 for every state “by algebra, not by assumption”) and "
  "approximate for flip channels (Poisson-binomial). “APPROXIMATE” is not a synonym for "
  "“SATISFIED”; there is no status meaning “probably fine”.")
CITE("backend/security/assumptions.py:L66-121, L126-361 ; backend/security/models.py:L160-167")
H2("13.2 Observability")
P("The observability matrix records, per threat, whether it causes quantum disturbance, whether "
  "the detector can see it quantum-mechanically, whether it requires a classical control, and the "
  "measured M5 detection/FAR. Protocol-layer attacks are “a threat to the protocol layer”, "
  "protected by classical controls, not by the quantum statistic.")
CITE("backend/security/observability.py:L21-24, L95-232")
H2("13.3 Composition")
P("The composition assessment evaluates each milestone component (M1–M6) with property evaluated, "
  "evidence source, assumption boundary, unresolved dependency and security conclusion. "
  "composition_summary() hard-codes formal_composition_theorem_present = False.")
CITE("backend/security/composition.py:L58-235, L246")
H2("13.4 The claim checker")
P("An in-repo checker rejects forbidden claims and banned terminology. Forbidden claims include "
  "“information-theoretically secure”, “formal forgery bound”, “detects all quantum attacks”, "
  "“the threshold is optimal”, and “FAR is the forgery probability”. Banned terminology includes "
  "“decoy”/“decoy-state” (a QKD mechanism this construction lacks). The allowed claim shape ends: "
  "“These are empirical rates on this dataset at this sample size and channel; they are not a "
  "formal forgery bound and they do not establish security.”")
CITE("backend/security/interpretation.py:L101-152, L155-288, L401-438")
H2("13.5 Finite-size interpretation and boundaries")
P("Finite-size quantities are confidence intervals, classification thresholds and empirical "
  "acceptance rates. A fourth kind — “formal cryptographic security bound” — is explicitly “not "
  "produced by this milestone”. Experimentally demonstrated: honest FRR at/below alpha at the "
  "calibrated channel, detection of the two channel attacks, non-detection of the four protocol "
  "attacks by the quantum statistic, robustness and sample-size behaviour. NOT formally proven: "
  "unforgeability, non-repudiation, transferability, any forgery bound, information-theoretic or "
  "composable security, adaptive-attack resistance, hardware behaviour, and generalisation beyond "
  "the reference configuration.")
CITE("backend/security/models.py:L53-67 ; backend/security/composition.py:L58-235 ; backend/evaluation/reports.py:L60-89")
PAGEBREAK()


H1("14. Limitations")
TBL(["Limitation", "Why it matters", "Evidence", "Impact", "Possible future improvement"], [
    ["Simulation-only validation", "No real quantum hardware; simulated disturbance may differ from physical devices", "backend/quantum/measure.py:L105-132 (Aer only)", "Results do not transfer to hardware", "Run on real QPU / optical testbed"],
    ["No secret signing key", "Without a secret there is no unforgeability; anyone can forge", "backend/protocol/models.py:L188-190; attacks/forgery.py", "Not a deployable signature scheme", "Add a keyed QDS construction with a formal model"],
    ["No formal forgery bound", "No adversary-advantage guarantee exists", "security/composition.py:L105-108", "Security is empirical, not proven", "Define a forgery game and prove/reduce"],
    ["No universal attack coverage", "Only six attack families modelled", "attacks/base.py:L69-77; interpretation.py:L101-152", "Unknown attacks undetected", "Extend the threat model"],
    ["No coherent / adaptive adversary", "Individual attacks only; no quantum memory, no multi-qubit coherent strategy", "attacks/intercept_resend.py:L44-52; channel_tampering.py:L33-38", "Stronger adversaries unmodelled", "Model collective/coherent attacks"],
    ["Classical replay/identity controls", "Replay and authorization are ledger/membership checks, in-memory and single-process", "detection/replay.py:L102-235; observability.py replay note", "Lost on restart; not distributed", "Persistent, distributed nonce/session store"],
    ["Finite-shot stochastic acceptance", "Sampled mode outcomes are stochastic; a tie counts as a match", "simulation/runner.py:L259-299", "Small-shot results vary", "Increase shots / analytic mode"],
    ["Threshold depends on sample size & config", "θ(N) invalid at another N; high noise breaks honest traffic", "calibration/thresholds.py; m5 robustness FRR=1.0 at η=0.10", "Operating point is conditional", "Per-configuration calibration; adaptive thresholds"],
    ["Noise/attack discrimination limits", "intercept_resend @0.05 not separable from honest noise at matched marginals", "m5-reference.json → discrimination", "Low-intensity interception can hide in noise", "Richer descriptors / more shots"],
    ["No formal composability theorem", "Components assessed, not composed under a theorem", "security/composition.py:L246", "No end-to-end compositional guarantee", "Prove a composition theorem"],
], widths=[1.4, 1.6, 1.5, 1.2, 1.4], font=7.6)
PAGEBREAK()


H1("15. Frontend — the Q-TRACE Web Console")
P("The console is React 18 + TypeScript + Vite with recharts charts and a single permanent dark "
  "theme (there is no light/dark switching in the shipped source). Navigation is state-based (no "
  "router library): a FrontPage gate then a seven-view workspace. The API client targets "
  "VITE_API_BASE_URL (default http://127.0.0.1:8000), calls operational endpoints at the root and "
  "business endpoints under /api/v1, and maps every non-2xx to the backend error envelope.")
CITE("frontend/package.json ; frontend/src/api/client.ts ; frontend/src/state/AppContext.tsx ; frontend/src/state/chartPalette.ts")
FIGURE("06_frontend_workflow.png",
       "Figure 15.1 — Console pages, the backend endpoints each calls, and the observable-only "
       "handoff from Simulation Bench to Detection Console.")
TBL(["Page", "Purpose", "Inputs", "Backend endpoint(s)", "Outputs / what the user learns"], [
    ["FrontPage", "Cinematic introduction and entry gate", "none (no API calls; footer links open the backend's /docs and /health in browser tabs)", "none", "The 7-stage pipeline, the evidence-only disclaimer, and a footer with the Q-TRACE brand block plus real in-app and backend-documentation links"],
    ["Dashboard (Console)", "Operational overview", "none", "GET /api/v1/sessions; GET /api/v1/calibration/reference; GET /api/v1/security/observability; /health,/ready,/version", "Readiness, counts, reference operating point, empirical detection/FAR per threat"],
    ["Session Studio", "Drive the signing lifecycle", "message, signer_id, verifier_id, state_count; verify: transcript JSON etc.", "POST/GET /api/v1/sessions; GET /{id}; POST /{id}/sign; POST /{id}/expire; POST /api/v1/verify", "Session detail, transcript + hash, verification flags — consistency, not a security verdict"],
    ["Simulation Bench", "Build and run a noise/attack scenario", "scenario id, ids, message, state_count, shot_count, seed, mode, noise type+strength, attack type+fraction+seed, eval toggle", "POST /api/v1/simulations; POST /api/v1/simulations/evaluation", "A “Running simulation…” spinner while the request is in flight; then per-state P(expected)/matched, mismatch & disturbance, authorization; observable-only handoff"],
    ["Detection Console", "Run the detector on observable evidence", "DetectionRequest JSON; consume_replay toggle", "POST /api/v1/detect", "overall_status, findings with evidence items, diagnostic radar; no security score"],
    ["Calibration Lab", "Derive an honest-only threshold", "config id, noise, state_count, mode, shots, sessions, seed start, confidence; or calibration id", "POST /api/v1/calibration/run; GET /api/v1/calibration/{id}; GET /api/v1/calibration/reference", "k_crit, p_upper, θ, intervals, homogeneity, operating point; validity is sample-size-bound"],
    ["Evaluation Center", "Run and inspect a benchmark", "profile (smoke/reference); evaluation id", "POST /api/v1/evaluation/run; GET /{id}; GET /{id}/artifact", "Per-attack metrics, confusion matrices, FRR-by-noise, heatmap, full artifact"],
    ["Security Argument", "Read the security posture", "noise_type, measurement_mode (assumptions tab); statements (claim checker)", "GET /api/v1/security/assumptions; /observability; /composition; POST /api/v1/security/analyze", "Assumption statuses, observability matrix, composition, ALLOWED/FORBIDDEN verdicts"],
], widths=[1.1, 1.3, 1.6, 1.7, 1.9], font=7.4)
H2("15.1 Branding")
P("The console is branded Q-TRACE. The logo asset is frontend/public/qtrace-logo.png; the HTML "
  "title is “Q-TRACE · Quantum Threat & Reliability Analysis for Cryptographic Evidence”; the "
  "shell header shows the logo, “Q-TRACE”, and the full name. The sidebar footer states the "
  "evidence-only positioning and that data is held in memory and lost on restart. The identifier "
  "“SIH26141” is deliberately kept as a small technical marker, not part of the console identity.")
P("The FrontPage carries a dedicated footer (FrontFooter.tsx): a brand block with the logo, the "
  "full name, a one-line factual description of the framework, and the marker “RQDS-TP-1.0 · "
  "SIH26141”; three link columns that point only at things that actually exist — the console views "
  "(via the app's state navigation), on-page front-page sections, and the configured backend's own "
  "/docs (Swagger) and /health endpoints; an in-memory-prototype note; and a bottom bar reading "
  "“© 2026 Q-TRACE” and “SIH 2026 project prototype • Experimental research and demonstration "
  "platform”. No invented external URLs are used.")
CITE("frontend/index.html ; frontend/src/components/Shell.tsx ; frontend/src/pages/FrontPage.tsx ; frontend/src/components/front/FrontFooter.tsx")
PAGEBREAK()


H1("16. Backend API")
P("The API is a FastAPI application factory (create_app) with settings and store injection, no "
  "module-level globals and no lifespan hook. Business routers mount under /api/v1; the three "
  "operational routers mount at the root. CORS is an explicit allow-list (credentials disabled); "
  "a wildcard origin is refused unless explicitly opted in. Middleware order puts CORS outermost "
  "around a request-correlation middleware that enforces a Content-Length bound and emits one "
  "structured JSON log per request without bodies.")
CITE("backend/api/app.py:L82-123 ; backend/api/version.py:L25-28 ; backend/api/config.py:L132-157 ; backend/api/middleware.py:L109-153")
H2("16.1 Endpoint table")
TBL(["Method", "Route", "Purpose", "Input", "Output"], [
    ["GET", "/health", "Liveness + versions + in-memory counts", "none", "HealthResponse"],
    ["GET", "/version", "Version inventory (app/API/protocol/python/packages)", "none", "VersionResponse"],
    ["GET", "/ready", "Component-import + store readiness probe", "none", "ReadyResponse"],
    ["POST", "/api/v1/sessions", "Create reference signing session (201)", "SessionCreateRequest", "SessionView"],
    ["GET", "/api/v1/sessions", "List sessions", "none", "SessionListResponse"],
    ["GET", "/api/v1/sessions/{id}", "Fetch one session (applies TTL)", "path id", "SessionView"],
    ["POST", "/api/v1/sessions/{id}/sign", "Sign session → transcript + hash", "path id", "SessionSignResponse"],
    ["POST", "/api/v1/sessions/{id}/expire", "Move session to EXPIRED", "path id", "SessionView"],
    ["POST", "/api/v1/verify", "Verify transcript (M2 verifier)", "VerificationRequest", "VerificationResponse"],
    ["POST", "/api/v1/simulations", "Run scenario — observable only", "SimulationRequest", "SimulationResponse (no ground truth)"],
    ["POST", "/api/v1/simulations/evaluation", "Run scenario — includes ground truth", "SimulationRequest", "SimulationEvaluationResponse"],
    ["POST", "/api/v1/detect", "Run detector over observable input", "DetectionRequest (extra=forbid)", "DetectionResponse"],
    ["POST", "/api/v1/calibration/run", "Derive threshold from honest-only data (201)", "CalibrationRunRequest", "CalibrationResponse"],
    ["GET", "/api/v1/calibration/reference", "Reference methodology + recorded operating point", "none", "ReferenceCalibrationResponse"],
    ["GET", "/api/v1/calibration/{id}", "Retrieve stored calibration", "path id", "CalibrationResponse"],
    ["POST", "/api/v1/evaluation/run", "Run benchmark profile (201, synchronous)", "EvaluationRunRequest {profile: smoke|reference}", "EvaluationSummary"],
    ["GET", "/api/v1/evaluation/{id}", "Retrieve evaluation summary", "path id", "EvaluationSummary"],
    ["GET", "/api/v1/evaluation/{id}/artifact", "Retrieve full benchmark artifact", "path id", "EvaluationArtifactResponse"],
    ["GET", "/api/v1/security/assumptions", "Assumption register", "query noise_type, measurement_mode", "AssumptionsResponse"],
    ["GET", "/api/v1/security/observability", "Threat-observability matrix", "none", "ObservabilityResponse"],
    ["GET", "/api/v1/security/composition", "Composition assessment", "none", "CompositionResponse"],
    ["POST", "/api/v1/security/analyze", "Check statements vs forbidden-claim register", "AnalyzeRequest", "AnalyzeResponse"],
], widths=[0.6, 2.1, 1.9, 1.6, 1.6], font=7.4)
H2("16.2 Storage, validation and errors")
P("Storage is entirely in-memory (sessions, calibrations, evaluations, and a shared replay "
  "registry reused from backend.detection.replay); a restart loses everything. A session "
  "lifecycle enum with an explicit allowed-transition map guards state changes (illegal → 409). "
  "Expensive work runs outside the store lock; only publication takes it. Request bodies are "
  "double-validated: once by FastAPI/Pydantic and again against configured limits via "
  "configured_body. Errors use a universal envelope {error:{code,message,request_id,details}}; "
  "validation failures are 422; a catch-all returns 500 and logs the traceback without returning it.")
CITE("backend/api/store.py:L51-81, L103-129, L176-251 ; backend/api/dependencies.py:L47-91 ; backend/api/errors.py:L41-61, L180-224")
NOTE("Documented-but-unused: ErrorCode.SERVICE_UNAVAILABLE (503) is defined but never raised, and "
     "the API reference's status table omits it. Reported as an implementation/documentation "
     "discrepancy, not reconciled.")
PAGEBREAK()


H1("17. Technology Stack (verified)")
TBL(["Category", "Technology", "Version", "Where verified"], [
    ["Language", "Python (CPython)", "3.13.5", "pyproject.toml requires-python>=3.13; benchmark provenance python=3.13.5"],
    ["Quantum SDK", "Qiskit", "2.5.2", "requirements.txt"],
    ["Quantum simulator", "Qiskit-Aer", "0.17.2", "requirements.txt"],
    ["Numerics", "NumPy", "2.5.3", "requirements.txt"],
    ["Scientific", "SciPy", "1.18.1", "requirements.txt (beta.ppf / binom in calibration & statistics)"],
    ["Symbolic", "SymPy", "1.14.0", "requirements.txt"],
    ["Testing", "pytest", "9.1.1", "requirements.txt"],
    ["Web framework", "FastAPI", "0.141.1", "requirements.txt"],
    ["ASGI toolkit", "starlette", "1.6.0", "requirements.txt"],
    ["Validation", "pydantic", "2.13.5", "requirements.txt"],
    ["ASGI server", "uvicorn", "0.53.0", "requirements.txt"],
    ["Async", "anyio", "4.14.2", "requirements.txt"],
    ["Test HTTP", "httpx2", "2.12.0", "requirements.txt (starlette TestClient)"],
    ["Frontend UI", "React / react-dom", "^18.3.1", "frontend/package.json"],
    ["Frontend lang", "TypeScript", "^5.7.2", "frontend/package.json"],
    ["Build tool", "Vite (+ @vitejs/plugin-react)", "^5.4.11 / ^4.3.4", "frontend/package.json"],
    ["Charts", "recharts", "^2.15.0", "frontend/package.json"],
    ["Icons", "lucide-react", "^0.469.0", "frontend/package.json"],
    ["Frontend tests", "vitest", "^3.2.7", "frontend/package.json"],
], widths=[1.3, 2.0, 1.2, 2.6], font=8.2)
NOTE("No machine-learning dependency is present, by design (requirements.txt header, SIH "
     "requirement R7). No sklearn / tensorflow / torch / keras anywhere in backend or frontend.")
PAGEBREAK()


H1("18. Testing and Quality Assurance")
H2("18.1 Organisation")
P("Tests mirror the backend packages: tests/{quantum, protocol, detection, calibration, "
  "evaluation, security, api}. Categories include unit/domain tests, per-layer architecture "
  "guards, milestone acceptance suites, API integration tests (FastAPI TestClient), wiring tests "
  "(AST/inspect guards that services are genuinely wired to settings and domain entry points), "
  "and negative tests (parametrized transcript-tampering lambdas).")
H2("18.2 Architecture and leakage guards")
B("Detection isolation: forbidden imports (backend.attacks/noise/simulation), forbidden field names, AST identifier scan, fresh-interpreter sys.modules check, and identical-observable behavioural tests.")
B("Calibration honesty: calibration configs/observations refuse non-CALIBRATION roles; evaluation refuses the CALIBRATION role; disjoint seed blocks asserted.")
B("Layering: detection must not import backend.quantum; API never imports qiskit; nothing imports the evaluation layer; ground-truth names confined to producers and the evaluation consumer.", level=1)
CITE("tests/detection/test_separation.py ; tests/detection/test_architecture.py ; tests/evaluation/test_leakage.py ; tests/evaluation/test_architecture.py ; tests/api/test_architecture.py ; tests/calibration/test_architecture.py")
H2("18.3 Reproducibility tests")
P("Determinism: identical seed_start and trial_count yield identical statistics, decisions, seeds "
  "and fingerprints; different seed blocks differ. Cache neutrality: the full benchmark run "
  "cached/uncached/cached produces field-identical reports except runtime_seconds and cache "
  "stats, and leaves the transpile cache disabled.")
CITE("tests/evaluation/test_reproducibility.py")
H2("18.4 Mutation testing and coverage")
NOTE("Not present. No mutation-testing tooling (mutmut/cosmic-ray/etc.) exists; the word "
     "“mutation” in tests/protocol/test_negative.py refers to transcript-tampering negative "
     "tests. Coverage is not configured or measured (no --cov, no .coveragerc, no CI). Reported "
     "honestly rather than invented.")
H2("18.5 Test totals (measured)")
TBL(["Scope", "Count", "Note"], [
    ["Backend test functions (grep 'def test_')", "1,546", "api 370 · evaluation 273 · security 269 · protocol 216 · detection 159 · calibration 149 · quantum 110"],
    ["Backend collected (project venv)", "1,848", "excludes tests/api (httpx missing in the measurement venv); parametrize multiplies cases"],
    ["Frontend (vitest run)", "31 passed", "3 files: scenarioForm 17 · client 7 · frameDelta 7"],
], widths=[2.4, 1.0, 3.4], font=8.4)
P("Formulation to quote: 1,546 backend test functions; 1,848 collected excluding the API suite at "
  "measurement time; 31 frontend tests passing. No pass/fail aggregate beyond the frontend run is "
  "claimed.", size=9.5, italic=True)
PAGEBREAK()


H1("19. Demo Workflow for Judges")
H2("Step 1 — Start the backend")
B("What to run: from the repo root, uvicorn backend.api.app:create_app --factory (or python -m uvicorn ...). Port 8000.")
B("Expected output: server up; GET /health returns status ok with api_version v1 and protocol_version RQDS-TP-1.0; GET /ready returns ready true.")
B("Presenter says: the API is a thin boundary over the engines; it adds no quantum or statistical dependency.")
H2("Step 2 — Start the frontend")
B("What to run: cd frontend; npm install; npm run dev. Port 5173 (whitelisted by default CORS).")
B("Expected output: the Q-TRACE FrontPage; connection probe flips to online once /health and /ready respond.")
H2("Step 3 — Session Studio")
B("Click: Session Studio → create. Input: message “transfer 100 units to account 7”, signer alice, verifier bob, state_count 16. Then Sign, then Verify.")
B("Expected output: session detail with nonce, message hash and binding; a signed transcript JSON with transcript_hash; verification accepted with all flags true and the structural caveat note.")
B("Presenter says: verification is consistency and binding, not unforgeability — there is no secret key.")
H2("Step 4 — Simulation Bench")
B("Click: Simulation Bench. Input: state_count 16, measurement mode sampled, shot_count 1; noise depolarizing strength 0.02; then a second run with attack channel_tampering fraction 0.2.")
B("Expected output: while the request is in flight the Run button shows a loading state and a “Running simulation…” spinner card appears; then the honest run shows P(expected)≈0.99 across states and a small mismatch, and the tampered run shows targeted states at P(expected)=0 and a higher mismatch count.")
B("Presenter says: the same physics, one honest and one attacked; the difference is observable disturbance.")
H2("Step 5 — Detection Console")
B("Click: “Send observable data to detector” from Simulation Bench, then run. Optionally toggle consume_replay.")
B("Expected output: honest → CLEAR or low-severity; tampered → a QUANTUM-family finding with evidence items (observed vs expected) and a Clopper–Pearson interval; no security score.")
B("Presenter says: the detector saw only observable evidence — no attack label was passed.")
H2("Step 6 — Calibration Lab")
B("Click: Calibration Lab → run. Input: state_count 100, sessions 8, depolarizing 0.02, confidence 0.95 (smoke scale).")
B("Expected output: k_crit, p_upper, θ and the validity warning that the threshold applies only at this sample size/mode/channel.")
B("Presenter says: thresholds are derived from honest data only and are finite-sample objects.")
H2("Step 7 — Evaluation Center")
B("Click: Evaluation Center → profile smoke → run (seconds). For a full run choose reference (minutes; synchronous).")
B("Expected output: per-attack detection/FAR bars, confusion matrices, FRR-by-noise table, and the full artifact.")
B("Presenter says: smoke numbers are too small to interpret; the committed reference artifact is the citable result.")
H2("Step 8 — Security Argument")
B("Click: each tab. In Claim Checker, submit “The system is 100% secure against all attacks.” and an honest empirical sentence.")
B("Expected output: FORBIDDEN for the first, ALLOWED for the second; the observability matrix shows the 2-vs-4 detection split.")
B("Presenter says: the project ships its own guard-rail against over-claiming.")
PAGEBREAK()


H1("20. Real-World Deployment Path")
H2("20.1 Current prototype (what exists today)")
B("Fully simulated quantum behaviour on a classical machine (Qiskit/Aer).")
B("In-memory storage; no persistence; restart loses all state.")
B("No authentication, no authorization beyond modelled membership sets, no TLS termination, no rate limiting, no audit log (documented as not implemented).")
B("Single-process replay ledger.")
H2("20.2 Future production system (proposed — not implemented)")
B("Real quantum hardware: replace the Aer/simulation seam with physical state preparation, transmission and measurement; re-validate the noise and disturbance model against device data.")
B("Identity and authentication: introduce real credentials/certificates so signer_id/verifier_id are authenticated, not declared.")
B("Key management: introduce a genuine keyed signature/QDS construction with secret material and a formal security model — this is what would enable unforgeability.")
B("Persistent storage: durable sessions, transcripts and calibrations.")
B("Distributed replay prevention: a shared, durable nonce/session consumption store across nodes.")
B("Monitoring and alerting on detection findings and calibration drift.")
B("Scaling: horizontal API workers with shared state; benchmark offloaded to batch compute.")
B("Formal security analysis: forgery game, advantage bounds, composability theorem, stronger (coherent/adaptive) adversary models.")
NOTE("None of the items in 20.2 are implemented. They are the deployment path, clearly separated "
     "from the current prototype.")
PAGEBREAK()


H1("21. Research Foundation")
P("External factual claims are sourced from the repository bibliography "
  "(docs/research/references.md), reproduced in Appendix G. The scientific basis separates "
  "cleanly into established quantum principles, the project's engineering choices, simulation "
  "results, statistical evidence, and (absent) formal cryptographic claims.")
H2("21.1 Quantum teleportation")
P("Teleportation of an unknown qubit using a shared EPR pair and two classical bits is established "
  "physics (Bennett et al., PRL 70, 1895 (1993) [R1]). Q-TRACE implements exactly this primitive "
  "in simulation; the implementation fact is that the correction and branch structure were "
  "verified numerically and on Aer.")
H2("21.2 QDS literature")
P("Foundational QDS and the memory-free line of work motivate the design: QDS without quantum "
  "memory (Dunjko, Wallden, Andersson, PRL 112, 040502 (2014) [R2]); its experimental realization "
  "(Collins et al., PRL 113, 040502 (2014) [R3]); and QDS built from QKD components (Wallden, "
  "Dunjko, Kent, Andersson, PRA 91, 042304 (2015) [R4]/[R10]). These are the cited papers' "
  "properties; Q-TRACE transfers no security claim from them.")
H2("21.3 Statistical confidence intervals")
P("Exact binomial intervals are Clopper–Pearson (Clopper & Pearson, Biometrika 26(4), 404 (1934) "
  "[R12]); the concentration cross-check is Hoeffding (Hoeffding, JASA 58(301), 13 (1963) [R11]); "
  "the implemented-but-unused multiple-comparison procedure is Holm (Holm, Scand. J. Statist. 6(2), "
  "65 (1979) [R13]). These are statements about estimators, not about adversaries.")
H2("21.4 Classification of claims in this report")
TBL(["Kind", "Meaning", "Example in this report"], [
    ["SOURCE-DERIVED FACT", "Taken from cited literature", "Teleportation needs one EPR pair + 2 classical bits [R1]"],
    ["IMPLEMENTATION FACT", "Verified in code / by execution", "p_match ≡ F for a pure expected state (density.py:L14-23)"],
    ["ENGINEERING CHOICE", "A design decision, not a standard", "The hash→state nibble-rejection mapping (encoding.py:L9-10)"],
    ["INTERPRETATION", "A reading of evidence, hedged", "“evidence of inconsistency, not attribution of a cause”"],
    ["(absent) FORMAL CLAIM", "Deliberately not made", "No forgery bound, no IT-security proof"],
], widths=[1.5, 2.0, 3.1], font=8.4)
PAGEBREAK()


H1("22. What Q-TRACE Actually Proves")
FIGURE("08_demonstrated_matrix.png",
       "Figure 22.1 — Three-way classification of what is demonstrated and what is not proven.")
H2("A. Demonstrated by code / tests")
B("The quantum primitives are correct and reproducible: eigenstate table, |Φ+⟩, teleportation with feed-forward correction, Born-rule measurement (tests/quantum/*, verified on Aer).")
B("p_match = Tr(P_ψρ) ≡ F = ⟨ψ|ρ|ψ⟩ for a pure expected state (density.py; fidelity.py).")
B("Canonical binding and deterministic, unbiased state-sequence derivation (protocol tests).")
B("Detector label-independence, enforced structurally, statically, at runtime and behaviourally (test_separation.py).")
B("Exact Clopper–Pearson intervals and an honest-null, sample-size-specific threshold; Hoeffding cross-check (calibration, finite_size).")
B("The API surface, in-memory lifecycle, error envelope and CORS behaviour (tests/api/*).")
H2("B. Demonstrated only under the simulated experimental model")
B("Intercept–resend and channel tampering detected at rate 1.0 with FAR 0.0 at fraction 0.20, N=500, η=0.02 (m5-reference).")
B("Honest FRR 0.0 at the calibrated channel; 0.5833 at η=0.05; 1.0 at η=0.10.")
B("Sample-size behaviour over N=100…2,500 with per-size recalibration.")
B("Channel tampering @0.05 separable from honest noise via basis-mismatch dispersion; intercept–resend @0.05 not separable at matched marginals.")
B("All of the above are finite-sample, configuration-dependent and simulation-only.")
H2("C. Not proven / out of scope")
B("Unforgeability, non-repudiation, transferability (no secret key; keyless forgery verifies).")
B("Any formal forgery bound or adversary-advantage guarantee.")
B("Information-theoretic, composable, unconditional or device-independent security.")
B("Shor's algorithm and RSA/DSA/ECDSA (not implemented; background only).")
B("Coherent / multi-qubit / adaptive adversaries; quantum memory.")
B("Hardware validation; official/standardised QDS protocol status.")
B("Universal attack detection; threshold-as-security-parameter.")
PAGEBREAK()


H1("23. Final Technical Assessment")
H2("23.1 One-sentence technical definition")
P("Q-TRACE is a quantum-simulation-backed, model-based statistical threat-detection and "
  "evidence platform for a teleportation-based reference signature construction: it simulates "
  "six-state Pauli encoding and Bell teleportation under honest Pauli noise and six modelled "
  "attacks, extracts only verifier-observable evidence, and applies exact finite-sample binomial "
  "statistics to decide whether an observed session is inconsistent with honest behaviour — "
  "while explicitly refusing to claim machine learning, formal security, or unforgeability.")
H2("23.2 The central innovation / idea")
P("The central idea is discipline, not a new algorithm: separate ground truth from observable "
  "evidence so thoroughly that the detector cannot cheat; separate the one primary statistic "
  "from diagnostics so the decision cannot be quietly gerrymandered; and separate empirical "
  "measurement from formal proof so the report cannot over-claim. The quantum disturbance of "
  "intercept–resend and channel tampering becomes a measurable, calibratable signal, while "
  "protocol-layer threats are honestly routed to classical controls.")
H2("23.3 The evidence the system produces")
P("Per-event: categorical findings with observed-vs-expected evidence items and exact confidence "
  "intervals, plus integrity/authorization/replay evidence. Per-experiment: FAR/FRR/detection "
  "rates, confusion matrices, eight reference curves, robustness and discrimination grids, and a "
  "sample-size study — all reproducible from a seed and committed as an artifact.")
H2("23.4 The strongest limitations")
P("Simulation-only validation; absence of any secret key (hence no unforgeability); no formal "
  "forgery bound or composability theorem; the quantum statistic's blindness to the four "
  "protocol-layer attacks; and thresholds that are conditional on sample size and channel, with "
  "honest traffic rejected outright once noise exceeds the calibrated level.")
PAGEBREAK()


H1("24. Glossary")
TBL(["Term", "Plain-English explanation"], [
    ["Qubit", "The smallest unit of quantum information; a two-level system described by a unit vector (or density matrix)."],
    ["Bell state", "A maximally entangled two-qubit state; |Φ+⟩ = (|00⟩+|11⟩)/√2 is the one used here."],
    ["Teleportation", "Moving an unknown qubit state to a distant qubit using shared entanglement plus two classical bits, without sending the qubit itself."],
    ["Pauli operator", "The three basic single-qubit operations X, Y, Z (plus identity I); their eigenstates form the six-state alphabet."],
    ["Eigenstate", "A state that a given operator leaves unchanged except for a scale factor (the eigenvalue); measuring an eigenstate in its own basis is deterministic."],
    ["Density matrix", "A matrix description of a quantum state that can represent mixtures and noise, not just pure vectors."],
    ["Projective measurement", "Measuring in a chosen basis; the probability of an outcome is the Born rule Tr(P ρ)."],
    ["Fidelity", "Overlap between the expected pure state and the actual (possibly mixed) state: F = ⟨ψ|ρ|ψ⟩. Here identical to the projective match probability."],
    ["Mismatch rate (D_m)", "The fraction of verified states whose measurement did not match the expected outcome — the primary detection statistic."],
    ["Calibration", "Measuring what honest behaviour looks like (from honest-only data) so a threshold can be set before judging real events."],
    ["False rejection (FRR)", "An honest session wrongly rejected."],
    ["False acceptance (FAR)", "A malicious trial wrongly accepted (empirical acceptance rate, not a forgery probability)."],
    ["Replay", "Re-presenting a previously valid transcript/nonce; detected by remembering what was already consumed, not by quantum disturbance."],
    ["Intercept–resend", "An eavesdropper measures each qubit and re-sends a fresh one; wrong-basis guesses disturb the state detectably."],
    ["Finite-size analysis", "Reasoning about statistics at a specific, finite sample size, with explicit confidence, instead of assuming infinite data."],
    ["QDS", "Quantum Digital Signatures: signature schemes whose security rests on quantum mechanics rather than computational hardness."],
    ["Classical cryptography", "Cryptography (e.g. RSA/DSA/ECDSA) whose security rests on hard math problems; broken by Shor's algorithm on a large quantum computer."],
    ["Shor's algorithm", "A quantum algorithm that factors integers and solves discrete logs efficiently; the reason classical public-key crypto is at risk. Not implemented here."],
], widths=[1.5, 5.1], font=8.6)
PAGEBREAK()


H1("Appendix A — Repository Structure")
TBL(["Path", "Contents"], [
    ["backend/quantum/", "states, bell, teleport, correction, density, measure, cache (M1 quantum core)"],
    ["backend/protocol/", "binding, canonical, encoding, session, signer, verifier, transcript, reference_qds, models (M2)"],
    ["backend/noise/", "base + depolarizing, bit_flip, phase_flip, bit_phase_flip (honest channels)"],
    ["backend/attacks/", "base + forgery, impersonation, unauthorized_verification, replay, intercept_resend, channel_tampering (M3)"],
    ["backend/simulation/", "scenario, seed, runner, results (M3 experiment harness)"],
    ["backend/detection/", "features, mismatch, fidelity, disturbance, consistency, authorization, replay, statistics, evidence, decision, engine, models (M4)"],
    ["backend/calibration/", "baseline, confidence, thresholds, multiple_testing, operating_points, models (M5)"],
    ["backend/evaluation/", "benchmark, harness, datasets, metrics, confusion, curves, sweeps, robustness, discrimination, reports, models (M5)"],
    ["backend/security/", "assumptions, observability, composition, finite_size, threat_bounds, interpretation, models (M6)"],
    ["backend/api/", "app, config, context, dependencies, errors, middleware, store, version + routes/ + schemas/ + services/ (M7)"],
    ["frontend/", "React/TS/Vite console (M8): src/pages, src/components, src/api, src/state, src/lib"],
    ["tests/", "7 packages mirroring backend + api integration/wiring suites"],
    ["benchmarks/", "m5-reference.json, m5-reference.md, run_reference_benchmark.py"],
    ["docs/", "api/, protocol/, security/, research/ (incl. SIH26141.pdf, consensus-research.md, references.md)"],
    ["README.md", "Repository-root project overview: problem statement, architecture summary, setup and usage instructions"],
], widths=[1.6, 5.0], font=8.4)

H1("Appendix B — API Endpoint Reference")
P("See Section 16.1 for the full method/route/purpose/input/output table. Operational endpoints "
  "(/health, /version, /ready) mount at the root; all business endpoints mount under /api/v1. "
  "Error envelope: {error:{code,message,request_id,details}} with codes BAD_REQUEST(400), "
  "NOT_FOUND(404), CONFLICT(409), PAYLOAD_TOO_LARGE(413), UNPROCESSABLE_ENTITY(422), "
  "INTERNAL_ERROR(500); SERVICE_UNAVAILABLE(503) is defined but never raised.")

H1("Appendix C — Attack Matrix")
FIGURE("07_attack_evidence_matrix.png",
       "Figure C.1 — Attack-to-evidence matrix: which observable carries each attack's signal, with "
       "the measured detection split.")
TBL(["Attack", "Quantum disturbance?", "Detection mechanism", "Measured detection / FAR (m5)"], [
    ["Forgery", "No", "Binding + state-sequence re-derivation (classical integrity)", "0.0 / 1.0 (quantum statistic)"],
    ["Impersonation", "No", "Authorization membership test (classical)", "0.0 / 1.0 (quantum statistic)"],
    ["Unauthorized verification", "No", "Authorization membership test (classical)", "0.0 / 1.0 (quantum statistic)"],
    ["Replay", "No", "In-memory nonce/session ledger (classical, cross-event)", "0.0 / 1.0 (quantum statistic)"],
    ["Intercept–resend", "Yes", "Elevated mismatch rate D_m (quantum)", "1.0 / 0.0"],
    ["Channel tampering", "Yes", "Elevated mismatch rate D_m (quantum)", "1.0 / 0.0"],
], widths=[1.6, 1.1, 2.4, 1.6], font=8.2)

H1("Appendix D — Statistical Equations")
TBL(["#", "Equation", "Where implemented"], [
    ["5.1", "message_hash = SHA256(utf8(NFC(message)))", "protocol/binding.py, canonical.py"],
    ["5.2", "binding = SHA256(canonical{domain, version, session, nonce, message})", "protocol/binding.py"],
    ["5.3", "block_k = SHA256(seed‖domainuint32(k)); accept nibble<12; idx = nibble mod 6", "protocol/encoding.py"],
    ["4.1", "|Φ+⟩ = (|00⟩+|11⟩)/√2", "quantum/bell.py"],
    ["4.2", "U(m0,m1) = Z^m0 · X^m1", "quantum/correction.py"],
    ["4.3", "p_match = Tr(P_ψ ρ)", "quantum/density.py"],
    ["4.4", "F = ⟨ψ|ρ|ψ⟩", "quantum/density.py"],
    ["6.1", "E(ρ) = Σ_p p_P · P ρ P", "noise/base.py"],
    ["6.2", "T(ρ,σ) = ½ Σ|eig(ρ−σ)|", "noise/base.py"],
    ["6.3", "p_match(honest, depol η) = 1 − η/2", "calibration/baseline.py"],
    ["9.1", "D_m = N_mismatch / N_valid", "detection/mismatch.py"],
    ["9.3", "D_v = N_disturbed / N_valid; disturbed ⟺ p < 1−1e-9", "detection/disturbance.py"],
    ["10.1", "H0: N_mismatch ~ Binomial(N, p0)", "calibration/baseline.py"],
    ["10.2", "Clopper–Pearson L,U via Beta quantiles", "calibration/confidence.py, detection/statistics.py"],
    ["10.3", "ε = sqrt(ln(m/α)/(2n))  (Hoeffding, cross-check)", "security/finite_size.py"],
    ["10.4", "p_upper; k_crit(N); θ(N)=k_crit/N; reject if N_mismatch>k_crit", "calibration/thresholds.py"],
    ["FWER", "1 − (1−α)^k", "calibration/multiple_testing.py"],
], widths=[0.6, 3.6, 2.4], font=8.0)

H1("Appendix E — Test and Benchmark Evidence")
P("Test totals: 1,546 backend test functions (api 370, evaluation 273, security 269, protocol 216, "
  "detection 159, calibration 149, quantum 110); 1,848 collected in the project venv excluding the "
  "API suite (httpx absent at measurement time); 31 frontend vitest tests passing. Coverage and "
  "mutation testing are not configured. Benchmark evidence: benchmarks/m5-reference.json "
  "(runtime 1504.86 s, 479 scenarios, 37 disjoint seed blocks, cache hit_rate 0.99998) with the "
  "operating point, attack evaluation, robustness, sample-size, discrimination and threshold "
  "tables reproduced in Sections 10–12.")

H1("Appendix F — Implementation Evidence Index")
TBL(["Claim", "File", "Function / Class", "Lines", "What it proves"], [
    ["Six Pauli eigenstates", "backend/quantum/states.py", "_DEFINITIONS / get_eigenstate", "L95-135", "Exact eigenstate table; P|ψ⟩=λ|ψ⟩"],
    ["Bell state |Φ+⟩", "backend/quantum/bell.py", "bell_circuit / bell_amplitudes_exact", "L31-58", "Entangled resource equals (|00⟩+|11⟩)/√2"],
    ["Teleportation circuit", "backend/quantum/teleport.py", "teleport_circuit", "L85-127", "CX/H/measure + conditional correction sequence"],
    ["Pauli correction convention", "backend/quantum/correction.py", "CORRECTION_TABLE / append_conditional_correction", "L74-137", "U=Z^m0·X^m1 as real feed-forward"],
    ["p_match ≡ F", "backend/quantum/density.py", "p_match / fidelity_pure", "L14-23, L87-117", "Same overlap quantity two ways; not independent evidence"],
    ["Born-rule measurement + rotations", "backend/quantum/measure.py", "add_basis_rotation / run_counts", "L56-132", "Basis rotation to Z; single Aer execution path; reproducibility"],
    ["SHA-256 canonical binding", "backend/protocol/binding.py", "compute_message_binding", "L56-99", "Domain-separated named-field binding"],
    ["Unbiased state-sequence derivation", "backend/protocol/encoding.py", "nibble_stream / derive_alphabet_indices", "L130-166", "Rejection sampling unbiased over 6 states; engineering choice"],
    ["No secret key", "backend/protocol/models.py", "Session / Transcript", "L188-246", "No key field anywhere; unforgeability not claimed"],
    ["Verifier never trusts signer", "backend/protocol/verifier.py", "ReferenceVerifier.verify", "L188-380", "Independent recomputation; structural caveat"],
    ["Pauli channel apply", "backend/noise/base.py", "QuantumChannel.apply", "L189-206", "Analytic density-matrix channel, trace-preserving/Hermitian guarded"],
    ["Measure-and-reprepare", "backend/attacks/intercept_resend.py", "_intercept", "L123-142", "Genuine Born-rule interception, not random replacement"],
    ["Coherent Pauli tampering", "backend/attacks/channel_tampering.py", "apply", "L100-137", "P ρ P† on a selected fraction"],
    ["Observable/ground-truth split", "backend/simulation/results.py", "ObservableExperimentData / GroundTruthMetadata", "L114-174", "Detector-consumable vs evaluation-only halves"],
    ["Mismatch rate", "backend/detection/mismatch.py", "analyse_mismatch", "L89-153", "D_m with honest denominator hygiene"],
    ["Exact binomial interval", "backend/detection/statistics.py", "exact_binomial_interval", "L67-104", "Clopper–Pearson via scipy beta.ppf"],
    ["Categorical decision, no score", "backend/detection/decision.py", "decide", "L161-197", "Family-based status; no security score"],
    ["Primary vs diagnostic", "backend/calibration/multiple_testing.py", "REFERENCE_PRIMARY_TEST / DIAGNOSTIC_METRICS", "L14-83", "Exactly one tested statistic"],
    ["Honest-null threshold", "backend/calibration/thresholds.py", "derive_threshold / critical_count", "L96-218", "p_upper → k_crit(N) → θ(N); sample-size bound"],
    ["Hoeffding cross-check", "backend/security/finite_size.py", "hoeffding_radius", "L212-231", "sqrt(ln(m/α)/2n); looser, never the threshold"],
    ["Claim checker", "backend/security/interpretation.py", "FORBIDDEN_CLAIMS / check_statement", "L101-388", "Rejects over-claims and banned terminology"],
    ["No composition theorem", "backend/security/composition.py", "composition_summary", "L246", "formal_composition_theorem_present = False"],
    ["App factory + CORS", "backend/api/app.py", "create_app", "L82-123", "Factory DI; CORS allow-list outermost"],
    ["In-memory store + replay reuse", "backend/api/store.py", "ApiStore", "L103-129", "No DB; reuses M4 ReplayRegistry"],
    ["Anti-leakage tests", "tests/detection/test_separation.py", "—", "L48-300", "Structural/static/runtime/behavioural label independence"],
], widths=[1.5, 1.6, 1.6, 0.9, 1.9], font=7.4)

H1("Appendix G — References")
refs = [
    ("[R1]", "C. H. Bennett, G. Brassard, C. Crépeau, R. Jozsa, A. Peres, W. K. Wootters, “Teleporting an Unknown Quantum State via Dual Classical and Einstein-Podolsky-Rosen Channels,” Physical Review Letters 70, 1895–1899 (1993). DOI 10.1103/PhysRevLett.70.1895"),
    ("[R2]", "V. Dunjko, P. Wallden, E. Andersson, “Quantum Digital Signatures without Quantum Memory,” Physical Review Letters 112, 040502 (2014). DOI 10.1103/PhysRevLett.112.040502"),
    ("[R3]", "R. J. Collins, R. J. Donaldson, V. Dunjko, P. Wallden, P. J. Clarke, E. Andersson, J. Jeffers, G. S. Buller, “Realization of Quantum Digital Signatures without the Requirement of Quantum Memory,” Physical Review Letters 113, 040502 (2014). DOI 10.1103/PhysRevLett.113.040502"),
    ("[R4]", "P. Wallden, V. Dunjko, A. Kent, E. Andersson, “Quantum Digital Signatures with Quantum-Key-Distribution Components,” Physical Review A 91, 042304 (2015). DOI 10.1103/PhysRevA.91.042304"),
    ("[R5]", "IBM Quantum Learning, “Quantum Teleportation.” https://quantum.cloud.ibm.com/learning/en/modules/computer-science/quantum-teleportation"),
    ("[R6]", "IBM Quantum, “Quantum Teleportation — Basics of Quantum Information.” https://qiskit.qotlabs.org/learning/courses/basics-of-quantum-information/entanglement-in-action/quantum-teleportation"),
    ("[R7]", "IBM Quantum, “Qiskit SDK API Documentation.” https://docs.quantum.ibm.com/api/qiskit"),
    ("[R8]", "Egreen Quanta LLP, “Quantum-Inspired Cyber Threat Detection for Digital Signature Security,” Smart India Hackathon Problem Statement 26141. Local: docs/research/SIH26141.pdf"),
    ("[R9]", "Consensus Research Synthesis (project research synthesis). Local: docs/research/consensus-research.md. Note: claims must be traced to primary literature before being treated as established."),
    ("[R10]", "Same paper as [R4] (Wallden et al., PRA 91, 042304 (2015)), cited under a second number for finite-size reasoning; it is one paper, not two."),
    ("[R11]", "W. Hoeffding, “Probability Inequalities for Sums of Bounded Random Variables,” Journal of the American Statistical Association 58(301), 13–30 (1963). DOI 10.1080/01621459.1963.10500830"),
    ("[R12]", "C. J. Clopper, E. S. Pearson, “The Use of Confidence or Fiducial Limits Illustrated in the Case of the Binomial,” Biometrika 26(4), 404–413 (1934). DOI 10.1093/biomet/26.4.404"),
    ("[R13]", "S. Holm, “A Simple Sequentially Rejective Multiple Test Procedure,” Scandinavian Journal of Statistics 6(2), 65–70 (1979)."),
]
for tag, body in refs:
    p = doc.add_paragraph()
    r = p.add_run(tag + "  ")
    r.bold = True; r.font.size = Pt(9)
    r2 = p.add_run(body)
    r2.font.size = Pt(9)
    p.paragraph_format.space_after = Pt(4)
P("Claims NOT transferred from the literature: no forgery probability, security parameter or "
  "composability claim is transferred from [R1]–[R4]/[R10]; [R11]–[R13] are statements about "
  "estimators, not adversaries; the project derives no formal forgery bound "
  "(docs/research/references.md:L204-229).", size=9, italic=True)

add_header_footer()
doc.save(OUT)
print("SAVED", OUT)

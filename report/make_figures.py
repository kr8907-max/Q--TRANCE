"""Generate the eight technical diagrams for the Q-TRACE report.

Clean, professional box/flow diagrams using plain rectangles (reliable geometry).
All content is grounded in the repository source of truth.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
import os

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

INK = "#1b2430"; SLATE = "#3d4a5c"; MUTED = "#6b7787"; LINE = "#9aa6b4"; PANEL = "#f4f6f9"
QUANT = "#1f6f8b"; QUANT_BG = "#e3f0f4"
CLASS = "#9a6b1f"; CLASS_BG = "#f7eeda"
STAT = "#3f6b3f"; STAT_BG = "#e6f0e6"
API = "#4a4a8a"; API_BG = "#e8e8f4"
FE = "#7a3f6b"; FE_BG = "#f3e6ef"
DANGER = "#a33a3a"; DANGER_BG = "#f6e3e3"
OK = "#2f6b3a"; OK_BG = "#e4f0e5"
WARN = "#9a6b1f"; WARN_BG = "#f7eeda"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "text.color": INK,
    "savefig.dpi": 200, "savefig.bbox": "tight", "savefig.facecolor": "white",
})


def new_ax(w, h, xlim=(0, 100), ylim=(0, 100)):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.axis("off")
    return fig, ax


def rect(ax, x, y, w, h, fc=PANEL, ec=LINE, lw=1.1, zorder=1):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                           linewidth=lw, zorder=zorder))


def txt(ax, x, y, s, fs=8, color=INK, weight="normal", ha="center", va="center",
        style="normal", zorder=4, ls=1.35, mono=False):
    ax.text(x, y, s, ha=ha, va=va, fontsize=fs, color=color, weight=weight,
            style=style, zorder=zorder, linespacing=ls,
            family="DejaVu Sans Mono" if mono else "DejaVu Sans")


def box(ax, x, y, w, h, s, fc=PANEL, ec=LINE, tc=INK, fs=8, weight="normal",
        ha="center", va="center", lw=1.1, zorder=1, ls=1.35):
    rect(ax, x, y, w, h, fc=fc, ec=ec, lw=lw, zorder=zorder)
    txt(ax, x + w / 2 if ha == "center" else x + 0.6, y + h / 2, s, fs=fs,
        color=tc, weight=weight, ha=ha, va=va, zorder=zorder + 2, ls=ls)


def arrow(ax, x1, y1, x2, y2, color=SLATE, lw=1.4, rad=0.0, ls="-", zorder=3):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=11, linewidth=lw, color=color,
                                 linestyle=ls, zorder=zorder,
                                 connectionstyle=f"arc3,rad={rad}"))


def title(ax, s, fs=12.5):
    top = ax.get_ylim()[1]
    txt(ax, 50, top - 1.0, s, fs=fs, weight="bold", va="top")


def save(fig, name):
    p = os.path.join(OUT, name); fig.savefig(p); plt.close(fig); print("wrote", p)





def fig_architecture():
    fig, ax = new_ax(11.5, 7.6, (0, 100), (0, 66))
    title(ax, "Q-TRACE end-to-end pipeline and component layers")

    stages = [
        ("Message", CLASS, CLASS_BG), ("Session /\nBinding", CLASS, CLASS_BG),
        ("Quantum State\nGeneration", QUANT, QUANT_BG), ("Bell-State\nTeleportation", QUANT, QUANT_BG),
        ("Noise / Attack\nSimulation", QUANT, QUANT_BG), ("Measurement\n(Born rule)", QUANT, QUANT_BG),
        ("Observable\nEvidence", STAT, STAT_BG), ("Detection", STAT, STAT_BG),
        ("Calibration /\nStatistics", STAT, STAT_BG), ("Evaluation", STAT, STAT_BG),
        ("Security\nInterpretation", STAT, STAT_BG),
    ]
    n = len(stages); bw, bh, gap = 8.2, 8.0, 0.9
    total = n * bw + (n - 1) * gap
    x0 = (100 - total) / 2; ytop = 52
    for i, (lbl, ec, fc) in enumerate(stages):
        x = x0 + i * (bw + gap)
        box(ax, x, ytop, bw, bh, lbl, fc=fc, ec=ec, fs=6.0, weight="bold")
        if i < n - 1:
            arrow(ax, x + bw, ytop + bh / 2, x + bw + gap, ytop + bh / 2, lw=1.2)
    txt(ax, x0, ytop + bh + 1.4, "Processing pipeline (one signing / verification / detection event)",
        fs=7.6, color=MUTED, style="italic", ha="left")

    dx = x0 + 6 * (bw + gap) - gap / 2
    ax.plot([dx, dx], [ytop - 1.2, ytop + bh + 1.2], color=LINE, lw=1.0, ls=":")


    txt(ax, 4, 45.5, "Component layers (which kind of mechanism each stage is)",
        fs=9.4, weight="bold", ha="left")
    layers = [
        ("1. QUANTUM", QUANT, QUANT_BG,
         "Six Pauli eigenstates, |Φ+⟩ Bell\npair, teleportation, Pauli\ncorrection Z^m0·X^m1, density-\nmatrix simulation, projective\nmeasurement, Pauli channels.\n\nbackend/quantum\nbackend/noise"),
        ("2. CLASSICAL PROTOCOL", CLASS, CLASS_BG,
         "SHA-256 message binding,\nsession id + nonce (CSPRNG),\ndeterministic state sequence,\ncanonical transcript, authorization\nmembership, replay ledger.\n\nbackend/protocol · backend/attacks\nbackend/detection/{replay,auth}"),
        ("3. STATISTICAL", STAT, STAT_BG,
         "Mismatch rate D_m, Clopper–\nPearson interval, honest-null\nthreshold k_crit(N), Hoeffding\ncross-check, FAR/FRR, primary-\nvs-diagnostic.  No ML.\n\nbackend/detection · calibration\nbackend/evaluation"),
        ("4. API / INFRA", API, API_BG,
         "FastAPI application factory,\n/api/v1 routes, Pydantic schemas\n(extra=\"forbid\"), in-memory store,\nCORS allow-list, JSON error\nenvelope, request-id middleware.\n\nbackend/api"),
        ("5. FRONTEND", FE, FE_BG,
         "React 18 + TypeScript + Vite\nconsole, recharts, single dark\ntheme, observable-only handoff\nto the detector, connection\nprobe (/health, /ready, /version).\n\nfrontend/src"),
    ]
    colw, colgap = 18.4, 1.2; cx0 = 4
    top = 42.0; hdr_h = 3.2; body_h = 26.0
    for i, (hdr, ec, fc, body) in enumerate(layers):
        x = cx0 + i * (colw + colgap)
        rect(ax, x, top - hdr_h - body_h, colw, body_h, fc=fc, ec=ec, lw=1.1)
        rect(ax, x, top - hdr_h, colw, hdr_h, fc=ec, ec=ec, lw=0, zorder=2)
        txt(ax, x + colw / 2, top - hdr_h / 2, hdr, fs=7.6, weight="bold",
            color="white", zorder=3)
        txt(ax, x + 1.0, top - hdr_h - 1.4, body, fs=6.4, ha="left", va="top",
            ls=1.45, zorder=3)
    txt(ax, 50, 1.6,
        "Ground truth (attack_type, attack_fraction, noise strength) never crosses into the detector — see the observable-evidence pipeline.",
        fs=7.6, color=DANGER, style="italic")
    save(fig, "01_architecture.png")





def fig_teleportation():
    fig, ax = new_ax(11.5, 6.8, (0, 100), (0, 60))
    title(ax, "Quantum teleportation of one signature state  (backend/quantum/teleport.py, correction.py)")

    txt(ax, 3, 50, "q0  |ψ⟩  (signature state)", fs=8.4, color=QUANT, weight="bold", ha="left")
    txt(ax, 3, 46.5, "q1  Alice ─┐  Bell pair |Φ+⟩ = (|00⟩+|11⟩)/√2", fs=8.4, color=SLATE, ha="left")
    txt(ax, 3, 43, "q2  Bob   ─┘", fs=8.4, color=SLATE, ha="left")

    steps = [
        (4, "1. Prepare\n|ψ⟩ on q0", QUANT_BG, QUANT),
        (27, "2. H(q1), CX(q1,q2)\n→ |Φ+⟩ on (q1,q2)", QUANT_BG, QUANT),
        (50, "3. CX(q0,q1)\nthen H(q0)", QUANT_BG, QUANT),
        (73, "4. Measure\nq0→m1, q1→m0", CLASS_BG, CLASS),
    ]
    for x, lbl, fc, ec in steps:
        box(ax, x, 30, 21, 9, lbl, fc=fc, ec=ec, fs=7.6, weight="bold")
    for i in range(3):
        arrow(ax, steps[i][0] + 21, 34.5, steps[i + 1][0], 34.5, lw=1.4)

    box(ax, 50, 15, 21, 8, "classical bits (m0,m1)\neach branch prob. 1/4", fc=CLASS_BG, ec=CLASS, fs=7.4, weight="bold")
    arrow(ax, 83.5, 30, 66, 23, color=CLASS, lw=1.4, rad=0.2)
    txt(ax, 78, 26.5, "public", fs=7.2, color=CLASS, style="italic")

    box(ax, 76, 15, 21, 8, "5. Pauli correction\nU = Z^m0 · X^m1", fc=QUANT_BG, ec=QUANT, fs=7.6, weight="bold")
    arrow(ax, 71, 19, 76, 19, color=CLASS, lw=1.4)
    box(ax, 76, 3, 21, 8, "Bob holds |ψ⟩ exactly\nin all 4 branches", fc=OK_BG, ec=OK, fs=7.8, weight="bold", tc=OK)
    arrow(ax, 86.5, 15, 86.5, 11, color=QUANT, lw=1.4)

    txt(ax, 4, 22, "Branch table (verified on Aer):", fs=8.0, weight="bold", ha="left")
    rows = [("(m0,m1)", "Bob before correction", "after Z^m0·X^m1"),
            ("(0,0)", "|ψ⟩", "|ψ⟩"), ("(0,1)", "X|ψ⟩", "|ψ⟩"),
            ("(1,0)", "Z|ψ⟩", "|ψ⟩"), ("(1,1)", "XZ|ψ⟩ = −ZX|ψ⟩", "|ψ⟩")]
    for i, r in enumerate(rows):
        yy = 19.5 - i * 3.1
        b = "bold" if i == 0 else "normal"
        txt(ax, 5, yy, r[0], fs=7.2, weight=b, ha="left", mono=True)
        txt(ax, 16, yy, r[1], fs=7.2, weight=b, ha="left", mono=True)
        txt(ax, 38, yy, r[2], fs=7.2, weight=b, ha="left", mono=True)
    txt(ax, 50, 55.5,
        "The signer teleports a publicly-derivable eigenstate; Bob's qubit is measured by the verifier, not the signer.",
        fs=7.6, color=MUTED, style="italic")
    save(fig, "02_teleportation.png")





def fig_threat_taxonomy():
    fig, ax = new_ax(11.5, 7.2, (0, 100), (0, 64))
    title(ax, "Threat taxonomy: six modelled attacks, two detection regimes")

    box(ax, 30, 56, 40, 5, "SIH26141 modelled threat surface", fc=PANEL, ec=SLATE, fs=9.2, weight="bold")
    box(ax, 4, 47, 42, 5, "CLASSICAL PROTOCOL EVIDENCE", fc=CLASS, ec=CLASS, tc="white", fs=8.8, weight="bold")
    box(ax, 54, 47, 42, 5, "QUANTUM-CHANNEL DISTURBANCE", fc=QUANT, ec=QUANT, tc="white", fs=8.8, weight="bold")
    arrow(ax, 42, 56, 25, 52, lw=1.3)
    arrow(ax, 58, 56, 75, 52, lw=1.3)

    classical = [
        ("Forgery", "re-bind / full-forge a transcript\nusing the PUBLIC derivation",
         "binding + state-sequence\nre-derivation (no key exists)"),
        ("Impersonation", "present an unauthorized signer_id",
         "authorization membership test\n— NOT by measurement"),
        ("Unauthorized verification", "present an unauthorized verifier_id",
         "authorization membership test\n— NOT by measurement"),
        ("Replay", "re-present an identical transcript\n(quantum evidence unchanged)",
         "in-memory nonce/session ledger\n(cross-event state)"),
    ]
    quantum = [
        ("Intercept–resend", "Eve measures in a basis and\nre-prepares the eigenstate",
         "wrong-basis guess → P(expected)=0.5\n→ elevated mismatch rate D_m"),
        ("Channel tampering", "apply coherent Pauli P ρ P†\nto a fraction of states",
         "anticommuting Pauli → P(expected)=0\n→ elevated mismatch rate D_m"),
    ]

    def col(items, x0, ec, fc, ystart):
        y = ystart
        for name, cap, det in items:
            box(ax, x0, y, 15, 7.4, name, fc=fc, ec=ec, fs=7.6, weight="bold")
            rect(ax, x0 + 16, y, 26, 7.4, fc="white", ec=ec, lw=1.0)
            txt(ax, x0 + 17, y + 6.4, cap, fs=6.5, ha="left", va="top", ls=1.3)
            txt(ax, x0 + 17, y + 2.6, "detected by: " + det, fs=6.3, ha="left",
                va="top", ls=1.3, color=ec, style="italic")
            y -= 8.6
    col(classical, 4, CLASS, CLASS_BG, 38)
    col(quantum, 54, QUANT, QUANT_BG, 38)

    box(ax, 4, 2.0, 42, 6.0,
        "Measured (m5-reference): detection 0.0, FAR 1.0 by the\nquantum statistic — caught only by classical controls",
        fc=WARN_BG, ec=WARN, fs=7.2, weight="bold")
    box(ax, 54, 2.0, 42, 6.0,
        "Measured (m5-reference, fraction 0.20):\ndetection 1.0 (12/12), FAR 0.0",
        fc=OK_BG, ec=OK, fs=7.4, weight="bold", tc=OK)
    save(fig, "03_threat_taxonomy.png")





def fig_evidence_pipeline():
    fig, ax = new_ax(11.5, 7.0, (0, 100), (0, 62))
    title(ax, "Observable-evidence pipeline and the anti-leakage boundary")

    box(ax, 3, 42, 26, 13,
        "SIMULATION RUNNER\nbackend/simulation\n\nproduces BOTH halves\nof every experiment",
        fc=PANEL, ec=SLATE, fs=8.0, weight="bold")
    box(ax, 3, 24, 26, 14,
        "GROUND TRUTH\n(GroundTruthMetadata)\nis_malicious · attack_type\nattack_fraction · noise_type\nnoise_strength · simulator_seed\nscenario_id (encodes fraction)\n\n→ evaluation layer ONLY",
        fc=DANGER_BG, ec=DANGER, fs=6.9, weight="normal")
    txt(ax, 16, 39.4, "must never reach the detector", fs=7.2, color=DANGER, weight="bold", style="italic")

    box(ax, 38, 30, 26, 25,
        "OBSERVABLE EVIDENCE\n(ObservableExperimentData)\n\nper-state: basis, expected_bit,\n  probability_expected, matched\nmismatch_count · mismatch_prop.\nmean_channel_disturbance\nbasis_counts\nverification flags\nauthorization observations\n\n“if a legitimate verifier cannot\nsee it, it is not here”",
        fc=STAT_BG, ec=STAT, fs=6.9, weight="bold")
    arrow(ax, 29, 48, 38, 46, lw=1.5)
    arrow(ax, 29, 31, 38, 36, color=DANGER, lw=1.5, ls=(0, (3, 3)))
    ax.plot([31.5, 35.5], [31.5, 35.0], color=DANGER, lw=2.4, zorder=5)
    ax.plot([31.5, 35.5], [35.0, 31.5], color=DANGER, lw=2.4, zorder=5)

    box(ax, 71, 30, 26, 25,
        "DETECTION ENGINE\nbackend/detection\n\nconsistency re-computation\nauthorization membership\nreplay ledger\nfeatures → findings → decide\n\nNO attack_type field\nNO attack_fraction field\nNO ground-truth label\n(import of backend.attacks\nis forbidden by test)",
        fc=API_BG, ec=API, fs=6.9, weight="bold")
    arrow(ax, 64, 42.5, 71, 42.5, color=STAT, lw=1.7)
    txt(ax, 67.5, 44.2, "observable only", fs=6.8, color=STAT, style="italic")

    rect(ax, 3, 4, 94, 16, fc="white", ec=SLATE, lw=1.1)
    txt(ax, 5, 18.4,
        "Anti-leakage enforced three ways (tests/detection/test_separation.py, tests/evaluation/test_leakage.py):\n"
        "  • STRUCTURAL — ObservableDetectionInput has no attack/noise/seed field; forbidden field names asserted absent.\n"
        "  • STATIC — AST scan forbids importing backend.attacks / backend.noise / backend.simulation and naming GroundTruthMetadata.\n"
        "  • RUNTIME + BEHAVIOURAL — a fresh interpreter importing backend.detection leaves those modules unloaded; two scenarios with\n"
        "    byte-identical observables but different ground truth must produce JSON-identical detect() results.",
        fs=7.0, ha="left", va="top", ls=1.55)
    save(fig, "04_evidence_pipeline.png")





def fig_calibration_flow():
    fig, ax = new_ax(11.5, 6.8, (0, 100), (0, 60))
    title(ax, "Calibration → detection → evaluation  (finite-sample statistics)")

    rect(ax, 3, 36, 28, 18, fc=STAT_BG, ec=STAT, lw=1.2)
    txt(ax, 4.2, 52.4, "1. HONEST CALIBRATION", fs=8.2, weight="bold", color=STAT, ha="left")
    txt(ax, 4.2, 49.6,
        "backend/calibration\nH0: N_mismatch ~ Binomial(N, p0)\nhonest-only sessions (role enforced)\npooled_rate = Σmismatch / Σvalid\none-sided Clopper–Pearson bound\n  p_upper = Beta⁻¹(1−α_cal; K+1, T−K)",
        fs=6.8, ha="left", va="top", ls=1.45)

    rect(ax, 3, 16, 28, 17, fc=STAT_BG, ec=STAT, lw=1.2)
    txt(ax, 4.2, 31.4, "2. THRESHOLD DERIVATION", fs=8.2, weight="bold", color=STAT, ha="left")
    txt(ax, 4.2, 28.6,
        "method: honest-null-quantile-with-\nupper-confidence-bound\nk_crit(N) = min{k : P[Binom(N,p_upper)≤k]\n                 ≥ 1−α_eval}\nθ(N) = k_crit / N  (sample-size specific)\nα split: α_cal + α_eval = α (0.025+0.025)",
        fs=6.8, ha="left", va="top", ls=1.45)
    arrow(ax, 17, 36, 17, 33, color=STAT, lw=1.5)

    rect(ax, 37, 24, 26, 24, fc=API_BG, ec=API, lw=1.2)
    txt(ax, 38.2, 46.4, "3. DETECTION", fs=8.2, weight="bold", color=API, ha="left")
    txt(ax, 38.2, 43.6,
        "backend/detection\nPRIMARY statistic:\n  D_m = N_mismatch / N_valid\n  tested against k_crit(N)\nDIAGNOSTIC (reported,\n  never adjudicated):\n  disturbance rate D_v, fidelity\n  (= match prob.), per-basis rates,\n  replay, authorization, consistency\ndecision is CATEGORICAL,\nno security score",
        fs=6.8, ha="left", va="top", ls=1.45)
    arrow(ax, 31, 24.5, 37, 32, color=STAT, lw=1.5)

    rect(ax, 69, 30, 28, 18, fc=QUANT_BG, ec=QUANT, lw=1.2)
    txt(ax, 70.2, 46.4, "4. EVALUATION", fs=8.2, weight="bold", color=QUANT, ha="left")
    txt(ax, 70.2, 43.6,
        "backend/evaluation\npositive class = “decision REJECTED”\nFAR = malicious accepted / malicious\nFRR = honest rejected / honest\ndetection_rate = TP / (TP+FN)\n8 reference curves (no ROC/PR\nby design); robustness ·\ndiscrimination · sample-size",
        fs=6.8, ha="left", va="top", ls=1.45)
    arrow(ax, 63, 36, 69, 39, color=API, lw=1.5)

    rect(ax, 69, 12, 28, 15, fc=WARN_BG, ec=WARN, lw=1.2)
    txt(ax, 70.2, 25.4, "5. SECURITY INTERPRETATION", fs=7.8, weight="bold", color=WARN, ha="left")
    txt(ax, 70.2, 22.6,
        "backend/security\nassumption register · observability\nmatrix · composition assessment\nclaim checker (forbidden claims /\nbanned terminology, e.g. “decoy”)\nfinite-size bound flagged\n  is_cryptographic_security_bound=False",
        fs=6.6, ha="left", va="top", ls=1.4)
    arrow(ax, 83, 30, 83, 27, color=QUANT, lw=1.5)

    rect(ax, 3, 2, 62, 11, fc="white", ec=SLATE, lw=1.1)
    txt(ax, 4.2, 11.4,
        "Reference operating point “m5-reference” (committed artifact benchmarks/m5-reference.json):\n"
        "  N = 500 · sampled · 1 shot/state · depolarizing η = 0.02 · α = 0.05 · 120 calibration sessions (seeds 0–119)\n"
        "  pooled_rate = 0.010 · p_upper = 0.010828629491245854 · k_crit = 10 · θ = 0.02 · observed calibration FRR = 0.0",
        fs=6.9, ha="left", va="top", ls=1.5)
    save(fig, "05_calibration_flow.png")





def fig_frontend():
    fig, ax = new_ax(11.5, 7.2, (0, 100), (0, 64))
    title(ax, "Q-TRACE web console: pages, backend endpoints, and the demo handoff")

    box(ax, 30, 56, 40, 5, "FrontPage → “Enter Security Console” → Dashboard", fc=FE_BG, ec=FE, fs=8.2, weight="bold")

    pages = [
        ("Session Studio", "POST /api/v1/sessions\nGET  /api/v1/sessions/{id}\nPOST /api/v1/sessions/{id}/sign\nPOST /api/v1/sessions/{id}/expire\nPOST /api/v1/verify",
         "create → sign → verify → expire;\nverification is consistency, not a verdict"),
        ("Simulation Bench", "POST /api/v1/simulations\nPOST /api/v1/simulations/evaluation",
         "build a noise/attack scenario;\nobservable-only handoff to detector"),
        ("Detection Console", "POST /api/v1/detect",
         "run detector on observable evidence;\nfindings, no security score"),
        ("Calibration Lab", "POST /api/v1/calibration/run\nGET  /api/v1/calibration/{id}\nGET  /api/v1/calibration/reference",
         "derive honest-only threshold;\nvalid only at its sample size"),
        ("Evaluation Center", "POST /api/v1/evaluation/run\nGET  /api/v1/evaluation/{id}\nGET  /api/v1/evaluation/{id}/artifact",
         "smoke / reference benchmark;\nFAR·FRR·detection, confusion matrix"),
        ("Security Argument", "GET  /api/v1/security/assumptions\nGET  /api/v1/security/observability\nGET  /api/v1/security/composition\nPOST /api/v1/security/analyze",
         "assumptions · observability ·\ncomposition · claim checker"),
    ]
    bw, bh = 30, 21
    positions = [(3, 28), (35, 28), (67, 28), (3, 4), (35, 4), (67, 4)]
    for (name, eps, learns), (x, y) in zip(pages, positions):
        rect(ax, x, y, bw, bh, fc="white", ec=FE, lw=1.1)
        rect(ax, x, y + bh - 3.6, bw, 3.6, fc=FE, ec=FE, lw=0, zorder=2)
        txt(ax, x + bw / 2, y + bh - 1.8, name, fs=8.2, weight="bold", color="white", zorder=3)
        txt(ax, x + 1.2, y + bh - 4.6, eps, fs=6.3, color=API, ha="left", va="top", ls=1.5, mono=True, zorder=3)
        txt(ax, x + 1.2, y + 7.4, learns, fs=6.5, color=MUTED, ha="left", va="top", ls=1.4, style="italic", zorder=3)
        arrow(ax, 50, 56, x + bw / 2, y + bh, color=LINE, lw=0.9)

    arrow(ax, 35, 38.5, 67, 38.5, color=OK, lw=1.7, rad=-0.06)
    txt(ax, 51, 40.4, "“Send observable data to detector” (never carries ground truth)",
        fs=6.8, color=OK, style="italic")
    txt(ax, 50, 1.0,
        "React 18 + TypeScript + Vite · single permanent dark theme · recharts · connection probe polls /health, /ready, /version every 8 s",
        fs=7.2, color=MUTED)
    save(fig, "06_frontend_workflow.png")





def fig_attack_matrix():
    fig, ax = new_ax(11.0, 5.8, (0, 100), (0, 54))
    title(ax, "Attack-to-evidence matrix (which observable carries the signal)")

    attacks = ["Forgery", "Imperson-\nation", "Unauth.\nverification", "Replay", "Intercept–\nresend", "Channel\ntampering"]
    evidence = ["Quantum-channel disturbance", "Mismatch rate D_m",
                "Transcript / binding integrity", "State-sequence re-derivation",
                "Authorization membership", "Replay ledger (nonce/session)"]
    M = [
        [0, 0, 0, 0, 2, 2],
        [0, 0, 0, 0, 2, 2],
        [2, 0, 0, 1, 0, 0],
        [2, 0, 0, 1, 0, 0],
        [0, 2, 2, 0, 0, 0],
        [0, 0, 0, 2, 0, 0],
    ]
    x0, y0 = 34, 8
    cw, ch = 9.4, 5.6
    for j, a in enumerate(attacks):
        txt(ax, x0 + j * cw + cw / 2, y0 + len(evidence) * ch + 1.2, a, fs=6.8,
            weight="bold", va="bottom", ls=1.2)
    for i, e in enumerate(evidence):
        yy = y0 + (len(evidence) - 1 - i) * ch + ch / 2
        txt(ax, x0 - 1.5, yy, e, fs=7.0, ha="right")
    for i in range(len(evidence)):
        for j in range(len(attacks)):
            v = M[i][j]
            xx = x0 + j * cw
            yy = y0 + (len(evidence) - 1 - i) * ch
            if v == 2:
                fc, ec, mark, mc = OK, OK, "●", "white"
            elif v == 1:
                fc, ec, mark, mc = WARN_BG, WARN, "◐", WARN
            else:
                fc, ec, mark, mc = "#f0f2f5", LINE, "", None
            rect(ax, xx, yy, cw - 0.5, ch - 0.5, fc=fc, ec=ec, lw=1.0)
            if mark:
                txt(ax, xx + (cw - 0.5) / 2, yy + (ch - 0.5) / 2, mark, fs=9, color=mc)
    ax.plot([x0, x0 + 4 * cw - 0.5], [y0 - 1.0, y0 - 1.0], color=CLASS, lw=2.0)
    txt(ax, x0 + 2 * cw, y0 - 2.6, "classical protocol evidence", fs=7.2, color=CLASS, weight="bold")
    ax.plot([x0 + 4 * cw, x0 + 6 * cw - 0.5], [y0 - 1.0, y0 - 1.0], color=QUANT, lw=2.0)
    txt(ax, x0 + 5 * cw, y0 - 2.6, "quantum-channel evidence", fs=7.2, color=QUANT, weight="bold")
    txt(ax, x0 + 6 * cw + 2.0, y0 + len(evidence) * ch / 2,
        "● primary signal\n◐ contributes\n\nMeasured detection\n(m5-reference):\nclassical four → 0.0\nquantum two → 1.0",
        fs=6.9, va="center", ha="left", ls=1.5)
    save(fig, "07_attack_evidence_matrix.png")





def fig_demonstrated():
    fig, ax = new_ax(11.5, 7.4, (0, 100), (0, 66))
    title(ax, "What Q-TRACE demonstrates — and what it does not prove")

    cols = [
        ("A. DEMONSTRATED BY CODE / TESTS", OK, OK_BG, [
            "Six Pauli eigenstates, |Φ+⟩, teleportation with\nPauli feed-forward (verified on Aer, reproducible)",
            "p_match = Tr(P_ψ ρ) ≡ F = ⟨ψ|ρ|ψ⟩ (one quantity)",
            "SHA-256 canonical binding; deterministic state\nsequence (unbiased nibble rejection sampling)",
            "Detector consumes observable evidence only;\nlabel independence enforced 3 ways + behaviourally",
            "Clopper–Pearson intervals; honest-null threshold\nk_crit(N); Hoeffding cross-check",
            "FastAPI surface; in-memory store; error envelope",
            "1,546 test functions (1,848 collected excl. API\nsuite); 31 frontend tests; no ML dependency",
        ]),
        ("B. DEMONSTRATED ONLY UNDER THE\nSIMULATED EXPERIMENTAL MODEL", WARN, WARN_BG, [
            "Intercept–resend & channel tampering detected at\nrate 1.0, FAR 0.0 (fraction 0.20, N=500, η=0.02)",
            "Honest FRR 0.0 at the calibrated channel;\nrises to 0.58 (η=0.05) and 1.0 (η=0.10)",
            "Sample-size behaviour over N = 100…2,500\n(5,000/10,000 declared, not simulated: >4,096 cap)",
            "Channel tampering @0.05 distinguishable from\nhonest noise via basis-mismatch dispersion",
            "Intercept–resend @0.05 NOT distinguishable at\nmatched marginals (“not distinguishable” verdict)",
            "All numbers are finite-sample, configuration-\ndependent, simulation-only — not hardware",
        ]),
        ("C. NOT PROVEN / OUT OF SCOPE", DANGER, DANGER_BG, [
            "No secret signing key → no unforgeability\n(a keyless full forgery verifies successfully)",
            "No formal forgery bound, no forgery game,\nno adversary advantage computation",
            "No information-theoretic / composable /\ndevice-independent security proof",
            "No Shor's algorithm; no RSA / DSA / ECDSA\nimplemented (background context only)",
            "No coherent / multi-qubit / adaptive adversary;\nindividual attacks only, no quantum memory",
            "Not hardware validated; not an official Egreen\nQuanta / standardized QDS protocol",
            "No universal attack detection; threshold is not\na cryptographic security parameter",
        ]),
    ]
    cw, gap = 31.0, 1.5
    x0 = (100 - (3 * cw + 2 * gap)) / 2
    top, hdr_h, body_h = 60.0, 5.4, 52.0
    for i, (hdr, ec, fc, items) in enumerate(cols):
        x = x0 + i * (cw + gap)
        rect(ax, x, top - hdr_h - body_h, cw, body_h, fc=fc, ec=ec, lw=1.3)
        rect(ax, x, top - hdr_h, cw, hdr_h, fc=ec, ec=ec, lw=0, zorder=2)
        txt(ax, x + cw / 2, top - hdr_h / 2, hdr, fs=7.6, weight="bold",
            color="white", zorder=3, ls=1.25)
        yy = top - hdr_h - 2.4
        for it in items:
            txt(ax, x + 1.6, yy, "▪", fs=8, color=ec, va="top", zorder=3)
            txt(ax, x + 3.4, yy, it, fs=6.7, va="top", ha="left", zorder=3, ls=1.4)
            yy -= (it.count("\n") + 1) * 2.9 + 2.0
    save(fig, "08_demonstrated_matrix.png")


if __name__ == "__main__":
    fig_architecture()
    fig_teleportation()
    fig_threat_taxonomy()
    fig_evidence_pipeline()
    fig_calibration_flow()
    fig_frontend()
    fig_attack_matrix()
    fig_demonstrated()
    print("ALL DIAGRAMS DONE")

# -*- coding: utf-8 -*-
"""Standalone, publication-quality architecture diagram for Q-TRACE.

Rendered with matplotlib only (vector-precise boxes/arrows, no AI artwork).
Output: report/figures/01_architecture_v2.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures", "01_architecture_v2.png")

W, H = 16.5, 12.2
fig, ax = plt.subplots(figsize=(W, H), dpi=200)
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("#F7F9FB")
ax.set_facecolor("#F7F9FB")

INK = "#1B2430"
MUTED = "#5C6773"
MONO = "DejaVu Sans Mono"

KIND = {
    "quantum":    dict(fill="#E1EEF3", edge="#1F6F8B", head="#1F6F8B"),
    "protocol":   dict(fill="#F6EEDC", edge="#A8760F", head="#A8760F"),
    "channel":    dict(fill="#F9E9E7", edge="#A33A3A", head="#A33A3A"),
    "stat":       dict(fill="#E8F1E8", edge="#3E7A3E", head="#3E7A3E"),
    "api":        dict(fill="#E9E9F6", edge="#4C4C9E", head="#4C4C9E"),
    "front":      dict(fill="#F4E7F0", edge="#9E3E77", head="#9E3E77"),
    "neutral":    dict(fill="#EEF1F4", edge="#5C6773", head="#5C6773"),
}

HDR = 0.34
TAGDY = 0.50
BULDY = 0.235
CHIP_H = 0.26
CHIP_PITCH = 0.32


def box(x, y, w, h, kind, title, tag=None, bullets=(), chips=(), title_size=10.5):
    c = KIND[kind]
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.0,rounding_size=0.10",
        linewidth=1.5, edgecolor=c["edge"], facecolor=c["fill"], zorder=2))
    ax.add_patch(FancyBboxPatch(
        (x, y + h - HDR), w, HDR,
        boxstyle="round,pad=0.0,rounding_size=0.10",
        linewidth=0, facecolor=c["head"], zorder=3))
    ax.add_patch(Rectangle((x, y + h - HDR), w, HDR / 2, facecolor=c["head"],
                           linewidth=0, zorder=3))
    ax.text(x + w / 2, y + h - HDR / 2, title, ha="center", va="center",
            color="white", fontsize=title_size, fontweight="bold", zorder=4)
    ty = y + h - 0.40
    if tag:
        ax.text(x + 0.16, ty, tag, ha="left", va="top", fontsize=7.2,
                family=MONO, color=MUTED, zorder=4)
    ty = y + h - 0.62
    for b in bullets:
        if b.startswith("  "):
            ax.text(x + 0.34, ty, b.strip(), ha="left", va="top", fontsize=8.0,
                    color=INK, zorder=4)
        else:
            ax.text(x + 0.18, ty, "•  " + b, ha="left", va="top", fontsize=8.0,
                    color=INK, zorder=4)
        ty -= BULDY
    if chips:
        cx = x + 0.16
        cy = y + h - 0.68 - CHIP_H
        for ch in chips:
            tw = 0.115 * len(ch) + 0.22
            if cx + tw > x + w - 0.12:
                cx = x + 0.16
                cy -= CHIP_PITCH
            ax.add_patch(FancyBboxPatch(
                (cx, cy), tw, CHIP_H,
                boxstyle="round,pad=0.0,rounding_size=0.10",
                linewidth=0.9, edgecolor=c["edge"], facecolor="white", zorder=4))
            ax.text(cx + tw / 2, cy + CHIP_H / 2, ch, ha="center", va="center",
                    fontsize=7.3, color=INK, zorder=5)
            cx += tw + 0.12
    return (x, y, w, h)


def path_arrow(pts, color="#44516B", lw=1.5, ls="-", label=None, lpos=None,
               lcolor=None, size=7.6, ha="center", va="center", rot=0, bbox=True):
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, ls=ls,
                solid_capstyle="round", zorder=6)
    ax.annotate("", xy=pts[-1], xytext=pts[-2],
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                linestyle=ls, shrinkA=0, shrinkB=0,
                                mutation_scale=13), zorder=6)
    if label and lpos:
        kw = dict(bbox=dict(boxstyle="round,pad=0.18", fc="#F7F9FB", ec="none",
                            alpha=0.92)) if bbox else dict()
        ax.text(lpos[0], lpos[1], label, fontsize=size, color=lcolor or color,
                ha=ha, va=va, rotation=rot, zorder=7, **kw)


def double_arrow(p1, p2, color="#44516B", lw=1.6, label=None, lpos=None, size=7.6):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="<|-|>", color=color, lw=lw,
                                shrinkA=0, shrinkB=0, mutation_scale=13), zorder=6)
    if label and lpos:
        ax.text(lpos[0], lpos[1], label, fontsize=size, color=color,
                ha="center", va="center", zorder=7,
                bbox=dict(boxstyle="round,pad=0.18", fc="#F7F9FB", ec="none", alpha=0.92))



ax.text(W / 2, 11.82, "Q-TRACE — System Architecture", ha="center", va="center",
        fontsize=21, fontweight="bold", color=INK)
ax.text(W / 2, 11.46, "Quantum Threat & Reliability Analysis for Cryptographic Evidence   ·   "
        "SIH26141   ·   Smart India Hackathon 2026",
        ha="center", va="center", fontsize=10.5, color=MUTED)


ax.text(0.28, 11.02, "PROCESSING PIPELINE  (one signing / verification / detection event)",
        fontsize=8.6, color=MUTED, fontweight="bold", ha="left", va="center")
stages = ["Message", "Session /\nBinding", "Quantum State\nGeneration", "Bell-State\nTeleportation",
          "Noise / Attack\nSimulation", "Measurement\n(Born rule)", "Observable\nEvidence",
          "Detection", "Calibration /\nStatistics", "Evaluation", "Security\nInterpretation"]
kinds = ["protocol", "protocol", "quantum", "quantum", "channel", "quantum",
         "stat", "stat", "stat", "stat", "neutral"]
sx, sw, gap, sy, sh = 0.28, 1.355, 0.115, 10.20, 0.62
for i, (s, k) in enumerate(zip(stages, kinds)):
    x = sx + i * (sw + gap)
    c = KIND[k]
    ax.add_patch(FancyBboxPatch((x, sy), sw, sh, boxstyle="round,pad=0.0,rounding_size=0.07",
                                linewidth=1.3, edgecolor=c["edge"], facecolor=c["fill"], zorder=2))
    ax.text(x + sw / 2, sy + sh / 2, s, ha="center", va="center", fontsize=7.9,
            color=INK, fontweight="bold", zorder=3, linespacing=1.25)
    if i < len(stages) - 1:
        ax.annotate("", xy=(x + sw + gap - 0.015, sy + sh / 2), xytext=(x + sw + 0.015, sy + sh / 2),
                    arrowprops=dict(arrowstyle="-|>", color="#44516B", lw=1.2,
                                    shrinkA=0, shrinkB=0, mutation_scale=10), zorder=4)
ax.plot([sx + 6 * (sw + gap) - gap / 2] * 2, [sy - 0.14, sy + sh + 0.14],
        color="#A33A3A", lw=1.4, ls=(0, (3, 2)), zorder=5)
ax.text(sx + 6 * (sw + gap) - gap / 2, sy - 0.24, "anti-leakage boundary",
        fontsize=7.2, color="#A33A3A", ha="center", va="top", style="italic")


box(0.28, 9.02, W - 0.56, 1.04, "front",
    "5 · FRONTEND — Q-TRACE WEB CONSOLE",
    tag="frontend/src  ·  React 18 + TypeScript + Vite + recharts  ·  single dark theme  ·  state-based navigation  ·  landing footer + running spinner",
    chips=["Dashboard", "Session Studio", "Simulation Bench", "Detection Console",
           "Calibration Lab", "Evaluation Center", "Security Argument"])


box(0.28, 7.42, W - 0.56, 1.34, "api",
    "4 · API / INFRA — FastAPI BOUNDARY",
    tag="backend/api  ·  app factory + DI  ·  Pydantic schemas (extra=forbid)  ·  JSON error envelope  ·  CORS allow-list  ·  in-memory store  ·  request-id middleware",
    chips=["/health /ready /version", "/api/v1/sessions", "/api/v1/verify",
           "/api/v1/simulations", "/api/v1/detect", "/api/v1/calibration",
           "/api/v1/evaluation", "/api/v1/security"])

double_arrow((W / 2, 9.00), (W / 2, 8.78), label="JSON over HTTP  (VITE_API_BASE_URL)",
             lpos=(W / 2 + 2.7, 8.89))


box(0.28, 4.62, 3.86, 2.36, "protocol",
    "2 · CLASSICAL PROTOCOL", tag="backend/protocol",
    bullets=["SHA-256 message binding",
             "session id + nonce (CSPRNG)",
             "deterministic 6-state sequence",
             "canonical transcript",
             "signer / verifier lifecycle",
             "no secret signing key"])
box(4.30, 4.62, 3.86, 2.36, "quantum",
    "1 · QUANTUM CORE", tag="backend/quantum  (Qiskit 2.5 + Aer)",
    bullets=["six Pauli eigenstates",
             "|Φ+⟩ Bell pair, teleportation",
             "Pauli correction  Z^m0 · X^m1",
             "density-matrix simulation",
             "projective (Born-rule) measurement",
             "p_match ≡ fidelity  F = ⟨ψ|ρ|ψ⟩"])
box(8.32, 4.62, 3.86, 2.36, "channel",
    "CHANNEL — NOISE & ATTACKS", tag="backend/noise  ·  backend/attacks",
    bullets=["honest noise: depolarizing,",
             "  bit / phase / bit-phase flip",
             "channel attacks: intercept–",
             "  resend, coherent Pauli tampering",
             "protocol attacks: forgery,",
             "  impersonation, unauth. verify, replay"])
box(12.34, 4.62, 3.88, 2.36, "neutral",
    "SIMULATION RUNNER", tag="backend/simulation  ·  seeded, cached",
    bullets=["scenario = protocol + noise",
             "  + attack + seed + shots",
             "deterministic for a fixed seed",
             "splits every result into:",
             "  observable evidence  vs",
             "  ground-truth metadata"])

path_arrow([(4.14, 5.80), (4.30, 5.80)])
path_arrow([(8.16, 5.80), (8.32, 5.80)])
path_arrow([(12.18, 5.80), (12.34, 5.80)])
path_arrow([(W / 2 - 3.0, 7.42), (W / 2 - 3.0, 6.98)],
           label="routes → services → engines", lpos=(W / 2 - 3.0, 7.20))


BY = 4.36
ax.plot([0.28, W - 0.28], [BY, BY], color="#A33A3A", lw=1.7, ls=(0, (5, 3)), zorder=5)
ax.text(0.34, BY + 0.06, "ANTI-LEAKAGE BOUNDARY — attack_type, attack_fraction and noise labels never enter the detector",
        fontsize=8.0, color="#A33A3A", ha="left", va="bottom", fontweight="bold", zorder=7,
        bbox=dict(boxstyle="round,pad=0.2", fc="#F7F9FB", ec="none", alpha=0.95))


path_arrow([(13.30, 4.62), (13.30, 4.22), (3.40, 4.22), (3.40, 4.10)],
           color="#3E7A3E", lw=1.8,
           label="observable evidence only  (counts, bases, ids)", lpos=(8.35, 4.22),
           lcolor="#3E7A3E", size=7.4)
ax.add_patch(Rectangle((13.30 - 0.07, BY - 0.07), 0.14, 0.14, angle=45,
                       facecolor="#3E7A3E", edgecolor="white", lw=1.0, zorder=8))

path_arrow([(15.30, 4.62), (15.30, 4.10)], color="#A33A3A", lw=1.6, ls=(0, (4, 2)),
           label="ground truth — evaluation ONLY", lpos=(15.15, 4.22), lcolor="#A33A3A",
           size=7.4, ha="right")
ax.add_patch(Rectangle((15.30 - 0.07, BY - 0.07), 0.14, 0.14, angle=45,
                       facecolor="#A33A3A", edgecolor="white", lw=1.0, zorder=8))


box(0.28, 2.16, 6.32, 1.94, "stat",
    "3 · STATISTICAL — DETECTION ENGINE", tag="backend/detection",
    bullets=["mismatch rate D_m — PRIMARY statistic",
             "fidelity / projective match, basis-wise disturbance — diagnostic",
             "integrity · authorization · replay evidence (classical)",
             "Clopper–Pearson interval per event",
             "categorical decision + evidence items — no security score"])
box(6.80, 2.16, 4.10, 1.94, "stat",
    "CALIBRATION", tag="backend/calibration",
    bullets=["honest-only null baseline p₀",
             "Clopper–Pearson upper bound",
             "k_crit(N), θ(N) at confidence 1−α",
             "FWER multiple-comparison policy",
             "validity bound to sample size/mode"])
box(11.10, 2.16, 5.12, 1.94, "stat",
    "EVALUATION & BENCHMARKING", tag="backend/evaluation",
    bullets=["smoke + reference profiles, disjoint seed blocks",
             "per-attack detection / FAR, confusion matrices",
             "FRR-by-noise, sample-size, discrimination studies",
             "the only consumer of ground-truth metadata"])

path_arrow([(6.80, 3.13), (6.60, 3.13)], color="#3E7A3E", lw=1.6)
ax.text(6.70, 3.13, "threshold θ(N), α", fontsize=7.0, color="#3E7A3E",
        ha="center", va="center", rotation=90, zorder=7)


box(0.28, 0.62, W - 0.56, 1.34, "neutral",
    "SECURITY INTERPRETATION", tag="backend/security",
    chips=["assumption register", "observability matrix", "composition status (no theorem)",
           "finite-size interpretation", "threat bounds", "claim checker (FORBIDDEN over-claims)"])
path_arrow([(3.40, 2.16), (3.40, 1.96)], label="findings + evidence", lpos=(4.62, 2.06), size=7.4)
path_arrow([(13.60, 2.16), (13.60, 1.96)], label="measured bounds", lpos=(14.72, 2.06), size=7.4)


ly = 0.28
legend = [("quantum", "1 quantum"), ("protocol", "2 classical protocol"),
          ("channel", "channel / attacks"), ("stat", "3 statistical"),
          ("api", "4 api / infra"), ("front", "5 frontend")]
lx = 0.34
for k, lab in legend:
    c = KIND[k]
    ax.add_patch(Rectangle((lx, ly - 0.09), 0.26, 0.18, facecolor=c["fill"],
                           edgecolor=c["edge"], lw=1.2, zorder=4))
    ax.text(lx + 0.34, ly, lab, fontsize=8.0, color=INK, va="center", zorder=4)
    lx += 0.34 + 0.082 * len(lab) + 0.30
ax.plot([lx, lx + 0.26], [ly, ly], color="#A33A3A", lw=1.6, ls=(0, (4, 2)), zorder=4)
ax.text(lx + 0.34, ly, "ground-truth path (evaluation only)", fontsize=8.0, color=INK, va="center")
lx += 0.34 + 0.082 * 34 + 0.32
ax.add_patch(Rectangle((lx, ly - 0.07), 0.13, 0.13, angle=45, facecolor="#3E7A3E",
                       edgecolor="white", lw=0.8, zorder=4))
ax.text(lx + 0.26, ly, "anti-leakage gate", fontsize=8.0, color=INK, va="center")

ax.text(W / 2, 0.055, "Detector = model-based statistical inference over quantum-simulation evidence. "
        "No machine learning, no Shor's algorithm, no RSA/DSA/ECDSA implementation, no formal unforgeability proof.",
        fontsize=7.8, color="#A33A3A", ha="center", va="center", style="italic")

fig.savefig(OUT, dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.12)
print("SAVED", OUT)

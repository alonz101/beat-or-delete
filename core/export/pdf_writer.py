from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

VERDICT_COLORS = {
    "CLUB READY":   colors.HexColor("#1a7a3e"),
    "CASUAL OK":    colors.HexColor("#2a7a6e"),
    "MARGINAL":     colors.HexColor("#c97a00"),
    "DO NOT PLAY":  colors.HexColor("#b52b2b"),
}

FLAG_COLOR = colors.HexColor("#555555")


def _verdict_color(verdict: str):
    return VERDICT_COLORS.get(verdict, colors.black)


def write_pdf(results: list[dict], output_path: str) -> str:
    out = Path(output_path)
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", fontSize=16, fontName="Helvetica-Bold", spaceAfter=4)
    sub_style = ParagraphStyle("sub", fontSize=9, fontName="Helvetica", textColor=colors.HexColor("#666666"), spaceAfter=10)
    label_style = ParagraphStyle("label", fontSize=8, fontName="Helvetica-Bold")
    value_style = ParagraphStyle("value", fontSize=8, fontName="Helvetica")

    story = []

    # --- Title ---
    story.append(Paragraph("DJ Audio Quality Report", title_style))
    total = len(results)
    ok = sum(1 for r in results if r.get("verdict") in ("CLUB READY", "CASUAL OK"))
    bad = sum(1 for r in results if r.get("verdict") == "DO NOT PLAY")
    story.append(Paragraph(
        f"{total} files analyzed — {ok} playable, {bad} DO NOT PLAY",
        sub_style
    ))

    # --- Summary table ---
    summary_data = [["#", "File", "Verdict", "Flags"]]
    for i, r in enumerate(results, 1):
        if "error" in r:
            summary_data.append([str(i), r.get("filename", "?"), "ERROR", r["error"]])
            continue
        summary_data.append([
            str(i),
            r["filename"],
            r["verdict"],
            ", ".join(r["flags"]) if r["flags"] else "—",
        ])

    col_widths = [8*mm, 80*mm, 32*mm, 55*mm]
    summary_table = Table(summary_data, colWidths=col_widths, repeatRows=1)

    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#222222")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    # Color verdict cells
    for i, r in enumerate(results, 1):
        if "error" in r:
            continue
        c = _verdict_color(r["verdict"])
        ts.add("TEXTCOLOR", (2, i), (2, i), c)
        ts.add("FONTNAME", (2, i), (2, i), "Helvetica-Bold")

    summary_table.setStyle(ts)
    story.append(summary_table)
    story.append(Spacer(1, 8*mm))

    # --- Per-file detail cards ---
    for i, r in enumerate(results, 1):
        if "error" in r:
            continue

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dddddd")))
        story.append(Spacer(1, 2*mm))

        # File header row
        vc = _verdict_color(r["verdict"])
        verdict_style = ParagraphStyle("vs", fontSize=11, fontName="Helvetica-Bold", textColor=vc)
        name_style = ParagraphStyle("ns", fontSize=10, fontName="Helvetica-Bold")

        header_data = [[
            Paragraph(f"{i}. {r['filename']}", name_style),
            Paragraph(r["verdict"], verdict_style),
        ]]
        header_table = Table(header_data, colWidths=[130*mm, 45*mm])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        story.append(header_table)

        if r["verdict_reasons"]:
            for reason in r["verdict_reasons"]:
                story.append(Paragraph(f"• {reason}", ParagraphStyle("reason", fontSize=7.5, textColor=colors.HexColor("#aa3333"), leftIndent=4)))

        story.append(Spacer(1, 2*mm))

        fmt = r["format"]
        auth = r["authenticity"]
        play = r["playability"]

        # Stats grid
        stats = [
            ["FORMAT", "", "AUTHENTICITY", "", "PLAYABILITY", ""],
            ["Codec", fmt["codec"], "Spectral coverage", f"{auth['spectral_coverage_ratio']*100:.1f}%", "Clipping L/R", f"{play['clipped_samples_L']} / {play['clipped_samples_R']}"],
            ["Sample rate", f"{fmt['sample_rate']} Hz", "Top freq", f"{auth['top_freq_hz']:.0f} Hz", "Peak", f"{play['peak_dbfs']} dBFS"],
            ["Bit depth", f"{fmt['bit_depth']}-bit" if fmt['bit_depth'] else "n/a", "Spectral verdict", auth["spectral_verdict"], "Loudness", f"{play['loudness_lufs']} LUFS"],
            ["Bitrate", f"{round(fmt['bitrate']/1000)}kbps" if fmt['bitrate'] else "n/a", "LAME header", str(auth["lame_header"]), "Dynamic range", f"{play['dynamic_range_db']:.1f} dB"],
            ["Duration", f"{fmt['duration']}s", "Suspected origin", auth["suspected_origin"], "Noise floor", f"{play['noise_floor_dbfs']} dBFS"],
        ]

        stats_table = Table(stats, colWidths=[25*mm, 30*mm, 32*mm, 35*mm, 28*mm, 25*mm])
        stats_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 1), (2, -1), "Helvetica-Bold"),
            ("FONTNAME", (4, 1), (4, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#eeeeee")),
            ("BACKGROUND", (2, 0), (3, 0), colors.HexColor("#eeeeee")),
            ("BACKGROUND", (4, 0), (5, 0), colors.HexColor("#eeeeee")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(stats_table)

        if r["flags"]:
            flags_str = "  ".join(f"[{f}]" for f in r["flags"])
            story.append(Paragraph(flags_str, ParagraphStyle("flags", fontSize=7, textColor=FLAG_COLOR, spaceBefore=2)))

        story.append(Spacer(1, 4*mm))

    doc.build(story)
    return str(out)

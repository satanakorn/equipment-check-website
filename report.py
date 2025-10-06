from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

import io
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def _generate_executive_summary(all_abnormal: dict) -> str:
    """สร้าง Executive Summary สำหรับรายงาน"""
    total_issues = 0
    critical_issues = 0
    sections_with_issues = 0
    
    for section_name, abn_dict in all_abnormal.items():
        if abn_dict:
            sections_with_issues += 1
            for subtype, df in abn_dict.items():
                if isinstance(df, pd.DataFrame) and not df.empty:
                    total_issues += len(df)
                    # ถือว่าเป็น critical ถ้ามี abnormal
                    critical_issues += len(df)
    
    if total_issues == 0:
        return "✅ All network components are operating within normal parameters. No critical issues detected."
    else:
        return f"⚠️ Network inspection detected {total_issues} issues across {sections_with_issues} component types. {critical_issues} require immediate attention."


def generate_report(all_abnormal: dict, include_charts: bool = True):
    """
    สร้าง PDF Report รวม FAN + CPU + MSU + Line + Client + Fiber + EOL + Core
    """

    # ===== Buffer & Document =====
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), 
                           leftMargin=0.5*inch, rightMargin=0.5*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)

    styles = getSampleStyleSheet()

    # ===== Custom Styles =====
    title_center = ParagraphStyle(
        "TitleCenter", parent=styles["Heading1"], alignment=1, spaceAfter=20,
        fontSize=24, textColor=HexColor("#1f77b4")
    )
    date_center = ParagraphStyle(
        "DateCenter", parent=styles["Normal"], alignment=1, spaceAfter=12,
        fontSize=12, textColor=HexColor("#666666")
    )
    section_title_left = ParagraphStyle(
        "SectionTitleLeft", parent=styles["Heading2"], alignment=0, spaceAfter=6,
        fontSize=16, textColor=HexColor("#2c3e50")
    )
    normal_left = ParagraphStyle(
        "NormalLeft", parent=styles["Normal"], alignment=0, spaceAfter=12,
        fontSize=10
    )
    summary_style = ParagraphStyle(
        "SummaryStyle", parent=styles["Normal"], alignment=1, spaceAfter=20,
        fontSize=14, textColor=HexColor("#27ae60")
    )

    elements = []

    # ===== Title & Date =====
    elements.append(Paragraph("🌐 3BB Network Inspection Report", title_center))
    elements.append(
        Paragraph(f"📅 Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", date_center)
    )
    elements.append(Spacer(1, 24))
    
    # ===== Executive Summary =====
    elements.append(Paragraph("📊 Executive Summary", section_title_left))
    summary_text = _generate_executive_summary(all_abnormal)
    elements.append(Paragraph(summary_text, summary_style))
    elements.append(Spacer(1, 24))

    # ===== Sections (CPU มาก่อน FAN) =====
    section_order = ["CPU", "FAN", "MSU", "Line", "Client", "Fiber", "EOL", "Core"]
    light_red = HexColor("#FF9999")
    light_yellow = HexColor("#FFF3CD")
    text_black = colors.black

    for section_name in section_order:
        abn_dict = all_abnormal.get(section_name, {})

        # ข้าม sections ที่ไม่มี abnormal data
        if not abn_dict:
            continue
            
        # ตรวจสอบว่ามี abnormal data จริงหรือไม่
        has_abnormal_data = False
        for subtype, df in abn_dict.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                has_abnormal_data = True
                break
                
        # ข้าม sections ที่ไม่มี abnormal data จริง
        if not has_abnormal_data:
            continue

        elements.append(Paragraph(f"{section_name} Performance", section_title_left))

        for subtype, df in abn_dict.items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            # Section Title
            elements.append(Paragraph(f"{subtype} – Abnormal Rows", section_title_left))
            elements.append(Spacer(1, 6))

            df_show = df.copy()

            # ===== Filter columns =====
            if section_name == "FAN":
                cols_to_show = [
                    "Site Name", "ME", "Measure Object",
                    "Maximum threshold", "Minimum threshold",
                    "Value of Fan Rotate Speed(Rps)"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]

            elif section_name == "CPU":
                cols_to_show = [
                    "Site Name", "ME", "Measure Object",
                    "Maximum threshold", "Minimum threshold",
                    "CPU utilization ratio"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]

            elif section_name == "MSU":
                cols_to_show = [
                    "Site Name", "ME", "Measure Object",
                    "Maximum threshold", "Laser Bias Current(mA)"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]

            elif section_name == "Client":
                cols_to_show = [
                    "Site Name", "ME", "Measure Object",
                    "Maximum threshold(out)", "Minimum threshold(out)", "Output Optical Power (dBm)",
                    "Maximum threshold(in)", "Minimum threshold(in)", "Input Optical Power(dBm)"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]

            elif section_name == "Line":
                cols_to_show = [
                    "Site Name", "ME", "Call ID", "Measure Object",
                    "Threshold", "Instant BER After FEC",
                    "Maximum threshold(out)", "Minimum threshold(out)", "Output Optical Power (dBm)",
                    "Maximum threshold(in)", "Minimum threshold(in)", "Input Optical Power(dBm)",
                    "Route"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]

            elif section_name == "Fiber":
                cols_to_show = [
                    "Begin Time", "End Time", "Site Name", "ME", "Measure Object",
                    "Max Value of Input Optical Power(dBm)",
                    "Min Value of Input Optical Power(dBm)",
                    "Input Optical Power(dBm)", "Max - Min (dB)"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]

            elif section_name == "EOL":
                cols_to_show = [
                    "Link Name", "EOL(dB)", "Current Attenuation(dB)",
                    "Loss current - Loss EOL", "Remark"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]

            elif section_name == "Core":
                cols_to_show = [
                    "Link Name", "Loss between core"
                ]
                df_show = df_show[[c for c in cols_to_show if c in df_show.columns]]


            # ===== Build table_data =====
            if df_show.empty:
                elements.append(Paragraph("⚠️ Data exists but no valid columns to display.", normal_left))
                elements.append(Spacer(1, 12))
                continue

            table_data = [list(df_show.columns)] + df_show.astype(str).values.tolist()
            table = Table(table_data, repeatRows=1)

            style_cmds = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]

            # ===== Highlight logic =====
            if section_name == "CPU" and "CPU utilization ratio" in cols_to_show:
                col_idx = cols_to_show.index("CPU utilization ratio")
                if col_idx < len(df_show.columns):
                    style_cmds.append(("BACKGROUND", (col_idx, 1), (col_idx, -1), light_red))
                    style_cmds.append(("TEXTCOLOR", (col_idx, 1), (col_idx, -1), text_black))

            elif section_name == "FAN" and "Value of Fan Rotate Speed(Rps)" in cols_to_show:
                col_idx = cols_to_show.index("Value of Fan Rotate Speed(Rps)")
                if col_idx < len(df_show.columns):
                    style_cmds.append(("BACKGROUND", (col_idx, 1), (col_idx, -1), light_red))
                    style_cmds.append(("TEXTCOLOR", (col_idx, 1), (col_idx, -1), text_black))

            elif section_name == "MSU" and "Laser Bias Current(mA)" in cols_to_show:
                col_idx = cols_to_show.index("Laser Bias Current(mA)")
                if col_idx < len(df_show.columns):
                    style_cmds.append(("BACKGROUND", (col_idx, 1), (col_idx, -1), light_red))
                    style_cmds.append(("TEXTCOLOR", (col_idx, 1), (col_idx, -1), text_black))

          
          
            elif section_name == "Client":
                nrows = len(df_show) + 1   # header + data
                ncols = len(df_show.columns)
                col_map = {c: i for i, c in enumerate(df_show.columns)}  # ✅ สร้าง map คอลัมน์จริง

                for ridx, row in df_show.iterrows():
                    # Output check
                    try:
                        v = float(row.get("Output Optical Power (dBm)", float("nan")))
                        lo = float(row.get("Minimum threshold(out)", float("nan")))
                        hi = float(row.get("Maximum threshold(out)", float("nan")))
                        if pd.notna(v) and pd.notna(lo) and pd.notna(hi) and (v < lo or v > hi):
                            cidx = col_map.get("Output Optical Power (dBm)")
                            if cidx is not None and 0 <= cidx < ncols and 0 <= ridx+1 < nrows:
                                style_cmds.append(("BACKGROUND", (cidx, ridx+1), (cidx, ridx+1), light_red))
                                style_cmds.append(("TEXTCOLOR", (cidx, ridx+1), (cidx, ridx+1), text_black))
                    except:
                        pass

                    # Input check
                    try:
                        v = float(row.get("Input Optical Power(dBm)", float("nan")))
                        lo = float(row.get("Minimum threshold(in)", float("nan")))
                        hi = float(row.get("Maximum threshold(in)", float("nan")))
                        if pd.notna(v) and pd.notna(lo) and pd.notna(hi) and (v < lo or v > hi):
                            cidx = col_map.get("Input Optical Power(dBm)")
                            if cidx is not None and 0 <= cidx < ncols and 0 <= ridx+1 < nrows:
                                style_cmds.append(("BACKGROUND", (cidx, ridx+1), (cidx, ridx+1), light_red))
                                style_cmds.append(("TEXTCOLOR", (cidx, ridx+1), (cidx, ridx+1), text_black))
                    except:
                        pass

            elif section_name == "Line":
                nrows = len(df_show) + 1   # header + data
                ncols = len(df_show.columns)
                col_map = {c: i for i, c in enumerate(df_show.columns)}

                for ridx, row in df_show.iterrows():
                    # BER check
                    try:
                        ber = float(row.get("Instant BER After FEC", float("nan")))
                        thr = float(row.get("Threshold", float("nan")))
                        if pd.notna(ber) and pd.notna(thr) and ber > thr:
                            cidx = col_map.get("Instant BER After FEC")
                            if cidx is not None and 0 <= cidx < ncols and 0 <= ridx+1 < nrows:
                                style_cmds.append(("BACKGROUND", (cidx, ridx+1), (cidx, ridx+1), light_red))
                                style_cmds.append(("TEXTCOLOR", (cidx, ridx+1), (cidx, ridx+1), text_black))
                    except:
                        pass

                    # Input check
                    try:
                        v = float(row.get("Input Optical Power(dBm)", float("nan")))
                        lo = float(row.get("Minimum threshold(in)", float("nan")))
                        hi = float(row.get("Maximum threshold(in)", float("nan")))
                        if pd.notna(v) and pd.notna(lo) and pd.notna(hi) and (v < lo or v > hi):
                            cidx = col_map.get("Input Optical Power(dBm)")
                            if cidx is not None and 0 <= cidx < ncols and 0 <= ridx+1 < nrows:
                                style_cmds.append(("BACKGROUND", (cidx, ridx+1), (cidx, ridx+1), light_red))
                                style_cmds.append(("TEXTCOLOR", (cidx, ridx+1), (cidx, ridx+1), text_black))
                    except:
                        pass

                    # Output check
                    try:
                        v = float(row.get("Output Optical Power (dBm)", float("nan")))
                        lo = float(row.get("Minimum threshold(out)", float("nan")))
                        hi = float(row.get("Maximum threshold(out)", float("nan")))
                        if pd.notna(v) and pd.notna(lo) and pd.notna(hi) and (v < lo or v > hi):
                            cidx = col_map.get("Output Optical Power (dBm)")
                            if cidx is not None and 0 <= cidx < ncols and 0 <= ridx+1 < nrows:
                                style_cmds.append(("BACKGROUND", (cidx, ridx+1), (cidx, ridx+1), light_red))
                                style_cmds.append(("TEXTCOLOR", (cidx, ridx+1), (cidx, ridx+1), text_black))
                    except:
                        pass

            elif section_name == "Fiber" and "Max - Min (dB)" in cols_to_show:
                col_idx = cols_to_show.index("Max - Min (dB)")
                if col_idx < len(df_show.columns):
                    style_cmds.append(("BACKGROUND", (col_idx, 1), (col_idx, -1), light_red))
                    style_cmds.append(("TEXTCOLOR", (col_idx, 1), (col_idx, -1), text_black))

            elif section_name == "EOL" and "Loss current - Loss EOL" in cols_to_show:
                col_idx = cols_to_show.index("Loss current - Loss EOL")
                if col_idx < len(df_show.columns):
                    style_cmds.append(("BACKGROUND", (col_idx, 1), (col_idx, -1), light_red))
                    style_cmds.append(("TEXTCOLOR", (col_idx, 1), (col_idx, -1), text_black))

            elif section_name == "Core" and "Loss between core" in cols_to_show:
                col_idx = cols_to_show.index("Loss between core")
                if col_idx < len(df_show.columns):
                    style_cmds.append(("BACKGROUND", (col_idx, 1), (col_idx, -1), light_red))
                    style_cmds.append(("TEXTCOLOR", (col_idx, 1), (col_idx, -1), text_black))


            # ===== Apply style & append =====
            table.setStyle(TableStyle(style_cmds))
            elements.append(table)
            elements.append(Spacer(1, 18))

    # ===== Build Document =====
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

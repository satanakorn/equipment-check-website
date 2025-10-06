import os
import sqlite3
import uuid
from datetime import datetime, date
import pytz
import streamlit as st
from streamlit_calendar import calendar
import io, zipfile
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ====== IMPORT ANALYZERS ======
from CPU_Analyzer import CPU_Analyzer
from FAN_Analyzer import FAN_Analyzer
from MSU_Analyzer import MSU_Analyzer
from Line_Analyzer import Line_Analyzer
from Client_Analyzer import Client_Analyzer
from Fiberflapping_Analyzer import FiberflappingAnalyzer
from EOL_Core_Analyzer import EOLAnalyzer, CoreAnalyzer
from Preset_Analyzer import (
    PresetStatusAnalyzer,
    render_preset_ui,
)
from APO_Analyzer import ApoRemnantAnalyzer
from APO_Analyzer import apo_kpi
# from viz import render_visualization, NetworkDashboardVisualizer  # Removed
from table1 import SummaryTableReport
from supabase_config import get_supabase


# ====== CONFIG ======
st.set_page_config(layout="wide")
pd.set_option("styler.render.max_elements", 1_200_000)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
DB_FILE = "files.db"


# ====== DB INIT ======
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upload_date TEXT,
        orig_filename TEXT,
        stored_path TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()


# ====== DB FUNCTIONS ======
def save_file(upload_date: str, file):
    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}_{file.name}"
    stored_path = os.path.join(UPLOAD_DIR, upload_date, stored_name)
    os.makedirs(os.path.dirname(stored_path), exist_ok=True)

    with open(stored_path, "wb") as f:
        f.write(file.getbuffer())

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO uploads (upload_date, orig_filename, stored_path, created_at)
        VALUES (?, ?, ?, ?)
    """, (upload_date, file.name, stored_path, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def list_files_by_date(upload_date: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, orig_filename, stored_path FROM uploads WHERE upload_date=?", (upload_date,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_file(file_id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT stored_path FROM uploads WHERE id=?", (file_id,))
    row = c.fetchone()
    if row:
        try:
            os.remove(row[0])  # ลบไฟล์จากดิสก์
        except FileNotFoundError:
            pass
    c.execute("DELETE FROM uploads WHERE id=?", (file_id,))
    conn.commit()
    conn.close()

def list_dates_with_files():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT upload_date, COUNT(*) FROM uploads GROUP BY upload_date")
    rows = c.fetchall()
    conn.close()
    return rows


# ====== CLEAR SESSION ======
def clear_all_uploaded_data():
    st.session_state.clear()


# ====== ZIP PARSER ======
KW = {
    "cpu": ("cpu",),
    "fan": ("fan",),
    "msu": ("msu",),
    "client": ("client", "client board"),
    "line":  ("line","line board"),       
    "wason": ("wason","log"), 
    "osc": ("osc","osc optical"),      
    "fm":  ("fm","alarm","fault management"),
    "atten": ("optical attenuation report", "optical_attenuation_report"),
    "atten": ("optical attenuation report","optical attenuation"),
    "preset": ("mobaxterm", "moba xterm", "moba"),
}

LOADERS = {
    ".xlsx": pd.read_excel,
    ".xls": pd.read_excel,
    ".txt":  lambda f: f.read().decode("utf-8", errors="ignore"),
}

def _ext(name: str) -> str:
    name = name.lower()
    return next((e for e in LOADERS if name.endswith(e)), "")

def _kind(name):
    n = name.lower()
    hits = [k for k, kws in KW.items() if any(s in n for s in kws)]

    # ---- Priority ----
    if "wason" in hits:
        return "wason"
    if "preset" in hits:
        return "preset"

    # ---- เช็คว่า line ต้องเป็น Excel เท่านั้น ----
    if "line" in hits and (n.endswith(".xlsx") or n.endswith(".xls") or n.endswith(".xlsm")):
        return "line"

    # ---- อื่น ๆ ตามปกติ ----
    for k in ("fan","cpu","msu","client","osc","fm","atten"):
        if k in hits:
            return k

    return hits[0] if hits else None


def find_in_zip(zip_file):
    found = {k: None for k in KW}
    def walk(zf):
        for name in zf.namelist():
            if all(found.values()): 
                return
            if name.endswith("/"): 
                continue
            lname = name.lower()
            if lname.endswith(".zip"):
                try:
                    walk(zipfile.ZipFile(io.BytesIO(zf.read(name))))
                except:
                    pass
                continue
            ext = _ext(lname)
            kind = _kind(lname)
            if not ext or not kind or found[kind]:
                continue
            try:
                with zf.open(name) as f:
                    df = LOADERS[ext](f)
                    print("DEBUG LOADED:", kind, type(df), name)

                # ถ้าเป็น log (.txt) → เก็บเป็น string ใน key "wason_log"
                if kind == "wason":
                    found[kind] = (df, name)   # df = string
                else:
                    found[kind] = (df, name)   # df = DataFrame

            except:
                continue
    walk(zipfile.ZipFile(zip_file))
    return found


def safe_copy(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.copy()
    return obj

# ====== SIDEBAR ======
menu = st.sidebar.radio("เลือกกิจกรรม", [
    "หน้าแรก","Dashboard","CPU","FAN","MSU","Line board","Client board",
    "Fiber Flapping","Loss between Core","Loss between EOL","Preset status","APO Remnant","Summary table & report"
])


# ====== หน้าแรก (Calendar Upload + Run Analysis + Delete) ======
if menu == "หน้าแรก":
    st.subheader("DWDM Monitoring Dashboard")
    st.markdown("#### Upload & Manage Files (ZIP, Excel, TXT) with Calendar")

    chosen_date = st.date_input("Select date", value=date.today())
    files = st.file_uploader(
        "Upload files (ZIP / Excel / TXT)",
        type=["zip", "xlsx", "xls", "xlsm", "txt"],
        accept_multiple_files=True,
        key=f"uploader_{chosen_date}"
    )
    if files:
        if st.button("Upload", key=f"upload_btn_{chosen_date}"):
            # สร้าง Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_files = len(files)
            uploaded_count = 0
            
            for i, file in enumerate(files):
                # อัพเดท status
                status_text.text(f"📤 Uploading {file.name}... ({i+1}/{total_files})")
                
                # อัพเดท progress bar
                progress = (i + 1) / total_files
                progress_bar.progress(progress)
                
                # อัปโหลดไฟล์
                try:
                    save_file(str(chosen_date), file)
                    uploaded_count += 1
                except Exception as e:
                    st.error(f"❌ Failed to upload {file.name}: {e}")
                
                # เพิ่ม delay เล็กน้อยเพื่อให้เห็น progress
                import time
                time.sleep(0.5)
            
            # เสร็จสิ้น
            progress_bar.progress(1.0)
            status_text.text(f"✅ Upload completed! Successfully uploaded {uploaded_count}/{total_files} files")
            
            # แสดงผลลัพธ์
            if uploaded_count == total_files:
                st.success(f"🎉 All {total_files} files uploaded successfully!")
            else:
                st.warning(f"⚠️ Uploaded {uploaded_count}/{total_files} files successfully")
            
            # รีเฟรชหน้า
            time.sleep(2)
            st.rerun()

    st.subheader("Calendar")
    events = []
    for d, cnt in list_dates_with_files():
        events.append({
            "title": f"{cnt} file(s)",
            "start": d,
            "allDay": True,
            "color": "blue"
        })

    calendar_res = calendar(
        events=events,
        options={
            "initialView": "dayGridMonth",
            "height": "400px",
            "selectable": True,
        },
        key="calendar",
    )

    if "selected_date" not in st.session_state:
        st.session_state["selected_date"] = str(date.today())

    clicked_date = None
    if calendar_res and calendar_res.get("callback") == "dateClick":
        iso_date = calendar_res["dateClick"]["date"]
        dt_utc = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        dt_th = dt_utc.astimezone(pytz.timezone("Asia/Bangkok"))
        clicked_date = dt_th.date().isoformat()

    if clicked_date:
        st.session_state["selected_date"] = clicked_date

    selected_date = st.session_state["selected_date"]

    st.subheader(f"Files for {selected_date}")
    files_list = list_files_by_date(selected_date)
    if not files_list:
        st.info("No files for this date")
    else:
        selected_files = []
        for fid, fname, fpath in files_list:
            col1, col2 = st.columns([4, 1])
            with col1:
                checked = st.checkbox(fname, key=f"chk_{fid}")
                if checked:
                    selected_files.append((fid, fname, fpath))
            with col2:
                if st.button("🗑️ Delete", key=f"del_{fid}"):
                    # แสดง Progress bar สำหรับการลบ
                    delete_progress = st.progress(0)
                    delete_status = st.empty()
                    
                    delete_status.text(f"🗑️ Deleting {fname}...")
                    delete_progress.progress(0.5)
                    
                    try:
                        delete_file(fid)
                        delete_progress.progress(1.0)
                        delete_status.text("✅ File deleted successfully!")
                        st.success(f"🗑️ {fname} has been deleted")
                        
                        # รีเฟรชหน้า
                        import time
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Failed to delete {fname}: {e}")
                        delete_progress.progress(0)
                        delete_status.text("❌ Delete failed")

        
        if st.button("Run Analysis", key="analyze_btn"):
            if not selected_files:
                st.warning("Please select at least one file to analyze")
            else:
                # สร้าง Progress bar สำหรับการวิเคราะห์
                analysis_progress = st.progress(0)
                analysis_status = st.empty()
                
                total_files = len(selected_files)
                processed_files = 0
                
                clear_all_uploaded_data()
                
                for i, (fid, fname, fpath) in enumerate(selected_files):
                    # อัพเดท status
                    analysis_status.text(f"🔍 Analyzing {fname}... ({i+1}/{total_files})")
                    
                    # อัพเดท progress bar
                    progress = (i + 1) / total_files
                    analysis_progress.progress(progress)
                    
                    try:
                        lname = fpath.lower()
                        if lname.endswith(".zip"):
                            with open(fpath, "rb") as f:
                                zip_bytes = io.BytesIO(f.read())
                                res = find_in_zip(zip_bytes)
                            # record results from zip
                            for kind, pack in res.items():
                                if not pack:
                                    continue
                                df, zname = pack
                                if kind == "wason":
                                    st.session_state["wason_log"] = df    # ✅ string log
                                    st.session_state["wason_file"] = zname
                                else:
                                    st.session_state[f"{kind}_data"] = df # ✅ DataFrame
                                    st.session_state[f"{kind}_file"] = zname
                            processed_files += 1
                        else:
                            # Direct Excel/TXT file
                            ext = _ext(lname)
                            kind = _kind(lname)
                            if not ext or not kind:
                                raise ValueError("Unsupported file type or cannot infer kind")
                            with open(fpath, "rb") as f:
                                data = LOADERS[ext](f)
                            if kind == "wason":
                                st.session_state["wason_log"] = data
                                st.session_state["wason_file"] = fname
                            else:
                                st.session_state[f"{kind}_data"] = data
                                st.session_state[f"{kind}_file"] = fname
                            processed_files += 1
                        
                    except Exception as e:
                        st.error(f"❌ Failed to analyze {fname}: {e}")
                    
                    # เพิ่ม delay เล็กน้อยเพื่อให้เห็น progress
                    import time
                    time.sleep(0.3)
                
                # เสร็จสิ้นการวิเคราะห์
                analysis_progress.progress(1.0)
                analysis_status.text(f"✅ Analysis completed! Processed {processed_files}/{total_files} files")
                
                # แสดงผลลัพธ์
                if processed_files == total_files:
                    st.success(f"🎉 All {total_files} files analyzed successfully!")
                    st.info("📊 You can now navigate to individual analysis pages to view results")
                else:
                    st.warning(f"⚠️ Analyzed {processed_files}/{total_files} files successfully")
                
                # รีเฟรชหน้า
                time.sleep(2)
                st.rerun()
        
        # ปุ่ม Clear All
        if files_list:
            st.markdown("---")
            if st.button("🗑️ Clear All Uploaded Data", key="clear_all_btn"):
                # แสดง Progress bar สำหรับการลบทั้งหมด
                clear_progress = st.progress(0)
                clear_status = st.empty()
                
                clear_status.text("🗑️ Clearing all uploaded data...")
                clear_progress.progress(0.3)
                
                try:
                    clear_all_uploaded_data()
                    clear_progress.progress(0.8)
                    clear_status.text("✅ All data cleared successfully!")
                    
                    # รีเฟรชหน้า
                    import time
                    time.sleep(1)
                    clear_progress.progress(1.0)
                    st.success("🎉 All uploaded data has been cleared!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Failed to clear data: {e}")
                    clear_progress.progress(0)
                    clear_status.text("❌ Clear operation failed")


elif menu == "CPU":
    if st.session_state.get("cpu_data") is not None:
        # แสดง Progress bar สำหรับการวิเคราะห์ CPU
        cpu_progress = st.progress(0)
        cpu_status = st.empty()
        
        try:
            cpu_status.text("📊 Loading CPU reference data...")
            cpu_progress.progress(0.2)
            
            df_ref = pd.read_excel("data/CPU.xlsx")
            cpu_progress.progress(0.4)
            
            cpu_status.text("🔍 Initializing CPU analyzer...")
            cpu_progress.progress(0.6)
            
            analyzer = CPU_Analyzer(
                df_cpu=safe_copy(st.session_state.get("cpu_data")),
                df_ref=df_ref.copy(),
                ns="cpu"
            )
            cpu_progress.progress(0.8)
            
            cpu_status.text("⚙️ Processing CPU analysis...")
            analyzer.process()
            cpu_progress.progress(1.0)
            
            cpu_status.text("✅ CPU analysis completed!")
            st.session_state["cpu_analyzer"] = analyzer
            
            import time
            time.sleep(1)
            
        except Exception as e:
            st.error(f"❌ An error occurred during CPU analysis: {e}")
            cpu_progress.progress(0)
            cpu_status.text("❌ CPU analysis failed")
    else:
        st.info("📁 Please upload a ZIP file that contains the CPU performance data.")


elif menu == "FAN":
    if st.session_state.get("fan_data") is not None:
        try:
            df_ref = pd.read_excel("data/FAN.xlsx")
            analyzer = FAN_Analyzer(
                df_fan=safe_copy(st.session_state.get("fan_data")),
                df_ref=df_ref.copy(),
                ns="fan"  # namespace สำหรับ cascading_filter
            )
            analyzer.process()
            st.session_state["fan_analyzer"] = analyzer
            st.write("DEBUG set fan_analyzer", st.session_state["fan_analyzer"])

        except Exception as e:
            st.error(f"An error occurred during processing: {e}")
    else:
        st.info("Please upload a FAN file to start the analysis")


elif menu == "MSU":
    if st.session_state.get("msu_data") is not None:
        try:
            df_ref = pd.read_excel("data/MSU.xlsx")
            analyzer = MSU_Analyzer(
                df_msu=safe_copy(st.session_state.get("msu_data")),
                df_ref=df_ref.copy(),
                ns="msu"
            )
            analyzer.process()
            st.session_state["msu_analyzer"] = analyzer
        except Exception as e:
            st.error(f"An error occurred during processing: {e}")
    else:
        st.info("Please upload an MSU file to start the analysis")


elif menu == "Line board":
    st.markdown("### Line Cards Performance")

    df_line = st.session_state.get("line_data")      # ✅ DataFrame
    log_txt = st.session_state.get("wason_log")     # ✅ String

    # gen pmap จาก TXT ถ้ามี
    if log_txt:
        st.session_state["lb_pmap"] = Line_Analyzer.get_preset_map(log_txt)
    pmap = st.session_state.get("lb_pmap", {})

    if df_line is not None:
        try:
            df_ref = pd.read_excel("data/Line.xlsx")
            analyzer = Line_Analyzer(
                df_line=df_line.copy(),   # ✅ ต้องเป็น DataFrame
                df_ref=df_ref.copy(),
                pmap=pmap,
                ns="line",
            )
            analyzer.process()
            st.caption(
                f"Using LINE file: {st.session_state.get('line_file')}  "
                f"{'(with WASON log)' if log_txt else '(no WASON log)'}"
            )
        except Exception as e:
            st.error(f"An error occurred during processing: {e}")
    else:
        st.info("Please upload a ZIP on 'หน้าแรก' that contains a Line workbook")



elif menu == "Client board":
    st.markdown("### Client Board")
    if st.session_state.get("client_data") is not None:
        try:
            # โหลด Reference
            df_ref = pd.read_excel("data/Client.xlsx")
            
            # สร้าง Analyzer
            analyzer = Client_Analyzer(
                df_client=st.session_state.client_data.copy(),
                ref_path="data/Client.xlsx"   # ✅ ให้ class โหลดเอง
            )
            analyzer.process()
            st.session_state["client_analyzer"] = analyzer
            st.caption(f"Using CLIENT file: {st.session_state.get('client_file')}")
        except Exception as e:
            st.error(f"An error occurred during processing: {e}")
    else:
        st.info("Please upload a ZIP on 'หน้าแรก' that contains a Client workbook")


elif menu == "Fiber Flapping":
    st.markdown("### Fiber Flapping (OSC + FM)")

    df_osc = st.session_state.get("osc_data")   # จาก ZIP: .xlsx → DataFrame
    df_fm  = st.session_state.get("fm_data")    # จาก ZIP: .xlsx → DataFrame

    if (df_osc is not None) and (df_fm is not None):
        try:
            analyzer = FiberflappingAnalyzer(
                df_optical=df_osc.copy(),
                df_fm=df_fm.copy(),
                threshold=2.0,   # คงเดิม
                ref_path="data/Flapping.xlsx"  # ใช้ชื่อไฟล์ตัวใหญ่ และมี fallback ภายใน
            )
            analyzer.process()
            st.caption(
                f"Using OSC: {st.session_state.get('osc_file')} | "
                f"FM: {st.session_state.get('fm_file')}"
            )
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.info("Please upload a ZIP on 'หน้าแรก' that contains both OSC (optical) and FM workbooks.")



elif menu == "Loss between EOL":
    st.markdown("### Loss between EOL")
    df_raw = st.session_state.get("atten_data")   # ใช้ atten_data ที่โหลดมา
    if df_raw is not None:
        try:
            analyzer = EOLAnalyzer(
                df_ref=None,
                df_raw_data=df_raw.copy(),
                ref_path="data/EOL.xlsx",
            )
            analyzer.process()   # ⬅ ตรงนี้ทำให้โชว์ทันที
            st.session_state["eol_analyzer"] = analyzer
            st.caption(f"Using RAW file: {st.session_state.get('atten_file')}")
        except Exception as e:
            st.error(f"An error occurred during EOL analysis: {e}")
    else:
        st.info("Please upload a ZIP file that contains the attenuation report.")


elif menu == "Loss between Core":
    st.markdown("### Loss between Core")
    df_raw = st.session_state.get("atten_data")   # ใช้ atten_data เหมือนกัน
    if df_raw is not None:
        try:
            analyzer = CoreAnalyzer(
                df_ref=None,
                df_raw_data=df_raw.copy(),
                ref_path="data/EOL.xlsx",
            )
            analyzer.process()   # ⬅ ตรงนี้ทำให้โชว์ทันที
            st.session_state["core_analyzer"] = analyzer
            st.caption(f"Using RAW file: {st.session_state.get('atten_file')}")
        except Exception as e:
            st.error(f"An error occurred during Core analysis: {e}")
    else:
        st.info("Please upload a ZIP file that contains the attenuation report.")



elif menu == "Dashboard":
    st.markdown("# 🌐 Network Monitoring Dashboard")
    st.markdown("---")
    
    # ตรวจสอบการเชื่อมต่อ Supabase
    supabase = get_supabase()
    if supabase.is_connected():
        st.success("✅ Connected to Supabase Database")
        
        # Simple Dashboard Info
        st.info("📊 Dashboard Overview")
        st.markdown("""
        ### 🚀 Getting Started
        1. Go to **หน้าแรก** to upload your ZIP files
        2. Select files and click **Run Analysis**
        3. Navigate to individual analysis pages (CPU, FAN, etc.)
        4. Check **Summary table & report** for comprehensive results
        """)
        
        # Show basic stats
        st.markdown("### 📈 Current Status")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📁 Total Files", len(supabase.get_dates_with_files()))
        
        with col2:
            analysis_results = supabase.get_analysis_results()
            st.metric("📊 Analysis Results", len(analysis_results))
        
        with col3:
            reports = supabase.get_reports()
            st.metric("📋 Generated Reports", len(reports))

        # ==============================
        # CPU Section (SNP, NCPM, NCPQ)
        # ==============================
        st.markdown("---")
        st.markdown("## CPU")

        def render_cpu_status(title: str, row: pd.Series | None):
            if row is None or row.empty:
                st.markdown(f"#### {title}")
                st.info("No data")
                return

            site = str(row.get("Site Name", "-"))
            board = str(row.get("Measure Object", "-"))
            cpu_pct = pd.to_numeric(row.get("CPU utilization ratio"), errors="coerce")
            if pd.notna(cpu_pct) and cpu_pct <= 1:
                cpu_pct = cpu_pct * 100.0

            cpu_text = f"{cpu_pct:.2f}%" if pd.notna(cpu_pct) else "-"

            # Threshold coloring
            status = "normal"
            color = "green"
            label = "green Normal"
            if pd.notna(cpu_pct) and cpu_pct > 90:
                status = "red critical"
                color = "red"
                label = "red critical >= 90%"
            elif pd.notna(cpu_pct) and cpu_pct >= 70:
                status = "orange major"
                color = "orange"
                label = "Orenge Major >=70%"
            elif pd.notna(cpu_pct) and cpu_pct >= 60:
                status = "yellow minor"
                color = "#d1a000"  # dark yellow
                label = "yellow Minor >=60%"

            # Header
            st.markdown(f"#### {title}")

            # Message: site name, board name, percentage (message text red if abnormal)
            msg_color = "red" if status != "normal" else "green"
            st.markdown(
                f"<div style='font-weight:600;color:{msg_color};'>"
                f"{site} — {board} — {cpu_text}"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Legend line similar to screenshot
            st.markdown(
                f"<div style='color:{color};'>{label}</div>",
                unsafe_allow_html=True,
            )

        def compute_max_cpu_per_type(df_merged: pd.DataFrame, pattern: str) -> pd.Series | None:
            if df_merged.empty:
                return None
            df_type = df_merged[df_merged["Measure Object"].astype(str).str.contains(pattern, na=False)].copy()
            if df_type.empty:
                return None
            # convert to percent if needed
            val = pd.to_numeric(df_type["CPU utilization ratio"], errors="coerce")
            if pd.notna(val.max()) and val.max() <= 1:
                val = val * 100.0
            df_type["CPU%"] = val
            df_type = df_type.sort_values("CPU%", ascending=False)
            return df_type.iloc[0] if not df_type.empty else None

        # Build merged CPU (from session if available)
        try:
            if st.session_state.get("cpu_data") is not None:
                cpu_df = st.session_state["cpu_data"].copy()
                ref = pd.read_excel("data/CPU.xlsx")

                # Normalize columns
                cpu_df.columns = (
                    cpu_df.columns.astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.replace("\u00a0", " ")
                )
                ref.columns = (
                    ref.columns.astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.replace("\u00a0", " ")
                )

                # Merge
                cpu_df["Mapping Format"] = (
                    cpu_df["ME"].astype(str).str.strip() + cpu_df["Measure Object"].astype(str).str.strip()
                )
                ref["Mapping"] = ref["Mapping"].astype(str).str.strip()
                merged = pd.merge(
                    cpu_df,
                    ref[["Mapping", "Maximum threshold", "Minimum threshold", "Site Name"]],
                    left_on="Mapping Format",
                    right_on="Mapping",
                    how="inner",
                )
                merged = merged[[
                    "Site Name", "ME", "Measure Object", "CPU utilization ratio", "Maximum threshold", "Minimum threshold"
                ]].copy()

                c1, c2, c3 = st.columns(3)
                with c1:
                    render_cpu_status("SNP", compute_max_cpu_per_type(merged, r"SNP\(E\)"))
                with c2:
                    render_cpu_status("NCPM", compute_max_cpu_per_type(merged, r"NCPM"))
                with c3:
                    render_cpu_status("NCPQ", compute_max_cpu_per_type(merged, r"NCPQ"))
            else:
                st.info("Upload CPU file and run analysis to populate CPU dashboard.")
        except Exception as e:
            st.warning(f"CPU dashboard could not be rendered: {e}")

        # ==============================
        # FAN Section (FCC, FCPL, FCPS, FCPP)
        # ==============================
        st.markdown("---")
        st.markdown("## FAN")

        def render_fan_gauge(title: str, row: pd.Series | None, threshold: float, vmax: float):
            st.markdown(f"#### {title}")
            if row is None or row.empty:
                st.info("No data")
                return

            site = str(row.get("Site Name", "-"))
            board = str(row.get("Measure Object", "-"))
            rps = pd.to_numeric(row.get("Value of Fan Rotate Speed(Rps)"), errors="coerce")
            value = float(rps) if pd.notna(rps) else 0.0

            # Bands relative to threshold (green/yellow/orange/red)
            g1 = 0.60 * threshold
            g2 = 0.70 * threshold
            g3 = 0.90 * threshold

            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=value,
                number={"suffix": " Rps", "font": {"color": "#000"}},
                gauge={
                    "axis": {"range": [0, vmax]},
                    "bar": {"color": "#6b4cff"},
                    "steps": [
                        {"range": [0, g1],  "color": "#8fd19e"},   # green
                        {"range": [g1, g2], "color": "#ffe08a"},   # yellow
                        {"range": [g2, g3], "color": "#ffb74d"},   # orange
                        {"range": [g3, vmax], "color": "#ff8a80"}, # red
                    ],
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.9,
                        "value": threshold,
                    },
                },
            ))

            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=220)
            st.plotly_chart(fig, use_container_width=True)

            # Text lines below gauge
            msg_color = "red" if value > threshold else "green"
            st.markdown(
                f"<div style='color:{msg_color};font-weight:600'>{site} — {board}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='color:{'red' if value > threshold else 'green'};'>"
                f"{'Abnormal > ' + str(int(threshold)) if value > threshold else 'green Normal'}"
                f"</div>",
                unsafe_allow_html=True,
            )

        def compute_max_fan_per_type(df_merged: pd.DataFrame, type_token: str) -> pd.Series | None:
            if df_merged.empty:
                return None
            df_type = df_merged[df_merged["Measure Object"].astype(str).str.contains(type_token, na=False)].copy()
            if df_type.empty:
                return None
            val = pd.to_numeric(df_type["Value of Fan Rotate Speed(Rps)"], errors="coerce")
            df_type["RpsVal"] = val
            df_type = df_type.sort_values("RpsVal", ascending=False)
            return df_type.iloc[0] if not df_type.empty else None

        try:
            if st.session_state.get("fan_data") is not None:
                fan_df = st.session_state["fan_data"].copy()
                ref = pd.read_excel("data/FAN.xlsx")

                # Normalize columns
                fan_df.columns = (
                    fan_df.columns.astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.replace("\u00a0", " ")
                )
                ref.columns = (
                    ref.columns.astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.replace("\u00a0", " ")
                )

                # Merge with reference
                fan_df["Mapping Format"] = (
                    fan_df["ME"].astype(str).str.strip() + fan_df["Measure Object"].astype(str).str.strip()
                )
                ref["Mapping"] = ref["Mapping"].astype(str).str.strip()
                merged = pd.merge(
                    fan_df,
                    ref[["Mapping", "Site Name", "Maximum threshold", "Minimum threshold"]],
                    left_on="Mapping Format",
                    right_on="Mapping",
                    how="inner",
                )
                merged = merged[[
                    "Site Name", "ME", "Measure Object", "Value of Fan Rotate Speed(Rps)",
                    "Maximum threshold", "Minimum threshold"
                ]].copy()

                # Thresholds
                thresholds = {"FCC": 120.0, "FCPL": 120.0, "FCPS": 230.0, "FCPP": 250.0}

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    render_fan_gauge(
                        "FCC",
                        compute_max_fan_per_type(merged, "FCC"),
                        thresholds["FCC"],
                        vmax= max(150.0, thresholds["FCC"] * 1.2),
                    )
                with c2:
                    render_fan_gauge(
                        "FCPL",
                        compute_max_fan_per_type(merged, "FCPL"),
                        thresholds["FCPL"],
                        vmax= max(150.0, thresholds["FCPL"] * 1.2),
                    )
                with c3:
                    render_fan_gauge(
                        "FCPS",
                        compute_max_fan_per_type(merged, "FCPS"),
                        thresholds["FCPS"],
                        vmax= max(280.0, thresholds["FCPS"] * 1.15),
                    )
                with c4:
                    render_fan_gauge(
                        "FCPP",
                        compute_max_fan_per_type(merged, "FCPP"),
                        thresholds["FCPP"],
                        vmax= max(300.0, thresholds["FCPP"] * 1.15),
                    )
            else:
                st.info("Upload FAN file and run analysis to populate FAN dashboard.")
        except Exception as e:
            st.warning(f"FAN dashboard could not be rendered: {e}")

        # ==============================
        # MSU Section
        # ==============================
        st.markdown("---")
        st.markdown("## MSU")

        try:
            if st.session_state.get("msu_data") is not None:
                msu_df = st.session_state["msu_data"].copy()
                ref = pd.read_excel("data/MSU.xlsx")

                # Normalize
                for df_ in (msu_df, ref):
                    df_.columns = (
                        df_.columns.astype(str)
                        .str.strip().str.replace(r"\s+", " ", regex=True).str.replace("\u00a0", " ")
                    )

                # Merge with reference for Site Name
                msu_df["Mapping Format"] = (
                    msu_df["ME"].astype(str).str.strip() + msu_df["Measure Object"].astype(str).str.strip()
                )
                ref["Mapping"] = ref["Mapping"].astype(str).str.strip()
                merged = pd.merge(
                    msu_df,
                    ref[["Mapping", "Site Name"]],
                    left_on="Mapping Format",
                    right_on="Mapping",
                    how="inner",
                )

                merged = merged[[
                    "Site Name", "ME", "Measure Object", "Laser Bias Current(mA)"
                ]].copy()

                merged["Laser Bias Current(mA)"] = pd.to_numeric(
                    merged["Laser Bias Current(mA)"], errors="coerce"
                )

                # Find maximum mA row
                row_max = merged.sort_values("Laser Bias Current(mA)", ascending=False).iloc[0] if not merged.empty else None

                c = st.columns(3)
                with c[0]:
                    st.markdown("#### MSU Max mA")
                    if row_max is None:
                        st.info("No data")
                    else:
                        site = str(row_max.get("Site Name", "-"))
                        board = str(row_max.get("Measure Object", "-"))
                        mA = float(row_max.get("Laser Bias Current(mA)", float("nan")))
                        msg_color = "red" if pd.notna(mA) and mA > 1100 else "green"
                        st.markdown(
                            f"<div style='font-weight:600;color:{msg_color};'>{site} — {board} — {mA:.2f} mA</div>",
                            unsafe_allow_html=True,
                        )
                        st.markdown("<div style='color:gray;'>Normal < 1100, Abnormal > 1100</div>", unsafe_allow_html=True)

                # Counts
                vals = pd.to_numeric(merged["Laser Bias Current(mA)"], errors="coerce")
                abn_cnt = int((vals > 1100).sum())
                ok_cnt = int((vals < 1100).sum())
                total = int(vals.notna().sum())

                with c[1]:
                    st.metric("Normal", f"{ok_cnt}")
                with c[2]:
                    st.metric("Abnormal", f"{abn_cnt}", f"Total {total}")
            else:
                st.info("Upload MSU file and run analysis to populate MSU dashboard.")
        except Exception as e:
            st.warning(f"MSU dashboard could not be rendered: {e}")

        # ==============================
        # Line Section Summary
        # ==============================
        st.markdown("---")
        st.markdown("## Line")
        try:
            if st.session_state.get("line_data") is not None:
                df_line = st.session_state["line_data"].copy()
                ref = pd.read_excel("data/Line.xlsx")

                # Normalize
                for df_ in (df_line, ref):
                    df_.columns = (
                        df_.columns.astype(str)
                        .str.strip().str.replace(r"\s+", " ", regex=True).str.replace("\u00a0", " ")
                    )

                # Merge
                df_line["Mapping Format"] = (
                    df_line["ME"].astype(str).str.strip() + df_line["Measure Object"].astype(str).str.strip()
                )
                ref["Mapping"] = ref["Mapping"].astype(str).str.strip()
                merged = pd.merge(
                    df_line,
                    ref[["Mapping", "Site Name", "Threshold",
                         "Maximum threshold(out)", "Minimum threshold(out)",
                         "Maximum threshold(in)",  "Minimum threshold(in)",
                         "Route"]],
                    left_on="Mapping Format",
                    right_on="Mapping",
                    how="inner",
                )

                # Cast
                ber = pd.to_numeric(merged.get("Instant BER After FEC"), errors="coerce")
                thr = pd.to_numeric(merged.get("Threshold"), errors="coerce")
                vin = pd.to_numeric(merged.get("Input Optical Power(dBm)"), errors="coerce")
                vout = pd.to_numeric(merged.get("Output Optical Power (dBm)"), errors="coerce")
                min_in = pd.to_numeric(merged.get("Minimum threshold(in)"), errors="coerce")
                max_in = pd.to_numeric(merged.get("Maximum threshold(in)"), errors="coerce")
                min_out = pd.to_numeric(merged.get("Minimum threshold(out)"), errors="coerce")
                max_out = pd.to_numeric(merged.get("Maximum threshold(out)"), errors="coerce")

                total = int(len(merged))
                ber_abn = int(((thr.notna()) & (ber.notna()) & (ber > thr)).sum())
                in_abn = int(((vin.notna() & min_in.notna() & max_in.notna()) & ((vin < min_in) | (vin > max_in))).sum())
                out_abn = int(((vout.notna() & min_out.notna() & max_out.notna()) & ((vout < min_out) | (vout > max_out))).sum())

                c = st.columns(4)
                c[0].metric("Total", f"{total}")
                c[1].metric("BER Abnormal", f"{ber_abn}")
                c[2].metric("Input Abnormal", f"{in_abn}")
                c[3].metric("Output Abnormal", f"{out_abn}")

                # Preset quick card
                preset_mask = merged.get("Route", pd.Series([], dtype=object)).astype(str).str.startswith("Preset")
                preset_total = int(preset_mask.sum())
                preset_df = merged.loc[preset_mask].copy()
                p_ber_abn = int(((pd.to_numeric(preset_df.get("Instant BER After FEC"), errors="coerce") > pd.to_numeric(preset_df.get("Threshold"), errors="coerce"))).sum())
                p_in_abn = int(((pd.to_numeric(preset_df.get("Input Optical Power(dBm)"), errors="coerce") < pd.to_numeric(preset_df.get("Minimum threshold(in)"), errors="coerce")) |
                                (pd.to_numeric(preset_df.get("Input Optical Power(dBm)"), errors="coerce") > pd.to_numeric(preset_df.get("Maximum threshold(in)"), errors="coerce"))).sum())
                p_out_abn = int(((pd.to_numeric(preset_df.get("Output Optical Power (dBm)"), errors="coerce") < pd.to_numeric(preset_df.get("Minimum threshold(out)"), errors="coerce")) |
                                 (pd.to_numeric(preset_df.get("Output Optical Power (dBm)"), errors="coerce") > pd.to_numeric(preset_df.get("Maximum threshold(out)"), errors="coerce"))).sum())

                st.markdown("#### Preset")
                pc = st.columns(4)
                pc[0].metric("Preset Total", f"{preset_total}")
                pc[1].metric("BER Abn (Preset)", f"{p_ber_abn}")
                pc[2].metric("Input Abn (Preset)", f"{p_in_abn}")
                pc[3].metric("Output Abn (Preset)", f"{p_out_abn}")

                # Preset usage table with status label (OK/Abnormal) per Preset
                if not preset_df.empty:
                    preset_df = preset_df.copy()
                    preset_df["PresetNo"] = preset_df["Route"].astype(str).str.extract(r"Preset\s*(\\d+)")
                    # Determine abnormal for each row
                    pber = pd.to_numeric(preset_df.get("Instant BER After FEC"), errors="coerce")
                    pthr = pd.to_numeric(preset_df.get("Threshold"), errors="coerce")
                    pinv = pd.to_numeric(preset_df.get("Input Optical Power(dBm)"), errors="coerce")
                    pinL = pd.to_numeric(preset_df.get("Minimum threshold(in)"), errors="coerce")
                    pinH = pd.to_numeric(preset_df.get("Maximum threshold(in)"), errors="coerce")
                    pout = pd.to_numeric(preset_df.get("Output Optical Power (dBm)"), errors="coerce")
                    poutL= pd.to_numeric(preset_df.get("Minimum threshold(out)"), errors="coerce")
                    poutH= pd.to_numeric(preset_df.get("Maximum threshold(out)"), errors="coerce")

                    row_abn = (
                        (pber.notna() & pthr.notna() & (pber > pthr)) |
                        (pinv.notna() & pinL.notna() & pinH.notna() & ((pinv < pinL) | (pinv > pinH))) |
                        (pout.notna() & poutL.notna() & poutH.notna() & ((pout < poutL) | (pout > poutH)))
                    )
                    preset_df["RowAbn"] = row_abn

                    preset_usage = (
                        preset_df.groupby("PresetNo").agg(
                            usage=("PresetNo", "count"),
                            abn=("RowAbn", "any"),
                        ).reset_index()
                    )
                    preset_usage["Status"] = preset_usage["abn"].map(lambda x: "Abnormal" if x else "Normal")
                    preset_usage = preset_usage[["PresetNo", "usage", "Status"]]
                    preset_usage = preset_usage.rename(columns={"PresetNo": "Preset", "usage": "Usage"})

                    st.markdown("#### Preset Usage • Status")
                    st.dataframe(preset_usage.reset_index(drop=True), use_container_width=True)
            else:
                st.info("Upload Line file and run analysis to populate Line dashboard.")
        except Exception as e:
            st.warning(f"Line dashboard could not be rendered: {e}")

        # ==============================
        # Client Section Summary
        # ==============================
        st.markdown("---")
        st.markdown("## Client")
        try:
            if st.session_state.get("client_data") is not None:
                df_client = st.session_state["client_data"].copy()
                ref = pd.read_excel("data/Client.xlsx")

                # Normalize
                for df_ in (df_client, ref):
                    df_.columns = (
                        df_.columns.astype(str)
                        .str.strip().str.replace(r"\s+", " ", regex=True).str.replace("\u00a0", " ")
                    )

                df_client["Mapping Format"] = (
                    df_client["ME"].astype(str).str.strip() + df_client["Measure Object"].astype(str).str.strip()
                )
                ref["Mapping"] = ref["Mapping"].astype(str).str.strip()
                merged = pd.merge(
                    df_client,
                    ref[[
                        "Mapping", "Site Name",
                        "Maximum threshold(out)", "Minimum threshold(out)",
                        "Maximum threshold(in)",  "Minimum threshold(in)",
                    ]],
                    left_on="Mapping Format",
                    right_on="Mapping",
                    how="inner",
                )

                vin = pd.to_numeric(merged.get("Input Optical Power(dBm)"), errors="coerce")
                vout = pd.to_numeric(merged.get("Output Optical Power (dBm)"), errors="coerce")
                min_in = pd.to_numeric(merged.get("Minimum threshold(in)"), errors="coerce")
                max_in = pd.to_numeric(merged.get("Maximum threshold(in)"), errors="coerce")
                min_out = pd.to_numeric(merged.get("Minimum threshold(out)"), errors="coerce")
                max_out = pd.to_numeric(merged.get("Maximum threshold(out)"), errors="coerce")

                # Exclude invalid -60
                mask_valid = (vin != -60) & (vout != -60)
                vin = vin.where(mask_valid)
                vout = vout.where(mask_valid)

                total = int(len(merged))
                in_abn = int(((vin.notna() & min_in.notna() & max_in.notna()) & ((vin < min_in) | (vin > max_in))).sum())
                out_abn = int(((vout.notna() & min_out.notna() & max_out.notna()) & ((vout < min_out) | (vout > max_out))).sum())

                c = st.columns(3)
                c[0].metric("Total", f"{total}")
                c[1].metric("Input Abnormal", f"{in_abn}")
                c[2].metric("Output Abnormal", f"{out_abn}")
            else:
                st.info("Upload Client file and run analysis to populate Client dashboard.")
        except Exception as e:
            st.warning(f"Client dashboard could not be rendered: {e}")

        # ==============================
        # EOL / Core / APO – Circle Charts
        # ==============================
        st.markdown("---")
        st.markdown("## EOL • Core • APO")

        cols = st.columns(3)

        # EOL Donut
        try:
            df_raw = st.session_state.get("atten_data")
            if df_raw is not None:
                eol = EOLAnalyzer(df_ref=None, df_raw_data=df_raw.copy(), ref_path="data/EOL.xlsx")
                df_result = eol.build_result_df()
                if not df_result.empty:
                    vals = pd.to_numeric(df_result.get("Loss current - Loss EOL"), errors="coerce")
                    remark = df_result.get("Remark").astype(str).fillna("")
                    status = []
                    for v, r in zip(vals, remark):
                        if r.strip() != "":
                            status.append("EOL Fiber Break")
                        elif pd.notna(v) and v >= 2.5:
                            status.append("EOL Excess Loss")
                        else:
                            status.append("EOL Normal")
                    with cols[0]:
                        fig = px.pie(pd.DataFrame({"Status": status}), names="Status", hole=0.5,
                                     color="Status",
                                     color_discrete_map={"EOL Normal": "green", "EOL Excess Loss": "red", "EOL Fiber Break": "gold"})
                        fig.update_traces(textinfo="value+label")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    with cols[0]:
                        st.info("No EOL data")
            else:
                with cols[0]:
                    st.info("No EOL data")
        except Exception as e:
            with cols[0]:
                st.warning(f"EOL chart error: {e}")

        # Core Donut
        try:
            df_raw = st.session_state.get("atten_data")
            if df_raw is not None:
                core = CoreAnalyzer(df_ref=None, df_raw_data=df_raw.copy(), ref_path="data/EOL.xlsx")
                df_res = core.build_result_df()
                if not df_res.empty:
                    df_loss_between_core = core.calculate_loss_between_core(df_res)
                    vals = df_loss_between_core["Loss between core"].tolist()
                    status = []
                    for v in vals:
                        if v == "--":
                            status.append("Core Fiber Break")
                        elif pd.notna(v) and v > 3:
                            try:
                                status.append("Core Loss Excess" if float(v) > 3 else "Core Normal")
                            except Exception:
                                status.append("Core Normal")
                        else:
                            status.append("Core Normal")
                    with cols[1]:
                        fig = px.pie(pd.DataFrame({"Status": status}), names="Status", hole=0.5,
                                     color="Status",
                                     color_discrete_map={"Core Normal": "green", "Core Loss Excess": "red", "Core Fiber Break": "gold"})
                        fig.update_traces(textinfo="value+label")
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    with cols[1]:
                        st.info("No Core data")
            else:
                with cols[1]:
                    st.info("No Core data")
        except Exception as e:
            with cols[1]:
                st.warning(f"Core chart error: {e}")

        # APO Donut
        try:
            wason = st.session_state.get("wason_log")
            if wason:
                apo = ApoRemnantAnalyzer(wason)
                apo.parse(); apo.analyze()
                rendered = apo.rendered
                apo_sites = sum(1 for x in rendered if x[2])
                noapo_sites = sum(1 for x in rendered if not x[2])
                df_summary = pd.DataFrame({
                    "Status": (["No APO Remnant"] * noapo_sites) + (["APO Remnant"] * apo_sites)
                })
                with cols[2]:
                    fig = px.pie(df_summary, names="Status", hole=0.5,
                                 color="Status",
                                 color_discrete_map={"No APO Remnant": "green", "APO Remnant": "red"})
                    fig.update_traces(textinfo="value+label")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                with cols[2]:
                    st.info("No APO log")
        except Exception as e:
            with cols[2]:
                st.warning(f"APO chart error: {e}")

        # ==============================
        # Fiber Flapping — Daily Sites Bar
        # ==============================
        st.markdown("---")
        st.markdown("## Fiber Flapping")
        try:
            df_osc = st.session_state.get("osc_data")
            df_fm  = st.session_state.get("fm_data")
            if (df_osc is not None) and (df_fm is not None):
                # Build minimal pipeline to get unmatched flapping per day
                analyzer_ff = FiberflappingAnalyzer(
                    df_optical=df_osc.copy(),
                    df_fm=df_fm.copy(),
                    threshold=2.0,
                    ref_path="data/Flapping.xlsx",
                )
                df_opt = analyzer_ff.normalize_optical()
                df_fm_norm, link_col = analyzer_ff.normalize_fm()
                df_filtered = analyzer_ff.filter_optical_by_threshold(df_opt)
                df_nomatch = analyzer_ff.find_nomatch(df_filtered, df_fm_norm, link_col)

                if df_nomatch.empty:
                    st.success("No unmatched fiber flapping records.")
                else:
                    df_nomatch = df_nomatch.copy()
                    df_nomatch["Date"] = pd.to_datetime(df_nomatch["Begin Time"]).dt.date
                    daily_counts = (
                        df_nomatch.groupby("Date")["ME"].nunique().reset_index().rename(columns={"ME": "Sites"})
                    )
                    fig = px.bar(daily_counts, x="Date", y="Sites", text="Sites",
                                 title="No Fiber Break Alarm Match (Fiber Flapping)")
                    fig.update_traces(textposition="outside")
                    fig.update_layout(xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Upload ZIP that includes OSC and FM for Fiber Flapping dashboard.")
        except Exception as e:
            st.warning(f"Fiber Flapping chart error: {e}")
    else:
        st.error("❌ Cannot connect to Supabase Database")
        st.info("Please check your Supabase configuration in Streamlit secrets.")

elif menu == "Preset status":
    st.markdown("### Preset Status Analysis")
    if st.session_state.get("wason_log") is not None:
        try:
            # สร้าง Progress bar สำหรับการวิเคราะห์ Preset
            preset_progress = st.progress(0)
            preset_status = st.empty()
            
            preset_status.text("📊 Loading Preset analyzer...")
            preset_progress.progress(0.3)
            
            analyzer = PresetStatusAnalyzer(st.session_state["wason_log"])
            preset_progress.progress(0.6)
            
            preset_status.text("🔍 Parsing WASON log...")
            analyzer.parse()
            preset_progress.progress(0.8)
            
            preset_status.text("⚙️ Analyzing preset status...")
            analyzer.analyze()
            preset_progress.progress(1.0)
            
            preset_status.text("✅ Preset analysis completed!")
            
            # แสดงผล
            df, summary = analyzer.to_dataframe()
            render_preset_ui(df, summary)
            
            # บันทึก analyzer ใน session state
            st.session_state["preset_analyzer"] = analyzer
            
            import time
            time.sleep(1)
            
        except Exception as e:
            st.error(f"❌ An error occurred during Preset analysis: {e}")
            preset_progress.progress(0)
            preset_status.text("❌ Preset analysis failed")
    else:
        st.info("📁 Please upload a ZIP file that contains the WASON log data.")

elif menu == "APO Remnant":
    st.markdown("### APO Remnant Analysis")
    if st.session_state.get("wason_log") is not None:
        try:
            # สร้าง Progress bar สำหรับการวิเคราะห์ APO
            apo_progress = st.progress(0)
            apo_status = st.empty()
            
            apo_status.text("📊 Loading APO analyzer...")
            apo_progress.progress(0.3)
            
            analyzer = ApoRemnantAnalyzer(st.session_state["wason_log"])
            apo_progress.progress(0.6)
            
            apo_status.text("🔍 Parsing WASON log...")
            analyzer.parse()
            apo_progress.progress(0.8)
            
            apo_status.text("⚙️ Analyzing APO remnant...")
            analyzer.analyze()
            apo_progress.progress(1.0)
            
            apo_status.text("✅ APO analysis completed!")
            
            # แสดงผล KPI และ UI
            apo_kpi(analyzer.rendered)
            analyzer.render_streamlit()
            
            # บันทึก analyzer ใน session state
            st.session_state["apo_analyzer"] = analyzer
            
            import time
            time.sleep(1)
            
        except Exception as e:
            st.error(f"❌ An error occurred during APO analysis: {e}")
            apo_progress.progress(0)
            apo_status.text("❌ APO analysis failed")
    else:
        st.info("📁 Please upload a ZIP file that contains the WASON log data.")

elif menu == "Summary table & report":
    summary = SummaryTableReport()
    summary.render()
import os
import sqlite3
import uuid
from datetime import datetime, date
import pytz
import streamlit as st
from streamlit_calendar import calendar
import io, zipfile
import pandas as pd

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
    st.markdown("#### Upload & Manage ZIP Files (with Calendar)")

    chosen_date = st.date_input("Select date", value=date.today())
    files = st.file_uploader(
        "Upload ZIP files",
        type=["zip"],
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
                        with open(fpath, "rb") as f:
                            zip_bytes = io.BytesIO(f.read())
                            res = find_in_zip(zip_bytes)
                        
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
                ref_path="data/flapping.xlsx"  # เพิ่ม reference file
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
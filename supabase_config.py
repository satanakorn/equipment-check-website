import os
import streamlit as st
from supabase import create_client, Client
import pandas as pd
from typing import Optional, Dict, Any
import json
from datetime import datetime

class SupabaseManager:
    """จัดการการเชื่อมต่อและใช้งาน Supabase Database"""
    
    def __init__(self):
        self.supabase: Optional[Client] = None
        self._init_connection()
    
    def _init_connection(self):
        """เริ่มต้นการเชื่อมต่อ Supabase"""
        try:
            # ใช้ environment variables หรือ Streamlit secrets
            url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
            key = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")
            
            if not url or not key:
                st.error("❌ Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit secrets or environment variables.")
                return
            
            self.supabase = create_client(url, key)
            st.success("✅ Connected to Supabase successfully!")
            
        except Exception as e:
            st.error(f"❌ Failed to connect to Supabase: {e}")
            self.supabase = None
    
    def is_connected(self) -> bool:
        """ตรวจสอบว่ามีการเชื่อมต่อ Supabase หรือไม่"""
        return self.supabase is not None
    
    # ===== FILE MANAGEMENT =====
    def save_upload_record(self, upload_date: str, orig_filename: str, stored_path: str) -> Optional[int]:
        """บันทึกข้อมูลการอัปโหลดไฟล์"""
        if not self.is_connected():
            return None
        
        try:
            data = {
                "upload_date": upload_date,
                "orig_filename": orig_filename,
                "stored_path": stored_path,
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("uploads").insert(data).execute()
            if result.data:
                return result.data[0]["id"]
            return None
            
        except Exception as e:
            st.error(f"❌ Failed to save upload record: {e}")
            return None
    
    def get_files_by_date(self, upload_date: str) -> list:
        """ดึงรายการไฟล์ตามวันที่"""
        if not self.is_connected():
            return []
        
        try:
            result = self.supabase.table("uploads").select("id, orig_filename, stored_path").eq("upload_date", upload_date).execute()
            return result.data or []
        except Exception as e:
            st.error(f"❌ Failed to get files by date: {e}")
            return []
    
    def delete_file_record(self, file_id: int) -> bool:
        """ลบข้อมูลไฟล์"""
        if not self.is_connected():
            return False
        
        try:
            self.supabase.table("uploads").delete().eq("id", file_id).execute()
            return True
        except Exception as e:
            st.error(f"❌ Failed to delete file record: {e}")
            return False
    
    def get_dates_with_files(self) -> list:
        """ดึงรายการวันที่ที่มีไฟล์"""
        if not self.is_connected():
            return []
        
        try:
            result = self.supabase.table("uploads").select("upload_date").execute()
            if not result.data:
                return []
            
            # นับจำนวนไฟล์ต่อวัน
            date_counts = {}
            for row in result.data:
                date = row["upload_date"]
                date_counts[date] = date_counts.get(date, 0) + 1
            
            return [(date, count) for date, count in date_counts.items()]
        except Exception as e:
            st.error(f"❌ Failed to get dates with files: {e}")
            return []
    
    # ===== ANALYSIS RESULTS =====
    def save_analysis_result(self, analysis_type: str, data: Dict[str, Any], file_id: int) -> Optional[int]:
        """บันทึกผลการวิเคราะห์"""
        if not self.is_connected():
            return None
        
        try:
            result_data = {
                "analysis_type": analysis_type,
                "file_id": file_id,
                "data": json.dumps(data, default=str),  # Convert to JSON string
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("analysis_results").insert(result_data).execute()
            if result.data:
                return result.data[0]["id"]
            return None
            
        except Exception as e:
            st.error(f"❌ Failed to save analysis result: {e}")
            return None
    
    def get_analysis_results(self, analysis_type: str = None, file_id: int = None) -> list:
        """ดึงผลการวิเคราะห์"""
        if not self.is_connected():
            return []
        
        try:
            query = self.supabase.table("analysis_results").select("*")
            
            if analysis_type:
                query = query.eq("analysis_type", analysis_type)
            if file_id:
                query = query.eq("file_id", file_id)
            
            result = query.execute()
            return result.data or []
        except Exception as e:
            st.error(f"❌ Failed to get analysis results: {e}")
            return []
    
    # ===== REPORTS =====
    def save_report(self, report_name: str, report_data: Dict[str, Any], file_ids: list) -> Optional[int]:
        """บันทึกรายงาน"""
        if not self.is_connected():
            return None
        
        try:
            report_record = {
                "report_name": report_name,
                "report_data": json.dumps(report_data, default=str),
                "file_ids": json.dumps(file_ids),
                "created_at": datetime.now().isoformat()
            }
            
            result = self.supabase.table("reports").insert(report_record).execute()
            if result.data:
                return result.data[0]["id"]
            return None
            
        except Exception as e:
            st.error(f"❌ Failed to save report: {e}")
            return None
    
    def get_reports(self) -> list:
        """ดึงรายการรายงาน"""
        if not self.is_connected():
            return []
        
        try:
            result = self.supabase.table("reports").select("*").order("created_at", desc=True).execute()
            return result.data or []
        except Exception as e:
            st.error(f"❌ Failed to get reports: {e}")
            return []

# Global instance
supabase_manager = SupabaseManager()

def get_supabase() -> SupabaseManager:
    """Get global Supabase manager instance"""
    return supabase_manager

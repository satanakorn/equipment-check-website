import streamlit as st
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from supabase_config import get_supabase

class AuthManager:
    """จัดการระบบ Authentication และ Authorization"""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.session_timeout = timedelta(hours=8)  # 8 ชั่วโมง
    
    def is_authenticated(self) -> bool:
        """ตรวจสอบว่าผู้ใช้ login แล้วหรือไม่"""
        if 'user_session' not in st.session_state:
            return False
        
        session = st.session_state['user_session']
        if not session:
            return False
        
        # ตรวจสอบ session timeout
        last_activity = session.get('last_activity')
        if last_activity:
            last_activity_dt = datetime.fromisoformat(last_activity)
            if datetime.now() - last_activity_dt > self.session_timeout:
                self.logout()
                return False
        
        # อัพเดท last activity
        session['last_activity'] = datetime.now().isoformat()
        return True
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลผู้ใช้ปัจจุบัน"""
        if not self.is_authenticated():
            return None
        return st.session_state['user_session'].get('user')
    
    def login(self, email: str, password: str) -> bool:
        """Login ผู้ใช้"""
        try:
            # ในระบบจริงควรใช้ Supabase Auth
            # ตอนนี้ใช้ระบบง่ายๆ สำหรับ demo
            
            # ตรวจสอบ credentials
            if self._validate_credentials(email, password):
                user = self._get_user_by_email(email)
                if user:
                    # สร้าง session
                    session_token = secrets.token_urlsafe(32)
                    st.session_state['user_session'] = {
                        'user': user,
                        'token': session_token,
                        'login_time': datetime.now().isoformat(),
                        'last_activity': datetime.now().isoformat()
                    }
                    return True
            return False
            
        except Exception as e:
            st.error(f"Login error: {e}")
            return False
    
    def logout(self):
        """Logout ผู้ใช้"""
        if 'user_session' in st.session_state:
            del st.session_state['user_session']
        st.rerun()
    
    def register(self, email: str, password: str, name: str, role: str = 'user') -> bool:
        """ลงทะเบียนผู้ใช้ใหม่"""
        try:
            # ตรวจสอบว่ามี email นี้แล้วหรือไม่
            if self._user_exists(email):
                st.error("Email already exists")
                return False
            
            # สร้างผู้ใช้ใหม่
            user_data = {
                'email': email,
                'name': name,
                'role': role,
                'password_hash': self._hash_password(password),
                'is_active': True,
                'created_at': datetime.now().isoformat()
            }
            
            # บันทึกลง Supabase
            if self.supabase.is_connected():
                result = self.supabase.supabase.table('users').insert(user_data).execute()
                if result.data:
                    st.success("Registration successful!")
                    return True
            
            return False
            
        except Exception as e:
            st.error(f"Registration error: {e}")
            return False
    
    def has_permission(self, required_role: str) -> bool:
        """ตรวจสอบสิทธิ์การเข้าถึง"""
        user = self.get_current_user()
        if not user:
            return False
        
        user_role = user.get('role', 'user')
        
        # Role hierarchy: admin > user > viewer
        role_hierarchy = {
            'admin': 3,
            'user': 2,
            'viewer': 1
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        return user_level >= required_level
    
    def _validate_credentials(self, email: str, password: str) -> bool:
        """ตรวจสอบ credentials"""
        try:
            if self.supabase.is_connected():
                result = self.supabase.supabase.table('users').select('*').eq('email', email).eq('is_active', True).execute()
                if result.data:
                    user = result.data[0]
                    stored_hash = user.get('password_hash')
                    if stored_hash and self._verify_password(password, stored_hash):
                        return True
            return False
        except Exception as e:
            st.error(f"Credential validation error: {e}")
            return False
    
    def _get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลผู้ใช้จาก email"""
        try:
            if self.supabase.is_connected():
                result = self.supabase.supabase.table('users').select('id, email, name, role, is_active').eq('email', email).execute()
                if result.data:
                    return result.data[0]
            return None
        except Exception as e:
            st.error(f"Get user error: {e}")
            return None
    
    def _user_exists(self, email: str) -> bool:
        """ตรวจสอบว่ามีผู้ใช้ email นี้แล้วหรือไม่"""
        try:
            if self.supabase.is_connected():
                result = self.supabase.supabase.table('users').select('id').eq('email', email).execute()
                return len(result.data) > 0
            return False
        except Exception as e:
            st.error(f"User exists check error: {e}")
            return False
    
    def _hash_password(self, password: str) -> str:
        """Hash password"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """ตรวจสอบ password"""
        return self._hash_password(password) == stored_hash

def render_login_page():
    """แสดงหน้า Login"""
    st.markdown("# 🔐 Login to Network Monitoring Dashboard")
    st.markdown("---")
    
    auth = AuthManager()
    
    # Login Form
    with st.form("login_form"):
        st.markdown("### Sign In")
        email = st.text_input("Email", placeholder="your.email@3bb.co.th")
        password = st.text_input("Password", type="password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            login_clicked = st.form_submit_button("🔑 Login", use_container_width=True)
        with col2:
            register_clicked = st.form_submit_button("📝 Register", use_container_width=True)
    
    if login_clicked:
        if email and password:
            if auth.login(email, password):
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid email or password")
        else:
            st.warning("⚠️ Please enter both email and password")
    
    if register_clicked:
        st.session_state['show_register'] = True
        st.rerun()
    
    # Register Form
    if st.session_state.get('show_register', False):
        st.markdown("---")
        with st.form("register_form"):
            st.markdown("### Register New Account")
            reg_name = st.text_input("Full Name", placeholder="John Doe")
            reg_email = st.text_input("Email", placeholder="john.doe@3bb.co.th")
            reg_password = st.text_input("Password", type="password")
            reg_confirm = st.text_input("Confirm Password", type="password")
            reg_role = st.selectbox("Role", ["user", "viewer"], help="Admin role requires approval")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                register_submit = st.form_submit_button("✅ Register", use_container_width=True)
            with col2:
                cancel_register = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if register_submit:
            if reg_name and reg_email and reg_password and reg_confirm:
                if reg_password == reg_confirm:
                    if auth.register(reg_email, reg_password, reg_name, reg_role):
                        st.session_state['show_register'] = False
                        st.rerun()
                else:
                    st.error("❌ Passwords do not match")
            else:
                st.warning("⚠️ Please fill all fields")
        
        if cancel_register:
            st.session_state['show_register'] = False
            st.rerun()

def require_auth(required_role: str = 'user'):
    """Decorator สำหรับตรวจสอบ authentication"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            auth = AuthManager()
            if not auth.is_authenticated():
                render_login_page()
                return
            if not auth.has_permission(required_role):
                st.error("❌ Access denied. Insufficient permissions.")
                return
            return func(*args, **kwargs)
        return wrapper
    return decorator

def render_user_info():
    """แสดงข้อมูลผู้ใช้และปุ่ม logout"""
    auth = AuthManager()
    user = auth.get_current_user()
    
    if user:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"👤 **{user.get('name', 'Unknown')}** ({user.get('role', 'user')})")
        with col2:
            st.markdown(f"📧 {user.get('email', 'Unknown')}")
        with col3:
            if st.button("🚪 Logout", key="logout_btn"):
                auth.logout()

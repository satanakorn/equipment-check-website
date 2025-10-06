# 🚀 Deployment Guide - 3BB Network Monitoring Dashboard

## 📋 Pre-Deployment Checklist

### ✅ Database Setup
- [ ] สร้าง Supabase project
- [ ] รัน SQL schema (`supabase_schema.sql`)
- [ ] ตั้งค่า Row Level Security (RLS)
- [ ] ทดสอบการเชื่อมต่อ database

### ✅ Code Preparation
- [ ] ทดสอบโค้ดใน local environment
- [ ] ตรวจสอบ dependencies ใน `requirements.txt`
- [ ] อัพเดท README.md
- [ ] Commit และ push ไป GitHub

### ✅ Configuration
- [ ] เตรียม Supabase credentials
- [ ] ตั้งค่า Streamlit secrets
- [ ] ตรวจสอบ file paths และ permissions

## 🌐 Streamlit Cloud Deployment

### Step 1: Prepare GitHub Repository
```bash
# ตรวจสอบไฟล์ที่จำเป็น
ls -la
# ควรมีไฟล์เหล่านี้:
# - app9.py (main file)
# - requirements.txt
# - README.md
# - .streamlit/config.toml
# - .streamlit/secrets.toml (template)
```

### Step 2: Deploy to Streamlit Cloud
1. ไปที่ [Streamlit Cloud](https://share.streamlit.io)
2. คลิก "New app"
3. เชื่อมต่อ GitHub repository
4. ตั้งค่า:
   - **Repository**: your-repo-name
   - **Branch**: main
   - **Main file path**: `app9.py`
   - **Python version**: 3.8+

### Step 3: Configure Secrets
1. ไปที่ App Settings → Secrets
2. เพิ่มข้อมูลต่อไปนี้:
```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_ANON_KEY = "your-supabase-anon-key"
```

### Step 4: Deploy
1. คลิก "Deploy!"
2. รอการ build และ deploy
3. ทดสอบการทำงาน

## 🔧 Environment Variables

### Required Variables
```bash
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key

# Optional: For development
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
```

### Streamlit Secrets Format
สร้างไฟล์ `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 🗄️ Database Migration

### From SQLite to Supabase
```python
# Migration script (run once)
import sqlite3
from supabase_config import get_supabase

def migrate_data():
    # Read from SQLite
    conn = sqlite3.connect('files.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM uploads")
    uploads = cursor.fetchall()
    
    # Write to Supabase
    supabase = get_supabase()
    for upload in uploads:
        supabase.save_upload_record(
            upload_date=upload[1],
            orig_filename=upload[2],
            stored_path=upload[3]
        )
    
    conn.close()
    print("Migration completed!")
```

## 🔒 Security Configuration

### Supabase RLS Policies
```sql
-- Enable RLS
ALTER TABLE uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Enable all operations for authenticated users" ON uploads
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Enable all operations for authenticated users" ON analysis_results
    FOR ALL USING (auth.role() = 'authenticated');
```

### CORS Configuration
```python
# ใน app9.py
st.set_page_config(
    page_title="3BB Network Monitoring",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

## 📊 Monitoring & Logging

### Application Logs
```python
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
```

### Error Handling
```python
try:
    # Your code here
    pass
except Exception as e:
    st.error(f"An error occurred: {e}")
    logger.error(f"Error: {e}", exc_info=True)
```

## 🚨 Troubleshooting

### Common Deployment Issues

#### 1. Build Failures
```
Error: Could not find a version that satisfies the requirement
```
**Solution**: ตรวจสอบ `requirements.txt` และ version compatibility

#### 2. Database Connection Issues
```
❌ Supabase credentials not found
```
**Solution**: ตรวจสอบ secrets configuration

#### 3. File Upload Issues
```
❌ Failed to save file
```
**Solution**: ตรวจสอบ file permissions และ storage configuration

#### 4. Memory Issues
```
Error: Out of memory
```
**Solution**: เพิ่ม memory limit หรือ optimize data processing

### Debug Commands
```bash
# Check logs
streamlit run app9.py --logger.level=debug

# Test database connection
python -c "from supabase_config import get_supabase; print(get_supabase().is_connected())"

# Validate requirements
pip check
```

## 📈 Performance Optimization

### Database Optimization
- ใช้ indexes สำหรับ queries ที่บ่อย
- ตั้งค่า connection pooling
- ใช้ pagination สำหรับข้อมูลจำนวนมาก

### Application Optimization
- Cache ข้อมูลที่ใช้บ่อย
- ใช้ lazy loading สำหรับ modules
- Optimize image และ file sizes

### Monitoring
- ตั้งค่า alerts สำหรับ errors
- Monitor database performance
- Track user activity

## 🔄 Updates & Maintenance

### Regular Updates
1. **Dependencies**: อัพเดท packages เป็นประจำ
2. **Security**: ตรวจสอบ security patches
3. **Database**: Backup และ maintenance
4. **Code**: Bug fixes และ feature updates

### Backup Strategy
```bash
# Database backup
pg_dump your_database > backup.sql

# File backup
tar -czf uploads_backup.tar.gz uploads/

# Code backup
git tag v1.0.0
git push origin v1.0.0
```

## 📞 Support & Maintenance

### Contact Information
- **Technical Support**: tech-support@3bb.co.th
- **Database Issues**: db-admin@3bb.co.th
- **Emergency**: +66-2-xxx-xxxx

### Maintenance Windows
- **Weekly**: Sunday 2:00-4:00 AM (Bangkok time)
- **Monthly**: First Sunday of each month
- **Emergency**: As needed

---

**Last Updated**: January 2024  
**Version**: 1.0.0  
**Maintainer**: Network Monitoring Team

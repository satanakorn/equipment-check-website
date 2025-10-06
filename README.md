# 🌐 3BB Network Monitoring Dashboard

ระบบตรวจสอบและวิเคราะห์อุปกรณ์เครือข่ายสำหรับ 3BB โดยใช้ Streamlit + Supabase

## 🚀 Features

### 📊 Analysis Modules
- **CPU Analyzer** - ตรวจสอบ CPU utilization
- **FAN Analyzer** - ตรวจสอบความเร็วพัดลม (FCC, FCPP, FCPL, FCPS)
- **MSU Analyzer** - ตรวจสอบ Laser Bias Current
- **Line Analyzer** - ตรวจสอบ Line cards performance (BER, Power)
- **Client Analyzer** - ตรวจสอบ Client board performance
- **Fiber Flapping Analyzer** - ตรวจสอบ Fiber flapping issues
- **EOL Analyzer** - ตรวจสอบ End of Life attenuation
- **Core Analyzer** - ตรวจสอบ Loss between core
- **APO Analyzer** - ตรวจสอบ APO remnant issues

### 📈 Dashboard
- **Overview Dashboard** - ภาพรวมสถานะระบบ
- **Basic Statistics** - สถิติพื้นฐานของระบบ
- **Database Status** - สถานะการเชื่อมต่อฐานข้อมูล

### 📋 Reporting
- **PDF Reports** - สร้างรายงาน PDF อัตโนมัติ
- **Summary Tables** - ตารางสรุปผลการตรวจสอบ
- **Export Functions** - ส่งออกข้อมูลในรูปแบบต่างๆ

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- Supabase account
- Streamlit Cloud account (optional)

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd dashboard5
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup Supabase Database

#### 3.1 Create Supabase Project
1. ไปที่ [Supabase](https://supabase.com)
2. สร้างโปรเจคใหม่
3. เก็บ URL และ API Key

#### 3.2 Run Database Schema
```sql
-- รันไฟล์ supabase_schema.sql ใน Supabase SQL Editor
```

#### 3.3 Configure Environment
สร้างไฟล์ `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_ANON_KEY = "your_supabase_anon_key"
```

### 4. Run Application
```bash
streamlit run app9.py
```

## 🚀 Deployment to Streamlit Cloud

### 1. Push to GitHub
```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Deploy to Streamlit Cloud
1. ไปที่ [Streamlit Cloud](https://share.streamlit.io)
2. เชื่อมต่อ GitHub repository
3. ตั้งค่า Secrets ใน Streamlit Cloud:
   - ไปที่ Settings → Secrets
   - เพิ่ม:
   ```toml
   SUPABASE_URL = "your_supabase_project_url"
   SUPABASE_ANON_KEY = "your_supabase_anon_key"
   ```

### 3. Configure App Settings
- **Main file path**: `app9.py`
- **Python version**: 3.8+

## 📁 Project Structure

```
dashboard5/
├── app9.py                 # Main Streamlit application
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── supabase_schema.sql    # Database schema
├── supabase_config.py     # Supabase connection
# viz.py removed
├── report.py              # PDF report generation
├── table1.py              # Summary table
├── .streamlit/
│   ├── config.toml        # Streamlit configuration
│   └── secrets.toml       # Environment variables template
├── data/                  # Reference data files
│   ├── CPU.xlsx
│   ├── FAN.xlsx
│   ├── MSU.xlsx
│   ├── Line.xlsx
│   ├── Client.xlsx
│   └── EOL.xlsx
├── utils/
│   └── filters.py         # Filter utilities
└── Analyzers/             # Analysis modules
    ├── CPU_Analyzer.py
    ├── FAN_Analyzer.py
    ├── MSU_Analyzer.py
    ├── Line_Analyzer.py
    ├── Client_Analyzer.py
    ├── Fiberflapping_Analyzer.py
    ├── EOL_Core_Analyzer.py
    ├── APO_Analyzer.py
    └── Preset_Analyzer.py
```

## 🔧 Configuration

### Database Configuration
- **Supabase**: PostgreSQL database with real-time capabilities
- **Tables**: uploads, analysis_results, reports, users, network_sites, thresholds, alerts

### File Upload
- **Supported formats**: ZIP files containing Excel/CSV data
- **File types**: CPU, FAN, MSU, Line, Client, OSC, FM, Attenuation reports
- **Storage**: Local file system (uploads/) + Supabase metadata

### Analysis Thresholds
- **CPU**: 90% utilization threshold
- **FAN**: FCC(120), FCPP(250), FCPL(120), FCPS(230) Rps
- **MSU**: Laser bias current thresholds
- **Line**: BER and power level thresholds
- **Client**: Input/Output power thresholds

## 📊 Usage Guide

### 1. Upload Data
1. ไปที่หน้า "หน้าแรก"
2. เลือกวันที่
3. อัปโหลดไฟล์ ZIP
4. เลือกไฟล์ที่ต้องการวิเคราะห์
5. คลิก "Run Analysis"

### 2. View Analysis
- **Dashboard**: ภาพรวมระบบและสถิติพื้นฐาน
- **Individual Analyzers**: วิเคราะห์แต่ละประเภทอุปกรณ์
- **Summary Table**: สรุปผลการตรวจสอบ

### 3. Generate Reports
- ไปที่ "Summary table & report"
- คลิก "Download Report (All Sections)"
- ได้ไฟล์ PDF รายงาน

## 🔒 Security

### Authentication (Future)
- User authentication with Supabase Auth
- Role-based access control
- Session management

### Data Protection
- Row Level Security (RLS) enabled
- Encrypted data transmission
- Secure file handling

## 🐛 Troubleshooting

### Common Issues

#### 1. Supabase Connection Error
```
❌ Supabase credentials not found
```
**Solution**: ตรวจสอบ secrets.toml และ environment variables

#### 2. File Upload Error
```
❌ Failed to process ZIP file
```
**Solution**: ตรวจสอบรูปแบบไฟล์และโครงสร้าง ZIP

#### 3. Analysis Error
```
❌ No matching mapping found
```
**Solution**: ตรวจสอบไฟล์ reference data ในโฟลเดอร์ data/

### Debug Mode
```bash
streamlit run app9.py --logger.level=debug
```

## 📞 Support

สำหรับคำถามหรือปัญหาการใช้งาน:
- 📧 Email: support@3bb.co.th
- 📱 Phone: 1530
- 💬 Chat: ผ่านระบบแชทในแอป

## 📄 License

Copyright © 2024 3BB. All rights reserved.

---

**Version**: 1.0.0  
**Last Updated**: January 2024  
**Maintainer**: Network Monitoring Team

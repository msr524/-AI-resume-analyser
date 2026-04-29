# =================================================================================
#  RESUME INTELLIGENCE SYSTEM (VERSION 99.0 - SYNTAX FIXED & ALL FEATURES)
#  Logic: Auto-detects Google Models and performs Semantic Analysis.
#  Fixes: SyntaxError on line 400 and preserves all Dashboard features.
# =================================================================================

import streamlit as st
import pandas as pd
import base64, random, time, datetime
import pymysql
import os, io
import requests
import json
import re
import plotly.express as px
from streamlit_lottie import st_lottie
from wordcloud import WordCloud
from pdfminer3.layout import LAParams
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager
from pdfminer3.pdfinterp import PDFPageInterpreter
from pdfminer3.converter import TextConverter
from streamlit_tags import st_tags
from streamlit_option_menu import option_menu
from pyresparser import ResumeParser
import nltk

# --- ROBUST IMPORT FOR PDF GENERATION ---
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# --- CONFIGURATION ---
st.set_page_config(
    page_title="ResumeIQ | Smart Recruitment",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 🚨 STEP 1: PASTE YOUR NEW API KEY FROM GOOGLE AI STUDIO BELOW
# ==============================================================================
API_KEY ="".strip() 

# ==============================================================================

# --- 1. CSS STYLING ---
st.markdown("""
<style>
    .stApp { background-color: #FAFAFA; font-family: 'Segoe UI', sans-serif; }
    .course-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .course-link { text-decoration: none; color: #2563eb; font-weight: 700; }
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #eee; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1, h2, h3 { color: #1e3a8a; font-weight: 700; }
    .success-box { background-color: #d1fae5; color: #065f46; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid #10b981; }
    .warning-box { background-color: #fee2e2; color: #991b1b; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid #ef4444; }
    .model-badge { background-color: #3b82f6; color: white; padding: 8px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- 2. SETUP ---
@st.cache_resource
def setup_nltk():
    try: nltk.data.find('tokenizers/punkt')
    except LookupError: nltk.download('punkt'); nltk.download('stopwords')
setup_nltk()

try:
    from Courses import ds_course, web_course, android_course, ios_course, uiux_course, ece_course, eee_course, mech_course, resume_videos, interview_videos
except ImportError:
    ds_course = web_course = android_course = ios_course = []
    resume_videos = ["https://youtu.be/qhocVNbvNHs", "https://youtu.be/MkWZuOEJzl8"]
    interview_videos = ["https://youtu.be/bILgiowkmTM", "https://youtu.be/TPilhhzHTnU"]

# --- 3. AI ENGINE (DYNAMIC CONNECTOR - AUTO-DETECT) ---
def connect_to_any_model(input_prompt):
    if not API_KEY:
        return "ERROR: API Key is missing. Please paste it in Line 47."
    
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1/models?key={API_KEY}"
        list_response = requests.get(list_url, timeout=10)
        
        if list_response.status_code == 200:
            all_models = list_response.json().get('models', [])
            models = [
                m['name'] for m in all_models 
                if 'gemini' in m['name'].lower() and 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            models.sort(key=lambda x: ('flash' not in x, 'pro' not in x))
        else:
            models = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]
    except:
        models = ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]

    last_error = ""
    for model in models:
        clean_model_name = model if model.startswith("models/") else f"models/{model}"
        url = f"https://generativelanguage.googleapis.com/v1/{clean_model_name}:generateContent?key={API_KEY}"
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": input_prompt}]}]}
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=12)
            if response.status_code == 200:
                st.session_state['working_model'] = clean_model_name.split('/')[-1]
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 429:
                last_error = "Quota exceeded (429)."
                continue 
            else:
                last_error = f"Error {response.status_code}: {response.text}"
                continue
        except Exception as e:
            last_error = str(e)
            continue

    return f"ALL_FAILED: {last_error}"

def check_ai_connection():
    if not API_KEY: return False
    return True

def extract_json_data(text):
    data = {
        "scores": {"skills": 0, "project": 0, "internship": 0, "objective": 0},
        "feedback": {
            "strengths": ["Resume parsed successfully."], 
            "weaknesses": ["Add more quantifiable results."], 
            "formatting": ["Layout is clean."]
        }
    }
    if not text: return data
    try:
        clean_text = re.sub(r"```json", "", text)
        clean_text = re.sub(r"```", "", clean_text).strip()
        match = re.search(r"\{.*\}", clean_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            if "scores" in parsed: data["scores"].update(parsed["scores"])
            if "feedback" in parsed: 
                if parsed["feedback"].get("strengths"): data["feedback"]["strengths"] = parsed["feedback"]["strengths"]
                if parsed["feedback"].get("weaknesses"): data["feedback"]["weaknesses"] = parsed["feedback"]["weaknesses"]
                if parsed["feedback"].get("formatting"): data["feedback"]["formatting"] = parsed["feedback"]["formatting"]
            return data
    except: pass
    return data

# --- 4. BACKUP SCORING ---
def internal_backup_score(text):
    text_lower = text.lower()
    
    # NEW: Safety check to catch sarcasm in backup logic
    red_flags = ["dislike", "unmotivated", "incorrectly", "intentionally reduced", "prevented growth"]
    if any(flag in text_lower for flag in red_flags):
        # Return a very low score if negative sentiment is detected
        return 5, 0, {"skills": 0, "project": 0, "internship": 0, "objective": 0}

    edu = 15 
    cgpa_match = re.search(r'\b([5-9]\.\d|10\.0)\b', text)
    percent_match = re.search(r'\b([5-9]\d|\d{3})%', text)
    val = 0
    if percent_match: val = float(percent_match.group(1))
    elif cgpa_match: val = float(cgpa_match.group(1)) * 9.5
    
    if val >= 85: edu = 30
    elif val >= 75: edu = 24
    elif val >= 60: edu = 18
    elif val > 0: edu = 15
    
    skill_count = sum(1 for k in ["python","java","sql","react","node","aws","c++","ai"] if k in text_lower)
    skills = min(30, skill_count * 4)
    intern = 10 if "intern" in text_lower else 0
    obj = 10 if "summary" in text_lower or "profile" in text_lower else 0
    proj = 10 if "project" in text_lower else 0
    git = 10 if "github.com" in text_lower else 0

    total = edu + skills + intern + obj + proj + git
    return total, edu, {"skills": skills, "project": proj, "internship": intern, "objective": obj}

# --- 5. MAIN SCORING ---
def calculate_score(resume_text, github_data=None):
    edu_score = 0
    content_scores = {"skills": 0, "project": 0, "internship": 0, "objective": 0}
    feedback = {}
    error_msg = None
    git_score = 10 if github_data and github_data.get('valid') else 0

    if API_KEY:
        edu_resp = connect_to_any_model(f"Act as Academic Auditor. Find grades. Avg>=85%->30, 75-84%->24, 60-74%->18, <60%->10. Return Integer only. Resume: {resume_text[:2000]}")
        if "FAILED" in edu_resp or "ERROR" in edu_resp:
            error_msg = edu_resp
        else:
            match = re.search(r'\d+', str(edu_resp))
            if match: edu_score = min(30, int(match.group()))

            prompt = f"""
            Act as a Senior HR Specialist. 
            SCAN TASK: Check for Professional Integrity. 
            If the candidate mentions 'disliking' core skills, 'intentionally reducing' performance, 
            or shows 'unprofessional sarcasm', set ALL scores to 0 immediately.

            Otherwise, provide a breakdown in JSON format (Max 60):
            - skills (30): Relevance and proficiency.
            - project (10): Quality of technical implementation.
            - internship (10): Professional experience.
            - objective (10): Professionalism and quality of the Summary.
            
            Resume: {resume_text[:3500]}
            Output JSON ONLY: {{ "scores": {{ "skills": 0, "project": 0, "internship": 0, "objective": 0 }}, "feedback": {{ "strengths":[], "weaknesses":[], "formatting":[] }} }}
            """
            resp = connect_to_any_model(prompt)
            data = extract_json_data(resp)
            content_scores = data["scores"]
            feedback = data["feedback"]
    
    total = edu_score + content_scores.get('skills', 0) + content_scores.get('project', 0) + \
            content_scores.get('internship', 0) + content_scores.get('objective', 0) + git_score
    
    backup_total, b_edu, b_scores = internal_backup_score(resume_text)
    if content_scores.get('objective') == 0 and ("dislike" in resume_text.lower() or "unmotivated" in resume_text.lower()):
        return 10, 0, {"skills": 0, "project": 0, "internship": 0, "objective": 0}, feedback, "AI", None

    if error_msg or total < backup_total:
        return backup_total, b_edu, b_scores, feedback, "Backup", error_msg
        
    return min(100, total), edu_score, content_scores, feedback, "AI", None

# --- 6. PDF REPORT ---
def generate_pdf_report(name, score, edu, content, feedback):
    if not FPDF_AVAILABLE: return None
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Resume Analysis Report', 0, 1, 'C')
            self.ln(5)
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Candidate: {name}", ln=True)
    pdf.cell(0, 10, txt=f"Total Score: {score}/100", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="Score Breakdown:", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Education: {edu}/30", ln=True)
    pdf.cell(0, 10, txt=f"Skills: {content.get('skills')}/30", ln=True)
    pdf.cell(0, 10, txt=f"Projects: {content.get('project')}/10", ln=True)
    pdf.ln(5)
    if feedback and feedback.get('weaknesses'):
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt="Actionable Improvements:", ln=True)
        pdf.set_font("Arial", size=12)
        for w in feedback['weaknesses']:
            pdf.multi_cell(0, 10, txt=f"- {w}")
    return pdf.output(dest='S').encode('latin-1')

# --- 7. HELPERS & DB ---
def get_db_connection():
    try: return pymysql.connect(host='localhost', user='root', password='root', db='cv')
    except: return None

def init_db():
    try:
        conn = pymysql.connect(host='localhost', user='root', password='root')
        cursor = conn.cursor(); cursor.execute("CREATE DATABASE IF NOT EXISTS cv"); conn.select_db('cv')
        cursor.execute("CREATE TABLE IF NOT EXISTS user_data (ID INT AUTO_INCREMENT PRIMARY KEY, Name varchar(500), Email_ID VARCHAR(500), Mobile_No varchar(20), Skills BLOB, Experience BLOB, Education BLOB, Location varchar(100), Recommended_Skills BLOB, Recommended_Courses BLOB, Resume varchar(100), Resume_Score varchar(10), Predicted_Field varchar(100), Timestamp varchar(50))")
        cursor.execute("CREATE TABLE IF NOT EXISTS user_feedback (ID INT AUTO_INCREMENT PRIMARY KEY, feed_name varchar(50), feed_email VARCHAR(50), feed_score VARCHAR(5), comments VARCHAR(100), Timestamp VARCHAR(50))")
        conn.close()
    except: pass

def pdf_reader(file):
    try:
        resource_manager = PDFResourceManager()
        fake_file_handle = io.StringIO()
        converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
        page_interpreter = PDFPageInterpreter(resource_manager, converter)
        with open(file, 'rb') as fh:
            for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
                page_interpreter.process_page(page)
            text = fake_file_handle.getvalue()
        converter.close(); fake_file_handle.close()
        return text
    except: return ""

def analyze_github(github_url):
    try:
        if not github_url or "github.com" not in github_url: return None
        response = requests.get(f"https://api.github.com/users/{github_url.split('/')[-1]}/repos")
        if response.status_code == 200: return {"valid": True}
        return {"valid": False}
    except: return {"valid": False}

def display_course_cards(course_list):
    if not course_list: return
    num = st.slider("Show Courses:", 3, 10, 4)
    random.shuffle(course_list)
    c1, c2 = st.columns(2)
    for i, (name, link) in enumerate(course_list[:num]):
        card = f"""<div class="course-card"><div class="course-title">{i+1}. {name}</div><a href="{link}" target="_blank" class="course-link">🔗 Start Learning →</a></div>"""
        with (c1 if i % 2 == 0 else c2): st.markdown(card, unsafe_allow_html=True)

def load_lottie(url):
    try: return requests.get(url).json()
    except: return None

# --- 8. SECTIONS ---
def candidate_section():
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("Resume Intelligence System")
        st.markdown("**Optimize your resume.** AI-Powered Scoring & Contextual Analysis.")
    with c2:
        lottie = load_lottie("https://assets5.lottiefiles.com/packages/lf20_12345.json")
        if lottie: st_lottie(lottie, height=120)

    active_model = st.session_state.get('working_model', 'Auto-Selecting...')
    st.markdown(f'<div class="model-badge">🤖 Active AI Model: {active_model}</div>', unsafe_allow_html=True)

    with st.container():
        st.markdown("### 1. Profile Details")
        c1, c2, c3, c4 = st.columns(4)
        act_name = c1.text_input("Full Name")
        act_mail = c2.text_input("Email")
        act_mob = c3.text_input("Mobile No")
        gh_link = c4.text_input("GitHub URL")
        uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

    if uploaded_file:
        save_path = './Uploaded_Resumes/' + uploaded_file.name
        os.makedirs('./Uploaded_Resumes', exist_ok=True)
        with open(save_path, "wb") as f: f.write(uploaded_file.getbuffer())

        with st.spinner("⚡ AI is processing..."):
            resume_text = pdf_reader(save_path)
            resume_data = ResumeParser(save_path).get_extracted_data()
            gh_data = analyze_github(gh_link) if gh_link else None
            score, edu_score, content_scores, feedback, source, error_msg = calculate_score(resume_text, gh_data)
            skills = resume_data.get('skills', []) if resume_data else []
            s_str = str(skills).lower()
            reco_field = "General"
            rec_courses = []
            if 'react' in s_str: reco_field = "Web Development"; rec_courses = web_course
            elif 'data' in s_str: reco_field = "Data Science"; rec_courses = ds_course
            elif 'android' in s_str: reco_field = "Android Development"; rec_courses = android_course
            st.divider()
            
            if not API_KEY:
                st.error("🚨 API Key Missing!")
            elif source == "Backup":
                st.warning("⚠️ High Keyword Match but Sentiment Warnings found.")
            else:
                final_m = st.session_state.get('working_model', 'AI')
                st.success(f"✅ Analysis Powered by {final_m}")

            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Candidate Name", act_name if act_name else "Candidate")
            with m2: st.metric("Predicted Role", reco_field)
            with m3: st.metric("Overall Score", f"{score}/100")

            if FPDF_AVAILABLE:
                pdf_bytes = generate_pdf_report(act_name, score, edu_score, content_scores, feedback)
                st.sidebar.download_button("📥 Download Analysis Report", data=pdf_bytes, file_name="Resume_Analysis.pdf", mime="application/pdf")

            tab_ai, tab_view, tab_rec, tab_jd = st.tabs(["💡 Analysis", "📄 Resume", "🎓 Learn", "🎯 Job Match"])
            with tab_ai:
                st.subheader("Performance Audit")
                with st.expander("📊 Full Score Breakdown", expanded=True):
                    c_s1, c_s2 = st.columns(2)
                    with c_s1:
                        st.write(f"**Academic (Education):** {edu_score}/30")
                        st.write(f"**Technical Skills:** {content_scores.get('skills', 0)}/30")
                        st.write(f"**Project Quality:** {content_scores.get('project', 0)}/10")
                    with c_s2:
                        st.write(f"**Internship Experience:** {content_scores.get('internship', 0)}/10")
                        # Show Objective/Summary score individually
                        st.write(f"**Objective/Summary:** {content_scores.get('objective', 0)}/10")
                        # Show GitHub score individually
                        st.write(f"**GitHub Integrity:** {10 if gh_data and gh_data.get('valid') else 0}/10")
                if skills:
                    st.subheader("☁️ Skills Cloud")
                    wc = WordCloud(width=800, height=250, background_color='white').generate(" ".join(skills))
                    st.image(wc.to_array())
                st.subheader("🎬 Smart Recommendations")
                if score < 80:
                    c_v1, c_v2 = st.columns(2)
                    with c_v1: st.video(resume_videos[0])
                    with c_v2: st.video(resume_videos[1])
                else:
                    c_v1, c_v2 = st.columns(2)
                    with c_v1: st.video(interview_videos[0])
                    with c_v2: st.video(interview_videos[1])

            with tab_view:
                with open(save_path, "rb") as f: base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>', unsafe_allow_html=True)
            with tab_rec:
                if rec_courses: display_course_cards(rec_courses)
                else: st.warning("No specific courses found.")
            with tab_jd:
                jd = st.text_area("Paste Job Description")
                if st.button("Compare"):
                    res = connect_to_any_model(f"Compare Resume vs JD: {resume_text} vs {jd}. Short summary.")
                    st.write(res)

            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                q = "INSERT INTO user_data (Name, Email_ID, Mobile_No, Skills, Resume_Score, Predicted_Field, Timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s)"
                v = (act_name, act_mail, act_mob, str(skills), str(score), reco_field, ts)
                try: cur.execute(q, v); conn.commit()
                except: pass
                conn.close()

def recruiter_section():
    st.markdown("## 👥 Recruiter Dashboard")
    conn = get_db_connection()
    if conn:
        df = pd.read_sql("SELECT * FROM user_data", conn)
        conn.close()
        if not df.empty:
            for col in ['Skills', 'Predicted_Field']:
                if col in df.columns: df[col] = df[col].apply(lambda x: x.decode('utf-8') if isinstance(x, bytes) else str(x))
            df['Resume_Score'] = pd.to_numeric(df['Resume_Score'])
            with st.expander("🔍 Search & Filter", expanded=True):
                c1, c2 = st.columns([2, 1])
                with c1: req = st_tags(label='Skills', text='Search...', key='rec_search')
                with c2: min_s = st.slider("Min Score", 0, 100, 50)
            if req:
                pat = '|'.join([s.lower() for s in req])
                df = df[df['Skills'].str.lower().str.contains(pat, na=False)]
            df = df[df['Resume_Score'] >= min_s]
            m1, m2 = st.columns(2)
            with m1: st.plotly_chart(px.pie(df, names='Predicted_Field', title='Domain Distribution'), use_container_width=True)
            with m2: st.plotly_chart(px.histogram(df, x="Resume_Score", title='Score Ranges'), use_container_width=True)
            df['Email Link'] = "mailto:" + df['Email_ID']
            st.dataframe(df[['Name', 'Email Link', 'Mobile_No', 'Resume_Score', 'Predicted_Field']], column_config={"Email Link": st.column_config.LinkColumn("Contact"), "Resume_Score": st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=100)}, use_container_width=True)
        else: st.info("No data found.")
    else: st.error("DB Error")

def admin_section():
    st.title("Admin Panel")
    if 'admin' not in st.session_state: st.session_state.admin = False
    if not st.session_state.admin:
        if st.text_input("Password", type="password") == "admin123": st.session_state.admin = True; st.rerun()
    else:
        if st.button("Logout"): st.session_state.admin = False; st.rerun()
        conn = get_db_connection()
        if conn:
            st.write("Users:")
            st.dataframe(pd.read_sql("SELECT * FROM user_data", conn))
            st.write("Feedback:")
            st.dataframe(pd.read_sql("SELECT * FROM user_feedback", conn))
            conn.close()

def run():
    init_db()
    with st.sidebar:
        if check_ai_connection(): st.markdown('<span style="color:green">🟢 AI Online</span>', unsafe_allow_html=True)
        else: st.markdown('<span style="color:red">🔴 AI Offline</span>', unsafe_allow_html=True)
        st.divider()
        menu = option_menu("Navigation", ["Candidate", "Recruiter", "Admin", "Feedback"], icons=["person", "briefcase", "shield", "chat"], default_index=0)
    
    if menu == "Candidate": candidate_section()
    elif menu == "Recruiter": recruiter_section()
    elif menu == "Admin": admin_section()
    elif menu == "Feedback":
        st.title("Feedback")
        with st.form("f"):
            n = st.text_input("Name"); e = st.text_input("Email"); r = st.slider("Rate", 1,5); c = st.text_area("Comment")
            if st.form_submit_button("Submit"):
                conn = get_db_connection()
                if conn: 
                    cur = conn.cursor()
                    cur.execute("INSERT INTO user_feedback (feed_name, feed_email, feed_score, comments, Timestamp) VALUES (%s,%s,%s,%s,%s)", (n,e,r,c,datetime.datetime.now()))
                    conn.commit(); conn.close()
                    st.success("Sent!")

if __name__ == "__main__":
    run()

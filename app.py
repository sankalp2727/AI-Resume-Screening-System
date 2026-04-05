import spacy
nlp = spacy.load("en_core_web_sm")
from flask import Flask, render_template, request
import os
import re
import csv
import smtplib
import matplotlib
matplotlib.use('Agg')
from email.mime.text import MIMEText
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Try better PDF reader
try:
    import pdfplumber
    USE_PDFPLUMBER = True
except:
    import PyPDF2
    USE_PDFPLUMBER = False

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)

# -----------------------------
# 🔴 EMAIL CONFIG (PUT YOUR DETAILS HERE)
# -----------------------------
SENDER_EMAIL = "your_email@gmail.com"
APP_PASSWORD = "your_app_password"


# -----------------------------
# EMAIL FUNCTION
# -----------------------------
def send_email(to_email, score):

    if score > 70:
        subject = "Interview Shortlisting Notification"
        body = f"""
Dear Candidate,

Congratulations! You have been shortlisted for the interview.

Your Resume Score: {score}%

Regards,
HR Team
"""
    else:
        subject = "Application Status Update"
        body = f"""
Dear Candidate,

Thank you for applying.

We regret to inform you that you are not shortlisted.

Your Resume Score: {score}%

Regards,
HR Team
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent to:", to_email)

    except Exception as e:
        print("❌ Email error:", e)


# -----------------------------
# PDF TEXT EXTRACTION
# -----------------------------
def extract_text(file_path):

    text = ""

    if USE_PDFPLUMBER:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    else:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"

    return text


# -----------------------------
# ✅ FINAL EMAIL EXTRACTION (BEST VERSION)
# -----------------------------
def extract_email(text):

    text = text.replace("\n", " ")

    # -----------------------------
    # 1. Try NORMAL regex first
    # -----------------------------
    pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
    emails = re.findall(pattern, text)

    if emails:
        return max(emails, key=len).lower()

    # -----------------------------
    # 2. AI fallback using spaCy
    # -----------------------------
    doc = nlp(text)

    for token in doc:
        if "@" in token.text and "." in token.text:
            return token.text.lower()

    # -----------------------------
    # 3. SMART FIX for merged text
    # -----------------------------
    merged_text = text.replace(" ", "")
    emails = re.findall(pattern, merged_text)

    if emails:
        return max(emails, key=len).lower()

    return "Not Found"

# -----------------------------
# PHONE EXTRACTION
# -----------------------------
def extract_phone(text):

    pattern = r'\+?\d[\d\s\-]{8,15}'
    match = re.search(pattern, text)

    return match.group() if match else "Not Found"


# -----------------------------
# RESUME MATCHING
# -----------------------------
def match_resume(resume_text, job_desc):

    documents = [resume_text, job_desc]

    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform(documents)

    similarity = cosine_similarity(vectors[0:1], vectors[1:2])

    return round(similarity[0][0] * 100, 2)


# -----------------------------
# HOME
# -----------------------------
@app.route('/')
def home():
    return render_template("index.html")


# -----------------------------
# UPLOAD
# -----------------------------
@app.route('/upload', methods=['GET', 'POST'])
def upload():

    if request.method == 'POST':

        files = request.files.getlist('resume')
        job_desc = request.form.get('job_desc')

        results = []

        for file in files:

            if file.filename == "":
                continue

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            resume_text = extract_text(file_path)

            print("\n--- DEBUG TEXT ---")
            print(resume_text[:300])

            email = extract_email(resume_text)
            phone = extract_phone(resume_text)
            score = match_resume(resume_text, job_desc)

            print("📧 Extracted Email:", email)

            # SEND EMAIL
            if email != "Not Found":
                send_email(email, score)
            else:
                print("⚠️ Email not found in:", file.filename)

            results.append({
                "filename": file.filename,
                "email": email,
                "phone": phone,
                "score": score
            })

        if not results:
            return render_template("upload.html", message="No resumes uploaded!")

        # Sort results
        results = sorted(results, key=lambda x: x['score'], reverse=True)

        # Dashboard stats
        total_candidates = len(results)
        average_score = round(sum(r['score'] for r in results) / total_candidates, 2)
        top_candidate = results[0]['filename']

        # Save CSV
        with open("results.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Resume", "Email", "Phone", "Score"])

            for r in results:
                writer.writerow([r["filename"], r["email"], r["phone"], r["score"]])

        # Chart
        names = [r['filename'] for r in results]
        scores = [r['score'] for r in results]

        plt.figure(figsize=(8,5))
        plt.bar(names, scores)
        plt.xticks(rotation=30)
        plt.ylabel("Match Score (%)")
        plt.title("Resume Ranking")

        plt.tight_layout()
        plt.savefig("static/chart.png")
        plt.close()

        return render_template(
            "results.html",
            results=results,
            total_candidates=total_candidates,
            average_score=average_score,
            top_candidate=top_candidate
        )

    return render_template("upload.html")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
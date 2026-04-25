from flask import Flask, render_template, request, redirect, session
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import random
from sklearn.ensemble import IsolationForest
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
import os

import pyotp
import qrcode

app = Flask(__name__)
app.secret_key = "healthcare_ai_secret"

# ================= SESSION =================
app.permanent_session_lifetime = timedelta(minutes=10)

# ================= MODEL =================
model = joblib.load("model/ml_fl_xai_model.pkl")
scaler = joblib.load("model/scaler.pkl")

# ================= USERS =================
USERS = {
    "admin": generate_password_hash("admin123"),
    "doctor": generate_password_hash("doc123")
}

AUTHORIZED_EMAILS = {
    "admin": "dhevananda09@gmail.com",
    "doctor": "tvdhevananda@gmail.com"
}

# ================= TOTP =================
USER_SECRETS = {
    "admin": pyotp.random_base32(),
    "doctor": pyotp.random_base32()
}

# ================= LOGIN SECURITY =================
login_attempts = defaultdict(int)
lockout_time = {}

# ================= BEHAVIOR MODEL =================
# ================= BEHAVIOR MODEL =================
behavior_model = IsolationForest(contamination=0.2, random_state=42)
behavior_model.fit([[0,5,0],[0,3,0],[0,7,0],[0,2,0],[0,6,0]])

def get_behavior_features(time, freq):
    return [[1 if time=="Night" else 0, int(freq), 1 if int(freq)>10 else 0]]

def detect_anomaly(time, freq):
    return behavior_model.predict(get_behavior_features(time,freq))[0] == -1


def get_behavior_label(time, freq):
    freq = int(freq)

   
    if time == "Night" and freq > 8:
        return "Suspicious"

    # ML-based (backup)
    return "Suspicious" if detect_anomaly(time, freq) else "Normal"

# ================= FEDERATED =================
def federated_predict(data):
    predictions = []
    for _ in range(3):
        pred = model.predict(data)[0]
        predictions.append(pred)
    return max(set(predictions), key=predictions.count)

# ================= EMAIL =================
def send_email(receiver, subject, body):
    sender = "tvdhevananda@gmail.com"
    password = "idxn ehlp xzre kthn"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email error:", e)

def send_alert(username, score):
    admin_email = AUTHORIZED_EMAILS.get("admin")
    send_email(admin_email, "🚨 HIGH RISK ALERT",
               f"User: {username}\nRisk Score: {score}")

# ================= RISK =================
def calculate_risk_score(role,time,device,location,sensitivity,violation):
    score=0
    if time=="Night": score+=25
    if device=="Unknown": score+=30
    if location=="Outside": score+=20
    if sensitivity=="High": score+=25
    if violation=="Yes": score+=40
    return score

def hybrid_risk_score(base, anomaly):
    return base + (20 if anomaly else 0)

def final_decision(score):
    return "LOW" if score<40 else "MEDIUM" if score<80 else "HIGH"

def security_action(risk):
    return "Allowed" if risk=="LOW" else "Monitor" if risk=="MEDIUM" else "Blocked"

# ================= LOGIN =================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":

        username=request.form.get("username")
        password=request.form.get("password")
        email=request.form.get("email")
        otp_method=request.form.get("otp_method","email")

        ip=request.remote_addr

        if ip in lockout_time and datetime.now()<lockout_time[ip]:
            return render_template("login.html", error="🔒 Locked for 5 minutes")

        if username not in USERS:
            return render_template("login.html", error="Invalid username")

        if not check_password_hash(USERS[username], password):
            login_attempts[ip]+=1

            if login_attempts[ip]>=3:
                lockout_time[ip]=datetime.now()+timedelta(minutes=5)
                return render_template("login.html",
                    error="⚠️ Too many attempts! Locked 5 mins")

            return render_template("login.html",
                error=f"Invalid password ({login_attempts[ip]}/3)")

        if AUTHORIZED_EMAILS.get(username)!=email:
            return render_template("login.html", error="Unauthorized email")

        login_attempts[ip]=0

# ✅ ADD HERE
        login_log = pd.DataFrame([{
            "Username": username,
            "Email": email,
            "Login Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "IP Address": ip
        }])

        login_log.to_csv("login_logs.csv",
                 mode="a",
                 header=not os.path.exists("login_logs.csv"),
                 index=False)

  

        session["username"]=username
        session["otp_method"]=otp_method

        # ================= EMAIL OTP =================
        if otp_method=="email":

            otp=str(random.randint(100000,999999))
            session["otp"]=otp
            session["otp_expiry"]=(datetime.now()+timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")

            send_email(email,"OTP",f"Your OTP: {otp}")
            return redirect("/otp")

        # ================= TOTP =================
        else:
            session["totp_secret"]=USER_SECRETS[username]
            return redirect("/setup_totp")   # 🔥 FIXED

    return render_template("login.html")

# ================= OTP =================
@app.route("/otp", methods=["GET","POST"])
def otp_verify():

    method=session.get("otp_method","email")

    if request.method=="POST":

        user_input=request.form["otp"]

        # EMAIL OTP
        if method=="email":

            expiry=session.get("otp_expiry")

            if expiry:
                expiry=datetime.strptime(expiry,"%Y-%m-%d %H:%M:%S")

                if datetime.now()>expiry:
                    return render_template("otp.html", error="OTP expired")

            if user_input==session.get("otp"):
                session.pop("otp",None)
                return redirect("/home")

        # TOTP
        else:
            secret=session.get("totp_secret")

            if secret:
                totp=pyotp.TOTP(secret)
                if totp.verify(user_input):
                    return redirect("/home")

        return render_template("otp.html", error="Invalid OTP", method=method)

    return render_template("otp.html",
                           method=method,
                           expiry_time=session.get("otp_expiry"))

# ================= RESEND =================
@app.route("/resend_otp")
def resend():
    if session.get("otp_method")=="email":

        username=session.get("username")
        email=AUTHORIZED_EMAILS.get(username)

        otp=str(random.randint(100000,999999))
        session["otp"]=otp
        session["otp_expiry"]=(datetime.now()+timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")

        send_email(email,"New OTP",f"Your OTP: {otp}")

    return redirect("/otp")

# ================= QR =================
@app.route("/setup_totp")
def setup():

    user=session.get("username")
    secret=USER_SECRETS.get(user)

    if not secret:
        return redirect("/")

    uri=pyotp.TOTP(secret).provisioning_uri(name=user, issuer_name="Healthcare AI")

    img=qrcode.make(uri)
    img.save("static/qr.png")

    return render_template("setup_totp.html")

# ================= HOME =================
@app.route("/home", methods=["GET","POST"])
def home():

    if "username" not in session:
        return redirect("/")

    prediction=None
    explanation=[]
    risk_score=0
    action=None
    high_risk=False
    risk_color="green"
    behavior=None

    ip = request.remote_addr

    if request.method=="POST":

        role=request.form["role"]
        time=request.form["time"]
        device=request.form["device"]
        location=request.form["location"]
        sensitivity=request.form["sensitivity"]
        freq=request.form["freq"]
        violation=request.form["violation"]

        data=np.array([[0,0,0,0,0,int(freq),0]])
        scaled=scaler.transform(data)

        pred = federated_predict(scaled)  # 🔥 FIXED

        base=calculate_risk_score(role,time,device,location,sensitivity,violation)
        behavior = get_behavior_label(time, freq)
        anomaly = True if behavior == "Suspicious" else False

        if anomaly:
            explanation.append("Suspicious behavior detected")
        if time=="Night":
            explanation.append("Access at unusual time")
        if device=="Unknown":
            explanation.append("Unknown device used")
        if location=="Outside":
            explanation.append("Access from outside location")
        if violation=="Yes":
            explanation.append("Policy violation detected")

        if not explanation:
            explanation.append("Normal safe activity")

        risk_score=hybrid_risk_score(base, anomaly)
        prediction=final_decision(risk_score)
        action=security_action(prediction)

        risk_color="green" if prediction=="LOW" else "orange" if prediction=="MEDIUM" else "red"

        if prediction=="HIGH":
            high_risk=True
            send_alert(session.get("username"), risk_score)

        log=pd.DataFrame([{
            "Time":datetime.now(),
            "Username": session["username"],
            "Role":role,
            "Device":device,
            "Location":location,
            "Risk":prediction,
            "Score":risk_score,
            "IP": ip,
            "Behavior":behavior
        }])

        log.to_csv("access_logs.csv", mode="a",
                   header=not os.path.exists("access_logs.csv"),
                   index=False)

    return render_template("index.html",
        prediction=prediction,
        explanation=explanation,
        risk_score=risk_score,
        action=action,
        high_risk=high_risk,
        risk_color=risk_color,
        behavior=behavior)

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():

    try:
        logs = pd.read_csv("access_logs.csv")
    except:
        logs = pd.DataFrame()

    try:
        login_logs = pd.read_csv("login_logs.csv")
    except:
        login_logs = pd.DataFrame()

    total = len(logs)
    low_count = len(logs[logs["Risk"]=="LOW"]) if not logs.empty else 0
    medium_count = len(logs[logs["Risk"]=="MEDIUM"]) if not logs.empty else 0
    high_count = len(logs[logs["Risk"]=="HIGH"]) if not logs.empty else 0

    avg_score = logs["Score"].mean() if not logs.empty else 0
    total_logins = len(login_logs) if not login_logs.empty else 0
    high_logs = logs[logs["Risk"]=="HIGH"].tail(5) if not logs.empty else pd.DataFrame()

    return render_template("dashboard.html",
        logs=logs,
        login_logs=login_logs,
        total=total,
        low_count=low_count,
        medium_count=medium_count,
        high_count=high_count,
        avg_score=avg_score,
        total_logins=total_logins,
        high_logs=high_logs)

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= RUN =================
if __name__=="__main__":
    app.run(debug=True)
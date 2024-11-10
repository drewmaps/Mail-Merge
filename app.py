from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import smtplib
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Use environment variables for configuration
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'static/signatures')

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    smtp_password = db.Column(db.String(120), nullable=True)
    signature_path = db.Column(db.String(200), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def attach_signature_image(message, signature_path):
    """Attach signature image to email"""
    if signature_path and os.path.exists(signature_path):
        with open(signature_path, 'rb') as img_file:
            img = MIMEImage(img_file.read())
            img.add_header('Content-ID', '<signature>')
            message.attach(img)
    return message

def send_personalized_email(recipient_email, subject, body, sender_email, smtp_password, signature_path):
    """Send a single personalized email with signature"""
    try:
        message = MIMEMultipart('related')
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = subject
        
        html_body = f"""
        <html>
            <body>
                <p>{body}</p>
                <br>
                {"<img src='cid:signature' alt='Signature' style='max-width: 200px;'/>" if signature_path else ""}
            </body>
        </html>
        """
        
        html_part = MIMEText(html_body, 'html')
        message.attach(html_part)
        
        if signature_path:
            message = attach_signature_image(message, signature_path)
        
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, smtp_password)
            server.send_message(message)
        
        return True
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {str(e)}")
        return False

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        smtp_password = request.form['smtp_password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
            
        user = User(username=username, email=email)
        user.set_password(password)
        user.smtp_password = smtp_password
        
        # Handle signature upload
        if 'signature' in request.files:
            file = request.files['signature']
            if file.filename:
                filename = secure_filename(f"{username}_signature.png")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                user.signature_path = filepath
        
        db.session.add(user)
        db.session.commit()
        flash('Registration successful')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'signature' in request.files:
            file = request.files['signature']
            if file.filename:
                filename = secure_filename(f"{current_user.username}_signature.png")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                current_user.signature_path = filepath
                
        if request.form.get('smtp_password'):
            current_user.smtp_password = request.form['smtp_password']
            
        db.session.commit()
        flash('Profile updated successfully')
        return redirect(url_for('profile'))
        
    return render_template('profile.html')

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded')
            return redirect(request.url)
            
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
            
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file')
            return redirect(request.url)
            
        try:
            df = pd.read_csv(file)
            required_columns = ['email', 'name']
            if not all(col in df.columns for col in required_columns):
                flash('CSV must contain email and name columns')
                return redirect(request.url)
                
            subject_template = request.form['subject']
            body_template = request.form['body']
            
            success_count = 0
            failed_count = 0
            
            for _, row in df.iterrows():
                personalized_subject = subject_template.format(**row.to_dict())
                personalized_body = body_template.format(**row.to_dict())
                
                if send_personalized_email(
                    row['email'],
                    personalized_subject,
                    personalized_body,
                    current_user.email,
                    current_user.smtp_password,
                    current_user.signature_path
                ):
                    success_count += 1
                else:
                    failed_count += 1
            
            flash(f'Sent {success_count} emails successfully. {failed_count} emails failed.')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(request.url)
    
    return render_template('index.html')

# Create database tables
def init_db():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
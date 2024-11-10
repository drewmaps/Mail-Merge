from flask import Flask, render_template, request, flash, redirect, url_for
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import os
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = '3d6f45a5fc12445dbac2f59c3b6c7cb1'  # Use your secret key

# Use your working email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "andrewmatope@gmail.com"  # Your email that worked in the test
SENDER_PASSWORD = "nsyb bkbc uysp mgkj"  # Your working app password

def send_personalized_email(recipient_email, subject, body):
    """Send a single personalized email"""
    try:
        message = MIMEMultipart()
        message['From'] = SENDER_EMAIL
        message['To'] = recipient_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
            print(f"Successfully sent email to {recipient_email}")
        return True
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {str(e)}")
        return False

@app.route('/', methods=['GET', 'POST'])
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
            # Read CSV
            df = pd.read_csv(file)
            
            # Get email template from form
            subject_template = request.form['subject']
            body_template = request.form['body']
            
            success_count = 0
            failed_count = 0
            
            # Process each row
            for _, row in df.iterrows():
                try:
                    # Personalize subject and body
                    personalized_subject = subject_template.format(**row.to_dict())
                    personalized_body = body_template.format(**row.to_dict())
                    
                    # Send email
                    if send_personalized_email(row['email'], personalized_subject, personalized_body):
                        success_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    print(f"Error processing row {row}: {str(e)}")
                    failed_count += 1
            
            flash(f'Sent {success_count} emails successfully. {failed_count} emails failed.')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(request.url)
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
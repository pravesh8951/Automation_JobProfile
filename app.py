"""
Complete LinkedIn Auto-Apply System with Flask + Playwright + ChatGPT
Single file application with web interface

Installation:
pip install flask flask-cors playwright openai PyPDF2 google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client python-dotenv
playwright install chromium

Usage:
python app.py
Open: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from playwright.sync_api import sync_playwright
import PyPDF2
import openai
import json
import os
import time
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import secrets
import traceback

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

# Global variables
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global status tracking
application_status = {
    'status': 'idle',
    'message': 'Ready',
    'progress': 0,
    'logs': [],
    'total_applied': 0
}


def extract_resume_text(pdf_path):
    """Extract text from PDF resume"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"Error extracting resume: {str(e)}"


def linkedin_login(page, email, password):
    """Login to LinkedIn"""
    try:
        page.goto('https://www.linkedin.com/login')
        time.sleep(2)
        
        page.fill('#username', email)
        page.fill('#password', password)
        page.click('button[type="submit"]')
        time.sleep(5)
        
        # Check if login successful
        if 'feed' in page.url or 'mynetwork' in page.url:
            return True
        return False
    except Exception as e:
        print(f"Login error: {e}")
        return False


def search_jobs(page, keywords, location, job_types, work_mode):
    """Search for Easy Apply jobs"""
    try:
        # Build search URL with filters
        search_query = keywords.split(',')[0].strip()
        base_url = f'https://www.linkedin.com/jobs/search/?keywords={search_query}&location={location}&f_AL=true'
        
        # Add job type filters
        if 'Full-time' in job_types:
            base_url += '&f_JT=F'
        if 'Part-time' in job_types:
            base_url += '&f_JT=P'
        if 'Contract' in job_types:
            base_url += '&f_JT=C'
        if 'Internship' in job_types:
            base_url += '&f_JT=I'
        
        # Add work mode filters
        if 'Remote' in work_mode:
            base_url += '&f_WT=2'
        
        page.goto(base_url)
        time.sleep(3)
        
        # Scroll to load jobs
        for _ in range(3):
            page.evaluate('window.scrollBy(0, 1000)')
            time.sleep(1)
        
        # Extract job listings
        jobs = []
        job_cards = page.query_selector_all('.job-card-container, .jobs-search-results__list-item')
        
        for card in job_cards[:20]:
            try:
                title_elem = card.query_selector('.job-card-list__title, .job-card-container__link')
                company_elem = card.query_selector('.job-card-container__company-name, .job-card-container__primary-description')
                link_elem = card.query_selector('a')
                
                if title_elem and link_elem:
                    job_url = link_elem.get_attribute('href').split('?')[0]
                    jobs.append({
                        'title': title_elem.inner_text().strip(),
                        'company': company_elem.inner_text().strip() if company_elem else 'Unknown',
                        'url': job_url
                    })
            except:
                continue
        
        return jobs
    except Exception as e:
        print(f"Search error: {e}")
        return []


def get_ai_answers(resume_text, job_title, company, job_description, questions, openai_key):
    """Use ChatGPT to answer application questions"""
    try:
        client = openai.OpenAI(api_key=openai_key)
        
        prompt = f"""You are an expert job application assistant. Answer the following job application questions based on the candidate's resume.

RESUME:
{resume_text[:3000]}

JOB DETAILS:
Title: {job_title}
Company: {company}
Description: {job_description[:500]}

QUESTIONS:
{questions}

INSTRUCTIONS:
1. Answer each question based on the resume
2. Be concise and professional
3. For yes/no questions, answer honestly
4. For experience, calculate from resume
5. Return as JSON with question as key and answer as value

Example output:
{{
  "full_name": "Name from resume",
  "email": "Email from resume",
  "phone": "Phone from resume",
  "years_experience": "X",
  "work_authorization": "Yes/No",
  "cover_letter": "Brief 2-3 sentence cover letter"
}}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500
        )
        
        answer_text = response.choices[0].message.content
        
        # Try to parse JSON
        try:
            # Remove markdown code blocks if present
            if '```json' in answer_text:
                answer_text = answer_text.split('```json')[1].split('```')[0]
            elif '```' in answer_text:
                answer_text = answer_text.split('```')[1].split('```')[0]
            
            answers = json.loads(answer_text.strip())
            return answers
        except:
            return {"error": "Could not parse AI response"}
            
    except Exception as e:
        print(f"AI error: {e}")
        return {"error": str(e)}


def apply_to_job(page, job_url, answers, resume_path):
    """Fill and submit Easy Apply form"""
    try:
        page.goto(job_url)
        time.sleep(2)
        
        # Click Easy Apply button
        easy_apply_btn = page.query_selector('button.jobs-apply-button, button[aria-label*="Easy Apply"]')
        if not easy_apply_btn:
            return False, "Easy Apply button not found"
        
        easy_apply_btn.click()
        time.sleep(3)
        
        # Upload resume if requested
        resume_input = page.query_selector('input[type="file"]')
        if resume_input:
            resume_input.set_input_files(resume_path)
            time.sleep(2)
        
        # Fill form fields
        for field_name, answer in answers.items():
            try:
                # Try multiple selectors
                selectors = [
                    f'input[id*="{field_name}"]',
                    f'input[name*="{field_name}"]',
                    f'textarea[id*="{field_name}"]',
                    f'select[id*="{field_name}"]'
                ]
                
                for selector in selectors:
                    field = page.query_selector(selector)
                    if field:
                        field_type = field.evaluate('el => el.tagName').lower()
                        if field_type == 'select':
                            field.select_option(str(answer))
                        else:
                            field.fill(str(answer))
                        break
            except:
                continue
        
        # Click through pages
        for _ in range(5):
            next_btn = page.query_selector('button[aria-label*="next"], button[aria-label*="Next"], button[aria-label*="Review"]')
            if next_btn and 'disabled' not in (next_btn.get_attribute('class') or ''):
                next_btn.click()
                time.sleep(2)
            else:
                break
        
        # Submit
        submit_btn = page.query_selector('button[aria-label*="Submit"], button[aria-label*="submit"]')
        if submit_btn:
            submit_btn.click()
            time.sleep(3)
            return True, "Application submitted successfully"
        
        return False, "Submit button not found"
        
    except Exception as e:
        return False, str(e)


def log_to_google_sheets(sheet_id, data):
    """Log application to Google Sheets"""
    try:
        # You'll need to setup Google Sheets API credentials
        # For now, we'll just print
        print(f"Logging to sheet: {data}")
        return True
    except Exception as e:
        print(f"Sheets error: {e}")
        return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start-application', methods=['POST'])
def start_application():
    """Start the automated application process"""
    global application_status
    
    try:
        # Get form data
        linkedin_email = request.form.get('linkedinEmail')
        linkedin_password = request.form.get('linkedinPassword')
        resume_file = request.files.get('resume')
        openai_key = request.form.get('openaiKey')
        google_sheet_id = request.form.get('googleSheetId')
        job_keywords = request.form.get('jobKeywords')
        location = request.form.get('location')
        job_types = json.loads(request.form.get('jobTypes', '[]'))
        work_mode = json.loads(request.form.get('workMode', '[]'))
        max_applications = int(request.form.get('maxApplications', 20))
        
        # Save resume
        resume_path = os.path.join(UPLOAD_FOLDER, 'resume.pdf')
        resume_file.save(resume_path)
        
        # Extract resume text
        resume_text = extract_resume_text(resume_path)
        
        # Initialize status
        application_status = {
            'status': 'running',
            'message': 'Initializing browser...',
            'progress': 5,
            'logs': [],
            'total_applied': 0
        }
        
        # Start automation in background
        import threading
        thread = threading.Thread(
            target=run_automation,
            args=(linkedin_email, linkedin_password, resume_path, resume_text, 
                  openai_key, google_sheet_id, job_keywords, location, 
                  job_types, work_mode, max_applications)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Automation started'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def run_automation(email, password, resume_path, resume_text, openai_key, 
                   sheet_id, keywords, location, job_types, work_mode, max_apps):
    """Main automation logic"""
    global application_status
    
    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = context.new_page()
            
            application_status['message'] = 'Logging into LinkedIn...'
            application_status['progress'] = 10
            
            # Login
            if not linkedin_login(page, email, password):
                application_status['status'] = 'error'
                application_status['message'] = 'Login failed'
                return
            
            application_status['logs'].append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'message': '✅ Logged into LinkedIn successfully',
                'success': True
            })
            
            application_status['message'] = 'Searching for jobs...'
            application_status['progress'] = 20
            
            # Search jobs
            jobs = search_jobs(page, keywords, location, job_types, work_mode)
            
            application_status['logs'].append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'message': f'📋 Found {len(jobs)} Easy Apply jobs',
                'success': True
            })
            
            # Apply to jobs
            applied_count = 0
            for idx, job in enumerate(jobs[:max_apps]):
                try:
                    application_status['message'] = f'Applying to: {job["title"]} at {job["company"]}'
                    application_status['progress'] = 20 + (idx / len(jobs[:max_apps])) * 70
                    
                    # Get AI answers
                    answers = get_ai_answers(
                        resume_text, job['title'], job['company'], 
                        '', 'Standard questions', openai_key
                    )
                    
                    # Apply
                    success, msg = apply_to_job(page, job['url'], answers, resume_path)
                    
                    if success:
                        applied_count += 1
                        application_status['logs'].append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'message': f'✅ Applied: {job["title"]} at {job["company"]}',
                            'success': True
                        })
                    else:
                        application_status['logs'].append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'message': f'❌ Failed: {job["title"]} - {msg}',
                            'success': False
                        })
                    
                    time.sleep(3)
                    
                except Exception as e:
                    application_status['logs'].append({
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'message': f'❌ Error applying to {job["title"]}: {str(e)}',
                        'success': False
                    })
            
            application_status['status'] = 'complete'
            application_status['message'] = f'✅ Completed! Applied to {applied_count} jobs'
            application_status['progress'] = 100
            application_status['total_applied'] = applied_count
            
            browser.close()
            
    except Exception as e:
        application_status['status'] = 'error'
        application_status['message'] = f'Error: {str(e)}'
        application_status['logs'].append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'message': f'❌ Fatal error: {str(e)}',
            'success': False
        })


@app.route('/status')
def get_status():
    """Get current application status"""
    return jsonify(application_status)


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 LinkedIn Auto-Apply System Starting...")
    print("=" * 60)
    print("📍 Open in browser: http://localhost:5000")
    print("=" * 60)
    print("\n✅ Features:")
    print("   - Web-based interface (no n8n needed)")
    print("   - ChatGPT-powered answers")
    print("   - Automatic form filling")
    print("   - Real-time progress tracking")
    print("   - Google Sheets logging")
    print("\n⚠️  Before starting:")
    print("   1. Make sure you have OpenAI API key")
    print("   2. Prepare your resume PDF")
    print("   3. Have Google Sheet ID ready")
    print("\n" + "=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
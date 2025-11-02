"""
Enhanced LinkedIn Auto-Apply System with Gemini AI
- Server-side Gemini API conf
iguration
- Optional Google Sheets logging
- Better form field detection
- Human-like automation

Installation:
pip install flask flask-cors playwright PyPDF2 google-generativeai gspread oauth2client python-dotenv
playwright install chromium

Create .env file with:
GEMINI_API_KEY=your_gemini_api_key_here

Usage:
python app.py
Open: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import PyPDF2
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import time
import random
from datetime import datetime
from dotenv import load_dotenv
import secrets
import traceback
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
CORS(app)

# Global variables
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configure Gemini API from environment
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini API configured from environment")
else:
    print("⚠️  WARNING: GEMINI_API_KEY not found in .env file")

# Global status tracking
application_status = {
    'status': 'idle',
    'message': 'Ready',
    'progress': 0,
    'logs': [],
    'total_applied': 0
}


def human_delay(min_sec=2, max_sec=5):
    """Add random human-like delay"""
    time.sleep(random.uniform(min_sec, max_sec))


def human_type(element, text, page):
    """Type text with human-like speed"""
    element.click()
    time.sleep(random.uniform(0.1, 0.3))
    for char in text:
        element.type(char)
        time.sleep(random.uniform(0.05, 0.15))
    time.sleep(random.uniform(0.2, 0.5))


def extract_resume_text(pdf_path):
    """Extract text from PDF resume with better formatting"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        # Clean up text
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
    except Exception as e:
        print(f"Error extracting resume: {str(e)}")
        return ""


def linkedin_login(page, email, password):
    """Login to LinkedIn with human-like behavior"""
    try:
        page.goto('https://www.linkedin.com/login', wait_until='domcontentloaded')
        human_delay(2, 3)
        
        # Type email
        email_field = page.wait_for_selector('#username', timeout=10000)
        human_type(email_field, email, page)
        
        # Type password
        password_field = page.query_selector('#password')
        human_type(password_field, password, page)
        
        # Click login
        human_delay(0.5, 1)
        page.click('button[type="submit"]')
        human_delay(5, 7)
        
        # Handle potential verification
        if 'checkpoint' in page.url or 'challenge' in page.url:
            print("⚠️  Security checkpoint detected. Please complete manually...")
            human_delay(30, 40)
        
        # Check if login successful
        if 'feed' in page.url or 'mynetwork' in page.url or page.query_selector('[data-id="voyager-feed"]'):
            return True
        return False
    except Exception as e:
        print(f"Login error: {e}")
        traceback.print_exc()
        return False


def search_jobs(page, keywords, location, job_types, work_mode):
    """Search for Easy Apply jobs with better filtering"""
    try:
        # Build search URL
        search_query = keywords.split(',')[0].strip().replace(' ', '%20')
        location_query = location.strip().replace(' ', '%20')
        base_url = f'https://www.linkedin.com/jobs/search/?keywords={search_query}&location={location_query}&f_AL=true'
        
        # Add job type filters (LinkedIn filter codes)
        job_type_codes = []
        if 'Full-time' in job_types:
            job_type_codes.append('F')
        if 'Part-time' in job_types:
            job_type_codes.append('P')
        if 'Contract' in job_types:
            job_type_codes.append('C')
        if 'Internship' in job_types:
            job_type_codes.append('I')
        
        if job_type_codes:
            base_url += '&f_JT=' + '%2C'.join(job_type_codes)
        
        # Add work mode filters
        if 'Remote' in work_mode:
            base_url += '&f_WT=2'
        if 'Hybrid' in work_mode:
            base_url += '&f_WT=3'
        
        page.goto(base_url, wait_until='domcontentloaded')
        human_delay(3, 5)
        
        # Scroll to load more jobs
        for i in range(3):
            page.evaluate('window.scrollBy(0, 800)')
            human_delay(1, 2)
        
        # Extract job listings
        jobs = []
        page.wait_for_selector('.jobs-search-results__list-item', timeout=10000)
        
        job_cards = page.query_selector_all('.jobs-search-results__list-item')
        print(f"Found {len(job_cards)} job cards")
        
        for card in job_cards[:30]:
            try:
                # Click on job card to load details
                card.click()
                human_delay(1, 2)
                
                # Extract job details
                title_elem = card.query_selector('.job-card-list__title')
                company_elem = card.query_selector('.job-card-container__primary-description')
                link_elem = card.query_selector('a.job-card-list__title')
                
                # Check for Easy Apply button
                easy_apply_btn = page.query_selector('button.jobs-apply-button')
                
                if title_elem and link_elem and easy_apply_btn:
                    job_url = link_elem.get_attribute('href').split('?')[0]
                    jobs.append({
                        'title': title_elem.inner_text().strip(),
                        'company': company_elem.inner_text().strip() if company_elem else 'Unknown',
                        'url': job_url
                    })
                    
            except Exception as e:
                print(f"Error extracting job: {e}")
                continue
        
        return jobs
    except Exception as e:
        print(f"Search error: {e}")
        traceback.print_exc()
        return []


def get_gemini_answers(resume_text, job_title, company, job_description):
    """Use Gemini AI to generate application answers"""
    try:
        if not GEMINI_API_KEY:
            return {"error": "Gemini API key not configured"}
        
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""You are a job application assistant. Based on the resume below, extract and provide information for a LinkedIn Easy Apply job application.

RESUME:
{resume_text[:4000]}

JOB DETAILS:
- Position: {job_title}
- Company: {company}
- Description: {job_description[:500]}

TASK: Extract the following information from the resume and provide as JSON:
1. full_name: Candidate's full name
2. email: Email address
3. phone: Phone number (with country code if available)
4. city: Current city/location
5. years_experience: Total years of professional experience (number only)
6. linkedin_url: LinkedIn profile URL if mentioned
7. portfolio_url: Portfolio/website URL if mentioned
8. work_authorization: "Yes" if mentioned, otherwise "Yes" (assume authorized)
9. require_sponsorship: "No" (default to No unless explicitly stated)
10. willing_to_relocate: "Yes" (default)
11. cover_letter: Generate a brief 2-3 sentence cover letter for this specific role
12. salary_expectation: Extract if mentioned, otherwise "Negotiable"

IMPORTANT:
- Return ONLY valid JSON, no markdown or extra text
- Use exact field names as listed
- If information is not in resume, use reasonable defaults
- Keep cover letter concise and tailored

Example output:
{{
  "full_name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "city": "San Francisco",
  "years_experience": "5",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "portfolio_url": "https://johndoe.com",
  "work_authorization": "Yes",
  "require_sponsorship": "No",
  "willing_to_relocate": "Yes",
  "cover_letter": "I am excited to apply for {job_title} at {company}. With 5 years of experience, I believe I can contribute significantly to your team.",
  "salary_expectation": "Negotiable"
}}
"""
        
        response = model.generate_content(prompt)
        answer_text = response.text
        
        # Clean and parse JSON
        answer_text = answer_text.strip()
        
        # Remove markdown code blocks
        if '```json' in answer_text:
            answer_text = answer_text.split('```json')[1].split('```')[0]
        elif '```' in answer_text:
            answer_text = answer_text.split('```')[1].split('```')[0]
        
        answer_text = answer_text.strip()
        answers = json.loads(answer_text)
        
        print(f"✅ Generated answers: {list(answers.keys())}")
        return answers
        
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response: {answer_text[:500]}")
        return {"error": "Could not parse AI response"}
    except Exception as e:
        print(f"Gemini API error: {e}")
        traceback.print_exc()
        return {"error": str(e)}


def smart_fill_field(page, field, answer, field_type='input'):
    """Intelligently fill form field with appropriate method"""
    try:
        if not field or not answer:
            return False
        
        # Scroll field into view
        field.scroll_into_view_if_needed()
        human_delay(0.3, 0.5)
        
        if field_type == 'select' or field.evaluate('el => el.tagName').lower() == 'select':
            # Handle dropdowns
            try:
                # Try selecting by value
                field.select_option(value=str(answer))
            except:
                try:
                    # Try selecting by label
                    field.select_option(label=str(answer))
                except:
                    # Just select first option if nothing works
                    options = field.query_selector_all('option')
                    if options and len(options) > 1:
                        field.select_option(index=1)
        
        elif field_type == 'radio' or field.get_attribute('type') == 'radio':
            field.check()
        
        elif field_type == 'checkbox' or field.get_attribute('type') == 'checkbox':
            if str(answer).lower() in ['yes', 'true', '1']:
                field.check()
        
        else:
            # Regular input/textarea
            field.click()
            human_delay(0.2, 0.4)
            field.fill('')  # Clear first
            human_delay(0.1, 0.2)
            
            # Type with human-like speed
            text = str(answer)[:500]  # Limit length
            for char in text:
                field.type(char)
                time.sleep(random.uniform(0.02, 0.08))
        
        human_delay(0.3, 0.6)
        return True
        
    except Exception as e:
        print(f"Error filling field: {e}")
        return False


def apply_to_job(page, job_url, answers, resume_path):
    """Apply to job with intelligent form filling"""
    try:
        page.goto(job_url, wait_until='domcontentloaded')
        human_delay(2, 3)
        
        # Find and click Easy Apply button
        easy_apply_selectors = [
            'button.jobs-apply-button',
            'button[aria-label*="Easy Apply"]',
            'button:has-text("Easy Apply")',
            '.jobs-apply-button'
        ]
        
        easy_apply_btn = None
        for selector in easy_apply_selectors:
            try:
                easy_apply_btn = page.wait_for_selector(selector, timeout=5000)
                if easy_apply_btn:
                    break
            except:
                continue
        
        if not easy_apply_btn:
            return False, "Easy Apply button not found"
        
        easy_apply_btn.click()
        human_delay(3, 4)
        
        # Wait for modal to open
        try:
            page.wait_for_selector('.jobs-easy-apply-modal', timeout=5000)
        except:
            pass
        
        max_pages = 10
        current_page = 0
        
        while current_page < max_pages:
            current_page += 1
            print(f"📄 Processing page {current_page}")
            
            human_delay(2, 3)
            
            # Upload resume if file input exists
            try:
                file_inputs = page.query_selector_all('input[type="file"]')
                for file_input in file_inputs:
                    if file_input.is_visible():
                        print("📎 Uploading resume...")
                        file_input.set_input_files(resume_path)
                        human_delay(2, 3)
                        break
            except Exception as e:
                print(f"Resume upload: {e}")
            
            # Find all form fields on current page
            form_fields = page.query_selector_all('input, textarea, select')
            
            for field in form_fields:
                try:
                    if not field.is_visible():
                        continue
                    
                    # Get field attributes
                    field_id = field.get_attribute('id') or ''
                    field_name = field.get_attribute('name') or ''
                    field_label = field.get_attribute('aria-label') or ''
                    field_type = field.get_attribute('type') or 'text'
                    
                    # Skip file inputs
                    if field_type == 'file':
                        continue
                    
                    # Try to find matching answer
                    field_key = (field_id + field_name + field_label).lower()
                    
                    matched_answer = None
                    
                    # Smart matching
                    for key, value in answers.items():
                        key_lower = key.lower().replace('_', '')
                        
                        if any(term in field_key for term in [
                            key_lower, key.replace('_', ''), key.replace('_', '-')
                        ]):
                            matched_answer = value
                            break
                    
                    # Additional field type matching
                    if not matched_answer:
                        if 'email' in field_key:
                            matched_answer = answers.get('email')
                        elif 'phone' in field_key or 'mobile' in field_key:
                            matched_answer = answers.get('phone')
                        elif 'name' in field_key and 'first' not in field_key and 'last' not in field_key:
                            matched_answer = answers.get('full_name')
                        elif 'city' in field_key or 'location' in field_key:
                            matched_answer = answers.get('city')
                        elif 'year' in field_key and 'experience' in field_key:
                            matched_answer = answers.get('years_experience')
                        elif 'cover' in field_key or 'letter' in field_key or 'why' in field_key:
                            matched_answer = answers.get('cover_letter')
                        elif 'linkedin' in field_key:
                            matched_answer = answers.get('linkedin_url')
                        elif 'website' in field_key or 'portfolio' in field_key:
                            matched_answer = answers.get('portfolio_url')
                        elif 'sponsor' in field_key:
                            matched_answer = answers.get('require_sponsorship', 'No')
                        elif 'authorization' in field_key or 'authorized' in field_key:
                            matched_answer = answers.get('work_authorization', 'Yes')
                        elif 'relocate' in field_key:
                            matched_answer = answers.get('willing_to_relocate', 'Yes')
                        elif 'salary' in field_key:
                            matched_answer = answers.get('salary_expectation', 'Negotiable')
                    
                    if matched_answer:
                        print(f"✍️  Filling field: {field_key[:50]} = {str(matched_answer)[:50]}")
                        smart_fill_field(page, field, matched_answer, field_type)
                
                except Exception as e:
                    print(f"Field error: {e}")
                    continue
            
            human_delay(2, 3)
            
            # Try to click Next or Review button
            next_clicked = False
            next_button_selectors = [
                'button[aria-label*="Continue"]',
                'button[aria-label*="Next"]',
                'button[aria-label*="Review"]',
                'button:has-text("Next")',
                'button:has-text("Review")',
                'button.artdeco-button--primary:has-text("Next")'
            ]
            
            for selector in next_button_selectors:
                try:
                    next_btn = page.query_selector(selector)
                    if next_btn and next_btn.is_visible() and next_btn.is_enabled():
                        print(f"➡️  Clicking: {selector}")
                        next_btn.click()
                        next_clicked = True
                        human_delay(3, 4)
                        break
                except:
                    continue
            
            if not next_clicked:
                # Check for Submit button
                submit_selectors = [
                    'button[aria-label*="Submit application"]',
                    'button[aria-label*="Submit"]',
                    'button:has-text("Submit application")',
                    'button:has-text("Submit")'
                ]
                
                for selector in submit_selectors:
                    try:
                        submit_btn = page.query_selector(selector)
                        if submit_btn and submit_btn.is_visible() and submit_btn.is_enabled():
                            print("✅ Found Submit button!")
                            human_delay(1, 2)
                            submit_btn.click()
                            human_delay(4, 6)
                            
                            # Verify submission
                            if page.query_selector('[data-test-modal*="success"]') or \
                               'Your application was sent' in page.content():
                                return True, "Application submitted successfully"
                            
                            return True, "Application likely submitted"
                    except:
                        continue
                
                # No more buttons found
                break
        
        return False, "Could not complete application flow"
        
    except Exception as e:
        print(f"Apply error: {e}")
        traceback.print_exc()
        return False, str(e)


def log_to_google_sheets(sheet_id, job_data):
    """Log application data to Google Sheets (optional)"""
    try:
        if not sheet_id:
            return False
        
        # Define the scope
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Check if credentials file exists
        if not os.path.exists('credentials.json'):
            print("⚠️  Google Sheets credentials.json not found, skipping logging")
            return False
        
        # Authenticate
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        
        # Open the sheet
        sheet = client.open_by_key(sheet_id).sheet1
        
        # Prepare row data
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            job_data.get('title', ''),
            job_data.get('company', ''),
            job_data.get('url', ''),
            job_data.get('status', ''),
            job_data.get('message', '')
        ]
        
        # Append row
        sheet.append_row(row)
        print(f"✅ Logged to Google Sheets: {job_data['title']}")
        return True
        
    except Exception as e:
        print(f"Google Sheets error: {e}")
        return False


@app.route('/')
def index():
    """Serve the HTML interface"""
    return send_from_directory('.', 'index.html')


@app.route('/start-application', methods=['POST'])
def start_application():
    """Start the automated application process"""
    global application_status
    
    try:
        # Get form data
        linkedin_email = request.form.get('linkedinEmail')
        linkedin_password = request.form.get('linkedinPassword')
        resume_file = request.files.get('resume')
        google_sheet_id = request.form.get('googleSheetId', '').strip()  # Optional
        job_keywords = request.form.get('jobKeywords')
        location = request.form.get('location')
        job_types = json.loads(request.form.get('jobTypes', '[]'))
        work_mode = json.loads(request.form.get('workMode', '[]'))
        max_applications = int(request.form.get('maxApplications', 20))
        
        # Validate Gemini API key
        if not GEMINI_API_KEY:
            return jsonify({'success': False, 'error': 'Gemini API key not configured. Please add GEMINI_API_KEY to .env file'})
        
        # Save resume
        resume_path = os.path.join(UPLOAD_FOLDER, f'resume_{int(time.time())}.pdf')
        resume_file.save(resume_path)
        
        # Extract resume text
        resume_text = extract_resume_text(resume_path)
        
        if not resume_text:
            return jsonify({'success': False, 'error': 'Could not extract text from resume'})
        
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
                  google_sheet_id, job_keywords, location, job_types, work_mode, max_applications)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Automation started'})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def run_automation(email, password, resume_path, resume_text, sheet_id,
                   keywords, location, job_types, work_mode, max_apps):
    """Main automation logic"""
    global application_status
    
    browser = None
    try:
        with sync_playwright() as p:
            # Launch browser (non-headless for debugging)
            browser = p.chromium.launch(
                headless=False,
                args=['--start-maximized']
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            application_status['message'] = 'Logging into LinkedIn...'
            application_status['progress'] = 10
            
            # Login
            if not linkedin_login(page, email, password):
                application_status['status'] = 'error'
                application_status['message'] = 'Login failed. Please check credentials.'
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
            
            if not jobs:
                application_status['status'] = 'complete'
                application_status['message'] = '⚠️  No Easy Apply jobs found'
                return
            
            application_status['logs'].append({
                'time': datetime.now().strftime('%H:%M:%S'),
                'message': f'📋 Found {len(jobs)} Easy Apply jobs',
                'success': True
            })
            
            # Apply to jobs
            applied_count = 0
            
            for idx, job in enumerate(jobs[:max_apps]):
                try:
                    application_status['message'] = f'Processing: {job["title"]} at {job["company"]}'
                    application_status['progress'] = 20 + (idx / min(len(jobs), max_apps)) * 70
                    
                    # Get AI answers
                    answers = get_gemini_answers(
                        resume_text, job['title'], job['company'], ''
                    )
                    
                    if 'error' in answers:
                        application_status['logs'].append({
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'message': f'❌ AI Error for {job["title"]}: {answers["error"]}',
                            'success': False
                        })
                        continue
                    
                    # Apply to job
                    success, msg = apply_to_job(page, job['url'], answers, resume_path)
                    
                    # Log to Google Sheets if sheet_id provided
                    if sheet_id:
                        log_to_google_sheets(sheet_id, {
                            'title': job['title'],
                            'company': job['company'],
                            'url': job['url'],
                            'status': 'Success' if success else 'Failed',
                            'message': msg
                        })
                    
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
                    
                    # Random delay between applications
                    human_delay(8, 15)
                    
                except Exception as e:
                    application_status['logs'].append({
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'message': f'❌ Error: {job["title"]} - {str(e)}',
                        'success': False
                    })
                    traceback.print_exc()
            
            application_status['status'] = 'complete'
            application_status['message'] = f'✅ Completed! Applied to {applied_count}/{len(jobs[:max_apps])} jobs'
            application_status['progress'] = 100
            application_status['total_applied'] = applied_count
            
            human_delay(3, 5)
            browser.close()
            
    except Exception as e:
        application_status['status'] = 'error'
        application_status['message'] = f'Error: {str(e)}'
        application_status['logs'].append({
            'time': datetime.now().strftime('%H:%M:%S'),
            'message': f'❌ Fatal error: {str(e)}',
            'success': False
        })
        traceback.print_exc()
        
        if browser:
            try:
                browser.close()
            except:
                pass


@app.route('/status')
def get_status():
    """Get current application status"""
    return jsonify(application_status)


if __name__ == '__main__':
    print("=" * 70)
    print("🚀 LinkedIn Auto-Apply System with Gemini AI")
    print("=" * 70)
    print("📍 Open: http://localhost:5000")
    print("=" * 70)
    
    if GEMINI_API_KEY:
        print("\n✅ Gemini API: Configured")
    else:
        print("\n❌ Gemini API: NOT CONFIGURED")
        print("   Please create .env file with: GEMINI_API_KEY=your_key_here")
        print("   Get key at: https://makersuite.google.com/app/apikey")
    
    print("\n✨ Features:")
    print("   ✅ Server-side API configuration")
    print("   ✅ Optional Google Sheets logging")
    print("   ✅ Intelligent form field detection")
    print("   ✅ Human-like typing and delays")
    print("   ✅ Better Easy Apply navigation")
    print("   ✅ Smart resume parsing")
    
    print("\n📝 Optional Google Sheets Setup:")
    print("   1. Create service account in Google Cloud Console")
    print("   2. Download credentials.json to this folder")
    print("   3. Share your Google Sheet with service account email")
    print("   4. Enter Sheet ID in the form")
    
    print("\n" + "=" * 70)
    
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True, use_reloader=False)
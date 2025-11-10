"""
Enhanced LinkedIn Auto-Apply System with Gemini AI
- Server-side Gemini API configuration
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


def human_delay(min_sec=1, max_sec=2):
    """Add random human-like delay - optimized for speed"""
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
        # Build search URL - simpler approach, let LinkedIn filter on the page
        search_query = keywords.split(',')[0].strip().replace(' ', '%20')
        location_query = location.strip().replace(' ', '%20')
        
        # Start with basic search, Easy Apply filter, and sort by most recent
        # f_TPR=r86400 means posted in last 24 hours
        # f_TPR=r604800 means posted in last week
        base_url = f'https://www.linkedin.com/jobs/search/?keywords={search_query}&location={location_query}&f_AL=true&sortBy=DD&f_TPR=r604800'
        
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
        
        print(f"🔗 Navigating to job search: {base_url}")
        page.goto(base_url, wait_until='networkidle', timeout=30000)
        human_delay(5, 7)
        
        # Take screenshot for debugging
        try:
            page.screenshot(path='uploads/job_search_page.png')
            print("📸 Screenshot saved: uploads/job_search_page.png")
        except:
            pass
        
        # Scroll to load more jobs
        print("📜 Scrolling to load jobs...")
        for i in range(5):
            page.evaluate('window.scrollBy(0, 1000)')
            human_delay(1, 2)
        
        # Wait for page to settle
        human_delay(3, 5)
        
        # NEW APPROACH: Get all job links directly from the page
        print("🔍 Extracting job URLs...")
        jobs = []
        
        # Get all job listing links
        job_links = page.query_selector_all('a[href*="/jobs/view/"]')
        print(f"Found {len(job_links)} potential job links")
        
        seen_ids = set()
        
        for link in job_links[:50]:  # Process more to find Easy Apply ones
            try:
                href = link.get_attribute('href')
                if not href:
                    continue
                
                # Extract job ID from URL
                job_id = None
                if '/jobs/view/' in href:
                    job_id = href.split('/jobs/view/')[1].split('/')[0].split('?')[0]
                
                if not job_id or job_id in seen_ids:
                    continue
                
                seen_ids.add(job_id)
                
                # Build clean job URL
                job_url = f"https://www.linkedin.com/jobs/view/{job_id}"
                
                # Try to get title from the link
                title = link.inner_text().strip() if link.inner_text() else None
                
                if title and len(title) > 5:  # Valid title
                    jobs.append({
                        'title': title,
                        'company': 'Unknown',  # Will get this when we open the job
                        'url': job_url,
                        'id': job_id
                    })
                    print(f"  ✅ Added: {title} - {job_id}")
                
                if len(jobs) >= 30:
                    break
                    
            except Exception as e:
                continue
        
        print(f"\n✅ Total jobs collected: {len(jobs)}")
        return jobs
        
    except Exception as e:
        print(f"❌ Search error: {e}")
        traceback.print_exc()
        return []


def get_gemini_answers(resume_text, job_title, company, job_description):
    """Use Gemini AI to generate application answers"""
    try:
        if not GEMINI_API_KEY:
            return {"error": "Gemini API key not configured"}
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        
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
    """Intelligently fill form field - only if empty"""
    try:
        if not field or not answer:
            return False
        
        # Check if field already has a value - DON'T OVERWRITE
        try:
            current_value = field.input_value() if field_type not in ['select', 'radio', 'checkbox'] else None
            if current_value and len(str(current_value).strip()) > 0:
                print(f"   ⏭️  Field already has value: '{current_value[:30]}' - skipping")
                return True  # Return True since field is already filled
        except:
            pass  # If we can't get value, proceed with filling
        
        # Scroll field into view
        field.scroll_into_view_if_needed()
        human_delay(0.2, 0.4)
        
        if field_type == 'select' or field.evaluate('el => el.tagName').lower() == 'select':
            # Handle dropdowns
            try:
                field.select_option(value=str(answer))
            except:
                try:
                    field.select_option(label=str(answer))
                except:
                    options = field.query_selector_all('option')
                    if options and len(options) > 1:
                        field.select_option(index=1)
        
        elif field_type == 'radio' or field.get_attribute('type') == 'radio':
            # For radio buttons, check if the label/value matches the answer
            try:
                radio_value = field.get_attribute('value') or ''
                radio_label = field.get_attribute('aria-label') or ''
                radio_id = field.get_attribute('id') or ''
                
                # Check if this radio button matches the answer
                answer_lower = str(answer).lower()
                radio_text = (radio_value + radio_label + radio_id).lower()
                
                # Match if answer is in radio text or vice versa
                if (answer_lower in radio_text or 
                    radio_text in answer_lower or
                    answer_lower == radio_value.lower()):
                    if not field.is_checked():
                        print(f"      Selecting radio option: {radio_value or radio_label}")
                        field.check()
                        return True
            except Exception as e:
                # Fallback: just check it if types match
                if not field.is_checked():
                    field.check()
                    return True
        
        elif field_type == 'checkbox' or field.get_attribute('type') == 'checkbox':
            should_check = str(answer).lower() in ['yes', 'true', '1']
            if should_check and not field.is_checked():
                field.check()
        
        else:
            # Regular input/textarea - DON'T clear if already has value
            field.click()
            human_delay(0.1, 0.2)
            
            # Type with human-like speed but faster
            text = str(answer)[:500]
            for char in text:
                field.type(char)
                time.sleep(random.uniform(0.01, 0.03))  # Faster typing
        
        human_delay(0.2, 0.3)
        return True
        
    except Exception as e:
        print(f"   Error filling field: {e}")
        return False


def apply_to_job(page, job_url, answers, resume_path, resume_text, years_experience):
    """Apply to job with intelligent form filling"""
    try:
        print(f"\n{'='*60}")
        print(f"🔗 Opening job: {job_url}")
        print(f"{'='*60}")
        print(f"💼 Using {years_experience} years of experience for this application")
        
        page.goto(job_url, wait_until='networkidle', timeout=30000)
        human_delay(3, 4)
        
        # Take screenshot for debugging
        try:
            page.screenshot(path='uploads/job_page.png')
            print("📸 Screenshot saved: uploads/job_page.png")
        except:
            pass
        
        # Scroll down to make sure everything loads
        print("📜 Scrolling page...")
        page.evaluate('window.scrollTo(0, 400)')
        human_delay(2, 3)
        
        # Look for Easy Apply button with extensive search
        print("🔍 Searching for Easy Apply button...")
        
        easy_apply_selectors = [
            'button.jobs-apply-button',
            'button[aria-label*="Easy Apply"]',
            'button:text("Easy Apply")',
            'button:has-text("Easy Apply")',
            '.jobs-apply-button',
            'button[data-control-name*="jobdetails_topcard_inapply"]',
            '.jobs-apply-button--top-card',
            'button.artdeco-button:has-text("Easy Apply")'
        ]
        
        easy_apply_btn = None
        
        for idx, selector in enumerate(easy_apply_selectors):
            try:
                print(f"  Trying selector {idx+1}/{len(easy_apply_selectors)}: {selector}")
                elements = page.query_selector_all(selector)
                
                if elements:
                    print(f"    Found {len(elements)} element(s)")
                    for elem in elements:
                        try:
                            if elem.is_visible():
                                text = elem.inner_text().strip() if elem.inner_text() else ''
                                print(f"    ✅ Visible element found: '{text}'")
                                easy_apply_btn = elem
                                break
                        except:
                            continue
                
                if easy_apply_btn:
                    break
                    
            except Exception as e:
                print(f"    Error: {e}")
                continue
        
        if not easy_apply_btn:
            print("❌ Easy Apply button not found - checking if it's a regular Apply job...")
            
            # Check if this is a non-Easy Apply job
            regular_apply_btns = page.query_selector_all('button:has-text("Apply")')
            if regular_apply_btns:
                print("⚠️  This is a regular Apply job (not Easy Apply) - skipping")
                return False, "Not an Easy Apply job"
            
            # Print page content for debugging
            print("\n📄 Page buttons found:")
            all_buttons = page.query_selector_all('button')
            for btn in all_buttons[:10]:  # Show first 10 buttons
                try:
                    if btn.is_visible():
                        btn_text = btn.inner_text().strip()
                        if btn_text:
                            print(f"  - {btn_text}")
                except:
                    continue
            
            return False, "Easy Apply button not found on page"
        
        # Found the button - now click it
        print(f"\n✅ Easy Apply button found!")
        try:
            # Scroll button into view
            easy_apply_btn.scroll_into_view_if_needed()
            human_delay(1, 2)
            
            # Highlight the button (for visual confirmation)
            try:
                page.evaluate("(element) => element.style.border = '3px solid red'", easy_apply_btn)
                human_delay(0.5, 1)
            except:
                pass
            
            # Click using multiple methods
            print("🖱️  Attempting to click Easy Apply button...")
            
            # Method 1: Regular click
            try:
                easy_apply_btn.click()
                print("  ✅ Click method 1: Regular click successful")
            except Exception as e:
                print(f"  ❌ Click method 1 failed: {e}")
                
                # Method 2: Force click
                try:
                    easy_apply_btn.click(force=True)
                    print("  ✅ Click method 2: Force click successful")
                except Exception as e2:
                    print(f"  ❌ Click method 2 failed: {e2}")
                    
                    # Method 3: JavaScript click
                    try:
                        page.evaluate("(element) => element.click()", easy_apply_btn)
                        print("  ✅ Click method 3: JavaScript click successful")
                    except Exception as e3:
                        print(f"  ❌ Click method 3 failed: {e3}")
                        return False, "Failed to click Easy Apply button"
            
            print("✅ Easy Apply button clicked!")
            human_delay(3, 4)
            
        except Exception as e:
            print(f"❌ Error clicking Easy Apply: {e}")
            return False, f"Failed to click Easy Apply: {str(e)}"
        
        # Wait for modal to open - try multiple selectors
        print("\n⏳ Waiting for application modal to open...")
        
        modal_selectors = [
            '.jobs-easy-apply-modal',
            '[role="dialog"]',
            '.artdeco-modal',
            '.jobs-easy-apply-content',
            'div[data-test-modal]'
        ]
        
        modal_found = False
        for selector in modal_selectors:
            try:
                print(f"  Checking for: {selector}")
                page.wait_for_selector(selector, timeout=8000)
                print(f"  ✅ Modal found: {selector}")
                modal_found = True
                break
            except:
                print(f"  ❌ Not found: {selector}")
                continue
        
        if not modal_found:
            print("⚠️  Modal selectors not found, checking page state...")
            # Take screenshot to see what happened
            try:
                page.screenshot(path='uploads/after_click.png')
                print("📸 Screenshot saved: uploads/after_click.png")
            except:
                pass
        
        max_pages = 10
        current_page = 0
        
        while current_page < max_pages:
            current_page += 1
            print(f"\n📄 Processing application page {current_page}")
            
            human_delay(3, 4)
            
            # Upload resume if file input exists
            print("📎 Checking for resume upload...")
            try:
                # DON'T click upload buttons - they open file dialog
                # Directly set file on hidden input elements
                
                file_inputs = page.query_selector_all('input[type="file"]')
                print(f"   Found {len(file_inputs)} file input(s)")
                
                upload_success = False
                for idx, file_input in enumerate(file_inputs):
                    try:
                        print(f"   Uploading to input {idx + 1}...")
                        
                        # Directly set the file without clicking anything
                        file_input.set_input_files(resume_path)
                        human_delay(1, 2)
                        
                        # Verify upload by checking for success indicators
                        time.sleep(1)
                        
                        # Look for filename or success message in page
                        resume_filename = os.path.basename(resume_path)
                        
                        # Check multiple indicators
                        success_indicators = [
                            f'text={resume_filename}',
                            'text=Resume',
                            'text=Uploaded',
                            '.artdeco-inline-feedback--success',
                            '[data-test-file-upload-success]'
                        ]
                        
                        for indicator in success_indicators:
                            try:
                                if page.query_selector(indicator):
                                    print(f"   ✅ Resume uploaded! Found indicator: {indicator}")
                                    upload_success = True
                                    break
                            except:
                                continue
                        
                        if upload_success:
                            break
                            
                        # If no indicator found but no error, consider it success
                        print(f"   ✅ Resume file set on input {idx + 1}")
                        upload_success = True
                        break
                        
                    except Exception as e:
                        print(f"   ❌ Upload failed on input {idx + 1}: {e}")
                        continue
                
                if not upload_success and len(file_inputs) > 0:
                    print("   ⚠️  Resume upload uncertain, continuing...")
                elif len(file_inputs) == 0:
                    print("   ℹ️  No file upload field on this page")
                    
            except Exception as e:
                print(f"Resume upload error: {e}")
            
            # Find all form fields on current page
            form_fields = page.query_selector_all('input:not([type="hidden"]), textarea, select')
            print(f"Found {len(form_fields)} form fields")
            
            fields_filled = 0
            processed_radio_groups = set()  # Track processed radio button groups
            
            for field in form_fields:
                try:
                    if not field.is_visible():
                        continue
                    
                    # Get field attributes
                    field_id = field.get_attribute('id') or ''
                    field_name = field.get_attribute('name') or ''
                    field_label = field.get_attribute('aria-label') or ''
                    field_placeholder = field.get_attribute('placeholder') or ''
                    field_type = field.get_attribute('type') or 'text'
                    
                    # Skip file inputs
                    if field_type == 'file':
                        continue
                    
                    # For radio buttons, handle as group (skip if already processed)
                    if field_type == 'radio':
                        radio_name = field_name
                        if radio_name in processed_radio_groups:
                            continue  # Already processed this radio group
                        processed_radio_groups.add(radio_name)
                    
                    # Check if field already has value - skip if filled
                    try:
                        if field_type not in ['radio', 'checkbox', 'select']:
                            current_value = field.input_value()
                            if current_value and len(str(current_value).strip()) > 0:
                                continue  # Skip already filled fields
                    except:
                        pass
                    
                    # Combine all field identifiers for matching
                    field_key = (field_id + field_name + field_label + field_placeholder).lower()
                    
                    matched_answer = None
                    matched_key = None
                    
                    # Smart matching with priority
                    matching_patterns = {
                        'email': ['email', 'e-mail', 'emailaddress'],
                        'phone': ['phone', 'mobile', 'telephone', 'contact'],
                        'full_name': ['fullname', 'name', 'your name'],
                        'city': ['city', 'location', 'where'],
                        'years_experience': ['years', 'experience', 'yoe'],
                        'cover_letter': ['cover', 'letter', 'why', 'interested', 'motivation'],
                        'linkedin_url': ['linkedin', 'profile'],
                        'portfolio_url': ['website', 'portfolio', 'github'],
                        'work_authorization': ['authorization', 'authorized', 'legal'],
                        'require_sponsorship': ['sponsor', 'visa'],
                        'willing_to_relocate': ['relocate', 'relocation', 'move'],
                        'salary_expectation': ['salary', 'compensation', 'expected']
                    }
                    
                    # Try pattern matching first
                    for answer_key, patterns in matching_patterns.items():
                        if any(pattern in field_key for pattern in patterns):
                            if answer_key in answers:
                                matched_answer = answers[answer_key]
                                matched_key = answer_key
                                break
                    
                    # If no match found, use AI to answer the question
                    if not matched_answer:
                        question_text = field_label or field_placeholder or field_name or field_id
                        
                        if question_text and len(question_text) > 2:
                            print(f"❓ Unknown field: '{question_text[:50]}'")
                            print(f"   🤖 Asking AI for answer...")
                            
                            # Use AI to answer with experience context
                            ai_answer = answer_unknown_question_with_ai(
                                question_text, 
                                resume_text, 
                                field_type,
                                years_experience
                            )
                            
                            if ai_answer:
                                matched_answer = ai_answer
                                matched_key = 'ai_generated'
                    
                    # For radio buttons, find and click the matching option
                    if matched_answer and field_type == 'radio':
                        print(f"🔘 Radio group: {field_name[:40]}")
                        print(f"   Looking for option matching: '{matched_answer}'")
                        
                        # Get all radio buttons in this group
                        radio_group = page.query_selector_all(f'input[type="radio"][name="{field_name}"]')
                        
                        matched_radio = False
                        for radio in radio_group:
                            try:
                                if not radio.is_visible():
                                    continue
                                
                                radio_value = radio.get_attribute('value') or ''
                                radio_label_for = radio.get_attribute('id') or ''
                                
                                # Try to get associated label text
                                radio_label_text = ''
                                if radio_label_for:
                                    label_elem = page.query_selector(f'label[for="{radio_label_for}"]')
                                    if label_elem:
                                        radio_label_text = label_elem.inner_text().strip()
                                
                                # Check if this radio matches the answer
                                answer_lower = str(matched_answer).lower()
                                radio_text = (radio_value + radio_label_text).lower()
                                
                                if (answer_lower in radio_text or 
                                    radio_text in answer_lower or
                                    answer_lower == radio_value.lower()):
                                    
                                    print(f"   ✅ Selecting: '{radio_label_text or radio_value}'")
                                    radio.check()
                                    matched_radio = True
                                    fields_filled += 1
                                    break
                                    
                            except Exception as e:
                                continue
                        
                        if not matched_radio:
                            print(f"   ⚠️  No matching radio option found")
                        
                        continue  # Move to next field
                    
                    if matched_answer:
                        if matched_key == 'ai_generated':
                            print(f"✍️  Filling (AI): '{str(matched_answer)[:30]}'")
                        else:
                            print(f"✍️  Filling '{matched_key}': '{str(matched_answer)[:30]}'")
                        
                        if smart_fill_field(page, field, matched_answer, field_type):
                            fields_filled += 1
                    else:
                        print(f"⏭️  Skipping field: {field_key[:40]}")
                
                except Exception as e:
                    print(f"Field error: {e}")
                    continue
            
            print(f"✅ Filled {fields_filled} fields on this page")
            human_delay(1, 2)
            
            # Try to click Next, Review, or Submit button
            next_clicked = False
            
            # First, try to find and click Next/Continue/Review buttons
            next_button_selectors = [
                'button[aria-label*="Continue to next step"]',
                'button[aria-label*="Continue"]',
                'button[aria-label*="Next"]',
                'button[aria-label*="Review"]',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button:has-text("Review")',
                'footer button.artdeco-button--primary',
                '.jobs-easy-apply-modal footer button[type="button"]'
            ]
            
            print("🔍 Looking for Next/Continue button...")
            for selector in next_button_selectors:
                try:
                    next_btn = page.query_selector(selector)
                    if next_btn and next_btn.is_visible() and next_btn.is_enabled():
                        btn_text = next_btn.inner_text().strip()
                        print(f"➡️  Found button: '{btn_text}' - clicking...")
                        next_btn.scroll_into_view_if_needed()
                        human_delay(0.5, 1)
                        next_btn.click()
                        next_clicked = True
                        human_delay(2, 3)
                        print(f"✅ Clicked '{btn_text}' button")
                        break
                except Exception as e:
                    print(f"   Error with selector {selector}: {e}")
                    continue
            
            if not next_clicked:
                print("🔍 No Next button found, looking for Submit button...")
                
                # Check for Submit button
                submit_selectors = [
                    'button[aria-label*="Submit application"]',
                    'button[aria-label*="Submit"]',
                    'button:has-text("Submit application")',
                    'button:has-text("Submit")',
                    'footer button.artdeco-button--primary:has-text("Submit")',
                    '.jobs-easy-apply-modal footer button[type="submit"]'
                ]
                
                submit_found = False
                for selector in submit_selectors:
                    try:
                        submit_btn = page.query_selector(selector)
                        if submit_btn and submit_btn.is_visible() and submit_btn.is_enabled():
                            btn_text = submit_btn.inner_text().strip()
                            print(f"✅ Found Submit button: '{btn_text}'")
                            submit_btn.scroll_into_view_if_needed()
                            human_delay(1, 2)
                            submit_btn.click()
                            submit_found = True
                            human_delay(3, 4)
                            print("✅ Clicked Submit button!")
                            
                            # Wait a bit and check for success indicators
                            human_delay(2, 3)
                            
                            # Check for success messages
                            success_indicators = [
                                '[data-test-modal*="success"]',
                                '.artdeco-inline-feedback--success',
                                'text=Your application was sent',
                                'text=Application submitted',
                                'text=successfully'
                            ]
                            
                            for indicator in success_indicators:
                                try:
                                    if page.query_selector(indicator):
                                        print("🎉 Success indicator found!")
                                        return True, "Application submitted successfully"
                                except:
                                    continue
                            
                            # If no explicit success message, check if modal closed
                            try:
                                modal_still_open = page.query_selector('.jobs-easy-apply-modal')
                                if not modal_still_open or not modal_still_open.is_visible():
                                    print("✅ Modal closed - likely submitted")
                                    return True, "Application submitted (modal closed)"
                            except:
                                pass
                            
                            return True, "Application submitted"
                    except Exception as e:
                        print(f"   Error with submit selector {selector}: {e}")
                        continue
                
                if submit_found:
                    break
                
                # No buttons found - end of flow
                print("⚠️  No Next or Submit button found - end of application flow")
                break
        
        # If we got here, check final status
        print("\n⚠️  Reached maximum pages or end of flow")
        
        # Final check for success
        try:
            if 'application' in page.url.lower() or 'success' in page.url.lower():
                return True, "Application likely submitted (URL changed)"
        except:
            pass
        
        return False, "Could not complete application flow - no submit button found"
        
    except Exception as e:
        print(f"❌ Apply error: {e}")
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
    try:
        # First try templates folder (Flask default)
        if os.path.exists('templates/index.html'):
            return render_template('index.html')
        # Then try current directory
        elif os.path.exists('index.html'):
            with open('index.html', 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return """
            <h1>Error: index.html not found</h1>
            <p>Please create index.html in one of these locations:</p>
            <ul>
                <li>templates/index.html (recommended)</li>
                <li>index.html (same folder as app.py)</li>
            </ul>
            <p>Current directory: {}</p>
            <p>Files in directory: {}</p>
            """.format(os.getcwd(), ', '.join(os.listdir('.')))
    except Exception as e:
        return f"Error loading index.html: {str(e)}"


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
        years_experience = request.form.get('yearsExperience', '2')  # Get experience from form
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
                  google_sheet_id, job_keywords, location, years_experience,
                  job_types, work_mode, max_applications)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Automation started'})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def run_automation(email, password, resume_path, resume_text, sheet_id,
                   keywords, location, years_experience, job_types, work_mode, max_apps):
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
                    success, msg = apply_to_job(page, job['url'], answers, resume_path, resume_text, years_experience)
                    
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
                    human_delay(5, 8)
                    
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
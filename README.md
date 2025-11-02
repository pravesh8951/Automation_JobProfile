# 🤖 LinkedIn Auto-Apply System with Gemini AI

Automate your LinkedIn job applications using AI-powered form filling with human-like behavior.

## ✨ Features

- 🧠 **Gemini AI Integration** - Server-side AI configuration (no user API key needed)
- 📝 **Smart Resume Parsing** - Automatically extracts information from PDF resumes
- 🎯 **Intelligent Form Filling** - Detects and fills all types of form fields
- 👤 **Human-like Behavior** - Random delays and typing speed to avoid detection
- 📊 **Optional Google Sheets Logging** - Track all applications in a spreadsheet
- 🎨 **Beautiful Web Interface** - Easy-to-use form with real-time progress tracking
- 🔒 **Secure** - Credentials only used during session, never stored

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Google Chrome or Chromium browser

## 🚀 Installation

### 1. Clone or Download the Project

```bash
# Create project directory
mkdir linkedin-auto-apply
cd linkedin-auto-apply
```

### 2. Install Python Dependencies

```bash
pip install flask flask-cors playwright PyPDF2 google-generativeai gspread oauth2client python-dotenv
```

### 3. Install Playwright Browser

```bash
playwright install chromium
```

### 4. Get Gemini API Key (FREE)

1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key

### 5. Configure Environment Variables

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` and add your Gemini API key:
```bash
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

## 📁 Project Structure

```
linkedin-auto-apply/
├── app.py              # Main Flask application
├── index.html          # Web interface
├── .env                # Configuration file (create this)
├── .env.example        # Example configuration
├── uploads/            # Resume uploads (auto-created)
└── credentials.json    # Google Sheets credentials (optional)
```

## 🎯 Usage

### 1. Start the Server

```bash
python app.py
```

You should see:
```
🚀 LinkedIn Auto-Apply System with Gemini AI
================================================================
📍 Open: http://localhost:5000
================================================================
✅ Gemini API: Configured
```

### 2. Open in Browser

Navigate to: http://localhost:5000

### 3. Fill in the Form

**Required Fields:**
- LinkedIn Email
- LinkedIn Password
- Resume (PDF file)
- Job Keywords (e.g., "Software Engineer")
- Location (e.g., "Remote")
- Job Types (select at least one)
- Work Mode (select at least one)

**Optional Field:**
- Google Sheet ID (for logging applications)

### 4. Start Auto-Applying

Click "🚀 Start Auto-Applying to Jobs" and watch the magic happen!

The system will:
1. Login to LinkedIn
2. Search for Easy Apply jobs
3. Extract information from your resume using AI
4. Fill application forms intelligently
5. Submit applications with human-like behavior

## 📊 Optional: Google Sheets Logging

To log all applications to a Google Sheet:

### 1. Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Sheets API
4. Create Service Account
5. Download credentials JSON file

### 2. Setup Credentials

1. Save the downloaded file as `credentials.json` in project root
2. Open the JSON file and copy the service account email
3. Create a new Google Sheet
4. Share the sheet with the service account email (give Editor access)
5. Copy the Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
   ```

### 3. Enter Sheet ID in Form

When using the application, paste your Sheet ID in the "Google Sheet ID" field.

## ⚙️ Configuration Options

### Maximum Applications
- Recommended: 10-20 per session
- Helps avoid LinkedIn rate limiting

### Job Types
- Full-time
- Part-time
- Contract
- Internship

### Work Modes
- Remote
- On-site
- Hybrid

## 🔧 Troubleshooting

### "Gemini API key not configured"
- Make sure `.env` file exists
- Check that `GEMINI_API_KEY` is set correctly
- Restart the server after changing `.env`

### "Login failed"
- Verify LinkedIn credentials
- Complete security checkpoint manually if prompted
- Try again after a few minutes

### "No Easy Apply jobs found"
- Adjust job keywords
- Try different locations
- Expand job type selections

### Resume not parsing correctly
- Ensure resume is in PDF format
- Check that text is selectable (not an image)
- Try a different resume format

### Browser doesn't open
- Make sure Chromium is installed: `playwright install chromium`
- Check if port 5000 is available

## 🛡️ Security & Privacy

- ✅ **Credentials never stored** - Only used during active session
- ✅ **Resume processed locally** - Not uploaded to external servers
- ✅ **API calls server-side** - Your Gemini key stays on your server
- ✅ **Open source** - Review all code yourself

## ⚡ Performance Tips

1. **Start Small**: Begin with 5-10 applications to test
2. **Random Delays**: Built-in human-like delays prevent detection
3. **Session Management**: Run during business hours for best results
4. **Resume Quality**: Better formatted resumes = better results

## 🤝 Contributing

Feel free to submit issues, fork the repository, and create pull requests!

## 📝 License

This project is for educational purposes. Use responsibly and in accordance with LinkedIn's Terms of Service.

## ⚠️ Disclaimer

This tool is designed to assist with job applications. Users are responsible for:
- Ensuring compliance with LinkedIn's Terms of Service
- Reviewing applications before submission
- Maintaining accurate resume information
- Using the tool ethically and responsibly

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section
2. Review console logs
3. Verify all dependencies are installed
4. Create an issue with detailed error messages

## 🎉 Success Tips

1. **Keep Resume Updated**: Ensure your PDF resume has current information
2. **Customize Keywords**: Use specific job titles for better matches
3. **Review Applications**: Periodically check submitted applications
4. **Monitor Progress**: Watch the real-time logs
5. **Be Patient**: Quality over quantity!

---

Made with ❤️ for job seekers

**Happy Job Hunting! 🚀**

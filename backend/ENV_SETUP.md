# Environment Variables Setup

## Required Environment Variables

The backend requires the following environment variables to be set. **NEVER commit API keys to version control!**

### 1. GEMINI_API_KEY (Required)
- **Purpose**: Primary Google Gemini AI API key
- **Get it from**: https://makersuite.google.com/app/apikey
- **Set it**: `export GEMINI_API_KEY='your-api-key'` (Linux/Mac) or `set GEMINI_API_KEY=your-api-key` (Windows)

### 2. GEMINI_API_KEY_BACKUP (Optional)
- **Purpose**: Backup Gemini API key for automatic failover
- **Set it**: `export GEMINI_API_KEY_BACKUP='your-backup-api-key'`

### 3. SCRAPERAPI_KEY (Required)
- **Purpose**: ScraperAPI key for web scraping
- **Get it from**: https://www.scraperapi.com/
- **Set it**: `export SCRAPERAPI_KEY='your-api-key'`

## Setup Instructions

### Option 1: Set environment variables in your terminal
```bash
# Linux/Mac
export GEMINI_API_KEY='your-gemini-api-key'
export SCRAPERAPI_KEY='your-scraperapi-key'

# Windows (PowerShell)
$env:GEMINI_API_KEY='your-gemini-api-key'
$env:SCRAPERAPI_KEY='your-scraperapi-key'

# Windows (Command Prompt)
set GEMINI_API_KEY=your-gemini-api-key
set SCRAPERAPI_KEY=your-scraperapi-key
```

### Option 2: Create a .env file (recommended)
1. Create a `.env` file in the `backend/` directory
2. Add your keys:
   ```
   GEMINI_API_KEY=your-gemini-api-key
   SCRAPERAPI_KEY=your-scraperapi-key
   ```
3. Install python-dotenv: `pip install python-dotenv`
4. Load in your code (if using uvicorn, it may auto-load .env files)

## Security Notes

⚠️ **IMPORTANT**: 
- The old hardcoded API keys have been removed for security
- Both keys mentioned in the codebase are compromised and should be revoked immediately
- Always use environment variables or secure secret management
- Never commit `.env` files or API keys to git




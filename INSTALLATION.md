# 📦 Installation Guide - SimilarLinks

Complete step-by-step instructions to set up and run SimilarLinks on your machine.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Frontend Setup](#frontend-setup)
3. [Backend Setup](#backend-setup)
4. [Environment Configuration](#environment-configuration)
5. [Running the Application](#running-the-application)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

| Software | Version | Download Link |
|----------|---------|---------------|
| **Node.js** | 18.0+ | [nodejs.org](https://nodejs.org/) |
| **Python** | 3.11+ | [python.org](https://www.python.org/) |
| **Git** | Latest | [git-scm.com](https://git-scm.com/) |
| **Expo Go** | Latest | [Play Store](https://play.google.com/store/apps/details?id=host.exp.exponent) / [App Store](https://apps.apple.com/app/expo-go/id982107779) |

### Required API Keys

| Service | Purpose | Free Tier | Get Key |
|---------|---------|-----------|---------|
| **Google Gemini AI** | Product analysis, recommendations | ✅ Yes | [ai.google.dev](https://ai.google.dev/) |
| **ScraperAPI** | Web scraping (optional) | 5,000 calls/month | [scraperapi.com](https://www.scraperapi.com/) |

---

## Frontend Setup

### 1. Clone Repository

```bash
git clone https://github.com/mailidpwd/Ecommerce.git
cd Ecommerce
```

### 2. Install Node Dependencies

```bash
npm install
```

**Or with Yarn:**
```bash
yarn install
```

### 3. Create Frontend Environment File

Create a file named `.env` in the **project root** directory:

**Windows (PowerShell):**
```powershell
New-Item -Path .env -ItemType File
```

**Mac/Linux:**
```bash
touch .env
```

**Add this content:**
```env
EXPO_PUBLIC_GEMINI_API_KEY=your-gemini-api-key-here
```

**To get Gemini API Key:**
1. Visit [Google AI Studio](https://ai.google.dev/)
2. Click "Get API Key"
3. Create new key or use existing
4. Copy the key
5. Paste in `.env` file

---

## Backend Setup

### 1. Navigate to Backend Directory

```bash
cd backend
```

### 2. Create Python Virtual Environment

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Backend Environment File

Create a file named `.env` in the **backend** directory:

**Windows (PowerShell):**
```powershell
New-Item -Path .env -ItemType File
```

**Mac/Linux:**
```bash
touch .env
```

**Add this content:**
```env
GEMINI_API_KEY=your-gemini-api-key-here
SCRAPERAPI_KEY=your-scraperapi-key-here
```

**Note:** ScraperAPI is optional. Without it:
- ✅ Product recommendations still work
- ✅ AI analysis works
- ⚠️ Limited product images
- ⚠️ Prices may show as ₹0

---

## Environment Configuration

### Frontend `.env` File Structure

```env
# Google Gemini API Key (Required)
EXPO_PUBLIC_GEMINI_API_KEY=your-actual-gemini-api-key
```

### Backend `.env` File Structure

```env
# Google Gemini API Key (Required)
GEMINI_API_KEY=your-actual-gemini-api-key

# ScraperAPI Key (Optional - for images and prices)
SCRAPERAPI_KEY=your-actual-scraperapi-key
```

### ⚠️ Security Notes

- ✅ `.env` files are in `.gitignore`
- ✅ Never commit API keys to GitHub
- ✅ Use environment variables only
- ✅ Keys should be kept secret

---

## Running the Application

### Option 1: Local Development (Recommended)

#### Step 1: Start Backend Server

**In backend directory:**
```bash
cd backend
python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### Step 2: Start Frontend (New Terminal)

**In project root:**
```bash
npx expo start --lan
```

**Expected output:**
- QR code appears
- Metro bundler starts
- "Metro waiting on exp://..."

#### Step 3: Open on Phone

1. Open **Expo Go** app
2. Scan the QR code
3. App loads on your phone
4. Start using!

---

### Option 2: Using Tunnel Mode (Different Networks)

If phone and computer are on different WiFi networks:

```bash
npx expo start --tunnel
```

**Note:** Tunnel mode is slower but works across networks.

---

### Option 3: Test on Web (Quick Test)

```bash
npx expo start
```

Press `w` to open in web browser.

---

## 🧪 Testing the Setup

### 1. Test Backend Health

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{"status":"healthy","timestamp":"2025-12-03T..."}
```

### 2. Test in App

1. **Paste Amazon share text:**
   ```
   Limited-time deal: ASUS Vivobook 15, Intel Core i5 13th Gen, 16GB RAM... https://amzn.in/d/xyz
   ```

2. **Expected behavior:**
   - ⚡ Smart badge appears
   - ✅ "Details captured" shows
   - 🦖 Dino game appears after 3s
   - Results in 8-15 seconds
   - 5-6 quality products shown

---

## 🔧 Troubleshooting

### "Module not found" Errors

**Solution:**
```bash
# Frontend
rm -rf node_modules
npm install

# Backend
cd backend
pip install --upgrade pip
pip install -r requirements.txt
```

### "API Key not found" Error

**Check:**
1. `.env` file exists in correct location
2. API key format is correct (no quotes, no spaces)
3. Restart Expo with `--clear` flag
4. Restart backend server

**Example fix:**
```bash
# Restart Expo
npx expo start --clear --lan
```

### "Network request failed" Error

**Possible causes:**
1. Backend not running
2. Wrong IP address
3. Phone and computer on different WiFi

**Solution:**
```bash
# Windows - Get your IP
ipconfig

# Mac/Linux - Get your IP
ifconfig

# Update src/services/api.ts with your IP:
const BACKEND_URL = 'http://YOUR_IP_HERE:8000';
```

### "Backend timeout" Error

**If backend takes > 60 seconds:**
- This is normal first time (Gemini warming up)
- Subsequent requests are faster
- Consider getting ScraperAPI key for better performance

### Expo Won't Start

**Solution:**
```bash
# Clear cache
npx expo start --clear

# Reset Metro
rm -rf .expo
npx expo start
```

---

## 📁 Project Structure

```
SimilarLinks/
├── src/                          # Frontend source code
│   ├── components/              # Reusable UI components
│   ├── screens/                 # App screens
│   ├── services/                # API and business logic
│   └── utils/                   # Helper functions
├── backend/                      # Python FastAPI backend
│   ├── main.py                  # Main API server
│   ├── gemini_vision.py         # Image recognition
│   ├── scraper_api.py           # Web scraping
│   └── requirements.txt         # Python dependencies
├── assets/                       # App icons and images
├── .env                          # Frontend API keys (DO NOT COMMIT)
├── backend/.env                  # Backend API keys (DO NOT COMMIT)
├── package.json                  # Node dependencies
└── README.md                     # This file
```

---

## 🌐 Network Configuration

### For Local Network (Same WiFi)

**Both phone and computer must be on the same WiFi network.**

1. Find your computer's IP address:
   - **Windows:** `ipconfig`
   - **Mac/Linux:** `ifconfig`

2. Update `src/services/api.ts`:
   ```typescript
   const BACKEND_URL = 'http://YOUR_IP:8000';
   ```

3. Start with LAN mode:
   ```bash
   npx expo start --lan
   ```

### For Different Networks (Tunnel Mode)

Use tunnel mode if phone and computer are on different networks:

```bash
npx expo start --tunnel
```

**Note:** Tunnel mode is slower but more flexible.

---

## 🎯 Getting API Keys

### Google Gemini API (Required)

1. Visit [Google AI Studio](https://ai.google.dev/)
2. Sign in with Google account
3. Click "Get API Key" 
4. Create new key or use existing
5. Copy the key (starts with `AIzaSy...`)
6. Add to both `.env` files

**Free tier includes:**
- 60 requests per minute
- Unlimited daily requests
- Full access to Gemini models

### ScraperAPI (Optional but Recommended)

1. Visit [ScraperAPI](https://www.scraperapi.com/)
2. Sign up for free account
3. Get API key from dashboard
4. Add to `backend/.env`

**Free tier includes:**
- 5,000 API calls per month
- Essential for:
  - Product images
  - Live prices
  - Product ratings
  - Full specifications

---

## 📱 Mobile Development

### Android

**Using Expo Go:**
1. Install Expo Go from Play Store
2. Scan QR code from terminal
3. App loads automatically

**Using Android Emulator:**
1. Install Android Studio
2. Set up Android Virtual Device (AVD)
3. Run `npx expo start`
4. Press `a` to open in emulator

### iOS

**Using Expo Go:**
1. Install Expo Go from App Store
2. Scan QR code with Camera app
3. Opens in Expo Go

**Using iOS Simulator (Mac only):**
1. Install Xcode
2. Run `npx expo start`
3. Press `i` to open in simulator

---

## 🔄 Development Workflow

### Daily Development

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # Mac/Linux
# OR
venv\Scripts\activate     # Windows
python main.py
```

**Terminal 2 - Frontend:**
```bash
npx expo start --lan
```

### Making Changes

**Frontend changes:**
- Edit files in `src/`
- Save file
- App reloads automatically (Fast Refresh)

**Backend changes:**
- Edit files in `backend/`
- Save file
- Restart backend server (Ctrl+C, then run again)

---

## 🚀 Deployment

### Backend Deployment (Optional)

The backend can be deployed to:
- Google Cloud Run
- AWS Lambda
- Heroku
- DigitalOcean

See deployment guides for each platform.

### Frontend Deployment

Build standalone apps:

```bash
# Android APK
eas build --platform android

# iOS IPA  
eas build --platform ios
```

Requires Expo EAS account (free tier available).

---

## 💡 Tips & Best Practices

### Performance

- Use **LAN mode** for fastest development
- Enable **Fast Refresh** in Expo settings
- Keep backend running to avoid restart delays
- Use **ScraperAPI** for complete data

### Development

- Check `.env` files are not committed
- Test on both Android and iOS
- Use TypeScript for type safety
- Follow existing code structure

### Debugging

- Check backend logs for errors
- Use React Native Debugger
- Enable console logs
- Test API endpoints directly with curl

---

## 📚 Additional Resources

- [Expo Documentation](https://docs.expo.dev/)
- [React Native Docs](https://reactnative.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Gemini AI Docs](https://ai.google.dev/docs)

---

## ✅ Installation Checklist

Before using the app, verify:

- [ ] Node.js installed (check: `node --version`)
- [ ] Python installed (check: `python --version`)
- [ ] Git installed (check: `git --version`)
- [ ] Repository cloned
- [ ] Frontend dependencies installed (`npm install`)
- [ ] Backend dependencies installed (`pip install -r requirements.txt`)
- [ ] Frontend `.env` created with Gemini API key
- [ ] Backend `.env` created with Gemini API key
- [ ] Backend server starts without errors
- [ ] Expo starts and shows QR code
- [ ] App loads on phone via Expo Go
- [ ] Can search for products and see results

---

## 🆘 Need Help?

1. Check [Troubleshooting](#troubleshooting) section
2. Review error messages carefully
3. Verify all prerequisites are met
4. Check API keys are correct
5. Ensure phone and computer are on same WiFi
6. Open an issue on GitHub with details

---

## 🎯 Quick Commands Reference

```bash
# Install frontend dependencies
npm install

# Install backend dependencies
cd backend && pip install -r requirements.txt

# Start backend
cd backend && python main.py

# Start frontend (LAN mode)
npx expo start --lan

# Start frontend (Tunnel mode)
npx expo start --tunnel

# Clear cache and restart
npx expo start --clear

# Check backend health
curl http://localhost:8000/health

# Get your IP address (Windows)
ipconfig

# Get your IP address (Mac/Linux)
ifconfig
```

---

**Ready to start? Follow the steps above and you'll be up and running in 10 minutes!** 🚀

**Questions?** Open an issue or check the troubleshooting section.


# SimilarLinks - AI Shopping Assistant

AI-powered mobile app that helps you make smarter purchasing decisions by finding product alternatives, comparing prices, and analyzing products using Google Gemini AI.

---

## Features

- **Smart Product Recommendations** - Paste product URL, get AI-powered alternatives
- **Image Recognition** - Take photo of any product, AI identifies it
- **Invoice Extraction** - Upload receipt, extract warranty and details
- **Multi-Platform Comparison** - Compare prices across Amazon, Flipkart, etc.
- **Dinosaur Game** - Play while waiting for results 🦖

---

## Tech Stack

**Frontend:** React Native, TypeScript, Expo  
**Backend:** Python, FastAPI  
**AI:** Google Gemini 2.5 Flash

---

## Project Structure

```
SimilarLinks/
├── src/                    # Frontend source
│   ├── components/         # UI components
│   ├── screens/           # App screens
│   ├── services/          # API clients
│   └── utils/             # Helpers
├── backend/               # Python backend
│   ├── main.py           # FastAPI server
│   ├── gemini_vision.py  # Image AI
│   └── scraper_api.py    # Web scraping
├── assets/               # Icons, images
└── .env                  # API keys (not committed)
```

---

## Installation

See [INSTALLATION.md](INSTALLATION.md) for complete setup instructions.

**Quick Start:**

1. **Clone repository**
   ```bash
   git clone https://github.com/mailidpwd/Ecommerce.git
   cd Ecommerce
   ```

2. **Install dependencies**
   ```bash
   npm install
   cd backend && pip install -r requirements.txt
   ```

3. **Configure API keys**
   ```bash
   # Copy templates
   cp .env.example .env
   cp backend/.env.example backend/.env
   
   # Add your Gemini API key to both .env files
   # Get key from: https://ai.google.dev/
   ```

4. **Run application**
   ```bash
   # Terminal 1: Start backend
   cd backend && python main.py
   
   # Terminal 2: Start frontend
   npx expo start --lan
   ```

5. **Open on phone**
   - Install Expo Go app
   - Scan QR code
   - Start using!

---

## License

MIT License

---

## Contact

**GitHub:** [mailidpwd](https://github.com/mailidpwd)  
**Email:** mailidpwd@gmail.com

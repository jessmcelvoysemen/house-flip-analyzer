# 🛠️ Local Development Guide

Test your changes locally before deploying to Azure!

## Quick Start

### 1. Install Dependencies

```bash
pip install -r dev-requirements.txt
```

This installs:
- `azure-functions` (Azure Functions SDK)
- `requests` (HTTP library)
- `flask` (Local web server)
- `flask-cors` (CORS support for local testing)

### 2. Configure API Keys

Your API keys are already in `local.settings.json`:
```json
{
  "Values": {
    "RAPIDAPI_KEY": "c44b111aacmshb7f1dddc19f4fb9p12056ajsn613d46763584",
    "RAPIDAPI_HOST": "realty-in-us.p.rapidapi.com"
  }
}
```

✅ These are automatically loaded by the dev server!

### 3. Start the Local Server

```bash
python3 local_dev_server.py
```

You should see:
```
======================================================================
🏠 FAMILY FLIP FINDER - Local Development Server
======================================================================

✅ Server starting at: http://localhost:5000
✅ Open this URL in your browser to test the app

📋 API Endpoints:
   - http://localhost:5000/api/analyze
   - http://localhost:5000/api/health
   - http://localhost:5000/api/listings

⚠️  Make sure you have your API keys set in local.settings.json
   - RAPIDAPI_KEY (for real estate data)

🛑 Press Ctrl+C to stop the server
======================================================================
```

### 4. Open in Browser

Open **http://localhost:5000** in your browser

The app should load and work exactly like it does on Azure!

---

## Testing Your Changes

### Frontend Changes (index.html)
1. Edit `index.html`
2. Save the file
3. Refresh your browser (Ctrl+R or Cmd+R)
4. See changes immediately!

### Backend Changes (api/function_app.py)
1. Edit `api/function_app.py`
2. Save the file
3. The Flask dev server will **auto-reload** (you'll see "Restarting..." in terminal)
4. Refresh your browser to test

---

## What You Can Test Locally

✅ **All the new neighborhoods** (Broad Ripple, Fountain Square, etc.)
✅ **New score labels** ("🔥 Hot!", "Meh", etc.)
✅ **Fixed negative values bug**
✅ **Census data fetching**
✅ **Market data (Days on Market)** - uses your real RapidAPI key
✅ **Listings lookup**
✅ **All scoring logic**

---

## Common Issues

### "ModuleNotFoundError: No module named 'flask'"
**Solution**: Run `pip install -r dev-requirements.txt`

### "Port 5000 is already in use"
**Solution**: Kill the existing process or change the port:
```python
# Edit local_dev_server.py, last line:
app.run(host='0.0.0.0', port=5001, debug=True)  # Use 5001 instead
```

### "Census API errors" or "RapidAPI errors"
**Check**:
1. You have internet connection
2. Your RapidAPI key is valid (check your RapidAPI dashboard)
3. You haven't exceeded your API rate limits

### Changes not showing up?
1. **Hard refresh** your browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Check the Flask terminal output for errors
3. Make sure the file saved properly

---

## Deploying to Azure

Once you've tested locally and everything works:

```bash
git add -A
git commit -m "Your commit message"
git push
```

Azure will automatically deploy from your branch!

---

## Pro Tips

### View API Responses Directly

Test the API endpoints directly in your browser:

- **Health check**: http://localhost:5000/api/health
- **Analysis**: http://localhost:5000/api/analyze?price_min=200000&price_max=225000

### Check Python Logs

Watch the terminal where `local_dev_server.py` is running to see:
- API requests
- Census API calls
- Errors and warnings
- Cache hits/misses

### Use Developer Tools

Open browser DevTools (F12):
- **Console**: See JavaScript errors
- **Network**: See API request/response details
- **Elements**: Inspect the HTML/CSS

---

## File Structure

```
house-flip-analyzer/
├── index.html                  # Frontend (open in browser)
├── api/
│   ├── function_app.py        # Backend logic
│   └── requirements.txt       # Production dependencies
├── local_dev_server.py        # 👈 Run this for local testing!
├── dev-requirements.txt       # Development dependencies
├── local.settings.json        # API keys (auto-loaded)
└── LOCAL_DEVELOPMENT.md       # This file!
```

---

**Happy Testing! 🚀**

# PULSE by Bestower Labs - Deployment Guide

## Geo-AI Trading & Financial Intelligence Terminal

---

## System Overview

PULSE is a fully functional, multi-asset, geo-aware, AI-powered financial intelligence and trading terminal.

### Features
- **Multi-Asset Coverage**: Crypto, US Stocks, UK Stocks, Commodities
- **Real-Time Market Data**: Live prices, charts, volume
- **AI Multi-Agent System**: 16+ specialized analysis agents
- **Technical Analysis**: RSI, MACD, Bollinger Bands, Moving Averages
- **News Intelligence**: Sentiment analysis, impact scoring
- **Whale Monitoring**: Exchange flows, accumulation trends
- **Trading Signals**: Buy/Sell/Hold with confidence scores, entry/exit points

---

## Architecture

```
PULSE System
├── Frontend (React + TypeScript + Tailwind)
│   ├── Dashboard
│   ├── Asset Detail with Charts
│   ├── News Intelligence Panel
│   ├── Whale Monitor
│   └── AI Agent Console
│
└── Backend (Python + FastAPI)
    ├── Data Providers (CoinGecko, Yahoo Finance)
    ├── News Engine (RSS + Sentiment Analysis)
    ├── 16 AI Analysis Agents
    ├── Signal Engine
    └── Technical Analysis
```

---

## Deployment Options

### Option 1: cPanel Shared Hosting (Frontend Only)
The frontend is a static React app that can be deployed to cPanel.

### Option 2: Full Deployment (Recommended)
Requires a VPS or dedicated server with Python support for the backend.

---

## cPanel Deployment Instructions

### Step 1: Upload Frontend

1. Log in to your cPanel account
2. Navigate to **File Manager**
3. Go to `public_html` directory (or your domain's document root)
4. **Delete existing files** (backup first if needed)
5. **Upload** all files from the `frontend` folder:
   - `index.html`
   - `assets/` folder (with all JS/CSS files)

### Step 2: Configure API Endpoint

1. Edit `frontend/assets/index-*.js` (the main JS file)
2. Find the API URL configuration
3. Update to point to your backend server:
   ```javascript
   const API_BASE_URL = 'https://your-backend-server.com/api';
   ```

### Step 3: Test Frontend

1. Visit your domain: `https://yourdomain.com`
2. The dashboard should load
3. Search for assets (BTC, AAPL, GOLD)
4. Verify all panels display correctly

---

## Backend Deployment (VPS/Dedicated Server)

### Requirements

- Python 3.9+
- pip
- Virtual environment support
- 2GB+ RAM
- 10GB+ storage

### Installation Steps

1. **Upload Backend Files**
   ```bash
   # Upload backend folder to /home/user/pulse-backend
   cd /home/user/pulse-backend
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create Environment File**
   ```bash
   nano .env
   ```
   
   Add configuration:
   ```
   APP_NAME=PULSE by Bestower Labs
   DEBUG=false
   HOST=0.0.0.0
   PORT=8000
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=sqlite:///./data/pulse.db
   ```

5. **Create Data Directory**
   ```bash
   mkdir -p data
   ```

6. **Test Backend**
   ```bash
   python -m app.main
   ```
   
   Backend should start on `http://localhost:8000`

7. **Setup Systemd Service** (for auto-start)
   ```bash
   sudo nano /etc/systemd/system/pulse-backend.service
   ```
   
   Add:
   ```ini
   [Unit]
   Description=PULSE Backend
   After=network.target

   [Service]
   Type=simple
   User=your-user
   WorkingDirectory=/home/user/pulse-backend
   Environment=PATH=/home/user/pulse-backend/venv/bin
   ExecStart=/home/user/pulse-backend/venv/bin/python -m app.main
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

8. **Start Service**
   ```bash
   sudo systemctl enable pulse-backend
   sudo systemctl start pulse-backend
   sudo systemctl status pulse-backend
   ```

9. **Setup Nginx Reverse Proxy**
   ```bash
   sudo nano /etc/nginx/sites-available/pulse
   ```
   
   Add:
   ```nginx
   server {
       listen 80;
       server_name api.yourdomain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

10. **Enable Site**
    ```bash
    sudo ln -s /etc/nginx/sites-available/pulse /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl restart nginx
    ```

---

## API Endpoints

### System
- `GET /api/system/health` - Health check

### Assets
- `GET /api/assets/search?query=BTC` - Search assets
- `GET /api/assets/{symbol}/overview` - Asset overview
- `GET /api/assets/{symbol}/chart` - Chart data (OHLCV)
- `GET /api/assets/{symbol}/technicals` - Technical analysis
- `GET /api/assets/{symbol}/news` - Asset-specific news
- `GET /api/assets/{symbol}/flow` - Whale/flow data
- `GET /api/assets/{symbol}/signal` - AI trading signal

### Global
- `GET /api/global/news` - Global news feed
- `GET /api/global/macro` - Macro-economic intelligence feed
- `GET /api/global/geopolitics` - Geopolitical intelligence feed

### Agents
- `GET /api/agents` - Agent status
- `POST /api/agents/{agent_name}/run` - Run specific agent
- `GET /api/agents/{agent_name}/status` - Specific agent status

### Dashboard
- `GET /api/dashboard` - Complete dashboard data

---

## Supported Assets

### Cryptocurrencies
BTC, ETH, BNB, SOL, XRP, ADA, AVAX, DOT, MATIC, LINK, UNI, LTC, BCH, ETC, XLM, ALGO, VET, FIL, TRX, EOS

### US Stocks
AAPL, MSFT, GOOGL, AMZN, TSLA, META, NVDA, NFLX, AMD, INTC, IBM, ORCL, CSCO, ADBE, CRM, PYPL, UBER, LYFT, ZM, SHOP

### UK Stocks
SHEL, AZN, ULVR, HSBA, BP, RIO, GSK, BARC, LLOY, VOD, BT-A, TSCO, BA, RR, JD, III, CRH, REL, CPG

### Commodities
GOLD, SILVER, OIL, BRENT, NATGAS, COPPER, WHEAT, CORN

---

## AI Agents

1. **Market Data Agent** - Price action analysis
2. **Technical Analysis Agent** - Indicator analysis
3. **Sentiment Analysis Agent** - News sentiment
4. **News Analysis Agent** - Event impact
5. **Macro Economic Agent** - Economic factors
6. **Geopolitical Risk Agent** - Risk assessment
7. **Whale Activity Agent** - Large holder analysis
8. **Volume & Liquidity Agent** - Volume patterns
9. **Correlation Agent** - Asset correlations
10. **Risk Management Agent** - Position sizing
11. **Signal Aggregator** - Final signal generation

---

## Troubleshooting

### Frontend 404 Errors
- Ensure all files uploaded correctly
- Check `.htaccess` for rewrite rules
- Verify `index.html` exists in root

### Backend Connection Issues
- Verify backend is running: `curl http://localhost:8000/api/system/health`
- Check firewall rules
- Verify CORS configuration

### API Rate Limits
- CoinGecko: 10-30 calls/minute (free tier)
- Yahoo Finance: No official limits
- Implement caching for production

---

## Security Notes

1. Change default SECRET_KEY in production
2. Use HTTPS for all communications
3. Implement rate limiting
4. Monitor API usage
5. Regular security updates

---

## Support

For issues or questions:
- Check API status: `/api/system/health`
- Review logs: `journalctl -u pulse-backend`
- Verify data sources are accessible

---

## License

PULSE by Bestower Labs - Proprietary Software

---

**Version**: 1.0.0  
**Build Date**: 2024  
**Status**: Production Ready

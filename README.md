# Indian Company Intelligence Scraper + NLP

Auto-generates live research gaps, competitor intelligence, and ESG monitoring for Indian companies.

## What It Does (All Free)

| Feature | How | Data Source |
|---------|-----|-------------|
| **Research gaps** | NLP scans news + SEBI filings, auto-detects risks | Google News RSS + BSE filings |
| **MR&I Solutions** | Maps detected gaps to research methodologies | Auto-generated templates |
| **Competitor intel** | Tracks rival company news automatically | Google News RSS |
| **ESG monitoring** | Scans for carbon, governance, controversy keywords | Google News RSS |
| **Sentiment** | On-device keyword scoring | No API needed |
| **News feed** | Latest headlines with sentiment labels | Google News RSS |

## Setup (5 Minutes)

1. Create free GitHub account at github.com/signup
2. Create new repository (name it `company-intelligence`)
3. Upload these files to the repo:
   - `scraper.py`
   - `.github/workflows/scrape.yml`
   - `README.md` (this file)
4. Go to Actions tab → enable workflows
5. Trigger first run manually or wait 6 hours

## How Dashboard Reads Data

Your dashboard HTML fetches from:
`https://raw.githubusercontent.com/arindammanpreet-create/company-intelligence/main/intelligence_data.json`

## Cost

$0. Uses GitHub Actions free tier (2,000 minutes/month).

## Companies Tracked

- Reliance Industries
- TCS
- Infosys
- HDFC Bank
- Bharti Airtel
- Mumbai Indians

Add more in `scraper.py` `COMPANIES` dict.

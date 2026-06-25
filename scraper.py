#!/usr/bin/env python3
"""
Indian Company Intelligence Scraper + NLP
Auto-generates research gaps, competitor tracking, ESG monitoring
Runs on GitHub Actions free tier
"""

import json
import re
import os
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.parse import quote
from xml.etree import ElementTree as ET
import ssl

# Disable SSL verification for some Indian sites with cert issues
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ============== CONFIG ==============
COMPANIES = {
    "Reliance Industries": {
        "ticker": "RELIANCE",
        "nse_url": "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE",
        "bse_code": "500325",
        "keywords": ["Reliance", "Jio", "Reliance Retail", "RIL", "Mukesh Ambani"],
        "sector": "conglomerate"
    },
    "TCS": {
        "ticker": "TCS",
        "bse_code": "532540",
        "keywords": ["TCS", "Tata Consultancy", "Krithivasan", "IT services"],
        "sector": "it"
    },
    "Infosys": {
        "ticker": "INFY",
        "bse_code": "500209",
        "keywords": ["Infosys", "Salil Parekh", "Topaz", "digital services"],
        "sector": "it"
    },
    "HDFC Bank": {
        "ticker": "HDFCBANK",
        "bse_code": "500180",
        "keywords": ["HDFC Bank", "HDFC", "Sashidhar Jagdishan", "private bank"],
        "sector": "banking"
    },
    "Bharti Airtel": {
        "ticker": "BHARTIARTL",
        "bse_code": "532454",
        "keywords": ["Airtel", "Bharti Airtel", "Gopal Vittal", "5G", "telecom"],
        "sector": "telecom"
    },
    "Mumbai Indians": {
        "ticker": "MI",
        "keywords": ["Mumbai Indians", "IPL", "Akash Ambani", "cricket franchise"],
        "sector": "sports"
    },
    "Royal Challengers Bengaluru": {
        "ticker": "RCB",
        "keywords": ["RCB", "Royal Challengers", "Virat Kohli", "IPL", "cricket franchise"],
        "sector": "sports"
    },
    "Delhi Capitals": {
        "ticker": "DC",
        "keywords": ["Delhi Capitals", "DC", "IPL", "Rishabh Pant", "cricket franchise"],
        "sector": "sports"
    },
    "Material": {
        "ticker": "MATRL",
        "keywords": ["Material", "Material Plus", "Material+", "LRW", "Lieberman Research", "Srijan Technologies", "customer experience", "market research", "Bill Kanarick", "Rahul Dewan"],
        "sector": "market_research"
    }
}

# ============== NLP SENTIMENT & KEYWORD ENGINE ==============

GAP_KEYWORDS = {
    "revenue_risk": ["revenue decline", "sales drop", "top line pressure", "weak demand", "slowing growth", "missed guidance"],
    "margin_pressure": ["margin compression", "cost inflation", "input cost", "EBITDA margin", "profitability pressure", "pricing power"],
    "competition": ["market share loss", "competitive pressure", "price war", "new entrant", "disruption", "losing ground"],
    "regulatory": ["regulatory scrutiny", "SEBI", "RBI", "TRAI", "investigation", "penalty", "compliance", "policy change"],
    "talent": ["attrition", "talent shortage", "hiring freeze", "layoff", "resignation", "key executive departure"],
    "debt_leverage": ["debt", "leverage", "interest burden", "credit rating", "default risk", "refinancing"],
    "esg_concern": ["carbon", "emissions", "pollution", "labor violation", "governance", "board", "whistleblower"],
    "digital_lag": ["digital transformation", "legacy system", "tech debt", "AI adoption", "automation lag"],
    "geopolitical": ["geopolitical", "sanctions", "trade war", "supply chain", "import ban", "export restriction"],
    "consumer_sentiment": ["brand damage", "consumer backlash", "boycott", "social media", "reputation"],
    "fan_engagement": ["fan engagement", "stadium attendance", "ticket sales", "viewership decline", "fan retention"],
    "sponsorship_roi": ["sponsor", "brand lift", "jersey sponsor", "title sponsor", "ROI"],
    "merchandise": ["merchandise", "jersey sales", "fan merchandise", "retail", "licensing"],
    "player_retention": ["player auction", "retention", "salary cap", "player transfer", "contract"],
    "digital_monetization": ["streaming", "digital rights", "OTT", "JioCinema", "broadcast"],
    "women_league": ["WPL", "women premier league", "women cricket", "WPL franchise"],
    "ai_disruption": ["AI disruption", "generative AI", "ChatGPT", "AI research", "synthetic data", "automation"],
    "data_privacy": ["data privacy", "GDPR", "consent", "tracking", "cookie deprecation", "privacy regulation"],
    "talent_war": ["talent shortage", "researcher shortage", "data scientist", "engineer retention", "hiring"],
    "client_churn": ["client loss", "account churn", "budget cut", "marketing spend reduction", "client departure"],
    "platform_competition": ["Qualtrics", "Medallia", "Forsta", "SurveyMonkey", "DIY research", "self-serve"]
}

SEVERITY_WEIGHTS = {
    "revenue_risk": 3, "margin_pressure": 3, "competition": 2, "regulatory": 3,
    "talent": 2, "debt_leverage": 3, "esg_concern": 2, "digital_lag": 2,
    "geopolitical": 2, "consumer_sentiment": 2,
    "fan_engagement": 2, "sponsorship_roi": 3, "merchandise": 2,
    "player_retention": 2, "digital_monetization": 3, "women_league": 2
}

POSITIVE_WORDS = ['growth', 'profit', 'rise', 'gain', 'surge', 'beat', 'exceed', 'strong', 'milestone', 'launch', 'partnership', 'expansion', 'innovation', 'upgrade', 'bullish', 'record']
NEGATIVE_WORDS = ['loss', 'fall', 'drop', 'decline', 'miss', 'weak', 'concern', 'risk', 'crisis', 'investigation', 'layoff', 'debt', 'slowdown', 'cut', 'delay', 'cancel', 'downgrade', 'bearish']

def analyze_sentiment(text):
    text = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    total = pos + neg
    if total == 0:
        return {"score": 0, "label": "Neutral", "pos": 0, "neg": 0}
    score = (pos - neg) / total
    if score > 0.2: label = "Positive"
    elif score < -0.2: label = "Negative"
    else: label = "Neutral"
    return {"score": round(score, 2), "label": label, "pos": pos, "neg": neg}

def detect_gaps(text, company_name):
    """Auto-detect research gaps from text using keyword matching + NLP"""
    text_lower = text.lower()
    gaps = []

    for gap_type, keywords in GAP_KEYWORDS.items():
        matches = [k for k in keywords if k in text_lower]
        if matches:
            severity = "High" if SEVERITY_WEIGHTS[gap_type] >= 3 else "Medium"
            # Create dynamic title and description
            title = generate_gap_title(gap_type, matches[0], company_name)
            desc = generate_gap_description(gap_type, matches, text[:200], company_name)

            gaps.append({
                "title": title,
                "severity": severity,
                "description": desc,
                "detected_from": text[:150] + "...",
                "gap_type": gap_type,
                "keywords_found": matches
            })

    return gaps

def generate_gap_title(gap_type, keyword, company):
    titles = {
        "revenue_risk": f"{company} Revenue Growth Under Pressure",
        "margin_pressure": f"Margin Compression Risk at {company}",
        "competition": f"Competitive Threat Intensifying for {company}",
        "regulatory": f"Regulatory Headwinds for {company}",
        "talent": f"Talent & Retention Challenges at {company}",
        "debt_leverage": f"Balance Sheet Stress Indicators at {company}",
        "esg_concern": f"ESG Compliance Gaps at {company}",
        "digital_lag": f"Digital Transformation Lag at {company}",
        "geopolitical": f"Geopolitical Supply Chain Risk for {company}",
        "consumer_sentiment": f"Brand Reputation Risk for {company}",
        "fan_engagement": f"Fan Engagement & Stadium Experience Gaps at {company}",
        "sponsorship_roi": f"Sponsorship ROI & Commercial Valuation Gaps at {company}",
        "merchandise": f"Merchandise Revenue & Licensing Gaps at {company}",
        "player_retention": f"Player Retention & Auction Strategy Risk at {company}",
        "digital_monetization": f"Digital Monetization & Streaming Revenue Risk at {company}",
        "women_league": f"Women's League (WPL) Commercial Viability at {company}",
        "ai_disruption": f"AI & Generative Technology Disruption Risk at {company}",
        "data_privacy": f"Data Privacy & Tracking Compliance Gaps at {company}",
        "talent_war": f"Talent Acquisition & Retention Crisis at {company}",
        "client_churn": f"Client Budget Cuts & Account Churn Risk at {company}",
        "platform_competition": f"DIY Platform & Self-Serve Research Threat to {company}"
    }
    return titles.get(gap_type, f"{gap_type.replace('_', ' ').title()} Concern at {company}")

def generate_gap_description(gap_type, matches, context, company):
    base_desc = {
        "revenue_risk": f"Recent reports indicate {company} facing demand challenges. Key indicators: {', '.join(matches[:2])}. Context suggests need for pricing elasticity and market share defense research.",
        "margin_pressure": f"Input cost pressures and pricing constraints affecting {company} profitability. Detected concerns: {', '.join(matches[:2])}. Requires cost structure and pricing power analysis.",
        "competition": f"Competitive intensity rising for {company} with {', '.join(matches[:2])} mentioned. Market positioning research needed to defend share.",
        "regulatory": f"Regulatory overhang detected for {company}: {', '.join(matches[:2])}. Compliance cost and policy risk assessment required.",
        "talent": f"Human capital risk flagged at {company}: {', '.join(matches[:2])}. Talent market intelligence and retention strategy research needed.",
        "debt_leverage": f"Financial leverage concerns for {company}: {', '.join(matches[:2])}. Credit risk and refinancing outlook research warranted.",
        "esg_concern": f"ESG red flags detected at {company}: {', '.join(matches[:2])}. Sustainability benchmarking and stakeholder perception study needed.",
        "digital_lag": f"Technology adoption gap identified at {company}: {', '.join(matches[:2])}. Digital maturity assessment and tech investment ROI research required.",
        "geopolitical": f"External risk factors affecting {company}: {', '.join(matches[:2])}. Supply chain resilience and geographic diversification research needed.",
        "consumer_sentiment": f"Reputation risk signals for {company}: {', '.join(matches[:2])}. Brand health tracking and consumer perception research urgently needed.",
        "fan_engagement": f"Fan engagement metrics declining for {company}: {', '.join(matches[:2])}. Need year-round engagement strategy and off-season retention research.",
        "sponsorship_roi": f"Sponsor attribution gaps at {company}: {', '.join(matches[:2])}. Brand lift measurement and commercial valuation framework needed.",
        "merchandise": f"Merchandise revenue underperformance at {company}: {', '.join(matches[:2])}. Product-market fit and pricing research required.",
        "player_retention": f"Squad stability concerns for {company}: {', '.join(matches[:2])}. Auction strategy and salary cap optimization research needed.",
        "digital_monetization": f"Digital revenue streams under pressure at {company}: {', '.join(matches[:2])}. Streaming rights and OTT monetization research warranted.",
        "women_league": f"WPL commercial gaps identified for {company}: {', '.join(matches[:2])}. Women's league brand positioning and sponsor acquisition study needed.",
        "ai_disruption": f"AI-driven disruption threatening {company}'s traditional research models: {', '.join(matches[:2])}. Need to assess synthetic data impact and GenAI integration strategy.",
        "data_privacy": f"Privacy regulation changes affecting {company}'s data collection: {', '.join(matches[:2])}. Compliance cost and alternative data strategy research required.",
        "talent_war": f"Talent competition intensifying for {company}: {', '.join(matches[:2])}. Need competitive compensation benchmarking and retention strategy research.",
        "client_churn": f"Client retention risk signals at {company}: {', '.join(matches[:2])}. Account health tracking and churn prediction research urgently needed.",
        "platform_competition": f"DIY platform threat growing for {company}: {', '.join(matches[:2])}. Competitive positioning and value differentiation research warranted."
    }
    return base_desc.get(gap_type, f"Research gap detected: {', '.join(matches[:2])} at {company}. Primary research recommended.")

# ============== DATA FETCHERS ==============

def fetch_google_news(company_name, keywords, max_items=15):
    """Fetch news from Google News RSS (free, no API key)"""
    articles = []
    query = quote(f"{' OR '.join(keywords[:3])}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        proxy_url = f"https://api.allorigins.win/raw?url={quote(rss_url)}"
        req = Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, context=ssl_context, timeout=15) as response:
            xml_text = response.read().decode('utf-8')

        root = ET.fromstring(xml_text)
        channel = root.find('channel')
        if channel is None:
            return articles

        items = channel.findall('item')
        for item in items[:max_items]:
            title = item.find('title')
            link = item.find('link')
            pub_date = item.find('pubDate')
            source = item.find('source')

            if title is None or link is None:
                continue

            title_text = title.text or ''
            # Clean title (remove source suffix if present)
            title_text = re.sub(r'\s+-\s+[^-]+$', '', title_text)

            articles.append({
                "title": title_text,
                "url": link.text or '#',
                "source": source.text if source is not None else 'Google News',
                "publishedAt": pub_date.text if pub_date is not None else datetime.now().isoformat(),
                "fetched_at": datetime.now().isoformat()
            })
    except Exception as e:
        print(f"Google News fetch failed for {company_name}: {e}")

    return articles

def fetch_sebi_filings(bse_code, company_name):
    """Fetch latest SEBI filings (BSE announcements)"""
    filings = []
    try:
        # BSE corporate announcements page
        url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?strCat=-1&strPrevDate={quote((datetime.now() - timedelta(days=30)).strftime('%Y%m%d'))}&strScrip={bse_code}&strSearchDate={quote(datetime.now().strftime('%Y%m%d'))}&strToDate={quote(datetime.now().strftime('%Y%m%d'))}&strType=C"

        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.bseindia.com/'
        })

        with urlopen(req, context=ssl_context, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))

        if 'Table' in data:
            for item in data['Table'][:10]:
                filings.append({
                    "title": item.get('HEADLINE', 'Corporate Announcement'),
                    "description": item.get('DESC', ''),
                    "date": item.get('NEWS_DT', ''),
                    "category": item.get('CATEGORYNAME', 'General'),
                    "url": f"https://www.bseindia.com/xml-data/corpfiling/Attach/{item.get('ATTACHMENTNAME', '')}"
                })
    except Exception as e:
        print(f"SEBI filings fetch failed for {company_name}: {e}")

    return filings

def fetch_competitor_intel(company_name, sector):
    """Fetch competitor-related news and market intel"""
    competitors = {
        "it": ["TCS", "Infosys", "Wipro", "HCL Tech", "Tech Mahindra"],
        "banking": ["HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak Mahindra"],
        "telecom": ["Airtel", "Jio", "Vodafone Idea", "BSNL"],
        "conglomerate": ["Reliance", "Tata Group", "Adani Group", "Birla Group"],
        "sports": ["Mumbai Indians", "CSK", "RCB", "KKR", "Rajasthan Royals"]
    }

    sector_comps = competitors.get(sector, [])
    comp_news = []

    for comp in sector_comps:
        if comp.lower() not in company_name.lower():
            news = fetch_google_news(comp, [comp], max_items=5)
            for n in news:
                n["related_to"] = comp
                n["relevance"] = "competitor"
            comp_news.extend(news)

    return comp_news

def fetch_esg_data(company_name, keywords):
    """Fetch ESG-related news and controversies"""
    esg_keywords = keywords + ["ESG", "sustainability", "carbon", "emissions", "CSR", "green", "renewable"]
    return fetch_google_news(f"{company_name} ESG", esg_keywords, max_items=10)

# ============== MAIN PIPELINE ==============

def process_company(company_name, config):
    print(f"\n🔍 Processing: {company_name}")

    # 1. Fetch all data sources
    news = fetch_google_news(company_name, config["keywords"])
    print(f"  📰 News articles: {len(news)}")

    filings = []
    if "bse_code" in config:
        filings = fetch_sebi_filings(config["bse_code"], company_name)
        print(f"  📋 SEBI filings: {len(filings)}")

    comp_intel = fetch_competitor_intel(company_name, config["sector"])
    print(f"  🏢 Competitor intel: {len(comp_intel)}")

    esg_news = fetch_esg_data(company_name, config["keywords"])
    print(f"  🌱 ESG news: {len(esg_news)}")

    # 2. NLP Analysis on all text
    all_texts = []
    for article in news + filings + comp_intel + esg_news:
        text = article.get("title", "") + " " + article.get("description", "")
        all_texts.append(text)

    combined_text = " ".join(all_texts)

    # 3. Sentiment analysis
    sentiment = analyze_sentiment(combined_text)

    # 4. Auto-detect research gaps
    auto_gaps = detect_gaps(combined_text, company_name)

    # 5. Deduplicate gaps by title
    seen_titles = set()
    unique_gaps = []
    for gap in auto_gaps:
        if gap["title"] not in seen_titles:
            seen_titles.add(gap["title"])
            unique_gaps.append(gap)

    # Limit to top 5 real gaps
    unique_gaps = unique_gaps[:5]

    # 6. Generate MR&I Solutions attached directly to each gap
    unique_gaps = generate_solutions(unique_gaps, company_name)

    # Fill to minimum 3 gaps with UNIQUE types and titles — no duplicates
    fill_templates = [
        ("monitoring", "Strategic Market Intelligence & Early Warning System", "Continuous macro monitoring, competitor tracking, and early signal detection for strategic pivots.", "Medium"),
        ("competition", "Competitive Intelligence & Win/Loss Analysis", "Deep-dive into competitor positioning, pricing moves, and market share defense strategies.", "Medium"),
        ("digital_lag", "Digital Transformation & Tech Investment Benchmarking", "Assessment of digital maturity, AI adoption, and technology ROI relative to sector leaders.", "Medium"),
        ("consumer_sentiment", "Brand Health & Stakeholder Perception Tracking", "Ongoing brand tracking, reputation monitoring, and crisis preparedness protocols.", "Medium"),
        ("esg_concern", "ESG Performance & Sustainability Benchmarking", "ESG scoring, carbon accounting, and stakeholder perception on sustainability commitments.", "Low")
    ]

    # Track which gap types we already have (from real gaps) to avoid duplicates
    existing_types = {g.get("gap_type", "monitoring") for g in unique_gaps}
    fill_idx = 0

    while len(unique_gaps) < 3 and fill_idx < len(fill_templates):
        gap_type, fill_title, fill_desc, fill_sev = fill_templates[fill_idx]
        # Only add if we don't already have this gap type
        if gap_type not in existing_types:
            extra_gap = {
                "title": f"{company_name}: {fill_title}",
                "severity": fill_sev,
                "description": fill_desc,
                "detected_from": "System-generated strategic coverage gap",
                "gap_type": gap_type,
                "keywords_found": []
            }
            extra_gap = generate_solutions([extra_gap], company_name)[0]
            unique_gaps.append(extra_gap)
            existing_types.add(gap_type)
        fill_idx += 1

    unique_gaps = unique_gaps[:5]  # Hard cap at 5

    # 7. Compile result
    result = {
        "company": company_name,
        "ticker": config["ticker"],
        "sector": config["sector"],
        "last_updated": datetime.now().isoformat(),
        "data_sources": {
            "news_count": len(news),
            "filings_count": len(filings),
            "competitor_intel_count": len(comp_intel),
            "esg_news_count": len(esg_news)
        },
        "sentiment": sentiment,
        "news": news[:10],  # Keep top 10
        "research_gaps": unique_gaps,
        "competitor_intel": comp_intel[:5],
        "esg_highlights": esg_news[:5],
        "filings": filings[:5]
    }

    return result

def generate_solutions(gaps, company_name):
    """Generate concise MR&I solutions attached directly to each gap"""

    # Define concise solution templates - one per gap type
    solution_templates = {
        "revenue_risk": {
            "title": "Revenue Elasticity & Demand Forecasting",
            "impact": "High",
            "timeline": "8-12 weeks",
            "price": "₹18-28 Lakhs",
            "methods": "Quantitative (CATI/CAWI n=5,000) + Qualitative (24 IDIs) + Econometric (ARIMA/VAR)",
            "deliverables": "TAM/SAM/SOM report, Price Sensitivity Meter, Revenue risk dashboard, Quarterly forecast model"
        },
        "margin_pressure": {
            "title": "Cost Structure & Pricing Power Analysis",
            "impact": "High",
            "timeline": "10-14 weeks", 
            "price": "₹22-35 Lakhs",
            "methods": "Mystery Shopping (200+ touchpoints) + Expert Interviews (16) + ABC Costing",
            "deliverables": "Monthly margin report, Cost-driver Pareto, Pricing scorecard, Margin optimization playbook"
        },
        "competition": {
            "title": "Competitive Positioning Intelligence",
            "impact": "High",
            "timeline": "6-10 weeks + ongoing",
            "price": "₹15-25 Lakhs + ₹3L/month",
            "methods": "Win/Loss (100 deals) + Social Listening + Patent/Job Tracking",
            "deliverables": "Weekly battlecards, Quarterly win/loss analysis, Pricing gap tracker, Response engine"
        },
        "regulatory": {
            "title": "Policy & Regulatory Risk Monitoring",
            "impact": "High",
            "timeline": "4-6 weeks + ongoing",
            "price": "₹12-18 Lakhs + ₹1.5L/month",
            "methods": "Monte Carlo Simulation + Delphi Panel (15 experts) + Scenario Planning",
            "deliverables": "Monthly regulatory radar, Compliance cost models, Stakeholder matrices, Pre-budget memos"
        },
        "talent": {
            "title": "Talent Market Intelligence & Employer Brand",
            "impact": "Medium",
            "timeline": "8-12 weeks",
            "price": "₹14-22 Lakhs",
            "methods": "LinkedIn Talent Insights + Campus Data (500+ colleges) + Exit Interviews (30)",
            "deliverables": "Quarterly talent report, Employer Brand Index, Compensation matrix, Retention heatmap"
        },
        "debt_leverage": {
            "title": "Credit Risk & Capital Structure Intelligence",
            "impact": "High",
            "timeline": "6-8 weeks",
            "price": "₹16-24 Lakhs",
            "methods": "Debt Covenant Stress-testing + Investor Interviews (12) + Altman Z-score Trending",
            "deliverables": "Quarterly capital briefing, Investor perception tracker, WACC model, Refinancing window analysis"
        },
        "esg_concern": {
            "title": "ESG Performance Benchmarking",
            "impact": "Medium",
            "timeline": "10-14 weeks",
            "price": "₹20-32 Lakhs",
            "methods": "CDP/Sustainalytics/MSCI Scoring + Stakeholder Interviews (25) + Carbon Accounting (GHG Protocol)",
            "deliverables": "Quarterly ESG scorecard, Carbon trajectory analysis, Stakeholder Perception Index, ESG investor deck"
        },
        "digital_lag": {
            "title": "Digital Maturity Assessment & Tech ROI",
            "impact": "Medium",
            "timeline": "8-12 weeks",
            "price": "₹18-28 Lakhs",
            "methods": "DMM Survey (200+ employees) + CIO Interviews (20) + NPV/IRR Modeling",
            "deliverables": "Digital transformation tracker, Tech prioritization matrix, Cloud/AI/ERP roadmap, Vendor scorecards"
        },
        "geopolitical": {
            "title": "Supply Chain Resilience & Geographic Risk",
            "impact": "Medium",
            "timeline": "10-16 weeks",
            "price": "₹22-35 Lakhs",
            "methods": "Herfindahl Index + UNCTAD Mapping + Supplier Interviews (30) + 4-Scenario Model",
            "deliverables": "Supply chain risk dashboard, Alternative sourcing map, Tariff impact model, Diversification strategy"
        },
        "consumer_sentiment": {
            "title": "Brand Health & Reputation Risk Tracking",
            "impact": "High",
            "timeline": "6-8 weeks + ongoing",
            "price": "₹16-25 Lakhs + ₹2.5L/month",
            "methods": "Brand Tracking (n=2,000 quarterly) + Focus Groups (16) + Social Listening (Brandwatch)",
            "deliverables": "Monthly brand scorecard, Reputation alerts, Perceptual positioning maps, Crisis playbook"
        },
        "monitoring": {
            "title": "Strategic Market Intelligence Subscription",
            "impact": "Medium",
            "timeline": "4-6 weeks setup + quarterly",
            "price": "₹12-20 Lakhs + ₹4-6L/quarter",
            "methods": "Macro Dashboard + Expert Interviews (15/quarter) + GLG/Third Bridge Network",
            "deliverables": "Quarterly strategy briefings, Scenario workshops (2/year), Opportunity reports, Board dashboard"
        },
        "fan_engagement": {
            "title": "Fan Lifecycle & Engagement Analytics",
            "impact": "High",
            "timeline": "6-12 months",
            "price": "₹15-25 Lakhs + ₹3L/quarter",
            "methods": "360° Fan Intelligence Platform + Social Listening + App Analytics + Stadium IoT",
            "deliverables": "Fan cohort analysis, Off-season retention playbook, Engagement heatmaps, Churn prediction model"
        },
        "sponsorship_roi": {
            "title": "Sponsorship Impact Measurement Framework",
            "impact": "High",
            "timeline": "6-12 months",
            "price": "₹18-28 Lakhs + ₹2.5L/quarter",
            "methods": "Brand Lift Studies + Jersey Exposure Tracking + Social Sentiment + Recall Surveys",
            "deliverables": "Quarterly sponsor ROI reports, Brand lift index, Competitive benchmarking, Attribution model"
        },
        "merchandise": {
            "title": "Merchandise Demand & Pricing Research",
            "impact": "Medium",
            "timeline": "12-18 months",
            "price": "₹14-22 Lakhs",
            "methods": "Conjoint Analysis (n=10,000) + Pricing Experiments + Retail Audit + SKU Tracking",
            "deliverables": "Demand forecast by SKU, Price elasticity curves, Limited edition concept testing, Retail channel strategy"
        },
        "player_retention": {
            "title": "Squad Strategy & Auction Intelligence",
            "impact": "Medium",
            "timeline": "4-6 months + ongoing",
            "price": "₹12-18 Lakhs + ₹1.5L/quarter",
            "methods": "Player Performance Analytics + Salary Cap Modeling + Peer Benchmarking + Scenario Planning",
            "deliverables": "Auction strategy playbook, Retention priority matrix, Salary cap optimizer, Competitor squad analysis"
        },
        "digital_monetization": {
            "title": "Digital Streaming & OTT Monetization Strategy",
            "impact": "High",
            "timeline": "8-14 months",
            "price": "₹20-32 Lakhs + ₹4L/quarter",
            "methods": "Viewer Behavior Analytics + Ad Revenue Modeling + Subscription Pricing + Content ROI",
            "deliverables": "Streaming revenue model, Ad inventory optimization, Paywall strategy, Content performance dashboard"
        },
        "women_league": {
            "title": "WPL Brand & Commercial Viability Study",
            "impact": "Medium",
            "timeline": "10-16 months",
            "price": "₹16-26 Lakhs",
            "methods": "Demographic Research + Sponsor Pipeline + Media Rights Valuation + Fan Overlap Mapping",
            "deliverables": "WPL brand positioning, Sponsor acquisition roadmap, Media rights valuation, Fan base overlap analysis"
        },
        "ai_disruption": {
            "title": "GenAI Integration & Synthetic Data Strategy",
            "impact": "High",
            "timeline": "8-14 months",
            "price": "₹22-35 Lakhs + ₹5L/quarter",
            "methods": "AI Readiness Audit + Synthetic Data Pilots + Client Perception Tracking + Competitive Benchmarking",
            "deliverables": "GenAI roadmap, Synthetic data governance framework, Client AI acceptance index, Competitive AI positioning report"
        },
        "data_privacy": {
            "title": "Privacy-First Research Architecture",
            "impact": "High",
            "timeline": "6-10 months",
            "price": "₹18-28 Lakhs",
            "methods": "Privacy Impact Assessment + Zero-Party Data Strategy + Consent Management Audit + Regulatory Scenario Planning",
            "deliverables": "Privacy-compliant research playbook, Zero-party data collection framework, Consent management system, Regulatory compliance dashboard"
        },
        "talent_war": {
            "title": "Talent Market Intelligence & Employer Brand Strategy",
            "impact": "Medium",
            "timeline": "8-12 months",
            "price": "₹14-22 Lakhs + ₹2L/quarter",
            "methods": "Compensation Benchmarking + Employer Brand Tracking + Exit Interview Analysis + Talent Pipeline Mapping",
            "deliverables": "Compensation matrix by role, Employer brand index, Retention risk heatmap, Talent acquisition playbook"
        },
        "client_churn": {
            "title": "Client Health & Churn Prediction System",
            "impact": "High",
            "timeline": "6-10 months + ongoing",
            "price": "₹20-32 Lakhs + ₹3L/quarter",
            "methods": "Account Health Scoring + Client Satisfaction Tracking + Budget Cycle Analysis + Win/Loss Research",
            "deliverables": "Churn prediction model, Client health dashboard, Quarterly NPS tracker, Account expansion playbook"
        },
        "platform_competition": {
            "title": "DIY Platform Competitive Defense Strategy",
            "impact": "Medium",
            "timeline": "8-12 months",
            "price": "₹16-25 Lakhs",
            "methods": "Platform Feature Benchmarking + Client Switching Cost Analysis + Value Proposition Testing + Pricing Elasticity",
            "deliverables": "Competitive feature matrix, Client switching barrier analysis, Value differentiation framework, Premium pricing model"
        }
    }

    # Attach one solution directly to EACH gap — no cross-gap deduplication
    for gap in gaps:
        gap_type = gap.get("gap_type", "monitoring")
        template = solution_templates.get(gap_type, solution_templates["monitoring"])

        gap["solutions"] = [{
            "title": f"{company_name}: {template['title']}",
            "impact": template["impact"],
            "timeline": template["timeline"],
            "price": template["price"],
            "methodology": template["methods"],
            "description": f"**MRA/ESOMAR-compliant study**. {template['methods']}. **Deliverables**: {template['deliverables']}.",
            "gap_type": gap_type,
            "framework": "MRA/ESOMAR"
        }]

    return gaps

def main():
    print("=" * 60)
    print("INDIAN COMPANY INTELLIGENCE SCRAPER + NLP")
    print(f"Run started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_data = {}

    for company_name, config in COMPANIES.items():
        try:
            result = process_company(company_name, config)
            all_data[company_name] = result
        except Exception as e:
            print(f"  ❌ Error processing {company_name}: {e}")
            all_data[company_name] = {
                "company": company_name,
                "error": str(e),
                "last_updated": datetime.now().isoformat()
            }

    # Save output
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "version": "1.0",
            "total_companies": len(COMPANIES),
            "data_sources": ["Google News RSS", "BSE Corporate Filings", "On-device NLP"]
        },
        "companies": all_data
    }

    with open('intelligence_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"✅ Complete! Saved to intelligence_data.json")
    print(f"📊 Companies processed: {len(all_data)}")
    print(f"⏱️  Total time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    # Print summary
    for name, data in all_data.items():
        if "error" not in data:
            gaps = len(data.get("research_gaps", []))
            news = data.get("data_sources", {}).get("news_count", 0)
            sent = data.get("sentiment", {}).get("label", "N/A")
            print(f"  • {name}: {gaps} gaps, {news} news, sentiment: {sent}")

if __name__ == "__main__":
    main()

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
    "consumer_sentiment": ["brand damage", "consumer backlash", "boycott", "social media", "reputation"]
}

SEVERITY_WEIGHTS = {
    "revenue_risk": 3, "margin_pressure": 3, "competition": 2, "regulatory": 3,
    "talent": 2, "debt_leverage": 3, "esg_concern": 2, "digital_lag": 2,
    "geopolitical": 2, "consumer_sentiment": 2
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
        "consumer_sentiment": f"Brand Reputation Risk for {company}"
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
        "consumer_sentiment": f"Reputation risk signals for {company}: {', '.join(matches[:2])}. Brand health tracking and consumer perception research urgently needed."
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

    # Limit to top 5 gaps
    unique_gaps = unique_gaps[:5]

    # If no gaps detected, add a generic one
    if not unique_gaps:
        unique_gaps.append({
            "title": f"{company_name} Strategic Monitoring Required",
            "severity": "Medium",
            "description": f"No critical gaps detected in current news cycle, but continuous market intelligence recommended for {company_name} given sector dynamics.",
            "detected_from": "Aggregate news analysis",
            "gap_type": "monitoring",
            "keywords_found": []
        })

    # 6. Generate MR&I Solutions based on gaps (always generate, even if no gaps)
    solutions = generate_solutions(unique_gaps, company_name)

    # Ensure we always have at least 3 solutions with MRA/ESOMAR framework references
    if len(solutions) < 3:
        additional = generate_solutions([], company_name)
        solutions.extend(additional)
        solutions = solutions[:5]

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
        "solutions": solutions,
        "competitor_intel": comp_intel[:5],
        "esg_highlights": esg_news[:5],
        "filings": filings[:5]
    }

    return result

def generate_solutions(gaps, company_name):
    """Generate MR&I solutions based on detected gaps using MRA, ESOMAR & industry frameworks"""
    solutions = []

    # If no gaps detected, create generic monitoring solutions
    if not gaps:
        gaps = [{
            "title": f"{company_name} Strategic Market Monitoring",
            "severity": "Medium",
            "gap_type": "monitoring"
        }]

    for i, gap in enumerate(gaps):
        gap_type = gap.get("gap_type", "general")
        severity = gap["severity"]

        # Map gap types to MR&I solutions with framework references
        solution_templates = {
            "revenue_risk": {
                "title": f"{company_name}: Revenue Elasticity & Demand Forecasting Study",
                "impact": "High",
                "timeline": "8-12 weeks",
                "price": "₹18-28 Lakhs",
                "methodology": "Quantitative + Econometric Modeling",
                "description": f"**MRA-Compliant Primary Research** using stratified random sampling (n=5,000 B2B/B2C customers). **Quantitative**: CATI/CAWI surveys with conjoint analysis for price-demand elasticity. **Qualitative**: 24 in-depth interviews (IDIs) with procurement heads and CFOs. **Econometric**: Time-series forecasting using ARIMA/VAR models on 3-year historical data. **Deliverables**: (1) TAM/SAM/SOM sizing report, (2) Price sensitivity meter (PSM) analysis, (3) Revenue risk dashboard with early-warning KPIs, (4) Quarterly demand forecasting model. **ESOMAR Ethics**: Informed consent, anonymized data, 95% confidence interval reporting. **Team**: 1 Research Director, 2 Quantitative Analysts, 1 Data Scientist."
            },
            "margin_pressure": {
                "title": f"{company_name}: Cost Structure & Pricing Power Analysis",
                "impact": "High",
                "timeline": "10-14 weeks",
                "price": "₹22-35 Lakhs",
                "methodology": "Competitive Intelligence + Mystery Shopping + Financial Modeling",
                "description": f"**MRA Competitive Intelligence Framework** with ESOMAR ethical compliance. **Quantitative**: Mystery shopping across 200+ dealer/distributor touchpoints, cost benchmarking vs. 5-7 peers. **Qualitative**: 16 expert interviews with ex-employees, suppliers, and industry consultants (all under NDA). **Financial Modeling**: Activity-based costing (ABC) decomposition, contribution margin waterfall analysis. **Deliverables**: (1) Monthly margin intelligence report, (2) Cost-driver Pareto charts, (3) Pricing power scorecard by SKU/segment, (4) Margin optimization playbook with scenario planning. **Anthropological**: Ethnographic observation of 10 shop-floor operations to identify hidden cost leakages. **Team**: 1 CI Director, 2 Financial Analysts, 1 Operations Researcher."
            },
            "competition": {
                "title": f"{company_name}: Competitive Positioning Intelligence (Battlecard Program)",
                "impact": "High",
                "timeline": "6-10 weeks initial + ongoing",
                "price": "₹15-25 Lakhs (initial) + ₹3 Lakhs/month (ongoing)",
                "methodology": "Continuous Monitoring + Win/Loss + Social Listening",
                "description": f"**MRA Continuous Research Program** per ESOMAR ongoing research standards. **Quantitative**: Win/loss analysis of 100 recent deals, market share tracking via Nielsen/IRI secondary data. **Qualitative**: 20 competitor executive interviews (blind recruitment), quarterly war-gaming workshops. **Digital**: Social listening via Brandwatch/Sprinklr, patent filing monitoring, job posting analysis for R&D direction. **Deliverables**: (1) Weekly competitive battlecards, (2) Quarterly win/loss analysis with root-cause coding, (3) Pricing gap tracker by product line, (4) Strategic response recommendation engine. **Brand Design**: Visual competitive landscape maps, perceptual positioning charts. **Team**: 1 CI Manager, 2 Research Associates, 1 Data Analyst (ongoing)."
            },
            "regulatory": {
                "title": f"{company_name}: Policy & Regulatory Risk Monitoring (Horizon Scanning)",
                "impact": "High",
                "timeline": "4-6 weeks setup + ongoing",
                "price": "₹12-18 Lakhs (setup) + ₹1.5 Lakhs/month (ongoing)",
                "methodology": "Policy Research + Delphi Method + Scenario Planning",
                "description": f"**MRA Policy Research Framework** with transparent source attribution. **Quantitative**: Regulatory cost-impact modeling using Monte Carlo simulation, compliance cost benchmarking across 10+ peers. **Qualitative**: Delphi panel of 15 regulatory experts (2 rounds), stakeholder mapping via power/interest grids. **Scenario Planning**: 3-scenario model (base/optimistic/pessimistic) for major regulatory changes. **Deliverables**: (1) Monthly regulatory radar with probability-weighted risk scores, (2) Compliance cost scenario models, (3) Stakeholder impact matrices, (4) Pre-budget memoranda and representation drafts. **Anthropological**: Field immersion with 5 regulatory consultants to understand informal decision-making channels. **Team**: 1 Public Affairs Director, 1 Policy Analyst, 1 Risk Modeler."
            },
            "talent": {
                "title": f"{company_name}: Talent Market Intelligence & Employer Brand Research",
                "impact": "Medium",
                "timeline": "8-12 weeks",
                "price": "₹14-22 Lakhs",
                "methodology": "HR Analytics + Employer Brand Tracking + Compensation Benchmarking",
                "description": f"**MRA Workforce Research Standards** with NASSCOM/AICTE data integration. **Quantitative**: Quarterly talent supply-demand analysis using LinkedIn Talent Insights, campus placement data (500+ colleges), compensation benchmarking vs. 5-7 peers (n=2,000 matched profiles). **Qualitative**: 30 exit interviews (structured), 20 campus recruiter focus groups, employer brand perception study via projective techniques. **Deliverables**: (1) Quarterly talent market report, (2) Employer brand perception index (EBI), (3) Compensation benchmarking matrix by role/level, (4) Retention risk heatmap with predictive scoring. **Brand Design**: Employer brand visual identity audit, EVP (Employee Value Proposition) messaging framework. **Team**: 1 HR Research Director, 2 Quantitative Researchers, 1 Brand Strategist."
            },
            "debt_leverage": {
                "title": f"{company_name}: Credit Risk & Capital Structure Intelligence",
                "impact": "High",
                "timeline": "6-8 weeks",
                "price": "₹16-24 Lakhs",
                "methodology": "Financial Research + Investor Perception + Credit Analytics",
                "description": f"**MRA Financial Research Protocols** with CRISIL/ICRA data partnership. **Quantitative**: Debt covenant stress-testing, credit rating sensitivity analysis, refinancing pipeline modeling using Bloomberg/Reuters data. **Qualitative**: 12 institutional investor interviews (CIOs, credit analysts), 8 debenture trustee discussions. **Credit Analytics**: Altman Z-score trending, interest coverage ratio forecasting, liquidity gap analysis. **Deliverables**: (1) Quarterly capital market briefing, (2) Investor perception tracking with sentiment scoring, (3) Optimal capital structure model (WACC minimization), (4) Refinancing timing recommendation with window analysis. **Quantitative**: Monte Carlo simulation for default probability under 5 macro scenarios. **Team**: 1 Financial Research Director, 2 Credit Analysts, 1 Quantitative Modeler."
            },
            "esg_concern": {
                "title": f"{company_name}: ESG Performance Benchmarking & Stakeholder Perception",
                "impact": "Medium",
                "timeline": "10-14 weeks",
                "price": "₹20-32 Lakhs",
                "methodology": "Sustainability Research + Stakeholder Engagement + Carbon Accounting",
                "description": f"**ESG Research aligned with GRI, SASB, BRSR, and TCFD frameworks**. **Quantitative**: Comparative ESG scoring across {company_name} and 5-7 peers using CDP responses, Sustainalytics ratings, MSCI ESG scores. Carbon footprint accounting (Scope 1/2/3) per GHG Protocol. **Qualitative**: 25 stakeholder interviews (investors, NGOs, community leaders), supply chain audits at 15 vendor locations. **Deliverables**: (1) Quarterly ESG scorecard with peer benchmarking, (2) Carbon trajectory analysis with net-zero pathway modeling, (3) Stakeholder perception index (SPI), (4) Sustainability communication strategy and ESG investor presentation. **Anthropological**: Community immersion study at 3 operational sites to understand local ESG impact narratives. **Brand Design**: ESG report visual redesign, sustainability storyboard for annual report. **Team**: 1 ESG Research Director, 2 Sustainability Analysts, 1 Carbon Accountant, 1 Visual Designer."
            },
            "digital_lag": {
                "title": f"{company_name}: Digital Maturity Assessment & Tech Investment ROI",
                "impact": "Medium",
                "timeline": "8-12 weeks",
                "price": "₹18-28 Lakhs",
                "methodology": "Technology Adoption Research + Digital Audit + ROI Modeling",
                "description": f"**MRA Technology Adoption Framework** using TAM/TOE/DOI models. **Quantitative**: Digital maturity assessment of 200+ employees via structured survey (DMM framework), tech spend benchmarking vs. Gartner peer data. **Qualitative**: 20 CIO/CTO/VP Engineering interviews, 5 vendor briefings (AWS, Azure, Salesforce), quarterly digital war-gaming. **ROI Modeling**: NPV/IRR analysis for proposed tech investments, payback period modeling, TCO comparison. **Deliverables**: (1) Quarterly digital transformation tracker, (2) Tech investment prioritization matrix (Effort vs. Impact), (3) Cloud/AI/ERP adoption roadmap with milestones, (4) Vendor evaluation scorecards. **Brand Design**: Digital customer journey maps, UX heuristic evaluation of 10 key touchpoints. **Team**: 1 Digital Research Director, 2 Tech Analysts, 1 UX Researcher, 1 Financial Modeler."
            },
            "geopolitical": {
                "title": f"{company_name}: Supply Chain Resilience & Geographic Risk Intelligence",
                "impact": "Medium",
                "timeline": "10-16 weeks",
                "price": "₹22-35 Lakhs",
                "methodology": "Trade Intelligence + Supplier Risk + Geopolitical Scenario Planning",
                "description": f"**MRA Trade Research & Geopolitical Risk Framework**. **Quantitative**: Supplier concentration analysis (Herfindahl index), geographic exposure mapping using UNCTAD/World Bank data, import duty scenario modeling. **Qualitative**: 30 supplier interviews (structured risk assessment), 10 logistics provider discussions, expert panel on India-China trade dynamics. **Scenario Planning**: 4-scenario geopolitical model (status quo/escalation/diversification/trade war) with probability weights. **Deliverables**: (1) Quarterly supply chain risk dashboard, (2) Alternative sourcing recommendations with total landed cost analysis, (3) Tariff impact model by product category, (4) Geographic diversification strategy with phased implementation. **Anthropological**: 2-week field immersion at key supplier clusters (e.g., Shenzhen, Dhaka) to understand informal supply chain dependencies. **Team**: 1 Supply Chain Research Director, 2 Trade Analysts, 1 Geopolitical Risk Specialist."
            },
            "consumer_sentiment": {
                "title": f"{company_name}: Brand Health Tracking & Reputation Risk Monitoring",
                "impact": "High",
                "timeline": "6-8 weeks setup + ongoing",
                "price": "₹16-25 Lakhs (setup) + ₹2.5 Lakhs/month (ongoing)",
                "methodology": "Brand Equity Research + Social Listening + Crisis Simulation",
                "description": f"**MRA Brand Research Standards** using Aaker/Keller brand equity frameworks. **Quantitative**: Continuous brand tracking (n=2,000 quarterly) via CAWI panel, brand health metrics (awareness, consideration, loyalty, NPS), conjoint-based brand preference modeling. **Qualitative**: 16 consumer focus groups (4 cities), 12 expert interviews with brand consultants, semiotics analysis of brand communications. **Digital**: Social listening via Brandwatch/Sprinklr (real-time), sentiment trend analysis, influencer mapping. **Deliverables**: (1) Monthly brand health scorecard, (2) Reputation risk alerts with escalation triggers, (3) Competitive brand positioning maps (perceptual mapping), (4) Crisis communication playbook with scenario trees. **Brand Design**: Visual brand audit, packaging/communication redesign recommendations, brand architecture optimization. **Anthropological**: Consumer home immersion (10 households) to understand cultural brand meanings. **Team**: 1 Brand Research Director, 2 Quantitative Researchers, 1 Semiotician, 1 Visual Designer (ongoing)."
            },
            "monitoring": {
                "title": f"{company_name}: Strategic Market Intelligence Subscription (Ongoing MR Program)",
                "impact": "Medium",
                "timeline": "4-6 weeks setup + quarterly deliverables",
                "price": "₹12-20 Lakhs (setup) + ₹4-6 Lakhs/quarter (ongoing)",
                "methodology": "Continuous Research + Expert Network + Scenario Planning",
                "description": f"**MRA Continuous Research Program** with ESOMAR ongoing research ethics. **Quantitative**: Monthly macro-indicator dashboard (GDP, inflation, sector growth, FDI flows), quarterly consumer confidence index, competitor financial tracking. **Qualitative**: Quarterly expert interviews (15 industry leaders), semi-annual executive roundtables, ongoing expert network access (GLG/Third Bridge). **Deliverables**: (1) Quarterly strategy briefings (50-slide deck), (2) Scenario planning workshops (2 per year), (3) Opportunity identification reports with TAM sizing, (4) Board-level market intelligence dashboard (real-time). **Brand Design**: Market landscape infographics, trend visualization reports, competitor comparison matrices. **Anthropological**: Annual cultural trend immersion (2 weeks) in key markets to identify emerging consumer behaviors. **Team**: 1 Research Director, 2 Senior Analysts, 1 Data Visualization Specialist (ongoing)."
            }
        }

        template = solution_templates.get(gap_type, solution_templates["monitoring"])

        solutions.append({
            "title": template["title"],
            "impact": template.get("impact", "Medium"),
            "timeline": template.get("timeline", "12-18 weeks"),
            "price": template.get("price", "₹15-25 Lakhs"),
            "methodology": template.get("methodology", "Mixed Methods Research"),
            "description": template["description"],
            "addresses_gap": gap["title"],
            "gap_type": gap_type,
            "framework": "MRA/ESOMAR"
        })

    # Always ensure at least 3-5 solutions
    while len(solutions) < 3:
        solutions.append({
            "title": f"{company_name}: Strategic Market Intelligence Subscription (Ongoing MR Program)",
            "impact": "Medium",
            "timeline": "4-6 weeks setup + quarterly deliverables",
            "price": "₹12-20 Lakhs (setup) + ₹4-6 Lakhs/quarter (ongoing)",
            "methodology": "Continuous Research + Expert Network + Scenario Planning",
            "description": f"**MRA Continuous Research Program** with ESOMAR ongoing research ethics. **Quantitative**: Monthly macro-indicator dashboard (GDP, inflation, sector growth, FDI flows), quarterly consumer confidence index, competitor financial tracking. **Qualitative**: Quarterly expert interviews (15 industry leaders), semi-annual executive roundtables, ongoing expert network access (GLG/Third Bridge). **Deliverables**: (1) Quarterly strategy briefings (50-slide deck), (2) Scenario planning workshops (2 per year), (3) Opportunity identification reports with TAM sizing, (4) Board-level market intelligence dashboard (real-time). **Brand Design**: Market landscape infographics, trend visualization reports, competitor comparison matrices. **Anthropological**: Annual cultural trend immersion (2 weeks) in key markets to identify emerging consumer behaviors. **Team**: 1 Research Director, 2 Senior Analysts, 1 Data Visualization Specialist (ongoing).",
            "addresses_gap": "General strategic monitoring",
            "gap_type": "monitoring",
            "framework": "MRA/ESOMAR"
        })

    return solutions[:5]  # Cap at 5 solutionsdef main():
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

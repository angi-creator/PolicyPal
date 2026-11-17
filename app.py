import html
import os
import re
from typing import List

import requests
import streamlit as st

TEXAS_LEG_SESSION = os.getenv("TEXAS_LEG_SESSION", "90R")

st.set_page_config(
    page_title="PolicyPal",
    page_icon="📜",
    layout="wide",
)

POLICY_PRIORITY_MAP = {
    "labor rights & worker protections": {
        "keywords": [
            "right to work", "union", "collective bargaining", "workers compensation",
            "worker compensation", "state employee", "public employee", "benefits",
            "wage theft", "overtime", "unemployment", "paid leave", "whistleblower",
            "retaliation", "heat stress", "first aid", "mental health", "ai", "artificial intelligence",
            "non-compete", "just cause", "off-duty", "privacy", "workplace safety",
            "employees", "pay raise", "public safety"
        ],
        "weight": 40,
    },
    "energy & infrastructure": {
        "keywords": [
            "utility", "transmission", "distribution", "electric grid", "reliability",
            "nuclear", "infrastructure", "water infrastructure", "water", "critical infrastructure",
            "data center", "power lines", "powerline", "buried power lines", "permits",
            "electric generation", "grid resilience", "restoration", "gulf coast", "energy"
        ],
        "weight": 38,
    },
    "workforce development & education": {
        "keywords": [
            "apprenticeship", "career and technical education", "cte", "training", "workforce",
            "commercial driver's license", "cdl", "veterans", "skilled trades", "credential",
            "reskilling", "upskilling", "school", "education", "technical education"
        ],
        "weight": 30,
    },
    "public contracting & economic development": {
        "keywords": [
            "prevailing wage", "project labor agreement", "economic development", "tax abatement",
            "public contracting", "procurement", "industrial", "supply chain", "manufacturing",
            "rail", "layoff", "closure"
        ],
        "weight": 32,
    },
    "economic security & family affordability": {
        "keywords": [
            "childcare", "healthcare", "medicaid", "paid family leave", "housing", "affordability",
            "toll", "retirement", "tax relief", "family affordability", "cost of living"
        ],
        "weight": 28,
    },
    "government accountability & reform": {
        "keywords": [
            "redistricting", "ethics", "transparency", "government accountability", "executive power",
            "local government", "anti-corruption", "railroad commission", "public accountability",
            "oversight", "state preemption"
        ],
        "weight": 24,
    },
    "labor representation in government": {
        "keywords": [
            "labor representation", "board", "commission", "advisory council", "agency rulemaking",
            "public policy", "workforce agencies", "utility regulation", "licensing"
        ],
        "weight": 26,
    },
}

DEFAULT_PRIORITY_TERMS = [
    "labor rights", "worker protections", "wages", "union", "overtime", "workers compensation",
    "state employee", "public employee", "benefits", "safety", "healthcare", "housing",
    "education", "apprenticeship", "energy", "water", "data center", "power lines",
    "infrastructure", "tax relief", "government accountability", "labor representation"
]

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def normalize_text(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", (value or "").strip()))


@st.cache_data(show_spinner=False)
def fetch_bill_report(chamber: str) -> str:
    chamber_id = "housefiled" if chamber.lower() == "house" else "senatefiled"
    url = f"https://capitol.texas.gov/Reports/Report.aspx?LegSess={TEXAS_LEG_SESSION}&ID={chamber_id}"
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_bill_entries(raw_html: str) -> List[dict]:
    raw_html = raw_html or ""
    bills = []

    entry_pattern = re.compile(
        r'\[(?P<bill_id>(?:HB|SB|HCR|HJR|HR|SJR|SR)\s*\d+)\]\s*\((?P<url>https?://capitol\.texas\.gov/BillLookup/History\.aspx\?[^)]*Bill=(?:HB|SB|HCR|HJR|HR|SJR|SR)\d+)\)\s*Author:\s*(?P<body>.*?)(?=\s*\[(?:HB|SB|HCR|HJR|HR|SJR|SR)\s*\d+\]\s*\(|\s*\Z)',
        re.IGNORECASE | re.DOTALL,
    )

    for match in entry_pattern.finditer(raw_html):
        bill_id = normalize_text(match.group("bill_id"))
        bill_url = match.group("url").strip()
        body = match.group("body")

        author_match = re.search(r"Author:\s*(.*?)(?=\s*Last Action:\s*)", body, re.IGNORECASE | re.DOTALL)
        last_action_match = re.search(r"Last Action:\s*(.*?)(?=\s*(?:Filed\s+)?Caption:\s*)", body, re.IGNORECASE | re.DOTALL)
        caption_match = re.search(r"(?:Filed\s+)?Caption:\s*(.*)", body, re.IGNORECASE | re.DOTALL)

        author = normalize_text(author_match.group(1)) if author_match else ""
        last_action = normalize_text(last_action_match.group(1)) if last_action_match else ""
        caption = normalize_text(caption_match.group(1)) if caption_match else ""

        if not bill_id or not caption:
            continue

        bills.append(
            {
                "bill_id": bill_id,
                "bill_type": bill_id.split()[0].upper(),
                "bill_number": int(re.search(r"(\d+)$", bill_id).group(1)),
                "url": bill_url,
                "author": author,
                "sponsor": "",
                "last_action": last_action,
                "caption": caption,
            }
        )

    if not bills:
        row_blocks = re.findall(r'<div class="row">(.*?)</div>\s*(?=<div class="row"|$)', raw_html, re.DOTALL)
        for row_html in row_blocks:
            bill_link_match = re.search(r'<a[^>]*>(\b(?:HB|SB|HCR|HJR|HR|SJR|SR)\s*\d+)\s*</a>', row_html, re.IGNORECASE)
            if not bill_link_match:
                continue

            bill_id = normalize_text(bill_link_match.group(1))
            author_match = re.search(r'<b>Author</b>:\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>', row_html, re.IGNORECASE | re.DOTALL)
            sponsor_match = re.search(r'<b>Sponsor</b>:\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>', row_html, re.IGNORECASE | re.DOTALL)
            last_action_match = re.search(r'<b>Last Action:</b>\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>', row_html, re.IGNORECASE | re.DOTALL)
            caption_match = re.search(r'<b>Caption</b>:\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>', row_html, re.IGNORECASE | re.DOTALL)

            author = normalize_text(re.sub(r'<.*?>', '', author_match.group(1) if author_match else '')) if author_match else ''
            sponsor = normalize_text(re.sub(r'<.*?>', '', sponsor_match.group(1) if sponsor_match else '')) if sponsor_match else ''
            last_action = normalize_text(re.sub(r'<.*?>', '', last_action_match.group(1) if last_action_match else '')) if last_action_match else ''
            caption = normalize_text(re.sub(r'<.*?>', '', caption_match.group(1) if caption_match else '')) if caption_match else ''

            if not bill_id or not caption:
                continue

            bills.append(
                {
                    "bill_id": bill_id,
                    "bill_type": bill_id.split()[0].upper(),
                    "bill_number": int(re.search(r"(\d+)$", bill_id).group(1)),
                    "url": re.search(r'href="(http[^"]+)"', row_html, re.IGNORECASE).group(1) if re.search(r'href="(http[^"]+)"', row_html, re.IGNORECASE) else "",
                    "author": author,
                    "sponsor": sponsor,
                    "last_action": last_action,
                    "caption": caption,
                }
            )

    return bills


def get_matching_categories(bill: dict, user_keywords: List[str]) -> List[str]:
    text = f"{bill['bill_id']} {bill['caption']} {bill['author']} {bill['last_action']}".lower()
    matched = []
    for category, config in POLICY_PRIORITY_MAP.items():
        if any(keyword.lower() in text for keyword in config["keywords"]):
            matched.append(category)

    for keyword in user_keywords:
        cleaned = keyword.strip().lower()
        if cleaned and cleaned in text and cleaned not in [item.lower() for item in matched]:
            matched.append(cleaned.title())

    return matched


def score_bill(bill: dict, user_keywords: List[str]) -> int:
    text = f"{bill['bill_id']} {bill['caption']} {bill['author']} {bill['last_action']}".lower()

    score = 0
    for category, config in POLICY_PRIORITY_MAP.items():
        for keyword in config["keywords"]:
            if keyword.lower() in text:
                score += config["weight"]
                break

    for keyword in user_keywords:
        cleaned = keyword.strip().lower()
        if cleaned and cleaned in text:
            score += 25

    if "effective immediately" in text or "effective on" in text:
        score += 8
    if "signed by the governor" in text or "effective" in text:
        score += 6
    if "referred to" in text or "filed" in text:
        score += 2

    return score


def filter_and_rank_bills(chamber: str, query: str, max_results: int) -> List[dict]:
    raw_html = fetch_bill_report(chamber)
    bills = extract_bill_entries(raw_html)

    search_terms = [part.strip().lower() for part in query.split(",") if part.strip()]
    if not search_terms:
        search_terms = [term.lower() for term in DEFAULT_PRIORITY_TERMS]

    filtered = []
    for bill in bills:
        bill_text = f"{bill['bill_id']} {bill['caption']} {bill['author']} {bill['sponsor']}".lower()
        matches_query = any(term in bill_text for term in search_terms)
        if matches_query:
            bill["priority_score"] = score_bill(bill, search_terms)
            bill["priority_categories"] = get_matching_categories(bill, search_terms)
            filtered.append(bill)

    if not filtered and bills:
        for bill in bills:
            bill["priority_score"] = score_bill(bill, search_terms or DEFAULT_PRIORITY_TERMS)
            bill["priority_categories"] = get_matching_categories(bill, search_terms or DEFAULT_PRIORITY_TERMS)
            filtered.append(bill)

    filtered.sort(key=lambda bill: bill["priority_score"], reverse=True)
    return filtered[:max_results]


st.title("📜 PolicyPal")
st.subheader("Texas Filed Bill Search and Priority Ranking")

with st.sidebar:
    st.markdown("### Search Filters")
    chamber = st.selectbox("Chamber", ["House", "Senate"])
    search_terms = st.text_input(
        "Priority keywords",
        value="labor rights, worker protections, wages, union, overtime, workers compensation, safety, healthcare, housing, education, apprenticeship, energy, infrastructure, tax relief, government accountability, labor representation",
        help="Enter comma-separated terms to rank bills by your policy priorities.",
    )
    max_results = st.slider("Max bills to show", min_value=5, max_value=50, value=15)
    run_search = st.button("Search and rank bills")

if run_search:
    with st.spinner(f"Fetching and ranking {chamber} bills..."):
        results = filter_and_rank_bills(chamber, search_terms, max_results)

    if not results:
        st.warning("No bills matched those keywords. Try a broader search.")
    else:
        st.markdown(f"### Top {len(results)} prioritized {chamber.lower()} bills")
        for bill in results:
            categories = bill.get("priority_categories") or ["Uncategorized"]
            categories_text = ", ".join(categories)
            st.markdown(
                f"""
                <div style="border:1px solid #ddd; border-radius:10px; padding:14px; margin-bottom:12px;">
                    <h4>{bill['bill_id']}</h4>
                    <p><strong>Priority score:</strong> {bill['priority_score']} | <strong>Priority area:</strong> {categories_text} | <strong>Last action:</strong> {bill['last_action']}</p>
                    <p><strong>Author:</strong> {bill['author']}</p>
                    <p><strong>Sponsor:</strong> {bill['sponsor'] if bill['sponsor'] else 'None listed'}</p>
                    <p>{bill['caption']}</p>
                    <p><a href="{bill['url']}" target="_blank">Open bill</a></p>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("---")
st.info(
    "This app ranks Texas bills using your policy platform priorities: labor rights, worker protections, energy/infrastructure, education/workforce, affordability, government accountability, and labor representation."
)
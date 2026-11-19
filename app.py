import csv
import html
import io
import os
import re
from datetime import date, datetime, timedelta
from typing import List, Optional

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

KEYWORD_DROPDOWN_MAP = {
    "Labor Rights & Worker Protections": [
        "right to work", "union", "collective bargaining", "workers compensation",
        "worker compensation", "state employee", "public employee", "benefits",
        "wage theft", "overtime", "unemployment", "paid leave", "whistleblower",
        "retaliation", "heat stress", "first aid", "mental health",
        "artificial intelligence", "workplace automation", "non-compete",
        "just cause", "off-duty", "privacy", "workplace safety", "employees",
        "pay raise", "worker classification", "fair scheduling",
    ],
    "Energy & Infrastructure": [
        "utility", "utility regulation", "transmission", "distribution",
        "electric grid", "grid reliability", "reliability", "nuclear",
        "nuclear waste", "geothermal", "infrastructure", "water infrastructure",
        "water", "critical infrastructure", "data center", "large load",
        "power lines", "buried power lines", "permits", "electric generation",
        "grid resilience", "restoration", "emergency utility restoration",
        "transmission development", "right of way", "gulf coast", "energy",
        "energy affordability", "electric cooperative",
    ],
    "Workforce Development & Education": [
        "apprenticeship", "career and technical education", "cte", "training",
        "workforce", "commercial driver's license", "cdl", "veterans",
        "skilled trades", "credential", "reskilling", "upskilling", "school",
        "education", "technical education",
    ],
    "Public Contracting": [
        "prevailing wage", "project labor agreement", "public contracting",
        "procurement", "supply chain", "manufacturing",
    ],
    "Economic Development": [
        "economic development", "tax abatement", "industrial", "rail",
        "layoff", "closure",
    ],
    "Economic Security": [
        "healthcare", "medicaid", "retirement", "tax relief",
        "cost of living", "toll",
    ],
    "Family Affordability": [
        "childcare", "paid family leave", "housing", "affordability",
        "family affordability",
    ],
    "Government Accountability & Reform": [
        "redistricting", "ethics", "transparency", "government accountability",
        "executive power", "local government", "anti-corruption",
        "railroad commission", "public accountability", "oversight",
        "state preemption",
    ],
    "Labor Representation in Government": [
        "labor representation", "board", "commission", "advisory council",
        "agency rulemaking", "public policy", "workforce agencies",
        "utility regulation", "licensing",
    ],
}

SPECIFIC_KEYWORD_MAP = {
    "Right to Work": "right to work",
    "Collective Bargaining": "collective bargaining",
    "Workers' Compensation": "workers compensation",
    "Unemployment Insurance": "unemployment",
    "Wage Theft": "wage theft",
    "Worker Classification": "worker classification",
    "Heat Stress": "heat stress",
    "Workplace Safety": "workplace safety",
    "Artificial Intelligence & Workplace Automation": "artificial intelligence",
    "Whistleblower Protections": "whistleblower",
    "Fair Scheduling": "fair scheduling",
    "Utility Regulation & Oversight": "utility regulation",
    "Large-Load & Data Centers": "data center",
    "Transmission & Distribution Infrastructure": "transmission",
    "Nuclear Energy": "nuclear",
    "Electric Cooperatives": "electric cooperative",
    "Energy Affordability": "energy affordability",
    "Grid Reliability": "grid reliability",
    "Nuclear Waste Management": "nuclear waste",
    "Geothermal": "geothermal",
    "Emergency Utility Restoration": "emergency utility restoration",
    "Transmission Development & Right of Way": "transmission development",
    "Water Infrastructure": "water infrastructure",
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def normalize_text(value: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", (value or "").strip()))


@st.cache_data(show_spinner=False, ttl=900)
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

    row_blocks = re.findall(
        r'<div\b[^>]*class=["\'][^"\']*\brow\b[^"\']*["\'][^>]*>(.*?)'
        r'(?=<div\b[^>]*class=["\'][^"\']*\brow\b[^"\']*["\']|</main>|</body>|\Z)',
        raw_html,
        re.IGNORECASE | re.DOTALL,
    )

    def strip_tags(value: str) -> str:
        return normalize_text(re.sub(r"<[^>]+>", " ", value or ""))

    for row_html in row_blocks:
        bill_link_match = re.search(
            r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            row_html,
            re.IGNORECASE | re.DOTALL,
        )
        if not bill_link_match:
            continue

        bill_id = normalize_text(re.sub(r"<[^>]+>", "", bill_link_match.group(2)))
        bill_id_match = re.fullmatch(
            r"(?:HB|SB|HCR|SCR|HJR|SJR|HR|SR)\s*\d+",
            bill_id,
            re.IGNORECASE,
        )
        if not bill_id_match:
            continue

        author_match = re.search(
            r'<b>Author</b>:\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>',
            row_html,
            re.IGNORECASE | re.DOTALL,
        )
        sponsor_match = re.search(
            r'<b>Sponsor</b>:\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>',
            row_html,
            re.IGNORECASE | re.DOTALL,
        )
        last_action_match = re.search(
            r'<b>Last Action:</b>\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>',
            row_html,
            re.IGNORECASE | re.DOTALL,
        )
        caption_match = re.search(
            r'<b>Caption</b>:\s*</div>\s*<div class="bill-search-result-data">(.*?)</div>',
            row_html,
            re.IGNORECASE | re.DOTALL,
        )
        bill_number = int(re.search(r"(\d+)$", bill_id).group(1))

        bills.append(
            {
                "bill_id": bill_id,
                "bill_type": bill_id.split()[0].upper(),
                "bill_number": bill_number,
                "url": html.unescape(bill_link_match.group(1)),
                "author": strip_tags(author_match.group(1) if author_match else ""),
                "sponsor": strip_tags(sponsor_match.group(1) if sponsor_match else ""),
                "last_action": strip_tags(last_action_match.group(1) if last_action_match else ""),
                "caption": strip_tags(caption_match.group(1) if caption_match else ""),
            }
        )

    if bills:
        return bills

    entry_pattern = re.compile(
        r'\[(?P<bill_id>(?:HB|SB|HCR|SCR|HJR|SJR|HR|SR)\s*\d+)\]\s*\((?P<url>https?://capitol\.texas\.gov/BillLookup/History\.aspx\?[^)]*Bill=(?:HB|SB|HCR|SCR|HJR|SJR|HR|SR)\d+)\)\s*Author:\s*(?P<body>.*?)(?=\s*\[(?:HB|SB|HCR|SCR|HJR|SJR|HR|SR)\s*\d+\]\s*\(|\s*\Z)',
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

    return bills


@st.cache_data(show_spinner=False, ttl=900)
def fetch_bill_history(url: str) -> str:
    if not url:
        return ""
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=12)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text
    except requests.RequestException:
        return ""


@st.cache_data(show_spinner=False, ttl=900)
def fetch_bill_companions(bill_id: str, leg_session: str) -> str:
    bill_token = re.sub(r"\s+", "", bill_id).upper()
    if not re.fullmatch(r"(?:HB|SB|HCR|SCR|HJR|SJR|HR|SR)\d+", bill_token):
        raise ValueError(f"Invalid Texas bill ID: {bill_id}")

    url = (
        "https://capitol.texas.gov/BillLookup/Companions.aspx"
        f"?LegSess={leg_session}&Bill={bill_token}"
    )
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=12)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def html_to_analysis_text(raw_html: str) -> str:
    text = re.sub(
        r"<(style|script)\b[^>]*>.*?</\1>",
        "",
        raw_html or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<br\b[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</(?:p|div|li|tr|table|h[1-6]|center)\s*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    lines = [normalize_text(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def extract_analysis_section(
    analysis_text: str,
    headings: List[str],
    end_headings: List[str],
    max_characters: int = 4500,
) -> str:
    def normalize_heading(value: str) -> str:
        return re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()

    lines = analysis_text.splitlines()
    normalized_lines = [normalize_heading(line) for line in lines]
    normalized_headings = {normalize_heading(heading) for heading in headings}
    start_index = next(
        (
            index
            for index, line in enumerate(normalized_lines)
            if line in normalized_headings
        ),
        None,
    )
    if start_index is None:
        return ""

    normalized_end_headings = {
        normalize_heading(heading) for heading in end_headings
    }
    end_index = next(
        (
            index
            for index in range(start_index + 1, len(lines))
            if normalized_lines[index] in normalized_end_headings
        ),
        len(lines),
    )
    section = "\n".join(lines[start_index + 1:end_index]).strip()
    if len(section) > max_characters:
        section = section[:max_characters].rsplit(" ", 1)[0].rstrip() + "…"
    return section


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_bill_analyses(bill_id: str, leg_session: str) -> List[dict]:
    bill_match = re.fullmatch(
        r"(HB|SB|HCR|SCR|HJR|SJR|HR|SR)\s*(\d+)",
        bill_id.strip(),
        re.IGNORECASE,
    )
    if not bill_match:
        raise ValueError(f"Invalid Texas bill ID: {bill_id}")

    session_token = re.sub(r"[()]", "", leg_session.strip()).upper()
    if not re.fullmatch(r"\d{2,3}R?", session_token):
        raise ValueError(f"Invalid Texas legislative session: {leg_session}")

    bill_token = f"{bill_match.group(1).upper()}{int(bill_match.group(2)):05d}"
    analyses = []
    for chamber_code, chamber_name in (("H", "House"), ("S", "Senate")):
        url = (
            "https://capitol.texas.gov/tlodocs/"
            f"{session_token}/analysis/html/{bill_token}{chamber_code}.htm"
        )
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=20)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"

        analysis_text = html_to_analysis_text(response.text)
        if "BILL ANALYSIS" not in analysis_text.upper():
            continue

        overview = extract_analysis_section(
            analysis_text,
            [
                "BACKGROUND AND PURPOSE",
                "AUTHOR'S / SPONSOR'S STATEMENT OF INTENT",
            ],
            [
                "CRIMINAL JUSTICE IMPACT",
                "RULEMAKING AUTHORITY",
                "ANALYSIS",
                "SECTION BY SECTION ANALYSIS",
            ],
        )
        if not overview:
            overview = extract_analysis_section(
                analysis_text,
                ["ANALYSIS"],
                ["ARTICLE 1", "ARTICLE I"],
            )

        details = extract_analysis_section(
            analysis_text,
            ["SECTION BY SECTION ANALYSIS", "ANALYSIS"],
            ["CRIMINAL JUSTICE IMPACT", "RULEMAKING AUTHORITY"],
        )
        title_match = re.search(
            r"<title\b[^>]*>(.*?)</title>",
            response.text,
            re.IGNORECASE | re.DOTALL,
        )
        title = normalize_text(
            re.sub(r"<[^>]+>", " ", title_match.group(1))
        ) if title_match else f"{chamber_name} bill analysis"
        if not title:
            title = f"{chamber_name} bill analysis"
        analyses.append(
            {
                "chamber": chamber_name,
                "title": title,
                "url": url,
                "overview": overview,
                "details": details,
            }
        )

    return analyses


def extract_opposite_chamber_companions(raw_html: str, chamber: str) -> List[dict]:
    section_match = re.search(
        r'<div\b[^>]*\bid=["\']pnlCompanions["\'][^>]*>(.*?)</div>',
        raw_html or "",
        re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        return []

    section = section_match.group(1)
    links = list(
        re.finditer(
            r'<a\b[^>]*href=["\'][^"\']*Bill=(?P<bill_token>(?:HB|SB|HCR|SCR|HJR|SJR|HR|SR)\d+)[^"\']*["\'][^>]*>(?P<label>.*?)</a>',
            section,
            re.IGNORECASE | re.DOTALL,
        )
    )
    companions = []
    for index, match in enumerate(links):
        bill_token = match.group("bill_token").upper()
        is_opposite_chamber = (
            bill_token.startswith("S") if chamber.lower() == "house"
            else bill_token.startswith("H")
        )
        if not is_opposite_chamber:
            continue

        bill_id = normalize_text(re.sub(r"<[^>]+>", "", match.group("label")))
        details_end = links[index + 1].start() if index + 1 < len(links) else len(section)
        details = normalize_text(
            re.sub(r"<[^>]+>", " ", section[match.end():details_end])
        )
        association_match = re.search(
            r"Degree of Association:\s*(.*?)(?=\s*(?:Author:|Last Action:|Caption:)|$)",
            details,
            re.IGNORECASE,
        )
        companions.append(
            {
                "bill_id": bill_id,
                "association": normalize_text(association_match.group(1)) if association_match else "",
                "url": (
                    "https://capitol.texas.gov/BillLookup/History.aspx"
                    f"?LegSess={TEXAS_LEG_SESSION}&Bill={bill_token}"
                ),
            }
        )

    return companions


def get_committee_and_progress(bill: dict) -> tuple:
    history_html = fetch_bill_history(bill.get("url", ""))
    plain_history = normalize_text(re.sub(r"<[^>]+>", " ", history_html))
    last_action = bill.get("last_action", "")

    committees = []
    committee_patterns = [
        r"Referred to\s+([A-Za-z0-9 '&(),.-]+?)\s*\.",
        r"Committee:\s*([A-Za-z0-9 '&(),.-]+)",
    ]
    for pattern in committee_patterns:
        for match in re.finditer(pattern, plain_history, re.IGNORECASE):
            name = normalize_text(match.group(1))
            name = re.split(r"\b(?:Chair|Chairperson|On |Actions? |Date)\b", name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            if name and name not in committees:
                committees.append(name)

    combined = f"{last_action} {plain_history}".lower()
    if "signed by the governor" in combined or "governor signed" in combined:
        progress = "Signed"
    elif "vetoed" in combined:
        progress = "Vetoed"
    elif "sent to the governor" in combined or "transmitted to governor" in combined:
        progress = "Sent to Governor"
    elif "passed senate" in combined or "s: passed" in combined:
        progress = "Passed Senate"
    elif "passed house" in combined or "h: passed" in combined:
        progress = "Passed House"
    elif "reported favorably" in combined or "committee report" in combined or "placed on calendar" in combined:
        progress = "Committee Reported"
    elif "set for hearing" in combined or "hearing" in combined or "scheduled" in combined:
        progress = "Committee Hearing"
    elif "referred to" in combined:
        progress = "Referred to Committee"
    else:
        progress = "Filed"

    return committees, progress


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


def render_bill_summary(
    bill: dict,
    categories: Optional[List[str]] = None,
    context: str = "search",
) -> None:
    categories = categories or bill.get("priority_categories", [])
    context_label = {
        "weekly": "This Week",
        "search": "Search results",
    }.get(context, context)
    with st.expander(
        f"Bill summary and impact: {bill['bill_id']} ({context_label})",
        expanded=False,
    ):
        st.markdown("**Official Texas Legislature analysis**")
        st.write(
            "Load the published House and Senate analyses for this bill. These are "
            "official explanatory documents, not a full-text AI scan, and may "
            "describe different bill versions."
        )
        bill_token = re.sub(r"\W+", "_", bill["bill_id"]).lower()
        analysis_key = f"official_bill_analyses_{bill_token}"
        if analysis_key not in st.session_state and st.button(
            "Load official analysis",
            key=f"load_official_analysis_{context}_{bill_token}",
        ):
            try:
                with st.spinner("Checking for official Texas bill analyses..."):
                    st.session_state[analysis_key] = fetch_bill_analyses(
                        bill["bill_id"], TEXAS_LEG_SESSION
                    )
            except requests.RequestException as exc:
                st.error(f"Could not load the official bill analysis: {exc}")

        if analysis_key in st.session_state:
            analyses = st.session_state[analysis_key]
            if analyses:
                for analysis in analyses:
                    st.markdown(
                        f"#### {analysis['chamber']} analysis: {analysis['title']}"
                    )
                    if analysis["overview"]:
                        st.markdown("**Overview from the official analysis**")
                        st.text(analysis["overview"])
                    elif analysis["details"]:
                        st.info(
                            "This analysis has no separate overview section; open "
                            "the section-by-section excerpt below."
                        )
                    if analysis["details"]:
                        with st.expander(
                            f"Section-by-section excerpt for {bill['bill_id']} "
                            f"({analysis['chamber']}, {context_label})",
                            expanded=False,
                        ):
                            st.text(analysis["details"])
                    st.link_button(
                        f"Open full {analysis['chamber']} analysis for "
                        f"{bill['bill_id']} ({context_label})",
                        analysis["url"],
                    )
            else:
                st.info(
                    "No official House or Senate bill analysis is available for "
                    "this bill in the session archive. PolicyPal is not generating "
                    "an impact summary from the caption alone."
                )

        st.markdown("**Bill details**")
        st.write(f"Author: {bill.get('author') or 'Not listed'}")
        if bill.get("sponsor"):
            st.write(f"Sponsor: {bill['sponsor']}")
        if bill.get("last_action"):
            st.write(f"Latest action: {bill['last_action']}")
        if bill.get("progress") and bill["progress"] != "Not checked":
            st.write(f"Progress: {bill['progress']}")
        if bill.get("committee_text") and bill["committee_text"] != "Not checked":
            st.write(f"Committee: {bill['committee_text']}")
        if categories:
            st.write(f"Matched topics: {', '.join(categories)}")
        st.caption(
            "Official analyses summarize particular committee versions; House and "
            "Senate reports can differ. Read the bill text and analysis source before "
            "drawing conclusions about its effects."
        )


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


def filter_and_rank_bills(
    chamber: str,
    query: str,
    max_results: int,
    committee_query: str = "",
    progress_query: str = "Any",
    include_all: bool = False,
    rank_results: bool = True,
    only_companion_bills: bool = False,
) -> List[dict]:
    raw_html = fetch_bill_report(chamber)
    bills = extract_bill_entries(raw_html)

    search_terms = [part.strip().lower() for part in query if part.strip()] if isinstance(query, list) else [
        part.strip().lower() for part in query.split(",") if part.strip()
    ]
    if not search_terms and not include_all:
        return []

    filtered = []
    for bill in bills:
        bill_text = f"{bill['bill_id']} {bill['caption']} {bill['author']} {bill['sponsor']}".lower()
        matches_query = not search_terms or any(term in bill_text for term in search_terms)
        if matches_query:
            companions = []
            if only_companion_bills:
                companion_html = fetch_bill_companions(
                    bill["bill_id"], TEXAS_LEG_SESSION
                )
                companions = extract_opposite_chamber_companions(
                    companion_html, chamber
                )
                if not companions:
                    continue

            needs_history = bool(committee_query.strip()) or progress_query != "Any"
            if needs_history:
                committees, progress = get_committee_and_progress(bill)
            else:
                committees, progress = [], "Not checked"
            committee_text = " | ".join(committees) if committees else (
                "Not checked" if not needs_history else "Not yet assigned"
            )

            if committee_query.strip():
                committee_query_lower = committee_query.strip().lower()
                if not any(committee_query_lower in committee.lower() for committee in committees):
                    continue
            if progress_query != "Any" and progress != progress_query:
                continue

            bill["priority_categories"] = get_matching_categories(bill, search_terms)
            bill["committees"] = committees
            bill["committee_text"] = committee_text
            bill["progress"] = progress
            bill["companion_bills"] = companions
            if rank_results:
                bill["priority_score"] = score_bill(bill, search_terms)
            filtered.append(bill)

    if rank_results:
        filtered.sort(key=lambda bill: bill["priority_score"], reverse=True)
        return filtered[:max_results]
    return filtered


def get_weekly_bill_activity(reference_date: date) -> tuple:
    week_start = reference_date - timedelta(days=reference_date.weekday())
    counts = {"House": 0, "Senate": 0}
    recent_bills = []

    for chamber in ("House", "Senate"):
        bills = extract_bill_entries(fetch_bill_report(chamber))
        for bill in bills:
            action_date_match = re.match(
                r"(\d{1,2}/\d{1,2}/\d{4})\b",
                bill.get("last_action", "").strip(),
            )
            if not action_date_match:
                continue

            action_date = datetime.strptime(
                action_date_match.group(1), "%m/%d/%Y"
            ).date()
            if not week_start <= action_date <= reference_date:
                continue

            counts[chamber] += 1
            recent_bills.append(
                {
                    **bill,
                    "chamber": chamber,
                    "action_date": action_date,
                }
            )

    recent_bills.sort(
        key=lambda bill: (bill["action_date"], bill["bill_id"]),
        reverse=True,
    )
    return week_start, counts, recent_bills


st.title("📜 PolicyPal")
st.subheader("Texas Filed Bill Search and Priority Ranking")

with st.expander("This Week", expanded=False):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    st.caption(
        f"Bill-report activity with a last-action date from "
        f"{week_start:%b %d} to {today:%b %d, %Y}. "
        "This is not a complete hearing or floor calendar."
    )

    if st.button("Refresh this week's activity", key="refresh_weekly_activity"):
        fetch_bill_report.clear()

    try:
        week_start, weekly_counts, weekly_bills = get_weekly_bill_activity(today)
    except requests.RequestException as exc:
        st.error(f"Could not load this week's filed-bill activity: {exc}")
    else:
        house_column, senate_column = st.columns(2)
        house_column.metric("House bills with action", weekly_counts["House"])
        senate_column.metric("Senate bills with action", weekly_counts["Senate"])

        if weekly_bills:
            page_size = 10
            page_count = (len(weekly_bills) + page_size - 1) // page_size
            page_key = "weekly_activity_page_index"
            page_index = min(
                st.session_state.get(page_key, 0),
                page_count - 1,
            )
            previous_column, page_column, next_column = st.columns([1, 2, 1])
            previous_clicked = previous_column.button(
                "← Previous",
                key="weekly_activity_previous",
                disabled=page_index == 0,
            )
            next_clicked = next_column.button(
                "Next →",
                key="weekly_activity_next",
                disabled=page_index == page_count - 1,
            )
            if previous_clicked:
                page_index -= 1
            elif next_clicked:
                page_index += 1
            st.session_state[page_key] = page_index

            first_item = page_index * page_size
            last_item = min(first_item + page_size, len(weekly_bills))
            page_column.markdown(
                f"**Page {page_index + 1} of {page_count}**  \n"
                f"Showing {first_item + 1}-{last_item} of {len(weekly_bills)} updates"
            )

            for bill in weekly_bills[first_item:last_item]:
                bill_column, detail_column = st.columns([1, 4])
                bill_column.link_button(
                    f"{bill['bill_id']} ({bill['chamber']})",
                    bill["url"],
                )
                detail_column.caption(
                    f"{bill['action_date']:%b %d} | {bill['last_action']}"
                )
                detail_column.write(bill["caption"])
                render_bill_summary(
                    bill,
                    get_matching_categories(bill, []),
                    context="weekly",
                )
        else:
            st.info("No filed-bill report entries show a last action this week.")

    st.markdown(
        "[Open the official Texas Legislature site for current calendars and notices.](https://capitol.texas.gov/)"
    )

with st.expander("New to the Texas Legislature? Start here", expanded=False):
    st.caption("A short guide to following a bill and understanding what happens next.")
    lesson_tabs = st.tabs(
        ["1. The basics", "2. A bill's path", "3. Read its status", "4. Member participation"]
    )

    with lesson_tabs[0]:
        st.markdown(
            """
            Texas has two chambers: the **House** and the **Senate**. A bill is a
            proposal for a new law or a change to existing law. House bills are
            labeled **HB** and Senate bills **SB**. Most bills must pass both
            chambers in the same form before they can become law.
            """
        )

    with lesson_tabs[1]:
        st.markdown(
            """
            1. A legislator files a bill.
            2. It is referred to a committee, which may hold a hearing, consider
               testimony, amend it, and vote on it.
            3. If it advances, the chamber may schedule and vote on it.
            4. The other chamber considers it and may make changes.
            5. Both chambers must agree on the same final text before it goes to
               the Governor, who may sign, veto, or allow it to become law
               without a signature.

            **A bill can stop at any point.** Being filed or receiving a hearing
            does not mean it will become law.

            If the chambers pass different versions, a conference committee may
            negotiate a final version for both chambers to approve. Most bills
            take effect September 1 after passage unless they specify another
            date; the required two-thirds vote in both chambers can allow an
            earlier effective date.
            """
        )

    with lesson_tabs[2]:
        st.markdown(
            """
            - **Filed:** The proposal has been introduced.
            - **Referred:** It has been assigned to a committee; it has not passed.
            - **Committee hearing:** The committee is considering it. Check the
              official notice for the time, location, and participation details.
            - **Reported / calendared:** It may be moving toward consideration
              by the full chamber.
            - **Passed one chamber:** It still needs action by the other chamber.

            “Last action” is the latest event shown in the bill record, not a
            prediction of what will happen next. A companion bill is related
            legislation in the other chamber; it is not necessarily identical.
            """
        )

    with lesson_tabs[3]:
        st.markdown(
            """
            1. Open the official bill record and read the bill text or analysis.
            2. Check committee notices and calendars for hearing details.
            3. Follow your local's guidance before speaking for the union or
               submitting testimony.
            4. Share verified information and direct links with fellow members.

            PolicyPal's priority score is a tool for finding relevant bills; it
            is not an endorsement or a prediction that a bill will pass.
            """
        )

    with st.form("legislature_basics_check"):
        quiz_answer = st.selectbox(
            "Quick check: A bill is referred to a committee. What does that mean?",
            [
                "Choose an answer...",
                "It has become law.",
                "It has been assigned for committee review; it still needs further action.",
                "The Governor has vetoed it.",
            ],
        )
        quiz_submitted = st.form_submit_button("Check answer")

    if quiz_submitted:
        if quiz_answer.startswith("It has been assigned"):
            st.success("Correct. Referral is an early step, not passage.")
        elif quiz_answer == "Choose an answer...":
            st.warning("Choose an answer first.")
        else:
            st.info(
                "Not quite. Referral assigns a bill to a committee for review; "
                "it does not mean the bill has passed."
            )

    st.markdown(
        "[Texas Legislature official site](https://capitol.texas.gov/) · "
        "[How a bill becomes law](https://texaspolitics.utexas.edu/archive/html/leg/features/0800_01/billtolaw.html)"
    )

with st.expander("Contact and Legislator Resources", expanded=False):
    st.markdown(
        """
        ### PolicyPal Contact
        **Angi DeFelippo**  
        IBEW LU 220  
        [Angi@ibewlu220.com](mailto:Angi@ibewlu220.com)

        ### Find a Texas Legislator
        [Find your House and Senate legislators](https://wrm.capitol.texas.gov/)  
        [Texas House member directory](https://house.texas.gov/members)  
        [Texas Senate member directory](https://senate.texas.gov/members.php)
        """
    )

with st.sidebar:
    st.markdown("### Choose your view")
    audience_view = st.radio(
        "Detail level",
        ["Member view", "Organizer view"],
        help="Member view keeps the search simple. Organizer view includes advanced filters, scores, and exports.",
    )
    chamber = st.selectbox("Chamber", ["House", "Senate"])
    if audience_view == "Member view":
        st.caption("Search by a topic, phrase, or bill number.")
        custom_keywords = st.text_input(
            "Search terms",
            value="",
            help="Enter a topic or phrase. Separate multiple terms with commas.",
        )
        selected_keywords = st.multiselect(
            "Topics",
            options=list(KEYWORD_DROPDOWN_MAP.keys()),
            help="Choose the policy areas you want to follow.",
        )
        result_view = "Priority-ranked matches"
        only_companion_bills = False
        committee_query = ""
        progress_query = "Any"
        max_results = 10
        search_button_label = "Find relevant bills"
    else:
        st.markdown("### Organizer filters")
        result_view = st.radio(
            "Results view",
            ["Priority-ranked matches", "All filed bills (unranked)"],
            help="The unranked view lists all filed bills when no keywords are entered; selected or entered keywords filter the list.",
        )
        only_companion_bills = st.checkbox(
            "Only bills with a companion in the other chamber",
            value=False,
            help="Uses the Texas Legislature's companion designations (Identical, Very Similar, Similar, or Duplicate). The Legislature notes these are an aid, not a final determination.",
        )
        custom_keywords = st.text_input(
            "Enter keyword(s)",
            value="",
            help="Enter any words or phrases to search for, separated by commas.",
        )

        dropdown_choices = list(KEYWORD_DROPDOWN_MAP.keys())
        dropdown_choices.extend(
            [
                "Right to Work", "Collective Bargaining", "Workers' Compensation",
                "Unemployment Insurance", "Wage Theft", "Worker Classification",
                "Heat Stress", "Workplace Safety",
                "Artificial Intelligence & Workplace Automation",
                "Whistleblower Protections", "Fair Scheduling",
                "Utility Regulation & Oversight", "Large-Load & Data Centers",
                "Transmission & Distribution Infrastructure", "Nuclear Energy",
                "Electric Cooperatives", "Energy Affordability", "Grid Reliability",
                "Nuclear Waste Management", "Geothermal",
                "Emergency Utility Restoration",
                "Transmission Development & Right of Way", "Water Infrastructure",
            ]
        )
        selected_keywords = st.multiselect(
            "Policy keywords",
            options=dropdown_choices,
            help="Select one or more categories or specific policy keywords.",
        )
        committee_query = st.text_input(
            "Committee",
            value="",
            help="Search by committee name, such as State Affairs or Public Education.",
        )
        progress_query = st.selectbox(
            "Legislative progress",
            [
                "Any",
                "Filed",
                "Referred to Committee",
                "Committee Hearing",
                "Committee Reported",
                "Passed House",
                "Passed Senate",
                "Sent to Governor",
                "Signed",
                "Vetoed",
            ],
        )
        max_results = (
            st.slider("Max bills to show", min_value=5, max_value=50, value=15)
            if result_view == "Priority-ranked matches"
            else 0
        )
        search_button_label = (
            "Search for companion bills"
            if only_companion_bills
            else "Search and rank bills"
            if result_view == "Priority-ranked matches"
            else "Load all filed bills"
        )

    search_terms = [
        term.strip()
        for term in custom_keywords.split(",")
        if term.strip()
    ]
    for selection in selected_keywords:
        if selection in KEYWORD_DROPDOWN_MAP:
            search_terms.extend(KEYWORD_DROPDOWN_MAP[selection])
        else:
            search_terms.append(SPECIFIC_KEYWORD_MAP.get(selection, selection))
    search_terms = list(dict.fromkeys(search_terms))

    run_search = st.button(search_button_label, type="primary")

if run_search and only_companion_bills and not search_terms:
    st.warning(
        "Enter at least one keyword to narrow the bill list before checking companion records."
    )
elif run_search:
    is_unranked = result_view == "All filed bills (unranked)"
    spinner_text = (
        f"Checking official companions for matching {chamber} bills..."
        if only_companion_bills
        else f"Fetching all filed {chamber} bills..."
        if is_unranked
        else f"Fetching and ranking {chamber} bills..."
    )
    try:
        with st.spinner(spinner_text):
            results = filter_and_rank_bills(
                chamber,
                search_terms,
                max_results,
                committee_query,
                progress_query,
                include_all=is_unranked,
                rank_results=not is_unranked,
                only_companion_bills=only_companion_bills,
            )
    except requests.RequestException as exc:
        st.error(f"Could not retrieve bill or companion information: {exc}")
        st.stop()

    if not results:
        if is_unranked:
            st.warning("No filed bills were found for that chamber and those filters.")
        else:
            st.warning("No bills matched those keywords and filters. Try a broader search.")
    elif is_unranked:
        result_description = (
            "filed bills with companions in the other chamber"
            if only_companion_bills
            else "filed bills matching filters"
            if search_terms
            else "filed bills"
        )
        st.header(
            f"{len(results)} {chamber.lower()} {result_description} (unranked)"
        )
        table_rows = [
            {
                "Bill": bill["bill_id"],
                "Author": bill["author"],
                "Sponsor": bill["sponsor"],
                "Last action": bill["last_action"],
                "Committee": bill["committee_text"],
                "Progress": bill["progress"],
                "Caption": bill["caption"],
                "Bill URL": bill["url"],
                "Companion bills": "; ".join(
                    f"{companion['bill_id']} ({companion['association']})"
                    for companion in bill["companion_bills"]
                ),
            }
            for bill in results
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        companion_rows = [
            {
                "Bill": bill["bill_id"],
                "Companion in other chamber": companion["bill_id"],
                "Association": companion["association"],
                "Open companion": companion["url"],
            }
            for bill in results
            for companion in bill["companion_bills"]
        ]
        if companion_rows:
            st.markdown("#### Companion bills in the other chamber")
            st.dataframe(
                companion_rows,
                column_config={
                    "Open companion": st.column_config.LinkColumn(
                        "Open companion", display_text="Open bill"
                    )
                },
                use_container_width=True,
                hide_index=True,
            )

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=table_rows[0].keys())
        writer.writeheader()
        writer.writerows(table_rows)
        st.download_button(
            "Download unranked bill list as CSV",
            data=csv_buffer.getvalue(),
            file_name=f"{chamber.lower()}_filed_bills_unranked.csv",
            mime="text/csv",
        )
    else:
        if audience_view == "Member view":
            st.header(f"{len(results)} {chamber.lower()} bills matching your search")
            st.caption(
                "Sorted by PolicyPal's relevance estimate, not an endorsement or "
                "prediction. Bill captions are official text and may use legal language."
            )
        else:
            result_description = (
                " with companions in the other chamber" if only_companion_bills else ""
            )
            st.header(
                f"Top {len(results)} prioritized {chamber.lower()} bills{result_description}"
            )

        for bill in results:
            categories = bill.get("priority_categories") or ["Uncategorized"]
            categories_text = ", ".join(categories)
            with st.container(border=True):
                if audience_view == "Member view":
                    st.subheader(bill["bill_id"])
                    st.caption(f"Matched topics: {categories_text}")
                    st.markdown("**Official bill caption**")
                    st.write(bill["caption"])
                    st.caption(f"Latest action: {bill['last_action']}")
                    st.link_button(
                        "Read official bill record",
                        bill["url"],
                        type="primary",
                    )
                else:
                    bill_column, score_column = st.columns([5, 1])
                    bill_column.subheader(bill["bill_id"])
                    bill_column.caption(f"Priority areas: {categories_text}")
                    score_column.metric("Priority score", bill["priority_score"])

                    st.markdown(f"**{bill['caption']}**")
                    action_column, progress_column, committee_column = st.columns(3)
                    action_column.caption(f"Last action: {bill['last_action']}")
                    progress_column.caption(f"Progress: {bill['progress']}")
                    committee_column.caption(f"Committee: {bill['committee_text']}")
                    st.caption(
                        f"Author: {bill['author']} | Sponsor: "
                        f"{bill['sponsor'] if bill['sponsor'] else 'None listed'}"
                    )
                    st.link_button(
                        "Open official bill record",
                        bill["url"],
                        type="primary",
                    )
                    if bill["companion_bills"]:
                        companion_links = " · ".join(
                            f"[{companion['bill_id']} ({companion['association']})]({companion['url']})"
                            for companion in bill["companion_bills"]
                        )
                        st.markdown(
                            f"**Companion bill(s) in the other chamber:** {companion_links}"
                        )
                render_bill_summary(bill, categories, context="search")

st.markdown("---")
st.info(
    "This app ranks Texas bills using your policy platform priorities: labor rights, worker protections, energy/infrastructure, education/workforce, affordability, government accountability, and labor representation."
)
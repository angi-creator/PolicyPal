import csv
import html
import io
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
            if rank_results:
                bill["priority_score"] = score_bill(bill, search_terms)
            filtered.append(bill)

    if rank_results:
        filtered.sort(key=lambda bill: bill["priority_score"], reverse=True)
        return filtered[:max_results]
    return filtered


st.title("📜 PolicyPal")
st.subheader("Texas Filed Bill Search and Priority Ranking")

with st.expander("How Bills Become Law in Texas", expanded=False):
    st.markdown(
        """
        1. **Filing:** A legislator files a bill in the House or Senate.
           Bills are assigned a number, such as HB 1 or SB 10.
        2. **Committee referral:** The presiding officer assigns the bill to a
           committee that studies policy related to the proposal.
        3. **Committee action:** The committee may schedule a hearing, take
           public testimony, amend the bill, leave it pending, or report it
           favorably to the chamber.
        4. **Calendaring:** If reported favorably, the bill is placed on a
           legislative calendar for consideration by the full chamber.
        5. **Chamber vote:** The bill must receive approval in the chamber
           where it began. In Texas, bills normally receive three readings
           and recorded votes.
        6. **Other chamber:** The bill then moves to the second chamber, where
           it may receive hearings, amendments, and a vote.
        7. **Conference committee:** If the House and Senate pass different
           versions, conference committee members may negotiate a final
           compromise version.
        8. **Final approval:** The House and Senate must agree to the exact
           same final bill before it is sent to the governor.
        9. **Governor:** The governor may sign the bill, allow it to become law
           without signing, or veto it. Legislators may attempt to override a
           veto during the allowed legislative process.
        10. **Effective date:** Bills generally take effect September 1 after
            they are passed, unless the bill specifies another effective date.
            Bills that receive the required two-thirds vote in both chambers
            may take effect immediately.

        [The Texas Politics Project](https://texaspolitics.utexas.edu/archive/html/leg/features/0800_01/billtolaw.html)
        [Texas Legislature: 89th Legislature Page](https://capitol.texas.gov/)
        """
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
    st.markdown("### Search Filters")
    chamber = st.selectbox("Chamber", ["House", "Senate"])
    result_view = st.radio(
        "Results view",
        ["Priority-ranked matches", "All filed bills (unranked)"],
        help="The unranked view lists all filed bills when no keywords are entered; selected or entered keywords filter the list.",
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

    if result_view == "Priority-ranked matches":
        max_results = st.slider("Max bills to show", min_value=5, max_value=50, value=15)
    else:
        max_results = 0
    run_search = st.button(
        "Search and rank bills" if result_view == "Priority-ranked matches" else "Load all filed bills"
    )

if run_search:
    is_unranked = result_view == "All filed bills (unranked)"
    with st.spinner(
        f"Fetching all filed {chamber} bills..." if is_unranked else f"Fetching and ranking {chamber} bills..."
    ):
        results = filter_and_rank_bills(
            chamber,
            search_terms,
            max_results,
            committee_query,
            progress_query,
            include_all=is_unranked,
            rank_results=not is_unranked,
        )

    if not results:
        if is_unranked:
            st.warning("No filed bills were found for that chamber and those filters.")
        else:
            st.warning("No bills matched those keywords. Try a broader search.")
    elif is_unranked:
        result_description = "filed bills matching filters" if search_terms else "filed bills"
        st.markdown(f"### {len(results)} {chamber.lower()} {result_description} (unranked)")
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
            }
            for bill in results
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

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
        st.markdown(f"### Top {len(results)} prioritized {chamber.lower()} bills")
        for bill in results:
            categories = bill.get("priority_categories") or ["Uncategorized"]
            categories_text = ", ".join(categories)
            st.markdown(
                f"""
                <div style="border:1px solid #ddd; border-radius:10px; padding:14px; margin-bottom:12px;">
                    <h4>{bill['bill_id']}</h4>
                    <p><strong>Priority score:</strong> {bill['priority_score']} | <strong>Priority area:</strong> {categories_text} | <strong>Last action:</strong> {bill['last_action']}</p>
                    <p><strong>Legislative progress:</strong> {bill['progress']} | <strong>Committee:</strong> {bill['committee_text']}</p>
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
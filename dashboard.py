#!/usr/bin/env python3
"""
Startup Job Tracker — Streamlit dashboard.
Run with: streamlit run dashboard.py
"""

import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta

from db.models import init_db
from db import queries

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Startup Job Tracker",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ── Sidebar nav ───────────────────────────────────────────────────────────────
PAGES = ["Overview", "Companies", "Job Feed", "Trends"]
page = st.sidebar.radio("Navigate", PAGES)
st.sidebar.markdown("---")
st.sidebar.caption("Run `python tracker.py` to refresh data.")

# ─────────────────────────────────────────────────────────────────────────────
# OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────
if page == "Overview":
    st.title("Startup Job Tracker")

    stats = queries.get_overview_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("Companies Tracked", stats["total_companies"])
    col2.metric("Active Job Postings", stats["total_active_jobs"])
    last_run = stats["last_run"] or "Never"
    col3.metric("Last Scrape", last_run[:16] if last_run != "Never" else last_run)

    st.markdown("---")

    # Sector breakdown bar chart
    sector_data = queries.get_sector_breakdown()
    if sector_data:
        df = pd.DataFrame(sector_data)
        st.subheader("Active Jobs by Sector")
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("job_count:Q", title="Active Jobs"),
                y=alt.Y("sector:N", sort="-x", title="Sector"),
                color=alt.Color("sector:N", legend=None),
                tooltip=["sector", "job_count"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No data yet. Run `python tracker.py` to scrape jobs.")

    # Jobs by department category
    dept_data = queries.get_department_breakdown()
    if dept_data:
        st.markdown("---")
        st.subheader("Jobs by Department")
        df_dept = pd.DataFrame(dept_data)
        chart_dept = (
            alt.Chart(df_dept)
            .mark_bar()
            .encode(
                x=alt.X("job_count:Q", title="Active Jobs"),
                y=alt.Y("category:N", sort="-x", title=""),
                color=alt.Color("category:N", legend=None),
                tooltip=["category", "job_count"],
            )
            .properties(height=400)
        )
        st.altair_chart(chart_dept, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# COMPANIES
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Companies":
    st.title("Companies")

    company_stats = queries.get_company_stats()
    if not company_stats:
        st.info("No companies loaded yet. Run `python tracker.py`.")
        st.stop()

    df = pd.DataFrame(company_stats)
    df = df.rename(columns={
        "name": "Company",
        "sector": "Sector",
        "funding_round": "Round",
        "funding_amount_m": "Raised ($M)",
        "funding_date": "Funded",
        "active_jobs": "Active Jobs",
        "last_scraped": "Last Scraped",
    })

    # Filters
    col1, col2 = st.columns(2)
    sectors = sorted(df["Sector"].dropna().unique())
    rounds  = sorted(df["Round"].dropna().unique())
    selected_sectors = col1.multiselect("Sector", sectors, default=sectors)
    selected_rounds  = col2.multiselect("Funding round", rounds, default=rounds)
    df = df[df["Sector"].isin(selected_sectors) & df["Round"].isin(selected_rounds)]

    display_cols = ["Company", "Sector", "Round", "Raised ($M)", "Funded", "Active Jobs", "Last Scraped"]
    st.dataframe(
        df[display_cols].sort_values("Active Jobs", ascending=False).reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# JOB FEED
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Job Feed":
    st.title("Job Feed")

    companies = queries.get_all_companies()
    filter_opts = queries.get_filter_options()

    company_options = {"All": None}
    company_options.update({c["name"]: c["id"] for c in companies})
    sectors = sorted({c["sector"] for c in companies if c.get("sector")})

    # ── Row 1: company / sector / search ──────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 3])
    selected_company = col1.selectbox("Company", list(company_options.keys()))
    selected_sector  = col2.selectbox("Sector", ["All"] + sectors)
    search           = col3.text_input("Search title / dept / location", "")

    # ── Row 2: date range / employment type ───────────────────────────────────
    col4, col5, col6 = st.columns([2, 2, 3])
    today      = date.today()
    tomorrow   = today + timedelta(days=1)
    date_from  = col4.date_input("First seen from", value=today - timedelta(days=365))
    date_to    = col5.date_input("First seen to",   value=tomorrow)
    emp_types  = ["All"] + filter_opts["employment_types"]
    selected_type = col6.selectbox("Employment type", emp_types)

    # ── Row 3: exclusion filter ──────────────────────────────────────────────
    all_company_names = sorted([c["name"] for c in companies])
    excluded_names = st.multiselect("Exclude companies", all_company_names)
    excluded_ids = [c["id"] for c in companies if c["name"] in excluded_names] or None

    jobs = queries.get_active_jobs(
        company_id=company_options[selected_company],
        exclude_company_ids=excluded_ids,
        sector=None if selected_sector == "All" else selected_sector,
        search=search or None,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        employment_type=None if selected_type == "All" else selected_type,
    )

    st.caption(f"{len(jobs)} postings match")

    if jobs:
        df = pd.DataFrame(jobs)

        # Clean up dates to just show the date portion
        df["first_seen_at"] = pd.to_datetime(df["first_seen_at"]).dt.date

        # Build display dataframe with URL as its own column for LinkColumn
        display = df[[
            "title", "company_name", "sector", "department",
            "location", "employment_type", "first_seen_at", "url"
        ]].rename(columns={
            "title":           "Title",
            "company_name":    "Company",
            "sector":          "Sector",
            "department":      "Department",
            "location":        "Location",
            "employment_type": "Type",
            "first_seen_at":   "First Seen",
            "url":             "Link",
        })

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Link": st.column_config.LinkColumn(
                    "Link",
                    display_text="View",
                    help="Open job posting",
                ),
                "First Seen": st.column_config.DateColumn("First Seen", format="MMM D, YYYY"),
                "Title": st.column_config.TextColumn("Title", width="large"),
            },
        )
    else:
        st.info("No jobs match your filters.")

# ─────────────────────────────────────────────────────────────────────────────
# TRENDS
# ─────────────────────────────────────────────────────────────────────────────
elif page == "Trends":
    st.title("Hiring Trends")

    trend_data = queries.get_job_count_over_time()
    if not trend_data:
        st.info("No trend data yet. Run `python tracker.py` at least once.")
        st.stop()

    df = pd.DataFrame(trend_data)
    df["date"] = pd.to_datetime(df["date"])

    # Company filter
    companies_list = sorted(df["company"].unique())
    selected_companies = st.multiselect(
        "Companies", companies_list, default=companies_list[:8]
    )
    filtered = df[df["company"].isin(selected_companies)]

    st.subheader("Job Count Over Time")
    line = (
        alt.Chart(filtered)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("job_count:Q", title="Active Jobs"),
            color=alt.Color("company:N", title="Company"),
            tooltip=["date:T", "company", "job_count"],
        )
        .properties(height=350)
    )
    st.altair_chart(line, use_container_width=True)

    st.markdown("---")
    st.subheader("Jobs by Sector Over Time")
    sector_df = (
        df[df["company"].isin(selected_companies)]
        .groupby(["date", "sector"], as_index=False)["job_count"]
        .sum()
    )
    area = (
        alt.Chart(sector_df)
        .mark_area()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("job_count:Q", title="Jobs", stack="normalize"),
            color=alt.Color("sector:N", title="Sector"),
            tooltip=["date:T", "sector", "job_count"],
        )
        .properties(height=300)
    )
    st.altair_chart(area, use_container_width=True)

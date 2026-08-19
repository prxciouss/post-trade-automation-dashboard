#Post Trade Automation Dashboard - Streamlit App ############################################################################################################################################################

# ABOUT: This is the interactive dashboard. It reads the reports exported by
# post_trade_automation.py, lets the user filter the trade book by 4 dimensions
# (asset class, status, side, client), and then recalculates the KPIs, exposure
# measures and charts live on whatever subset of trades is currently selected.
#
# Colour choices below come from a pre-validated, colourblind-safe palette (not
# picked by eye) - see the comments next to each chart for which "job" each colour
# is doing (categorical = identity, sequential/ordinal = magnitude, status = state).

#Libraries ############################################################################################################################################################
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Post Trade Automation Dashboard",
    layout="wide",
)

#Colour palette (fixed, validated - see dataviz reference palette) ############################################################################################################################################################
CATEGORICAL_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7"]
    # blue, orange, aqua, yellow, magenta, violet - fixed order, never reshuffled per filter

STATUS_COLOURS = {
    # status = "state" of a trade, so this uses the status palette (never reused
    # for anything else), not the categorical one
    "Executed": "#8a8a86",             # neutral grey - just started, no risk signal yet
    "Validated": "#ec835a",            # serious
    "Pending Settlement": "#fab219",   # warning
    "Settled": "#0ca30c",              # good
    "Failed": "#d03b3b",               # critical
}

EXPOSURE_COLOURS = {
    "Total Notional": "#2a78d6",        # informational, not a risk state
    "Outstanding Notional": "#fab219",  # warning - still live
    "Failed Notional": "#d03b3b",       # critical
    "Overdue Notional": "#ec835a",      # serious
}

# Ordinal ramp (single hue, stepped by stage) for the lifecycle funnel - lightest
# for the earliest stage, darkest for the latest, matching the funnel's narrowing
FUNNEL_STAGE_COLOURS = {
    "Executed": "#86b6ef",
    "Validated": "#5598e7",
    "Pending Settlement": "#2a78d6",
    "Settled": "#184f95",
}

#Header ############################################################################################################################################################
st.title("Post-Trade Automation Dashboard")

st.write("""
This dashboard automates post-trade monitoring: it validates trade data, tracks
trades through a 5-stage lifecycle, calculates value-based exposure alongside
operational KPIs, and generates an AI-powered operational summary. Prices are
sourced from real historical market data (see `fetch_market_data.py`).
""")

#Load reports ############################################################################################################################################################
clean_df = pd.read_csv(
    "Reports/CSV/clean_trades.csv",
    parse_dates=["trade_date", "settlement_date"],
)
validation_report_df = pd.read_csv("Reports/CSV/validation_report.csv")
settlement_summary_df = pd.read_csv("Reports/CSV/settlement_summary.csv")
lifecycle_df = pd.read_csv("Data/lifecycle_events.csv", parse_dates=["timestamp"])

with open("Reports/operational_summary.txt", "r") as file:
    operational_summary = file.read()

#Sidebar filters (4 in total) ############################################################################################################################################################
st.sidebar.header("Filters")

selected_asset_classes = st.sidebar.multiselect(
    "Asset Class",
    options=sorted(clean_df["asset_class"].unique()),
    default=sorted(clean_df["asset_class"].unique()),
)

selected_statuses = st.sidebar.multiselect(
    "Status",
    options=sorted(clean_df["status"].unique()),
    default=sorted(clean_df["status"].unique()),
)

selected_sides = st.sidebar.multiselect(
    "Side",
    options=sorted(clean_df["side"].unique()),
    default=sorted(clean_df["side"].unique()),
)

selected_clients = st.sidebar.multiselect(
    "Client",
    options=sorted(clean_df["client_name"].unique()),
    default=sorted(clean_df["client_name"].unique()),
)

# Apply all 4 filters at once with boolean masking + .isin()
filtered_df = clean_df[
    clean_df["asset_class"].isin(selected_asset_classes) &
    clean_df["status"].isin(selected_statuses) &
    clean_df["side"].isin(selected_sides) &
    clean_df["client_name"].isin(selected_clients)
]

st.sidebar.write(f"Showing **{len(filtered_df)}** of **{len(clean_df)}** trades")

# Everything below recalculates live from filtered_df, so the numbers/charts
# always reflect whatever the 4 filters currently select.

#Count-based KPIs (recalculated on the filtered selection) ############################################################################################################################################################
IN_FLIGHT_STATUSES = ["Executed", "Validated", "Pending Settlement"]
today = pd.Timestamp.today().normalize()

if len(filtered_df) > 0:
    settled_count = len(filtered_df[filtered_df["status"] == "Settled"])
    failed_count = len(filtered_df[filtered_df["status"] == "Failed"])
    overdue_df = filtered_df[
        (filtered_df["settlement_date"] < today) &
        (filtered_df["status"].isin(IN_FLIGHT_STATUSES))
    ]
    overdue_count = len(overdue_df)

    high_priority_df = filtered_df[filtered_df["priority"] == "High"]
    high_priority_failed_df = high_priority_df[high_priority_df["status"] == "Failed"]

    completion_rate = settled_count / len(filtered_df) * 100
    failure_rate = failed_count / len(filtered_df) * 100
    overdue_rate = overdue_count / len(filtered_df) * 100
    high_priority_failure_rate = (
        len(high_priority_failed_df) / len(high_priority_df) * 100
        if len(high_priority_df) > 0 else 0
    )
else:
    completion_rate = failure_rate = overdue_rate = high_priority_failure_rate = 0
    overdue_df = filtered_df

st.subheader("KPI Summary")
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
kpi_col1.metric("Completion Rate", f"{completion_rate:.1f}%")
kpi_col2.metric("Failure Rate", f"{failure_rate:.1f}%")
kpi_col3.metric("Overdue Rate", f"{overdue_rate:.1f}%")
kpi_col4.metric("High Priority Failure Rate", f"{high_priority_failure_rate:.1f}%")

#Value-based exposure measures (4 in total, recalculated on the filtered selection) ############################################################################################################################################################
total_notional = filtered_df["notional"].sum()
outstanding_notional = filtered_df[filtered_df["status"].isin(IN_FLIGHT_STATUSES)]["notional"].sum()
failed_notional = filtered_df[filtered_df["status"] == "Failed"]["notional"].sum()
overdue_notional = overdue_df["notional"].sum()

st.subheader("Exposure Summary (value-based)")
exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
exp_col1.metric("Total Notional", f"${total_notional:,.0f}")
exp_col2.metric("Outstanding Notional", f"${outstanding_notional:,.0f}")
exp_col3.metric("Failed Notional", f"${failed_notional:,.0f}")
exp_col4.metric("Overdue Notional", f"${overdue_notional:,.0f}")

exposure_bar_df = pd.DataFrame([
    {"Measure": "Total Notional", "Notional": total_notional},
    {"Measure": "Outstanding Notional", "Notional": outstanding_notional},
    {"Measure": "Failed Notional", "Notional": failed_notional},
    {"Measure": "Overdue Notional", "Notional": overdue_notional},
])

exposure_fig = px.bar(
    exposure_bar_df,
    x="Measure",
    y="Notional",
    title="Exposure by Measure",
    color="Measure",
    color_discrete_map=EXPOSURE_COLOURS,
    text_auto=".2s",
        # direct labels on the bars themselves, so values are readable without a legend
)
exposure_fig.update_layout(showlegend=False, template="plotly_white")
    # one categorical axis already names each bar, so a legend would just repeat it
st.plotly_chart(exposure_fig, use_container_width=True)

st.caption(
    f"Average time-to-settlement (full book): "
    f"{settlement_summary_df.iloc[0]['Value']} hours, "
    f"based on {settlement_summary_df.iloc[0]['Trades Measured']} settled trades."
)

#Lifecycle funnel chart ############################################################################################################################################################
st.subheader("Trade Lifecycle Funnel")

filtered_trade_ids = set(filtered_df["trade_id"])
filtered_lifecycle_df = lifecycle_df[lifecycle_df["trade_id"].isin(filtered_trade_ids)]

LIFECYCLE_STAGES = ["Executed", "Validated", "Pending Settlement", "Settled"]
    # the 4 "happy path" stages a trade can progress through in order

stage_counts = [
    filtered_lifecycle_df[filtered_lifecycle_df["stage"] == stage]["trade_id"].nunique()
    for stage in LIFECYCLE_STAGES
]

funnel_fig = go.Figure(go.Funnel(
    y=LIFECYCLE_STAGES,
    x=stage_counts,
    marker={"color": [FUNNEL_STAGE_COLOURS[stage] for stage in LIFECYCLE_STAGES]},
    textinfo="value+percent initial",
))
funnel_fig.update_layout(title="Trades Reaching Each Lifecycle Stage", template="plotly_white")
st.plotly_chart(funnel_fig, use_container_width=True)

failed_in_filter = len(filtered_df[filtered_df["status"] == "Failed"])
st.caption(
    f"{failed_in_filter} trade(s) in the current selection exited the pipeline as "
    f"Failed rather than reaching Settled (not shown on the funnel above, since a "
    f"funnel represents the successful/happy path)."
)

#Buy / Sell breakdown ############################################################################################################################################################
st.subheader("Buy / Sell Breakdown")

side_summary_df = (
    filtered_df.groupby("side")
    .agg(trade_count=("trade_id", "count"), total_notional=("notional", "sum"))
    .reset_index()
)

side_col1, side_col2 = st.columns(2)

with side_col1:
    count_fig = px.bar(
        side_summary_df, x="side", y="trade_count", color="side",
        color_discrete_sequence=CATEGORICAL_COLOURS,
        title="Trade Count by Side", text_auto=True,
    )
    count_fig.update_layout(showlegend=False, template="plotly_white")
    st.plotly_chart(count_fig, use_container_width=True)

with side_col2:
    notional_fig = px.bar(
        side_summary_df, x="side", y="total_notional", color="side",
        color_discrete_sequence=CATEGORICAL_COLOURS,
        title="Notional by Side", text_auto=".2s",
    )
    notional_fig.update_layout(showlegend=False, template="plotly_white")
    st.plotly_chart(notional_fig, use_container_width=True)

#Top clients by exposure ############################################################################################################################################################
st.subheader("Top Clients by Exposure")

top_clients_df = (
    filtered_df.groupby("client_name")["notional"]
    .sum()
    .sort_values(ascending=False)
    .head(8)
    .reset_index()
)

top_clients_fig = px.bar(
    top_clients_df,
    x="notional",
    y="client_name",
    orientation="h",
    title="Top 8 Clients by Total Notional",
        # single series -> ONE colour for every bar (bar length carries the ranking,
        # not colour - a different hue per bar would wrongly imply separate categories)
    color_discrete_sequence=[CATEGORICAL_COLOURS[0]],
)
top_clients_fig.update_layout(
    yaxis={"categoryorder": "total ascending"},
    template="plotly_white",
)
st.plotly_chart(top_clients_fig, use_container_width=True)

#Status distribution (asset class breakdown, for context) ############################################################################################################################################################
st.subheader("Asset Class Breakdown")

asset_class_fig = px.pie(
    filtered_df,
    names="asset_class",
    title="Trades by Asset Class",
    color="asset_class",
    color_discrete_sequence=CATEGORICAL_COLOURS,
)
asset_class_fig.update_traces(textinfo="percent+label")
st.plotly_chart(asset_class_fig, use_container_width=True)

#Validation report (filtered to the current selection) ############################################################################################################################################################
st.subheader("Validation Report")

filtered_validation_df = validation_report_df[
    validation_report_df["trade_id"].isin(filtered_trade_ids)
]
st.dataframe(filtered_validation_df, use_container_width=True)

#Clean trades table ############################################################################################################################################################
st.subheader("Trades")
st.dataframe(filtered_df, use_container_width=True)

#AI operational summary ############################################################################################################################################################
st.subheader("AI Operational Summary")
st.caption("Generated by Llama 3.2 (via Ollama) from the full trade book, not the filtered selection above.")
st.write(operational_summary)

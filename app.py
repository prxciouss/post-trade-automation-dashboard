import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Post Trade Automation Dashboard",
    layout="wide"
)

st.title("Post-Trade Automation Dashboard")

st.write("""
This dashboard automates post-trade monitoring by 
validating trade data, identifying operational issues, 
calculating KPIs and generating AI-powered operational summaries.
""")

kpi_summary_df = pd.read_csv("Reports/CSV/kpi_summary.csv")
validation_report_df = pd.read_csv("Reports/CSV/validation_report.csv")
clean_df = pd.read_csv("Reports/CSV/clean_trades.csv")

st.subheader("KPI Summary")

col1, col2 = st.columns(2)

with col1:
    st.metric("Completion Rate", f"{kpi_summary_df.iloc[0]['Value']}%")
    st.metric("Overdue Rate", f"{kpi_summary_df.iloc[2]['Value']}%")

with col2:
    st.metric("Failure Rate", f"{kpi_summary_df.iloc[1]['Value']}%")
    st.metric("High Priority Failure Rate", f"{kpi_summary_df.iloc[3]['Value']}%")

status_counts = clean_df["status"].value_counts()

status_counts = clean_df["status"].value_counts()

fig = px.pie(
    values=status_counts.values,
    names=status_counts.index,
    title="Trade Status Distribution",
    color=status_counts.index,
    color_discrete_map={
        "Completed": "#2E86DE",
        "Failed": "#E74C3C",
        "Pending": "#F39C12"
    }
)

st.plotly_chart(fig, use_container_width=True)

st.subheader("Validation Report")
st.dataframe(validation_report_df, use_container_width=True)

st.subheader("Clean Trades")
st.dataframe(clean_df, use_container_width=True)

st.subheader("AI Operational Summary")

with open("Reports/operational_summary.txt", "r") as file:
    operational_summary = file.read()

st.write(operational_summary)
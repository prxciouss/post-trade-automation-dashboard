import streamlit as st
import pandas as pd

st.title("Post Trade Automation Dashboard")

kpi_summary_df = pd.read_csv("kpi_summary.csv")
validation_report_df = pd.read_csv("validation_report.csv")
clean_df = pd.read_csv("clean_trades.csv")

st.subheader("KPI Summary")

col1, col2 = st.columns(2)

with col1:
    st.metric("Completion Rate", f"{kpi_summary_df.iloc[0]['Value']}%")
    st.metric("Overdue Rate", f"{kpi_summary_df.iloc[2]['Value']}%")

with col2:
    st.metric("Failure Rate", f"{kpi_summary_df.iloc[1]['Value']}%")
    st.metric("High Priority Failure Rate", f"{kpi_summary_df.iloc[3]['Value']}%")

st.subheader("Validation Report")
st.dataframe(validation_report_df, use_container_width=True)

st.subheader("Clean Trades")
st.dataframe(clean_df, use_container_width=True)
#Post Trade Automation Dashboard

# ABOUT : The application will process trade and workflow data from spreadsheets, automatically identify operational issues, 
    #generate KPI summaries, and present insights through an interactive dashboard.

# WHAT THE APP WILL DO / BUILD STAGES:
# 1 XD. Load data - read simulated Post Trade data from a CSV/Excel file into the application.
# 2 XD. Inspect data - check the dataset structure, including columns, row count, and sample records.
# 3 XD. Clean data - standardise text formatting, remove extra spaces, fix capitalisation, and convert dates.
# 4 XD. Validate data - identify operational issues such as missing owners, duplicate trade IDs, failed trades, and overdue settlements.
# 5 XD. Analyse data - filter the data to find key groups such as failed, pending, high-priority, and unresolved trades.
# 6 XD. Generate KPIs (Key Performance Indicator) - calculate summary metrics such as total trades, failure rates, completion rates, overdue items, and issue frequency.
# 7 XD. Build dashboard - display KPIs, charts, tables, warnings, and trends in an interactive Streamlit dashboard.
# 8 XD. Export reports - generate cleaned datasets, validation reports, and KPI summaries as downloadable Excel files.
# 9 XD. Generate AI summaries - produce plain-English operational summaries highlighting key risks, trends, and recommended actions.

# Libraries expected to be used in this project:  
    #Pandas -> handles spreadsheets/data tables
    #Streamlit -> turns Python scripts into web apps/dashboards
    #Plotly ->  makes charts and graphs
    #OpenPyXL ->  reads/writes Excel files 

#Libraries ############################################################################################################################################################
import pandas as pd
from ollama import chat
    # nicknames panda -> pd

#Functions ######################################################################################
        #f" is an f string, formatted string = now you can put variables directly inside the text using:{}
def print_validation_check(title, dataframe):
    count = len(dataframe)

    print(f"\nNumber of {title}:", count)

    if count > 0:
        print(f"{title}:")
        print(dataframe)

#Load raw data ############################################################################################################################################################
raw_df = pd.read_csv("Data/sample_trades.csv")
    #df = dataframe

# Create a cleaned copy of the raw data to clean, so raw df is traceable 
clean_df = raw_df.copy()

# Clean data - spelling, capitlisation and duplicates
clean_df["client_name"] = clean_df["client_name"].str.strip()
clean_df["status"] = clean_df["status"].str.strip().str.title()
clean_df["priority"] = clean_df["priority"].str.strip().str.title()
clean_df["issue_type"] = clean_df["issue_type"].str.strip()
clean_df["owner"] = clean_df["owner"].str.strip()
    #.str.strip() = removes spaces
    #str.title() = standardises capitalisation
    #otherwise FAILED == Failed -> false
duplicate_trades = clean_df[clean_df["trade_id"].duplicated()]
number_of_duplicate_trades = len(duplicate_trades)
clean_df = clean_df.drop_duplicates(subset="trade_id")
    #.drop.duplicates, .strip etc are called methods

# Convert settlement dates
clean_df["settlement_date"] = pd.to_datetime(clean_df["settlement_date"])

#Inspect Data ############################################################################################################################################################

raw_total_trades = len(raw_df)
    #may contain duplicates

print("CSV column names :")
print(clean_df.columns)
    #.columns shows column names and type of column name list (str)
print("\nThe first 5 rows of clean df trades are:")
print(clean_df.head())
    #.head() = first 5 rows. otherwise it shows everyrow and can make the terminal too long
#print(clean_df.dtypes)

# Validation checks ############################################################################################################################################################

#Duplicate Trades 
#duplicate_trades = clean_df[clean_df["trade_id"].duplicated()]
#number_of_duplicate_trades = len(duplicate_trades)
print_validation_check("Duplicate trades",
                       duplicate_trades)

#Missing owners 
missing_owners = clean_df[clean_df["owner"].isna()]
#     #.isna = Check whether values are missing
number_of_missing_owners = len(missing_owners)
print_validation_check("Missing owners",
                       missing_owners)

#Missing settlement dates
missing_settlement_dates = clean_df[clean_df["settlement_date"].isna()]
number_of_missing_settlement_dates = len(missing_settlement_dates)
print_validation_check("Missing settlement dates",
                       missing_settlement_dates)

#Pending trades 
pending_trades = clean_df[clean_df["status"] == "Pending"]
number_of_pending_trades = len(pending_trades)  
print_validation_check("Pending trades",
                       pending_trades) 

#Completed trades
completed_trades = clean_df[clean_df["status"] == "Completed"]

#Overdue trades
today = pd.Timestamp.today().normalize()
overdue_trades = clean_df[
    (clean_df["settlement_date"] < today) & # < is an inequality
    (clean_df["status"] != "Completed")
]
number_of_overdue_trades = len(overdue_trades)
print_validation_check("Overdue trades",
                       overdue_trades)

#Failed trades 
failed_trades = clean_df[clean_df["status"] == "Failed"]
    #dataframe such that status equals Failed
number_of_failed_trades = len(failed_trades)
print_validation_check("Failed trades",
                       failed_trades)

#High pritority trades 
high_priority_trades = clean_df[clean_df["priority"] == "High"]
number_of_high_priority_trades = len(high_priority_trades)

#High priority failed trades
high_priority_failed_trades = clean_df[
    (clean_df["priority"] == "High") & 
    (clean_df["status"] == "Failed")
]
    #linebreak is useful for stacking many conditions
number_of_high_priority_failed_trades = len(high_priority_failed_trades) 
print_validation_check("High priority failed trades",
                       high_priority_failed_trades)

#Validation report ###########################################################################################################################################################
validation_issues = []

# Missing owners
for _, row in missing_owners.iterrows():
    validation_issues.append({
        "trade_id": row["trade_id"],
        "issue": "Missing Owner",
        "severity": "Medium",
        "reason": "No individual has been assigned responsibility for investigating or resolving the trade."
    })

# Missing settlement dates
for _, row in missing_settlement_dates.iterrows():
    validation_issues.append({
        "trade_id": row["trade_id"],
        "issue": "Missing Settlement Date",
        "severity": "High",
        "reason": "The system cannot determine when the trade is due to settle."
    })

# Duplicate trades
for _, row in duplicate_trades.iterrows():
    validation_issues.append({
        "trade_id": row["trade_id"],
        "issue": "Duplicate Trade ID",
        "severity": "High",
        "reason": "Duplicate records may result in incorrect reporting or processing."
    })

# Failed trades
for _, row in failed_trades.iterrows():
    validation_issues.append({
        "trade_id": row["trade_id"],
        "issue": "Failed Trade",
        "severity": "High",
        "reason": "The trade has not completed successfully and requires investigation."
    })

# Overdue trades
for _, row in overdue_trades.iterrows():
    validation_issues.append({
        "trade_id": row["trade_id"],
        "issue": "Overdue Trade",
        "severity": "High",
        "reason": "The settlement date has passed and the trade remains unresolved."
    })

# High priority failed trades
for _, row in high_priority_failed_trades.iterrows():
    validation_issues.append({
        "trade_id": row["trade_id"],
        "issue": "High Priority Failed Trade",
        "severity": "Critical",
        "reason": "A high-priority trade has failed and requires immediate attention."
    })

#Exporting Validation report
validation_report_df = pd.DataFrame(validation_issues)

print("\nVALIDATION REPORT \nNumber of issues:", len(validation_report_df))
print(validation_report_df)

validation_report_df.to_csv(
    "validation_report.csv",
    index=False
)

print("\nValidation report exported successfully.")

#Introducing KPI Summary ############################################################################################################################################################
clean_total_trades = (
    raw_total_trades -
    number_of_duplicate_trades
)

# KPI calculations
completed_trades_count = len(completed_trades)

completion_rate = (completed_trades_count / clean_total_trades) * 100
failure_rate = (number_of_failed_trades / clean_total_trades) * 100
overdue_rate = (number_of_overdue_trades / clean_total_trades) * 100
if number_of_high_priority_trades > 0:
    high_priority_failure_rate = (
        number_of_high_priority_failed_trades / number_of_high_priority_trades
    ) * 100
else:
    high_priority_failure_rate = 0

kpi_summary_df = pd.DataFrame([
    {
        "KPI": "Completion Rate",
        "Value": round(completion_rate, 2)
    },
    {
        "KPI": "Failure Rate",
        "Value": round(failure_rate, 2)
    },
    {
        "KPI": "Overdue Rate",
        "Value": round(overdue_rate, 2)
    },
    {
        "KPI": "High Priority Failure Rate",
        "Value": round(high_priority_failure_rate, 2)
    }
])

print("\nKPI DATAFRAME")
print(kpi_summary_df)

kpi_summary_df.to_csv(
    "kpi_summary.csv",
    index=False
)

print("\nKPI summary exported successfully.")

clean_df.to_csv(
    "clean_trades.csv",
    index=False
)

print("\nClean trades exported successfully.")

print("\nKPI SUMMARY")
print("Raw total trades:", raw_total_trades)
print("Clean total trades:", clean_total_trades)
print("Number of duplicate trades:", number_of_duplicate_trades)
print("Number of missing owners:", number_of_missing_owners)
print("Number of missing settlement dates:", number_of_missing_settlement_dates)
print("Number of pending trades:", number_of_pending_trades)
print("Number of overdue trades:", number_of_overdue_trades)
print("Number of failed trades:", number_of_failed_trades)
print("Number of high priority trades:", number_of_high_priority_trades)
print("Number of high priority failed trades:", number_of_high_priority_failed_trades)
print("Completion rate:", round(completion_rate, 2), "%")
print("Failure rate:", round(failure_rate, 2), "%")
print("Overdue rate:", round(overdue_rate, 2), "%")
print("High priority failure rate:", round(high_priority_failure_rate, 2), "%")

prompt = f"""
You are a post-trade operations analyst.

Analyse the following metrics and write a concise operational summary.

Clean trades reviewed: {clean_total_trades}
Failed trades: {number_of_failed_trades}
Overdue trades: {number_of_overdue_trades}
High-priority failed trades: {number_of_high_priority_failed_trades}
Missing owners: {number_of_missing_owners}

Include:
- Key operational risks
- Recommended actions
- Professional business language
"""

response = chat(
    model="llama3.2",
    messages=[
        {"role": "user", "content": prompt}
    ]
)

operational_summary = response.message.content

print("\nOPERATIONAL SUMMARY")
print(operational_summary)

with open("operational_summary.txt", "w") as file:
    file.write(operational_summary)

print("\nOperational summary exported successfully.")

# Excel exports

clean_df.to_excel(
    "clean_trades.xlsx",
    index=False
)

validation_report_df.to_excel(
    "validation_report.xlsx",
    index=False
)

kpi_summary_df.to_excel(
    "kpi_summary.xlsx",
    index=False
)

print("\nExcel reports exported successfully.")
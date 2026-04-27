import streamlit as st
import pandas as pd
from openai import OpenAI

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="AI Workforce Analytics Assistant", layout="wide")

# =========================
# OPENAI CLIENT
# =========================
import streamlit as st
from openai import OpenAI

client = OpenAI(api_key="OPENAI_API_KEY")

# =========================
# HELPERS
# =========================
def safe_divide(a: float, b: float) -> float:
    return a / b if b not in (0, None) else 0.0

def simple_forecast(series: pd.Series) -> float:
    series = series.dropna()
    if len(series) == 0:
        return 0.0
    if len(series) == 1:
        return float(series.iloc[-1])

    x = pd.Series(range(len(series)), dtype="float64")
    y = series.astype("float64").reset_index(drop=True)

    x_mean = x.mean()
    y_mean = y.mean()

    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return float(y.iloc[-1])

    slope = (((x - x_mean) * (y - y_mean)).sum()) / denom
    intercept = y_mean - slope * x_mean
    next_x = x.iloc[-1] + 1
    return float(intercept + slope * next_x)

def is_workforce_analytics_question(question: str) -> bool:
    q = (question or "").lower().strip()

    if q == "":
        return True

    allowed_keywords = [
        "payroll", "pay", "salary", "cost", "cost per case",
        "volume", "cases", "delivered",
        "region", "west", "east", "central",
        "job", "driver", "forklift", "warehouse", "night loader",
        "labor", "efficiency", "productivity",
        "forecast", "trend", "risk", "warning",
        "overtime", "rate", "performance",
        "scenario", "what-if", "simulate", "simulation",
        "highest", "lowest", "top", "bottom", "average", "total",
        "why", "root cause"
    ]

    return any(keyword in q for keyword in allowed_keywords)

def parse_question(question: str) -> dict:
    q = (question or "").lower().strip()

    intent = None
    if any(word in q for word in ["top", "highest", "max"]):
        intent = "max"
    elif any(word in q for word in ["bottom", "lowest", "min"]):
        intent = "min"
    elif any(word in q for word in ["average", "avg", "mean"]):
        intent = "avg"
    elif any(word in q for word in ["total", "sum"]):
        intent = "sum"

    metric = None
    if any(word in q for word in ["pay", "salary", "payroll", "cost"]):
        metric = "pay"
    elif any(word in q for word in ["volume", "cases", "delivered"]):
        metric = "volume"
    elif "rate" in q:
        metric = "rate"

    time_filter = None
    if "last week" in q:
        time_filter = "last_week"
    elif any(word in q for word in ["latest", "recent", "most recent"]):
        time_filter = "latest"

    final_region_override = None
    if "west" in q:
        final_region_override = ["West"]
    elif "east" in q:
        final_region_override = ["East"]
    elif "central" in q:
        final_region_override = ["Central"]

    final_job_override = None
    if "driver" in q:
        final_job_override = ["Driver"]
    elif "forklift" in q:
        final_job_override = ["Forklift Operator"]
    elif "warehouse" in q:
        final_job_override = ["Warehouse Selector"]
    elif "night" in q:
        final_job_override = ["Night Loader"]

    return {
        "q": q,
        "intent": intent,
        "metric": metric,
        "time_filter": time_filter,
        "region_override": final_region_override,
        "job_override": final_job_override,
        "top_n": 3 if "top" in q else None,
        "bottom_n": 3 if "bottom" in q else None,
    }

def build_computed_result(final_combined, filtered_payroll, intent, metric, question):

    q = (question or "").lower()

    # Decide dimension
    if "region" in q and "week" in q:
        dim = "region_week"
    elif "region" in q:
        dim = "region"
    elif "week" in q:
        dim = "week"
    elif "job" in q:
        dim = "job"
    else:
        dim = "overall"

    if metric == "pay":
        col = "Total_Pay"
    elif metric == "volume":
        col = "Delivered_Cases"
    elif metric == "rate":
        col = "Base_Pay_Rate"
    else:
        return None, None

    # Grouping logic
    if dim == "region_week":
        df = final_combined.groupby(["Region","Week_Start"], as_index=False)[col].sum()
    elif dim == "region":
        df = final_combined.groupby("Region", as_index=False)[col].sum()
    elif dim == "week":
        df = final_combined.groupby("Week_Start", as_index=False)[col].sum()
    elif dim == "job":
        df = filtered_payroll.groupby("Job_Profile", as_index=False)[col].sum()
    else:
        df = final_combined[[col]]

    if df.empty:
        return df, None

    if intent == "max":
        result = df.loc[df[col].idxmax()]
    elif intent == "min":
        result = df.loc[df[col].idxmin()]
    elif intent == "avg":
        result = float(df[col].mean())
    elif intent == "sum":
        result = float(df[col].sum())
    else:
        result = None

    return df, result

# =========================
# LOAD DATA
# =========================
st.title("🤖 AI Workforce Analytics Assistant")

payroll = pd.read_excel("payroll.xlsx")
volume = pd.read_csv("volume.csv")

payroll["Week_Start"] = pd.to_datetime(payroll["Week_Start"])
volume["Week_Start"] = pd.to_datetime(volume["Week_Start"])

# =========================
# REGION MAPPING
# =========================
location_region_map = {
    "FL02": "East",
    "MD01": "Central",
    "CA03": "West",
    "WH_CA_303": "West",
    "WH_FL_202": "East",
    "WH_MD_102": "Central",
}
payroll["Region"] = payroll["Location_ID"].map(location_region_map)

# Keep only mapped rows for analytics
payroll = payroll[payroll["Region"].notna()].copy()

# =========================
# SIDEBAR FILTERS
# =========================
st.sidebar.header("🔍 Filters")

all_regions = sorted(volume["Region"].dropna().unique().tolist())
all_jobs = sorted(payroll["Job_Profile"].dropna().unique().tolist())

selected_region = st.sidebar.multiselect(
    "Region",
    options=all_regions,
    default=all_regions,
    key="region_filter",
)

selected_job = st.sidebar.multiselect(
    "Job Profile",
    options=all_jobs,
    default=all_jobs,
    key="job_filter",
)

question = st.text_input("💬 Ask a question", key="question_input")

if question and not is_workforce_analytics_question(question):
    st.warning(
        "⚠️ This assistant is designed only for workforce analytics questions. "
        "Please ask about payroll, volume, region, job profile, productivity, trends, forecasting, or scenario analysis."
    )
    st.stop()

compare_all_regions = False
if question:
    compare_all_regions = "which region" in question.lower()

parsed = parse_question(question)
intent = parsed["intent"]
metric = parsed["metric"]
time_filter = parsed["time_filter"]

final_region = parsed["region_override"] if parsed["region_override"] else selected_region
final_job = parsed["job_override"] if parsed["job_override"] else selected_job

# =========================
# SMART FILTER OVERRIDE
# =========================

if compare_all_regions:
    st.warning("⚠️ Comparing across all regions (overriding filter)")

    filtered_payroll = payroll[
        payroll["Job_Profile"].isin(final_job)
    ].copy()

    filtered_volume = volume.copy()

else:
    filtered_payroll = payroll[
        (payroll["Region"].isin(final_region)) &
        (payroll["Job_Profile"].isin(final_job))
    ].copy()

    filtered_volume = volume[
        volume["Region"].isin(final_region)
    ].copy()
    
# Keep only common weeks (same as before)
common_weeks = sorted(
    set(filtered_payroll["Week_Start"]).intersection(set(filtered_volume["Week_Start"]))
)

filtered_payroll = filtered_payroll[
    filtered_payroll["Week_Start"].isin(common_weeks)
].copy()

filtered_volume = filtered_volume[
    filtered_volume["Week_Start"].isin(common_weeks)
].copy()

final_combined = pd.merge(
    filtered_payroll.groupby(["Week_Start", "Region"], as_index=False).agg({
        "Total_Pay": "sum",
        "Base_Pay_Rate": "mean"
    }),
    filtered_volume.groupby(["Week_Start", "Region"], as_index=False).agg({
        "Delivered_Cases": "sum"
    }),
    on=["Week_Start", "Region"],
    how="inner"
)

if not final_combined.empty and time_filter in {"last_week", "latest"}:
    max_date = final_combined["Week_Start"].max()
    final_combined = final_combined[final_combined["Week_Start"] == max_date].copy()
    filtered_payroll = filtered_payroll[filtered_payroll["Week_Start"] == max_date].copy()
    filtered_volume = filtered_volume[filtered_volume["Week_Start"] == max_date].copy()

# =========================
# APPLIED FILTERS
# =========================
st.markdown("### 🤖 AI Applied Filters")
st.write("Region:", final_region)
st.write("Job Profile:", final_job)
if question:
    st.markdown(f"### 🔍 Answering: **{question}**")

if final_combined.empty:
    st.error("No data available after applying filters. Adjust region, job profile, or question.")
    with st.expander("Analyst Details"):
        st.write("Filtered payroll rows:", len(filtered_payroll))
        st.write("Filtered volume rows:", len(filtered_volume))
    st.stop()

# =========================
# CORE METRICS
# =========================
total_payroll = float(final_combined["Total_Pay"].sum())
total_cases = float(final_combined["Delivered_Cases"].sum())
avg_pay = float(final_combined["Base_Pay_Rate"].mean()) if not final_combined["Base_Pay_Rate"].empty else 0.0
cost_per_case = safe_divide(total_payroll, total_cases)
cases_per_dollar = safe_divide(total_cases, total_payroll)

payroll_trend = final_combined.groupby("Week_Start")["Total_Pay"].sum().sort_index()
volume_trend = final_combined.groupby("Week_Start")["Delivered_Cases"].sum().sort_index()

# =========================
# COMPUTED RESULT
# =========================

df_result, result = build_computed_result(
    final_combined, filtered_payroll, intent, metric, question
)

computed_answer = None
problem_week = None
problem_region = None

if isinstance(result, pd.Series):

    # Extract region
    if "Region" in result.index:
        problem_region = result["Region"]

    # Extract week if available
    if "Week_Start" in result.index:
        problem_week = pd.to_datetime(result["Week_Start"])

    # Extract metric value safely
    if metric == "volume":
        metric_value = result["Delivered_Cases"] if "Delivered_Cases" in result.index else result.iloc[-1]

    elif metric == "pay":
        metric_value = result["Total_Pay"] if "Total_Pay" in result.index else result.iloc[-1]

    elif metric == "rate":
        metric_value = result["Base_Pay_Rate"] if "Base_Pay_Rate" in result.index else result.iloc[-1]

    else:
        metric_value = result.iloc[-1]

    # 🔥 CRITICAL FIX: Ensure week exists for root cause
    if problem_week is None and problem_region is not None:

        region_data = final_combined[
            final_combined["Region"] == problem_region
        ]

        if not region_data.empty:

            if metric == "volume":
                problem_week = region_data.loc[
                    region_data["Delivered_Cases"].idxmin()
                ]["Week_Start"]

            elif metric == "pay":
                problem_week = region_data.loc[
                    region_data["Total_Pay"].idxmax()
                ]["Week_Start"]

            else:
                # fallback: just take latest week
                problem_week = region_data["Week_Start"].max()

    # Build answer
    if problem_region is not None and problem_week is not None:
        computed_answer = (
            f"{problem_region} in week {problem_week.date()} has the {intent} "
            f"{metric}: {metric_value:,.2f}"
        )

    elif problem_region is not None:
        computed_answer = f"{problem_region} has the {intent} {metric}: {metric_value:,.2f}"

elif isinstance(result, (int, float)):
    computed_answer = f"{intent} {metric}: {result:,.2f}"

# =========================
# EXECUTIVE SUMMARY
# =========================
st.markdown("## 🔵 Executive Summary")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Cost per Case", f"${cost_per_case:.2f}")
k2.metric("Productivity (Cases/$)", f"{cases_per_dollar:.2f}")
k3.metric("Total Volume", f"{int(total_cases):,}")
k4.metric("Total Payroll", f"${total_payroll:,.0f}")

if computed_answer:
    st.info(f"**Answer:** {computed_answer}")

st.markdown("### 🚨 Executive Flags")
weekly_baseline_cost = float((final_combined.groupby("Week_Start").apply(
    lambda x: safe_divide(x["Total_Pay"].sum(), x["Delivered_Cases"].sum())
)).mean()) if len(final_combined) > 0 else 0.0

if weekly_baseline_cost > 0 and cost_per_case > weekly_baseline_cost * 1.2:
    st.error("🚨 Cost spike detected vs baseline")
elif weekly_baseline_cost > 0 and cost_per_case > weekly_baseline_cost:
    st.warning("⚠️ Cost slightly above normal")
else:
    st.success("✅ Healthy cost efficiency")

if total_cases < float(final_combined.groupby("Week_Start")["Delivered_Cases"].sum().mean()):
    st.warning("📉 Volume below average")

if total_payroll > float(final_combined.groupby("Week_Start")["Total_Pay"].sum().mean()):
    st.warning("💰 Payroll above normal — check efficiency")

# =========================
# AI EXECUTIVE INSIGHT
# =========================
st.markdown("### 🤖 AI Insights")

insight_prompt = f"""
You are a senior executive-level Operations Analytics advisor.

Output exactly in this structure:

### 1. Executive Summary
### 2. What is happening
### 3. Why it matters
### 4. Recommended Actions

Keep it concise, direct, and executive-ready.

User Question:
{question if question else "Provide an executive summary of the current filtered operations view."}

Computed Answer:
{computed_answer if computed_answer else "No specific computed answer was generated."}

Business Context:
- Regions: {final_region}
- Job Profiles: {final_job}

Key Metrics:
- Total Payroll: {total_payroll:,.2f}
- Delivered Cases: {total_cases:,.0f}
- Avg Pay Rate: {avg_pay:,.2f}
- Cost per Case: {cost_per_case:.4f}
- Cases per Dollar: {cases_per_dollar:.4f}

Recent Payroll Trend:
{payroll_trend.tail(5).to_string()}

Recent Volume Trend:
{volume_trend.tail(5).to_string()}
"""

try:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=insight_prompt
    )
    st.markdown(response.output_text)
except Exception as e:
    st.warning(f"AI insight unavailable: {e}")

# ------------------------
# SMART ANSWER (EXECUTIVE)
# ------------------------
if isinstance(result, pd.Series):

    if metric == "volume":
        value = result["Delivered_Cases"]
        label = "Delivered Cases"
    elif metric == "pay":
        value = result["Total_Pay"]
        label = "Total Payroll"
    elif metric == "rate":
        value = result["Base_Pay_Rate"]
        label = "Pay Rate"
    else:
        value = result.iloc[-1]
        label = metric

    region = result.get("Region", "N/A")
    week = result.get("Week_Start", None)

    if pd.notna(week):
        week_text = f"week of {week.date()}"
    else:
        week_text = ""

    st.markdown("### 🎯 Key Insight")

    st.success(
        f"👉 **{region}** has the **{intent} {label}** "
        f"{week_text} → **{value:,.2f}**"
    )

# =========================
# ROOT CAUSE & DIAGNOSIS
# =========================
st.markdown("## 🟡 Root Cause & Diagnosis")

if intent in ["min", "max"] and problem_week is not None:
    st.subheader("🔍 Root Cause Drilldown")

    week_data = final_combined[final_combined["Week_Start"] == problem_week].copy()
    if problem_region is not None:
        region_week_data = week_data[week_data["Region"] == problem_region].copy()
    else:
        region_week_data = week_data.copy()

    st.write(f"**Problem Week:** {problem_week.date()}")
    st.dataframe(week_data, use_container_width=True)

    avg_cases_weekly = float(final_combined.groupby("Week_Start")["Delivered_Cases"].sum().mean())
    week_cases = float(region_week_data["Delivered_Cases"].sum()) if not region_week_data.empty else 0.0

    avg_pay_weekly = float(final_combined.groupby("Week_Start")["Total_Pay"].sum().mean())
    week_pay = float(region_week_data["Total_Pay"].sum()) if not region_week_data.empty else 0.0

    if week_cases < avg_cases_weekly:
        st.warning("📉 Volume is below average")
    if week_pay > avg_pay_weekly:
        st.warning("💰 Payroll is higher than average")
    if week_pay > avg_pay_weekly and week_cases < avg_cases_weekly:
        st.error("🚨 Inefficiency detected: high payroll + low volume")

    st.subheader("👷 Job Cost Breakdown")
    job_breakdown = filtered_payroll[
        filtered_payroll["Week_Start"] == problem_week
    ].groupby("Job_Profile", as_index=False)["Total_Pay"].sum()

    if not job_breakdown.empty:
        st.bar_chart(job_breakdown.set_index("Job_Profile"))
        st.dataframe(job_breakdown, use_container_width=True)
    else:
        st.info("No job-level payroll detail available for the identified week.")
else:
    st.info("Detailed root cause drilldown becomes available when the question returns a specific max/min week or region-week result.")

# =========================
# TRENDS & RISK
# =========================
st.markdown("## 🟢 Trends & Risk")

t1, t2 = st.columns(2)
with t1:
    st.subheader("Payroll Trend")
    st.line_chart(payroll_trend)

with t2:
    st.subheader("Volume Trend")
    st.line_chart(volume_trend)

if len(volume_trend) > 2:
    pct_change = volume_trend.pct_change().dropna()
    spikes = pct_change[abs(pct_change) > 0.30]
    if not spikes.empty:
        st.warning("⚠️ Significant volume change detected")
        st.dataframe(spikes.rename("Pct_Change").to_frame(), use_container_width=True)

# =========================
# MULTI-WEEK PATTERN DETECTION
# =========================
st.subheader("📊 Multi-Week Pattern Detection")

weekly_summary = final_combined.groupby("Week_Start", as_index=False).agg({
    "Total_Pay": "sum",
    "Delivered_Cases": "sum"
})
weekly_summary["Cost_per_Case"] = weekly_summary.apply(
    lambda row: safe_divide(row["Total_Pay"], row["Delivered_Cases"]), axis=1
)

avg_cost = float(weekly_summary["Cost_per_Case"].mean()) if not weekly_summary.empty else 0.0
avg_volume = float(weekly_summary["Delivered_Cases"].mean()) if not weekly_summary.empty else 0.0

weekly_summary["Inefficient"] = (
    (weekly_summary["Cost_per_Case"] > avg_cost) &
    (weekly_summary["Delivered_Cases"] < avg_volume)
)

st.dataframe(weekly_summary, use_container_width=True)

consecutive_issues = 0
max_consecutive = 0
for flag in weekly_summary["Inefficient"]:
    if flag:
        consecutive_issues += 1
        max_consecutive = max(max_consecutive, consecutive_issues)
    else:
        consecutive_issues = 0

if max_consecutive >= 3:
    st.error("🚨 Systemic inefficiency detected (3+ consecutive weeks)")
elif max_consecutive == 2:
    st.warning("⚠️ Repeating inefficiency pattern detected (2 consecutive weeks)")
else:
    st.success("✅ No repeating inefficiency pattern")

recent_trend = weekly_summary.tail(3)
if len(recent_trend) >= 2:
    if recent_trend["Cost_per_Case"].iloc[-1] > recent_trend["Cost_per_Case"].iloc[0]:
        st.warning("📈 Cost efficiency worsening in recent weeks")
    else:
        st.success("📉 Cost efficiency improving in recent weeks")

# =========================
# FORECAST & EARLY WARNING
# =========================
st.markdown("## 🔮 Forecast & Early Warning")

forecast_df = weekly_summary.sort_values("Week_Start").copy()
predicted_cases = simple_forecast(forecast_df["Delivered_Cases"])
predicted_pay = simple_forecast(forecast_df["Total_Pay"])
predicted_cost = safe_divide(predicted_pay, predicted_cases)

current_cost = float(forecast_df["Cost_per_Case"].iloc[-1]) if not forecast_df.empty else 0.0

f1, f2, f3 = st.columns(3)
f1.metric("Predicted Volume", f"{int(predicted_cases):,}")
f2.metric("Predicted Payroll", f"${predicted_pay:,.0f}")
f3.metric("Predicted Cost/Case", f"${predicted_cost:.2f}")

st.markdown("### 🚨 Early Warning Signals")
if predicted_cases < avg_volume:
    st.warning("📉 Forecasted volume below average → demand risk")
if predicted_cost > avg_cost * 1.15:
    st.error("🚨 Cost spike expected next week")
if predicted_cost > current_cost:
    st.warning("⚠️ Cost trend increasing")
if predicted_cases < avg_volume and predicted_cost > avg_cost:
    st.error("🚨 High risk: low volume + high cost expected")
if predicted_cases > avg_volume and predicted_cost < avg_cost:
    st.success("✅ Healthy outlook: improving efficiency")

forecast_plot = forecast_df[["Week_Start", "Delivered_Cases"]].copy()
next_week = forecast_plot["Week_Start"].max() + pd.Timedelta(days=7)
forecast_plot = pd.concat([
    forecast_plot,
    pd.DataFrame({"Week_Start": [next_week], "Delivered_Cases": [predicted_cases]})
], ignore_index=True).set_index("Week_Start")

st.markdown("### 📈 Volume Forecast Trend")
st.line_chart(forecast_plot)

# =========================
# SCENARIO SIMULATION
# =========================
st.markdown("## 🎯 Scenario Simulation (What-If)")
st.write("Adjust assumptions to simulate impact on cost efficiency.")

s1, s2 = st.columns(2)
with s1:
    payroll_change = st.slider("Payroll Change (%)", min_value=-50, max_value=50, value=0, step=5)
with s2:
    volume_change = st.slider("Volume Change (%)", min_value=-50, max_value=50, value=0, step=5)

payroll_factor = 1 + payroll_change / 100
volume_factor = 1 + volume_change / 100

base_pay = total_payroll
base_cases = total_cases
base_cost = safe_divide(base_pay, base_cases)

sim_pay = base_pay * payroll_factor
sim_cases = base_cases * volume_factor
sim_cost = safe_divide(sim_pay, sim_cases)

st.subheader("📊 Scenario Results")
r1, r2, r3 = st.columns(3)
r1.metric("Simulated Payroll", f"${sim_pay:,.0f}")
r2.metric("Simulated Volume", f"{int(sim_cases):,}")
r3.metric("Simulated Cost/Case", f"${sim_cost:.2f}", delta=f"{sim_cost - base_cost:.2f}")

st.subheader("🚨 Scenario Insights")
if sim_cost > base_cost * 1.2:
    st.error("🚨 Significant cost increase — not recommended")
elif sim_cost > base_cost:
    st.warning("⚠️ Cost increase — efficiency drops")
elif sim_cost < base_cost:
    st.success("✅ Efficiency improvement")

if payroll_change > 0 and volume_change <= 0:
    st.error("🚨 Risky: increasing payroll without volume growth")
if payroll_change < 0 and volume_change > 0:
    st.success("✅ Strong scenario: better utilization")
if volume_change < 0:
    st.warning("📉 Volume drop risk — monitor demand")

compare_df = pd.DataFrame({
    "Scenario": ["Current", "Simulated"],
    "Cost_per_Case": [base_cost, sim_cost]
}).set_index("Scenario")

st.markdown("### 📈 Cost Comparison")
st.bar_chart(compare_df)

# =========================
# ANALYST DETAIL EXPANDER
# =========================
with st.expander("🔎 Analyst Details"):
    st.write("Region mapping check")
    st.dataframe(payroll[["Location_ID", "Region"]].drop_duplicates(), use_container_width=True)

    st.write("Available regions in combined data")
    st.write(sorted(final_combined["Region"].dropna().unique().tolist()))

    st.write("Combined dataset preview")
    st.dataframe(final_combined.head(10), use_container_width=True)

    st.write("Row count:", len(final_combined))

    st.write("Filtered payroll preview")
    st.dataframe(filtered_payroll.head(10), use_container_width=True)

    st.write("Filtered volume preview")
    st.dataframe(filtered_volume.head(10), use_container_width=True)

    if df_result is not None:
        st.write("Computed result dataset preview")
        st.dataframe(df_result.head(10), use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components
import base64
import os

# =========================
# GET ICON LOCALLY
# =========================
@st.cache_data
def get_icon_base64():
    """Reads icon.png from the local folder to guarantee it cannot be blocked by the internet."""
    if os.path.exists("icon.png"):
        try:
            with open("icon.png", "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                return f"data:image/png;base64,{b64}"
        except Exception as e:
            st.error(f"Error reading icon.png: {e}")
            
    return "https://i.imgur.com/dOpt87p.png"

ICON_DATA = get_icon_base64()

# Set page configuration
st.set_page_config(layout="wide", page_title="Sales Dashboard", page_icon="📊")

# =========================
# PROGRESSIVE WEB APP (PWA) INJECTION
# =========================
def setup_pwa(icon_data):
    """Injects a Web App Manifest and forces the custom icon using Base64 data."""
    pwa_html = f"""
    <script>
        try {{
            const parentDoc = window.parent.document;
            const parentWin = window.parent;
            const parentLoc = parentWin.location.origin + parentWin.location.pathname; 

            const oldIcons = parentDoc.querySelectorAll('link[rel="shortcut icon"], link[rel="icon"], link[rel="apple-touch-icon"]');
            oldIcons.forEach(icon => icon.remove());

            const appleIcon = parentDoc.createElement('link');
            appleIcon.rel = 'apple-touch-icon';
            appleIcon.href = '{icon_data}';
            parentDoc.head.appendChild(appleIcon);
            
            const standardIcon = parentDoc.createElement('link');
            standardIcon.rel = 'icon';
            standardIcon.href = '{icon_data}';
            parentDoc.head.appendChild(standardIcon);

            const oldManifest = parentDoc.querySelector('link[rel="manifest"]');
            if (oldManifest) oldManifest.remove();

            const manifest = {{
                "name": "Sales Dashboard Application",
                "short_name": "SalesDash",
                "display": "standalone",
                "start_url": parentLoc, 
                "icons": [
                    {{ "src": "{icon_data}", "sizes": "192x192", "type": "image/png" }},
                    {{ "src": "{icon_data}", "sizes": "512x512", "type": "image/png" }}
                ]
            }};
            
            const stringManifest = JSON.stringify(manifest);
            const blob = new Blob([stringManifest], {{type: 'application/json'}});
            const manifestURL = URL.createObjectURL(blob);
            
            const manifestLink = parentDoc.createElement('link');
            manifestLink.rel = 'manifest';
            manifestLink.href = manifestURL;
            parentDoc.head.appendChild(manifestLink);

        }} catch (err) {{
            console.error("PWA setup failed:", err);
        }}
    </script>
    """
    components.html(pwa_html, height=0, width=0)

setup_pwa(ICON_DATA)

# =========================
# LOAD DATA (Cloud-Safe Version)
# =========================
@st.cache_data
def load_data():
    # 1. Search for the file ignoring case sensitivity (crucial for Linux/Streamlit Cloud)
    files_in_dir = os.listdir()
    target_file = None
    
    for f in files_in_dir:
        if f.lower() in ["rawdata.xlsx", "rawdata.csv"]:
            target_file = f
            break
            
    if not target_file:
        st.error(f"❌ Could not find raw data! Here are the files I see in your directory: {files_in_dir}")
        return pd.DataFrame()

    # 2. Load the file
    try:
        if target_file.endswith(".xlsx"):
            df = pd.read_excel(target_file)
        else:
            df = pd.read_csv(target_file)
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return pd.DataFrame()

    df.columns = df.columns.str.strip()

    rename_map = {
        "CHANNEL": "Channel",
        "Customer Name": "CustomerName",
        "Sub Category": "SubCategory",
        "Part Number": "PartNo",
        "Amount": "Value",
        "Sales Executive": "Salesman"
    }
    df = df.rename(columns=rename_map)

    expected_cols = ["Channel", "CustomerName", "Category", "SubCategory", "Salesman", "PartNo", "Type", "Value", "Qty", "Date"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = "Unknown" if col not in ["Value", "Qty"] else 0

    df["Type"] = df["Type"].astype(str).str.upper().str.strip()
    
    # 3. Strip Commas to prevent Pandas from turning thousands into zeros
    df["Value"] = df["Value"].astype(str).str.replace(',', '', regex=False)
    df["Qty"] = df["Qty"].astype(str).str.replace(',', '', regex=False)

    df["Value"] = pd.to_numeric(df["Value"], errors="coerce").fillna(0)
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)

    # 4. Ensure returns are handled as negative values
    df.loc[df["Type"] == "RETURN", "Value"] = -df.loc[df["Type"] == "RETURN", "Value"].abs()

    # 5. Correct Date Format
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=False, errors="coerce")
    
    # Safety check for broken dates
    if df["Date"].isna().all():
        st.error("❌ All dates failed to process. Please check the date format in your CSV.")
        
    df = df.dropna(subset=["Date"])
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()

    return df

df = load_data()

if df.empty:
    st.stop() # Stops execution gracefully if data fails to load

# =========================
# GLOBAL FILTERS (SIDEBAR)
# =========================
st.title("📊 Sales Dashboard")

st.sidebar.header("🔍 Filter Data")
filtered_df = df.copy()

# Helper function for cascading filters
def apply_multiselect(current_df, label, column):
    options = sorted(current_df[column].dropna().astype(str).unique())
    selected = st.sidebar.multiselect(label, options)
    if selected:
        return current_df[current_df[column].isin(selected)]
    return current_df

# Apply cascading filters in order
filtered_df = apply_multiselect(filtered_df, "Channel", "Channel")
filtered_df = apply_multiselect(filtered_df, "Customer Name", "CustomerName")
filtered_df = apply_multiselect(filtered_df, "Category", "Category")
filtered_df = apply_multiselect(filtered_df, "Sub Category", "SubCategory")
filtered_df = apply_multiselect(filtered_df, "Part Number", "PartNo")
filtered_df = apply_multiselect(filtered_df, "Sales Executive", "Salesman")

# Type Filter
type_filter = st.sidebar.selectbox("Type", ["BOTH", "SALE", "RETURN"])
if type_filter != "BOTH":
    filtered_df = filtered_df[filtered_df["Type"] == type_filter]

# Dates placed safely at the bottom
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Date Range")

# Extract safe min/max dates for the widgets
min_date = df["Date"].min().date()
max_date = df["Date"].max().date()

start_date = st.sidebar.date_input("Start Date", min_date)
end_date = st.sidebar.date_input("End Date", max_date)

# Fix Midnight Cutoff using .dt.date
filtered_df = filtered_df[
    (filtered_df["Date"].dt.date >= start_date) & 
    (filtered_df["Date"].dt.date <= end_date)
]

# =========================
# KPI CALCULATIONS
# =========================
sales_df = filtered_df[filtered_df["Type"] == "SALE"]
return_df = filtered_df[filtered_df["Type"] == "RETURN"]

net_revenue = filtered_df["Value"].sum()
sales_value = sales_df["Value"].sum()
return_value = return_df["Value"].sum()
sales_volume = sales_df["Qty"].sum()

# CSS with fixed pixels for uniform PC/Mobile appearance
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background-color: rgba(28, 131, 225, 0.1);
    border: 1px solid rgba(28, 131, 225, 0.1);
    padding: 15px 20px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Net Revenue", f"OMR {net_revenue:,.2f}")
k2.metric("Sale Value", f"OMR {sales_value:,.2f}")
k3.metric("Return Value", f"OMR {return_value:,.2f}")
k4.metric("Sale Volume", f"{sales_volume:,.0f}")

# =========================
# MONTHLY PERFORMANCE TREND
# =========================
st.markdown("---")
st.subheader("📈 Monthly Performance Trend")

if not filtered_df.empty:
    monthly_trend = filtered_df.groupby(["Month", "Type"])["Value"].sum().reset_index()
    fig_trend = px.bar(
        monthly_trend, x="Month", y="Value", color="Type",
        barmode="group",
        labels={"Value": "Amount (OMR)"},
        color_discrete_map={"SALE": "#017016", "RETURN": "#99060B"}
    )
    fig_trend.update_xaxes(dtick="M1", tickformat="%b %Y")
    st.plotly_chart(fig_trend, use_container_width=True)

# =========================
# CHARTS ROW
# =========================
st.markdown("---")
c1, c2 = st.columns(2)
chart_data = filtered_df.copy()
chart_data["AbsValue"] = chart_data["Value"].abs()

if not chart_data.empty:
    fig_cat = px.pie(chart_data, values="AbsValue", names="Category", hole=0.5, title="Revenue Share by Category")
    c1.plotly_chart(fig_cat, use_container_width=True)

    fig_ch = px.pie(chart_data, values="AbsValue", names="Channel", hole=0.5, title="Revenue Share by Channel")
    c2.plotly_chart(fig_ch, use_container_width=True)

# =========================
# TOP SKU TABLE
# =========================
st.markdown("---")
st.subheader("🔥 Top 10 Fast Moving SKU")
fast_sku = (
    filtered_df[filtered_df["Type"] == "SALE"]
    .groupby(["PartNo", "Category", "SubCategory"])["Qty"]
    .sum()
    .reset_index()
    .sort_values("Qty", ascending=False)
    .head(10)
)
st.dataframe(fast_sku, use_container_width=True, hide_index=True)

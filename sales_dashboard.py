import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components

# Set page configuration
st.set_page_config(layout="wide", page_title="Sales Dashboard", page_icon="📊")

# =========================
# PROGRESSIVE WEB APP (PWA) INJECTION
# =========================
def setup_pwa():
    """
    Injects a Web App Manifest, iOS meta tags, and a minimal Service Worker into the Streamlit app.
    This fulfills browser requirements to prompt the user to "Add to Home Screen" or "Install App".
    """
    pwa_html = """
    <script>
        // 1. Define the Web App Manifest
        const manifest = {
            "name": "Sales Dashboard Application",
            "short_name": "SalesDash",
            "description": "Comprehensive Sales Analytics and Tracking",
            "theme_color": "#F0F2F6",
            "background_color": "#FFFFFF",
            "display": "standalone",
            "orientation": "portrait-primary",
            "scope": "/",
            "start_url": "/",
            "icons": [
                {
                    "src": "https://imgur.com/a/tQYT0R8",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable"
                },
                {
                    "src": "https://imgur.com/a/tQYT0R8",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable"
                }
            ]
        };
        
        // Convert the manifest to a Blob and create a URL
        const stringManifest = JSON.stringify(manifest);
        const blob = new Blob([stringManifest], {type: 'application/json'});
        const manifestURL = URL.createObjectURL(blob);
        
        // Inject the manifest link into the <head> if it doesn't exist
        if (!document.querySelector('link[rel="manifest"]')) {
            const manifestLink = document.createElement('link');
            manifestLink.rel = 'manifest';
            manifestLink.href = manifestURL;
            document.head.appendChild(manifestLink);
        }

        // 2. Inject Apple/iOS specific meta tags for home screen compatibility
        const metaTags = [
            { name: 'apple-mobile-web-app-capable', content: 'yes' },
            { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
            { name: 'apple-mobile-web-app-title', content: 'SalesDash' }
        ];
        
        metaTags.forEach(tag => {
            if (!document.querySelector(`meta[name="${tag.name}"]`)) {
                const meta = document.createElement('meta');
                meta.name = tag.name;
                meta.content = tag.content;
                document.head.appendChild(meta);
            }
        });

        // 3. Dummy Service Worker Registration
        // Chrome requires a registered Service Worker with a fetch event handler to trigger the install prompt.
        if ('serviceWorker' in navigator) {
            // A simple pass-through service worker
            const swCode = "self.addEventListener('fetch', function(event) { event.respondWith(fetch(event.request)); });";
            const swBlob = new Blob([swCode], {type: 'application/javascript'});
            const swUrl = URL.createObjectURL(swBlob);
            
            navigator.serviceWorker.register(swUrl).then(registration => {
                console.log('PWA Service Worker registered for installability.');
            }).catch(err => {
                console.log('Service Worker registration failed: ', err);
            });
        }
    </script>
    """
    # Render the component invisibly
    components.html(pwa_html, height=0, width=0)

# Initialize the PWA functionality immediately
setup_pwa()

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data():
    try:
        # Try reading Excel first based on the sheet image, fallback to CSV
        try:
            df = pd.read_excel("RawData.xlsx")
        except FileNotFoundError:
            df = pd.read_csv("RawData.csv")
    except FileNotFoundError:
        st.error("Data file (RawData.xlsx or RawData.csv) not found. Please place it in the same directory.")
        return pd.DataFrame()

    # --- Standardize column names ---
    df.columns = df.columns.str.strip()
    
    # Map headers to standard names (ignores if missing)
    rename_map = {
        "CHANNEL": "Channel",
        "Customer Name": "CustomerName",
        "Sub Category": "SubCategory",
        "Part Number": "PartNo",
        "Amount": "Value",
        "Sales Executive": "Salesman"
    }
    df = df.rename(columns=rename_map)

    # --- Safety Checks for Missing Columns ---
    expected_cols = ["Channel", "CustomerName", "Category", "SubCategory", "Salesman", "PartNo", "Type", "Value", "Qty", "Date"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = "Unknown" if col not in ["Value", "Qty"] else 0

    # --- Data Cleaning ---
    df["Type"] = df["Type"].astype(str).str.upper().str.strip()
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce").fillna(0)
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)

    # 🔴 Force returns to be negative
    df.loc[df["Type"] == "RETURN", "Value"] = -df.loc[df["Type"] == "RETURN", "Value"].abs()

    # --- Date Parsing (DD/MM/YYYY) ---
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Date"])

    # --- Create Month-Year column for the trend graph ---
    df["Month"] = df["Date"].dt.to_period("M").dt.to_timestamp()

    return df

df = load_data()

if df.empty:
    st.warning("No valid data to display. Please check your data file format and Date column.")
    st.stop()

# =========================
# GLOBAL FILTERS (Cascading)
# =========================
st.title("📊 Sales Dashboard")

# We apply filters sequentially so the options in the next dropdown are limited by previous choices
filtered_df = df.copy()

f_row1 = st.columns(4)
f_row2 = st.columns(5) 

# --- Row 1 Filters (Date, Type, Channel) ---
start_date = f_row1[0].date_input("Start Date", df["Date"].min())
end_date = f_row1[1].date_input("End Date", df["Date"].max())
type_filter = f_row1[2].selectbox("Type", ["BOTH", "SALE", "RETURN"])

# Apply Date and Type filters first
filtered_df = filtered_df[(filtered_df["Date"] >= pd.to_datetime(start_date)) & (filtered_df["Date"] <= pd.to_datetime(end_date))]
if type_filter != "BOTH":
    filtered_df = filtered_df[filtered_df["Type"] == type_filter]

# Channel
channel_options = sorted(filtered_df["Channel"].dropna().astype(str).unique())
channel_filter = f_row1[3].multiselect("Channel", channel_options)
if channel_filter:
    filtered_df = filtered_df[filtered_df["Channel"].isin(channel_filter)]

# --- Row 2 Filters (Dependent on Row 1) ---
# Customer 
customer_options = sorted(filtered_df["CustomerName"].dropna().astype(str).unique())
customer_filter = f_row2[0].multiselect("Customer", customer_options)
if customer_filter:
    filtered_df = filtered_df[filtered_df["CustomerName"].isin(customer_filter)]

# Category
cat_options = sorted(filtered_df["Category"].dropna().astype(str).unique())
cat_filter = f_row2[1].multiselect("Category", cat_options)
if cat_filter:
    filtered_df = filtered_df[filtered_df["Category"].isin(cat_filter)]

# Sub Category
subcat_options = sorted(filtered_df["SubCategory"].dropna().astype(str).unique())
subcat_filter = f_row2[2].multiselect("Sub Category", subcat_options)
if subcat_filter:
    filtered_df = filtered_df[filtered_df["SubCategory"].isin(subcat_filter)]

# Salesman
salesman_options = sorted(filtered_df["Salesman"].dropna().astype(str).unique())
salesman_filter = f_row2[3].multiselect("Sales Executive", salesman_options)
if salesman_filter:
    filtered_df = filtered_df[filtered_df["Salesman"].isin(salesman_filter)]

# Part Number
part_options = sorted(filtered_df["PartNo"].dropna().astype(str).unique())
part_filter = f_row2[4].multiselect("Part Number", part_options)
if part_filter:
    filtered_df = filtered_df[filtered_df["PartNo"].isin(part_filter)]


# =========================
# KPI CALCULATIONS
# =========================
sales_df = filtered_df[filtered_df["Type"] == "SALE"]
return_df = filtered_df[filtered_df["Type"] == "RETURN"]

net_revenue = filtered_df["Value"].sum()
sales_value = sales_df["Value"].sum()
return_value = return_df["Value"].sum()
sales_volume = sales_df["Qty"].sum()

# Styling metrics for better visual separation
st.markdown("""
<style>
div[data-testid="metric-container"] {
    background-color: rgba(28, 131, 225, 0.1);
    border: 1px solid rgba(28, 131, 225, 0.1);
    padding: 5% 10% 5% 10%;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
</style>
""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Net Revenue", f"OMR {net_revenue:,.2f}")
k2.metric("Sale Value", f"OMR {sales_value:,.2f}")
k3.metric("Return Value", f"OMR {return_value:,.2f}")
k4.metric("Sale Volume", f"{sales_volume:,.0f}")

# =========================
# NEW: MONTHLY PERFORMANCE TREND
# =========================
st.markdown("---")
st.subheader("📈 Monthly Performance Trend")

if not filtered_df.empty:
    # Group by Month and Type to see Sales vs Returns over time
    monthly_trend = filtered_df.groupby(["Month", "Type"])["Value"].sum().reset_index()

    # Sort by date so the graph flows correctly
    monthly_trend = monthly_trend.sort_values("Month")

    # Create the chart
    fig_trend = px.bar(
        monthly_trend, 
        x="Month", 
        y="Value", 
        color="Type",
        barmode="group",
        title="Revenue & Returns by Month",
        labels={"Value": "Amount (OMR)", "Month": "Month of Year"},
        color_discrete_map={"SALE": "#017016", "RETURN": "#99060B"}
    )

    # Formatting X-Axis to show Month names
    fig_trend.update_xaxes(dtick="M1", tickformat="%b %Y")
    fig_trend.update_layout(hovermode="x unified", plot_bgcolor='rgba(0,0,0,0)')

    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.warning("No data found for the current filters.")

# =========================
# CHARTS ROW (Share)
# =========================
st.markdown("---")
c1, c2 = st.columns(2)
chart_data = filtered_df.copy()
chart_data["AbsValue"] = chart_data["Value"].abs()

if not chart_data.empty:
    fig_cat = px.pie(chart_data, values="AbsValue", names="Category", hole=0.5, title="Revenue Share by Category")
    fig_cat.update_traces(textposition='inside', textinfo='percent+label')
    c1.plotly_chart(fig_cat, use_container_width=True)

    fig_ch = px.pie(chart_data, values="AbsValue", names="Channel", hole=0.5, title="Revenue Share by Channel")
    fig_ch.update_traces(textposition='inside', textinfo='percent+label')
    c2.plotly_chart(fig_ch, use_container_width=True)

# =========================
# FAST MOVING SKU
# =========================
st.markdown("---")
st.subheader("🔥 Top 10 Fast Moving SKU (Based on Selected Filters)")
fast_sku = (
    filtered_df[filtered_df["Type"] == "SALE"]
    .groupby(["PartNo", "Category", "SubCategory"])["Qty"]
    .sum()
    .reset_index()
    .sort_values("Qty", ascending=False)
    .head(10)
)
st.dataframe(fast_sku, use_container_width=True, hide_index=True)



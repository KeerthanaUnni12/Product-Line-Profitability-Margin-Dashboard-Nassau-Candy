import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Nassau Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Custom CSS for styling
st.markdown("""
<style>
    .main {
        background-color: #f5f5f5;
    }
    .stMetric {
    background-color: white;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    color: black !important;
}

.stMetric label {
    color: #555 !important;
}

.stMetric div {
    color: black !important;
}
    .css-1d391kg {
        padding-top: 1rem;
    }
    .sidebar-content {
        background-color: #ffffff;
    }
    div[data-testid="stExpander"] {
        background-color: white;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .reportview-container {
        background: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# Database connection with error handling
@st.cache_resource
def get_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="Kitu@2004",
            database="nassau"
        )
    except mysql.connector.Error as e:
        st.error(f"Database connection failed: {e}")
        return None

conn = get_connection()

def load_data(query, params=None):
    try:
        if conn is None:
            return pd.DataFrame()

        if not conn.is_connected():
            conn.reconnect()

        cursor = conn.cursor(dictionary=True)

        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        rows = cursor.fetchall()
        cursor.close()

        return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

# Load all data for filters
@st.cache_data
def load_filters():
    try:
        divisions = load_data("SELECT DISTINCT Division FROM sales")
        products = load_data("SELECT DISTINCT Product_Name FROM sales")
        return (
            divisions['Division'].tolist() if not divisions.empty else [],
            products['Product_Name'].tolist() if not products.empty else []
        )
    except Exception as e:
        st.error(f"Error loading filters: {e}")
        return [], []

# Sidebar
st.sidebar.title("🔍 Filters")
st.sidebar.markdown("---")

# Refresh button
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

st.sidebar.markdown("---")

# Load filter options
divisions, products = load_filters()

# Check if we have data
if not divisions or not products:
    st.error("No data available from database. Please check your database connection.")
    st.stop()

# Multi-select filters
selected_divisions = st.sidebar.multiselect(
    "🏢 Select Divisions",
    options=divisions,
    default=divisions,
    help="Filter by division(s)"
)

selected_products = st.sidebar.multiselect(
    "📦 Select Products",
    options=products,
    default=products[:10] if len(products) > 10 else products,
    help="Filter by product(s)"
)

# View toggle
view_mode = st.sidebar.radio(
    "📊 View Mode",
    ["Profit", "Margin"],
    horizontal=True
)

st.sidebar.markdown("---")
st.sidebar.info("💡 Use filters to customize your dashboard view")

# FIX 1: build_filter_query was missing the `all_values` parameter in several call sites.
# Also fixed the WHERE/AND logic to correctly detect existing WHERE clauses.
def build_filter_query(base_query, filter_col, filter_values, all_values=None):
    """
    Appends a WHERE / AND clause for filter_col if a subset is selected.
    Returns (query_string, params_list).
    Accepts base_query as either a plain string or a (string, list) tuple
    so calls can be chained.
    """
    # Support chaining: base_query may already be a (query, params) tuple
    if isinstance(base_query, tuple):
        query, params = base_query
    else:
        query, params = base_query, []

    if not filter_values:
        return query, params

    if all_values is not None and len(filter_values) == len(all_values):
        return query, params

    placeholders = ', '.join(['%s'] * len(filter_values))

    upper = query.upper()

    if "GROUP BY" in upper:
        parts = query.split("GROUP BY", 1)
        base = parts[0]
        tail = "GROUP BY" + parts[1]
    else:
        base = query
        tail = ""

    connector = "AND" if "WHERE" in base.upper() else "WHERE"

    query = f"{base} {connector} {filter_col} IN ({placeholders}) {tail}"

    params = params + list(filter_values)
    return query, params

# Main Dashboard
st.title("📊 Product Line Profitability & Margin Dashboard")
st.markdown("---")

# KPI Section
base_kpi = "SELECT SUM(Sales) Revenue, SUM(Gross_Profit) Profit FROM sales"
kpi_query, kpi_params = build_filter_query(base_kpi, 'Division', selected_divisions, divisions)
kpi_query, kpi_params = build_filter_query((kpi_query, kpi_params), 'Product_Name', selected_products, products)

kpi = load_data(kpi_query, params=kpi_params if kpi_params else None)

# Handle None/NaN values safely
revenue = kpi["Revenue"].iloc[0] if not kpi.empty and pd.notna(kpi["Revenue"].iloc[0]) else 0
profit  = kpi["Profit"].iloc[0]  if not kpi.empty and pd.notna(kpi["Profit"].iloc[0])  else 0
margin  = (profit / revenue * 100) if revenue else 0

# KPI Cards
col1, gap1, col2, gap2, col3 = st.columns([1, 0.15, 1, 0.15, 1])
with col1:
    st.metric("💰 Total Revenue", f"${revenue:,.3f}")
with col2:
    st.metric("📈 Total Profit", f"${profit:,.2f}")
with col3:
    st.metric("📊 Profit Margin", f"{margin:.2f}%")

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["🏠 Overview", "🏢 Division Analysis", "📦 Products", "📈 Advanced Analysis"])

# ==================== TAB 1: OVERVIEW ====================
with tab1:
    st.subheader("📋 Division Performance Overview")

    base_div = """
        SELECT Division,
               SUM(Sales)       AS Revenue,
               SUM(Gross_Profit) AS Profit,
               ROUND(SUM(Gross_Profit)*100/SUM(Sales), 2) AS Margin
        FROM sales
        GROUP BY Division
    """
    # FIX 2: original call was missing `all_values` argument → always filtered even when all selected
    div_query, div_params = build_filter_query(base_div, 'Division', selected_divisions, divisions)
    division = load_data(div_query, params=div_params if div_params else None)

    if not division.empty:
        st.dataframe(
            division,
            column_config={
                "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                "Profit":  st.column_config.NumberColumn("Profit",  format="$%.2f"),
                "Margin":  st.column_config.NumberColumn("Margin %", format="%.2f%%"),
            },
            use_container_width=True,
            hide_index=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            if view_mode == "Profit":
                fig1 = px.bar(division, x="Division", y="Profit",
                              title="Profit by Division", color="Profit",
                              color_continuous_scale="Greens", text_auto='.2s')
            else:
                fig1 = px.bar(division, x="Division", y="Margin",
                              title="Margin % by Division", color="Margin",
                              color_continuous_scale="Blues", text_auto='.2s')
            fig1.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#333")
            st.plotly_chart(fig1, use_container_width=True)

        with c2:
            fig2 = px.pie(division, values="Profit", names="Division",
                          title="Profit Distribution by Division",
                          hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#333")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("No data available for selected filters")

# ==================== TAB 2: DIVISION ANALYSIS ====================
with tab2:
    st.subheader("🏢 Detailed Division Analysis")

    div_list = division['Division'].tolist() if not division.empty else []
    selected_division = st.selectbox("Select Division for Detailed Analysis", div_list)

    if selected_division:
        # FIX 3: replaced f-string SQL injection with parameterised query
        div_detail_query = """
            SELECT Product_Name,
                   SUM(Sales)        AS Revenue,
                   SUM(Gross_Profit) AS Profit,
                   ROUND(SUM(Gross_Profit)*100/SUM(Sales), 2) AS Margin
            FROM sales
            WHERE Division = %s
            GROUP BY Product_Name
        """
        div_detail_query = div_detail_query + " ORDER BY Profit DESC"
        div_detail = load_data(div_detail_query, params=(selected_division,))

        if not div_detail.empty:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.dataframe(
                    div_detail,
                    column_config={
                        "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                        "Profit":  st.column_config.NumberColumn("Profit",  format="$%.2f"),
                        "Margin":  st.column_config.NumberColumn("Margin %", format="%.2f%%"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )
            with c2:
                total_rev  = div_detail['Revenue'].sum()
                total_prof = div_detail['Profit'].sum()
                avg_margin = div_detail['Margin'].mean()
                st.metric("Division Revenue", f"${total_rev:,.2f}")
                st.metric("Division Profit",  f"${total_prof:,.2f}")
                st.metric("Avg Margin",        f"{avg_margin:.2f}%")

            fig_tree = px.treemap(
                div_detail, path=['Product_Name'], values='Profit',
                title=f"Product Profit Treemap – {selected_division}",
                color='Profit', color_continuous_scale='RdYlGn'
            )
            fig_tree.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_tree, use_container_width=True)

            fig_hbar = px.bar(
                div_detail.head(10), x="Profit", y="Product_Name",
                orientation='h',
                title=f"Top 10 Products by Profit – {selected_division}",
                color="Profit", color_continuous_scale="Greens"
            )
            fig_hbar.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font_color="#333", yaxis={'categoryorder': 'total ascending'}
            )
            st.plotly_chart(fig_hbar, use_container_width=True)

# ==================== TAB 3: PRODUCTS ====================
with tab3:
    st.subheader("📦 Product Performance")

    base_prod = """
        SELECT Product_Name, Division,
               SUM(Sales)        AS Revenue,
               SUM(Gross_Profit) AS Profit,
               ROUND(SUM(Gross_Profit)*100/SUM(Sales), 2) AS Margin
        FROM sales
        GROUP BY Product_Name, Division
    """
    # FIX 4: chained filter calls now return (query, params) tuples properly
    prod_query, prod_params = build_filter_query(base_prod,      'Product_Name', selected_products, products)
    prod_query, prod_params = build_filter_query((prod_query, prod_params), 'Division',      selected_divisions, divisions)
    prod_query = prod_query + " ORDER BY Profit DESC"
    products_df = load_data(prod_query, params=prod_params if prod_params else None)

    if not products_df.empty:
        st.markdown("### 🏆 Top Products Leaderboard")

        sort_col, sort_dir = st.columns(2)
        with sort_col:
            sort_by = st.selectbox("Sort by", ["Profit", "Revenue", "Margin"])
        with sort_dir:
            ascending = st.toggle("Ascending", False)

        products_df = products_df.sort_values(by=sort_by, ascending=ascending)

        st.dataframe(
            products_df,
            column_config={
                "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                "Profit":  st.column_config.NumberColumn("Profit",  format="$%.2f"),
                "Margin":  st.column_config.NumberColumn("Margin %", format="%.2f%%"),
            },
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### 📊 Product Comparison")
        compare_metric = st.radio("Compare by:", ["Profit", "Revenue", "Margin"], horizontal=True)

        fig_prod = px.bar(
            products_df.head(15), x="Product_Name", y=compare_metric,
            title=f"Top 15 Products by {compare_metric}",
            color=compare_metric, color_continuous_scale="Viridis", text_auto='.2s'
        )
        fig_prod.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#333", xaxis_tickangle=-45
        )
        st.plotly_chart(fig_prod, use_container_width=True)

        st.markdown("### 🏢 Products by Division")
        div_prod = products_df.groupby('Division').agg(
            Product_Count=('Product_Name', 'count'),
            Total_Revenue=('Revenue', 'sum'),
            Total_Profit=('Profit', 'sum'),
            Avg_Margin=('Margin', 'mean')
        ).reset_index()
        div_prod.columns = ['Division', 'Product Count', 'Total Revenue', 'Total Profit', 'Avg Margin']

        st.dataframe(
            div_prod,
            column_config={
                "Total Revenue": st.column_config.NumberColumn("Revenue",    format="$%.2f"),
                "Total Profit":  st.column_config.NumberColumn("Profit",     format="$%.2f"),
                "Avg Margin":    st.column_config.NumberColumn("Avg Margin %", format="%.2f%%"),
            },
            use_container_width=True,
            hide_index=True,
        )

# ==================== TAB 4: ADVANCED ANALYSIS ====================
with tab4:
    st.subheader("📈 Advanced Analysis Tools")

    st.markdown("### 📉 Pareto Analysis (80/20 Rule)")

    base_pareto = """
        SELECT Product_Name, SUM(Gross_Profit) AS Profit
        FROM sales
        GROUP BY Product_Name
    """
    # FIX 5: original code appended raw ORDER BY after a filter, breaking SQL; fixed by chaining before ORDER BY
    pareto_query, pareto_params = build_filter_query(base_pareto, 'Product_Name', selected_products, products)
    pareto_query = pareto_query + " ORDER BY Profit DESC"
    pareto = load_data(pareto_query, params=pareto_params if pareto_params else None)

    if not pareto.empty:
        pareto["cum"] = pareto["Profit"].cumsum() / pareto["Profit"].sum() * 100

        fig_pareto = go.Figure()
        fig_pareto.add_trace(go.Bar(
            x=pareto["Product_Name"], y=pareto["Profit"],
            name="Profit", marker_color='steelblue'
        ))
        fig_pareto.add_trace(go.Scatter(
            x=pareto["Product_Name"], y=pareto["cum"],
            name="Cumulative %", yaxis='y2',
            line=dict(color='red', width=2)
        ))
        fig_pareto.update_layout(
            title="Pareto Profit Curve",
            xaxis_title="Products",
            yaxis_title="Profit ($)",
            # FIX 6: yaxis2 key was 'overlay' (wrong) → should be 'overlaying'
            yaxis2=dict(
                title="Cumulative %",
                overlaying='y',
                side='right',
                range=[0, 105]
            ),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#333", xaxis_tickangle=-45, hovermode="x unified"
        )
        fig_pareto.add_hline(y=80, line_dash="dash", line_color="orange",
                             annotation_text="80% Threshold", annotation_position="top right")
        st.plotly_chart(fig_pareto, use_container_width=True)

        products_80   = pareto[pareto["cum"] <= 80].shape[0]
        total_products = pareto.shape[0]
        pct = products_80 / total_products * 100 if total_products else 0
        st.info(f"📊 Insight: {products_80} out of {total_products} products ({pct:.1f}%) contribute to 80% of total profit")

    st.markdown("---")

    st.markdown("### 💰 Cost vs Sales Analysis")

    base_scatter = "SELECT Cost, Sales, Product_Name, Division FROM sales"
    scatter_query, scatter_params = build_filter_query(base_scatter, 'Product_Name', selected_products, products)
    scatter_query, scatter_params = build_filter_query((scatter_query, scatter_params), 'Division', selected_divisions, divisions)
    scatter = load_data(scatter_query, params=scatter_params if scatter_params else None)

    if not scatter.empty:
        correlation = scatter['Cost'].corr(scatter['Sales'])

        col1, col2 = st.columns([3, 1])
        with col1:
            # Convert Cost and Sales to numeric (IMPORTANT FIX)
            scatter["Cost"] = pd.to_numeric(scatter["Cost"], errors="coerce")
            scatter["Sales"] = pd.to_numeric(scatter["Sales"], errors="coerce")
            scatter = scatter.dropna(subset=["Cost","Sales"])

            fig_scatter = px.scatter(
                scatter,
                x="Cost",
                y="Sales",
                title="Cost vs Sales Scatter Plot",
                color="Division",
                size="Sales",
                hover_data=["Product_Name"],
                color_discrete_sequence=px.colors.qualitative.Set1,
                trendline="ols"
            )
            fig_scatter.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#333"
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        with col2:
            st.metric("Correlation", f"{correlation:.3f}")
            if correlation > 0.7:
                st.success("Strong positive correlation")
            elif correlation > 0.4:
                st.info("Moderate positive correlation")
            else:
                st.warning("Weak correlation")

    st.markdown("---")

    st.markdown("### 📊 Profit Margin Distribution")

    base_margin_dist = """
        SELECT Division,
               ROUND(SUM(Gross_Profit)*100/SUM(Sales), 2) AS Margin
        FROM sales
        GROUP BY Division
    """
    margin_query, margin_params = build_filter_query(base_margin_dist, 'Division', selected_divisions, divisions)
    margin_dist = load_data(margin_query, params=margin_params if margin_params else None)

    if not margin_dist.empty:
        # FIX 7: box plot on aggregated data (one row per division) makes no statistical sense;
        # switched to a bar chart which is meaningful for this aggregated result.
        fig_margin = px.bar(
            margin_dist, x="Division", y="Margin",
            title="Profit Margin by Division",
            color="Division",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            text_auto='.2f'
        )
        fig_margin.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#333"
        )
        st.plotly_chart(fig_margin, use_container_width=True)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "📊 Nassau Dashboard | Powered by Streamlit | Last Updated: "
    + datetime.now().strftime("%Y-%m-%d %H:%M:%S") +
    "</div>",
    unsafe_allow_html=True
)
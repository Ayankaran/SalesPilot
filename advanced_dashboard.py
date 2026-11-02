
import io
import html

import pandas as pd
import plotly.express as px
import streamlit as st
from pdf_report import create_pdf_report

def show_advanced_dashboard(valid):
    """Interactive dashboard using validated sales records."""

    st.subheader("8. Advanced Sales Analytics")

    data = valid.copy()
    data["Date"] = pd.to_datetime(data["Date"])
    data["Revenue"] = pd.to_numeric(data["Revenue"])

    # ===== INTERACTIVE FILTERS =====

    st.write("### Filter Sales Data")

    min_date = data["Date"].min().date()
    max_date = data["Date"].max().date()

    selected_dates = st.date_input(
        "Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="advanced_dates"
    )

    products = sorted(data["Product"].dropna().unique())

    selected_products = st.multiselect(
        "Select products",
        options=products,
        default=products,
        key="advanced_products"
    )

    if len(selected_dates) != 2:
        st.info("Select a start and end date.")
        return

    start_date, end_date = selected_dates

    filtered = data[
        (data["Date"].dt.date >= start_date)
        & (data["Date"].dt.date <= end_date)
        & (data["Product"].isin(selected_products))
    ].copy()

    if filtered.empty:
        st.warning("No sales records match these filters.")
        return

    # ===== KPIs =====

    revenue = filtered["Revenue"].sum()
    records = len(filtered)
    avg_record = revenue / records

    a, b, c = st.columns(3)

    a.metric("Total Revenue", f"₹{revenue:,.2f}")
    b.metric("Sales Records", f"{records:,}")
    c.metric("Average Record Value", f"₹{avg_record:,.2f}")

    if "Quantity" in filtered.columns:
        qty = pd.to_numeric(
            filtered["Quantity"], errors="coerce"
        )
        if qty.notna().all():
            st.metric("Units Sold", f"{qty.sum():,.0f}")

    # ===== MONTHLY TREND =====

    filtered["Month"] = (
        filtered["Date"].dt.to_period("M").astype(str)
    )

    monthly = (
        filtered.groupby("Month", as_index=False)["Revenue"]
        .sum()
        .sort_values("Month")
    )

    st.plotly_chart(
        px.line(
            monthly,
            x="Month",
            y="Revenue",
            markers=True,
            title="Monthly Revenue Trend"
        ),
        use_container_width=True
    )

    # ===== PRODUCT PERFORMANCE =====

    product_sales = (
        filtered.groupby("Product", as_index=False)["Revenue"]
        .sum()
        .sort_values("Revenue", ascending=False)
    )

    st.plotly_chart(
        px.bar(
            product_sales.head(10),
            x="Product",
            y="Revenue",
            title="Top 10 Products by Revenue"
        ),
        use_container_width=True
    )

    # ===== PRODUCT CONTRIBUTION =====

    st.plotly_chart(
        px.pie(
            product_sales.head(10),
            names="Product",
            values="Revenue",
            title="Revenue Contribution — Top 10 Products"
        ),
        use_container_width=True
    )

    # ===== EXPORT DATA =====

    st.write("### Export Analytics")

    excel_buffer = io.BytesIO()

    with pd.ExcelWriter(
        excel_buffer, engine="openpyxl"
    ) as writer:
        filtered.to_excel(
            writer, sheet_name="Filtered Sales", index=False
        )
        monthly.to_excel(
            writer, sheet_name="Monthly Revenue", index=False
        )
        product_sales.to_excel(
            writer, sheet_name="Product Performance", index=False
        )

        kpis = pd.DataFrame({
            "Metric": [
                "Total Revenue",
                "Sales Records",
                "Average Record Value"
            ],
            "Value": [revenue, records, avg_record]
        })

        kpis.to_excel(
            writer, sheet_name="KPIs", index=False
        )

    st.download_button(
        "Download Excel Analytics Report",
        data=excel_buffer.getvalue(),
        file_name="SalesPilot_Analytics.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )

    # ===== HTML REPORT =====

    top_rows = product_sales.head(10)
    product_table = top_rows.to_html(
        index=False, escape=True
    )
    monthly_table = monthly.to_html(
        index=False, escape=True
    )

    report = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <title>SalesPilot Analytics Report</title>
    <style>
      body {{font-family:Arial,sans-serif;
             margin:40px;color:#222;}}
      h1 {{color:#2457a7;}}
      table {{border-collapse:collapse;width:100%;
              margin-bottom:30px;}}
      th,td {{border:1px solid #ddd;
              padding:9px;text-align:left;}}
      th {{background:#f0f3f8;}}
    </style>
    </head>
    <body>
      <h1>SalesPilot Analytics Report</h1>
      <p>Period: {start_date} to {end_date}</p>
      <h2>Sales Summary</h2>
      <p>Total Revenue: ₹{revenue:,.2f}</p>
      <p>Sales Records: {records:,}</p>
      <p>Average Record Value: ₹{avg_record:,.2f}</p>
      <h2>Monthly Revenue</h2>
      {monthly_table}
      <h2>Top Products</h2>
      {product_table}
      <p>All statistics are based on filtered,
      validated sales records.</p>
    </body>
    </html>
    """

    st.download_button(
        "Download Printable Business Report",
        data=report.encode("utf-8"),
        file_name="SalesPilot_Business_Report.html",
        mime="text/html"
    )

    # ===== PDF EXPORT WITH CHARTS =====

    pdf_data = create_pdf_report(
        filtered,
        monthly,
        product_sales
    )

    st.download_button(
        label="Download PDF Report with Charts",
        data=pdf_data,
        file_name="SalesPilot_Analytics_Report.pdf",
        mime="application/pdf"
    )

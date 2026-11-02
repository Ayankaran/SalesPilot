import re
import pandas as pd
import plotly.express as px
import streamlit as st
from data_processing import (
    run_eda,
    preprocess_sales,
    analyze_missing_values,
    detect_outliers,
    generate_quality_report,
    generate_business_insights,
    create_ai_summary
)
from ai_assistant import ask_ai
from advanced_dashboard import show_advanced_dashboard
from pdf_report import create_pdf_report




st.set_page_config(page_title='SalesPilot', page_icon='📊', layout='wide')
if "show_dashboard" not in st.session_state:
    st.session_state.show_dashboard = False

if "previous_file_id" not in st.session_state:
    st.session_state.previous_file_id = None
st.title('📊 SalesPilot')
st.caption('Upload sales data → explore quality → clean → build dashboard')

ALIASES = {
    'date': ['date', 'sales date', 'sale date', 'order date', 'transaction date'],
    'product': ['product', 'product name', 'item', 'item name', 'sku', 'product description'],
    'quantity': ['quantity', 'qty', 'qty sold', 'units', 'units sold', 'order quantity'],
    'unit_price': ['unit price', 'price per unit', 'selling price', 'unit selling price', 'rate'],
    'total_amount': ['revenue', 'total revenue', 'sales amount', 'total amount', 'total sales', 'line total', 'amount', 'sales value'],
}


def normalize(name):
    return re.sub(r'[^a-z0-9]+', ' ', str(name).lower()).strip()


def detect_column(columns, role):
    aliases = {normalize(name) for name in ALIASES[role]}
    return next((col for col in columns if normalize(col) in aliases), None)


def select_column(label, columns, guess, key, required=True):
    options = (['-- Select --'] if required else ['-- None --']) + columns
    index = options.index(guess) if guess in options else 0
    result = st.selectbox(label, options, index=index, key=key)
    return result if result in columns else None


upload = st.file_uploader('Upload a CSV or Excel sales file', type=['csv', 'xlsx'])
import hashlib

if upload is not None:
    file_id = hashlib.sha256(upload.getvalue()).hexdigest()

    if st.session_state.previous_file_id != file_id:
        st.session_state.previous_file_id = file_id
        st.session_state.show_dashboard = False
else:
    st.session_state.previous_file_id = None
    st.session_state.show_dashboard = False
if upload is None:
    st.info('Upload a file to begin. Sample columns: Date, Product, Quantity, Unit Price.')
    st.stop()

try:
    if upload.name.lower().endswith('.csv'):
        df = pd.read_csv(upload)
    else:
        sheets = pd.read_excel(upload, sheet_name=None)
        sheet = st.selectbox('Worksheet', list(sheets))
        df = sheets[sheet]
except Exception as exc:
    st.error(f'Unable to read this file: {exc}')
    st.stop()

if df.empty or not len(df.columns):
    st.error('This sheet has no usable rows or columns.')
    st.stop()
if df.columns.duplicated().any():
    st.error('Some column headers are repeated. Rename them before uploading.')
    st.stop()

st.subheader('1. Raw data and automated EDA')
st.dataframe(df.head(15), use_container_width=True)
summary, missing, numeric_stats = run_eda(df)
missing_values = analyze_missing_values(df)
a, b, c, d = st.columns(4)
a.metric('Rows', f"{summary['rows']:,}")
b.metric('Columns', summary['columns'])
c.metric('Exact duplicate rows', summary['duplicate_rows'])
d.metric('Missing cells', summary['missing_cells'])
st.dataframe(missing, use_container_width=True, hide_index=True)

    # Missing-value visualization
missing_analysis = analyze_missing_values(df)

st.write("### Missing Value Visualization")

fig_missing = px.bar(
    missing_analysis,
    x="Column",
    y="Missing Percentage",
    title="Missing Values by Column",
    text="Missing Percentage"
)

st.plotly_chart(
    fig_missing,
    use_container_width=True
)

if not numeric_stats.empty:
    with st.expander('Numeric descriptive statistics'):
        st.dataframe(numeric_stats, use_container_width=True)
st.caption('Duplicates are reported, not automatically deleted: legitimate transactions can look identical.')

st.subheader('2. Confirm column mapping')
cols = list(df.columns)
date_col = select_column('Sales date', cols, detect_column(cols, 'date'), 'map_date')
product_col = select_column('Product / item', cols, detect_column(cols, 'product'), 'map_product')
qty_col = select_column('Quantity (optional when total revenue is provided)', cols,
                        detect_column(cols, 'quantity'), 'map_quantity', required=False)
total_guess = detect_column(cols, 'total_amount')
price_guess = detect_column(cols, 'unit_price')
mode = st.radio('How is revenue represented?', ['Unit price × quantity', 'Total sales amount'],
                index=1 if total_guess else 0, horizontal=True)
amount_col = select_column('Unit price' if mode.startswith('Unit') else 'Total sales amount',
                           cols, price_guess if mode.startswith('Unit') else total_guess, 'map_amount')
date_order = st.radio('Date order for text dates', ['Day first (DD/MM/YYYY)', 'Month first (MM/DD/YYYY)'],
                      horizontal=True)

if st.button('Run preprocessing and generate dashboard', type='primary'):
    st.session_state.show_dashboard = True

if not st.session_state.show_dashboard:
    st.stop()

required_cols = [date_col, product_col, amount_col]
if mode.startswith('Unit'):
    required_cols.append(qty_col)
if any(col is None for col in required_cols):
    st.error('Select the date, product, amount and (if using unit price) quantity columns.')
    st.stop()
selected_cols = required_cols + ([qty_col] if qty_col and not mode.startswith('Unit') else [])
if len(selected_cols) != len(set(selected_cols)):
    st.error('Each mapped field must use a different source column.')
    st.stop()

valid, rejected = preprocess_sales(
    df=df, date_col=date_col, product_col=product_col,
    amount_col=amount_col, qty_col=qty_col,
    amount_type='unit_price' if mode.startswith('Unit') else 'total_amount',
    dayfirst=date_order.startswith('Day')
)

st.subheader('3. Preprocessing and data quality')
a, b, c = st.columns(3)
a.metric('Accepted rows', len(valid))
b.metric('Rejected rows', len(rejected))
c.metric('Acceptance rate', f'{len(valid) / len(df):.1%}')
if not rejected.empty:
    st.warning('Some rows have missing/invalid dates, products or amounts, or negative revenue. Review them: returns and credit notes may be valid business transactions.')
    st.dataframe(rejected.head(50), use_container_width=True)
    st.download_button('Download rejected rows', rejected.to_csv(index=False).encode('utf-8-sig'),
                       'salespilot_rejected.csv', 'text/csv')
st.download_button('Download cleaned rows', valid.to_csv(index=False).encode('utf-8-sig'),
                   'salespilot_cleaned.csv', 'text/csv')
if valid.empty:
    st.error('No valid records remain. Check your mapping and source data.')
    st.stop()



# ===== OUTLIER DETECTION =====

st.subheader("Outlier Detection")

outliers, lower, upper = detect_outliers(valid, "Revenue")

if lower is None:
    st.info("Not enough data for outlier detection.")
else:
    a, b, c = st.columns(3)

    a.metric("Outliers Detected", len(outliers))
    b.metric("Lower Bound", f"₹{lower:,.2f}")
    c.metric("Upper Bound", f"₹{upper:,.2f}")

    fig_outliers = px.box(
        valid,
        y="Revenue",
        points="all",
        title="Sales Revenue Outlier Analysis"
    )

    st.plotly_chart(
        fig_outliers,
        use_container_width=True
    )

    if not outliers.empty:
        st.warning(
            f"{len(outliers)} unusual transactions detected."
        )

        st.dataframe(
            outliers,
            use_container_width=True
        )

        st.download_button(
            "Download Outlier Records",
            data=outliers.to_csv(index=False),
            file_name="salespilot_outliers.csv",
            mime="text/csv"
        )
    else:
        st.success("No outliers detected.")




# ===== DATA QUALITY REPORT =====

st.subheader("Download Data Quality Report")

quality_report = generate_quality_report(
    df, valid, rejected, outliers
)

st.download_button(
    label="Download Data Quality Report",
    data=quality_report.encode("utf-8"),
    file_name="SalesPilot_Data_Quality_Report.html",
    mime="text/html"
)

# ===== END DATA QUALITY REPORT =====





st.subheader('4. Sales dashboard')
revenue = valid['Revenue'].sum()
rows = len(valid)
a, b, c = st.columns(3)
a.metric('Total revenue', f'₹{revenue:,.2f}')
b.metric('Sales records', f'{rows:,}')
c.metric('Avg. sales record value', f'₹{revenue / rows:,.2f}')
if qty_col:
    st.metric('Units sold', f"{valid['Quantity'].sum():,.0f}")

daily = valid.assign(Day=valid['Date'].dt.date).groupby('Day', as_index=False)['Revenue'].sum()
products = valid.groupby('Product', as_index=False)['Revenue'].sum().sort_values('Revenue', ascending=False)
st.plotly_chart(px.line(daily, x='Day', y='Revenue', markers=True, title='Daily sales trend'),
                use_container_width=True)
st.plotly_chart(px.bar(products.head(10), x='Product', y='Revenue', title='Top 10 products by revenue'),
                use_container_width=True)


# ===== AUTOMATED BUSINESS INSIGHTS =====

st.subheader("5. Automatic Business Insights")

insights = generate_business_insights(valid)

for i, insight in enumerate(insights, start=1):
    st.info(f"{i}. {insight}")

# ===== END AUTOMATED BUSINESS INSIGHTS =====


# ===== AI DATA SUMMARY =====

st.subheader("6. AI-Ready Business Summary")

ai_summary = create_ai_summary(valid)

with st.expander("View calculated business data"):
    st.json(ai_summary)

# ===== END AI DATA SUMMARY =====


# ===== ADVANCED SALES DASHBOARD =====

show_advanced_dashboard(valid)

# ===== END ADVANCED DASHBOARD =====








# ===== AI BUSINESS ANALYST =====
st.subheader("7. AI Business Analyst")

st.caption(
    "Prototype: use synthetic data only. "
    "Summary statistics are sent to an external AI API."
)

ai_enabled = st.checkbox(
    "Enable external AI analysis for this test dataset"
)

if ai_enabled:
    try:
        api_key = st.secrets.get("GROQ_API_KEY", "")
    except FileNotFoundError:
        api_key = ""

    if not api_key:
        st.warning("Add GROQ_API_KEY to secrets.toml.")
    else:
        model_name = st.text_input(
            "Groq model",
            value="openai/gpt-oss-20b",
            help="Use a model available to your API key."
        )

        question = st.text_input(
            "Ask a question about your sales",
            placeholder="Which products generate the most revenue?"
        )

        if st.button("Ask SalesPilot AI"):
            if not question.strip():
                st.warning("Please enter a question.")
            else:
                with st.spinner("Analyzing sales data..."):
                    try:
                        answer = ask_ai(
                            question,
                            ai_summary,
                            api_key,
                            model_name
                        )

                        st.markdown(answer)

                    except Exception as error:
                        st.error(
                            "The AI request failed. "
                            "Check your API key, model access "
                            "and free-tier quota."
                        )

# ===== END AI BUSINESS ANALYST =====


import pandas as pd


def run_eda(df):
    missing = pd.DataFrame({
        'Column': df.columns,
        'Missing Values': df.isna().sum().values,
        'Missing %': (df.isna().mean().values * 100).round(2),
        'Data Type': df.dtypes.astype(str).values,
        'Unique Values': [df[col].nunique(dropna=True) for col in df.columns]
    })
    summary = {'rows': len(df), 'columns': len(df.columns),
               'duplicate_rows': int(df.duplicated().sum()),
               'missing_cells': int(df.isna().sum().sum())}
    numeric_stats = df.describe(include='number').transpose()
    return summary, missing, numeric_stats



def analyze_missing_values(df):
    """Calculate missing values for each column."""

    missing = df.isna().sum()

    missing_df = pd.DataFrame({
        "Column": df.columns,
        "Missing Count": missing.values,
        "Missing Percentage": (
            df.isna().mean().values * 100
        ).round(2)
    })

    return missing_df




def preprocess_sales(df, date_col, product_col, amount_col, qty_col=None,
                     amount_type='unit_price', dayfirst=True):
    data = df.copy()
    data['Date'] = pd.to_datetime(df[date_col], errors='coerce', dayfirst=dayfirst)
    data['Product'] = df[product_col].astype('string').str.strip().replace('', pd.NA)

    def to_number(series):
        cleaned = series.astype('string').str.replace(r'[₹$,\s]', '', regex=True)
        return pd.to_numeric(cleaned, errors='coerce')

    amount = to_number(df[amount_col])
    data['Quantity'] = to_number(df[qty_col]) if qty_col else pd.Series(pd.NA, index=df.index, dtype='Float64')
    data['Revenue'] = amount * data['Quantity'] if amount_type == 'unit_price' else amount
    invalid = data['Date'].isna() | data['Product'].isna() | data['Revenue'].isna() | (data['Revenue'] < 0)
    if amount_type == 'unit_price':
        invalid = invalid | data['Quantity'].isna() | (data['Quantity'] <= 0)
    valid, rejected = data.loc[~invalid.fillna(True)].copy(), data.loc[invalid.fillna(True)].copy()
    return valid, rejected



def detect_outliers(df, column="Revenue"):
    """Detect outliers using the IQR method."""

    if column not in df.columns:
        return pd.DataFrame(), None, None

    values = pd.to_numeric(
        df[column], errors="coerce"
    ).dropna()

    if len(values) < 4:
        return pd.DataFrame(), None, None

    Q1 = values.quantile(0.25)
    Q3 = values.quantile(0.75)

    IQR = Q3 - Q1

    if IQR == 0:
        return pd.DataFrame(), None, None

    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR

    outliers = df[
        (pd.to_numeric(df[column], errors="coerce") < lower_bound)
        | (pd.to_numeric(df[column], errors="coerce") > upper_bound)
    ].copy()

    return outliers, lower_bound, upper_bound



def generate_quality_report(
    df, valid, rejected, outliers
):
    """Generate an HTML data quality report."""

    total_rows = len(df)
    accepted = len(valid)
    rejected_count = len(rejected)

    acceptance_rate = (
        accepted / total_rows * 100
        if total_rows else 0
    )

    missing = df.isna().sum()
    duplicates = df.duplicated().sum()

    missing_table = pd.DataFrame({
        "Column": df.columns,
        "Missing Values": missing.values,
        "Missing %": (
            df.isna().mean().values * 100
        ).round(2)
    })

    html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>SalesPilot Data Quality Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                color: #222;
            }}
            h1 {{ color: #2457a7; }}
            h2 {{ margin-top: 30px; }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{ background: #f0f3f8; }}
            .metric {{
                padding: 12px;
                background: #f5f7fa;
                margin: 8px 0;
            }}
        </style>
    </head>
    <body>
        <h1>SalesPilot Data Quality Report</h1>

        <h2>Dataset Overview</h2>
        <div class="metric">Total Rows: {total_rows}</div>
        <div class="metric">Accepted Rows: {accepted}</div>
        <div class="metric">Rejected Rows: {rejected_count}</div>
        <div class="metric">
            Acceptance Rate: {acceptance_rate:.1f}%
        </div>

        <h2>Data Quality Findings</h2>
        <div class="metric">Duplicate Rows: {duplicates}</div>
        <div class="metric">
            Outlier Transactions: {len(outliers)}
        </div>

        <h2>Missing Value Analysis</h2>
        {missing_table.to_html(index=False, escape=True)}

        <h2>Notes</h2>
        <p>
        Duplicate records and statistical outliers
        are flagged, not automatically deleted.
        Rejected records failed sales validation.
        </p>
    </body>
    </html>
    """

    return html




def generate_business_insights(df):
    """Generate automatic insights from cleaned sales data."""

    insights = []

    if df.empty:
        return ["No valid sales data available."]

    # 1. Total revenue
    total_revenue = df["Revenue"].sum()

    insights.append(
        f"Total sales revenue is ₹{total_revenue:,.2f}."
    )

    # 2. Product performance
    product_sales = (
        df.groupby("Product")["Revenue"]
        .sum()
        .sort_values(ascending=False)
    )

    if not product_sales.empty:
        top_product = product_sales.index[0]
        top_revenue = product_sales.iloc[0]

        contribution = (
            top_revenue / total_revenue * 100
            if total_revenue > 0 else 0
        )

        insights.append(
            f"{top_product} is the highest revenue-generating "
            f"product, contributing {contribution:.1f}% "
            "of total sales."
        )

    # 3. Monthly revenue trend
    monthly_sales = (
        df.assign(
            Month=df["Date"].dt.to_period("M")
        )
        .groupby("Month")["Revenue"]
        .sum()
        .sort_index()
    )

    if len(monthly_sales) >= 2:
        previous = monthly_sales.iloc[-2]
        current = monthly_sales.iloc[-1]

        previous_month = str(monthly_sales.index[-2])
        current_month = str(monthly_sales.index[-1])

        if previous > 0:
            growth = (
                (current - previous) / previous * 100
            )

            if growth > 0:
                trend = "increased"
            elif growth < 0:
                trend = "decreased"
            else:
                trend = "remained unchanged"

            insights.append(
                f"Recorded sales {trend} by "
                f"{abs(growth):.1f}% from "
                f"{previous_month} to {current_month}."
            )

            # Flag incomplete final months
            latest_date = df["Date"].max()
            if latest_date.day < latest_date.days_in_month:
                insights.append(
                    f"Note: {current_month} may be incomplete. "
                    "The monthly comparison may not be like-for-like."
                )

    # 4. Revenue concentration
    if total_revenue > 0 and len(product_sales) >= 3:
        top_three_share = (
            product_sales.head(3).sum()
            / total_revenue * 100
        )

        insights.append(
            f"The top three products contribute "
            f"{top_three_share:.1f}% of total revenue."
        )

    return insights



def create_ai_summary(df):
    """Prepare calculated sales metrics for AI analysis."""

    if df.empty:
        return {}

    total_revenue = float(df["Revenue"].sum())

    product_sales = (
        df.groupby("Product")["Revenue"]
        .sum()
        .sort_values(ascending=False)
    )

    monthly_sales = (
        df.assign(
            Month=df["Date"].dt.to_period("M")
        )
        .groupby("Month")["Revenue"]
        .sum()
        .sort_index()
    )

    return {
        "total_revenue": round(total_revenue, 2),
        "sales_records": len(df),
        "top_products": [
            {
                "product": str(product),
                "revenue": round(float(revenue), 2)
            }
            for product, revenue
            in product_sales.head(5).items()
        ],
        "monthly_revenue": {
            str(month): round(float(revenue), 2)
            for month, revenue in monthly_sales.items()
        }
    }

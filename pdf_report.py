
import io
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    KeepTogether
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape


def create_pdf_report(filtered, monthly, product_sales):
    """Create a PDF containing sales KPIs and charts."""

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()
    styles["Title"].alignment = TA_CENTER

    story = []

    def text(value, style="Normal"):
        story.append(
            Paragraph(str(value), styles[style])
        )

    def chart_image(fig):
        """Convert a Matplotlib chart to a PDF image."""

        image_buffer = io.BytesIO()

        fig.savefig(
            image_buffer,
            format="png",
            dpi=160,
            bbox_inches="tight"
        )

        plt.close(fig)
        image_buffer.seek(0)

        image = Image(
            image_buffer,
            width=480,
            height=260
        )

        # Keep image bytes available during PDF building
        image._salespilot_buffer = image_buffer
        return image

    # ===== REPORT TITLE =====

    text("SalesPilot", "Title")
    text("Sales Performance Analytics Report", "Heading2")

    story.append(Spacer(1, 18))

    # ===== EXECUTIVE SUMMARY =====

    revenue = float(filtered["Revenue"].sum())
    records = len(filtered)
    average = revenue / records if records else 0

    text("1. Executive Summary", "Heading2")

    text(f"Total Revenue: INR {revenue:,.2f}")
    text(f"Sales Records: {records:,}")
    text(f"Average Record Value: INR {average:,.2f}")

    start = filtered["Date"].min().date()
    end = filtered["Date"].max().date()

    text(f"Reporting Period: {start} to {end}")

    story.append(Spacer(1, 18))

    # ===== MONTHLY REVENUE CHART =====

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.plot(
        monthly["Month"],
        monthly["Revenue"],
        marker="o",
        linewidth=2
    )

    ax.set_title("Monthly Revenue Trend")
    ax.set_ylabel("Revenue (INR)")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(alpha=0.2)

    fig.tight_layout()

    story.append(
        KeepTogether([
            Paragraph(
                "2. Monthly Revenue Trend",
                styles["Heading2"]
            ),
            chart_image(fig)
        ])
    )

    story.append(Spacer(1, 12))

    # ===== TOP PRODUCTS BAR CHART =====

    top = product_sales.head(10).iloc[::-1]

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.barh(
        top["Product"].astype(str),
        top["Revenue"]
    )

    ax.set_title("Top Products by Revenue")
    ax.set_xlabel("Revenue (INR)")

    fig.tight_layout()

    story.append(
        KeepTogether([
            Paragraph(
                "3. Product Performance",
                styles["Heading2"]
            ),
            chart_image(fig)
        ])
    )

    story.append(Spacer(1, 12))

    # ===== REVENUE CONTRIBUTION =====

    top_products = product_sales.head(10).copy()

    remaining = (
        product_sales["Revenue"].sum()
        - top_products["Revenue"].sum()
    )

    if remaining > 0:
        import pandas as pd

        top_products = pd.concat([
            top_products,
            pd.DataFrame([{
                "Product": "Other",
                "Revenue": remaining
            }])
        ], ignore_index=True)

    positive = top_products[
        top_products["Revenue"] > 0
    ]

    if not positive.empty:
        fig, ax = plt.subplots(figsize=(8, 4))

        ax.pie(
            positive["Revenue"],
            labels=positive["Product"].astype(str),
            autopct="%1.1f%%",
            startangle=90,
            textprops={"fontsize": 8}
        )

        ax.set_title("Revenue Contribution")
        fig.tight_layout()

        story.append(
            KeepTogether([
                Paragraph(
                    "4. Revenue Contribution",
                    styles["Heading2"]
                ),
                chart_image(fig)
            ])
        )

    story.append(Spacer(1, 12))

    # ===== BUSINESS INSIGHTS =====

    text("5. Business Insights", "Heading2")

    top_product = product_sales.iloc[0]

    share = (
        top_product["Revenue"] / revenue * 100
        if revenue > 0 else 0
    )

    safe_name = escape(str(top_product["Product"]))

    text(
        f"The highest-revenue product is "
        f"{safe_name}, contributing "
        f"{share:.1f}% of total revenue."
    )

    if len(monthly) >= 2:
        previous = monthly.iloc[-2]["Revenue"]
        current = monthly.iloc[-1]["Revenue"]

        if previous > 0:
            change = (current - previous) / previous * 100

            text(
                f"Revenue changed by {change:+.1f}% "
                "between the last two recorded months. "
                "Check whether both periods contain "
                "complete and comparable sales data."
            )

    story.append(Spacer(1, 12))

    text(
        "Generated by SalesPilot using filtered, "
        "validated sales records."
    )

    doc.build(story)

    buffer.seek(0)
    return buffer.getvalue()

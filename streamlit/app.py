"""Olist analytics dashboard.

Reads ONLY the dbt marts (schema `marts`). All business logic lives in dbt;
this app just queries the finished tables and draws them.
"""

import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Olist Analytics", page_icon="📦", layout="wide")

# Chart colours (one hue per job; see README).
BLUE = "#2a78d6"     # single-series default
ORANGE = "#eb6834"   # second category (late orders)
MUTED = "#898781"    # reference lines
PLOTLY_CONFIG = {"displayModeBar": False}


# --------------------------------------------------------------------------- data

@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    """Run a read-only query, cached for 10 minutes."""
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn)


def marts_ready() -> bool:
    """True when dbt has built the marts this app depends on."""
    needed = {
        "fct_orders", "fct_order_items", "dim_products", "dim_customers",
        "monthly_revenue", "delivery_delay_by_state", "top_sellers", "customer_repeat_rate",
    }
    found = query(
        "select table_name from information_schema.tables where table_schema = 'marts'"
    )
    missing = needed - set(found["table_name"])
    if missing:
        st.error(
            "These dbt marts are missing: " + ", ".join(sorted(missing))
            + ".\n\nBuild them first: `docker compose run --rm --no-deps dbt dbt build`"
        )
    return not missing


def style(fig: go.Figure, height: int = 380) -> go.Figure:
    """Shared chart look: no title (Streamlit headers do that), light grid, tight margins."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        hovermode="closest",
        showlegend=False,
        bargap=0.25,
    )
    fig.update_xaxes(title=None, showgrid=False)
    fig.update_yaxes(title=None)
    return fig


def brl(value: float) -> str:
    """Format Brazilian reais compactly: R$1.17M, R$85.3K."""
    if value >= 1_000_000:
        return f"R${value / 1_000_000:,.2f}M"
    if value >= 1_000:
        return f"R${value / 1_000:,.1f}K"
    return f"R${value:,.0f}"


# ----------------------------------------------------------------------- layout

st.title("Olist E-Commerce Analytics")
st.caption(
    "Brazilian marketplace orders, 2016–2018. Built from the dbt marts in Postgres; "
    "canceled and unavailable orders are excluded from revenue."
)

try:
    ready = marts_ready()
except Exception as exc:  # database not reachable
    st.error(f"Could not connect to Postgres: {exc}")
    st.stop()
if not ready:
    st.stop()

# ---------------------------------------------------------------- headline KPIs

kpi = query("""
    select
        (select sum(revenue)     from marts.monthly_revenue)      as revenue,
        (select sum(order_count) from marts.monthly_revenue)      as orders,
        (select round(avg(review_score), 2) from marts.fct_orders) as avg_review,
        (select round(100.0 * avg(is_late::int), 1)
           from marts.fct_orders where delivered_at is not null)   as late_pct,
        (select repeat_rate_pct from marts.customer_repeat_rate)   as repeat_rate
""").iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Revenue", brl(kpi.revenue))
c2.metric("Orders", f"{int(kpi.orders):,}")
c3.metric("Avg review", f"{kpi.avg_review} ★")
c4.metric("Delivered late", f"{kpi.late_pct}%")
c5.metric("Repeat customers", f"{kpi.repeat_rate}%")

tab_rev, tab_del, tab_sel, tab_cust = st.tabs(
    ["📈 Revenue", "🚚 Delivery", "🏪 Sellers", "👥 Customers"]
)

# ---------------------------------------------------------------------- revenue

with tab_rev:
    st.subheader("How is revenue trending month over month?")

    monthly = query("select * from marts.monthly_revenue order by month")
    monthly["month"] = pd.to_datetime(monthly["month"])

    # The first and last months only hold a handful of orders; hide them by default
    # so they don't distort the trend.
    full_only = st.toggle("Hide partial months (fewer than 100 orders)", value=True)
    view = monthly[monthly["order_count"] >= 100] if full_only else monthly

    measure = st.radio(
        "Measure", ["Revenue", "Orders", "Average order value"], horizontal=True
    )
    column = {"Revenue": "revenue", "Orders": "order_count",
              "Average order value": "avg_order_value"}[measure]

    fig = px.bar(
        view, x="month", y=column,
        custom_data=["revenue", "order_count", "avg_order_value", "revenue_growth_pct"],
    )
    fig.update_traces(
        marker_color=BLUE,
        hovertemplate=(
            "<b>%{x|%b %Y}</b><br>"
            "Revenue: R$%{customdata[0]:,.0f}<br>"
            "Orders: %{customdata[1]:,}<br>"
            "Avg order: R$%{customdata[2]:,.2f}<br>"
            "Growth vs prev. month: %{customdata[3]}%<extra></extra>"
        ),
    )
    fig.update_xaxes(dtick="M2", tickformat="%b\n%Y")
    if column != "order_count":
        fig.update_yaxes(tickprefix="R$")
    st.plotly_chart(style(fig), width="stretch", config=PLOTLY_CONFIG)

    best = view.loc[view["revenue"].idxmax()]
    st.info(
        f"**Peak month:** {best.month:%B %Y} with {brl(best.revenue)} "
        f"({best.revenue_growth_pct:+.0f}% on the month before) - Black Friday."
    )

    st.subheader("Which categories earn the most?")
    top_n = st.slider("Number of categories", 5, 30, 15)
    categories = query(f"""
        select p.category_name,
               sum(i.price)              as revenue,
               count(*)                  as items_sold,
               count(distinct i.order_id) as orders
        from marts.fct_order_items as i
        join marts.dim_products   as p on i.product_id = p.product_id
        where i.order_status not in ('canceled', 'unavailable')
        group by p.category_name
        order by revenue desc
        limit {int(top_n)}
    """)
    fig = px.bar(
        categories.sort_values("revenue"), x="revenue", y="category_name",
        orientation="h", custom_data=["items_sold", "orders"],
    )
    fig.update_traces(
        marker_color=BLUE,
        hovertemplate=(
            "<b>%{y}</b><br>Revenue: R$%{x:,.0f}<br>"
            "Items sold: %{customdata[0]:,}<br>Orders: %{customdata[1]:,}<extra></extra>"
        ),
    )
    fig.update_xaxes(tickprefix="R$", showgrid=True)
    st.plotly_chart(style(fig, height=max(300, 26 * top_n)),
                    width="stretch", config=PLOTLY_CONFIG)
    st.caption("Category revenue is item price only (no freight), from `fct_order_items`.")

# --------------------------------------------------------------------- delivery

with tab_del:
    st.subheader("Which regions receive orders late, and by how many days?")

    states = query("select * from marts.delivery_delay_by_state")
    national = query("""
        select round(100.0 * avg(is_late::int), 1) as late_pct
        from marts.fct_orders where delivered_at is not null
    """).iloc[0].late_pct

    min_orders = st.slider(
        "Only states with at least this many delivered orders", 0, 2000, 0, step=100
    )
    view = states[states["delivered_orders"] >= min_orders].sort_values("late_pct")

    fig = px.bar(
        view, x="late_pct", y="customer_state", orientation="h",
        custom_data=["delivered_orders", "late_orders",
                     "avg_days_to_deliver", "avg_days_late_when_late"],
    )
    fig.update_traces(
        marker_color=BLUE,
        hovertemplate=(
            "<b>%{y}</b><br>Late: %{x}% (%{customdata[1]:,} of %{customdata[0]:,})<br>"
            "Avg delivery time: %{customdata[2]} days<br>"
            "Avg delay when late: %{customdata[3]} days<extra></extra>"
        ),
    )
    fig.add_vline(
        x=national, line_dash="dot", line_color=MUTED, line_width=1.5,
        annotation_text=f"National {national}%", annotation_position="top",
    )
    fig.update_xaxes(ticksuffix="%", showgrid=True)
    fig = style(fig, height=max(320, 24 * len(view)))
    fig.update_layout(margin_t=32)  # room for the "National" label above the line
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

    left, right = st.columns(2)
    with left:
        st.subheader("Do late deliveries hurt reviews?")
        reviews = query("""
            select case when is_late then 'Late' else 'On time' end as delivery,
                   count(*)                     as orders,
                   round(avg(review_score), 2)  as avg_review
            from marts.fct_orders
            where delivered_at is not null and review_score is not null
            group by 1
            order by 1 desc
        """)
        fig = px.bar(reviews, x="delivery", y="avg_review", text="avg_review",
                     color="delivery",
                     color_discrete_map={"On time": BLUE, "Late": ORANGE},
                     custom_data=["orders"])
        fig.update_traces(
            texttemplate="%{text} ★", textposition="outside",
            hovertemplate="<b>%{x}</b><br>Avg review: %{y} ★<br>"
                          "Orders: %{customdata[0]:,}<extra></extra>",
        )
        fig.update_yaxes(range=[0, 5.4], dtick=1)
        st.plotly_chart(style(fig, height=320), width="stretch",
                        config=PLOTLY_CONFIG)

    with right:
        st.subheader("State details")
        st.dataframe(
            states.sort_values("late_pct", ascending=False),
            hide_index=True,
            width="stretch",
            height=320,
            column_config={
                "customer_state": "State",
                "delivered_orders": st.column_config.NumberColumn("Delivered", format="%d"),
                "late_orders": st.column_config.NumberColumn("Late", format="%d"),
                "late_pct": st.column_config.NumberColumn("Late %", format="%.1f%%"),
                "avg_days_to_deliver": st.column_config.NumberColumn("Avg days", format="%.1f"),
                "avg_days_late_when_late": st.column_config.NumberColumn(
                    "Avg delay when late", format="%.1f"),
            },
        )

# ---------------------------------------------------------------------- sellers

with tab_sel:
    st.subheader("Who are the best and worst sellers by revenue and review score?")

    sellers = query("select * from marts.top_sellers")
    # Seller IDs are 32-char hashes; the first 8 characters are enough to tell them apart.
    sellers["seller"] = sellers["seller_id"].str[:8] + "…"

    rank_by = st.radio("Rank by", ["Revenue", "Review score"], horizontal=True)
    show = st.slider("Number of sellers", 5, 50, 10)
    if rank_by == "Revenue":
        best = sellers.nsmallest(show, "revenue_rank")
        worst = sellers.nlargest(show, "revenue_rank")
    else:
        rated = sellers.dropna(subset=["review_rank"])
        best = rated.nsmallest(show, "review_rank")
        worst = rated.nlargest(show, "review_rank")
        st.caption("Review ranking only includes sellers with 10 or more reviewed orders.")

    columns = {
        "revenue_rank": st.column_config.NumberColumn("Revenue rank", format="%d"),
        "review_rank": st.column_config.NumberColumn("Review rank", format="%d"),
        "seller": "Seller",
        "seller_state": "State",
        "revenue": st.column_config.NumberColumn("Revenue", format="R$%.0f"),
        "order_count": st.column_config.NumberColumn("Orders", format="%d"),
        "avg_review_score": st.column_config.NumberColumn("Avg review", format="%.2f ★"),
    }
    if rank_by == "Review score":  # lead with the rank being sorted on
        columns = {"review_rank": columns.pop("review_rank"), **columns}
    order = list(columns)

    left, right = st.columns(2)
    left.markdown(f"**Top {show}**")
    left.dataframe(best[order], hide_index=True, width="stretch",
                   column_config=columns)
    right.markdown(f"**Bottom {show}**")
    right.dataframe(worst[order], hide_index=True, width="stretch",
                    column_config=columns)

    st.subheader("Does more revenue mean happier customers?")
    rated = sellers[sellers["reviewed_orders"] >= 10]
    fig = px.scatter(
        rated, x="revenue", y="avg_review_score", log_x=True,
        custom_data=["seller", "seller_state", "revenue_rank", "review_rank"],
    )
    fig.update_traces(
        marker=dict(color=BLUE, size=8, opacity=0.45, line=dict(width=0)),
        hovertemplate=(
            "<b>Seller %{customdata[0]}</b> (%{customdata[1]})<br>"
            "Revenue: R$%{x:,.0f} (rank %{customdata[2]})<br>"
            "Avg review: %{y} ★ (rank %{customdata[3]})<extra></extra>"
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        tickvals=[100, 1_000, 10_000, 100_000, 1_000_000],
        ticktext=["R$100", "R$1K", "R$10K", "R$100K", "R$1M"],
    )
    fig.update_yaxes(range=[0.8, 5.2], dtick=1, ticksuffix=" ★")
    st.plotly_chart(style(fig, height=420), width="stretch",
                    config=PLOTLY_CONFIG)
    st.caption(
        f"{len(rated):,} sellers with 10+ reviewed orders. Revenue is on a log scale. "
        "High revenue does not guarantee good reviews."
    )

# -------------------------------------------------------------------- customers

with tab_cust:
    st.subheader("How many customers buy more than once?")

    repeat = query("select * from marts.customer_repeat_rate").iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", f"{int(repeat.total_customers):,}")
    c2.metric("Ordered more than once", f"{int(repeat.repeat_customers):,}")
    c3.metric("Repeat rate", f"{repeat.repeat_rate_pct}%")
    c4.metric("Orders per customer", f"{repeat.avg_orders_per_customer}")

    left, right = st.columns(2)
    with left:
        st.markdown("**Customers by number of orders**")
        dist = query("""
            select total_orders, count(*) as customers
            from marts.dim_customers
            group by total_orders
            order by total_orders
        """)
        dist["share_pct"] = (100 * dist["customers"] / dist["customers"].sum()).round(2)
        st.dataframe(
            dist, hide_index=True, width="stretch",
            column_config={
                "total_orders": st.column_config.NumberColumn("Orders placed", format="%d"),
                "customers": st.column_config.NumberColumn("Customers", format="%d"),
                "share_pct": st.column_config.ProgressColumn(
                    "Share", format="%.2f%%", min_value=0, max_value=100),
            },
        )

    with right:
        st.markdown("**Customers by state**")
        by_state = query("""
            select customer_state as state,
                   count(*)                                   as customers,
                   round(100.0 * avg(is_repeat_customer::int), 2) as repeat_pct,
                   round(avg(lifetime_paid), 2)               as avg_lifetime_paid
            from marts.dim_customers
            group by customer_state
            order by customers desc
        """)
        st.dataframe(
            by_state, hide_index=True, width="stretch", height=360,
            column_config={
                "state": "State",
                "customers": st.column_config.NumberColumn("Customers", format="%d"),
                "repeat_pct": st.column_config.NumberColumn("Repeat %", format="%.2f%%"),
                "avg_lifetime_paid": st.column_config.NumberColumn(
                    "Avg lifetime spend", format="R$%.2f"),
            },
        )

    st.info(
        "Nearly every customer buys once. Olist's growth depends on acquiring new "
        "buyers, so retention (follow-up offers, loyalty) is the obvious lever."
    )

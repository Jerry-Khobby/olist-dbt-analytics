"""Olist analytics dashboard (reads the dbt marts from Postgres)."""

import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine


@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}"
        f"/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url)


st.set_page_config(page_title="Olist Analytics", layout="wide")
st.title("Olist E-Commerce Analytics")

tables = pd.read_sql(
    "select table_schema, table_name from information_schema.tables "
    "where table_schema not in ('pg_catalog', 'information_schema') "
    "order by 1, 2",
    get_engine(),
)
st.subheader("Tables in the warehouse")
st.dataframe(tables, use_container_width=True)

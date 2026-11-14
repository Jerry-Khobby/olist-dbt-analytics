FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Pinned so a rebuild months from now gets the same, known-working versions
RUN pip install --no-cache-dir \
    "streamlit~=1.67.0" \
    "plotly~=7.1.0" \
    "pandas~=3.1.1" \
    "SQLAlchemy~=2.1.8" \
    "psycopg2-binary~=2.9.13"

WORKDIR /app

COPY streamlit/ .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

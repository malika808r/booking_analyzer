FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .

# Обновляем установщик и ставим защиту: 5 попыток переподключения при сбое сети
RUN pip install --upgrade pip && \
    pip install --default-timeout=100 --retries 5 --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8501
CMD ["bash", "-c", "sleep 5 && python bootstrap_db.py ; streamlit run app.py --server.port=8501 --server.address=0.0.0.0"]
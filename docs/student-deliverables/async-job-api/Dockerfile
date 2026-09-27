FROM python:3.12-slim
WORKDIR /service
RUN useradd --create-home appuser
RUN pip install --no-cache-dir fastapi uvicorn
COPY app ./app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

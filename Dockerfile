FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VVN_SERVICE_MODE=real
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir setuptools==82.0.1
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
RUN pip install --no-deps --no-build-isolation -e .
EXPOSE 8000
CMD ["vvn-data-service", "serve", "--mode", "real", "--host", "0.0.0.0", "--port", "8000"]

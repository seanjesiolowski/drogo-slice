FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use PORT env var if set by Railway, otherwise default to 8000
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]

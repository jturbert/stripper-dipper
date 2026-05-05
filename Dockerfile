FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser plus all required system libraries
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Output directory must exist for the static file mount at startup
RUN mkdir -p output

EXPOSE 8000

CMD ["python", "app.py"]

FROM python:3.13-slim

# System deps for WeasyPrint (Cairo, Pango, GDK-Pixbuf, fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chrome + system deps
RUN playwright install --with-deps chrome

# Copy source (after deps for better cache hits)
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Ensure persistent dirs exist inside the image as fallback
RUN mkdir -p dashboard/data reports output

ENTRYPOINT ["/entrypoint.sh"]
CMD ["dashboard"]

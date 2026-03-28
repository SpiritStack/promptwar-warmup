# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install system dependencies for OpenCV and other media processing
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service on container startup using Streamlit.
# CMD is required to run on Heroku / Cloud Run
# Cloud Run sets the PORT environment variable to 8080 by default.
EXPOSE 8080
CMD streamlit run app.py \
    --server.port=${PORT:-8080} \
    --server.address=0.0.0.0 \
    --browser.gatherUsageStats=false

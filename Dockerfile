FROM python:3.10-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the necessary files
COPY kibana_mcp_server.py config.yaml run_kibana_mcp.sh ./
COPY AI_rules_file.txt ./

# Make shell script executable
RUN chmod +x run_kibana_mcp.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the port for the HTTP server
EXPOSE 8000

# Start HTTP server
CMD ["python", "kibana_mcp_server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"] 
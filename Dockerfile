FROM python:3.10-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all necessary files
COPY . .

# Make shell script executable
RUN chmod +x run_kibana_mcp.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose the port (Smithery will provide PORT env var)
EXPOSE 8000

# Command for Smithery HTTP deployment
CMD ["python", "kibana_mcp_server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"] 
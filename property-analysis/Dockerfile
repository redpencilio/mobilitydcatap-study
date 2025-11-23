FROM python:3.11-slim

WORKDIR /app

# Install required packages
RUN pip install requests

# Copy the script
COPY property_analysis.py .

# Make script executable
RUN chmod +x property_analysis.py

# Set the default command
CMD ["python", "property_analysis.py"]
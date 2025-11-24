FROM python:3.11-slim

WORKDIR /app

# Install required packages
RUN pip install requests

# Copy the script
COPY dcat_vocabulary_checker.py .

# Make script executable
RUN chmod +x dcat_vocabulary_checker.py

# Set the default command
CMD ["python", "dcat_vocabulary_checker.py"]
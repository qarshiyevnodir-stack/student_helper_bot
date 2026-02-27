# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to avoid Python creating .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (LibreOffice and poppler-utils for presentation previews)
RUN apt-get update && apt-get install -y \
    libreoffice \
    poppler-utils \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Create directories for templates and previews
RUN mkdir -p templates previews

# Make port 80 available to the world outside this container (if needed for health checks)
EXPOSE 80

# Run main.py when the container launches
CMD ["python", "main.py"]

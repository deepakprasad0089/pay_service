# Start with the official Python image - the perfect foundation for our app
FROM python:3.9-slim

# Tell Python to spill its guts to the console and keep our virtual env alive
ENV PYTHONUNBUFFERED=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Set up our app's home sweet home in the container
WORKDIR /app

# Install some essential system dependencies - think of it as buying furniture for our new home
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Bring in our requirements file - the ultimate shopping list for our app
COPY requirements.txt .

# Create a virtual environment and install our dependencies - it's like moving into a new home and unpacking our bags!
RUN python -m venv $VIRTUAL_ENV \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy the rest of our app's code into the container
COPY . .

# Open up port 5000 to the world - our app is ready to shine :)
EXPOSE 5000

# Define the entry point for our container - the starting point for our app
CMD ["gunicorn", "main:app"]
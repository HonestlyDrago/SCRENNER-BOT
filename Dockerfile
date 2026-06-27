FROM python:3.11-slim

WORKDIR /app

# Copy the requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY crypto_scanner_bot.py .

# Expose the port used by the dummy server
EXPOSE 7860

# Run the bot
CMD ["python", "-u", "crypto_scanner_bot.py"]

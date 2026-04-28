FROM python:3.12-slim

WORKDIR /app

# System deps for common wheels (kept minimal; most deps are wheels)
RUN python -m pip install --no-cache-dir --upgrade pip

COPY requirements.txt ./requirements.txt
COPY requirements.bot.txt ./requirements.bot.txt
RUN python -m pip install --no-cache-dir -r requirements.bot.txt

# Copy the full repo (bot imports quant_agent/*)
COPY . .

# Default entrypoint; override in docker-compose if needed
CMD ["python", "test_live_1hour_questrade.py"]

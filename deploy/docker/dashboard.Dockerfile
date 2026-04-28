FROM python:3.12-slim

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip

COPY dashboard/requirements.txt ./dashboard/requirements.txt
RUN python -m pip install --no-cache-dir -r dashboard/requirements.txt

# Dashboard imports local modules within dashboard/
COPY dashboard ./dashboard

WORKDIR /app/dashboard

EXPOSE 5000

CMD ["python", "app.py"]

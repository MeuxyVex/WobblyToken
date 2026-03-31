FROM python:3.11

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install -r requirements.txt

COPY . .


CMD ["python", "app.py"]

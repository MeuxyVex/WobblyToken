FROM python:3.11

#on garde le code hors du volume du wallet
#sinon les anciens fichiers python du volume peuvent être chargés à sa place
WORKDIR /app/noeud

COPY requirements.txt .

RUN python -m pip install -r requirements.txt

COPY . .


CMD ["python", "app.py"]

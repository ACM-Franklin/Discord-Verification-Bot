FROM python:3.12-slim
WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Environment variables — defaults are empty; set real values in docker-compose.yml
# bot
ENV token=
ENV key=
ENV used_emails=
ENV warn_emails=
ENV hash_key=
ENV moderator_email=

# email
ENV sample=
ENV domain=
ENV from=
ENV password=
ENV subject=
ENV server=
ENV port=
ENV webmail_link=

# discord
ENV server_role=
ENV channel_id=
ENV notify_id=
ENV admin_id=
ENV ticket_id=
ENV author_name=

COPY . /app

CMD ["python", "bot.py"]

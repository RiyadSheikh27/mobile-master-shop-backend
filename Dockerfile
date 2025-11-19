FROM python:3.14

RUN mkdir /app
WORKDIR /app


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y netcat-openbsd
RUN pip install --upgrade pip


COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/


COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000


ENTRYPOINT ["/entrypoint.sh"]
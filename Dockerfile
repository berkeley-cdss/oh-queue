FROM python:3.10-slim

ENV APP_HOME /app
ENV FLASK_APP=manage.py
ENV PYTHONPATH=$PYTHONPATH:.

WORKDIR $APP_HOME
COPY . ./

RUN pip install -r requirements.txt

# execution permissions
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

CMD gunicorn -k eventlet -b :$PORT -w 4 manage:app -t 3000

FROM python:3.14-slim

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

# The page polls the server, so plain threads are enough; eventlet isn't needed.
CMD gunicorn -b :$PORT --workers 4 --threads 8 --timeout 120 manage:app

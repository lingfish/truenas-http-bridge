FROM python:3.11

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY truenas_bridge.py /code/

CMD ["fastapi", "run", "daemon.py", "--host", "::", "--port", "8000"]

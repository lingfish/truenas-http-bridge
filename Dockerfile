FROM python:3.11

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY src/truenas_http_bridge /code/truenas_http_bridge

CMD ["fastapi", "run", "truenas_http_bridge/truenas_bridge.py", "--host", "::", "--port", "8000"]

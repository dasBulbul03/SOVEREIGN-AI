FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
RUN pip install --no-cache-dir pytest==8.4.2
RUN mkdir -p /work && chmod 755 /work
COPY entrypoint.py /sandbox-entrypoint.py
WORKDIR /work
USER 65532:65532
ENTRYPOINT ["python", "/sandbox-entrypoint.py"]

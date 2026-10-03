FROM python:3.11-slim

WORKDIR /app
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY app.py media_scribe.py cloud_transcribe.py ./

ENV MEDIA_SCRIBE_BACKEND=groq \
    MEDIA_SCRIBE_HOST=0.0.0.0 \
    PORT=7860
EXPOSE 7860
CMD ["python", "app.py"]

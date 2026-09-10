# Deployment design; pin the base image by digest before confirmatory runs.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir torch==2.10.0 --index-url https://download.pytorch.org/whl/cpu \
 && python -m pip install --no-cache-dir '.[game,test]'
COPY scripts ./scripts
COPY tests ./tests
COPY configs ./configs
CMD ["python", "-m", "pytest", "-q"]

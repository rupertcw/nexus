FROM mambaorg/micromamba:1.5-bullseye-slim

COPY --chown=$MAMBA_USER:$MAMBA_USER env.yaml /tmp/env.yaml
RUN micromamba install -y -n base -f /tmp/env.yaml && \
    micromamba clean --all --yes

WORKDIR /app

COPY src /app/src
# Expose the API port
EXPOSE 8001

# We use the micromamba entrypoint which activates the base environment
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

FROM python:3.12-slim
WORKDIR /app
COPY app /app/app
COPY install.sh /app/install.sh
COPY catalog /app/catalog
# Hosted absorb shells out to git for GitHub sources.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git \
 && rm -rf /var/lib/apt/lists/*
# Install runtime deps + the sz package itself, because /v1/absorb imports sz.core.absorb.
# We install system-zero from PyPI after it is published (phase 15). During development
# (pre-PyPI-publish) the build uses the fallback Dockerfile.prelaunch.
ARG SZ_SOURCE=pypi
RUN if [ "$SZ_SOURCE" = "pypi" ]; then \
      pip install --no-cache-dir fastapi uvicorn[standard] stripe httpx pyyaml supabase resend pyjwt[crypto] sz-cli; \
    else \
      pip install --no-cache-dir fastapi uvicorn[standard] stripe httpx pyyaml supabase resend pyjwt[crypto]; \
    fi
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

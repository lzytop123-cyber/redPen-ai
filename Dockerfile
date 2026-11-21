# Stage 1: Build PC Web (web/)
FROM node:20-alpine AS web-builder
WORKDIR /build/web
COPY web/package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY web/ ./
RUN npm run build

# Stage 2: Build Admin Web (admin-web/)
FROM node:20-alpine AS admin-builder
WORKDIR /build/admin-web
COPY admin-web/package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY admin-web/ ./
RUN npm run build

# Stage 3: Production Python FastAPI Runtime
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY app/ ./app/
COPY data/ ./data/
COPY --from=web-builder /build/web/dist ./web/dist
COPY --from=admin-builder /build/admin-web/dist ./admin-web/dist

RUN mkdir -p /app/data/uploads

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

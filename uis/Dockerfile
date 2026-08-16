FROM node:24-alpine

WORKDIR /workspace

# Cada aplicación conserva su lockfile y sus dependencias independientes.
COPY uis/website/package.json uis/website/package-lock.json ./uis/website/
RUN cd uis/website && npm ci

COPY uis/backoffice/package.json uis/backoffice/package-lock.json ./uis/backoffice/
RUN cd uis/backoffice && npm ci

COPY src ./src
COPY uis ./uis

ENV PLATFORM_API_INTERNAL_URL=http://backend:8000 \
    TALENT_API_INTERNAL_URL=http://talent-api:4000 \
    NEXT_PUBLIC_PLATFORM_API_URL=/platform-api \
    NEXT_PUBLIC_SUPPLIERS_API_URL=/platform-api \
    NEXT_PUBLIC_PLATFORM_WS_URL=/platform-api \
    NEXT_PUBLIC_API_URL=/talent-api

RUN cd /workspace/uis/website && npm run build \
    && cd /workspace/uis/backoffice && npm run build \
    && chmod +x /workspace/uis/start.sh /workspace/uis/start-production.sh \
    && chown -R node:node /workspace

EXPOSE 3000 3001

USER node

CMD ["/workspace/uis/start-production.sh"]

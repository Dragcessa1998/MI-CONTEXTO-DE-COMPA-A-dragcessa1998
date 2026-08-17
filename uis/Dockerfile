FROM node:24-alpine

WORKDIR /workspace

# Cada aplicación conserva su lockfile y sus dependencias independientes.
COPY uis/website/package.json uis/website/package-lock.json ./uis/website/
RUN cd uis/website && npm ci

COPY uis/backoffice/package.json uis/backoffice/package-lock.json ./uis/backoffice/
RUN cd uis/backoffice && npm ci

COPY src ./src
COPY uis ./uis

RUN chmod +x /workspace/uis/start.sh

EXPOSE 3000 3001

CMD ["/workspace/uis/start.sh"]

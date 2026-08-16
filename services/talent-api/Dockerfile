FROM node:24-alpine

WORKDIR /workspace/services/talent-api

COPY services/talent-api/package.json services/talent-api/package-lock.json ./
RUN npm ci

COPY --chown=node:node src /workspace/src
COPY --chown=node:node services/talent-api /workspace/services/talent-api

ENV NODE_ENV=production

EXPOSE 4000

USER node

CMD ["npm", "start"]

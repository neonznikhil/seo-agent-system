FROM node:20-alpine

WORKDIR /app/frontend-next

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .
RUN npm run build

EXPOSE 3000

USER node

CMD ["npm", "start"]



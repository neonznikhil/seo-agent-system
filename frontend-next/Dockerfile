FROM node:18-alpine

WORKDIR /app/frontend-next

COPY frontend-next/package.json frontend-next/package-lock.json* ./
RUN npm ci || npm install

COPY frontend-next/ .
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]


FROM node:20-slim

WORKDIR /app

COPY package.json .
RUN npm install --production

COPY app.js .

EXPOSE 80

CMD ["node", "app.js"]

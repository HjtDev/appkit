# build-check only (profile "build-check") — proves demo-sdk COMPILES against appkit's
# published frontend surface, in isolation. A standalone `npm install` here (not the
# playground/ npm workspace playground/frontend/Dockerfile uses) is fine for a compile-only
# check: the runtime "duplicate @tanstack/react-query copy" bug documented in
# playground/frontend/Dockerfile only matters once React Context identity is involved, which a
# `tsc` build-check never touches.
FROM node:22-alpine
WORKDIR /app
COPY frontend/ /app/frontend/
RUN cd /app/frontend && npm install && npm run build
COPY playground/demo-sdk/ /app/playground/demo-sdk/
WORKDIR /app/playground/demo-sdk
RUN npm install && npm run build

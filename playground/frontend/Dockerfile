# Built with the REPO ROOT as context (playground/docker-compose.yml: `context: ..`), preserving
# the on-disk relative layout — /app/frontend (appkit's own frontend), /app/playground (the npm
# WORKSPACE root — see playground/package.json), /app/playground/demo-sdk,
# /app/playground/frontend — so the `file:../../frontend` dep in playground/frontend's
# package.json resolves identically in and out of Docker.
#
# playground/ is a real npm workspace (frontend + demo-sdk as members), NOT just two independent
# `npm install`s — found live, the hard way: demo-sdk listed `@tanstack/react-query` as its own
# devDependency (for local `tsc` typechecking), which without a workspace installs a SECOND,
# separate physical copy in demo-sdk/node_modules. useQuery() inside demo-sdk's compiled code
# then reads a DIFFERENT React Context object than the one playground/frontend's
# QueryClientProvider creates — "No QueryClient set, use QueryClientProvider to set one" despite
# a provider being correctly mounted. Exactly appkit's own documented "duplicate copy" class of
# bug (docs/CONTRACT.md §2010-2020, runDuplicateCopyGuard), just for @tanstack/react-query
# instead of appkit itself. A workspace's single hoisted node_modules is what dedupes it.
FROM node:22-alpine
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# appkit's frontend half: dist/ is gitignored (frontend/package.json's `prepare` script builds
# it on `npm install`, same as a real host's `npm install @hjtdev/appkit` would trigger) — built
# explicitly here anyway, since this dependency is path-linked (`file:../../frontend`, not the
# registry), so a stale dist/ from a previous build could otherwise linger unrebuilt.
COPY frontend/ /app/frontend/
RUN cd /app/frontend && npm install && npm run build

COPY playground/package.json /app/playground/package.json
COPY playground/demo-sdk/ /app/playground/demo-sdk/
COPY playground/frontend/ /app/playground/frontend/
RUN cd /app/playground && npm install
RUN cd /app/playground && npm run build --workspace=demo-sdk

WORKDIR /app/playground/frontend

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

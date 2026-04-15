FROM caddy:2-alpine AS build
COPY . /src
# Substitute build-time placeholders BEFORE baking the image.
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_POSTHOG_KEY
ARG SZ_API_ENDPOINT
RUN if [ -z "$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" ]; then echo "missing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY build arg" >&2; exit 1; fi
RUN if [ -z "$SZ_API_ENDPOINT" ]; then echo "missing SZ_API_ENDPOINT build arg" >&2; exit 1; fi
RUN for f in /src/*.html /src/*.js /src/pricing.html /src/index.html /src/Caddyfile; do \
      [ -f "$f" ] && \
        sed -i \
          -e "s|__NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY__|${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}|g" \
          -e "s|__NEXT_PUBLIC_SUPABASE_URL__|${NEXT_PUBLIC_SUPABASE_URL}|g" \
          -e "s|__NEXT_PUBLIC_SUPABASE_ANON_KEY__|${NEXT_PUBLIC_SUPABASE_ANON_KEY}|g" \
          -e "s|__NEXT_PUBLIC_POSTHOG_KEY__|${NEXT_PUBLIC_POSTHOG_KEY:-}|g" \
          -e "s|__SZ_API_ENDPOINT__|${SZ_API_ENDPOINT}|g" \
          "$f"; \
    done

FROM caddy:2-alpine
COPY --from=build /src /srv
COPY --from=build /src/Caddyfile /etc/caddy/Caddyfile
EXPOSE 80

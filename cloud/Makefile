.PHONY: launch deploy deploy-prelaunch logs ssh secrets prepare-prelaunch

launch:
	fly launch --copy-config --no-deploy --name sz-cloud --region iad

secrets:
	# Resolve CLERK_JWKS_URL if not already set in the env.
	# Clerk exposes a per-instance frontend API host; the JWKS URL is <host>/.well-known/jwks.json.
	set -a; . ../.env; [ -f ../.env.cloud ] && . ../.env.cloud; set +a; \
	export FLY_API_TOKEN="$$FLYIO_API_TOKEN"; \
	if [ -z "$$CLERK_JWKS_URL" ]; then \
	  if [ -n "$$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" ]; then \
	    CLERK_JWKS_URL=$$(python3 -c 'import base64, os; k=os.environ.get("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",""); p=k.split("_",2)[-1].rstrip("$$"); print("https://" + base64.b64decode(p + "="*((4-len(p)%4)%4)).decode().rstrip("$$") + "/.well-known/jwks.json")' 2>/dev/null || true); \
	  fi; \
	fi; \
	if [ -z "$$CLERK_JWKS_URL" ]; then \
	  CLERK_JWKS_URL=$$(curl -sS https://api.clerk.com/v1/jwks -H "Authorization: Bearer $$CLERK_SECRET_KEY" -o /dev/null -w '%{url_effective}\n' 2>/dev/null); \
	  if ! echo "$$CLERK_JWKS_URL" | grep -q "jwks"; then \
	    CLERK_FAPI=$$(curl -sS https://api.clerk.com/v1/instance -H "Authorization: Bearer $$CLERK_SECRET_KEY" | jq -r '.frontend_api // empty'); \
	    [ -n "$$CLERK_FAPI" ] && CLERK_JWKS_URL="https://$$CLERK_FAPI/.well-known/jwks.json"; \
	  fi; \
	  [ -z "$$CLERK_JWKS_URL" ] && { echo "CLERK_JWKS_URL could not be resolved; set it manually in .env"; exit 2; }; \
	fi; \
	fly secrets set --stage \
	  STRIPE_SECRET_KEY=$$STRIPE_SECRET_KEY \
	  STRIPE_PUBLISHABLE_KEY=$$STRIPE_PUBLISHABLE_KEY \
	  STRIPE_WEBHOOK_SECRET=$$STRIPE_WEBHOOK_SECRET \
	  STRIPE_PRICE_PRO=$$STRIPE_PRICE_PRO \
	  STRIPE_PRICE_TEAM=$$STRIPE_PRICE_TEAM \
	  CLERK_SECRET_KEY=$$CLERK_SECRET_KEY \
	  CLERK_JWKS_URL="$$CLERK_JWKS_URL" \
	  SUPABASE_URL=$$SUPABASE_URL \
	  SUPABASE_SERVICE_ROLE_KEY=$$SUPABASE_SERVICE_ROLE_KEY \
	  RESEND_API_KEY=$$RESEND_API_KEY \
	  OPENAI_API_KEY=$$OPENAI_API_KEY \
	  GROQ_API_KEY=$$GROQ_API_KEY

deploy: secrets
	set -a; . ../.env; [ -f ../.env.cloud ] && . ../.env.cloud; set +a; \
	export FLY_API_TOKEN="$$FLYIO_API_TOKEN"; \
	fly deploy

prepare-prelaunch:
	rm -rf local-sz spec catalog pyproject.toml install.sh
	cp -R ../sz local-sz
	cp -R ../spec spec
	cp -R ../catalog catalog
	cp ../pyproject.toml .
	cp ../install.sh .

deploy-prelaunch: prepare-prelaunch secrets
	set -a; . ../.env; [ -f ../.env.cloud ] && . ../.env.cloud; set +a; \
	export FLY_API_TOKEN="$$FLYIO_API_TOKEN"; \
	fly deploy --build-arg SZ_SOURCE=local --dockerfile Dockerfile.prelaunch

logs:
	fly logs

ssh:
	fly ssh console

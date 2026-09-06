.PHONY: db-up db-down db-reset db-apply db-test test check

db-up:
	docker compose up -d db

db-down:
	docker compose down

db-reset:
	docker compose down -v
	docker compose up -d db

db-apply:
	docker compose exec -T db psql -U $${POSTGRES_USER:-whitelist} -d $${POSTGRES_DB:-whitelist} -v ON_ERROR_STOP=1 -f /workspace/db/apply.sql

db-test:
	docker compose exec -T db psql -U $${POSTGRES_USER:-whitelist} -d $${POSTGRES_DB:-whitelist} -v ON_ERROR_STOP=1 -f /workspace/db/test.sql

test:
	pytest

check: test

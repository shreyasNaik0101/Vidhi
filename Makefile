# RBI Regulatory Timeline Engine — every stage has a target (PROJECT_SPEC.md §4).
# POSIX make. On Windows, run targets under Git Bash or invoke the python commands directly.

.PHONY: install db-up db-down db-logs test test-llm lint extract cost \
        langchain-install db-sync-langchain agent-install agent agent-ask \
        fetch normalise classify parse verify apply group eval pipeline aws-destroy

export PYTHONPATH := src

# --- setup ---
install:          ## install package + dev deps
	python -m pip install -e ".[dev,llm,api]"

db-up:            ## start Postgres+pgvector (Docker)
	docker compose up -d

db-down:          ## stop Postgres
	docker compose down

db-logs:
	docker compose logs -f db

db-sync:          ## run the pipeline on samples and persist into Postgres
	python -m rbi.db.cli sync --model gemma4:latest

db-resolve:       ## example: as-of query against Postgres (the date flip)
	python -m rbi.db.cli resolve --entity RRB --clause 68C --as-of 2026-10-02

# --- API (Node + Express, reads Postgres) ---
api-install:      ## install API deps
	cd api && npm install

api-test:         ## run the ported-resolver tests
	cd api && npm test

api-dev:          ## start the API on :3001 (needs db-up + db-sync first)
	cd api && npm start

ingest-dev:       ## start the live-ingestion service on :8030 (FastAPI)
	python -m uvicorn rbi.ingest.service:app --port 8030

# --- parse backend (native | langchain) ---
langchain-install: ## install the optional LangChain parse backend
	python -m pip install -e ".[langchain]"

db-sync-langchain: ## run the pipeline with the LangChain parse backend
	PARSE_BACKEND=langchain python -m rbi.db.cli sync --model gemma4:latest

# --- agent (LangChain tool-calling agent over the resolver, via Groq) ---
agent-install:    ## install the optional Groq agent layer
	python -m pip install -e ".[agent]"

agent:            ## chat with the regulatory agent (needs GROQ_API_KEY + db-up)
	python -m rbi.agent.cli chat

agent-ask:        ## one-shot: make agent-ask Q="SNFA income for a rural bank in November 2026"
	python -m rbi.agent.cli ask "$(Q)"

# --- quality ---
test:             ## run the test suite
	python -m pytest -q

test-llm:         ## run the live local-model tests (slow; incl. LangChain end-to-end)
	RUN_LLM_TESTS=1 python -m pytest tests/test_langchain_parse.py -q

lint:
	ruff check src tests

# --- pipeline stages (§6) ---
fetch:            ## [stage 1] scrape RBI notifications (respectful; --dry-run to preview)
	python -m rbi.fetch.cli --limit 5 --dry-run

extract:          ## [stage 2-3] extract + normalise sample PDFs
	python -m rbi.extract.cli --limit 2

classify:         ## [stage 4] regex-first, gemma3:4b fallback (not yet implemented)
	@echo "TODO: src/rbi/classify"

parse:            ## [stage 5] qwen3:8b -> strict JSON ops (not yet implemented)
	@echo "TODO: src/rbi/parse"

verify:           ## [stage 6] independent second check (stub = free; --bedrock = paid)
	python -m rbi.verify.cli --sample-rate 1.0

apply:            ## [stage 7] materialise clause timeline (not yet implemented)
	@echo "TODO: src/rbi/apply"

group:            ## [stage 8] link change across entity types (not yet implemented)
	@echo "TODO: src/rbi/group"

pipeline: fetch extract classify parse verify apply group  ## run all stages in order

# --- cost / eval ---
cost:             ## print LLM spend by stage and model
	python -m rbi.llm.cost

eval:             ## Baseline A (naive RAG) vs C (full system) on the golden set
	python -m rbi.eval.cli compare --model gemma4:latest

eval-index:       ## (re)build the naive-RAG pgvector index
	python -m rbi.eval.cli build-naive-index

aws-destroy:      ## tear down all AWS resources
	@echo "TODO: infra — cdk destroy"

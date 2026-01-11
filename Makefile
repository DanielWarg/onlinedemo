.PHONY: dev up down verify clean verify-fas0 verify-fas1 verify-fas2 verify-fas4-static verify-all verify-transcription-quality verify-projects-e2e verify-feed-import verify-feed-full verify-fortknox-v1 verify-fortknox-v1-loop fortknox-local down-fortknox

.PHONY: build-web prod-up prod-down prod-logs prod-smoke

.PHONY: web-dev web-dev-stop funnel-off stop-all

dev:
	@echo "Starting development environment..."
	@$(MAKE) fortknox-local
	docker-compose up --build

up:
	@echo "Starting production environment..."
	@$(MAKE) fortknox-local
	docker-compose up -d --build

down:
	@echo "Stopping all services..."
	docker-compose down
	@$(MAKE) down-fortknox

# ============================================================================
# Local frontend dev server (Vite) with pidfile so we can stop reliably
# ============================================================================

WEB_DEV_PID := /tmp/arbetsytan_web_dev.pid
WEB_DEV_LOG := /tmp/arbetsytan_web_dev.log

web-dev:
	@echo "Starting web dev server (Vite) ..."
	@if [ -f "$(WEB_DEV_PID)" ] && ps -p "$$(cat $(WEB_DEV_PID))" >/dev/null 2>&1; then \
		echo "✓ web-dev already running (PID: $$(cat $(WEB_DEV_PID)))"; \
		exit 0; \
	fi
	@cd apps/web && nohup npm run dev > "$(WEB_DEV_LOG)" 2>&1 & echo $$! > "$(WEB_DEV_PID)"
	@sleep 1
	@echo "✓ web-dev started (PID: $$(cat $(WEB_DEV_PID)), log: $(WEB_DEV_LOG))"

web-dev-stop:
	@echo "Stopping web dev server (Vite)..."
	@if [ -f "$(WEB_DEV_PID)" ]; then \
		PID=$$(cat "$(WEB_DEV_PID)"); \
		if ps -p "$$PID" >/dev/null 2>&1; then \
			kill -TERM "$$PID" 2>/dev/null || true; \
			echo "✓ Stopped web-dev (PID: $$PID)"; \
		fi; \
		rm -f "$(WEB_DEV_PID)" 2>/dev/null || true; \
	fi
	@# Best-effort fallback if started outside Makefile
	@pkill -f "npm run dev" 2>/dev/null || true
	@pkill -f "vite" 2>/dev/null || true

# ============================================================================
# Tailscale Funnel helpers (optional)
# ============================================================================

funnel-off:
	@echo "Stopping Tailscale Funnel (if enabled)..."
	@if command -v tailscale >/dev/null 2>&1; then \
		tailscale funnel off || true; \
	else \
		echo "tailscale not found. Install: brew install tailscale"; \
	fi

# ============================================================================
# One command to stop EVERYTHING related to this repo (Docker + local AI + dev server)
# ============================================================================

stop-all:
	@echo "======================================================================"
	@echo "Stopping ALL Arbetsytan processes (docker + fortknox-local + web-dev)"
	@echo "======================================================================"
	@# Stop prod-demo stack (Caddy + API + DB)
	@docker compose -f deploy/tailscale/docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
	@# Stop root dev stack (web + api + db)
	@docker-compose down --remove-orphans 2>/dev/null || true
	@# Stop local Fort Knox services (llama.cpp + fortknox-local)
	@$(MAKE) down-fortknox 2>/dev/null || true
	@# Stop local web dev server (Vite)
	@$(MAKE) web-dev-stop 2>/dev/null || true
	@# Stop funnel if running (optional)
	@$(MAKE) funnel-off 2>/dev/null || true
	@echo "✓ Done. Verify with: docker ps (should be empty) + lsof -iTCP -sTCP:LISTEN | grep -E '8787|8080|5173|8000|8443'"
	@echo "======================================================================"

FORTKNOX_DIR := $(shell pwd)/fortknox-local

fortknox-local:
	@echo "======================================================================"
	@echo "Starting Fort Knox Local services"
	@echo "======================================================================"
	@if [ ! -d "$(FORTKNOX_DIR)" ]; then \
		echo "⚠️  Fort Knox Local directory not found: $(FORTKNOX_DIR)"; \
		echo "   Skipping Fort Knox Local startup"; \
		exit 0; \
	fi; \
	\
	# Check if llama-server is already running on port 8080
	if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "✓ llama-server already running on port 8080"; \
	else \
		echo "Starting llama-server..."; \
		if [ -f "$(FORTKNOX_DIR)/start_llama_server.sh" ]; then \
			chmod +x "$(FORTKNOX_DIR)/start_llama_server.sh"; \
			cd "$(FORTKNOX_DIR)" && nohup ./start_llama_server.sh > /tmp/llama_server.log 2>&1 & \
			echo $$! > /tmp/llama_server.pid; \
			echo "✓ llama-server started (PID: $$(cat /tmp/llama_server.pid), log: /tmp/llama_server.log)"; \
			sleep 3; \
		else \
			echo "⚠️  start_llama_server.sh not found in $(FORTKNOX_DIR)"; \
		fi; \
	fi; \
	\
	# Check if Fort Knox Local is already running on port 8787
	if lsof -Pi :8787 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "✓ Fort Knox Local already running on port 8787"; \
	else \
		echo "Starting Fort Knox Local..."; \
		if [ -f "$(FORTKNOX_DIR)/start.sh" ]; then \
			chmod +x "$(FORTKNOX_DIR)/start.sh"; \
			cd "$(FORTKNOX_DIR)" && nohup ./start.sh > /tmp/fortknox_local.log 2>&1 & \
			echo $$! > /tmp/fortknox_local.pid; \
			echo "✓ Fort Knox Local started (PID: $$(cat /tmp/fortknox_local.pid), log: /tmp/fortknox_local.log)"; \
			sleep 2; \
		else \
			echo "⚠️  start.sh not found in $(FORTKNOX_DIR)"; \
		fi; \
	fi; \
	echo ""
	@echo "======================================================================"
	@echo "✅ Fort Knox Local services started"
	@echo "======================================================================"
	@echo "llama-server: http://localhost:8080"
	@echo "Fort Knox Local: http://localhost:8787"
	@echo ""
	@echo "Logs:"
	@echo "  llama-server: tail -f /tmp/llama_server.log"
	@echo "  Fort Knox Local: tail -f /tmp/fortknox_local.log"
	@echo ""
	@echo "Stop with: make down-fortknox"
	@echo ""

down-fortknox:
	@echo "Stopping Fort Knox Local services..."
	@# Stop processes on ports first (more reliable)
	@if lsof -Pi :8787 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		PIDS=$$(lsof -ti :8787); \
		for PID in $$PIDS; do \
			kill $$PID 2>/dev/null || true; \
			echo "✓ Stopped process on port 8787 (PID: $$PID)"; \
		done; \
		sleep 1; \
		if lsof -Pi :8787 -sTCP:LISTEN -t >/dev/null 2>&1; then \
			lsof -ti :8787 | xargs kill -9 2>/dev/null || true; \
			echo "✓ Force killed remaining processes on port 8787"; \
		fi; \
	fi
	@if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		PIDS=$$(lsof -ti :8080); \
		for PID in $$PIDS; do \
			kill $$PID 2>/dev/null || true; \
			echo "✓ Stopped process on port 8080 (PID: $$PID)"; \
		done; \
		sleep 1; \
		if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then \
			lsof -ti :8080 | xargs kill -9 2>/dev/null || true; \
			echo "✓ Force killed remaining processes on port 8080"; \
		fi; \
	fi
	@rm -f /tmp/fortknox_local.pid /tmp/llama_server.pid 2>/dev/null || true
	@echo "✅ Fort Knox Local services stopped"

# ============================================================================
# Tailscale Funnel demo deploy (local Mac): one domain, HTTPS via Funnel, Caddy routing
# ============================================================================

build-web:
	@echo "Building web (VITE_API_BASE=/api)..."
	@mkdir -p apps/web/public
	@if [ -f "Arbetsytan__Teknisk_djupdykning.mp4" ]; then \
		echo "Copying showreel video into apps/web/public/..."; \
		cp -f "Arbetsytan__Teknisk_djupdykning.mp4" "apps/web/public/Arbetsytan__Teknisk_djupdykning.mp4"; \
	else \
		echo "NOTE: Arbetsytan__Teknisk_djupdykning.mp4 not found in repo root; intro video will be missing unless VITE_SHOWREEL_VIDEO_URL is set."; \
	fi
	@cd apps/web && VITE_API_BASE=/api npm ci --silent
	@cd apps/web && VITE_API_BASE=/api npm run build --silent

prod-up:
	@bash deploy/tailscale/scripts/start.sh

prod-down:
	@bash deploy/tailscale/scripts/stop.sh

prod-logs:
	@docker-compose -f deploy/tailscale/docker-compose.prod.yml logs -f --tail=200

prod-smoke:
	@bash deploy/tailscale/scripts/smoke.sh

verify:
	@echo "Running smoke tests..."
	@echo "Testing /health endpoint..."
	@curl -s http://localhost:8000/health | grep -q "ok" && echo "✓ Health check passed" || (echo "✗ Health check failed" && exit 1)
	@echo "Testing /api/hello endpoint (with auth)..."
	@curl -s -u admin:password http://localhost:8000/api/hello | grep -q "Hello" && echo "✓ Hello endpoint passed" || (echo "✗ Hello endpoint failed" && exit 1)
	@echo "Creating project..."
	@PROJECT_ID=$$(curl -s -u admin:password -X POST http://localhost:8000/api/projects \
		-H "Content-Type: application/json" \
		-d '{"name":"Test Project","description":"Test description","classification":"normal"}' \
		| grep -o '"id":[0-9]*' | grep -o '[0-9]*' | head -1) && \
		echo "✓ Project created (ID: $$PROJECT_ID)" || (echo "✗ Project creation failed" && exit 1)
	@echo "Listing projects..."
	@curl -s -u admin:password http://localhost:8000/api/projects | grep -q "Test Project" && echo "✓ List projects passed" || (echo "✗ List projects failed" && exit 1)
	@echo "Adding event..."
	@PROJECT_ID=$$(curl -s -u admin:password http://localhost:8000/api/projects | grep -o '"id":[0-9]*' | grep -o '[0-9]*' | head -1) && \
		curl -s -u admin:password -X POST http://localhost:8000/api/projects/$$PROJECT_ID/events \
		-H "Content-Type: application/json" \
		-d '{"event_type":"test_event","metadata":{"key":"value"}}' | grep -q "test_event" && \
		echo "✓ Add event passed" || (echo "✗ Add event failed" && exit 1)
	@echo "Fetching events..."
	@PROJECT_ID=$$(curl -s -u admin:password http://localhost:8000/api/projects | grep -o '"id":[0-9]*' | grep -o '[0-9]*' | head -1) && \
		curl -s -u admin:password http://localhost:8000/api/projects/$$PROJECT_ID/events | grep -q "test_event" && \
		echo "✓ Fetch events passed" || (echo "✗ Fetch events failed" && exit 1)
	@echo "All smoke tests passed!"

verify-sanitization:
	@echo "Running sanitization verification test..."
	@docker-compose exec -T api python3 /app/_verify/verify_sanitization.py || \
		(echo "Note: If containers are not running, start with 'make dev' first" && exit 1)

verify-fas0:
	@echo "=== FAS 0: Styrning & disciplin ==="
	@test -f agent.md && echo "✓ agent.md exists" || (echo "✗ agent.md missing" && exit 1)
	@test -f VISION.md && echo "✓ VISION.md exists" || (echo "✗ VISION.md missing" && exit 1)
	@test -f PRINCIPLES.md && echo "✓ PRINCIPLES.md exists" || (echo "✗ PRINCIPLES.md missing" && exit 1)
	@test -f SECURITY_MODEL.md && echo "✓ SECURITY_MODEL.md exists" || (echo "✗ SECURITY_MODEL.md missing" && exit 1)
	@test -s agent.md && echo "✓ agent.md is not empty" || (echo "✗ agent.md is empty" && exit 1)
	@grep -q "Plan Mode" agent.md && echo "✓ agent.md contains 'Plan Mode'" || (echo "✗ agent.md missing 'Plan Mode'" && exit 1)
	@grep -q "demo-first\|demo first" agent.md && echo "✓ agent.md contains 'demo-first'" || (echo "✗ agent.md missing 'demo-first'" && exit 1)
	@echo "✓ FAS 0 PASS"

verify-fas1:
	@echo "=== FAS 1: Core Platform & UI-system ==="
	@echo "Testing backend health..."
	@curl -s http://localhost:8000/health | grep -q "ok" && echo "✓ Backend health check passed" || (echo "✗ Backend health check failed" && exit 1)
	@echo "Testing frontend availability..."
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200" && echo "✓ Frontend responds" || (echo "✗ Frontend not responding" && exit 1)
	@echo "Testing API endpoints..."
	@curl -s -u admin:password http://localhost:8000/api/projects | grep -q "projects\|id" && echo "✓ API projects endpoint works" || (echo "✗ API projects endpoint failed" && exit 1)
	@echo "✓ FAS 1 PASS"

verify-fas2:
	@echo "=== FAS 2: Material ingest & läsning ==="
	@echo "Testing document upload..."
	@PROJECT_ID=$$(curl -s -u admin:password -X POST http://localhost:8000/api/projects \
		-H "Content-Type: application/json" \
		-d '{"name":"FAS2 Test","classification":"normal"}' \
		| grep -o '"id":[0-9]*' | cut -d: -f2 | head -1); \
		echo "✓ Test project created (ID: $$PROJECT_ID)"; \
		echo "Uploading test document..."; \
		DOC_RESPONSE=$$(curl -s -u admin:password -X POST http://localhost:8000/api/projects/$$PROJECT_ID/documents \
			-F "file=@apps/api/_verify/safe_document.txt"); \
		DOC_ID=$$(echo "$$DOC_RESPONSE" | grep -o '"id":[0-9]*' | cut -d: -f2 | head -1); \
		if [ -z "$$DOC_ID" ]; then \
			echo "✗ Document upload failed or ID not found"; \
			exit 1; \
		fi; \
		echo "✓ Document uploaded (ID: $$DOC_ID)"; \
		echo "Verifying document metadata (no masked_text in list)..."; \
		if curl -s -u admin:password http://localhost:8000/api/projects/$$PROJECT_ID/documents | grep -q "masked_text"; then \
			echo "✗ masked_text found in list response (should not be)"; \
			exit 1; \
		fi; \
		echo "✓ masked_text not in list response"; \
		echo "Verifying document view (masked_text in detail)..."; \
		if ! curl -s -u admin:password http://localhost:8000/api/documents/$$DOC_ID | grep -q "masked_text\|EMAIL\|PHONE"; then \
			echo "✗ masked_text missing in detail response"; \
			exit 1; \
		fi; \
		echo "✓ masked_text present in detail response"; \
		echo "✓ FAS 2 PASS"

verify-fas4-static:
	@echo "=== FAS 4: Narrativ låsning (statisk) ==="
	@test -f DEMO_NARRATIVE.md && echo "✓ DEMO_NARRATIVE.md exists" || (echo "✗ DEMO_NARRATIVE.md missing" && exit 1)
	@echo "Checking for locked formulations in UI..."
	@grep -r "All känslig information är automatiskt maskerad" apps/web/src 2>/dev/null && echo "✓ 'All känslig information är automatiskt maskerad' found" || (echo "✗ Masked view explanation not found" && exit 1)
	@grep -r "Maskad vy" apps/web/src 2>/dev/null && echo "✓ 'Maskad vy' found in UI" || (echo "✗ 'Maskad vy' not found in UI" && exit 1)
	@grep -r "Klassificering påverkar åtkomst" apps/web/src 2>/dev/null && echo "✓ Classification explanation found" || (echo "✗ Classification explanation not found" && exit 1)
	@grep -r "Normal: Standard sanering" apps/web/src 2>/dev/null && echo "✓ Sanitization level (Normal) explanation found" || (echo "✗ Sanitization level (Normal) not found" && exit 1)
	@grep -r "Strikt: Ytterligare numeriska sekvenser" apps/web/src 2>/dev/null && echo "✓ Sanitization level (Strikt) explanation found" || (echo "✗ Sanitization level (Strikt) not found" && exit 1)
	@grep -r "Paranoid: Alla siffror och känsliga mönster" apps/web/src 2>/dev/null && echo "✓ Sanitization level (Paranoid) explanation found" || (echo "✗ Sanitization level (Paranoid) not found" && exit 1)
	@grep -r "AI avstängt" apps/web/src 2>/dev/null && echo "✓ 'AI avstängt' found in UI" || (echo "✗ 'AI avstängt' not found in UI" && exit 1)
	@grep -r "Dokumentet krävde paranoid sanering" apps/web/src 2>/dev/null && echo "✓ AI disabled explanation found" || (echo "✗ AI disabled explanation not found" && exit 1)
	@echo "Note: 'Originalmaterial bevaras i säkert lager' should be added to DocumentView tooltip (see DEMO_NARRATIVE.md)"
	@echo "✓ FAS 4 (static) PASS"

verify-fas4-5:
	@echo "=== FAS 4.5: Editorial Control Layer ==="
	@echo "Testing due_date in project responses..."
	@PROJECT_ID=$$(curl -s -u admin:password -X POST http://localhost:8000/api/projects \
		-H "Content-Type: application/json" \
		-d '{"name":"FAS4.5 Test","classification":"normal","due_date":"2025-12-31T00:00:00Z"}' \
		| grep -o '"id":[0-9]*' | cut -d: -f2 | head -1); \
		if [ -z "$$PROJECT_ID" ]; then \
			echo "✗ Project creation failed"; \
			exit 1; \
		fi; \
		echo "✓ Project created (ID: $$PROJECT_ID)"; \
		if ! curl -s -u admin:password http://localhost:8000/api/projects/$$PROJECT_ID | grep -q "due_date"; then \
			echo "✗ due_date missing in project response"; \
			exit 1; \
		fi; \
		echo "✓ due_date present in project response"; \
		echo "Testing project edit (PUT)..."; \
		if ! curl -s -u admin:password -X PUT http://localhost:8000/api/projects/$$PROJECT_ID \
			-H "Content-Type: application/json" \
			-d '{"name":"FAS4.5 Test Updated"}' | grep -q "FAS4.5 Test Updated"; then \
			echo "✗ Project edit failed"; \
			exit 1; \
		fi; \
		echo "✓ Project edit works"; \
		echo "Testing project delete (DELETE)..."; \
		DELETE_STATUS=$$(curl -s -u admin:password -X DELETE http://localhost:8000/api/projects/$$PROJECT_ID -w "%{http_code}" -o /dev/null); \
		if [ "$$DELETE_STATUS" != "204" ]; then \
			echo "✗ Project delete failed (status: $$DELETE_STATUS, expected 204)"; \
			exit 1; \
		fi; \
		echo "✓ Project delete works (status: 204)"; \
		echo "✓ FAS 4.5 PASS"

verify-projects-e2e:
	@echo "=== Projects E2E Verification ==="
	@docker-compose exec -T api python3 /app/_verify/verify_projects_e2e.py || \
		(echo "Note: If containers are not running, start with 'make dev' first" && exit 1)

verify-transcription-quality:
	@echo "=== Transcription Quality Verification ==="
	@echo "Note: This may take 3-10 minutes with large-v3 (first run downloads model)"
	@echo "      If this hangs, run directly in container:"
	@echo "      docker exec arbetsytan-api-1 python3 /app/_verify/verify_transcription_quality.py"
	@docker-compose exec -T api python3 /app/_verify/verify_transcription_quality.py || \
		(echo "" && \
		 echo "Note: If containers are not running, start with 'make dev' first" && \
		 echo "      If timeout occurred, run directly in container:" && \
		 echo "      docker exec arbetsytan-api-1 python3 /app/_verify/verify_transcription_quality.py" && \
		 exit 1)

verify-security-phase1:
	@echo "======================================================================"
	@echo "PHASE 1: SECURITY BY DESIGN - Verification Suite"
	@echo "======================================================================"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "TEST 1/2: Event No Content Policy"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose exec -T -e DEBUG=true api python _verify/verify_event_no_content_policy.py || \
		(echo "✗ Event No Content Policy verification FAILED" && exit 1)
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "TEST 2/2: Secure Delete Policy"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose exec -T api python _verify/verify_secure_delete.py || \
		(echo "✗ Secure Delete Policy verification FAILED" && exit 1)
	@echo ""
	@echo "======================================================================"
	@echo "✅ PHASE 1 VERIFICATION COMPLETE - All security policies enforced"
	@echo "======================================================================"
	@echo "Event No Content: ✅ PASS"
	@echo "Secure Delete: ✅ PASS"
	@echo ""

verify-all:
	@echo "🧭 Running all FAS 0-4 verifications..."
	@$(MAKE) verify-fas0
	@$(MAKE) verify-fas1
	@$(MAKE) verify-fas2
	@$(MAKE) verify-sanitization
	@$(MAKE) verify-fas4-static
	@$(MAKE) verify-fas4-5
	@$(MAKE) verify-projects-e2e
	@$(MAKE) verify-transcription-quality
	@echo ""
	@echo "🟢 All verifications PASSED - System ready for FAS 5"

clean:
	@echo "Cleaning up..."
	docker-compose down -v
	docker system prune -f

benchmark-stt:
	@echo "======================================================================"
	@echo "STT BENCHMARK MATRIX - Prestanda & Kvalitet"
	@echo "======================================================================"
	@echo "Kör 4 konfigurationer * 2 runs = 8 totala körningar"
	@echo "Uppskattad tid: 30-60 minuter (beroende på modell)"
	@echo ""
	@docker compose up -d --build
	@sleep 10
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "KONFIGURATION 1/4: Whisper base"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose exec -T -e STT_ENGINE=whisper -e WHISPER_MODEL=base -e TEST_AUDIO_PATH=/app/Del21.wav -e NUM_RUNS=2 api python _verify/benchmark_stt_matrix.py
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "KONFIGURATION 2/4: Whisper small"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose exec -T -e STT_ENGINE=whisper -e WHISPER_MODEL=small -e TEST_AUDIO_PATH=/app/Del21.wav -e NUM_RUNS=2 api python _verify/benchmark_stt_matrix.py
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "KONFIGURATION 3/4: faster-whisper base"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose exec -T -e STT_ENGINE=faster_whisper -e WHISPER_MODEL=base -e TEST_AUDIO_PATH=/app/Del21.wav -e NUM_RUNS=2 api python _verify/benchmark_stt_matrix.py
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "KONFIGURATION 4/4: faster-whisper small"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose exec -T -e STT_ENGINE=faster_whisper -e WHISPER_MODEL=small -e TEST_AUDIO_PATH=/app/Del21.wav -e NUM_RUNS=2 api python _verify/benchmark_stt_matrix.py
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "AGGREGERAR RESULTAT"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose exec -T api python _verify/aggregate_stt_benchmark.py
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "KOPIERAR RAPPORT"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@docker compose cp api:/app/test_results/STT_BENCHMARK.md docs/STT_BENCHMARK.md 2>/dev/null || echo "⚠️  Kunde inte kopiera rapport (kör manuellt: docker compose cp api:/app/test_results/STT_BENCHMARK.md docs/STT_BENCHMARK.md)"
	@echo ""
	@echo "======================================================================"
	@echo "✅ BENCHMARK KLAR"
	@echo "======================================================================"
	@echo "JSON Rapport: apps/api/test_results/stt_benchmark_report.json"
	@echo "Markdown Rapport: docs/STT_BENCHMARK.md"
	@echo "Transcripts: apps/api/test_results/transcripts/"
	@echo ""

verify-feed-import:
	@echo "======================================================================"
	@echo "FEED IMPORT VERIFICATION"
	@echo "======================================================================"
	@docker-compose exec -T api python3 /app/_verify/verify_feed_import.py || \
		(echo "" && \
		 echo "Note: If containers are not running, start with 'make dev' first" && \
		 exit 1)
	@echo ""
	@echo "======================================================================"
	@echo "✅ FEED IMPORT VERIFICATION COMPLETE"
	@echo "======================================================================"
	@echo "Results: apps/api/test_results/feed_import_verify.json"
	@echo ""

verify-feed-full:
	@echo "======================================================================"
	@echo "FEED IMPORT FULL VERIFICATION (Project + Note + Source + Document)"
	@echo "======================================================================"
	@docker-compose exec -T api python3 /app/_verify/verify_feed_project_full.py || \
		(echo "" && \
		 echo "Note: If containers are not running, start with 'make dev' first" && \
		 exit 1)
	@echo ""
	@echo "======================================================================"
	@echo "✅ FEED IMPORT FULL VERIFICATION COMPLETE"
	@echo "======================================================================"
	@echo "Results: test_results/feed_project_full_verify.json"
	@echo ""

verify-fortknox-v1:
	@echo "======================================================================"
	@echo "FORT KNOX V1 VERIFICATION"
	@echo "======================================================================"
	@echo "Note: This test may restart the API container to test FORTKNOX_OFFLINE"
	@MAX_RESTARTS=5; \
	RESTART_COUNT=0; \
	while [ $$RESTART_COUNT -le $$MAX_RESTARTS ]; do \
		docker-compose exec -T -e FORTKNOX_TESTMODE=1 api python3 /app/_verify/verify_fortknox_v1.py; \
		EXIT_CODE=$$?; \
		if [ $$EXIT_CODE -eq 100 ]; then \
			RESTART_COUNT=$$((RESTART_COUNT + 1)); \
			echo "Test requires restart ($$RESTART_COUNT/$$MAX_RESTARTS) - updating docker-compose.yml..."; \
			if docker-compose exec -T api test -f /tmp/fortknox_compose_update_needed 2>/dev/null; then \
				COMPOSE_PATH=$$(docker-compose exec -T api cat /tmp/fortknox_compose_update_needed 2>/dev/null | head -1 | tr -d '\r\n' | xargs); \
				echo "Compose path from container: [$$COMPOSE_PATH]"; \
				if [ -n "$$COMPOSE_PATH" ]; then \
					echo "Copying modified compose file from container..."; \
					if [ ! -f docker-compose.yml.bak_before_fortknox_test ]; then \
						cp docker-compose.yml docker-compose.yml.bak_before_fortknox_test || true; \
					fi; \
					if docker-compose exec -T api cat "$$COMPOSE_PATH" > ./docker-compose.yml.tmp 2>/dev/null; then \
						if [ -f ./docker-compose.yml.tmp ] && [ -s ./docker-compose.yml.tmp ]; then \
							mv ./docker-compose.yml.tmp docker-compose.yml; \
							echo "✅ docker-compose.yml updated on host"; \
							echo "Verifying update..."; \
							grep -E "(FORTKNOX_REMOTE_URL|FORTKNOX_TESTMODE)" docker-compose.yml | head -2; \
						else \
							echo "⚠️ Warning: Copied file is empty or missing"; \
							if [ -f docker-compose.yml.bak_before_fortknox_test ]; then \
								mv docker-compose.yml.bak_before_fortknox_test docker-compose.yml 2>/dev/null || true; \
							fi; \
						fi; \
					else \
						echo "⚠️ Warning: Failed to read compose file from container"; \
						if [ -f docker-compose.yml.bak_before_fortknox_test ]; then \
							mv docker-compose.yml.bak_before_fortknox_test docker-compose.yml 2>/dev/null || true; \
						fi; \
					fi; \
				else \
					echo "⚠️ Warning: Empty compose path"; \
				fi; \
				docker-compose exec -T api rm -f /tmp/fortknox_compose_update_needed 2>/dev/null || true; \
			fi; \
			echo "Unsetting FORTKNOX_REMOTE_URL on host (if set)..."; \
			unset FORTKNOX_REMOTE_URL; \
			echo "Recreating API container (to load new env vars)..."; \
			docker-compose up -d --force-recreate api; \
			echo "Waiting for API to be healthy..."; \
			sleep 20; \
			timeout=90; \
			while [ $$timeout -gt 0 ]; do \
				if docker-compose exec -T api curl -f http://localhost:8000/health >/dev/null 2>&1; then \
					echo "✅ API is healthy"; \
					break; \
				fi; \
				sleep 3; \
				timeout=$$((timeout - 3)); \
			done; \
			if [ $$timeout -le 0 ]; then \
				echo "⚠️ API health check timeout, waiting additional 30s..."; \
				sleep 30; \
			fi; \
			echo "Creating resume flag..."; \
			docker-compose exec -T api touch /tmp/fortknox_resume_after_restart 2>/dev/null || true; \
			echo "Re-running verification after restart..."; \
			echo "Note: FORTKNOX_TESTMODE is controlled by docker-compose.yml for TEST 5"; \
		elif [ $$EXIT_CODE -ne 0 ]; then \
			echo ""; \
			echo "Note: If containers are not running, start with 'make dev' first"; \
			if [ -f docker-compose.yml.bak_before_fortknox_test ]; then \
				echo "Restoring original docker-compose.yml..."; \
				mv docker-compose.yml.bak_before_fortknox_test docker-compose.yml; \
				docker-compose up -d api; \
			fi; \
			exit 1; \
		else \
			break; \
		fi; \
	done; \
	if [ $$RESTART_COUNT -gt $$MAX_RESTARTS ]; then \
		echo "⚠️ Maximum restart count reached ($$MAX_RESTARTS)"; \
		exit 1; \
	fi; \
	if [ -f docker-compose.yml.bak_before_fortknox_test ]; then \
		echo "Restoring original docker-compose.yml..."; \
		mv docker-compose.yml.bak_before_fortknox_test docker-compose.yml; \
		docker-compose up -d api; \
	fi
	@echo ""
	@echo "======================================================================"
	@echo "✅ FORT KNOX V1 VERIFICATION COMPLETE"
	@echo "======================================================================"
	@echo "Results: apps/api/test_results/fortknox_v1_verify.json"
	@echo ""

verify-fortknox-v1-loop:
	@echo "=== Fort Knox v1 Verification (loop until done) ==="
	@MAX=8; \
	i=1; \
	while [ $$i -le $$MAX ]; do \
		echo ""; \
		echo "--- Attempt $$i/$$MAX ---"; \
		docker-compose exec -T api python3 /app/_verify/verify_fortknox_v1.py; \
		code=$$?; \
		if [ $$code -eq 0 ]; then \
			echo "PASS: Fort Knox verification completed."; \
			exit 0; \
		elif [ $$code -eq 100 ]; then \
			echo "NEEDS_RESTART (100): Applying compose update/restore and restarting api..."; \
			if docker-compose exec -T api test -f /tmp/fortknox_compose_update_needed; then \
				workfile=$$(docker-compose exec -T api sh -lc 'cat /tmp/fortknox_compose_update_needed | head -n 1 | tr -d "\r"'); \
				echo "Copying compose from container workfile: $$workfile → ./docker-compose.yml"; \
				docker-compose cp api:$$workfile ./docker-compose.yml; \
				docker-compose exec -T api sh -lc 'rm -f /tmp/fortknox_compose_update_needed'; \
			fi; \
			if docker-compose exec -T api test -f /tmp/fortknox_restore_needed; then \
				echo "Restore requested. (compose already copied back above if needed)"; \
				docker-compose exec -T api sh -lc 'rm -f /tmp/fortknox_restore_needed'; \
			fi; \
			docker-compose restart api; \
			echo "Waiting for API health..."; \
			n=0; \
			until curl -fsS http://localhost:8000/health >/dev/null 2>&1; do \
				n=$$((n+1)); \
				if [ $$n -ge 60 ]; then echo "Health timeout"; exit 1; fi; \
				sleep 2; \
			done; \
			i=$$((i+1)); \
			continue; \
		else \
			echo "FAIL: Verification returned $$code"; \
			exit $$code; \
		fi; \
	done; \
	echo "FAIL: Exceeded max attempts ($$MAX)."; \
	exit 1

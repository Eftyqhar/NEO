# Neo: Lightweight Real-Time CLI Workflow Automation Engine

**Neo** is a fast, terminal-first, headless alternative to heavy UI-based automation tools like n8n. Operating with a tiny memory footprint (<30 MB RAM), Neo executes asynchronous, event-driven pipelines defined via human-readable YAML specifications.

---

## Key Features

* **True Real-Time Event Push (<100ms)**:
  * **IMAP IDLE (RFC 2177)**: Persistent push socket for instant email triggers (no slow 60s polling).
  * **Telegram Bot**: Long-polling stream for real-time bot commands (`/status`, `/deploy`) and messages.
  * **Async Webhook Server**: Ultra-fast embedded HTTP server (`aiohttp`) for external API webhooks.
  * **File Watcher**: Real-time directory monitoring for file creations and modifications.
  * **Cron & Interval**: High-precision scheduling via `APScheduler`.
* **Outbound Actions & Connectors**:
  * **SMTP Mailer**: SSL/TLS, STARTTLS, HTML templates, Markdown, and attachments.
  * **Telegram Bot**: Formatted Markdown messages, photos, documents, and chat alerts.
  * **HTTP / REST**: Full GET/POST/PUT/DELETE client with headers, JSON, and bearer auth.
  * **Shell Execution**: Cross-platform execution (PowerShell / Bash) with stdout/stderr capture.
  * **AI Transformers**: LLM integration (Gemini / Ollama) for text summarization and extraction.
* **Terminal UI (TUI) & Persistence**:
  * Rich terminal execution tables with sub-second execution timings.
  * Live background daemon dashboard (`neo start`).
  * SQLite run ledger (`neo history`).

---

## Installation & Setup

1. **Activate the Virtual Environment**:
   ```powershell
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   ```
   Add your credentials for IMAP, SMTP, Telegram Bot, or Gemini API.

---

## CLI Usage

### 1. Run a Workflow Once
Execute any workflow pipeline immediately:
```bash
neo run ./workflows/demo_pipeline.yaml
```

### 2. Test with Mock Trigger Data
Dry-run a workflow with a synthetic JSON payload:
```bash
neo test ./workflows/email_to_telegram.yaml --mock '{"subject": "Urgent Server Alert", "from": "admin@example.com"}'
```

### 3. Start the Background Daemon (TUI Dashboard)
Start real-time listener sockets for all workflows in `./workflows`:
```bash
neo start
```

### 4. View Execution History
Inspect past execution runs and performance metrics from the SQLite ledger:
```bash
neo history --limit 15
```

### 5. Generate a Workflow with AI
Generate a validated YAML workflow using natural language:
```bash
neo create "Listen for incoming emails from Stripe and send a Telegram message to chat 12345"
```

---

## Workflow YAML Specification

Workflows are simple, declarative YAML files:

```yaml
name: "Urgent Email to Telegram Alert"
description: "Pushes urgent emails to Telegram in real-time"
enabled: true

trigger:
  type: imap
  host: "imap.gmail.com"
  port: 993
  username: "{{ env.EMAIL_USER }}"
  password: "{{ env.EMAIL_PASS }}"
  folder: "INBOX"

steps:
  # 1. Condition Filter
  - id: check_priority
    type: filter
    condition: "'urgent' in steps.trigger.subject.lower()"

  # 2. Telegram Notification
  - id: alert_telegram
    type: telegram
    bot_token: "{{ env.TELEGRAM_BOT_TOKEN }}"
    chat_id: "{{ env.TELEGRAM_CHAT_ID }}"
    parse_mode: "Markdown"
    message: |
      🚨 *Priority Email Received*
      *From:* {{ steps.trigger.from }}
      *Subject:* {{ steps.trigger.subject }}
      
      {{ steps.trigger.snippet }}
```

---

## Pre-bundled Workflows

Neo comes with ready-to-use workflows in `./workflows/`:
* `demo_pipeline.yaml`: Self-contained diagnostic pipeline (OS check, HTTP fetch, filtering).
* `email_to_telegram.yaml`: Real-time IMAP IDLE push forwarded to Telegram.
* `telegram_devops_bot.yaml`: Telegram `/status` command triggering server diagnostics.
* `webhook_to_smtp.yaml`: HTTP POST webhook forwarding to SMTP email.

---

## Running the Test Suite

```bash
pytest -v
```

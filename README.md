# Meeting Notes Organizer

Production-ready Stage 3 MCP server for ChatGPT Developer Mode.

## Run

```powershell
python server.py
```

The server listens on `http://127.0.0.1:8000` by default.

## Routes

- `GET /`
- `GET /privacy`
- `GET /terms`
- `GET /support`
- `GET /health`
- `GET /.well-known/openai-apps-challenge`
- `POST /mcp`

## Quick tests

Homepage:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/ -UseBasicParsing
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Challenge token:

```powershell
$env:OPENAI_APPS_CHALLENGE='your-token'
Invoke-WebRequest http://127.0.0.1:8000/.well-known/openai-apps-challenge -UseBasicParsing
```

Initialize:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/mcp `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

List tools:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/mcp `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

Call the tool:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/mcp `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"organize_meeting_notes","arguments":{"meeting_text":"Schedule review with Nina and Alex in Room 12 on 2026-06-01 at 14:30"}}}'
```

## Notes

- Uses Python standard library only.
- Uses no external APIs.
- Uses no database.
- Stores no user data.
- Binds to `0.0.0.0` and reads `PORT` from the environment for Render or similar deployment targets.

## Deployment

Render-compatible start command:

```powershell
python server.py
```

Required environment variables:

- `PORT` provided by the hosting platform
- `OPENAI_APPS_CHALLENGE` for the challenge endpoint when needed

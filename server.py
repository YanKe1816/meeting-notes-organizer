import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape


PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "meeting-notes-organizer", "version": "0.1.0"}
TOOL_NAME = "organize_meeting_notes"
TOOL_DESCRIPTION = (
    "Use this tool only when the user provides actual meeting notes or a meeting record text "
    "and needs extraction of fixed structured fields. The tool extracts only meeting_date, "
    "meeting_time, location, participants, topic, missing_fields, and source_text. Do not use "
    "this tool to summarize meetings, generate action items, infer decisions, provide "
    "recommendations, create next steps, schedule meetings, give productivity advice, or "
    "process text that explicitly says it is not a meeting note or not a meeting record. If "
    "the user asks for a summary, action items, recommendations, advice, or any output beyond "
    "the fixed extraction fields, do not use this tool. This tool is useful only when "
    "deterministic structured extraction is needed."
)
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "meeting_text": {
            "type": "string",
            "description": "Raw meeting notes or a natural-language meeting description provided by the user.",
        }
    },
    "required": ["meeting_text"],
    "additionalProperties": False,
}
TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "openWorldHint": False,
}
OUT_OF_SCOPE_HINTS = (
    "not a meeting note",
    "not a meeting record",
    "not a formal meeting",
    "not a formal meeting record",
    "casual conversation",
    "informal conversation",
    "went to the park",
    "gardening with friends",
    "summarize",
    "summary",
    "meeting summary",
    "generate action item",
    "generate action items",
    "action item",
    "action items",
    "generate action",
    "next steps",
    "key updates",
    "discussion points",
    "decision / agreement",
    "advice",
    "give me advice",
    "should i",
    "recommend",
    "recommendation",
    "productivity advice",
    "schedule more meetings",
    "financial advice",
    "stocks",
    "crypto",
    "invest",
    "calendar event",
    "calendar invite",
    "send notification",
    "notify",
)
OUT_OF_SCOPE_PATTERNS = (
    r"\bnot a meeting note\b",
    r"\bnot a meeting record\b",
    r"\bnot a formal meeting\b",
    r"\bnot a formal meeting record\b",
    r"\bcasual conversation\b",
    r"\binformal conversation\b",
    r"\bwent to the park\b",
    r"\bgardening with friends\b",
    r"\bnot .*meeting record\b",
    r"\bnot .*meeting note\b",
    r"\bsummarize\b",
    r"\bsummary\b",
    r"\bmeeting summary\b",
    r"\bgenerate action item\b",
    r"\bgenerate action items\b",
    r"\baction item\b",
    r"\baction items\b",
    r"\bgenerate action\b",
    r"\bnext steps\b",
    r"\bkey updates\b",
    r"\bdiscussion points\b",
    r"\bdecision / agreement\b",
    r"\bgive me advice\b",
    r"\bshould i\b",
    r"\brecommend\b",
    r"\brecommendation\b",
    r"\bproductivity advice\b",
    r"\bschedule more meetings\b",
    r"\bfinancial advice\b",
    r"\bstocks\b",
    r"\bcrypto\b",
    r"\binvest\b",
)
MEETING_SIGNAL_PATTERNS = (
    r"\bmeeting\b",
    r"\bteam sync\b",
    r"\bheld a meeting\b",
    r"\bmeeting took place\b",
    r"\battendees\b",
    r"\bparticipants\b",
    r"\bmeeting\b",
    r"\broom\b",
    r"\bconference room\b",
    r"\bon\s+\d{4}-\d{2}-\d{2}\b",
    r"\bat\s+\d{1,2}:\d{2}\b",
)
OVERRIDE_MEETING_PATTERNS = (
    r"\bheld a meeting\b",
    r"\bmeeting took place\b",
)
SUPPORT_EMAIL = "sidcraigau@gmail.com"


def success_response(meeting_text, meeting_date, meeting_time, location, participants, topic):
    missing_fields = [
        field
        for field, value in (
            ("meeting_date", meeting_date),
            ("meeting_time", meeting_time),
            ("location", location),
            ("participants", participants),
            ("topic", topic),
        )
        if value in (None, [])
    ]
    return {
        "status": "success",
        "meeting_date": meeting_date,
        "meeting_time": meeting_time,
        "location": location,
        "participants": participants,
        "topic": topic,
        "missing_fields": missing_fields,
        "source_text": meeting_text,
    }


def error_response(error_type, message):
    return {
        "status": "error",
        "error_type": error_type,
        "message": message,
    }


def extract_date(meeting_text):
    match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", meeting_text)
    return match.group(0) if match else None


def extract_time(meeting_text):
    match = re.search(r"\b\d{1,2}:\d{2}\b", meeting_text)
    return match.group(0) if match else None


def clean_capture(value):
    cleaned = value.strip(" .,\t\r\n")
    return cleaned or None


def extract_location(meeting_text):
    patterns = [
        r"\bin\s+(.+?)(?=\s+for\s+a\s+.+?\bmeeting\b|\.\s|,\s+attendees\b|\.\s+attendees\b|\.\s+participants\b|\.\s+the\s+topic\b|\s+with\s+|\s+on\s+\d{4}-\d{2}-\d{2}\b|\s+at\s+\d{1,2}:\d{2}\b|$)",
        r"\bat\s+(.+?)(?=\s+for\s+a\s+.+?\bmeeting\b|\.\s|,\s+attendees\b|\.\s+attendees\b|\.\s+participants\b|\.\s+the\s+topic\b|\s+with\s+|\s+on\s+\d{4}-\d{2}-\d{2}\b|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, meeting_text, flags=re.IGNORECASE)
        if match:
            candidate = clean_capture(match.group(1))
            if candidate and not re.fullmatch(r"\d{1,2}:\d{2}", candidate):
                return candidate
    return None


def split_participants(raw_value):
    normalized = re.sub(r"\s+(and|&)\s+", ",", raw_value.strip(), flags=re.IGNORECASE)
    parts = [part.strip(" .,\t\r\n") for part in normalized.split(",")]
    participants = []
    for part in parts:
        if part:
            participants.append(part)
    return participants


def extract_participants(meeting_text):
    participant_patterns = (
        r"\b(?:attendees|participants)\s*:\s*(.+?)(?=\.\s|;\s|\s+in\s+|\s+on\s+\d{4}-\d{2}-\d{2}\b|\s+at\s+\d{1,2}:\d{2}\b|$)",
        r"\battendees included\s+(.+?)(?=\.\s|;|$)",
        r"\bparticipants included\s+(.+?)(?=\.\s|;|$)",
        r"\bparticipants were\s+(.+?)(?=\.\s|;|$)",
        r"\battendees\s+(.+?)(?=\s+reviewed\b|\s+discussed\b|\s+covered\b|\.\s|;|$)",
    )
    for pattern in participant_patterns:
        label_match = re.search(pattern, meeting_text, flags=re.IGNORECASE)
        if label_match:
            return split_participants(label_match.group(1))

    with_match = re.search(
        r"\bwith\s+(.+?)(?=\s+in\s+|\s+on\s+\d{4}-\d{2}-\d{2}\b|\s+at\s+\d{1,2}:\d{2}\b|$)",
        meeting_text,
        flags=re.IGNORECASE,
    )
    if with_match:
        return split_participants(with_match.group(1))

    return []


def extract_topic(meeting_text):
    topic_match = re.search(
        r"\b(?:the\s+main\s+topic\s+of\s+the\s+meeting\s+was|the\s+topic\s+of\s+the\s+meeting\s+was|the\s+meeting\s+topic\s+was|the\s+topic\s+was)\s+(.+?)(?=\.\s|;|$)",
        meeting_text,
        flags=re.IGNORECASE,
    )
    if topic_match:
        candidate = clean_capture(topic_match.group(1))
        if candidate and candidate.lower() != "meeting":
            return candidate

    first_sentence = re.split(r"(?<=[.!?])\s+", meeting_text.strip(), maxsplit=1)[0]
    match = re.match(
        r"^\s*(.+?)(?=\s+with\s+|\s+in\s+|\s+on\s+\d{4}-\d{2}-\d{2}\b|\s+at\s+\d{1,2}:\d{2}\b|$)",
        first_sentence,
    )
    if not match:
        return None
    candidate = clean_capture(match.group(1))
    if not candidate:
        return None
    if candidate.lower() == "meeting":
        return None
    return candidate


def is_out_of_scope(meeting_text):
    lowered = meeting_text.lower()
    if any(hint in lowered for hint in OUT_OF_SCOPE_HINTS):
        return True

    if any(re.search(pattern, lowered) for pattern in OUT_OF_SCOPE_PATTERNS):
        return True

    if "conversation with friends" in lowered:
        return True

    signal_count = sum(
        1
        for pattern in MEETING_SIGNAL_PATTERNS
        if re.search(pattern, meeting_text, flags=re.IGNORECASE)
    )
    has_override_signal = any(
        re.search(pattern, meeting_text, flags=re.IGNORECASE)
        for pattern in OVERRIDE_MEETING_PATTERNS
    )

    if len(meeting_text.strip()) < 50 and signal_count == 0:
        return True

    if has_override_signal:
        return False

    return signal_count < 2


def organize_meeting_notes(arguments):
    try:
        if not isinstance(arguments, dict):
            return error_response("missing_field", "meeting_text is required")
        if "meeting_text" not in arguments:
            return error_response("missing_field", "meeting_text is required")

        meeting_text = arguments["meeting_text"]
        if not isinstance(meeting_text, str) or not meeting_text.strip():
            return error_response("invalid_value", "meeting_text must be a non-empty string")

        meeting_text = meeting_text.strip()
        if is_out_of_scope(meeting_text):
            return error_response(
                "out_of_scope",
                "This tool only extracts structured meeting details from provided meeting text.",
            )

        meeting_date = extract_date(meeting_text)
        meeting_time = extract_time(meeting_text)
        location = extract_location(meeting_text)
        participants = extract_participants(meeting_text)
        topic = extract_topic(meeting_text)

        return success_response(
            meeting_text=meeting_text,
            meeting_date=meeting_date,
            meeting_time=meeting_time,
            location=location,
            participants=participants,
            topic=topic,
        )
    except Exception:
        return error_response("internal_error", "An internal error occurred")


def tool_definition():
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "inputSchema": TOOL_INPUT_SCHEMA,
        "annotations": TOOL_ANNOTATIONS,
    }


def initialize_result():
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "serverInfo": SERVER_INFO,
        "capabilities": {"tools": {}},
    }


def jsonrpc_result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_call_result(structured):
    compact_json = json.dumps(structured, ensure_ascii=True, separators=(",", ":"))
    return {
        "content": [
            {
                "type": "text",
                "text": compact_json,
            }
        ],
        "structuredContent": structured,
        "isError": structured["status"] == "error",
    }


def html_page(title, body_html):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: #fffdfa;
      --text: #1f2933;
      --muted: #52606d;
      --accent: #8b5e34;
      --border: #dccfbd;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, #fff7ed 0%, transparent 28%),
        linear-gradient(180deg, #efe7da 0%, var(--bg) 100%);
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 48px 20px 72px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 32px;
      box-shadow: 0 12px 32px rgba(31, 41, 51, 0.08);
    }}
    h1, h2 {{ line-height: 1.15; margin-top: 0; }}
    p, li {{ line-height: 1.6; color: var(--muted); }}
    a {{ color: var(--accent); }}
    code {{
      background: #f3e9d8;
      border-radius: 4px;
      padding: 0.12rem 0.35rem;
    }}
    nav {{
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid var(--border);
    }}
    .eyebrow {{
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 0.8rem;
      color: var(--accent);
      margin-bottom: 12px;
    }}
    ul {{ padding-left: 1.2rem; }}
  </style>
</head>
<body>
  <main>
    <section class="panel">
      {body_html}
      <nav>
        <a href="/">Home</a>
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
        <a href="/support">Support</a>
      </nav>
    </section>
  </main>
</body>
</html>"""


def homepage_html():
    return html_page(
        "Meeting Notes Organizer",
        """
        <div class="eyebrow">Meeting Notes Organizer</div>
        <h1>Meeting Notes Organizer</h1>
        <p>Extracts structured meeting details from raw meeting notes.</p>
        <h2>How to use it</h2>
        <ul>
          <li>Send raw meeting notes or meeting record text to the MCP tool <code>organize_meeting_notes</code>.</li>
          <li>The tool returns only structured fields for date, time, location, participants, topic, missing fields, and the original source text.</li>
          <li>Do not use it for summaries, action items, recommendations, scheduling advice, or non-meeting text.</li>
        </ul>
        <p>Use <code>GET /health</code> for service health and <code>POST /mcp</code> for MCP requests.</p>
        """,
    )


def privacy_html():
    return html_page(
        "Privacy",
        f"""
        <div class="eyebrow">Privacy</div>
        <h1>Privacy</h1>
        <p>This service processes only the text you send in the current request so it can extract structured meeting details.</p>
        <p>The service is stateless. It does not use a database, does not create user accounts, and does not intentionally retain submitted meeting text after the request is completed.</p>
        <p>The service does not sell, share, or enrich user data with external APIs. Any deployment platform logs are subject to that platform's default operational logging.</p>
        <p>If you need support, contact <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>.</p>
        """,
    )


def terms_html():
    return html_page(
        "Terms",
        """
        <div class="eyebrow">Terms</div>
        <h1>Terms</h1>
        <p>This service is limited to deterministic extraction of structured meeting details from provided meeting record text.</p>
        <p>You are responsible for reviewing results before relying on them, confirming that submitted text is appropriate to process, and complying with any privacy or workplace rules that apply to your data.</p>
        <p>The service does not guarantee completeness, suitability, uninterrupted availability, or fitness for any legal, compliance, scheduling, or operational decision.</p>
        <p>Use of the service for summaries, action items, recommendations, professional advice, or unrelated content is outside the intended scope.</p>
        """,
    )


def support_html():
    return html_page(
        "Support",
        f"""
        <div class="eyebrow">Support</div>
        <h1>Support</h1>
        <p>Support email: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
        <p>Users are responsible for submitting only appropriate meeting text, verifying extracted output, and avoiding prohibited uses such as generating advice, summaries, action items, or unrelated content.</p>
        <p>If you encounter extraction issues, boundary errors, or deployment problems, send feedback with the request text, expected behavior, and actual behavior so the issue can be reproduced safely.</p>
        """,
    )


def handle_mcp_request(payload):
    if not isinstance(payload, dict):
        return jsonrpc_error(None, -32600, "Invalid Request")

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        return jsonrpc_result(request_id, initialize_result())

    if method == "tools/list":
        return jsonrpc_result(request_id, {"tools": [tool_definition()]})

    if method == "tools/call":
        if not isinstance(params, dict):
            return jsonrpc_error(request_id, -32602, "Invalid params")
        if params.get("name") != TOOL_NAME:
            return jsonrpc_error(request_id, -32602, f"Unknown tool: {params.get('name')}")
        arguments = params.get("arguments")
        structured = organize_meeting_notes(arguments)
        return jsonrpc_result(request_id, tool_call_result(structured))

    return jsonrpc_error(request_id, -32601, "Method not found")


class MCPRequestHandler(BaseHTTPRequestHandler):
    server_version = "MeetingNotesOrganizer/0.1.0"

    def _write_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, status_code, html_text):
        body = html_text.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_text(self, status_code, text_value):
        body = text_value.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._write_html(200, homepage_html())
            return
        if self.path == "/privacy":
            self._write_html(200, privacy_html())
            return
        if self.path == "/terms":
            self._write_html(200, terms_html())
            return
        if self.path == "/support":
            self._write_html(200, support_html())
            return
        if self.path == "/health":
            self._write_json(200, {"status": "ok"})
            return
        if self.path == "/.well-known/openai-apps-challenge":
            token = os.environ.get("OPENAI_APPS_CHALLENGE", "") or "test"
            self._write_text(200, token)
            return
        if self.path == "/mcp":
            self._write_json(405, {"error": "MCP only accepts POST"})
            return
        self._write_json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/mcp":
            self._write_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._write_json(400, jsonrpc_error(None, -32700, "Parse error"))
            return

        response = handle_mcp_request(payload)
        self._write_json(200, response)

    def log_message(self, format_string, *args):
        return


def run():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), MCPRequestHandler)
    try:
        print(f"Meeting Notes Organizer MCP server listening on http://127.0.0.1:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()

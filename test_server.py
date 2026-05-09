import unittest

import server


class MeetingNotesOrganizerTests(unittest.TestCase):
    def test_sample_1(self):
        result = server.organize_meeting_notes(
            {"meeting_text": "Schedule review with Nina and Alex in Room 12 on 2026-06-01 at 14:30"}
        )
        self.assertEqual(
            result,
            {
                "status": "success",
                "meeting_date": "2026-06-01",
                "meeting_time": "14:30",
                "location": "Room 12",
                "participants": ["Nina", "Alex"],
                "topic": "Schedule review",
                "missing_fields": [],
                "source_text": "Schedule review with Nina and Alex in Room 12 on 2026-06-01 at 14:30",
            },
        )

    def test_sample_2(self):
        result = server.organize_meeting_notes(
            {"meeting_text": "Meeting with Emma in Conference Room B at 16:00"}
        )
        self.assertEqual(
            result,
            {
                "status": "success",
                "meeting_date": None,
                "meeting_time": "16:00",
                "location": "Conference Room B",
                "participants": ["Emma"],
                "topic": None,
                "missing_fields": ["meeting_date", "topic"],
                "source_text": "Meeting with Emma in Conference Room B at 16:00",
            },
        )

    def test_sample_3(self):
        result = server.organize_meeting_notes(
            {"meeting_text": "Team sync on 2026-05-03 at 09:30"}
        )
        self.assertEqual(
            result,
            {
                "status": "success",
                "meeting_date": "2026-05-03",
                "meeting_time": "09:30",
                "location": None,
                "participants": [],
                "topic": "Team sync",
                "missing_fields": ["location", "participants"],
                "source_text": "Team sync on 2026-05-03 at 09:30",
            },
        )

    def test_positive_product_launch_review_meeting(self):
        result = server.organize_meeting_notes(
            {
                "meeting_text": "On 2026-06-01 at 14:30, the product team held a launch review meeting in Room 12. Attendees included Alex, Nina, and John. The main topic of the meeting was product launch review."
            }
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["meeting_date"], "2026-06-01")
        self.assertEqual(result["meeting_time"], "14:30")
        self.assertEqual(result["location"], "Room 12")
        self.assertEqual(result["participants"], ["Alex", "Nina", "John"])
        self.assertEqual(result["topic"], "product launch review")

    def test_positive_project_kickoff_meeting(self):
        result = server.organize_meeting_notes(
            {
                "meeting_text": "The project kickoff meeting took place on 2026-06-02 in Conference Room B. Participants were Emma, Michael, and Sarah. The topic of the meeting was project kickoff and first sprint planning."
            }
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["meeting_date"], "2026-06-02")
        self.assertEqual(result["location"], "Conference Room B")
        self.assertEqual(result["participants"], ["Emma", "Michael", "Sarah"])
        self.assertEqual(result["topic"], "project kickoff and first sprint planning")

    def test_positive_team_sync(self):
        result = server.organize_meeting_notes(
            {
                "meeting_text": "During the team sync on 2026-06-03 at 09:30 in Main Hall, attendees John, Lisa, and Kevin reviewed ongoing tasks. The meeting topic was team sync and milestone review."
            }
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["meeting_date"], "2026-06-03")
        self.assertEqual(result["meeting_time"], "09:30")
        self.assertEqual(result["location"], "Main Hall")
        self.assertEqual(result["participants"], ["John", "Lisa", "Kevin"])
        self.assertEqual(result["topic"], "team sync and milestone review")

    def test_positive_launch_campaign_planning_meeting(self):
        result = server.organize_meeting_notes(
            {
                "meeting_text": "On 2026-06-04 at 11:00, the marketing team met in Room 5 for a launch campaign planning meeting. Participants included Olivia, Mark, and Sophia. The topic was launch campaign planning."
            }
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["meeting_date"], "2026-06-04")
        self.assertEqual(result["meeting_time"], "11:00")
        self.assertEqual(result["location"], "Room 5")
        self.assertEqual(result["participants"], ["Olivia", "Mark", "Sophia"])
        self.assertEqual(result["topic"], "launch campaign planning")

    def test_missing_meeting_text(self):
        self.assertEqual(
            server.organize_meeting_notes({}),
            {
                "status": "error",
                "error_type": "missing_field",
                "message": "meeting_text is required",
            },
        )

    def test_empty_meeting_text(self):
        self.assertEqual(
            server.organize_meeting_notes({"meeting_text": "   "}),
            {
                "status": "error",
                "error_type": "invalid_value",
                "message": "meeting_text must be a non-empty string",
            },
        )

    def test_out_of_scope(self):
        self.assertEqual(
            server.organize_meeting_notes({"meeting_text": "Please summarize this meeting with Emma"}),
            {
                "status": "error",
                "error_type": "out_of_scope",
                "message": "This tool only extracts structured meeting details from provided meeting text.",
            },
        )

    def test_negative_casual_conversation_is_out_of_scope(self):
        self.assertEqual(
            server.organize_meeting_notes(
                {
                    "meeting_text": "Yesterday I went to the park and had a long conversation about gardening with friends. We talked about flowers, soil, and weekend plans, but this was not a meeting note or formal meeting record."
                }
            ),
            {
                "status": "error",
                "error_type": "out_of_scope",
                "message": "This tool only extracts structured meeting details from provided meeting text.",
            },
        )

    def test_negative_summary_and_action_items_is_out_of_scope(self):
        self.assertEqual(
            server.organize_meeting_notes(
                {
                    "meeting_text": "Summarize this meeting and generate action items for every participant."
                }
            ),
            {
                "status": "error",
                "error_type": "out_of_scope",
                "message": "This tool only extracts structured meeting details from provided meeting text.",
            },
        )

    def test_negative_advice_request_is_out_of_scope(self):
        self.assertEqual(
            server.organize_meeting_notes(
                {
                    "meeting_text": "Should I schedule more meetings next week to improve team productivity? Please give me advice."
                }
            ),
            {
                "status": "error",
                "error_type": "out_of_scope",
                "message": "This tool only extracts structured meeting details from provided meeting text.",
            },
        )

    def test_negative_financial_request_is_out_of_scope(self):
        self.assertEqual(
            server.organize_meeting_notes(
                {
                    "meeting_text": "I need financial advice on whether to invest $10,000 in stocks or crypto this month."
                }
            ),
            {
                "status": "error",
                "error_type": "out_of_scope",
                "message": "This tool only extracts structured meeting details from provided meeting text.",
            },
        )

    def test_tools_list_contains_one_tool_with_annotations(self):
        result = server.handle_mcp_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        self.assertEqual(len(result["result"]["tools"]), 1)
        self.assertEqual(result["result"]["tools"][0]["name"], "organize_meeting_notes")
        self.assertEqual(
            result["result"]["tools"][0]["annotations"],
            {
                "readOnlyHint": True,
                "destructiveHint": False,
                "openWorldHint": False,
            },
        )

    def test_tools_call_content_is_compact_json_only(self):
        result = server.handle_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "organize_meeting_notes",
                    "arguments": {
                        "meeting_text": "On 2026-06-01 at 14:30, the product team held a launch review meeting in Room 12. Attendees included Alex, Nina, and John. The main topic of the meeting was product launch review."
                    },
                },
            }
        )
        structured = result["result"]["structuredContent"]
        self.assertEqual(
            result["result"]["content"][0]["text"],
            server.json.dumps(structured, ensure_ascii=True, separators=(",", ":")),
        )

    def test_tools_call_error_content_is_compact_json_only(self):
        result = server.handle_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "organize_meeting_notes",
                    "arguments": {
                        "meeting_text": "Summarize this meeting and generate action items for every participant."
                    },
                },
            }
        )
        structured = result["result"]["structuredContent"]
        self.assertEqual(
            result["result"]["content"][0]["text"],
            server.json.dumps(structured, ensure_ascii=True, separators=(",", ":")),
        )


if __name__ == "__main__":
    unittest.main()

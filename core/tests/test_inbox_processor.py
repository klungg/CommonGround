import asyncio

from agent_core.framework.inbox_processor import InboxProcessor


def test_inbox_processor_constructs_cli_style_parts() -> None:
    text_segments = [
        {"type": "preamble", "text": "\n--- Content from referenced files ---"},
        {"type": "file_intro", "relative_path": "docs/a.txt", "text": "\nContent from @docs/a.txt:\n"},
        {"type": "file_body", "relative_path": "docs/a.txt", "text": "Line 1\nLine 2"},
        {"type": "epilogue", "text": "\n--- End of content ---"},
    ]

    context = {
        "state": {
            "inbox": [
                {
                    "item_id": "inbox_test",
                    "source": "USER_PROMPT",
                    "payload": {
                        "prompt": "Tell me about @docs/a.txt",
                        "text_segments": text_segments,
                        "aggregated_text": "".join(segment["text"] for segment in text_segments),
                    },
                    "consumption_policy": "consume_on_read",
                    "metadata": {"created_at": "2025-01-01T00:00:00Z"},
                }
            ],
            "messages": [],
        },
        "refs": {
            "team": {"turns": []},
            "run": {
                "config": {
                    "shared_llm_configs_ref": {
                        "llm_default": {
                            "name": "default",
                            "is_active": True,
                            "is_deleted": False,
                            "rev": 1,
                            "config": {"model": "fake-model"},
                        }
                    }
                },
                "runtime": {"turn_manager": None},
            },
        },
        "meta": {"agent_id": "test-agent", "run_id": "run-test"},
    }

    profile = {"llm_config_ref": "default"}
    processor = InboxProcessor(profile, context)
    result = asyncio.run(processor.process())

    messages = result["messages_for_llm"]
    assert len(messages) == 1
    message = messages[0]

    assert message["role"] == "user"
    content = message["content"]
    assert isinstance(content, list)

    texts = [part["text"] for part in content if part.get("type") == "text"]
    assert texts == [
        "Tell me about @docs/a.txt",
        "\n--- Content from referenced files ---",
        "\nContent from @docs/a.txt:\n",
        "Line 1\nLine 2",
        "\n--- End of content ---",
    ]

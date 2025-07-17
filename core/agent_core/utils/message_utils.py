import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def tool_call_safenet(messages: List[Dict], agent_id: str) -> List[Dict]:
    """
    A final defensive mechanism to ensure the integrity of the message history
    before sending it to an LLM. It checks for and corrects proximity and
    symmetry violations between 'assistant' tool_calls and 'tool' responses.

    Args:
        messages: The list of messages to be sanitized.
        agent_id: The ID of the agent whose messages are being processed, for logging.

    Returns:
        A new list of messages that is guaranteed to be compliant with the
        assistant->tool calling convention.
    """
    if not messages:
        return []

    corrected_messages = []
    i = 0
    while i < len(messages):
        current_msg = messages[i]
        
        # Check if this is an assistant message that is making tool calls
        if current_msg.get("role") == "assistant" and current_msg.get("tool_calls"):
            # This is the start of a potential tool interaction block.
            assistant_msg_with_calls = current_msg
            corrected_messages.append(assistant_msg_with_calls)
            
            expected_tool_ids = {tc['id'] for tc in assistant_msg_with_calls.get("tool_calls", [])}
            
            # Scan ahead to find the corresponding tool responses
            j = i + 1
            tool_results_block = []
            interloper_block = []
            
            while j < len(messages):
                msg_role = messages[j].get("role")
                if msg_role == "tool":
                    tool_results_block.append(messages[j])
                    j += 1
                elif msg_role == "assistant":
                    # Found next assistant message, this is normal - stop scanning
                    break
                else:
                    # Found a non-tool, non-assistant message (like 'user')
                    # Check if we're expecting more tool responses
                    current_tool_ids = {tr.get("tool_call_id") for tr in tool_results_block 
                                      if tr.get("tool_call_id") is not None}
                    missing_responses = expected_tool_ids - current_tool_ids
                    
                    if missing_responses:
                        # We're still expecting tool responses, so this is an interloper
                        interloper_block.append(messages[j])
                        j += 1
                    else:
                        # All expected tool responses have been found, this is just the next normal message
                        break
            
            # --- 1. Proximity Correction ---
            # Only log error and modify if there are actual interloper messages
            if interloper_block:
                error_msg = (
                    f"[SAFENET ERROR] Proximity violation detected for agent '{agent_id}'. "
                    f"Found {len(interloper_block)} message(s) between tool call and tool response. Reordering. "
                    f"Messages: {[msg.get('role', 'unknown') for msg in interloper_block]}. "
                    f"Tool calls: {len(assistant_msg_with_calls.get('tool_calls', []))}, Tool responses: {len(tool_results_block)}."
                )
                logger.error(error_msg)
                # Create copies of interloper messages with warning instead of modifying originals
                modified_interloper_block = []
                for interloper_msg in interloper_block:
                    modified_msg = interloper_msg.copy()
                    original_content = modified_msg.get("content", "")
                    modified_msg["content"] = f"{error_msg}\n\n{original_content}"
                    modified_interloper_block.append(modified_msg)
                interloper_block = modified_interloper_block

            # --- 2. Symmetry Correction ---
            # Filter out None values when building the found_tool_ids set
            found_tool_ids = {tr.get("tool_call_id") for tr in tool_results_block 
                            if tr.get("tool_call_id") is not None}
            
            # Case 1: More calls than results
            missing_ids = expected_tool_ids - found_tool_ids
            if missing_ids:
                error_msg = (
                    f"[SAFENET ERROR] Symmetry violation detected for agent '{agent_id}'. "
                    f"Missing responses for tool_call_ids: {missing_ids}. Injecting error responses."
                )
                logger.error(error_msg)
                for missing_id in missing_ids:
                    # Find the original tool name for better error reporting
                    tool_name = next((tc.get('function', {}).get('name') for tc in assistant_msg_with_calls.get("tool_calls", []) if tc.get('id') == missing_id), "unknown_tool")
                    error_response = {
                        "role": "tool",
                        "tool_call_id": missing_id,
                        "name": tool_name,
                        "content": f'{{"error": "no_response_from_tool", "message": "{error_msg}"}}'
                    }
                    tool_results_block.append(error_response)

            # Case 2: More results than calls
            extra_ids = found_tool_ids - expected_tool_ids
            if extra_ids:
                error_msg = (
                    f"[SAFENET ERROR] Symmetry violation detected for agent '{agent_id}'. "
                    f"Found extra tool responses for non-existent calls: {extra_ids}. Neutralizing them."
                )
                logger.error(error_msg)
                # Create new list with modified tool messages instead of modifying in place
                corrected_tool_block = []
                for tool_msg in tool_results_block:
                    if tool_msg.get("tool_call_id") in extra_ids:
                        # Create a copy and neutralize it
                        neutralized_msg = tool_msg.copy()
                        neutralized_msg["role"] = "assistant"
                        original_content = neutralized_msg.get("content", "")
                        neutralized_msg["content"] = f"{error_msg}\n\nOriginal tool response content:\n{original_content}"
                        # Remove tool-specific keys
                        neutralized_msg.pop("tool_call_id", None)
                        neutralized_msg.pop("name", None)
                        corrected_tool_block.append(neutralized_msg)
                    else:
                        corrected_tool_block.append(tool_msg)
                tool_results_block = corrected_tool_block

            # Append the corrected blocks in the right order
            corrected_messages.extend(tool_results_block)
            corrected_messages.extend(interloper_block)
            
            # Jump the main loop index past the processed block
            i = j
        else:
            # Not a tool-calling message, just append and move on
            corrected_messages.append(current_msg)
            i += 1
            
    return corrected_messages

def test_tool_call_safenet():
    """
    Tests various scenarios for the tool_call_safenet function.
    """
    print("=" * 60)
    print("Starting tests for tool_call_safenet function")
    print("=" * 60)
    
    # Test Case 1: Normal Sequence
    def test_normal_sequence():
        print("\nTest Case 1: Normal Sequence")
        messages = [
            {'role': 'user', 'content': 'What is the latest news about Trump?'},
            {
                'role': 'assistant', 
                'content': '', 
                'tool_calls': [
                    {
                        'id': 'call_123',
                        'function': {'name': 'search_news'},
                        'type': 'function'
                    }
                ]
            },
            {
                'role': 'tool',
                'content': 'Found some news...',
                'tool_call_id': 'call_123',
                'name': 'search_news'
            },
            {'role': 'user', 'content': 'Thank you'}
        ]
        
        result = tool_call_safenet(messages, "test_agent")
        print(f"Original message count: {len(messages)}")
        print(f"Processed message count: {len(result)}")
        print(" Normal sequence test completed")
        return result

    # Test Case 2: Proximity Violation
    def test_proximity_violation():
        print("\nTest Case 2: Proximity Violation")
        messages = [
            {'role': 'user', 'content': 'Search something'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [
                    {
                        'id': 'call_456',
                        'function': {'name': 'search'},
                        'type': 'function'
                    }
                ]
            },
            {'role': 'user', 'content': 'Wait, I have another question'},  # This is an interloper message
            {
                'role': 'tool',
                'content': 'Search results...',
                'tool_call_id': 'call_456',
                'name': 'search'
            }
        ]
        
        result = tool_call_safenet(messages, "test_agent")
        print(f"Original message count: {len(messages)}")
        print(f"Processed message count: {len(result)}")
        print(" Proximity violation test completed")
        return result

    # Test Case 3: Missing Tool Response
    def test_missing_tool_response():
        print("\nTest Case 3: Missing Tool Response")
        messages = [
            {'role': 'user', 'content': 'Call two tools'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [
                    {
                        'id': 'call_789',
                        'function': {'name': 'tool1'},
                        'type': 'function'
                    },
                    {
                        'id': 'call_abc',
                        'function': {'name': 'tool2'},
                        'type': 'function'
                    }
                ]
            },
            {
                'role': 'tool',
                'content': 'Tool 1 response',
                'tool_call_id': 'call_789',
                'name': 'tool1'
            }
            # Note: call_abc response is missing
        ]
        
        result = tool_call_safenet(messages, "test_agent")
        print(f"Original message count: {len(messages)}")
        print(f"Processed message count: {len(result)}")
        print(" Missing response test completed")
        return result

    # Test Case 4: Extra Tool Response
    def test_extra_tool_response():
        print("\nTest Case 4: Extra Tool Response")
        messages = [
            {'role': 'user', 'content': 'Call a tool'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [
                    {
                        'id': 'call_def',
                        'function': {'name': 'tool1'},
                        'type': 'function'
                    }
                ]
            },
            {
                'role': 'tool',
                'content': 'Correct response',
                'tool_call_id': 'call_def',
                'name': 'tool1'
            },
            {
                'role': 'tool',
                'content': 'Extra response',
                'tool_call_id': 'call_xyz',  # This ID does not exist
                'name': 'unknown_tool'
            }
        ]
        
        result = tool_call_safenet(messages, "test_agent")
        print(f"Original message count: {len(messages)}")
        print(f"Processed message count: {len(result)}")
        print(" Extra response test completed")
        return result

    # Test Case 5: Tool Response Missing tool_call_id
    def test_missing_tool_call_id():
        print("\nTest Case 5: Tool Response Missing tool_call_id")
        messages = [
            {'role': 'user', 'content': 'Call a tool'},
            {
                'role': 'assistant',
                'content': '',
                'tool_calls': [
                    {
                        'id': 'call_ghi',
                        'function': {'name': 'tool1'},
                        'type': 'function'
                    }
                ]
            },
            {
                'role': 'tool',
                'content': 'Response content',
                # Note: tool_call_id is missing here
                'name': 'tool1'
            }
        ]
        
        result = tool_call_safenet(messages, "test_agent")
        print(f"Original message count: {len(messages)}")
        print(f"Processed message count: {len(result)}")
        print("Missing ID test completed")
        return result

    # Test Case 6: Complex Sequence - Multiple tool call blocks
    def test_complex_sequence():
        print("\nTest Case 6: Complex Sequence - Multiple tool call blocks")
        messages = [
            {'role': 'user', 'content': 'Any recent news about Trump?'},
            {
                'role': 'assistant', 
                'content': '', 
                'tool_calls': [
                    {
                        'id': 'call_1',
                        'function': {'name': 'manage_work_modules'},
                        'type': 'function'
                    }
                ]
            },
            {
                'role': 'tool',
                'content': 'Failed on action 1...',
                'tool_call_id': 'call_1',
                'name': 'manage_work_modules'
            },
            {
                'role': 'assistant', 
                'content': '', 
                'tool_calls': [
                    {
                        'id': 'call_2',
                        'function': {'name': 'manage_work_modules'},
                        'type': 'function'
                    }
                ]
            },
            {
                'role': 'tool',
                'content': '{"summary": "Successfully updated..."}',
                'tool_call_id': 'call_2',
                'name': 'manage_work_modules'
            },
            {'role': 'user', 'content': '### Current Work Modules Status...'}
        ]
        
        result = tool_call_safenet(messages, "test_agent")
        print(f"Original message count: {len(messages)}")
        print(f"Processed message count: {len(result)}")
        print("Complex sequence test completed")
        return result

    # Run all tests
    try:
        test_normal_sequence()
        test_proximity_violation()
        test_missing_tool_response()
        test_extra_tool_response()
        test_missing_tool_call_id()
        test_complex_sequence()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()


def run_detailed_test():
    """
    Runs detailed tests, showing the results of each test case.
    """
    print("Running detailed tests...")
    
    # Simple normal case
    print("\n" + "="*50)
    print("Detailed Test: Normal Case")
    normal_messages = [
        {'role': 'user', 'content': 'Hello'},
        {
            'role': 'assistant',
            'content': '',
            'tool_calls': [{'id': 'call_test', 'function': {'name': 'test_tool'}, 'type': 'function'}]
        },
        {
            'role': 'tool',
            'content': 'Tool response',
            'tool_call_id': 'call_test',
            'name': 'test_tool'
        },
        {'role': 'assistant', 'content': 'Processing complete'}
    ]
    
    result = tool_call_safenet(normal_messages, "test")
    print("Original messages:")
    for i, msg in enumerate(normal_messages):
        print(f"  {i}: {msg.get('role')} - {msg.get('content', '')[:50]}...")
    
    print("Processed messages:")
    for i, msg in enumerate(result):
        print(f"  {i}: {msg.get('role')} - {msg.get('content', '')[:50]}...")


if __name__ == "__main__":
    # If this file is run directly, execute the tests
    test_tool_call_safenet()
    print("\n" + "-"*50)
    run_detailed_test()

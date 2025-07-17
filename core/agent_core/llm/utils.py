import ast
import json
import uuid
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def _parse_arguments_string(args_str: str, agent_id: str) -> Dict[str, Any]:
    """
    Parses a string of arguments (e.g., 'query="hello", limit=5') into a dictionary.
    Uses ast.literal_eval for safe evaluation of literals.
    """
    args_dict = {}
    if not args_str.strip():
        return args_dict

    try:
        # Wrap in a dummy function call 'dummy(...)' to make the args_str parseable
        # by ast.parse as a Call node's arguments.
        # Example: if args_str is 'k1="v1", k2=123', we parse 'dummy(k1="v1", k2=123)'
        # ast.parse creates a Module -> Expr -> Call node.
        # The Call node's 'args' and 'keywords' attributes hold the parsed arguments.
        node = ast.parse(f"dummy({args_str})")
        
        if not isinstance(node, ast.Module) or \
           not node.body or \
           not isinstance(node.body[0], ast.Expr) or \
           not isinstance(node.body[0].value, ast.Call):
            logger.error("ast_parsing_failed", extra={"agent_id": agent_id, "args_str": args_str})
            return {}

        call_node = node.body[0].value

        # Positional arguments (less common for LLM tools but handled for completeness)
        for i, arg_node_val in enumerate(call_node.args):
            try:
                args_dict[f"arg{i}"] = ast.literal_eval(arg_node_val)
            except ValueError as e_literal:
                # If literal_eval fails, it might be a more complex expression or non-literal.
                # For LLM tools, arguments are typically literals.
                logger.warning("positional_arg_literal_eval_failed", extra={"agent_id": agent_id, "arg_index": i, "args_str": args_str, "error_message": str(e_literal), "node_dump": ast.dump(arg_node_val)})
                # Fallback: try to unparse if possible (Python 3.9+) or store as string.
                # For now, we'll skip if it's not a simple literal.
                # If you have Python 3.9+, you could use ast.unparse(arg_node_val)
                args_dict[f"arg{i}"] = "Error: Non-literal positional argument"


        # Keyword arguments
        for keyword_node in call_node.keywords:
            if keyword_node.arg is None: # Handles **kwargs, which we don't expect here
                logger.warning("kwargs_not_supported", extra={"agent_id": agent_id, "args_str": args_str})
                continue
            try:
                args_dict[keyword_node.arg] = ast.literal_eval(keyword_node.value)
            except ValueError as e_literal:
                logger.warning("keyword_arg_literal_eval_failed", extra={"agent_id": agent_id, "keyword_arg": keyword_node.arg, "args_str": args_str, "error_message": str(e_literal), "node_dump": ast.dump(keyword_node.value)})
                # Fallback for keyword arguments
                args_dict[keyword_node.arg] = f"Error: Non-literal value for {keyword_node.arg}"

    except SyntaxError as e_syntax:
        logger.error("syntax_error_parsing_args", extra={"agent_id": agent_id, "args_str": args_str, "error_message": str(e_syntax)})
        return {} # Return empty if basic parsing fails
    except Exception as e_general:
        logger.error("general_error_parsing_args", extra={"agent_id": agent_id, "args_str": args_str, "error_message": str(e_general)}, exc_info=True)
        return {}
        
    return args_dict

def extract_tool_calls_from_content(content: str, agent_id: str) -> List[Dict]:
    """
    Extracts tool calls from a string based on the <tool_code>print(...)</tool_code> pattern.
    """
    extracted_tool_calls = []
    # Regex to find <tool_code>print(ActualToolCall(...))</tool_code>
    # It captures the content inside print(...), which is ActualToolCall(...)
    # Using re.DOTALL so that '.' matches newlines within the print() arguments.
    pattern = re.compile(r"<tool_code>\s*print\((.*?)\)\s*</tool_code>", re.DOTALL)

    for match in pattern.finditer(content):
        # tool_call_expression_str is the content of print(), e.g., "MyTool(arg1="val1", arg2=123)"
        tool_call_expression_str = match.group(1).strip()
        
        logger.info("fallback_tool_call_found", extra={"agent_id": agent_id, "tool_call_expression": tool_call_expression_str})

        # Regex to extract tool name and the arguments string from "ToolName(args_string)"
        # ToolName must be a valid Python identifier.
        # args_string is everything between the parentheses.
        call_match = re.match(r"([a-zA-Z_]\w*)\s*\((.*)\)", tool_call_expression_str, re.DOTALL)
        
        if not call_match:
            logger.warning("tool_call_parsing_failed", extra={"agent_id": agent_id, "tool_call_expression": tool_call_expression_str})
            continue

        tool_name = call_match.group(1)
        args_str = call_match.group(2).strip() # This is the raw string of arguments

        try:
            # Parse the arguments string into a dictionary
            arguments_dict = _parse_arguments_string(args_str, agent_id)
            # Convert the dictionary of arguments into a JSON string
            arguments_json_str = json.dumps(arguments_dict)
        except Exception as e_json:
            logger.error("json_conversion_failed", extra={"agent_id": agent_id, "tool_name": tool_name, "args_str": args_str, "error_message": str(e_json)}, exc_info=True)
            arguments_json_str = "{}" # Fallback to empty JSON object

        tool_call_id = f"fallback_{agent_id}_{uuid.uuid4()}"
        extracted_tool_calls.append({
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": arguments_json_str
            }
        })
        logger.info("fallback_tool_call_extracted", extra={"agent_id": agent_id, "tool_call_id": tool_call_id, "tool_name": tool_name, "arguments_json": arguments_json_str})

    if extracted_tool_calls:
        logger.info("fallback_extraction_complete", extra={"agent_id": agent_id, "tool_calls_count": len(extracted_tool_calls)})
    return extracted_tool_calls

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional, Type

from langchain_core.messages import (
	AIMessage,
	BaseMessage,
	HumanMessage,
	SystemMessage,
	ToolMessage,
)

logger = logging.getLogger(__name__)


# def extract_json_from_model_output(content: str) -> dict:
# 	"""Extract JSON from model output, handling both plain JSON and code-block-wrapped JSON."""
# 	try:
# 		# If content is wrapped in code blocks, extract just the JSON part
# 		if '```' in content:
# 			# Find the JSON content between code blocks
# 			content = content.split('```')[1]
# 			# Remove language identifier if present (e.g., 'json\n')
# 			if '\n' in content:
# 				content = content.split('\n', 1)[1]
# 		# Parse the cleaned content
# 		return json.loads(content)
# 	except json.JSONDecodeError as e:
# 		logger.warning(f'Failed to parse model output: {content} {str(e)}')
# 		raise ValueError('Could not parse response.')


def extract_json_from_model_output(content: str) -> dict:
    logger.info("Extracting JSON from model output...")

    # 1. Extract all blocks inside <|python_start|> and <|python_end|>
    matches = re.findall(r"<\|python_start\|>(.*?)<\|python_end\|>", content, re.DOTALL)
    if not matches:
        logger.warning("No <|python_start|> block found.")
        raise ValueError("No recognizable JSON block found.")

    for i, block in enumerate(matches):
        block = block.strip()
        logger.debug(f"Trying block {i+1}: {block[:200]}...")

        try:
            # 2. Try parsing the block as JSON
            parsed = json.loads(block)

            # 3. Handle function call format with stringified "arguments"
            if isinstance(parsed, dict) and parsed.get("type") == "function":
                arguments = parsed.get("function", {}).get("arguments")
                if arguments:
                    try:
                        inner = json.loads(arguments)
                        logger.info("Parsed function arguments successfully.")
                        return inner
                    except json.JSONDecodeError:
                        logger.warning("Function 'arguments' field is not valid JSON.")

            # 4. Handle legacy list-of-functions format
            if isinstance(parsed, list):
                for func in parsed:
                    if func.get("type") == "function":
                        arguments = func.get("function", {}).get("arguments")
                        if arguments:
                            try:
                                inner = json.loads(arguments)
                                logger.info("Parsed function list item arguments successfully.")
                                return inner
                            except json.JSONDecodeError:
                                logger.warning("Function list item 'arguments' not valid JSON.")

            # 5. Handle dict with stringified "parameters"
            if isinstance(parsed, dict) and "parameters" in parsed:
                try:
                    parsed["parameters"] = json.loads(parsed["parameters"])
                    logger.info("Parsed top-level dict with 'parameters'.")
                    return parsed
                except json.JSONDecodeError:
                    logger.warning("'parameters' field is not valid JSON.")

            # 6. If already valid dict structure
            if isinstance(parsed, dict):
                logger.info("Parsed direct dict structure.")
                return parsed

        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode failed for block {i+1}: {str(e)}")

    # All attempts failed
    logger.error("All attempts to parse JSON failed.")
    raise ValueError("Could not parse model output.")



def convert_input_messages(input_messages: list[BaseMessage], model_name: Optional[str]) -> list[BaseMessage]:
	"""Convert input messages to a format that is compatible with the planner model"""
	if model_name is None:
		return input_messages
	if model_name == 'deepseek-reasoner' or 'deepseek-r1' in model_name:
		converted_input_messages = _convert_messages_for_non_function_calling_models(input_messages)
		merged_input_messages = _merge_successive_messages(converted_input_messages, HumanMessage)
		merged_input_messages = _merge_successive_messages(merged_input_messages, AIMessage)
		return merged_input_messages
	return input_messages


def _convert_messages_for_non_function_calling_models(input_messages: list[BaseMessage]) -> list[BaseMessage]:
	"""Convert messages for non-function-calling models"""
	output_messages = []
	for message in input_messages:
		if isinstance(message, HumanMessage):
			output_messages.append(message)
		elif isinstance(message, SystemMessage):
			output_messages.append(message)
		elif isinstance(message, ToolMessage):
			output_messages.append(HumanMessage(content=message.content))
		elif isinstance(message, AIMessage):
			# check if tool_calls is a valid JSON object
			if message.tool_calls:
				tool_calls = json.dumps(message.tool_calls)
				output_messages.append(AIMessage(content=tool_calls))
			else:
				output_messages.append(message)
		else:
			raise ValueError(f'Unknown message type: {type(message)}')
	return output_messages


def _merge_successive_messages(messages: list[BaseMessage], class_to_merge: Type[BaseMessage]) -> list[BaseMessage]:
	"""Some models like deepseek-reasoner dont allow multiple human messages in a row. This function merges them into one."""
	merged_messages = []
	streak = 0
	for message in messages:
		if isinstance(message, class_to_merge):
			streak += 1
			if streak > 1:
				if isinstance(message.content, list):
					merged_messages[-1].content += message.content[0]['text']  # type:ignore
				else:
					merged_messages[-1].content += message.content
			else:
				merged_messages.append(message)
		else:
			merged_messages.append(message)
			streak = 0
	return merged_messages


def save_conversation(input_messages: list[BaseMessage], response: Any, target: str, encoding: Optional[str] = None) -> None:
	"""Save conversation history to file."""

	# create folders if not exists
	if dirname := os.path.dirname(target):
		os.makedirs(dirname, exist_ok=True)

	with open(
		target,
		'w',
		encoding=encoding,
	) as f:
		_write_messages_to_file(f, input_messages)
		_write_response_to_file(f, response)


def _write_messages_to_file(f: Any, messages: list[BaseMessage]) -> None:
	"""Write messages to conversation file"""
	for message in messages:
		f.write(f' {message.__class__.__name__} \n')

		if isinstance(message.content, list):
			for item in message.content:
				if isinstance(item, dict) and item.get('type') == 'text':
					f.write(item['text'].strip() + '\n')
		elif isinstance(message.content, str):
			try:
				content = json.loads(message.content)
				f.write(json.dumps(content, indent=2) + '\n')
			except json.JSONDecodeError:
				f.write(message.content.strip() + '\n')

		f.write('\n')


def _write_response_to_file(f: Any, response: Any) -> None:
	"""Write model response to conversation file"""
	f.write(' RESPONSE\n')
	f.write(json.dumps(json.loads(response.model_dump_json(exclude_unset=True)), indent=2))

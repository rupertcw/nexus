import os
from abc import ABC, abstractmethod
from app.retriever import Retriever
from app.duckdb_engine import DuckDBEngine
import logging
import json

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


HYBRID_ROUTER_SYSTEM_PROMPT = """You are a hybrid AI knowledge router.
You have access to unstructured documents via 'search_documents' and structured analytical data via 'query_parquet'.

CRITICAL: You are a specialized tool-calling engine. 
- NEVER use the format <function=...>. This is an invalid internal format.
- To use a tool, use the built-in tool calling functionality ONLY.
- Output NO text before or after a tool call.

Here is the available Parquet database schema overview:
{schema_context}
"""


class AgentLLMInterface(ABC):
    @abstractmethod
    def invoke(self, system_prompt: str, messages: list):
        pass


class DummyAgentLLM(AgentLLMInterface):
    def __init__(self, duckdb_engine: DuckDBEngine, retriever: Retriever, tools: list):
        self.duckdb_engine = duckdb_engine
        self.retriever = retriever
        self.tools = tools

    def invoke(self, system_prompt: str, messages: list):
        logger.info("Invoking DummyAgentLLM (Mock Mode)")

        last_msg = messages[-1]
        # Inspect if we are on Turn 1 (pure plaintext user prompt) or Turn 2 (returning tool blocks)
        if last_msg["role"] == "user" and isinstance(last_msg["content"], str):
            prompt = last_msg["content"].lower()
            # TODO: this is ugly - fix
            if "sql" in prompt or "travel spend" in prompt or "q3" in prompt:
                # Dynamically find the first parquet file to make the "mock" real
                data_dir = self.duckdb_engine.data_dir
                files = [f for f in os.listdir(data_dir) if f.endswith(".parquet")]
                target_path = (
                    os.path.join(data_dir, files[0]) if files else "mock_table"
                )

                return {
                    "stop_reason": "tool_use",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "query_parquet",
                            "input": {
                                "sql_query": f"SELECT * FROM '{target_path}' LIMIT 5"
                            },
                            "id": "tool_1",
                        }
                    ],
                }
            else:
                return {
                    "stop_reason": "tool_use",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "search_documents",
                            "input": {"query": prompt},
                            "id": "tool_2",
                        }
                    ],
                }

        # We are on Turn 2 (Tool result provided by AgentRouter)
        tool_res = ""
        if isinstance(last_msg["content"], list) and last_msg["content"]:
            tool_res = last_msg["content"][0].get("content", "")

        # Refactored for natural language responses as requested
        prompt_low = str(messages[0]["content"]).lower()
        if "sql" in prompt_low or "travel spend" in prompt_low or "q3" in prompt_low:
            return {
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": f"I've analyzed the structured dataset for your query (Executed SELECT query). Here is the relevant breakdown from the requested tables:\n\n{tool_res[:300]}",
                    }
                ],
            }
        else:
            return {
                "stop_reason": "end_turn",
                "content": [
                    {
                        "type": "text",
                        "text": f"I successfully searched the document knowledge base for your inquiry. Based on the snippets found, it appears that:\n\n{tool_res[:300]}...\n\nYou can review the specific document references below for more detail.",
                    }
                ],
            }


class AnthropicAgentLLM(AgentLLMInterface):
    def __init__(self, tools: list):
        from anthropic import Anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=api_key)
        self.tools = tools

    def invoke(self, system_prompt: str, messages: list):
        logger.info("Invoking AnthropicAgentLLM")
        # Anthropic SDK handles its own response objects, we just need to wrap them so AgentRouter can use them.
        res = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
            tools=self.tools,
        )
        # Convert Anthropic response object to our internal dict format
        return {
            "stop_reason": res.stop_reason,
            "content": [
                {
                    "type": b.type,
                    "text": getattr(b, "text", ""),
                    "name": getattr(b, "name", ""),
                    "input": getattr(b, "input", {}),
                    "id": getattr(b, "id", ""),
                }
                for b in res.content
            ],
        }


class GroqAgentLLM(AgentLLMInterface):
    def __init__(self, tools: list):
        from groq import Groq

        api_key = os.environ.get("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)
        self.tools = tools
        # 1. Map Anthropic-style tools to Groq-style (OpenAI function calling)
        self.groq_tools = []
        for tool in self.tools:
            self.groq_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["input_schema"],
                    },
                }
            )
        logger.info(f"GroqAgentLLM tools: {self.groq_tools}")

    def invoke(self, system_prompt: str, messages: list):
        logger.info("Invoking GroqAgentLLM")

        # 2. Map Multi-turn history from Internal (Anthropic style) to Groq/OpenAI style
        groq_messages = [{"role": "system", "content": system_prompt}]
        for message in messages:
            role = message["role"]
            content = message["content"]

            if role == "user":
                if isinstance(content, list):
                    # Check for tool results
                    for block in content:
                        if block["type"] == "tool_result":
                            groq_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": block["tool_use_id"],
                                    "content": str(block["content"]),
                                }
                            )
                else:
                    groq_messages.append({"role": "user", "content": content})

            elif role == "assistant":
                # Convert content blocks to Tool Calls and text content
                text_content = ""
                tool_calls = []
                for block in content:
                    if block["type"] == "text":
                        text_content += block["text"]
                    elif block["type"] == "tool_use":
                        tool_calls.append(
                            {
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"]),
                                },
                            }
                        )

                msg = {"role": "assistant", "content": text_content if text_content.strip() else ""}
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                groq_messages.append(msg)

        # 3. Call Groq
        response = self.client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=groq_messages,
            tools=self.groq_tools,
            tool_choice="auto",
            temperature=0,
        )

        message = response.choices[0].message
        res_content = []
        if message.content:
            res_content.append({"type": "text", "text": message.content})

        if message.tool_calls:
            for tc in message.tool_calls:
                res_content.append(
                    {
                        "type": "tool_use",
                        "name": tc.function.name,
                        "input": json.loads(tc.function.arguments),
                        "id": tc.id,
                    }
                )

        return {
            "stop_reason": "tool_use" if message.tool_calls else "end_turn",
            "content": res_content,
        }


class AgentRouter:
    def __init__(self, retriever: Retriever, duckdb_engine: DuckDBEngine, turns: int = 5):
        groq_key = os.environ.get("GROQ_API_KEY")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "dummy_key")
        tools = [
            {
                "name": "search_documents",
                "description": "Search unstructured text chunks from uploaded PDF policies and documentation.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query."}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "query_parquet",
                "description": "Run standard SQL 'SELECT' queries over provided Parquet structured tables.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "DuckDB-compatible SELECT statement",
                        }
                    },
                    "required": ["sql_query"],
                },
            },
        ]

        def is_valid(key):
            if not key or not key.strip():
                return False
            low_key = key.lower()
            return "your_" not in low_key and "dummy" not in low_key

        if is_valid(groq_key):
            logger.info("AgentRouter: Selecting GroqAgentLLM provider")
            self.llm = GroqAgentLLM(tools=tools)
        elif is_valid(anthropic_key) and anthropic_key != "dummy_key":
            logger.info("AgentRouter: Selecting AnthropicAgentLLM provider")
            self.llm = AnthropicAgentLLM(tools=tools)
        else:
            logger.info(
                "AgentRouter: Selecting DummyAgentLLM (No valid API keys found)"
            )
            self.llm = DummyAgentLLM(duckdb_engine=duckdb_engine, retriever=retriever, tools=tools)

        self.retriever = retriever
        self.duckdb_engine = duckdb_engine
        self.turns = turns

    def run(self, user_prompt: str, vector: list[float] | None = None) -> dict:
        """Process a natural language query with structured SQL and unstructured Vector DB tools."""
        schema_context = self.duckdb_engine.get_schema_context()
        system_prompt = HYBRID_ROUTER_SYSTEM_PROMPT.format(schema_context=schema_context)
        messages = [{"role": "user", "content": user_prompt}]
        sources = []

        # We loop to allow the agent to use tools then answer
        for turn in range(self.turns):
            # Send state to dynamic interface
            logger.debug(f"AgentRouter: turn {turn}")
            response = self.llm.invoke(
                system_prompt=system_prompt, messages=messages
            )
            logger.debug(f"AgentRouter: invoke response: {response}")

            if response["stop_reason"] == "tool_use":
                # Ensure we add the assistant's request to call the tool to message history
                messages.append({"role": "assistant", "content": response["content"]})

                # Execute mapped python function
                for content_block in response["content"]:
                    if content_block["type"] == "tool_use":
                        tool_name = content_block["name"]
                        tool_inputs = content_block["input"]
                        tool_use_id = content_block["id"]

                        logger.info(
                            f"AgentRouter: Executing tool '{tool_name}' with inputs {tool_inputs}"
                        )

                        if tool_name == "search_documents":
                            search_res = self.retriever.search(tool_inputs["query"], vector=vector)
                            tool_result_str = search_res.get(
                                "context_str", "No results found."
                            )
                            sources.extend(search_res.get("sources", []))

                        elif tool_name == "query_parquet":
                            sql = tool_inputs.get("sql_query", "")
                            tool_result_str = self.duckdb_engine.query(sql)

                        else:
                            tool_result_str = "Error: Unknown tool."

                        # Feed the concrete result back up for Claude to observe
                        messages.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": tool_use_id,
                                        "content": tool_result_str,
                                    }
                                ],
                            }
                        )
            else:
                # Agent formulated a final response
                final_text = ""
                for b in response["content"]:
                    if b["type"] == "text":
                        final_text += b["text"]
                return {"response": final_text, "sources": sources}

        # Fallback if loop hit cap
        return {
            "response": "The agent exhausted tool usage constraints before formulating an answer.",
            "sources": sources,
        }

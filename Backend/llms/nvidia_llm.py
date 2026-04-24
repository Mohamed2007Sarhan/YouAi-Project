import logging
from openai import OpenAI
from typing import List, Dict, Optional, Generator
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.mood_manager import MoodManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NvidiaLLM")


class NvidiaLLM:
    """
    NVIDIA Nemotron LLM via OpenAI-compatible API.
    Model: nvidia/llama-3.3-nemotron-super-49b-v1.5
    Includes Responder-Reviser architecture and Mood/Identity management.
    """

    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
    NVIDIA_API_KEY  = "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"
    DEFAULT_MODEL   = "nvidia/llama-3.3-nemotron-super-49b-v1.5"

    def __init__(
        self,
        api_key: str = None,
        default_model: str = None,
    ):
        self.api_key       = api_key or self.NVIDIA_API_KEY
        self.default_model = default_model or self.DEFAULT_MODEL
        self.mood_manager  = MoodManager()

        try:
            self.client = OpenAI(
                base_url=self.NVIDIA_BASE_URL,
                api_key=self.api_key,
            )
            logger.info(f"NvidiaLLM client initialized. Model: {self.default_model}")
        except Exception as e:
            logger.error(f"Failed to initialize NvidiaLLM client: {e}")
            raise

    def set_model(self, model_name: str):
        self.default_model = model_name
        logger.info(f"Model updated to: {self.default_model}")

    # ── Identity / Mood ───────────────────────────────────────────────────────

    def get_identity_prompt(self, is_talking_to_user: bool = True) -> str:
        mood_ctx = self.mood_manager.get_mood_context()
        if is_talking_to_user:
            identity = (
                "You are YouAi, a helpful AI assistant. "
                "You are talking directly to your creator/user."
            )
        else:
            identity = (
                "You are a Digital Twin of the user. "
                "You are talking to someone else on their behalf. "
                "Roleplay as the user based on available information — "
                "NEVER mention that you are an AI."
            )
        if mood_ctx:
            identity += f"\n\n{mood_ctx}"
        return identity

    # ── Core chat method ──────────────────────────────────────────────────────

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.6,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        stream: bool = False,
        is_talking_to_user: bool = True,
        use_reviser: bool = True,
        tools: Optional[List[Dict]] = None,
        tool_executor=None,
        **kwargs,          # absorb any extra kwargs (e.g. use_reviser=False from deep_setup)
    ):
        """Send a chat message to the NVIDIA LLM."""
        system_prompt = self.get_identity_prompt(is_talking_to_user)

        mod_messages = list(messages)
        if mod_messages and mod_messages[0]["role"] == "system":
            mod_messages[0]["content"] = (
                f"{system_prompt}\n\n{mod_messages[0]['content']}"
            )
        else:
            mod_messages.insert(0, {"role": "system", "content": system_prompt})

        target_model = model or self.default_model
        logger.info(f"Sending chat request | model={target_model} | reviser={use_reviser}")

        # Allow up to 5 tool-call iterations per user request to prevent infinite loops
        for _ in range(5):
            try:
                completion_kwargs = {
                    "model": target_model,
                    "messages": mod_messages,
                    "temperature": temperature,
                    "top_p": top_p,
                    "max_tokens": max_tokens,
                    "frequency_penalty": 0,
                    "presence_penalty": 0,
                    "stream": stream,
                }
                
                if tools and tool_executor:
                    completion_kwargs["tools"] = tools

                completion = self.client.chat.completions.create(**completion_kwargs)

                if stream:
                    if use_reviser:
                        logger.warning("Streaming on — Reviser skipped.")
                    return self._stream_generator(completion)

                msg = completion.choices[0].message
                
                if getattr(msg, "tool_calls", None) and tools and tool_executor:
                    logger.info(f"LLM requested {len(msg.tool_calls)} tool calls.")
                    
                    assistant_msg = {"role": "assistant", "content": msg.content or "", "tool_calls": []}
                    for tc in msg.tool_calls:
                        assistant_msg["tool_calls"].append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        })
                    mod_messages.append(assistant_msg)
                    
                    for tc in msg.tool_calls:
                        tool_name = tc.function.name
                        tool_args = tc.function.arguments
                        result = tool_executor.execute(tool_name, tool_args)
                        
                        mod_messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tool_name,
                            "content": result
                        })
                    
                    # Loop continues, sending tool results back to LLM
                    continue

                else:
                    response_content = msg.content or ""
                    # Strip NVIDIA <think>…</think> reasoning blocks if present
                    if "<think>" in response_content and "</think>" in response_content:
                        response_content = response_content.split("</think>", 1)[-1].strip()

                    logger.info("Chat request completed successfully.")

                    # Reviser step — skip if JSON (tool output)
                    if use_reviser and "{" not in response_content:
                        response_content = self._revise_response(response_content, target_model)

                    return response_content

            except Exception as e:
                logger.error(f"Error during chat request: {e}")
                raise
        
        logger.warning("Max tool calls reached. Returning last response.")
        return response_content or "Tool execution limit reached."

    # ── Reviser ───────────────────────────────────────────────────────────────

    def _revise_response(self, draft: str, model: str) -> str:
        mood_ctx = self.mood_manager.get_mood_context()
        reviser_prompt = (
            "You are a strict text reviser. Fix ANY grammatical, linguistic, or logical errors.\n\n"
            "CRITICAL RULES:\n"
            "1. OUTPUT ONLY THE REVISED TEXT.\n"
            "2. DO NOT include headers like 'Revised Text:' or 'Changes Made:'.\n"
            "3. DO NOT add explanations or introductory remarks.\n"
            "4. If no changes are needed, output the original text exactly.\n\n"
        )
        if mood_ctx:
            reviser_prompt += f"Tone/Mood Requirement: {mood_ctx}\n\n"
        reviser_prompt += f"DRAFT TO REVISE:\n{draft}\n\nREVISED TEXT:"

        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": reviser_prompt}],
                temperature=0.2,
                max_tokens=4096,
                stream=False,
            )
            revised = completion.choices[0].message.content
            if "<think>" in revised and "</think>" in revised:
                revised = revised.split("</think>", 1)[-1].strip()
            logger.info("Reviser completed successfully.")
            return revised
        except Exception as e:
            logger.warning(f"Reviser failed, using original draft. Error: {e}")
            return draft

    # ── Stream helper ─────────────────────────────────────────────────────────

    def _stream_generator(self, completion) -> Generator[str, None, None]:
        try:
            for chunk in completion:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if not delta:
                    continue
                content = getattr(delta, "content", None)
                if content:
                    yield content
            logger.info("Stream completed successfully.")
        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            raise


if __name__ == "__main__":
    llm = NvidiaLLM()
    messages = [{"role": "user", "content": "من أنت؟ أجب في جملة واحدة."}]
    response = llm.chat(messages, is_talking_to_user=True, use_reviser=False)
    print(response)

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMRouter:
    """
    统一 OpenAI 兼容模型路由层：
    - 兼容 DeepSeek / 通义千问 / 豆包 / OpenAI / Gemini OpenAI-compatible 接口
    - 强制 JSON 输出 + Pydantic v2 强类型校验 + 自动纠错重试
    - 独立支持多模态视觉模型做手写答卷 OCR
    """

    def __init__(self) -> None:
        self.text_client = AsyncOpenAI(
            api_key=settings.llm_api_key or "missing-key",
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self.vlm_client = AsyncOpenAI(
            api_key=settings.effective_vlm_api_key or "missing-key",
            base_url=settings.effective_vlm_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    @staticmethod
    def _extract_json(raw: str) -> str:
        """容错提取模型返回的 JSON（去除可能的 ```json ... ``` 包裹）"""
        text = raw.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        # 兜底找最外层花括号
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    async def call_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        max_retries: int = 2,
    ) -> T:
        """调用文本大模型并严格校验返回为指定 Pydantic 模型"""
        schema_json = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        full_system = (
            f"{system_prompt}\n\n"
            "【输出格式铁律】\n"
            "你必须且只能输出一个合法的 JSON 对象，不要包含任何额外解释或前后缀文本。\n"
            f"JSON 必须严格遵循以下 JSON Schema：\n{schema_json}"
        )

        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": user_prompt},
        ]

        last_err: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                resp = await self.text_client.chat.completions.create(
                    model=settings.llm_model,
                    messages=messages,
                    temperature=settings.llm_temperature,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content or "{}"
                cleaned = self._extract_json(content)
                return response_model.model_validate_json(cleaned)
            except (ValidationError, json.JSONDecodeError) as e:
                last_err = e
                # 把校验错误反馈给模型做一次自修复重试
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"你刚才输出的 JSON 未通过 Schema 校验，错误信息如下：\n{e}\n"
                            "请严格修复并重新只输出合法的 JSON 对象。"
                        ),
                    }
                )
        raise RuntimeError(f"LLM 结构化输出连续 {max_retries + 1} 次校验失败: {last_err}")

    async def ocr_handwriting(self, image_path: str | Path) -> str:
        """
        Step 0: 使用多模态视觉大模型识别手写答卷照片（支持申论方格纸和英文手写稿）
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"手写图片不存在: {path}")

        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or "image/jpeg"
        b64_data = base64.b64encode(path.read_bytes()).decode("utf-8")

        resp = await self.vlm_client.chat.completions.create(
            model=settings.vlm_model,
            temperature=0.05,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位高精度的考试手写答卷文字识别专家。"
                        "请忠实还原图片中的手写正文内容：\n"
                        "1. 保留考生原本的分段和标点，忽略被明显划掉/涂改的废字；\n"
                        "2. 不要帮考生修改语法错误或错别字（原样还原以便后续批改）；\n"
                        "3. 只输出识别出的答卷正文，不要输出任何额外解释。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别这张手写答卷中的全部正文内容："},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
                        },
                    ],
                },
            ],
        )
        return (resp.choices[0].message.content or "").strip()

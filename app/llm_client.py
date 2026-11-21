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
        validation_context: dict | None = None,
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
                return response_model.model_validate_json(cleaned, context=validation_context)
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

    async def ocr_handwriting(self, image_path: str | Path, exam_type: str = "shenlun_short") -> str:
        """
        Step 0: 使用多模态视觉大模型识别答卷照片（支持申论方格纸、英文手写稿及印刷练习卷）
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"手写图片不存在: {path}")

        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or "image/jpeg"
        b64_data = base64.b64encode(path.read_bytes()).decode("utf-8")

        if exam_type == "kaoyan_english":
            extra_rule = "若为英文作答，必须原样保留考生拼写（严禁自动纠正拼写或语法错误），行尾连字符断词请自动拼接为完整单词。"
        else:
            extra_rule = "若为申论方格稿纸，请忽略格子线及格纸边缘印刷的字数角标（如“100字”“300字”页码标记）。"

        prompt_text = (
            "请直接把图片主画面中的全部正文文字完整转录出来（无需长篇推理分析）：\n"
            "1. 无论是手写体还是印刷体均需从头到尾完整转录，不得漏段或提前截断；\n"
            "2. 若图片边缘露出装订线外相邻另一页被裁切一半的残缺字，请忽略残缺边缘页，只转录画面主体页；\n"
            "3. 同一自然段内因方格纸或行宽折行的文字请自动拼成连续完整句子，仅在真正分段或序号（如 1./（1）/一、）处换行；\n"
            f"4. 忽略明显涂改划掉的废字，不要帮考生改错别字。{extra_rule}\n"
            "5. 只输出识别出的正文纯文本，不要输出任何额外解释。"
        )

        for attempt in range(2):
            cur_prompt = prompt_text if attempt == 0 else "请直接完整输出这张图片中的所有正文文字，不要遗漏："
            resp = await self.vlm_client.chat.completions.create(
                model=settings.vlm_model,
                temperature=0.0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": cur_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
                            },
                        ],
                    },
                ],
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
        return ""

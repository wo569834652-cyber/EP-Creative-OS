import httpx

from app.config import get_settings


class DeepSeekClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1200,
    ) -> tuple[bool, str]:
        if not self.settings.deepseek_api_key:
            return (
                False,
                "DeepSeek API key 未配置。请在 .env 中设置 DEEPSEEK_API_KEY；本地 CRUD、Hook、Suno Prompt 和 Cubase 导出仍可继续使用。",
            )

        base_url = self.settings.deepseek_base_url.rstrip("/")
        payload = {
            "model": self.settings.deepseek_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=40) as client:
                response = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return False, f"DeepSeek 请求失败：HTTP {exc.response.status_code} - {exc.response.text[:300]}"
        except httpx.RequestError as exc:
            return False, f"DeepSeek 网络请求失败：{exc}"
        except ValueError:
            return False, "DeepSeek 返回了无法解析的 JSON。"

        try:
            return True, data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return False, "DeepSeek 返回格式不符合 OpenAI-compatible chat completions。"

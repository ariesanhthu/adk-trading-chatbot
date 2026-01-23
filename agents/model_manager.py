"""
Model Manager - Quản lý các LLM models với auto-fallback.

Hỗ trợ Groq và OpenRouter với khả năng fallback khi gặp lỗi.
"""

import os
from typing import Optional

from google.adk.models.lite_llm import LiteLlm

from agents.config import AgentConfig


class GroqModelManager:
    """
    Quản lý các model Groq với auto-fallback khi gặp token limit.

    Models theo thứ tự ưu tiên:
    1. groq/compound (mặc định, cân bằng)
    2. groq/llama-3.3-70b-versatile (tốt nhất, lớn nhất)
    3. groq/llama-3.1-8b-instant (nhanh nhất, nhỏ nhất)
    """

    GROQ_MODELS = [
        "groq/llama-3.1-8b-instant",  # Ưu tiên 1: Model mặc định, cân bằng
        "groq/llama3-8b-8192",  # Ưu tiên 3: Model nhanh nhất
        "groq/compound",
        "groq/llama-3.1-70b-versatile",  # Ưu tiên 2: Model lớn nhất, tốt nhất
        "groq/llama3-70b-8192",  # Ưu tiên 4: Model lớn nhất
    ]

    def __init__(self, api_key: Optional[str] = None, timeout: float = 120.0):
        """
        Khởi tạo GroqModelManager.

        Args:
            api_key: Groq API key (nếu None, sẽ lấy từ env GROQ_API_KEY)
            timeout: Timeout cho requests (default: 120s)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not found. Please set GROQ_API_KEY in environment "
                "variables or .env file"
            )

        self.timeout = timeout
        self.current_model_index = 0
        self.current_model: Optional[LiteLlm] = None
        self._create_current_model()

    def _create_current_model(self) -> LiteLlm:
        """
        Tạo LiteLlm model với model hiện tại.

        Returns:
            LiteLlm model instance
        """
        model_name = self.GROQ_MODELS[self.current_model_index]
        self.current_model = LiteLlm(
            model=model_name,
            api_key=self.api_key,
            timeout=self.timeout,
        )
        print(f"✅ Created Groq model: {model_name}")
        return self.current_model

    def get_model(self) -> LiteLlm:
        """
        Lấy model hiện tại.

        Returns:
            LiteLlm model instance
        """
        return self.current_model

    def switch_to_next_model(self) -> Optional[LiteLlm]:
        """
        Chuyển sang model tiếp theo trong danh sách.

        Returns:
            LiteLlm model mới hoặc None nếu đã hết models
        """
        if self.current_model_index < len(self.GROQ_MODELS) - 1:
            self.current_model_index += 1
            print(
                f"⚠️  Switching to next Groq model: "
                f"{self.GROQ_MODELS[self.current_model_index]}"
            )
            return self._create_current_model()
        else:
            print("❌ No more Groq models available for fallback")
            return None

    def get_current_model_name(self) -> str:
        """
        Lấy tên model hiện tại.

        Returns:
            Tên model
        """
        return self.GROQ_MODELS[self.current_model_index]

    def has_more_models(self) -> bool:
        """
        Kiểm tra còn model nào để fallback không.

        Returns:
            True nếu còn model, False nếu đã hết
        """
        return self.current_model_index < len(self.GROQ_MODELS) - 1


class OpenRouterModelManager:
    """Quản lý OpenRouter model."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = 180.0,
    ):
        """
        Khởi tạo OpenRouterModelManager.

        Args:
            api_key: OpenRouter API key (nếu None, sẽ lấy từ env)
            model_name: Tên model (nếu None, sẽ lấy từ env hoặc default)
            timeout: Timeout cho requests (default: 180s cho free tier)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            print("⚠️  WARNING: OPENROUTER_API_KEY not found in environment variables!")
            print("   Please set OPENROUTER_API_KEY in .env file")
        else:
            print(f"✅ OPENROUTER_API_KEY found: {self.api_key[:10]}...")

        # Set biến môi trường cho litellm
        os.environ["OPENROUTER_API_KEY"] = self.api_key or ""

        self.model_name = model_name or os.getenv(
            "OPENROUTER_MODEL", "openrouter/openai/gpt-oss-120b:free"
        )
        self.timeout = timeout
        self.model: Optional[LiteLlm] = None
        self._create_model()

    def _create_model(self) -> LiteLlm:
        """
        Tạo LiteLlm model với OpenRouter.

        LiteLlm tự động detect API base từ model name prefix (openrouter/...).

        Returns:
            LiteLlm model instance
        """
        self.model = LiteLlm(
            model=self.model_name,
            api_key=self.api_key,
            timeout=self.timeout,
            extra_headers={
                "HTTP-Referer": "https://github.com/ai-core-trading",
                "X-Title": "VNStock Agent",
            },
        )
        print(f"✅ Created OpenRouter model: {self.model_name}")
        return self.model

    def get_model(self) -> LiteLlm:
        """
        Lấy model.

        Returns:
            LiteLlm model instance
        """
        return self.model

    def get_model_name(self) -> str:
        """
        Lấy tên model.

        Returns:
            Tên model
        """
        return self.model_name


class ModelManager:
    """Quản lý model chính với khả năng chọn giữa Groq và OpenRouter."""

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Khởi tạo ModelManager.

        Args:
            config: AgentConfig instance (nếu None, sẽ tạo mới)
        """
        self.config = config or AgentConfig()
        self.model: Optional[LiteLlm] = None
        self.model_name: str = ""
        self.groq_manager: Optional[GroqModelManager] = None
        self.openrouter_manager: Optional[OpenRouterModelManager] = None
        self._initialize_model()

    def _initialize_model(self):
        """Khởi tạo model (Groq hoặc OpenRouter)."""
        # Kiểm tra xem dùng Groq hay OpenRouter
        use_groq = self.config.get_env_var("USE_GROQ", "true").lower() == "true"
        groq_api_key = self.config.get_env_var("GROQ_API_KEY")

        if use_groq and groq_api_key:
            print("🔧 Using Groq models with auto-fallback")
            try:
                self.groq_manager = GroqModelManager(
                    api_key=groq_api_key, timeout=120.0
                )
                self.model = self.groq_manager.get_model()
                self.model_name = self.groq_manager.get_current_model_name()
                print(f"✅ Groq model initialized: {self.model_name}")
            except Exception as e:
                print(f"⚠️  Failed to initialize Groq models: {e}")
                print("   Falling back to OpenRouter...")
                self._initialize_openrouter()
        else:
            self._initialize_openrouter()

    def _initialize_openrouter(self):
        """Khởi tạo OpenRouter model."""
        print("🔧 Using OpenRouter models")
        self.openrouter_manager = OpenRouterModelManager()
        self.model = self.openrouter_manager.get_model()
        self.model_name = self.openrouter_manager.get_model_name()
        print(f"✅ OpenRouter model initialized: {self.model_name}")

    def get_model(self) -> LiteLlm:
        """
        Lấy model hiện tại.

        Returns:
            LiteLlm model instance
        """
        return self.model

    def get_model_name(self) -> str:
        """
        Lấy tên model hiện tại.

        Returns:
            Tên model
        """
        return self.model_name

    def switch_to_next_groq_model(self) -> Optional[LiteLlm]:
        """
        Chuyển sang Groq model tiếp theo (chỉ hoạt động nếu đang dùng Groq).

        Returns:
            LiteLlm model mới hoặc None
        """
        if self.groq_manager:
            new_model = self.groq_manager.switch_to_next_model()
            if new_model:
                self.model = new_model
                self.model_name = self.groq_manager.get_current_model_name()
            return new_model
        return None

"""
Unified configuration loader.

Priority: CLI arguments > Environment variables (.env) > config.yaml

Sensitive information (API keys) must be configured in .env, not in yaml.
config.yaml is REQUIRED - no default values are used for global keys.
"""
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TypeVar

import yaml
from dotenv import load_dotenv

# ===== Project paths =====
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ===== Required global keys in config.yaml =====
_GLOBAL_REQUIRED_KEYS = [
    "skill_group",
    "max_skills",
    "prune_enabled",
    "port",
    "manager",
    "orchestrator",
]

# Cache TTL lower bound (1 year)
MIN_CACHE_TTL_SECONDS = 31_536_000

# ===== Frozen dataclass schemas for plugin config =====

T = TypeVar("T")


@dataclass(frozen=True)
class RetryConfig:
    base_delay: float = 1.0
    max_retries: int = 3


@dataclass(frozen=True)
class TreeBuildConfig:
    max_workers: int = 4
    caching: bool = True
    num_retries: int = 3
    timeout: float = 600.0
    deterministic_prompts: bool = True
    discovery_seed: int = 42
    prompt_fingerprint_version: str = "v1"
    cache_observability: bool = True


@dataclass(frozen=True)
class TreeSearchConfig:
    max_parallel: int = 5
    temperature: float = 0.3
    timeout: float = 600.0
    caching: bool = True


# Layering config classes (defined before TreeManagerConfig to avoid forward references)
@dataclass(frozen=True)
class DormantSearchConfig:
    """Configuration for dormant skill search."""
    keyword_enabled: bool = True      # Enable keyword search
    cache_ttl: int = MIN_CACHE_TTL_SECONDS

    def __post_init__(self):
        """Clamp TTL to at least one year."""
        try:
            ttl = int(self.cache_ttl)
        except (TypeError, ValueError):
            ttl = MIN_CACHE_TTL_SECONDS
        if ttl < MIN_CACHE_TTL_SECONDS:
            ttl = MIN_CACHE_TTL_SECONDS
        object.__setattr__(self, "cache_ttl", ttl)


_VALID_LAYERING_MODES = {"disabled", "directory", "install-count"}


@dataclass(frozen=True)
class LayeringConfig:
    """Configuration for active/dormant skill layering strategy.

    mode controls how layering works:
    - "disabled": no layering (default)
    - "directory": dormant skills live in a separate directory
    - "install-count": dormant/active split based on install counts
    """
    mode: str = "disabled"            # "disabled" | "directory" | "install-count"
    dormant_skills_dir: str = ""      # path relative to project root, for mode=directory
    active_threshold: int = 50        # Top N skills to keep active (for mode=install-count)
    max_dormant_suggestions: int = 10 # Max dormant skills to suggest
    dormant_search: DormantSearchConfig = field(default_factory=DormantSearchConfig)
    installs_data_path: str = "tools/skills_downloader_from_skillssh/skills_scraped.json"

    def __post_init__(self):
        if self.mode not in _VALID_LAYERING_MODES:
            raise ValueError(
                f"Invalid layering mode: {self.mode!r}. "
                f"Must be one of {sorted(_VALID_LAYERING_MODES)}"
            )
        if self.mode == "directory" and not self.dormant_skills_dir:
            raise ValueError(
                "dormant_skills_dir is required when layering mode is 'directory'. "
                "Set managers.tree.layering.dormant_skills_dir in config.yaml."
            )

    @property
    def is_enabled(self) -> bool:
        return self.mode != "disabled"

    @property
    def is_directory_mode(self) -> bool:
        return self.mode == "directory"

    @property
    def is_install_count_mode(self) -> bool:
        return self.mode == "install-count"


@dataclass(frozen=True)
class TreeManagerConfig:
    branching_factor: int = 8
    max_depth: int = 6
    build: TreeBuildConfig = field(default_factory=TreeBuildConfig)
    search: TreeSearchConfig = field(default_factory=TreeSearchConfig)
    layering: LayeringConfig = field(default_factory=LayeringConfig)


def _default_runtime_model() -> str:
    """Get default runtime model from env or fallback to 'sonnet'."""
    return os.environ.get("ANTHROPIC_MODEL", "sonnet")


@dataclass(frozen=True)
class RuntimeConfig:
    """Shared runtime config for all orchestrators (maps to SkillClient params)."""
    model: str = field(default_factory=_default_runtime_model)
    execution_timeout: float = 0.0       # 0 = no timeout
    summary_max_length: int = 500


@dataclass(frozen=True)
class DagOrchestratorConfig:
    node_timeout: float = 3600.0
    max_concurrent: int = 6
    batch_auto_plan: int = 0  # Plan index for batch/headless mode (0=quality, 1=speed, 2=simplicity)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    def __post_init__(self):
        if not (0 <= self.batch_auto_plan <= 2):
            raise ValueError(
                f"batch_auto_plan must be 0-2, got {self.batch_auto_plan}. "
                f"(0=quality, 1=speed, 2=simplicity)"
            )


@dataclass(frozen=True)
class FreestyleOrchestratorConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


@dataclass(frozen=True)
class DirectOrchestratorConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)


@dataclass(frozen=True)
class VectorBuildConfig:
    batch_size: int = 100
    max_workers: int = 4
    caching: bool = True


@dataclass(frozen=True)
class VectorManagerConfig:
    top_k: int = 10
    collection_name: str = "skills"
    build: VectorBuildConfig = field(default_factory=VectorBuildConfig)


# Registry mapping plugin names to their config dataclass
@dataclass(frozen=True)
class DirectManagerConfig:
    """No configuration needed — directly provides all skills to agent."""
    pass


_MANAGER_SCHEMAS: dict[str, type] = {
    "tree": TreeManagerConfig,
    "vector": VectorManagerConfig,
    "direct": DirectManagerConfig,
}

_ORCHESTRATOR_SCHEMAS: dict[str, type] = {
    "dag": DagOrchestratorConfig,
    "free-style": FreestyleOrchestratorConfig,
    "no-skill": DirectOrchestratorConfig,
}


def _build_nested_dataclass(cls: type[T], raw: dict | None) -> T:
    """Recursively construct a frozen dataclass from a raw dict.

    Missing keys fall back to dataclass field defaults.
    Extra keys are silently ignored.
    """
    if raw is None:
        raw = {}

    kwargs = {}
    for f in fields(cls):
        if f.name not in raw:
            continue
        value = raw[f.name]
        # Check if the field type is itself a dataclass
        if hasattr(f.type, "__dataclass_fields__"):
            value = _build_nested_dataclass(f.type, value if isinstance(value, dict) else {})
        kwargs[f.name] = value

    return cls(**kwargs)


class Config:
    """
    Unified configuration loader. Priority: CLI > ENV > YAML

    Usage:
        cfg = get_config()
        cfg.skill_group          # global (from yaml)
        cfg.llm_model            # from .env
        cfg.manager_config()     # TreeManagerConfig (or other based on active manager)
        cfg.orchestrator_config()  # DagOrchestratorConfig (or other)
        cfg.core_retry()         # RetryConfig
    """

    _yaml_cache = None
    _instance = None
    _config_path = None

    def __init__(self, cli_args: dict = None, config_path: str = None):
        self._cli = cli_args or {}
        if config_path:
            Config._config_path = Path(config_path)
        if Config._yaml_cache is None:
            Config._yaml_cache = self._load_yaml()

    @classmethod
    def get_instance(cls, cli_args: dict = None, config_path: str = None) -> "Config":
        """Get singleton instance, optionally updating CLI args."""
        if cls._instance is None:
            cls._instance = cls(cli_args, config_path=config_path)
        elif cli_args:
            cls._instance._cli.update(cli_args)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None
        cls._yaml_cache = None
        cls._config_path = None

    def _load_yaml(self) -> dict:
        """Load config.yaml with validation."""
        path = Config._config_path or (PROJECT_ROOT / "config" / "config.yaml")
        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}\n"
                "Please copy config/config.yaml.example to config/config.yaml and modify as needed."
            )

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        missing = [k for k in _GLOBAL_REQUIRED_KEYS if k not in data]
        if missing:
            raise ValueError(f"config.yaml missing required keys: {missing}")

        return data

    def _get(self, key: str, env_key: str = None):
        """Get a top-level config value with priority: CLI > ENV > yaml."""
        if key in self._cli and self._cli[key] is not None:
            return self._cli[key]
        if env_key and os.getenv(env_key):
            return os.getenv(env_key)
        if Config._yaml_cache and key in Config._yaml_cache:
            return Config._yaml_cache[key]
        raise KeyError(f"config.yaml missing required key: {key}")

    # ===== Nested config accessors =====

    def core_retry(self) -> RetryConfig:
        """Get shared retry configuration from core.retry block."""
        core = Config._yaml_cache.get("core", {}) if Config._yaml_cache else {}
        raw = core.get("retry", {})
        return _build_nested_dataclass(RetryConfig, raw)

    def manager_config(self, name: str = None) -> object:
        """Get manager plugin config as a frozen dataclass.

        Args:
            name: Manager name. Defaults to the active manager from config.
        """
        name = name or self.manager
        schema = _MANAGER_SCHEMAS.get(name)
        if schema is None:
            return None
        managers = Config._yaml_cache.get("managers", {}) if Config._yaml_cache else {}
        raw = managers.get(name, {})
        return _build_nested_dataclass(schema, raw)

    def orchestrator_config(self, name: str = None) -> object:
        """Get orchestrator plugin config as a frozen dataclass.

        Args:
            name: Orchestrator name. Defaults to the active orchestrator from config.
        """
        name = name or self._get("orchestrator")
        schema = _ORCHESTRATOR_SCHEMAS.get(name)
        if schema is None:
            return None
        orchestrators = Config._yaml_cache.get("orchestrators", {}) if Config._yaml_cache else {}
        raw = orchestrators.get(name, {})
        return _build_nested_dataclass(schema, raw)

    def layering_config(self) -> LayeringConfig:
        """Get layering configuration from managers.tree.layering."""
        managers = Config._yaml_cache.get("managers", {}) if Config._yaml_cache else {}
        tree_config = managers.get("tree", {})
        raw = tree_config.get("layering", {})

        # Detect legacy config: 'enabled' was replaced by 'mode' in the tri-state refactor
        if "enabled" in raw:
            raise ValueError(
                "The 'layering.enabled' field has been removed. "
                "Use 'layering.mode' instead:\n"
                "  mode: 'install-count'  (replaces enabled: true)\n"
                "  mode: 'directory'      (new directory-based layering)\n"
                "  mode: 'disabled'       (replaces enabled: false)\n"
                "Please update managers.tree.layering in config.yaml."
            )

        return _build_nested_dataclass(LayeringConfig, raw)

    # ===== Global properties =====

    @property
    def skill_group(self) -> str:
        return self._get("skill_group")

    @property
    def max_skills(self) -> int:
        return int(self._get("max_skills"))

    @property
    def prune_enabled(self) -> bool:
        val = self._get("prune_enabled", "PRUNE_ENABLED")
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"

    @property
    def port(self) -> int:
        return int(self._get("port"))

    @property
    def manager(self) -> str:
        return str(self._get("manager"))

    # ===== LLM Configuration (from .env only) =====

    @property
    def llm_model(self) -> str:
        return os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

    @property
    def llm_base_url(self) -> str:
        return os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")

    @property
    def llm_api_key(self) -> str:
        return os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")

    @property
    def llm_max_retries(self) -> int:
        return int(os.getenv("LLM_MAX_RETRIES", "3"))

    # ===== Embedding Configuration (from .env only) =====

    @property
    def embedding_model(self) -> str:
        return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    @property
    def embedding_base_url(self) -> str:
        return os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")

    @property
    def embedding_api_key(self) -> str:
        return os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")

    @property
    def embedding_batch_size(self) -> int:
        return int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))

    @property
    def chroma_persist_dir(self) -> str:
        return os.getenv("CHROMA_PERSIST_DIR", "data/vector_stores")


# ===== Global config instance =====
def get_config(cli_args: dict = None, config_path: str = None) -> Config:
    """Get global config instance."""
    return Config.get_instance(cli_args, config_path=config_path)


# ===== Backward compatibility: module-level variables =====
# These are kept for backward compatibility with existing code
# Path variables are always available
DATA_DIR = PROJECT_ROOT / "data"
SKILLS_DIR = DATA_DIR / "skill_seeds"

# LLM Configuration (from .env, with sensible defaults for optional items)
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))

# Embedding Configuration (from .env, with sensible defaults for optional items)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))


# ===== Lazy-loaded config values =====
# These require config.yaml to exist and will raise errors if not configured
# Uses __getattr__ for backward-compatible module-level access

_LAZY_CONFIG_KEYS = {
    # Tree Building
    "BRANCHING_FACTOR": "branching_factor",
    "TREE_BUILD_MAX_WORKERS": "tree_build_max_workers",
    "TREE_BUILD_CACHING": "tree_build_caching",
    "TREE_BUILD_NUM_RETRIES": "tree_build_num_retries",
    "TREE_BUILD_TIMEOUT": "tree_build_timeout",
    "MAX_DEPTH": "max_depth",
    # Search
    "SEARCH_MAX_PARALLEL": "search_max_parallel",
    "SEARCH_TEMPERATURE": "search_temperature",
    "SEARCH_TIMEOUT": "search_timeout",
    "SEARCH_CACHING": "search_caching",
    # Orchestrator
    "NODE_TIMEOUT": "node_timeout",
    "MAX_CONCURRENT": "max_concurrent",
    # Retry
    "RETRY_BASE_DELAY": "retry_base_delay",
    "MAX_RETRIES": "max_retries",
    # Others
    "PRUNE_ENABLED": "prune_enabled",
}


_BOOL_KEYS = {"PRUNE_ENABLED", "TREE_BUILD_CACHING", "SEARCH_CACHING"}
_FLOAT_KEYS = {"TREE_BUILD_TIMEOUT", "SEARCH_TEMPERATURE", "SEARCH_TIMEOUT", "NODE_TIMEOUT", "RETRY_BASE_DELAY"}


def __getattr__(name: str):
    """Lazy load config values from config.yaml on first access."""
    if name in _LAZY_CONFIG_KEYS:
        yaml_key = _LAZY_CONFIG_KEYS[name]
        value = get_config().get(yaml_key)
        if name in _BOOL_KEYS:
            if isinstance(value, bool):
                return value
            return str(value).lower() == "true"
        if name in _FLOAT_KEYS:
            return float(value)
        return int(value)
    raise AttributeError(f"module 'config' has no attribute '{name}'")

# ===== Skill Groups Configuration =====
# Alias mapping for backward compatibility (e.g., "default" -> "skill_seeds")
SKILL_GROUP_ALIASES = {"default": "skill_seeds"}

SKILL_GROUPS = [
    {
        "id": "skill_seeds",
        "name": "Curated (RECOMMENDED)",
        "description": "Carefully curated skill set (~50 skills)",
        "skills_dir": str(DATA_DIR / "skill_seeds"),
        "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree.yaml"),
        "is_default": True,
    },
    {
        "id": "top500",
        "name": "Top 500",
        "description": "Top 500 skills collection from skills.sh",
        "skills_dir": str(DATA_DIR / "skill_top500"),
        "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_top500.yaml"),
    },
    {
        "id": "top1000",
        "name": "Top 1000",
        "description": "Top 1000 skills collection from skills.sh",
        "skills_dir": str(DATA_DIR / "skill_top1000"),
        "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_top1000.yaml"),
    },
    {
        "id": "project_toolifier",
        "name": "Project Toolifier (local)",
        "description": "Turn local repos/apps into callable tools (wrappers + manifests).",
        "skills_dir": str(DATA_DIR / "project_toolifier"),
        "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_project_toolifier.yaml"),
    },
    {
        "id": "llm_routing",
        "name": "LLM Routing & Proxies",
        "description": "OpenAI-compatible routing, provider quirks, tool-output hardening.",
        "skills_dir": str(DATA_DIR / "llm_routing"),
        "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_llm_routing.yaml"),
    },
    {
        "id": "local_devops",
        "name": "Local DevOps (WSL/Docker)",
        "description": "Ports, processes, docker networking, reproducible debug bundles.",
        "skills_dir": str(DATA_DIR / "local_devops"),
        "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_local_devops.yaml"),
    },
    {
        "id": "docs_media",
        "name": "Docs & Media Output",
        "description": "Docx reports, screenshot annotation, README digests.",
        "skills_dir": str(DATA_DIR / "docs_media"),
        "tree_path": str(Path(__file__).parent / "skill_retriever/capability_tree/tree_docs_media.yaml"),
    },
]

# ===== Demo Tasks Configuration =====
# DEMO_TASKS = [
#     {
#         "id": "frontend_debug",
#         "title": "前端Debug报告",
#         "description": "修复登录页面Bug并生成报告",
#         "prompt": "我是一名前端开发人员，用户反馈我编写的登录页面在手机访问时出现了Bug。我登录页面的代码位于 login.html。请帮我识别并修复这个Bug，并撰写一份Bug修复报告。报告中需要包含Bug修复前的网页问题截图和Bug修复后的正常网页截图。在截图中，需要使用清晰且醒目的标记突出Bug的位置。该报告应保存为 bug_report.md。",
#         "files": ["artifacts/login.html"],
#         "icon": "bug",
#     },
#     {
#         "id": "ui_research",
#         "title": "融合UI创作",
#         "description": "知识管理产品视觉设计调研",
#         "prompt": "我是产品设计师，我们公司计划打造一个知识管理软件产品。因此，我需要你调研多个相关产品，比如 Notion 和 Confluence，并撰写一份关于它们的视觉设计风格调研报告。该视觉风格调研报告需保存为 report.docx，并且必须包含这些软件的界面截图、配色分析、排版风格等内容。",
#         "files": [],
#         "icon": "design",
#     },
#     {
#         "id": "paper_promotion",
#         "title": "论文推广助手",
#         "description": "研究论文多平台推广方案",
#         "prompt": "作为一名博士生，我最近完成了一篇研究论文，希望能够在国内外社交媒体平台上有效地推广它。此外，我需要帮助创建在线材料，作为清晰展示和向更广泛受众传播我的研究成果的中心枢纽。我的论文位于本地：Avengers.pdf。",
#         "files": ["artifacts/Avengers.pdf"],
#         "icon": "paper",
#     },
#     {
#         "id": "cat_meme_video",
#         "title": "猫Meme视频生成",
#         "description": "生成老板质问员工的猫猫梗视频",
#         "prompt": '''我是一位短视频创作者，我需要你生成一个猫猫梗视频。视频主题是老板在质问员工工作进度，员工做出了巧妙的回应。其中质问猫是老板，委屈猫是员工。\n\n视频素材：质问猫和委屈猫视频素材是 video.mp4,视频背景图片是bg.jpg。\n\n视频质量要求：完全去除质问猫和委屈猫视频素材的绿幕背景，将背景换为bg.jpg。保持背景图片比例不变形。猫需要占据画面主体，尽量保持猫素材的完整。\n\n格式要求：生成视频的时间与素材视频保持一致。文字应该全都是中文，因此注意乱码问题。\n\n文字要求：质问猫和委屈猫旁边需要有"老板""员工"的身份标识。对话字幕的出现时机和持续时间必须准确，一只猫的连续喵喵声应该被认为是一句话。两只猫的对话要幽默，员工回复老板的文案要机智，具有能够在互联网上的广泛传播的潜力。根据两只猫每句话的持续时间确定对应的文案长度。''',
#         "files": ["artifacts/video.mp4", "artifacts/bg.jpg"],
#         "icon": "video",
#     },
# ]


DEMO_TASKS = [
    {
        "id": "frontend_debug",
        "title": "Frontend Debug Report",
        "description": "Fix login page bug and generate report",
        "prompt": "I am a front-end developer. Users have reported that a bug occurs when accessing the login page I wrote on a mobile phone. The code for my login page is login.html. Please help me identify and fix the bug, and write a bug fix report. The report should include a screenshot of the problematic web page before the bug fix and a screenshot of the normal web page after the bug fix. In the screenshots, the location of the bug should be highlighted with clear and eye-catching markers. The report should be saved as bug_report.md.",
        "files": ["artifacts/login.html"],
        "icon": "bug",
    },
    {
        "id": "ui_research",
        "title": "Fusion UI Design",
        "description": "Visual design research for knowledge management product",
        "prompt": "I am a product designer, and our company is planning to build a knowledge management software product. Therefore, I need you to research multiple related products, such as Notion and Confluence, and produce a visual design style research report about them. The visual style research report should be saved as report.docx and must include screenshots of these software products. Then, based on the analysis, synthesize the design characteristics of these products and generate three design concept images for a knowledge management software to provide design inspiration. The design concept images should be saved as fusion_design_1.png, fusion_design_2.png, and fusion_design_3.png, respectively.",
        "files": [],
        "icon": "design",
    },
    {
        "id": "paper_promotion",
        "title": "Paper Promotion Assistant",
        "description": "Multi-platform promotion plan for research paper",
        "prompt": "As a PhD student, I have recently completed a research paper and would like to effectively promote it on both domestic and international social media platforms. In addition, I need help creating online materials that can serve as a central hub for clearly presenting and disseminating my research findings to a broader audience. My paper is located locally at Avengers.pdf.",
        "files": ["artifacts/Avengers.pdf"],
        "icon": "paper",
    },
    {
        "id": "cat_meme_video",
        "title": "Cat Meme Video Generation",
        "description": "Generate cat meme video of boss questioning employee",
        "prompt": "I am a short-video content creator, and I need you to generate a funny cat meme video. The theme of the video is a boss questioning an employee about work progress, and the employee gives a clever response. The questioning cat represents the boss, and the aggrieved cat represents the employee.\nVideo materials: The video materials for the questioning cat and the aggrieved cat are in video.mp4. The background image for the video is background.jpg.\nVideo quality requirements: Completely remove the green screen background from both the questioning cat and the aggrieved cat video materials, and replace it with background.jpg. Keep the background image’s aspect ratio without distortion. The cats should occupy the main focus of the frame, and the integrity of the cat footage should be preserved as much as possible.\nFormat requirements: The generated video must have the same duration as the original video material. All text must be in Chinese, so please pay attention to potential text encoding issues.\nText requirements: Identity labels reading “Boss” and “Employee” should appear next to the questioning cat and the aggrieved cat respectively. The timing and duration of the dialogue subtitles must be accurate. Continuous meowing by a single cat should be treated as one sentence. The dialogue between the two cats should be humorous, and the employee’s responses to the boss should be witty and have strong potential for widespread sharing on the internet. The length of the dialogue text should be determined based on the duration of each line spoken by the two cats.",
        "files": ["artifacts/video.mp4", "artifacts/bg.jpg"],
        "icon": "video",
    },
]

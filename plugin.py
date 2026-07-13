"""拆分图文/文+表情合发的消息为独立消息发送。

钩住 send_service.after_build_message，检测一条消息中同时包含文字组件
和表情/图片组件时，将表情/图片拆出为独立消息发送，原消息只保留文字。

防递归：拆出的纯表情/图片消息不含文字组件，不满足拆分条件。
"""

from typing import Any, Dict, List

from maibot_sdk import Field, HookHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder


class PluginSection(PluginConfigBase):
    """插件基础配置。"""

    __ui_label__ = "插件设置"
    __ui_order__ = 0

    config_version: str = Field(
        default="1.0.0",
        description="配置文件版本",
    )
    enabled: bool = Field(
        default=True,
        description="启用后将文字+表情/图片的合发消息拆为两条消息发送。",
    )


class SplitConfig(PluginConfigBase):
    """拆分行为配置。"""

    __ui_label__ = "拆分规则"
    __ui_order__ = 10

    split_emoji: bool = Field(
        default=True,
        description="把文字+表情的合发消息拆成文字和表情两条消息。",
    )
    split_image: bool = Field(
        default=False,
        description="把文字+图片的合发消息拆成文字和图片两条消息（默认关闭，图片通常需要附在文字后）。",
    )


class SplitRichMessageConfig(PluginConfigBase):
    """插件完整配置。"""

    plugin: PluginSection = Field(default_factory=PluginSection)
    split: SplitConfig = Field(default_factory=SplitConfig)


class SplitRichMessagePlugin(MaiBotPlugin):
    """拆分合发消息插件。"""

    config_model = SplitRichMessageConfig

    async def on_load(self) -> None:
        self.ctx.logger.info(
            "合发消息拆分插件已加载 (enabled=%s)", self.config.plugin.enabled
        )

    async def on_unload(self) -> None:
        self.ctx.logger.info("合发消息拆分插件已卸载")

    async def on_config_update(
        self, scope: str, config_data: dict[str, object], version: str
    ) -> None:
        self.ctx.logger.info("配置已更新: scope=%s version=%s", scope, version)
        del config_data

    @HookHandler(
        "send_service.after_build_message",
        name="split_rich_message",
        mode=HookMode.BLOCKING,
        order=HookOrder.NORMAL,
        error_policy=ErrorPolicy.SKIP,
        timeout_ms=5000,
    )
    async def handle_split(
        self, message: dict, stream_id: str, **kwargs: Any
    ) -> dict[str, Any]:
        """检查合发消息，拆出表情/图片单独发送。"""
        if not self.config.plugin.enabled:
            return {"action": "continue"}

        raw_message: List[Dict[str, Any]] = message.get("raw_message", []) or []
        if not raw_message:
            return {"action": "continue"}

        # 检查是否同时包含文字和表情/图片
        has_text = any(c.get("type") == "text" for c in raw_message)
        has_emoji = any(c.get("type") == "emoji" for c in raw_message)
        has_image = any(c.get("type") == "image" for c in raw_message)

        should_split_emoji = has_text and has_emoji and self.config.split.split_emoji
        should_split_image = has_text and has_image and self.config.split.split_image

        if not should_split_emoji and not should_split_image:
            return {"action": "continue"}

        # 提取文字内容
        text_parts: list[str] = []
        for c in raw_message:
            if c.get("type") == "text":
                text_parts.append(c.get("data", ""))
        full_text = "".join(text_parts).strip()

        if not full_text:
            return {"action": "continue"}

        # 分类组件：保留的（文字、at、reply等） vs 要拆出的（表情、图片）
        kept_components: list[Dict[str, Any]] = []
        pending_emoji: list[Dict[str, Any]] = []
        pending_image: list[Dict[str, Any]] = []

        for c in raw_message:
            t = c.get("type")
            if t == "text":
                kept_components.append(c)
            elif t == "emoji" and should_split_emoji:
                pending_emoji.append(c)
            elif t == "image" and should_split_image:
                pending_image.append(c)
            else:
                kept_components.append(c)

        if not pending_emoji and not pending_image:
            return {"action": "continue"}

        # 修改原消息：只保留文字 + 非二进制组件
        modified_message = dict(message)
        modified_message["raw_message"] = kept_components
        modified_message["processed_plain_text"] = full_text
        modified_message["is_emoji"] = False
        modified_message["is_picture"] = False

        self.ctx.logger.info(
            "拆分合发消息: stream=%s text_len=%d emoji=%d image=%d",
            stream_id,
            len(full_text),
            len(pending_emoji),
            len(pending_image),
        )

        # 异步发送拆出的表情/图片
        # 这些纯表情/图片消息不含 text 组件，不会再次触发拆分 → 天然防递归
        for emoji_comp in pending_emoji:
            binary_data = emoji_comp.get("binary_data_base64", "")
            if binary_data:
                await self.ctx.send.emoji(binary_data, stream_id)
            else:
                self.ctx.logger.warning(
                    "表情组件缺少 binary_data_base64，跳过: hash=%s",
                    emoji_comp.get("hash", ""),
                )

        for image_comp in pending_image:
            binary_data = image_comp.get("binary_data_base64", "")
            if binary_data:
                await self.ctx.send.image(binary_data, stream_id)
            else:
                self.ctx.logger.warning(
                    "图片组件缺少 binary_data_base64，跳过: hash=%s",
                    image_comp.get("hash", ""),
                )

        # 让修改后的纯文字消息继续走发送流程
        return {
            "action": "continue",
            "modified_kwargs": {
                "message": modified_message,
            },
        }


def create_plugin() -> SplitRichMessagePlugin:
    return SplitRichMessagePlugin()

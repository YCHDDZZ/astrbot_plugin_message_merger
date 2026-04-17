import asyncio
from typing import Dict, List, Tuple

from astrbot.api.event import AstrMessageEvent
import astrbot.api.event
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain


@register("message_merger", "YCHDDZZ", "消息合并器", "1.0.0")
class MessageMerger(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.message_cache: Dict[Tuple[str, str], List[str]] = {}
        self.timers: Dict[Tuple[str, str], asyncio.Task] = {}
        self.merged_flags: Dict[Tuple[str, str], bool] = {}
        self.conversation_history: Dict[Tuple[str, str], List[str]] = {}  # 存储对话历史

    @astrbot.api.event.filter.on_message(priority=5)
    async def on_message(self, event: AstrMessageEvent):
        if not self.config.get("enabled", True):
            await event.continue_event()
            return

        session_id = event.message_obj.session_id
        sender_id = event.message_obj.sender.user_id
        key = (session_id, sender_id)
        message_text = event.message_str

        if not message_text:
            # 清理空消息相关的缓存和计时器
            if key in self.timers:
                self.timers[key].cancel()
                del self.timers[key]
            await event.continue_event()
            return

        if self.merged_flags.get(key, False):
            # 清理已合并标记，准备接收下一轮消息
            if key in self.merged_flags:
                del self.merged_flags[key]
            await event.continue_event()
            return

        if key not in self.message_cache:
            self.message_cache[key] = []
        self.message_cache[key].append(message_text)

        max_messages = self.config.get("max_messages", 5)
        if len(self.message_cache[key]) >= max_messages:
            await self._handle_merge(event, key)
            return

        if key in self.timers:
            self.timers[key].cancel()
        timeout = self.config.get("timeout_seconds", 3)
        self.timers[key] = asyncio.create_task(self._timeout_handler(event, key, timeout))

        event.stop_event()

    async def _timeout_handler(self, event: AstrMessageEvent, key: Tuple[str, str], timeout: int):
        await asyncio.sleep(timeout)
        if key in self.message_cache and self.message_cache[key]:
            combined_text = "\n".join(self.message_cache[key])
            # 更新对话历史
            if key not in self.conversation_history:
                self.conversation_history[key] = []
            self.conversation_history[key].append(combined_text)
            
            self.merged_flags[key] = True
            event.message_str = combined_text
            event.message_obj.message = [Plain(combined_text)]
            self._cleanup(key)
            await event.continue_event()
            logger.info(f"会话 {key} 超时，强制合并并放行")
        elif key in self.message_cache:  # 即使缓存为空也要清理
            self._cleanup(key)

    async def _handle_merge(self, event: AstrMessageEvent, key: Tuple[str, str]):
        if key not in self.message_cache or not self.message_cache[key]:
            return

        combined_text = "\n".join(self.message_cache[key])
        # 获取最近的对话历史用于上下文判断
        recent_history = self.conversation_history.get(key, [])[-3:]  # 取最近3次对话
        is_complete = await self._check_completeness(event, combined_text, recent_history)

        if is_complete:
            # 更新对话历史
            if key not in self.conversation_history:
                self.conversation_history[key] = []
            self.conversation_history[key].append(combined_text)
            
            self.merged_flags[key] = True
            event.message_str = combined_text
            event.message_obj.message = [Plain(combined_text)]
            self._cleanup(key)
            await event.continue_event()
        else:
            logger.info(f"会话 {key} 消息不完整，继续等待")
            # 清理缓存以避免无限积压消息
            self._cleanup(key)

    async def _check_completeness(self, event: AstrMessageEvent, combined_text: str, recent_history: List[str] = None) -> bool:
        judge_prompt_template = self.config.get("judge_prompt", "")
        if not judge_prompt_template:
            # 更全面的完整性检查，不仅看标点符号
            text = combined_text.strip()
            if not text:
                return True  # 空消息认为是完整的
            # 检查是否以表示未完成的词语结尾
            incomplete_endings = ["然后", "还有", "而且", "并且", "但是", "然后呢", "然后呢？", "还有吗", "另外", "此外", "比如"]
            for ending in incomplete_endings:
                if text.endswith(ending):
                    return False
            # 检查是否以标点符号结尾
            return text.endswith(("。", "！", "？", ".", "!", "?", ":", ";"))

        # 如果有对话历史，构建包含上下文的提示词
        if recent_history and len(recent_history) > 0:
            history_context = "\n最近对话历史:\n" + "\n".join([f"- {h}" for h in recent_history])
            prompt = judge_prompt_template.format(text=combined_text) + history_context
        else:
            prompt = judge_prompt_template.format(text=combined_text)
        
        provider_id = await self._get_judge_provider_id(event)

        try:
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
            result = llm_resp.completion_text.strip()
            logger.info(f"判断结果: {result}")
            return "完整" in result
        except Exception as e:
            logger.error(f"调用判断模型失败: {e}，默认放行")
            return True

    async def _get_judge_provider_id(self, event: AstrMessageEvent) -> str:
        config_id = self.config.get("judge_provider_id", "")
        if config_id:
            return config_id
        try:
            umo = event.unified_msg_origin
            return await self.context.get_current_chat_provider_id(umo=umo)
        except Exception as e:
            logger.error(f"获取当前聊天提供商ID失败: {e}，返回空字符串")
            return ""  # 返回空字符串，让后续逻辑处理

    def _cleanup(self, key: Tuple[str, str]):
        if key in self.timers:
            self.timers[key].cancel()
            del self.timers[key]
        if key in self.message_cache:
            del self.message_cache[key]
        if key in self.merged_flags:
            del self.merged_flags[key]
        # 注意：保留对话历史，不在此处清理，因为对话历史用于上下文判断

    async def terminate(self):
        """插件卸载时清理所有定时器"""
        for key, timer in self.timers.items():
            timer.cancel()
        self.timers.clear()
        self.message_cache.clear()
        self.merged_flags.clear()
        self.conversation_history.clear()  # 清理对话历史
        logger.info("消息合并插件已卸载，资源已清理")
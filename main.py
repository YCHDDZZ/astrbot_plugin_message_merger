import asyncio
from typing import Dict, List, Tuple, Optional

from astrbot.api.event import AstrMessageEvent
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
        self.conversation_history: Dict[Tuple[str, str], List[str]] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        # 初始化配置
        self.config = getattr(context, '_config', {})
        self._start_auto_cleanup()
        
        # 添加对 follow-up 消息的支持
        self.follow_up_processing = True
        
    # 直接重写 on_message 方法，无需装饰器
    async def on_message(self, event: AstrMessageEvent):
        # 检查是否启用调试日志
        advanced_settings = self.config.get("advanced_settings", {})
        enable_debug = advanced_settings.get("enable_debug_log", False)
        
        if enable_debug:
            logger.info(f"消息合并插件接收到消息: {event.message_str}")
            # 检查消息来源，看是否能识别 follow-up 消息
            if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'extra'):
                extra_info = getattr(event.message_obj, 'extra', {})
                if extra_info:
                    logger.info(f"消息额外信息: {extra_info}")
        
        if not self.config.get("enabled", True):
            if enable_debug:
                logger.info("插件未启用，继续事件处理")
            await event.continue_event()
            return

        session_id = event.message_obj.session_id
        sender_id = event.message_obj.sender.user_id
        key = (session_id, sender_id)
        message_text = event.message_str

        if not message_text:
            if enable_debug:
                logger.info(f"收到空消息，继续事件处理")
            if key in self.timers:
                self.timers[key].cancel()
                del self.timers[key]
            await event.continue_event()
            return

        if self.merged_flags.get(key, False):
            # 清除合并标记，准备接收新消息
            if key in self.merged_flags:
                del self.merged_flags[key]
            if enable_debug:
                logger.info(f"处理合并后消息，继续事件处理")
            # 由于这是合并后的消息处理完毕，我们需要继续事件处理
            await event.continue_event()
            return

        if key not in self.message_cache:
            self.message_cache[key] = []
        self.message_cache[key].append(message_text)

        if enable_debug:
            logger.info(f"缓存消息: '{message_text}', 当前缓存大小: {len(self.message_cache[key])}, key: {key}")

        # 获取合并配置
        merge_settings = self.config.get("merge_settings", {})
        max_messages = merge_settings.get("max_messages", 5)
        
        if len(self.message_cache[key]) >= max_messages:
            # 达到最大消息数限制，强制合并
            combined_text = "\n".join(self.message_cache[key])
            if enable_debug:
                logger.info(f"达到最大消息数限制，强制合并: {combined_text}")
            if key not in self.conversation_history:
                self.conversation_history[key] = []
            self.conversation_history[key].append(combined_text)

            self.merged_flags[key] = True
            event.message_str = combined_text
            event.message_obj.message = [Plain(combined_text)]
            self._cleanup(key)
            await event.continue_event()
            return

        if key in self.timers:
            self.timers[key].cancel()
        
        timeout = merge_settings.get("timeout_seconds", 3)
        if enable_debug:
            logger.info(f"启动 {timeout} 秒超时计时器，key: {key}")
        self.timers[key] = asyncio.create_task(self._timeout_handler(event, key, timeout))

        # 关键：总是阻止事件传播，直到我们决定是否合并消息
        event.stop_event()
        
    def _should_intercept_message(self, event: AstrMessageEvent) -> bool:
        """
        判断是否应该拦截当前消息
        """
        return self.config.get("enabled", True)

    async def _timeout_handler(self, event: AstrMessageEvent, key: Tuple[str, str], timeout: int):
        await asyncio.sleep(timeout)
        # 检查是否启用调试日志
        advanced_settings = self.config.get("advanced_settings", {})
        enable_debug = advanced_settings.get("enable_debug_log", False)
        
        if enable_debug:
            logger.info(f"会话 {key} 超时 ({timeout}秒)，开始处理...")
            
        if key in self.message_cache and self.message_cache[key]:
            combined_text = "\n".join(self.message_cache[key])
            # 即使超时，也要先检查完整性，除非达到最大消息数限制
            recent_history = self.conversation_history.get(key, [])[-3:]
            is_complete = await self._check_completeness(event, combined_text, recent_history)
            
            if is_complete or len(self.message_cache[key]) >= self.config.get("merge_settings", {}).get("max_messages", 5):
                # 消息完整或已达到最大消息数，发送合并的消息
                if key not in self.conversation_history:
                    self.conversation_history[key] = []
                self.conversation_history[key].append(combined_text)

                self.merged_flags[key] = True
                event.message_str = combined_text
                event.message_obj.message = [Plain(combined_text)]
                self._cleanup(key)
                if enable_debug:
                    logger.info(f"会话 {key} 超时，合并并放行完整消息: {combined_text}")
                await event.continue_event()
            else:
                # 消息不完整，继续等待
                if enable_debug:
                    logger.info(f"会话 {key} 消息不完整，继续等待: {combined_text}")
                merge_settings = self.config.get("merge_settings", {})
                timeout = merge_settings.get("timeout_seconds", 3)
                if key in self.timers:
                    self.timers[key].cancel()
                self.timers[key] = asyncio.create_task(self._timeout_handler(event, key, timeout))
        elif key in self.message_cache:
            self._cleanup(key)
            if enable_debug:
                logger.info(f"会话 {key} 清理空缓存")

    async def _handle_merge(self, event: AstrMessageEvent, key: Tuple[str, str]):
        if key not in self.message_cache or not self.message_cache[key]:
            return

        combined_text = "\n".join(self.message_cache[key])
        recent_history = self.conversation_history.get(key, [])[-3:]
        is_complete = await self._check_completeness(event, combined_text, recent_history)

        if is_complete:
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
            self._cleanup(key)

    async def _check_completeness(self, event: AstrMessageEvent, combined_text: str, recent_history: List[str] = None) -> bool:
        # 检查是否启用调试日志
        advanced_settings = self.config.get("advanced_settings", {})
        enable_debug = advanced_settings.get("enable_debug_log", False)
        
        if enable_debug:
            logger.info(f"检查消息完整性: {combined_text}")
        
        # 获取模型配置
        model_settings = self.config.get("model_settings", {})
        judge_prompt_template = model_settings.get("judge_prompt", "")
        
        if not judge_prompt_template:
            text = combined_text.strip()
            if not text:
                if enable_debug:
                    logger.info("消息为空，判断为完整")
                return True
            incomplete_endings = ["然后", "还有", "而且", "并且", "但是", "然后呢", "然后呢？", "还有吗", "另外", "此外", "比如"]
            for ending in incomplete_endings:
                if text.endswith(ending):
                    if enable_debug:
                        logger.info(f"消息以 '{ending}' 结尾，判断为不完整")
                    return False
            is_complete = text.endswith(("。", "！", "？", ".", "!", "?", ":", ";"))
            if enable_debug:
                logger.info(f"基于标点符号判断，消息{'完整' if is_complete else '不完整'}: {text}")
            return is_complete

        if recent_history and len(recent_history) > 0:
            history_context = "\n最近对话历史:\n" + "\n".join([f"- {h}" for h in recent_history])
            prompt = judge_prompt_template.format(text=combined_text) + history_context
        else:
            prompt = judge_prompt_template.format(text=combined_text)

        provider_id = await self._get_judge_provider_id(event)
        model_id = model_settings.get("judge_model_id", "")

        try:
            if enable_debug:
                logger.info(f"调用模型判断消息完整性，提供商: {provider_id}, 模型: {model_id}")
                
            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                model_id=model_id if model_id else None,
                prompt=prompt,
            )
            result = llm_resp.completion_text.strip()
            
            if enable_debug:
                logger.info(f"模型判断结果: {result}")
                
            is_complete = "完整" in result
            if enable_debug:
                logger.info(f"最终判断结果: {'完整' if is_complete else '不完整'}")
                
            return is_complete
        except Exception as e:
            logger.error(f"调用判断模型失败: {e}，默认放行")
            return True

    async def _get_judge_provider_id(self, event: AstrMessageEvent) -> str:
        model_settings = self.config.get("model_settings", {})
        config_id = model_settings.get("judge_provider_id", "")
        if config_id:
            return config_id
        try:
            umo = event.unified_msg_origin
            return await self.context.get_current_chat_provider_id(umo=umo)
        except Exception as e:
            logger.error(f"获取当前聊天提供商ID失败: {e}，返回空字符串")
            return ""

    def _start_auto_cleanup(self):
        """启动自动清理任务"""
        async def cleanup_loop():
            while True:
                try:
                    # 获取清理间隔配置
                    advanced_settings = self.config.get("advanced_settings", {})
                    interval_minutes = advanced_settings.get("auto_cleanup_interval", 30)
                    
                    # 转换为秒
                    interval_seconds = interval_minutes * 60
                    
                    # 等待清理间隔
                    await asyncio.sleep(interval_seconds)
                    
                    # 执行清理
                    self._perform_cleanup()
                    
                    # 记录清理日志（如果启用调试日志）
                    if advanced_settings.get("enable_debug_log", False):
                        logger.info(f"自动清理完成，下次清理将在 {interval_minutes} 分钟后执行")
                        
                except Exception as e:
                    logger.error(f"自动清理任务出错: {e}")
                    await asyncio.sleep(60)  # 出错后等待1分钟再重试
        
        self.cleanup_task = asyncio.create_task(cleanup_loop())

    def _perform_cleanup(self):
        """执行清理操作"""
        # 清理过期的计时器
        current_time = asyncio.get_event_loop().time()
        keys_to_remove = []
        
        for key, timer in self.timers.items():
            if timer.done():
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            if key in self.timers:
                del self.timers[key]
            if key in self.message_cache:
                del self.message_cache[key]
            if key in self.merged_flags:
                del self.merged_flags[key]
        
        # 清理长时间未使用的对话历史（超过1小时）
        # 这里可以添加更复杂的清理逻辑，但目前先简单清理
        if keys_to_remove:
            logger.debug(f"清理了 {len(keys_to_remove)} 个过期会话")

    def _cleanup(self, key: Tuple[str, str]):
        if key in self.timers:
            self.timers[key].cancel()
            del self.timers[key]
        if key in self.message_cache:
            del self.message_cache[key]
        if key in self.merged_flags:
            del self.merged_flags[key]

    async def terminate(self):
        # 停止自动清理任务
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 清理所有计时器
        for key, timer in self.timers.items():
            timer.cancel()
        self.timers.clear()
        self.message_cache.clear()
        self.merged_flags.clear()
        self.conversation_history.clear()
        logger.info("消息合并插件已卸载，资源已清理")
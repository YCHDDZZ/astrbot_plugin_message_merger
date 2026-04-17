import asyncio
from typing import Dict, List, Tuple, Optional

from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain


@register("message_merger", "YCHDDZZ", "消息合并器", "1.0.1")
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

    async def on_message(self, event: AstrMessageEvent):
        # ========== 优先级设置 ==========
        # 尝试设置最高优先级，确保插件在其他处理器之前执行
        if hasattr(event, 'set_priority'):
            try:
                event.set_priority(0)  # 数值越小优先级越高
                logger.debug("消息合并插件优先级已设置为最高 (0)")
            except Exception as e:
                logger.warning(f"设置优先级失败: {e}")

        # ========== 配置读取 ==========
        enabled = self.config.get("enabled", True)
        advanced_settings = self.config.get("advanced_settings", {})
        enable_debug = advanced_settings.get("enable_debug_log", False)
        intercept_follow_up = advanced_settings.get("enable_follow_up_interception", True)

        # ========== Follow-up 检测与拦截 ==========
        is_follow_up = False
        if hasattr(event, 'is_follow_up'):
            is_follow_up = event.is_follow_up
        # 有些框架可能用 extra 字段标记
        elif hasattr(event, 'message_obj') and hasattr(event.message_obj, 'extra'):
            extra = getattr(event.message_obj, 'extra', {})
            is_follow_up = extra.get('is_follow_up', False)

        if enable_debug:
            logger.info(f"收到消息: '{event.message_str}' | session={event.message_obj.session_id} | "
                        f"sender={event.message_obj.sender.user_id} | is_follow_up={is_follow_up}")

        # 插件未启用，直接放行
        if not enabled:
            if enable_debug:
                logger.info("插件未启用，放行消息")
            await event.continue_event()
            return

        # 如果消息是 follow-up 且拦截功能开启，则强制停止传播并处理
        if is_follow_up and intercept_follow_up:
            if enable_debug:
                logger.info("检测到 follow-up 消息，强制拦截并进入合并流程")
            event.stop_event()  # 阻止原有路由
            # 注意：不要立即 return，继续执行合并逻辑

        # ========== 正常消息处理 ==========
        session_id = event.message_obj.session_id
        sender_id = event.message_obj.sender.user_id
        key = (session_id, sender_id)
        message_text = event.message_str

        # 空消息处理
        if not message_text:
            if enable_debug:
                logger.info("收到空消息，清理相关状态并放行")
            if key in self.timers:
                self.timers[key].cancel()
                del self.timers[key]
            # 若非 follow-up 拦截模式，则继续事件；若为拦截模式则直接返回
            if is_follow_up and intercept_follow_up:
                return  # 已被 stop_event，不再传播
            await event.continue_event()
            return

        # 如果该 key 的合并消息刚刚发送完成，则清除标记并放行（这是合并后第一条新消息的正常流程）
        if self.merged_flags.get(key, False):
            if key in self.merged_flags:
                del self.merged_flags[key]
            if enable_debug:
                logger.info("合并后新消息，正常放行")
            if is_follow_up and intercept_follow_up:
                # 如果仍在拦截模式下，需要主动发送该消息，因为事件已被 stop
                await self._send_message(event, message_text)
                return
            await event.continue_event()
            return

        # 缓存消息
        if key not in self.message_cache:
            self.message_cache[key] = []
        self.message_cache[key].append(message_text)

        if enable_debug:
            logger.info(f"缓存消息: '{message_text}' | 当前缓存: {self.message_cache[key]} | key={key}")

        # 获取合并配置
        merge_settings = self.config.get("merge_settings", {})
        max_messages = merge_settings.get("max_messages", 5)

        # 达到最大消息数限制，强制合并
        if len(self.message_cache[key]) >= max_messages:
            combined_text = "\n".join(self.message_cache[key])
            if enable_debug:
                logger.info(f"达到最大消息数 {max_messages}，强制合并: {combined_text}")

            if key not in self.conversation_history:
                self.conversation_history[key] = []
            self.conversation_history[key].append(combined_text)

            self.merged_flags[key] = True
            self._cleanup(key)
            # 直接发送合并消息
            await self._send_message(event, combined_text)
            return

        # 重置计时器
        if key in self.timers:
            self.timers[key].cancel()

        timeout = merge_settings.get("timeout_seconds", 3)
        if enable_debug:
            logger.info(f"启动 {timeout} 秒超时计时器，key={key}")
        self.timers[key] = asyncio.create_task(self._timeout_handler(event, key, timeout))

        # 始终停止事件传播（除非我们主动放行）
        event.stop_event()

    async def _timeout_handler(self, event: AstrMessageEvent, key: Tuple[str, str], timeout: int):
        await asyncio.sleep(timeout)

        advanced_settings = self.config.get("advanced_settings", {})
        enable_debug = advanced_settings.get("enable_debug_log", False)

        if enable_debug:
            logger.info(f"会话 {key} 超时 ({timeout}秒)，检查合并条件")

        if key not in self.message_cache or not self.message_cache[key]:
            self._cleanup(key)
            # 超时但无消息，放行原始事件（由于之前 stop 了，这里需要继续传播）
            await event.continue_event()
            return

        combined_text = "\n".join(self.message_cache[key])
        recent_history = self.conversation_history.get(key, [])[-3:]
        is_complete = await self._check_completeness(event, combined_text, recent_history)

        max_messages = self.config.get("merge_settings", {}).get("max_messages", 5)

        if is_complete or len(self.message_cache[key]) >= max_messages:
            # 消息完整或达到最大条数，执行合并发送
            if key not in self.conversation_history:
                self.conversation_history[key] = []
            self.conversation_history[key].append(combined_text)

            self.merged_flags[key] = True
            self._cleanup(key)

            if enable_debug:
                logger.info(f"会话 {key} 合并发送: {combined_text}")

            await self._send_message(event, combined_text)
        else:
            # 消息不完整，继续等待
            if enable_debug:
                logger.info(f"会话 {key} 消息不完整，重置计时器继续等待")
            merge_settings = self.config.get("merge_settings", {})
            new_timeout = merge_settings.get("timeout_seconds", 3)
            if key in self.timers:
                self.timers[key].cancel()
            self.timers[key] = asyncio.create_task(self._timeout_handler(event, key, new_timeout))
            # 注意：继续 stop 状态，不传播事件

    async def _send_message(self, event: AstrMessageEvent, text: str):
        """
        主动发送一条消息到当前会话
        """
        try:
            # 方法1：使用 context 的发送接口（如果存在）
            if hasattr(self.context, 'send_message'):
                await self.context.send_message(
                    unified_msg_origin=event.unified_msg_origin,
                    message_chain=[Plain(text)]
                )
                logger.info(f"已发送合并消息: {text}")
                return
        except Exception as e:
            logger.error(f"通过 context.send_message 发送失败: {e}")

        try:
            # 方法2：使用 event 的发送方法（部分框架支持）
            if hasattr(event, 'send'):
                await event.send(text)
                logger.info(f"已通过 event.send 发送合并消息: {text}")
                return
        except Exception as e:
            logger.error(f"通过 event.send 发送失败: {e}")

        try:
            # 方法3：通过平台适配器发送
            platform = self.context.get_platform(event.unified_msg_origin)
            if platform:
                await platform.send_message(
                    target=event.unified_msg_origin,
                    message=[Plain(text)]
                )
                logger.info(f"已通过平台适配器发送合并消息: {text}")
                return
        except Exception as e:
            logger.error(f"通过平台发送失败: {e}")

        # 最终降级：打印警告，并尝试让原始事件继续传播（不推荐）
        logger.warning("无法主动发送消息，尝试继续传播原始事件（可能导致碎片消息）")
        event.message_str = text
        event.message_obj.message = [Plain(text)]
        await event.continue_event()

    async def _check_completeness(self, event: AstrMessageEvent, combined_text: str, recent_history: List[str] = None) -> bool:
        advanced_settings = self.config.get("advanced_settings", {})
        enable_debug = advanced_settings.get("enable_debug_log", False)

        if enable_debug:
            logger.info(f"检查消息完整性: {combined_text}")

        model_settings = self.config.get("model_settings", {})
        judge_prompt_template = model_settings.get("judge_prompt", "")

        if not judge_prompt_template:
            # 无模型配置时的简单规则判断
            text = combined_text.strip()
            if not text:
                return True
            incomplete_endings = ["然后", "还有", "而且", "并且", "但是", "然后呢", "然后呢？", "还有吗", "另外", "此外", "比如"]
            for ending in incomplete_endings:
                if text.endswith(ending):
                    if enable_debug:
                        logger.info(f"消息以 '{ending}' 结尾，判断为不完整")
                    return False
            is_complete = text.endswith(("。", "！", "？", ".", "!", "?", ":", ";"))
            if enable_debug:
                logger.info(f"基于标点判断: {'完整' if is_complete else '不完整'}")
            return is_complete

        # 使用 LLM 判断
        if recent_history and len(recent_history) > 0:
            history_context = "\n最近对话历史:\n" + "\n".join([f"- {h}" for h in recent_history])
            prompt = judge_prompt_template.format(text=combined_text) + history_context
        else:
            prompt = judge_prompt_template.format(text=combined_text)

        provider_id = await self._get_judge_provider_id(event)
        model_id = model_settings.get("judge_model_id", "")

        try:
            if enable_debug:
                logger.info(f"调用 LLM 判断完整性，provider={provider_id}, model={model_id}")

            llm_resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                model_id=model_id if model_id else None,
                prompt=prompt,
            )
            result = llm_resp.completion_text.strip()
            if enable_debug:
                logger.info(f"LLM 返回: {result}")

            is_complete = "完整" in result
            if enable_debug:
                logger.info(f"最终判断: {'完整' if is_complete else '不完整'}")
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
        async def cleanup_loop():
            while True:
                try:
                    advanced_settings = self.config.get("advanced_settings", {})
                    interval_minutes = advanced_settings.get("auto_cleanup_interval", 30)
                    interval_seconds = interval_minutes * 60
                    await asyncio.sleep(interval_seconds)

                    self._perform_cleanup()

                    if advanced_settings.get("enable_debug_log", False):
                        logger.info(f"自动清理完成，下次清理将在 {interval_minutes} 分钟后执行")
                except Exception as e:
                    logger.error(f"自动清理任务出错: {e}")
                    await asyncio.sleep(60)

        self.cleanup_task = asyncio.create_task(cleanup_loop())

    def _perform_cleanup(self):
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
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        for timer in self.timers.values():
            timer.cancel()
        self.timers.clear()
        self.message_cache.clear()
        self.merged_flags.clear()
        self.conversation_history.clear()
        logger.info("消息合并插件已卸载，资源已清理")
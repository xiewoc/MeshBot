# core/message_processor.py
import logging
from typing import Dict, Any, Optional, Tuple, List

from meshbot.config.config_loader import get_system_prompt, get_max_response_length
from meshbot.utils.text_utils import truncate_by_sentences

logger = logging.getLogger(__name__)


class MessageProcessor:
    """处理 Meshtastic 消息的解析和处理"""
    
    def __init__(self, nodes, node_id):
        self.nodes = nodes
        self.node_id = node_id
        self.system_prompt = get_system_prompt()
        self.max_response_length = get_max_response_length()
        
        # 群发消息配置
        self.broadcast_enabled = True  # 是否启用群发消息处理
        self.broadcast_keywords = ["@all", "@大家", "@所有人", "大家", "全体"]  # 触发关键词
        self.broadcast_response_threshold = 0.7  # 相似度阈值，用于判断是否需要回复群发消息
        
        # 消息统计
        self.message_stats = {
            "private_messages": 0,
            "broadcast_messages": 0,
            "mentions": 0
        }

    def analyze_packet(self, packet: Dict[str, Any]) -> Optional[Tuple]:
        """解析数据包"""
        if 'decoded' not in packet:
            logger.warning("⚠️ 数据包缺少 'decoded' 字段")
            return None

        from_id = packet.get('from', '未知')
        from_id_hex = packet.get('fromId', '未知')
        to_id = packet.get('to', '未知')
        decoded = packet['decoded']
        message_type = decoded.get('portnum', '未知类型')

        if message_type == 'TEXT_MESSAGE_APP':
            # 处理所有文本消息，包括私聊和群发
            return self._process_text_message(
                packet, from_id, from_id_hex, to_id, decoded
            )
        elif message_type == 'POSITION_APP':
            self._process_position_message(packet, from_id)
        return None

    def _process_text_message(
        self,
        packet: Dict[str, Any],
        from_id: str,
        from_id_hex: str,
        to_id: str,
        decoded: Dict[str, Any],
    ) -> Optional[Tuple]:
        """处理文本消息"""
        text = decoded.get('text', '').strip()
        if not text:
            return None

        long_name = self._get_sender_name(from_id_hex)
        self._log_message_reception(from_id, long_name, text, packet, to_id)
        
        # 判断消息类型
        is_broadcast = self._is_broadcast_message(to_id)
        is_mention = self._contains_mention(text, long_name)
        
        # 更新统计
        if is_broadcast:
            self.message_stats["broadcast_messages"] += 1
        else:
            self.message_stats["private_messages"] += 1
            
        if is_mention:
            self.message_stats["mentions"] += 1
        
        # 返回消息数据，包含消息类型信息
        return (from_id, to_id, long_name, text, is_broadcast, is_mention)

    def _is_broadcast_message(self, to_id: str) -> bool:
        """判断是否为群发消息"""
        # 在 Meshtastic 中，广播消息的 to_id 通常为特定值或与当前节点不同
        # 常见的广播地址：0xffffffff (广播到所有节点), 0xfffffff0 (广播到附近节点)
        broadcast_addresses = {
            "4294967295",  # 0xffffffff 的十进制
            "4294967280",  # 0xfffffff0 的十进制
            "65535",       # 其他可能的广播地址
            "65534"
        }
        
        # 如果 to_id 是广播地址，或者是空值（某些情况下的广播）
        if to_id in broadcast_addresses or to_id == "0" or to_id == "65535":
            return True
            
        # 如果 to_id 不是当前节点，也视为广播（消息不是直接发给我们的）
        if to_id != self.node_id:
            return True
            
        return False

    def _contains_mention(self, text: str, sender_name: str) -> bool:
        """检查消息是否包含提及"""
        # 检查直接提及机器人
        bot_mentions = [
            "@bot", "@机器人", "@ai", "@助手",
            f"@{sender_name}" if sender_name else ""
        ]
        
        for mention in bot_mentions:
            if mention and mention.lower() in text.lower():
                return True
        
        # 检查群发关键词
        for keyword in self.broadcast_keywords:
            if keyword in text:
                return True
                
        return False

    def _should_respond_to_broadcast(self, text: str, long_name: str, is_mention: bool) -> bool:
        """判断是否应该回复群发消息"""
        # 如果明确提及，总是回复
        if is_mention:
            logger.info(f"🎯 检测到提及，将回复群发消息")
            return True
            
        # 检查消息是否包含问题或请求
        question_indicators = ["吗？", "?", "怎么办", "如何", "为什么", "什么", "怎样", "能不能", "是否可以"]
        for indicator in question_indicators:
            if indicator in text:
                logger.info(f"❓ 检测到问题，将回复群发消息")
                return True
                
        # 对于其他群发消息，可以根据配置决定是否回复
        if self.broadcast_enabled:
            # 简单的关键词匹配
            response_keywords = ["帮助", "求助", "问题", "请教", "建议", "意见"]
            for keyword in response_keywords:
                if keyword in text:
                    logger.info(f"🔍 检测到关键词 '{keyword}'，将回复群发消息")
                    return True
                    
        return False

    def _get_sender_name(self, from_id_hex: str) -> str:
        """获取发送者名称"""
        if not self.nodes:
            return ""
        node_info = self.nodes.get(from_id_hex)
        if isinstance(node_info, dict):
            long_name = node_info.get('user', {}).get('longName', '')
            if long_name:
                logger.info(
                    f"👤 节点 {from_id_hex} 名称: {long_name}"
                )
            return long_name
        else:
            logger.warning(f"⚠️ 节点 {from_id_hex} 信息非字典类型")
            return ""

    def _log_message_reception(
        self,
        from_id: str,
        long_name: str,
        text: str,
        packet: Dict[str, Any],
        to_id: str,
    ) -> None:
        """记录消息日志"""
        rssi = packet.get('rxRssi')
        snr = packet.get('rxSnr')
        name_info = f"({long_name})" if long_name else ""
        short_text = text[:50] + ('...' if len(text) > 50 else '')
        
        # 判断消息类型并添加相应标识
        is_broadcast = self._is_broadcast_message(to_id)
        message_type = "📢 群发" if is_broadcast else "📩 私聊"
        
        logger.info(
            f"{message_type} 来自 {from_id}{name_info}: {short_text}"
        )
        
        if rssi is not None:
            logger.debug(f"📶 RSSI: {rssi} dBm")
        if snr is not None:
            logger.debug(f"🔊 SNR: {snr} dB")

    def _process_position_message(self, packet: Dict[str, Any], from_id: str) -> None:
        """处理位置消息"""
        location_info = self._parse_from_and_position(packet)
        if not location_info:
            return

        pos = location_info.get('position')
        if not pos:
            return

        # 始终记录非敏感信息
        logger.info(
            f"📍 收到 {from_id} 的位置信息"
        )

        # 仅在 DEBUG 模式下记录详细坐标
        if logger.isEnabledFor(logging.DEBUG):
            lat = pos['latitude']
            lon = pos['longitude']
            logger.debug(
                f"详细位置: {lat:.6f}, {lon:.6f}"
            )

    def _parse_from_and_position(
        self,
        packet: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """解析位置数据包"""
        result = {}
        from_id_int = packet.get('from')
        if not from_id_int:
            logger.error("❌ 缺少 'from' 字段")
            return None

        node_hex = f"{from_id_int:08x}".lower()
        result['node_id'] = {
            'decimal': from_id_int,
            'hex': node_hex,
            'formatted': f"!{node_hex}",
        }

        decoded = packet.get('decoded')
        if not decoded or decoded.get('portnum') != 'POSITION_APP':
            result['position'] = None
        else:
            result['position'] = self._extract_position_data(decoded.get('position'))

        return result

    def _extract_position_data(
        self,
        position: Optional[Dict],
    ) -> Optional[Dict[str, Any]]:
        """提取位置字段"""
        if not position:
            logger.warning("⚠️ 位置数据为空")
            return None

        lat = position.get('latitude')
        lon = position.get('longitude')
        alt = position.get('altitude')

        if lat is None or lon is None:
            logger.error("❌ 缺失经纬度")
            return None

        return {'latitude': lat, 'longitude': lon, 'altitude': alt}

    async def handle_incoming_message(self, message_data: Tuple, interface, client) -> None:
        """调用 AI 并回复消息"""
        from_id, to_id, long_name, text, is_broadcast, is_mention = message_data
        
        try:
            # 对于群发消息，检查是否需要回复
            if is_broadcast and not self._should_respond_to_broadcast(text, long_name, is_mention):
                logger.info(f"⏭️  忽略群发消息（未触发回复条件）")
                return
                
            # 构建系统提示（针对群发消息添加额外上下文）
            system_prompt = self._build_contextual_prompt(
                self.system_prompt, is_broadcast, long_name
            )
            
            result = await client.chat(
                long_name, text, system_prompt=system_prompt
            )
            
            if result["success"]:
                response = result['response'][:self.max_response_length]
                # 如果 response 是 list/tuple，先 join 为字符串；保证后续按字节处理
                if isinstance(response, (list, tuple)):
                    response = "\n".join(map(str, response))

                # 为群发消息添加前缀标识
                if is_broadcast:
                    response = f"💬 {response}"
                    logger.info(f"🤖 AI 回复群发消息: {response}")
                else:
                    logger.info(f"🤖 AI 回复私聊消息: {response}")

                # 基于 UTF-8 字节长度判断是否需要分片
                try:
                    resp_bytes_len = len(response.encode('utf-8'))
                except Exception:
                    resp_bytes_len = len(str(response))

                # 发送回复
                if resp_bytes_len > self.max_response_length:
                    response_list = truncate_by_sentences(response, self.max_response_length)
                    for sentence in response_list:
                        if is_broadcast:
                            # 群发消息使用广播方式回复
                            interface.sendText(sentence)
                        else:
                            # 私聊消息回复给发送者
                            interface.sendText(sentence, from_id)
                else:
                    if is_broadcast:
                        # 群发消息使用广播方式回复
                        interface.sendText(response)
                    else:
                        # 私聊消息回复给发送者
                        interface.sendText(response, from_id)
            else:
                error_msg = result.get('error', '未知错误')
                logger.error(
                    f"❌ AI 处理失败: {error_msg}"
                )
                # 错误消息也根据消息类型发送
                if is_broadcast:
                    interface.sendText(f"❌ 处理失败: {error_msg}")
                else:
                    interface.sendText(
                        f"❌ 处理失败: {error_msg}",
                        from_id
                    )
        except Exception as e:
            logger.error(f"❌ 消息处理异常: {e}")
            if is_broadcast:
                interface.sendText("❌ 处理异常，请稍后重试")
            else:
                interface.sendText("❌ 处理异常，请稍后重试", from_id)

    def _build_contextual_prompt(self, base_prompt: str, is_broadcast: bool, sender_name: str) -> str:
        """构建上下文相关的系统提示"""
        if is_broadcast:
            return f"""{base_prompt}

当前场景：这是一条群发消息，来自{sender_name}。请用适当的语气回复，让所有群组成员都能受益。
回复要求：简洁明了，对大家都有帮助。
"""
        else:
            return base_prompt

    def get_message_stats(self) -> Dict[str, Any]:
        """获取消息统计信息"""
        return {
            **self.message_stats,
            "total_messages": sum(self.message_stats.values()),
            "broadcast_enabled": self.broadcast_enabled
        }

    def update_broadcast_settings(self, enabled: bool = False, keywords: List[str] = [""]):
        """更新群发消息设置"""
        if enabled is not None:
            self.broadcast_enabled = enabled
            logger.info(f"🔄 群发消息处理: {'启用' if enabled else '禁用'}")
            
        if keywords is not None:
            self.broadcast_keywords = keywords
            logger.info(f"🔄 更新群发触发关键词: {keywords}")
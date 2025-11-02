# utils/text_utils.py
import re
import logging

logger = logging.getLogger(__name__)


def truncate_by_sentences(text, byte_limit):
    """
    将文本按完整句子截断，确保每段在 UTF-8 编码下不超过 byte_limit 字节。

    Args:
        text (str): 输入文本
        byte_limit (int): 每段的最大字节数限制（UTF-8）

    Returns:
        list: 包含截断后句子的列表（每项为 str）
    """
    if not text or byte_limit <= 0:
        return []

    # 将非字符串（例如 list/tuple）转换为字符串
    if isinstance(text, (list, tuple)):
        text = "\n".join(map(str, text))

    # 使用正则表达式分割句子（支持中文和英文标点和换行）
    sentence_endings = r'[。！？!?\.]|\n+'
    sentences = re.split(sentence_endings, text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    result = []
    current_chunk = ""

    def byte_len(s: str) -> int:
        return len(s.encode('utf-8'))

    for sentence in sentences:
        # 如果单句字节数就超过限制，需要进一步按短停顿分割
        if byte_len(sentence) > byte_limit:
            if current_chunk:
                result.append(current_chunk)
                current_chunk = ""

            # 对超长句子按中文或英文逗号等进一步分割
            sub_sentences = re.split(r'[，,；;\s]+', sentence)
            for sub in sub_sentences:
                sub = sub.strip()
                if not sub:
                    continue

                if current_chunk and byte_len(current_chunk + '，' + sub) <= byte_limit:
                    current_chunk = current_chunk + '，' + sub
                elif not current_chunk and byte_len(sub) <= byte_limit:
                    current_chunk = sub
                else:
                    if current_chunk:
                        result.append(current_chunk + '。')
                    # 如果单个 sub 仍然超出限制，则需要按字截断（安全回退）
                    if byte_len(sub) > byte_limit:
                        # 逐字（逐字符）累加，注意多字节字符
                        temp = ''
                        for ch in sub:
                            if byte_len(temp + ch) <= byte_limit:
                                temp += ch
                            else:
                                if temp:
                                    result.append(temp + '。')
                                temp = ch
                        if temp:
                            current_chunk = temp
                        else:
                            current_chunk = ''
                    else:
                        current_chunk = sub

            continue

        # 正常句子处理（基于字节长度）
        if current_chunk:
            candidate = current_chunk + '。' + sentence
        else:
            candidate = sentence

        if byte_len(candidate) <= byte_limit:
            current_chunk = candidate
        else:
            if current_chunk:
                result.append(current_chunk + '。')
            current_chunk = sentence

    if current_chunk:
        # 确保末尾有句号风格的终止符
        if not current_chunk.endswith('。'):
            current_chunk = current_chunk + '。'
        result.append(current_chunk)

    return result
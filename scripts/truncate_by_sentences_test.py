import re

def truncate_by_sentences(text, char_limit):
    """
    将文本按完整句子截断，确保每段在字符限制内
    
    Args:
        text (str): 输入文本
        char_limit (int): 每段的最大字符数限制
    
    Returns:
        list: 包含截断后句子的列表
    """
    if not text or char_limit <= 0:
        return []
    
    # 使用正则表达式分割句子（支持中文和英文标点）
    sentence_endings = r'[。！？!?\.\n]+\s*'
    sentences = re.split(sentence_endings, text.strip())
    
    # 过滤空字符串
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return []
    
    result = []
    current_chunk = ""
    
    for sentence in sentences:
        # 如果单句就超过限制，需要进一步分割
        if len(sentence) > char_limit:
            if current_chunk:
                result.append(current_chunk)
                current_chunk = ""
            
            # 对超长句子按标点进一步分割
            sub_sentences = re.split(r'[，,；;]', sentence)
            for sub_sentence in sub_sentences:
                sub_sentence = sub_sentence.strip()
                if not sub_sentence:
                    continue
                    
                if len(current_chunk) + len(sub_sentence) + 1 <= char_limit:
                    if current_chunk:
                        current_chunk += "，" + sub_sentence
                    else:
                        current_chunk = sub_sentence
                else:
                    if current_chunk:
                        result.append(current_chunk)
                    current_chunk = sub_sentence
            
            continue
        
        # 正常句子处理
        if len(current_chunk) + len(sentence) + 1 <= char_limit:
            if current_chunk:
                current_chunk += "。" + sentence
            else:
                current_chunk = sentence
        else:
            if current_chunk:
                result.append(current_chunk + "。")
            current_chunk = sentence
    
    # 添加最后一段
    if current_chunk:
        result.append(current_chunk + "。")
    
    return result

# 测试函数
def test_truncate_function():
    # 测试用例1：普通中文文本
    text1 = "这是一个测试句子。这是另一个测试句子。这是第三个测试句子。"
    result1 = truncate_by_sentences(text1, 20)
    print("测试1:", result1)
    
    # 测试用例2：包含长句子的文本
    text2 = "这是一个很长的测试句子，它包含多个部分，需要被适当分割。这是另一个普通句子。"
    result2 = truncate_by_sentences(text2, 25)
    print("测试2:", result2)
    
    # 测试用例3：英文文本
    text3 = "This is a test sentence. This is another test sentence. This is the third test sentence."
    result3 = truncate_by_sentences(text3, 30)
    print("测试3:", result3)
    
    # 测试用例4：超长单句
    text4 = "这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。"
    result4 = truncate_by_sentences(text4, 20)
    print("测试4:", result4)

    text5 = "这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。这是一个非常长的句子，它包含了很多内容，需要被分割成多个部分，以确保每个部分都不会超过字符限制。"
    result5 = truncate_by_sentences(text5, 200)
    print("测试5:", result5)
    print(len(result5[0]))

# 运行测试
if __name__ == "__main__":
    test_truncate_function()
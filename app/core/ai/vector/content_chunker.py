# app/core/ai/vector/content_chunker.py
import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class ContentChunker:
    """
    负责将长文本内容分割成适合输入 AI 模型的较小块。
    实现了基本的按段落、句子分割，并处理重叠。
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        初始化分块器。

        Args:
            chunk_size: 每个块的最大字符数。
            chunk_overlap: 相邻块之间的重叠字符数。
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("重叠大小 (chunk_overlap) 必须小于块大小 (chunk_size)。")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        logger.debug(f"ContentChunker 初始化: chunk_size={self.chunk_size}, chunk_overlap={self.chunk_overlap}")

    def chunk_text(self, text: str) -> List[str]:
        """
        将文本分割成块。
        尝试按段落和句子边界分割，如果仍然过长，则硬性分割。

        Args:
            text: 需要分割的原始文本。

        Returns:
            分割后的文本块列表。
        """
        if not text:
            return []

        final_chunks: List[str] = []
        # 1. 初始按段落分割 (\n\n)
        # 使用 lookbehind 和 lookahead 来保留分隔符，但 re.split 可能不完美处理所有边缘情况
        # 更简单的方式是 split 然后再 join
        # paragraphs = re.split(r'(\n\s*\n)', text) # 这会包含分隔符
        paragraphs = text.split('\n\n') # 按双换行分割
        paragraphs = [p.strip() for p in paragraphs if p.strip()] # 去除空段落

        current_chunk = ""

        for i, paragraph in enumerate(paragraphs):
            paragraph_len = len(paragraph)

            if not paragraph: continue

            # 如果当前块为空，或者加上新段落（和分隔符）不超过大小限制
            # +2 是为了段落间的 \n\n
            if not current_chunk or (len(current_chunk) + paragraph_len + (2 if current_chunk else 0) <= self.chunk_size):
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
            else:
                # 当前块已满或加入新段落会超长
                # 如果当前块不为空，先处理当前块
                if current_chunk:
                    # 如果 current_chunk 本身就超长，需要先分割它
                    if len(current_chunk) > self.chunk_size:
                        final_chunks.extend(self._split_long_text(current_chunk))
                    else:
                        final_chunks.append(current_chunk)

                    # 开始新的块，考虑重叠
                    # 从上一个块的末尾取 overlap 个字符
                    overlap_part = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_part + "\n\n" + paragraph # 开始新块，带上重叠和新段落
                    # 如果新块（带重叠）又超长了，立刻分割
                    if len(current_chunk) > self.chunk_size:
                         final_chunks.extend(self._split_long_text(current_chunk))
                         current_chunk = "" # 分割后清空
                    # 否则，继续累加

                else:
                     # 如果当前块是空的，说明单个段落就超长了
                     final_chunks.extend(self._split_long_text(paragraph))
                     current_chunk = "" # 分割后清空


        # 处理最后一个累加的块
        if current_chunk:
            if len(current_chunk) > self.chunk_size:
                final_chunks.extend(self._split_long_text(current_chunk))
            else:
                final_chunks.append(current_chunk)

        # 进一步检查是否有块仍然超长（硬分割可能产生）
        # 并确保块之间有必要的重叠（如果硬分割发生）
        # 这个逻辑比较复杂，上面的实现可能不够完美，特别是重叠部分
        # 可以考虑 LangChain 或 LlamaIndex 的成熟文本分割器实现
        # 这里提供一个简化版的后处理，合并太短的块，再次分割太长的块

        merged_chunks = self._merge_short_chunks(final_chunks, self.chunk_size // 2) # 合并小于一半大小的块
        final_processed_chunks = []
        for chunk in merged_chunks:
             if len(chunk) > self.chunk_size:
                  final_processed_chunks.extend(self._split_long_text(chunk, hard_split=True))
             elif chunk: # 确保非空
                  final_processed_chunks.append(chunk)


        logger.info(f"文本分块完成，原始长度 {len(text)}, 分割为 {len(final_processed_chunks)} 块。")
        return final_processed_chunks

    def _split_long_text(self, text: str, hard_split: bool = False) -> List[str]:
        """
        将过长的文本块进一步分割。
        优先按句子分割，如果句子仍然过长或 hard_split=True，则按字符硬分割。
        """
        if not text: return []

        sentences = re.split(r'(?<=[.?!。？！])\s+', text) # 按常见句子结束符分割
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            sentence_len = len(sentence)
            if not sentence: continue

            # 如果句子本身超长，或需要硬分割
            if hard_split or sentence_len > self.chunk_size:
                # 先把当前累加的块加入结果
                if current_chunk:
                    chunks.append(current_chunk)
                    # 获取重叠部分用于下一个硬分割块的开始
                    overlap_part = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                    current_chunk = "" # 清空累加块
                else:
                     overlap_part = "" # 如果没有累加块，重叠为空

                # 硬分割这个长句子/文本
                start = 0
                while start < sentence_len:
                    # 第一次分割时加上上一个块的重叠
                    prefix = overlap_part if start == 0 and overlap_part else ""
                    # 计算本次能取的长度，需要减去前缀长度
                    remaining_len = self.chunk_size - len(prefix)
                    if remaining_len <= 0: # 如果重叠部分就超长了，只取 chunk_size
                         prefix = prefix[-self.chunk_overlap:] # 缩短重叠
                         remaining_len = self.chunk_size - len(prefix)
                         if remaining_len <= 0: # 极端情况
                              prefix = ""
                              remaining_len = self.chunk_size

                    end = start + remaining_len
                    # 如果不是最后一块，尝试在末尾加入重叠部分给下一块
                    # 但硬分割的重叠比较难处理，简单起见，按固定步长移动
                    # 步长 = chunk_size - overlap
                    step = self.chunk_size - self.chunk_overlap
                    if step <= 0: step = self.chunk_size # 防止步长为0或负

                    # 取子串
                    sub_chunk = prefix + sentence[start:min(end, sentence_len)]
                    if sub_chunk: # 确保非空
                         chunks.append(sub_chunk)

                    # 为下一次硬分割准备重叠
                    if end < sentence_len: # 如果句子还没完
                        overlap_part = sub_chunk[-self.chunk_overlap:] if len(sub_chunk) > self.chunk_overlap else sub_chunk
                    else: # 句子完了
                         overlap_part = "" # 不再需要重叠

                    start += step # 移动起始位置
                current_chunk = "" # 硬分割后清空累加

            # 如果句子不超长，尝试加入当前块
            elif not current_chunk or (len(current_chunk) + sentence_len + 1 <= self.chunk_size): # +1 for space
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                # 当前块已满，将当前块加入结果
                chunks.append(current_chunk)
                # 开始新块，考虑重叠
                overlap_part = current_chunk[-self.chunk_overlap:]
                current_chunk = overlap_part + " " + sentence # 开始新块
                # 检查新块（带重叠）是否超长
                if len(current_chunk) > self.chunk_size:
                     # 如果是，说明重叠+新句子超长，需要硬分割 current_chunk
                     chunks.extend(self._split_long_text(current_chunk, hard_split=True))
                     current_chunk = "" # 分割后清空


        # 加入最后一个累加的块
        if current_chunk:
             if len(current_chunk) > self.chunk_size:
                  chunks.extend(self._split_long_text(current_chunk, hard_split=True))
             else:
                  chunks.append(current_chunk)

        return chunks

    def _merge_short_chunks(self, chunks: List[str], min_chunk_size: int) -> List[str]:
        """合并过短的文本块 (简单的实现)"""
        if not chunks: return []

        merged: List[str] = []
        buffer = ""
        for chunk in chunks:
            if not chunk: continue

            # 如果 buffer 为空，直接放入
            if not buffer:
                 buffer = chunk
            # 如果 buffer + chunk 不超过大小限制，则合并
            elif len(buffer) + len(chunk) + 2 <= self.chunk_size: # +2 for \n\n
                 buffer += "\n\n" + chunk
            # 如果合并会超长，或者当前 chunk 本身就比 min_size 大
            elif len(chunk) >= min_chunk_size:
                 # 先将 buffer 加入结果
                 if buffer: merged.append(buffer)
                 # 当前 chunk 作为一个新块
                 buffer = chunk
            else: # 合并超长，但当前 chunk 太短，尝试合并到 buffer
                 buffer += "\n\n" + chunk # 强制合并，后续会被再次分割

        # 加入最后的 buffer
        if buffer: merged.append(buffer)

        return merged

# --- 简单的 C# ChunkText 逻辑复刻 (按段落优先) ---
# 这个版本更接近 C# 的实现逻辑，但可能不如上面的健壮
class SimpleChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        if not text: return []
        chunks = []
        current_pos = 0
        text_len = len(text)

        while current_pos < text_len:
            end_pos = min(current_pos + self.chunk_size, text_len)
            chunk = text[current_pos:end_pos]

            # 如果不是最后一块，并且长度足够，尝试回溯找到合适的断句点
            if end_pos < text_len and len(chunk) > self.chunk_overlap:
                # 优先找段落 (\n\n)
                last_para_break = chunk.rfind('\n\n', self.chunk_overlap)
                if last_para_break != -1:
                    end_pos = current_pos + last_para_break + 2 # 包含换行符
                    chunk = text[current_pos:end_pos]
                else:
                    # 其次找句子结束符
                    # 需要考虑中英文标点
                    sentence_ends = ['.', '!', '?', '。', '！', '？', '\n']
                    best_break = -1
                    # 从 chunk_overlap 之后开始找，到末尾
                    for i in range(len(chunk) - 1, self.chunk_overlap -1, -1):
                        if chunk[i] in sentence_ends:
                             # 找到断点后，确保后面是空白符或结束，避免断在中间
                             if i + 1 < len(chunk) and chunk[i+1].isspace():
                                 best_break = i + 1 # 包含标点
                                 break
                             elif i + 1 == len(chunk): # 句末
                                  best_break = i + 1
                                  break
                    if best_break != -1:
                        end_pos = current_pos + best_break
                        chunk = text[current_pos:end_pos]

            # 确保 chunk 不为空
            if chunk.strip():
                chunks.append(chunk.strip())

            # 计算下一次的起始位置，考虑重叠
            # 移动步长 = 当前块长 - 重叠部分
            # 但如果块很短（例如最后一块），不能移动过多
            step = max(len(chunk) - self.chunk_overlap, self.chunk_overlap // 2) # 保证最小移动量
            if step <= 0: step = len(chunk) # 如果块比重叠还小

            current_pos += step
            # 防止死循环
            if step == 0:
                 logger.warning("分块步长为0，可能导致死循环，强制前进。")
                 current_pos += 1

        return chunks
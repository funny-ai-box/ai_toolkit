import pandas as pd
import numpy as np
import csv
import re
import os
import json
import datetime
from typing import List, Tuple, Optional, Dict, Any
import logging

from app.core.ai.chat.base import IChatAIService
from app.modules.tools.dataanalysis.models import TableColumn

class FileParserService:
    """文件解析服务实现"""
    
    def __init__(self, ai_service: IChatAIService):
        """
        初始化文件解析服务
        
        Args:
            ai_service: AI服务
        """
        self.ai_service = ai_service

    
    async def parse_excel_file_async(self, file_path: str, sheet_index: int = 0) -> Tuple[List[TableColumn], pd.DataFrame]:
        """
        解析Excel文件
        
        Args:
            file_path: 文件路径
            sheet_index: 工作表索引
        
        Returns:
            列信息和数据
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"找不到指定的Excel文件: {file_path}")
        
        # 尝试读取Excel文件
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_index)
        except Exception as ex:
            print(f"读取Excel文件失败: {file_path}, 错误: {str(ex)}")
            raise ValueError(f"读取Excel文件失败: {str(ex)}")
        
        # 处理空数据
        if df.empty:
            raise ValueError("Excel文件没有数据")
        
        # 获取列信息
        columns_list = []
        
        # 分析前5行数据来确定数据类型
        sample_rows = min(5, len(df))
        sample_data = df.head(sample_rows)
        
        # 处理每一列
        for i, col_name in enumerate(df.columns):
            # 确保列名不为空
            original_name = str(col_name).strip()
            if not original_name:
                original_name = f"Column_{i + 1}"
            
            # 推断数据类型
            data_type = self._infer_data_type(df, col_name)
            
            # 创建列信息对象
            column = TableColumn(
                original_name=original_name,
                english_name=f"col_{i + 1}",  # 临时英文名，后面会通过AI重命名
                description=original_name,
                data_type=data_type,
                column_index=i
            )
            
            columns_list.append(column)
        
        # 使用AI转换列名
        columns_list = await self.translate_column_names_async(columns_list)
        
        # 更新DataFrame的列名
        df.columns = [col.english_name for col in columns_list]
        
        return columns_list, df
    
    async def parse_csv_file_async(self, file_path: str) -> Tuple[List[TableColumn], pd.DataFrame]:
        """
        解析CSV文件
        
        Args:
            file_path: 文件路径
        
        Returns:
            列信息和数据
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"找不到指定的CSV文件: {file_path}")
        
        # 尝试读取CSV文件
        try:
            # 先尝试检测编码和分隔符
            encoding = 'utf-8'  # 默认编码
            
            # 尝试确定分隔符
            with open(file_path, 'r', encoding=encoding) as f:
                sample = f.read(1024)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
            
            # 读取CSV文件
            df = pd.read_csv(file_path, encoding=encoding, delimiter=delimiter)
        except Exception as ex:
            # 如果失败，尝试其他常见编码和分隔符
            try:
                # 尝试使用其他编码
                encodings = ['utf-8-sig', 'latin1', 'gbk', 'gb2312', 'big5']
                delimiters = [',', ';', '\t', '|']
                
                for enc in encodings:
                    for delim in delimiters:
                        try:
                            df = pd.read_csv(file_path, encoding=enc, delimiter=delim)
                            # 如果成功，则跳出循环
                            break
                        except:
                            continue
                    if 'df' in locals():
                        break
            except Exception as ex2:
                print(f"读取CSV文件失败: {file_path}, 错误: {str(ex2)}")
                raise ValueError(f"读取CSV文件失败: {str(ex2)}")
        
        # 处理空数据
        if df.empty:
            raise ValueError("CSV文件没有数据")
        
        # 获取列信息
        columns_list = []
        
        # 处理每一列
        for i, col_name in enumerate(df.columns):
            # 确保列名不为空
            original_name = str(col_name).strip()
            if not original_name:
                original_name = f"Column_{i + 1}"
            
            # 推断数据类型
            data_type = self._infer_data_type(df, col_name)
            
            # 创建列信息对象
            column = TableColumn(
                original_name=original_name,
                english_name=f"col_{i + 1}",  # 临时英文名，后面会通过AI重命名
                description=original_name,
                data_type=data_type,
                column_index=i
            )
            
            columns_list.append(column)
        
        # 使用AI转换列名
        columns_list = await self.translate_column_names_async(columns_list)
        
        # 更新DataFrame的列名
        df.columns = [col.english_name for col in columns_list]
        
        return columns_list, df
    
    async def translate_column_names_async(self, columns: List[TableColumn]) -> List[TableColumn]:
        """
        使用AI转换列名
        
        Args:
            columns: 原始列信息列表
        
        Returns:
            转换后的列信息列表
        """
        try:
            # 构建提示词
            prompt = "我需要将以下中文列名转换为合适的英文数据库列名（小写字母，下划线分隔）。请分析每个列的含义，并给出最合适的英文名称和描述。\n\n列信息：\n"
            
            # 添加列信息
            for column in columns:
                prompt += f"- {column.original_name} (数据类型: {column.data_type})\n"
            
            # 请求格式示例
            prompt += """
            请以JSON数组形式返回结果，每个列包含original_name和english_name字段：
            [
                {"original_name": "原始列名1", "english_name": "english_column_name1"},
                {"original_name": "原始列名2", "english_name": "english_column_name2"}
            ]
            
            要求：
            1. english_name必须是有效的MySQL列名，只包含小写字母、数字和下划线
            2. 英文名应该言简意赅，符合英文命名习惯
            3. 对于数字列名，需转换为更有语义的名称
            """
            
            # 调用AI服务
            ai_messages = [
                {"role": "system", "content": "你是一个专业的数据库命名专家。"},
                {"role": "user", "content": prompt}
            ]
            response = await self.ai_service.chat_completion_async(ai_messages)
            
            try:
                # 提取JSON部分 (AI回复可能包含额外文本)
                json_str = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
                if json_str:
                    json_str = json_str.group(0)
                else:
                    json_str = response
                
                # 解析结果
                translated_columns = json.loads(json_str)
                
                # 更新列信息
                for column in columns:
                    for translated in translated_columns:
                        if translated.get("original_name") == column.original_name:
                            english_name = translated.get("english_name")
                            if english_name:
                                column.english_name = self._clean_column_name(english_name)
                                break
            except Exception as ex:
                print(f"解析AI响应失败: {str(ex)}")
                # 如果解析失败，使用默认命名规则
                for column in columns:
                    column.english_name = self._clean_column_name(column.original_name)
        except Exception as ex:
            print(f"调用AI转换列名失败: {str(ex)}")
            # 使用默认命名规则
            for column in columns:
                column.english_name = self._clean_column_name(column.original_name)
        
        # 确保所有列名唯一
        self._ensure_unique_column_names(columns)
        
        return columns
    
    def _infer_data_type(self, df: pd.DataFrame, column_name: str) -> str:
        """
        推断数据类型
        
        Args:
            df: DataFrame
            column_name: 列名
        
        Returns:
            数据类型
        """
        # 获取列数据
        col_data = df[column_name]
        
        # 检查是否所有值都是空值
        if col_data.isna().all():
            return "string"
        
        # 获取非空值
        non_na_values = col_data.dropna()
        if len(non_na_values) == 0:
            return "string"
        
        # 检查是否可以转换为日期
        try:
            pd.to_datetime(non_na_values)
            return "date"
        except:
            pass
        
        # 检查是否是整数
        if pd.api.types.is_integer_dtype(non_na_values):
            return "integer"
        
        # 检查是否可以转换为整数
        try:
            # 如果所有非空值都可以转换为整数
            if all(float(x).is_integer() for x in non_na_values if pd.notna(x)):
                return "integer"
        except:
            pass
        
        # 检查是否是浮点数
        if pd.api.types.is_float_dtype(non_na_values):
            return "float"
        
        # 检查是否可以转换为浮点数
        try:
            non_na_values.astype(float)
            return "float"
        except:
            pass
        
        # 检查是否是布尔值
        if pd.api.types.is_bool_dtype(non_na_values):
            return "boolean"
        
        # 检查是否只包含"是/否"或"真/假"或"0/1"
        if set(non_na_values.astype(str).str.lower().unique()).issubset({'0', '1', 'true', 'false', '是', '否', 'yes', 'no', 'y', 'n', 't', 'f'}):
            return "boolean"
        
        # 默认为字符串
        return "string"
    
    def _clean_column_name(self, column_name: str) -> str:
        """
        清理列名，使其符合SQL列名规范
        
        Args:
            column_name: 列名
        
        Returns:
            清理后的列名
        """
        # 替换空格和特殊字符为下划线
        result = ""
        for c in str(column_name).lower():
            if c.isalnum():
                result += c
            else:
                result += '_'
        
        # 确保不以数字开头
        if result and result[0].isdigit():
            result = 'c_' + result
        
        # 确保不为空
        if not result:
            result = 'column'
        
        # 去除多余的下划线
        result = re.sub(r'_+', '_', result)
        result = result.strip('_')
        
        return result
    
    def _ensure_unique_column_names(self, columns: List[TableColumn]) -> None:
        """
        确保所有列名唯一
        
        Args:
            columns: 列信息列表
        """
        seen_names = {}
        
        for column in columns:
            base_name = column.english_name
            
            # 如果列名已存在
            if base_name in seen_names:
                # 添加索引后缀
                counter = seen_names[base_name]
                column.english_name = f"{base_name}_{counter}"
                seen_names[base_name] = counter + 1
            else:
                seen_names[base_name] = 1
import json
from typing import Dict, List, Any, Optional

from app.modules.tools.dataanalysis.dtos import (
    EChartsConfig,
    TableConfig
)
from app.core.exceptions import BusinessException

class VisualizationExecutor:
    """可视化执行器类"""
    
    @staticmethod
    def fill_table(table_config: TableConfig, result: List[Dict[str, Any]]) -> None:
        """
        填充表格的数据
        
        Args:
            table_config: 表格配置对象
            result: SQL 查询结果
        """
        columns = []
        rows = []
        
        # 若没有行，columns无法初始化
        for row in result:
            if not columns:  # 第一次，拿columns
                columns = list(row.keys())
            
            row_data = []
            for col in columns:
                row_data.append(row.get(col, None))
            rows.append(row_data)
        
        if table_config.config:
            table_config.config.columns = columns
            table_config.config.rows = rows
    
    @staticmethod
    def fill_echarts_data(echarts_config: EChartsConfig, result: List[Dict[str, Any]]) -> None:
        """
        填充 ECharts 配置，根据不同类型正确处理数据
        
        Args:
            echarts_config: ECharts 配置对象
            result: SQL 查询结果
        """
        if not echarts_config.type:
            return
            
        chart_type = echarts_config.type.lower()
        
        if chart_type in ["line", "bar"]:
            VisualizationExecutor._fill_line_or_bar_chart(echarts_config, result)
        elif chart_type == "pie":
            VisualizationExecutor._fill_pie_chart(echarts_config, result)
        elif chart_type == "scatter":
            VisualizationExecutor._fill_scatter_chart(echarts_config, result)
        else:
            raise BusinessException(f"暂不支持的图表类型: {chart_type}")
    
    @staticmethod
    def _fill_line_or_bar_chart(echarts_config: EChartsConfig, result: List[Dict[str, Any]]) -> None:
        """
        填充折线图或柱状图的数据
        
        Args:
            echarts_config: ECharts 配置对象
            result: SQL 查询结果
        """
        if not echarts_config.data_format:
            return
            
        x_axis_field = echarts_config.data_format.x_axis
        series_mapping = echarts_config.data_format.series
        
        if not x_axis_field or not series_mapping or not echarts_config.config:
            return
        
        # 填充 xAxis 数据
        if echarts_config.config.x_axis:
            x_axis_data = [row.get(x_axis_field, "") for row in result]
            echarts_config.config.x_axis.data = x_axis_data
        
        # 填充 series 数据
        if not echarts_config.config.series:
            return
            
        for series in echarts_config.config.series:
            if not series.name or series.name not in series_mapping:
                continue
                
            field = series_mapping.get(series.name)
            data_list = []
            
            for row in result:
                if field in row:
                    value = row[field]
                    
                    # 尝试转换数字类型
                    try:
                        if isinstance(value, str):
                            if '.' in value:
                                value = float(value)
                            else:
                                value = int(value)
                    except (ValueError, TypeError):
                        pass
                        
                    data_list.append(value)
                else:
                    data_list.append(0)
            
            series.data = data_list
    
    @staticmethod
    def _fill_pie_chart(echarts_config: EChartsConfig, result: List[Dict[str, Any]]) -> None:
        """
        填充饼图的数据
        
        Args:
            echarts_config: ECharts 配置对象
            result: SQL 查询结果
        """
        if not echarts_config.data_format:
            return
            
        series_mapping = echarts_config.data_format.series
        x_axis_field = echarts_config.data_format.x_axis
        
        if not series_mapping or not x_axis_field or not echarts_config.config or not echarts_config.config.series:
            return
        
        for series in echarts_config.config.series:
            if not series.name or series.name not in series_mapping:
                continue
                
            val_field = series_mapping.get(series.name)
            data_list = []
            
            for row in result:
                name_val = row.get(x_axis_field, "unknown")
                value_val = 0.0
                
                if val_field in row:
                    try:
                        value_val = float(row[val_field])
                    except (ValueError, TypeError):
                        pass
                
                data_list.append({
                    "name": name_val,
                    "value": value_val
                })
            
            series.data = data_list
    
    @staticmethod
    def _fill_scatter_chart(echarts_config: EChartsConfig, result: List[Dict[str, Any]]) -> None:
        """
        填充散点图的数据
        
        Args:
            echarts_config: ECharts 配置对象
            result: SQL 查询结果
        """
        if not echarts_config.data_format:
            return
            
        series_mapping = echarts_config.data_format.series
        
        if not series_mapping or not echarts_config.config or not echarts_config.config.series:
            return
        
        for series in echarts_config.config.series:
            if not series.name or series.name not in series_mapping:
                continue
                
            # 获取映射字段
            field_str = series_mapping.get(series.name)
            if not field_str:
                continue
                
            fields = field_str.split(',')
            if len(fields) < 2:
                continue
            
            # 清理字段名（去除空格）
            x_field = fields[0].strip()
            y_field = fields[1].strip()
            
            # 构造散点数据
            data_list = []
            
            for row in result:
                # 尝试获取x和y坐标值
                try:
                    x_val = float(row.get(x_field, 0))
                except (ValueError, TypeError):
                    x_val = 0
                    
                try:
                    y_val = float(row.get(y_field, 0))
                except (ValueError, TypeError):
                    y_val = 0
                
                data_list.append([x_val, y_val])
            
            series.data = data_list


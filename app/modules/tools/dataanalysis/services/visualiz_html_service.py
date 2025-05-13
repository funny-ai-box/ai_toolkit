import json
from typing import Any, Dict, List, Optional
import textwrap

from app.modules.tools.dataanalysis.models import Visualization
from app.modules.tools.dataanalysis.dtos import SqlQueryDto

class VisualizHtmlService:
    """可视化Html的生成服务"""
    
    @staticmethod
    def generate_html_content(visualization: Visualization, sql_result: str) -> str:
        """
        生成HTML内容
        
        Args:
            visualization: 可视化配置实体
            sql_result: SQL查询结果（JSON字符串）
        
        Returns:
            HTML内容
        """
        # 根据可视化类型生成不同的HTML
        chart_init_code = ""
        
        # 获取可视化类型
        vis_type = visualization.visualization_type.lower() if visualization.visualization_type else "table"
        
        if vis_type in ["line", "bar", "pie", "scatter"]:
            chart_init_code = VisualizHtmlService._generate_echarts_code(visualization, sql_result)
        elif vis_type == "table":
            chart_init_code = VisualizHtmlService._generate_table_code(visualization, sql_result)
        else:
            raise ValueError(f"不支持的可视化类型: {vis_type}")
        
        # 生成HTML模板
        return textwrap.dedent(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>数据可视化</title>
            <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.0/dist/echarts.min.js"></script>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    color: #333;
                    background-color: #f8f9fa;
                }}
                #chart-container {{
                    width: 100%;
                    height: 600px;
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
                    overflow: hidden;
                    margin-bottom: 20px;
                }}
                .header {{
                    padding: 15px 20px;
                    background-color: #f5f7f9;
                    border-bottom: 1px solid #e9ecef;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .header h2 {{
                    margin: 0;
                    font-size: 18px;
                    font-weight: 500;
                }}
                .error {{
                    color: #721c24;
                    background-color: #f8d7da;
                    border: 1px solid #f5c6cb;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 15px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                    background-color: white;
                    border-radius: 4px;
                    overflow: hidden;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
                }}
                th, td {{
                    border: 1px solid #e9ecef;
                    padding: 12px 15px;
                    text-align: left;
                }}
                th {{
                    background-color: #f8f9fa;
                    border-bottom: 2px solid #dee2e6;
                    font-weight: 600;
                }}
                tr:nth-child(even) {{
                    background-color: #f9fafb;
                }}
                tr:hover {{
                    background-color: #f0f4f8;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>数据可视化: {visualization.visualization_type}</h2>
                <div>ID: {visualization.id}</div>
            </div>
            <div id="chart-container"></div>
            <div id="error-container" class="error" style="display: none;"></div>
            <script>
                try {{
                    {chart_init_code}
                }} catch (error) {{
                    // 显示错误信息
                    const errorContainer = document.getElementById('error-container');
                    errorContainer.style.display = 'block';
                    errorContainer.innerHTML = '<strong>错误:</strong> ' + error.message;
                    console.error('可视化渲染错误:', error);
                }}
            </script>
        </body>
        </html>
        """)
    
    @staticmethod
    def _generate_echarts_code(visualization: Visualization, sql_result: str) -> str:
        """
        生成ECharts初始化代码
        
        Args:
            visualization: 可视化配置实体
            sql_result: SQL查询结果
        
        Returns:
            ECharts初始化代码
        """
        return textwrap.dedent("""
        // 初始化ECharts实例
        var chart = echarts.init(document.getElementById('chart-container'));
        
        // 查询结果数据
        var sqlData = """ + sql_result + """;
        
        // 可视化配置
        var chartConfig = """ + visualization.chart_config + """;
        
        // 数据格式化处理
        try {
            // 根据可视化类型处理数据
            if (chartConfig.dataFormat) {
                // 这里根据不同图表类型应用数据
                if (chartConfig.type === 'line' || chartConfig.type === 'bar') {
                    // 处理折线图或柱状图
                    if (chartConfig.dataFormat.xAxis && chartConfig.dataFormat.series) {
                        // 设置X轴数据
                        chartConfig.config.xAxis.data = getDataByFields(sqlData, chartConfig.dataFormat.xAxis);
                        
                        // 设置系列数据
                        for (var i = 0; i < chartConfig.config.series.length; i++) {
                            var seriesName = chartConfig.config.series[i].name;
                            if (chartConfig.dataFormat.series[seriesName]) {
                                chartConfig.config.series[i].data = getDataByFields(sqlData, chartConfig.dataFormat.series[seriesName]);
                            }
                        }
                    }
                } else if (chartConfig.type === 'pie') {
                    // 处理饼图
                    if (chartConfig.dataFormat.series) {
                        for (var i = 0; i < chartConfig.config.series.length; i++) {
                            chartConfig.config.series[i].data = transformDataForPie(sqlData, chartConfig.dataFormat.series);
                        }
                    }
                } else if (chartConfig.type === 'scatter') {
                    // 处理散点图
                    if (chartConfig.dataFormat.series) {
                        for (var i = 0; i < chartConfig.config.series.length; i++) {
                            var seriesName = chartConfig.config.series[i].name;
                            if (chartConfig.dataFormat.series[seriesName]) {
                                chartConfig.config.series[i].data = getScatterData(sqlData, chartConfig.dataFormat.series[seriesName]);
                            }
                        }
                    }
                }
            }
        } catch (e) {
            console.error('数据处理错误:', e);
            document.getElementById('chart-container').innerHTML = '<div style="color:red;padding:20px;">' + 
                '<h3>数据处理错误</h3><p>' + e.message + '</p>' +
                '<p>请检查可视化配置和SQL查询结果是否匹配</p></div>';
        }
        
        // 设置配置项和数据
        chart.setOption(chartConfig.config);
        
        // 适应容器大小变化
        window.addEventListener('resize', function() {
            chart.resize();
        });
        
        // 辅助函数: 根据字段名从SQL数据中提取数据
        function getDataByFields(data, fields) {
            if (typeof fields === 'string') {
                // 单个字段
                return data.map(function(item) {
                    return item[fields];
                });
            } else if (Array.isArray(fields)) {
                // 多个字段
                return fields.map(function(field) {
                    return data.map(function(item) {
                        return item[field];
                    });
                });
            }
            return [];
        }
        
        // 辅助函数: 为饼图转换数据
        function transformDataForPie(data, seriesConfig) {
            var result = [];
            if (seriesConfig.name && seriesConfig.value) {
                // 名称和值字段
                data.forEach(function(item) {
                    result.push({
                        name: item[seriesConfig.name],
                        value: item[seriesConfig.value]
                    });
                });
            }
            return result;
        }
        
        // 辅助函数: 获取散点图数据
        function getScatterData(data, fields) {
            var result = [];
            if (fields.length >= 2) {
                data.forEach(function(item) {
                    var point = [];
                    for (var i = 0; i < fields.length; i++) {
                        point.push(item[fields[i]]);
                    }
                    result.push(point);
                });
            }
            return result;
        }
        """)
    
    @staticmethod
    def _generate_table_code(visualization: Visualization, sql_result: str) -> str:
        """
        生成表格HTML代码
        
        Args:
            visualization: 可视化配置实体
            sql_result: SQL查询结果
        
        Returns:
            表格HTML代码
        """
        return textwrap.dedent("""
        // 查询结果数据
        var sqlData = """ + sql_result + """;
        
        // 可视化配置
        var tableConfig = """ + visualization.chart_config + """;
        
        // 生成表格HTML
        var tableHtml = '';
        
        try {
            // 如果配置中指定了列和行，使用配置生成表格
            if (tableConfig.config && tableConfig.config.columns && tableConfig.config.rows) {
                tableHtml = generateConfigTable(tableConfig.config);
            } else {
                // 否则直接从SQL数据生成表格
                tableHtml = generateSqlDataTable(sqlData);
            }
            
            // 替换图表容器内容
            document.getElementById('chart-container').innerHTML = tableHtml;
        } catch (e) {
            console.error('表格生成错误:', e);
            document.getElementById('chart-container').innerHTML = '<div style="color:red;padding:20px;">' + 
                '<h3>表格生成错误</h3><p>' + e.message + '</p>' +
                '<p>请检查可视化配置和SQL查询结果是否有效</p></div>';
        }
        
        // 辅助函数: 使用配置生成表格
        function generateConfigTable(config) {
            var html = '<table>';
            
            // 添加表头
            html += '<tr>';
            config.columns.forEach(function(column) {
                html += '<th>' + column + '</th>';
            });
            html += '</tr>';
            
            // 添加数据行
            config.rows.forEach(function(row) {
                html += '<tr>';
                row.forEach(function(cell) {
                    html += '<td>' + (cell !== null ? cell : '') + '</td>';
                });
                html += '</tr>';
            });
            
            html += '</table>';
            return html;
        }
        
        // 辅助函数: 从SQL数据直接生成表格
        function generateSqlDataTable(data) {
            if (!data || !data.length) {
                return '<p>无数据可显示</p>';
            }
            
            var html = '<table>';
            
            // 添加表头
            html += '<tr>';
            Object.keys(data[0]).forEach(function(key) {
                html += '<th>' + key + '</th>';
            });
            html += '</tr>';
            
            // 添加数据行
            data.forEach(function(row) {
                html += '<tr>';
                Object.keys(row).forEach(function(key) {
                    var value = row[key];
                    html += '<td>' + (value !== null ? value : '') + '</td>';
                });
                html += '</tr>';
            });
            
            html += '</table>';
            return html;
        }
        """)
    
    @staticmethod
    def generate_html_content_from_query(sql_query: SqlQueryDto, sql_result: str) -> str:
        """
        根据SQL查询DTO生成HTML内容
        
        Args:
            sql_query: SQL查询DTO
            sql_result: SQL查询结果（JSON字符串）
        
        Returns:
            HTML内容
        """
        # 构建可视化对象
        visualization = Visualization(
            id=0,
            sql_execution_id=0,
            visualization_type=sql_query.type,
            chart_config=json.dumps(sql_query.echarts.__dict__ if sql_query.echarts else sql_query.table.__dict__),
            html_path=""
        )
        
        return VisualizHtmlService.generate_html_content(visualization, sql_result)
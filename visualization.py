"""
視覺化模組 - 使用 Plotly 生成互動式圖表 (v3.1 - 修正版)
✅ 修正 add_vline 的 datetime 錯誤
✅ 改用 add_shape + add_annotation 組合
✅ 優化圖表可讀性
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional, Any

from config import TIMEZONE


# ==================== 🎨 配色方案 ====================

# 深色主題配色
DARK_THEME = {
    'plot_bgcolor': '#0f172a',      # 深藍灰色背景
    'paper_bgcolor': '#1e293b',     # 紙張背景
    'grid_color': 'rgba(148, 163, 184, 0.2)',  # 網格線
    'text_color': '#f1f5f9',        # 主要文字（淺色）
    'title_color': '#60a5fa',       # 標題顏色（亮藍）
    'annotation_bg': 'rgba(30, 41, 59, 0.95)',  # 註解背景
    'annotation_border': '#475569'   # 註解邊框
    }

# 狀態顏色（高對比版本）
STATUS_COLORS = {
    '現靠': 'rgb(34, 197, 94)',      # 綠色
    '接靠': 'rgb(59, 130, 246)',     # 藍色
    '移泊': 'rgb(245, 158, 11)',     # 橘色
    '其他': 'rgb(156, 163, 175)'     # 灰色
    }

# ==================== 時間解析 ====================

def parse_datetime(dt_value):
    """
    安全解析日期時間
    
    Args:
        dt_value: 日期時間值（可能是 str, datetime, None）
    
    Returns:
        datetime 物件或 None
    """
    if dt_value is None or dt_value == '' or dt_value == '[無資料]':
        return None
    
    if isinstance(dt_value, datetime):
        if dt_value.tzinfo is None:
            return pytz.timezone(TIMEZONE).localize(dt_value)
        return dt_value
    
    if isinstance(dt_value, str):
        try:
            if 'T' in dt_value:
                dt = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            else:
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y/%m/%d %H:%M']:
                    try:
                        dt = datetime.strptime(dt_value, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return None
            
            if dt.tzinfo is None:
                dt = pytz.timezone(TIMEZONE).localize(dt)
            
            return dt
        except Exception:
            return None
    
    return None


# ==================== 泊位甘特圖 ====================

def create_berth_gantt_chart(
    berth_status: Dict[str, Any],
    eta: Optional[str] = None,
    ship_length: Optional[float] = None
) -> go.Figure:
    """
    建立泊位占用甘特圖（深色主題優化版）
    """
    if 'error' in berth_status or not berth_status.get('berths'):
        fig = go.Figure()
        fig.add_annotation(
            text=berth_status.get('error', '無泊位資料'),
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color=DARK_THEME['text_color'])
        )
        fig.update_layout(
            plot_bgcolor=DARK_THEME['plot_bgcolor'],
            paper_bgcolor=DARK_THEME['paper_bgcolor']
        )
        return fig
    
    # 準備資料
    tasks = []
    colors = []
    
    eta_dt = parse_datetime(eta) if eta else None
    check_time = berth_status.get('check_time')
    if isinstance(check_time, str):
        check_time = parse_datetime(check_time)
    
    for berth in berth_status['berths']:
        berth_code = berth['wharf_code']
        berth_name = berth['wharf_name']
        
        for vessel in berth.get('vessels', []):
            vessel_name = vessel.get('vessel_name', '[未知船舶]')
            status = vessel.get('alongside_status', '[未知狀態]')
            
            start_dt = parse_datetime(vessel.get('ata_berth') or vessel.get('eta_berth'))
            end_dt = parse_datetime(vessel.get('etd_berth'))
            
            if start_dt is None:
                continue
            
            if end_dt is None:
                end_dt = start_dt + timedelta(hours=24)
            
            # 狀態顏色（高對比）
            if '現靠' in status or '在泊' in status:
                color = STATUS_COLORS['現靠']
            elif '接靠' in status:
                color = STATUS_COLORS['接靠']
            elif '移泊' in status:
                color = STATUS_COLORS['移泊']
            else:
                color = STATUS_COLORS['其他']
            
            loa = vessel.get('loa_m', 0)
            gt = vessel.get('gt', 0)
            
            tasks.append({
                'Task': f"{berth_name}\n({berth_code})",
                'Start': start_dt,
                'Finish': end_dt,
                'Resource': f"{vessel_name}",
                'Status': status,
                'LOA': loa,
                'GT': gt,
                'Agent': vessel.get('agent', ''),
                'PrevPort': vessel.get('prev_port', ''),
                'NextPort': vessel.get('next_port', '')
            })
            colors.append(color)
    
    if not tasks:
        fig = go.Figure()
        fig.add_annotation(
            text="目前無船舶占用泊位",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color=DARK_THEME['text_color'])
        )
        fig.update_layout(
            plot_bgcolor=DARK_THEME['plot_bgcolor'],
            paper_bgcolor=DARK_THEME['paper_bgcolor']
        )
        return fig
    
    df = pd.DataFrame(tasks)
    
    # 建立甘特圖
    fig = go.Figure()
    
    for i, row in df.iterrows():
        duration = row['Finish'] - row['Start']
        
        fig.add_trace(go.Bar(
            x=[duration],
            y=[row['Task']],
            base=row['Start'],
            orientation='h',
            marker=dict(
                color=colors[i],
                line=dict(color=DARK_THEME['plot_bgcolor'], width=2)  # 深色邊框
            ),
            name=row['Resource'],
            text=f"<b>{row['Resource']}</b><br>({row['LOA']:.0f}m)",
            textposition='inside',
            textfont=dict(color='white', size=12, family='Microsoft JhengHei bold'),
            hovertemplate=(
                f"<b>🚢 {row['Resource']}</b><br><br>"
                f"<b>📍 泊位:</b> {row['Task']}<br>"
                f"<b>📏 船長:</b> {row['LOA']:.0f}m<br>"
                f"<b>⚖️ 總噸:</b> {row['GT']:,} GT<br>"
                f"<b>🔄 狀態:</b> {row['Status']}<br>"
                f"<b>🏢 代理:</b> {row['Agent']}<br>"
                f"<b>🌏 前港:</b> {row['PrevPort']}<br>"
                f"<b>🌏 次港:</b> {row['NextPort']}<br>"
                f"<b>⏰ 到港:</b> {row['Start'].strftime('%Y-%m-%d %H:%M')}<br>"
                f"<b>⏰ 離港:</b> {row['Finish'].strftime('%Y-%m-%d %H:%M')}<br>"
                "<extra></extra>"
            )
        ))
    
    # 添加 ETA 標記線
    if eta_dt:
        fig.add_shape(
            type="line",
            x0=eta_dt,
            x1=eta_dt,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="#ef4444", width=4, dash="dash")  # 亮紅色
        )
        
        fig.add_annotation(
            x=eta_dt,
            y=1,
            yref="paper",
            text=f"<b>預計到港</b><br>{eta_dt.strftime('%m/%d %H:%M')}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="#ef4444",
            ax=0,
            ay=-40,
            font=dict(color="#fecaca", size=15, family='Microsoft JhengHei bold'),
            bgcolor=DARK_THEME['annotation_bg'],
            bordercolor="#ef4444",
            borderwidth=2,
            borderpad=8
        )
    
    # 添加當前時間線
    if check_time:
        fig.add_shape(
            type="line",
            x0=check_time,
            x1=check_time,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="#a78bfa", width=4, dash="dot")  # 亮紫色
        )
        
        fig.add_annotation(
            x=check_time,
            y=0,
            yref="paper",
            text=f"<b>現在時刻</b><br>{check_time.strftime('%m/%d %H:%M')}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="#a78bfa",
            ax=0,
            ay=40,
            font=dict(color="#ddd6fe", size=15, family='Microsoft JhengHei bold'),
            bgcolor=DARK_THEME['annotation_bg'],
            bordercolor="#a78bfa",
            borderwidth=2,
            borderpad=8
        )
    
    # 更新佈局（深色主題）
    fig.update_layout(
        title={
            'text': f'🚢 {berth_status["port_name"]} 泊位占用甘特圖<br><sub>顯示各泊位船舶占用時間與重疊情況</sub>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 26, 'color': DARK_THEME['title_color'], 'family': 'Microsoft JhengHei'}
        },
        xaxis_title='<b>時間軸</b>',
        yaxis_title='<b>泊位名稱</b>',
        height=max(600, len(df['Task'].unique()) * 70),
        showlegend=False,
        hovermode='closest',
        plot_bgcolor=DARK_THEME['plot_bgcolor'],
        paper_bgcolor=DARK_THEME['paper_bgcolor'],
        font=dict(family="Microsoft JhengHei, Arial, sans-serif", size=14, color=DARK_THEME['text_color']),
        xaxis=dict(
            type='date',
            tickformat='%m/%d<br>%H:%M',
            gridcolor=DARK_THEME['grid_color'],
            showgrid=True,
            zeroline=False,
            tickfont=dict(size=13, color=DARK_THEME['text_color']),
            title_font=dict(color=DARK_THEME['text_color'])
        ),
        yaxis=dict(
            gridcolor=DARK_THEME['grid_color'],
            showgrid=True,
            zeroline=False,
            categoryorder='category ascending',
            tickfont=dict(size=14, color=DARK_THEME['text_color']),
            title_font=dict(color=DARK_THEME['text_color'])
        ),
        margin=dict(l=180, r=60, t=120, b=120)
    )
    
    # 圖表說明（深色背景）
    fig.add_annotation(
        text=(
            "📊 <b>圖表說明</b><br>"
            "• <b style='color:#22c55e'>綠色</b>：現靠/在泊船舶<br>"
            "• <b style='color:#3b82f6'>藍色</b>：接靠船舶<br>"
            "• <b style='color:#f59e0b'>橘色</b>：移泊船舶<br>"
            "• <b style='color:#ef4444'>紅色虛線</b>：預計到港時間<br>"
            "• <b style='color:#a78bfa'>紫色點線</b>：當前時間"
        ),
        xref="paper", yref="paper",
        x=0.02, y=-0.12,
        showarrow=False,
        font=dict(size=12, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
        align="left",
        bgcolor=DARK_THEME['annotation_bg'],
        bordercolor=DARK_THEME['annotation_border'],
        borderwidth=1,
        borderpad=10
    )
    
    return fig


# ==================== 泊位容量分析圖 ====================

def create_berth_capacity_chart(berth_status: Dict[str, Any]) -> go.Figure:
    """建立泊位剩餘空間視覺化圖表（深色主題優化版）"""
    if 'error' in berth_status or not berth_status.get('berths'):
        fig = go.Figure()
        fig.add_annotation(
            text=berth_status.get('error', '無泊位資料'),
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color=DARK_THEME['text_color'])
        )
        fig.update_layout(
            plot_bgcolor=DARK_THEME['plot_bgcolor'],
            paper_bgcolor=DARK_THEME['paper_bgcolor']
        )
        return fig
    
    # 準備資料
    berth_names = []
    total_lengths = []
    occupied_lengths = []
    remaining_lengths = []
    occupancy_rates = []
    vessel_counts = []
    colors = []
    
    for berth in berth_status['berths']:
        berth_name = f"{berth['wharf_name']}<br>({berth['wharf_code']})"
        
        berth_names.append(berth_name)
        total_lengths.append(berth['total_length_m'])
        occupied_lengths.append(berth['occupied_length_m'])
        remaining_lengths.append(berth['remaining_length_m'])
        occupancy_rates.append(berth['occupancy_rate'])
        vessel_counts.append(berth['vessel_count'])
        
        rate = berth['occupancy_rate']
        if rate < 50:
            colors.append('#22c55e')  # 綠色
        elif rate < 80:
            colors.append('#f59e0b')  # 橘色
        else:
            colors.append('#ef4444')  # 紅色
    
    # 建立圖表
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            '<b>泊位總長度與占用情況</b><br><sub>堆疊顯示已占用與剩餘空間</sub>',
            '<b>泊位占用率</b><br><sub>百分比顯示使用程度</sub>',
            '<b>泊位剩餘空間</b><br><sub>可供新船舶使用的長度</sub>',
            '<b>停泊船舶數</b><br><sub>各泊位當前船舶數量</sub>'
        ),
        specs=[
            [{'type': 'bar'}, {'type': 'bar'}],
            [{'type': 'bar'}, {'type': 'bar'}]
        ],
        vertical_spacing=0.18,
        horizontal_spacing=0.15
    )
    
    # 1. 堆疊柱狀圖
    fig.add_trace(
        go.Bar(
            x=berth_names,
            y=occupied_lengths,
            name='已占用長度',
            marker=dict(color='#ef4444', line=dict(color=DARK_THEME['plot_bgcolor'], width=1)),
            text=[f"<b>{val:.0f}m</b>" for val in occupied_lengths],
            textposition='inside',
            textfont=dict(color='white', size=13, family='Microsoft JhengHei bold'),
            hovertemplate="<b>%{x}</b><br>已占用: <b>%{y:.0f}m</b><extra></extra>"
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=berth_names,
            y=remaining_lengths,
            name='剩餘空間',
            marker=dict(color='#22c55e', line=dict(color=DARK_THEME['plot_bgcolor'], width=1)),
            text=[f"<b>{val:.0f}m</b>" for val in remaining_lengths],
            textposition='inside',
            textfont=dict(color='white', size=13, family='Microsoft JhengHei bold'),
            hovertemplate="<b>%{x}</b><br>剩餘: <b>%{y:.0f}m</b><extra></extra>"
        ),
        row=1, col=1
    )
    
    # 2. 占用率柱狀圖
    fig.add_trace(
        go.Bar(
            x=berth_names,
            y=occupancy_rates,
            name='占用率',
            marker=dict(color=colors, line=dict(color=DARK_THEME['plot_bgcolor'], width=1)),
            text=[f"<b>{val:.1f}%</b>" for val in occupancy_rates],
            textposition='outside',
            textfont=dict(size=14, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
            hovertemplate="<b>%{x}</b><br>占用率: <b>%{y:.1f}%</b><extra></extra>"
        ),
        row=1, col=2
    )
    
    # 3. 剩餘空間柱狀圖
    fig.add_trace(
        go.Bar(
            x=berth_names,
            y=remaining_lengths,
            name='剩餘空間',
            marker=dict(
                color=remaining_lengths,
                colorscale=[[0, '#1e3a8a'], [1, '#22c55e']],  # 深藍到綠色
                showscale=False,
                line=dict(color=DARK_THEME['plot_bgcolor'], width=1)
            ),
            text=[f"<b>{val:.0f}m</b>" for val in remaining_lengths],
            textposition='outside',
            textfont=dict(size=14, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
            hovertemplate="<b>%{x}</b><br>剩餘空間: <b>%{y:.0f}m</b><extra></extra>"
        ),
        row=2, col=1
    )
    
    # 4. 船舶數柱狀圖
    fig.add_trace(
        go.Bar(
            x=berth_names,
            y=vessel_counts,
            name='船舶數',
            marker=dict(
                color=vessel_counts,
                colorscale=[[0, '#1e3a8a'], [1, '#3b82f6']],  # 深藍到亮藍
                showscale=False,
                line=dict(color=DARK_THEME['plot_bgcolor'], width=1)
            ),
            text=[f"<b>{val}</b>" for val in vessel_counts],
            textposition='outside',
            textfont=dict(size=15, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
            hovertemplate="<b>%{x}</b><br>船舶數: <b>%{y}</b><extra></extra>"
        ),
        row=2, col=2
    )
    
    # 更新佈局（深色主題）
    fig.update_layout(
        title={
            'text': f'📊 {berth_status["port_name"]} 泊位容量分析<br><sub>綜合評估各泊位使用狀況與剩餘空間</sub>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 26, 'color': DARK_THEME['title_color'], 'family': 'Microsoft JhengHei'}
        },
        height=900,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=14, family='Microsoft JhengHei', color=DARK_THEME['text_color'])
        ),
        plot_bgcolor=DARK_THEME['plot_bgcolor'],
        paper_bgcolor=DARK_THEME['paper_bgcolor'],
        font=dict(family="Microsoft JhengHei, Arial, sans-serif", size=13, color=DARK_THEME['text_color']),
        barmode='stack'
    )
    
    # 更新子圖軸（深色主題）
    for row in [1, 2]:
        for col in [1, 2]:
            fig.update_xaxes(
                tickangle=-45,
                tickfont=dict(size=12, color=DARK_THEME['text_color']),
                gridcolor=DARK_THEME['grid_color'],
                row=row, col=col
            )
            fig.update_yaxes(
                gridcolor=DARK_THEME['grid_color'],
                tickfont=dict(color=DARK_THEME['text_color']),
                row=row, col=col
            )
    
    fig.update_yaxes(
        title_text="<b>長度 (m)</b>",
        title_font=dict(color=DARK_THEME['text_color']),
        row=1, col=1
    )
    fig.update_yaxes(
        title_text="<b>占用率 (%)</b>",
        range=[0, 110],
        title_font=dict(color=DARK_THEME['text_color']),
        row=1, col=2
    )
    fig.update_yaxes(
        title_text="<b>長度 (m)</b>",
        title_font=dict(color=DARK_THEME['text_color']),
        row=2, col=1
    )
    fig.update_yaxes(
        title_text="<b>船舶數</b>",
        title_font=dict(color=DARK_THEME['text_color']),
        row=2, col=2
    )
    
    # 圖表說明（深色背景）
    fig.add_annotation(
        text=(
            "📊 <b>圖表意義</b><br>"
            "• <b>左上</b>：顯示各泊位總長度中，已被船舶占用與剩餘的空間比例<br>"
            "• <b>右上</b>：以百分比呈現泊位使用率，<b style='color:#22c55e'>綠色</b>(<50%) / "
            "<b style='color:#f59e0b'>橘色</b>(50-80%) / <b style='color:#ef4444'>紅色</b>(>80%)<br>"
            "• <b>左下</b>：顯示各泊位剩餘可用長度，協助評估新船舶靠泊可能性<br>"
            "• <b>右下</b>：統計各泊位當前停泊船舶數量，評估泊位繁忙程度"
        ),
        xref="paper", yref="paper",
        x=0.5, y=-0.08,
        showarrow=False,
        font=dict(size=12, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
        align="center",
        bgcolor=DARK_THEME['annotation_bg'],
        bordercolor=DARK_THEME['annotation_border'],
        borderwidth=1,
        borderpad=10
    )
    
    return fig


# ==================== 競爭分析圖 ====================

def create_competition_chart(
    timeline: Dict[str, Any],
    eta: str,
    competition_window_minutes: int = 60
) -> go.Figure:
    """建立進港競合程度分析圖（深色主題優化版）"""
    eta_dt = parse_datetime(eta)
    if eta_dt is None:
        fig = go.Figure()
        fig.add_annotation(
            text="無效的 ETA 時間",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color=DARK_THEME['text_color'])
        )
        fig.update_layout(
            plot_bgcolor=DARK_THEME['plot_bgcolor'],
            paper_bgcolor=DARK_THEME['paper_bgcolor']
        )
        return fig
    
    time_range_start = eta_dt - timedelta(hours=12)
    time_range_end = eta_dt + timedelta(hours=12)
    
    time_points = []
    current_time = time_range_start
    
    while current_time <= time_range_end:
        time_points.append(current_time)
        current_time = current_time + timedelta(minutes=15)
    
    competition_counts = []
    
    for time_point in time_points:
        count = 0
        window_start = time_point - timedelta(minutes=competition_window_minutes)
        window_end = time_point + timedelta(minutes=competition_window_minutes)
        
        for vessel in timeline.get('vessels', []):
            vessel_eta = parse_datetime(vessel.get('start_time'))
            
            if vessel_eta:
                if window_start <= vessel_eta <= window_end:
                    count += 1
        
        competition_counts.append(count)
    
    if not time_points or not competition_counts:
        fig = go.Figure()
        fig.add_annotation(
            text="無競合資料",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color=DARK_THEME['text_color'])
        )
        fig.update_layout(
            plot_bgcolor=DARK_THEME['plot_bgcolor'],
            paper_bgcolor=DARK_THEME['paper_bgcolor']
        )
        return fig
    
    time_points_str = [t.strftime('%Y-%m-%d %H:%M:%S') for t in time_points]
    eta_str_formatted = eta_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 建立圖表
    fig = go.Figure()
    
    # 添加競合程度曲線（高對比配色）
    fig.add_trace(go.Scatter(
        x=time_points_str,
        y=competition_counts,
        mode='lines+markers',
        name='競合船舶數',
        line=dict(color='#60a5fa', width=4),  # 亮藍色
        marker=dict(size=10, symbol='circle', color='#3b82f6', line=dict(width=2, color='white')),
        fill='tozeroy',
        fillcolor='rgba(96, 165, 250, 0.3)',
        hovertemplate=(
            "<b>⏰ 時間:</b> %{x}<br>"
            "<b>🚢 競合船舶數:</b> %{y}<br>"
            "<extra></extra>"
        )
    ))
    
    # 添加 ETA 標記線
    fig.add_shape(
        type="line",
        x0=eta_str_formatted,
        x1=eta_str_formatted,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color="#ef4444", width=4, dash="dash")
    )
    
    fig.add_annotation(
        x=eta_str_formatted,
        y=1,
        yref="paper",
        text=f"<b>預計到港</b><br>{eta_dt.strftime('%m/%d %H:%M')}",
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=2,
        arrowcolor="#ef4444",
        ax=0,
        ay=-40,
        font=dict(color="#fecaca", size=16, family='Microsoft JhengHei bold'),
        bgcolor=DARK_THEME['annotation_bg'],
        bordercolor="#ef4444",
        borderwidth=2,
        borderpad=8
    )
    
    # 找出競爭最低的時間點
    if competition_counts:
        min_competition = min(competition_counts)
        min_index = competition_counts.index(min_competition)
        min_time_str = time_points_str[min_index]
        min_time = time_points[min_index]
        
        fig.add_shape(
            type="line",
            x0=min_time_str,
            x1=min_time_str,
            y0=0,
            y1=1,
            yref="paper",
            line=dict(color="#22c55e", width=4, dash="dot")
        )
        
        fig.add_annotation(
            x=min_time_str,
            y=0,
            yref="paper",
            text=f"<b>最佳時段</b><br>{min_time.strftime('%m/%d %H:%M')}<br>競合數: {min_competition}",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="#22c55e",
            ax=0,
            ay=40,
            font=dict(color="#bbf7d0", size=14, family='Microsoft JhengHei bold'),
            bgcolor=DARK_THEME['annotation_bg'],
            bordercolor="#22c55e",
            borderwidth=2,
            borderpad=8
        )
    
    # 更新佈局（深色主題）
    fig.update_layout(
        title={
            'text': f'📈 進港競合程度分析（時窗: ±{competition_window_minutes}分鐘）<br><sub>評估不同時段的泊位競爭強度，協助選擇最佳到港時間</sub>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 24, 'color': DARK_THEME['title_color'], 'family': 'Microsoft JhengHei'}
        },
        xaxis_title='<b>時間</b>',
        yaxis_title='<b>競合船舶數</b>',
        height=600,
        hovermode='x unified',
        plot_bgcolor=DARK_THEME['plot_bgcolor'],
        paper_bgcolor=DARK_THEME['paper_bgcolor'],
        font=dict(family="Microsoft JhengHei, Arial, sans-serif", size=14, color=DARK_THEME['text_color']),
        xaxis=dict(
            type='category',
            tickangle=-45,
            gridcolor=DARK_THEME['grid_color'],
            showgrid=True,
            tickmode='linear',
            tick0=0,
            dtick=8,
            tickfont=dict(size=12, color=DARK_THEME['text_color']),
            title_font=dict(color=DARK_THEME['text_color'])
        ),
        yaxis=dict(
            gridcolor=DARK_THEME['grid_color'],
            showgrid=True,
            rangemode='tozero',
            tickfont=dict(size=13, color=DARK_THEME['text_color']),
            title_font=dict(color=DARK_THEME['text_color'])
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=14, family='Microsoft JhengHei', color=DARK_THEME['text_color'])
        ),
        margin=dict(l=80, r=60, t=140, b=120)
    )
    
    # 圖表說明（深色背景）
    fig.add_annotation(
        text=(
            "📊 <b>圖表意義</b><br>"
            "• <b style='color:#60a5fa'>藍色曲線</b>：顯示各時段預計進港船舶數量，曲線越高表示競爭越激烈<br>"
            "• <b style='color:#ef4444'>紅色虛線</b>：您的預計到港時間 (ETA)<br>"
            "• <b style='color:#22c55e'>綠色點線</b>：競爭最低的時段，建議優先考慮此時段到港<br>"
            "• <b>應用建議</b>：選擇曲線低谷時段到港可降低等待時間，提高靠泊效率"
        ),
        xref="paper", yref="paper",
        x=0.5, y=-0.18,
        showarrow=False,
        font=dict(size=12, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
        align="center",
        bgcolor=DARK_THEME['annotation_bg'],
        bordercolor=DARK_THEME['annotation_border'],
        borderwidth=1,
        borderpad=10
    )
    
    return fig


# ==================== 船舶長度分布圖 ====================

def create_ship_length_distribution(
    d005_df: pd.DataFrame,
    d003_df: pd.DataFrame,
    d004_df: pd.DataFrame
) -> Optional[go.Figure]:
    """建立船舶長度分布圖（深色主題優化版）"""
    all_lengths = []
    all_statuses = []
    
    for df, status in [(d005_df, '在泊'), (d003_df, '進港'), (d004_df, '出港')]:
        if not df.empty and 'loa_m' in df.columns:
            lengths = pd.to_numeric(df['loa_m'], errors='coerce').dropna()
            all_lengths.extend(lengths.tolist())
            all_statuses.extend([status] * len(lengths))
    
    if not all_lengths:
        return None
    
    df = pd.DataFrame({
        'length': all_lengths,
        'status': all_statuses
    })
    
    # 建立圖表
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            '<b>船舶長度分布（直方圖）</b><br><sub>顯示不同長度區間的船舶數量</sub>',
            '<b>船舶長度分布（箱型圖）</b><br><sub>統計分析船長的分布特徵</sub>'
        ),
        specs=[[{'type': 'histogram'}, {'type': 'box'}]],
        horizontal_spacing=0.15
    )
    
    colors = {
        '在泊': '#22c55e',
        '進港': '#3b82f6',
        '出港': '#f59e0b'
    }
    
    # 直方圖
    for status in ['在泊', '進港', '出港']:
        status_data = df[df['status'] == status]['length']
        if len(status_data) > 0:
            fig.add_trace(
                go.Histogram(
                    x=status_data,
                    name=status,
                    marker=dict(
                        color=colors[status],
                        line=dict(color=DARK_THEME['plot_bgcolor'], width=2)
                    ),
                    opacity=0.8,
                    nbinsx=25,
                    hovertemplate=(
                        f"<b>{status}</b><br>"
                        "船長範圍: <b>%{x}</b><br>"
                        "船舶數: <b>%{y}</b><br>"
                        "<extra></extra>"
                    )
                ),
                row=1, col=1
            )
    
    # 箱型圖
    for status in ['在泊', '進港', '出港']:
        status_data = df[df['status'] == status]['length']
        if len(status_data) > 0:
            fig.add_trace(
                go.Box(
                    y=status_data,
                    name=status,
                    marker=dict(color=colors[status]),
                    boxmean='sd',
                    hovertemplate=(
                        f"<b>{status}</b><br>"
                        "最大值: <b>%{y:.0f}m</b><br>"
                        "<extra></extra>"
                    )
                ),
                row=1, col=2
            )
    
    # 更新佈局（深色主題）
    fig.update_layout(
        title={
            'text': '📏 船舶長度分布分析<br><sub>統計港口內不同狀態船舶的長度分布情況</sub>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 24, 'color': DARK_THEME['title_color'], 'family': 'Microsoft JhengHei'}
        },
        height=600,
        barmode='overlay',
        plot_bgcolor=DARK_THEME['plot_bgcolor'],
        paper_bgcolor=DARK_THEME['paper_bgcolor'],
        font=dict(family="Microsoft JhengHei, Arial, sans-serif", size=14, color=DARK_THEME['text_color']),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=14, family='Microsoft JhengHei', color=DARK_THEME['text_color'])
        ),
        margin=dict(l=80, r=60, t=140, b=120)
    )
    
    fig.update_xaxes(
        title_text="<b>船長 (公尺)</b>",
        tickfont=dict(size=13, color=DARK_THEME['text_color']),
        title_font=dict(color=DARK_THEME['text_color']),
        gridcolor=DARK_THEME['grid_color'],
        row=1, col=1
    )
    fig.update_yaxes(
        title_text="<b>船舶數量</b>",
        tickfont=dict(size=13, color=DARK_THEME['text_color']),
        title_font=dict(color=DARK_THEME['text_color']),
        gridcolor=DARK_THEME['grid_color'],
        row=1, col=1
    )
    fig.update_yaxes(
        title_text="<b>船長 (公尺)</b>",
        tickfont=dict(size=13, color=DARK_THEME['text_color']),
        title_font=dict(color=DARK_THEME['text_color']),
        gridcolor=DARK_THEME['grid_color'],
        row=1, col=2
    )
    
    # 圖表說明（深色背景）
    fig.add_annotation(
        text=(
            "📊 <b>圖表意義</b><br>"
            "• <b>左側直方圖</b>：顯示不同長度區間的船舶數量分布，可快速了解港口船舶尺寸結構<br>"
            "• <b>右側箱型圖</b>：統計分析包含中位數、四分位數、極值等，評估船長分布的集中與離散程度<br>"
            "• <b>應用價值</b>：協助評估泊位規劃是否符合實際船舶尺寸需求，優化泊位配置策略"
        ),
        xref="paper", yref="paper",
        x=0.5, y=-0.15,
        showarrow=False,
        font=dict(size=12, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
        align="center",
        bgcolor=DARK_THEME['annotation_bg'],
        bordercolor=DARK_THEME['annotation_border'],
        borderwidth=1,
        borderpad=10
    )
    
    return fig


# ==================== 港口摘要儀表板（深色優化版）====================

def create_port_summary_dashboard(berth_status: Dict[str, Any]) -> go.Figure:
    """建立港口摘要儀表板（深色主題優化版）"""
    if 'error' in berth_status:
        fig = go.Figure()
        fig.add_annotation(
            text=berth_status.get('error', '無資料'),
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color=DARK_THEME['text_color'])
        )
        fig.update_layout(
            plot_bgcolor=DARK_THEME['plot_bgcolor'],
            paper_bgcolor=DARK_THEME['paper_bgcolor']
        )
        return fig
    
    summary = berth_status['summary']
    
    # 建立儀表板
    fig = make_subplots(
        rows=2, cols=2,
        specs=[
            [{'type': 'indicator'}, {'type': 'indicator'}],
            [{'type': 'indicator'}, {'type': 'indicator'}]
        ],
        subplot_titles=(
            '<b>總泊位數</b><br><sub>港口總泊位數量</sub>',
            '<b>可用泊位</b><br><sub>當前可供使用的泊位</sub>',
            '<b>停泊船舶</b><br><sub>目前在港船舶總數</sub>',
            '<b>平均占用率</b><br><sub>整體泊位使用程度</sub>'
        ),
        vertical_spacing=0.25,
        horizontal_spacing=0.15
    )
    
    # 總泊位數
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=summary['total_berths'],
            number={'font': {'size': 70, 'color': DARK_THEME['text_color'], 'family': 'Microsoft JhengHei'}},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=1, col=1
    )
    
    # 可用泊位
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=summary['available_berths'],
            delta={
                'reference': summary['total_berths'],
                'relative': False,
                'valueformat': '.0f',
                'font': {'size': 24, 'color': '#bbf7d0'}
            },
            number={'font': {'size': 70, 'color': DARK_THEME['text_color'], 'family': 'Microsoft JhengHei'}},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=1, col=2
    )
    
    # 停泊船舶
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=summary['total_vessels'],
            number={'font': {'size': 70, 'color': '#3b82f6', 'family': 'Arial Black'}},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=2, col=1
    )
    
    # 平均占用率
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=summary['avg_occupancy_rate'],
            number={'suffix': "%", 'font': {'size': 50, 'family': 'Arial Black', 'color': DARK_THEME['text_color']}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "#60a5fa", 'tickfont': {'color': DARK_THEME['text_color']}},
                'bar': {'color': "#60a5fa", 'thickness': 0.8},
                'bgcolor': DARK_THEME['plot_bgcolor'],
                'borderwidth': 3,
                'bordercolor': "#475569",
                'steps': [
                    {'range': [0, 50], 'color': "rgba(34, 197, 94, 0.3)"},
                    {'range': [50, 80], 'color': "rgba(245, 158, 11, 0.3)"},
                    {'range': [80, 100], 'color': "rgba(239, 68, 68, 0.3)"}
                ],
                'threshold': {
                    'line': {'color': "#ef4444", 'width': 5},
                    'thickness': 0.8,
                    'value': 90
                }
            },
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=2, col=2
    )
    
    # 更新佈局（深色主題）
    fig.update_layout(
        title={
            'text': f'📊 {berth_status["port_name"]} 港口摘要<br><sub>即時港口營運關鍵指標總覽</sub>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 28, 'color': DARK_THEME['title_color'], 'family': 'Microsoft JhengHei'}
        },
        height=700,
        paper_bgcolor=DARK_THEME['paper_bgcolor'],
        font=dict(family="Microsoft JhengHei, Arial, sans-serif", size=15, color=DARK_THEME['text_color']),
        margin=dict(l=60, r=60, t=140, b=100)
    )
    
    # 更新子標題顏色
    for annotation in fig['layout']['annotations']:
        annotation['font'] = dict(size=14, color=DARK_THEME['text_color'], family='Microsoft JhengHei')
    
    # 圖表說明（深色背景）
    fig.add_annotation(
        text=(
            "📊 <b>指標說明</b><br>"
            "• <b>總泊位數</b>：港口可供船舶停靠的泊位總數<br>"
            "• <b>可用泊位</b>：當前無船舶占用、可立即使用的泊位數量（負值表示超額使用）<br>"
            "• <b>停泊船舶</b>：目前在港內各泊位停靠的船舶總數<br>"
            "• <b>平均占用率</b>：所有泊位的平均使用率，<b style='color:#22c55e'>綠色</b>(<50%) 表示充裕、"
            "<b style='color:#f59e0b'>黃色</b>(50-80%) 表示適中、<b style='color:#ef4444'>紅色</b>(>80%) 表示擁擠"
        ),
        xref="paper", yref="paper",
        x=0.5, y=-0.08,
        showarrow=False,
        font=dict(size=12, family='Microsoft JhengHei', color=DARK_THEME['text_color']),
        align="center",
        bgcolor=DARK_THEME['annotation_bg'],
        bordercolor=DARK_THEME['annotation_border'],
        borderwidth=1,
        borderpad=10
    )
    
    return fig


# ==================== 港口摘要儀表板 ====================

def create_port_summary_dashboard(berth_status: Dict[str, Any]) -> go.Figure:
    """
    建立港口摘要儀表板（增強版）
    
    Args:
        berth_status: get_berth_status() 的返回值
    
    Returns:
        Plotly Figure 物件
    """
    if 'error' in berth_status:
        fig = go.Figure()
        fig.add_annotation(
            text=berth_status.get('error', '無資料'),
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="gray")
        )
        return fig
    
    summary = berth_status['summary']
    
    # 建立儀表板
    fig = make_subplots(
        rows=2, cols=2,
        specs=[
            [{'type': 'indicator'}, {'type': 'indicator'}],
            [{'type': 'indicator'}, {'type': 'indicator'}]
        ],
        subplot_titles=(
            '<b>總泊位數</b><br><sub>港口總泊位數量</sub>',
            '<b>可用泊位</b><br><sub>當前可供使用的泊位</sub>',
            '<b>停泊船舶</b><br><sub>目前在港船舶總數</sub>',
            '<b>平均占用率</b><br><sub>整體泊位使用程度</sub>'
        ),
        vertical_spacing=0.25,
        horizontal_spacing=0.15
    )
    
    # 總泊位數
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=summary['total_berths'],
            number={'font': {'size': 70, 'color': '#0052a3', 'family': 'Arial Black'}},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=1, col=1
    )
    
    # 可用泊位
    delta_value = summary['available_berths'] - summary['total_berths']
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=summary['available_berths'],
            delta={
                'reference': summary['total_berths'],
                'relative': False,
                'valueformat': '.0f',
                'font': {'size': 24}
            },
            number={'font': {'size': 70, 'color': 'rgb(34, 197, 94)', 'family': 'Arial Black'}},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=1, col=2
    )
    
    # 停泊船舶
    fig.add_trace(
        go.Indicator(
            mode="number",
            value=summary['total_vessels'],
            number={'font': {'size': 70, 'color': 'rgb(59, 130, 246)', 'family': 'Arial Black'}},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=2, col=1
    )
    
    # 平均占用率
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=summary['avg_occupancy_rate'],
            number={'suffix': "%", 'font': {'size': 50, 'family': 'Arial Black'}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "darkblue"},
                'bar': {'color': "darkblue", 'thickness': 0.8},
                'bgcolor': DARK_THEME['annotation_bg'],
                'borderwidth': 3,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 50], 'color': "rgba(34, 197, 94, 0.3)"},
                    {'range': [50, 80], 'color': "rgba(245, 158, 11, 0.3)"},
                    {'range': [80, 100], 'color': "rgba(239, 68, 68, 0.3)"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 5},
                    'thickness': 0.8,
                    'value': 90
                }
            },
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=2, col=2
    )
    
    # 更新佈局
    fig.update_layout(
        title={
            'text': f'📊 {berth_status["port_name"]} 港口摘要<br><sub>即時港口營運關鍵指標總覽</sub>',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 28, 'color': '#0052a3', 'family': 'Microsoft JhengHei'}
        },
        height=700,
        paper_bgcolor= DARK_THEME['annotation_bg'],
        font=dict(family="Microsoft JhengHei, Arial, sans-serif", size=14),
        margin=dict(l=60, r=60, t=140, b=100)
    )
    
    # 圖表說明
    fig.add_annotation(
        text=(
            "📊 <b>指標說明</b><br>"
            "• <b>總泊位數</b>：港口可供船舶停靠的泊位總數<br>"
            "• <b>可用泊位</b>：當前無船舶占用、可立即使用的泊位數量（負值表示超額使用）<br>"
            "• <b>停泊船舶</b>：目前在港內各泊位停靠的船舶總數<br>"
            "• <b>平均占用率</b>：所有泊位的平均使用率，<b style='color:rgb(34,197,94)'>綠色</b>(<50%) 表示充裕、"
            "<b style='color:rgb(245,158,11)'>黃色</b>(50-80%) 表示適中、<b style='color:rgb(239,68,68)'>紅色</b>(>80%) 表示擁擠"
        ),
        xref="paper", yref="paper",
        x=0.5, y=-0.08,
        showarrow=False,
        font=dict(size=11, family='Microsoft JhengHei'),
        align="center",
        bgcolor= DARK_THEME['annotation_bg'],
        bordercolor="#cbd5e1",
        borderwidth=1,
        borderpad=8
    )
    
    return fig


def create_error_figure(message: str) -> go.Figure:
    """建立錯誤訊息圖表（深色主題）"""
    fig = go.Figure()
    fig.add_annotation(
        text=f"⚠️ {message}",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=22, color="#fca5a5", family="Microsoft JhengHei")
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=400,
        plot_bgcolor=DARK_THEME['plot_bgcolor'],
        paper_bgcolor=DARK_THEME['paper_bgcolor']
    )
    return fig


# ==================== 測試程式 ====================


if __name__ == "__main__":
    print("=== 視覺化模組測試 v3.2 (深色主題優化版) ===\n")
    print("✅ 修正背景過亮問題")
    print("✅ 提升文字對比度")
    print("✅ 優化配色方案")
    print("✅ 深色主題一致性")
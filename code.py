# -----------------------------------------------------------------
# NBA 球員數據儀表板 (Streamlit App) v2.0
# 修正：全中文化 (包含位置、年資)、球隊篩選、生涯數據視覺化
# -----------------------------------------------------------------
import streamlit as st
import pandas as pd
import plotly.express as px 
from datetime import datetime
from nba_api.stats.static import players, teams 
from nba_api.stats.endpoints import (
    commonplayerinfo,
    playercareerstats,
    playerawards,
    scoreboardv2,  
    commonallplayers 
)

# ====================================================================
# 0. 全域變數與設定
# ====================================================================
st.set_page_config(
    page_title="NBA 球員數據儀表板 (Pro)",
    page_icon="🏀",
    layout="wide"
)

# 球隊中文對照表 (擴充歷史球隊)
TEAM_ABBR_TO_ZH = {
    # 現役球隊
    'ATL': '亞特蘭大 老鷹', 'BOS': '波士頓 賽爾提克', 'BKN': '布魯克林 籃網', 'CHA': '夏洛特 黃蜂', 
    'CHI': '芝加哥 公牛', 'CLE': '克里夫蘭 騎士', 'DAL': '達拉斯 獨行俠', 'DEN': '丹佛 金塊', 
    'DET': '底特律 活塞', 'GSW': '金州 勇士', 'HOU': '休士頓 火箭', 'IND': '印第安納 溜馬', 
    'LAC': '洛杉磯 快艇', 'LAL': '洛杉磯 湖人', 'MEM': '曼菲斯 灰熊', 'MIA': '邁阿密 熱火', 
    'MIL': '密爾瓦基 公鹿', 'MIN': '明尼蘇達 灰狼', 'NOP': '紐奧良 鵜鶘', 'NYK': '紐約 尼克', 
    'OKC': '奧克拉荷馬雷霆', 'ORL': '奧蘭多 魔術', 'PHI': '費城 76人', 'PHX': '鳳凰城 太陽', 
    'POR': '波特蘭 拓荒者', 'SAC': '沙加緬度 國王', 'SAS': '聖安東尼奧 馬刺', 'TOR': '多倫多 暴龍', 
    'UTA': '猶他 爵士', 'WAS': '華盛頓 巫師',
    'TOT': '多隊',
    
    # 歷史/更名球隊
    'NJN': '紐澤西 籃網', 'SEA': '西雅圖 超音速', 'NOH': '紐奧良 黃蜂', 'NOK': '紐奧良/奧克拉荷馬市 黃蜂',
    'CHH': '夏洛特 黃蜂 (舊)', 'VAN': '溫哥華 灰熊', 'WSB': '華盛頓 子彈', 'SDC': '聖地牙哥 快艇',
    'KCK': '堪薩斯城 國王', 'GOS': '金州 勇士 (舊)' 
}

# ====================================================================
# 2. 數據獲取與處理的核心邏輯
# ====================================================================

@st.cache_data
def get_player_id(player_name):
    """根據球員姓名查找其唯一的 Player ID"""
    try:
        nba_players = players.get_players()
        player_info = [
            player for player in nba_players
            if player['full_name'].lower() == player_name.lower()
        ]
        return player_info[0]['id'] if player_info else None
    except Exception:
        return None

def get_precise_positions(generic_position, translate_to_zh=False):
    """將 NBA API 返回的通用位置轉換為所有精確位置。"""
    position_map = {
        'Guard': ['PG', 'SG'], 'Forward': ['SF', 'PF'], 'Center': ['C'],
        'G-F': ['PG', 'SG', 'SF'], 'F-G': ['SG', 'SF', 'PF'], 'F-C': ['SF', 'PF', 'C'],
        'C-F': ['PF', 'C', 'SF'], 'G': ['PG', 'SG'], 'F': ['SF', 'PF'], 'C': ['C'],
    }
    positions = position_map.get(generic_position)
    
    if positions:
        if translate_to_zh:
            zh_map = {
                'PG': '控球後衛', 'SG': '得分後衛', 'SF': '小前鋒', 
                'PF': '大前鋒', 'C': '中鋒'
            }
            translated_positions = [zh_map.get(p, p) for p in positions]
            return ", ".join(translated_positions)
        return ", ".join(positions)

    if translate_to_zh:
        zh_generic_map = {
            'Forward': '前鋒', 'Guard': '後衛', 'Center': '中鋒',
            'G-F': '後衛-前鋒', 'F-G': '前鋒-後衛', 'F-C': '前鋒-中鋒',
            'C-F': '中鋒-前鋒', 'G': '後衛', 'F': '前鋒', 'C': '中鋒'
        }
        return zh_generic_map.get(generic_position, generic_position)
        
    return generic_position

def analyze_style(stats, position):
    """根據場均數據和位置，生成簡單的球員風格分析。"""
    try:
        pts = float(stats.get('pts', 0))
        ast = float(stats.get('ast', 0))
        reb = float(stats.get('reb', 0))
    except ValueError:
        return {'core_style': '數據不足', 'simple_rating': '請嘗試查詢有數據的賽季。'}

    HIGH_PTS, HIGH_AST, HIGH_REB = 25, 8, 10
    core_style, simple_rating = "角色球員", "可靠的輪換球員。"

    if pts >= HIGH_PTS and ast >= 6 and reb >= 6:
        core_style = "🌟 頂級全能巨星 (Elite All-Around Star)"
        simple_rating = "集得分、組織和籃板於一身的劃時代球員。"
    elif pts >= HIGH_PTS:
        core_style = "得分機器 (Volume Scorer)"
        simple_rating = "聯盟頂級的得分手，能夠在任何位置取分。"
    elif ast >= HIGH_AST and pts >= 15:
        core_style = "🎯 組織大師 (Playmaking Maestro)"
        simple_rating = "以傳球優先的組織核心，同時具備可靠的得分能力。"
    elif reb >= HIGH_REB and pts < 15:
        core_style = "🧱 籃板/防守支柱 (Rebounding/Defense Anchor)"
        simple_rating = "內線防守和籃板的專家，隊伍的堅實後盾。"
    else:
        core_style = "角色球員 (Role Player)"
        simple_rating = "一名可靠的輪換球員。"

    return {'core_style': core_style, 'simple_rating': simple_rating}

@st.cache_data
def get_all_players_static():
    """獲取所有 NBA 球員的靜態列表 (含退役)"""
    nba_players = players.get_players()
    player_df = pd.DataFrame(nba_players)
    player_df = player_df[['full_name', 'id']]
    player_df.columns = ['姓名', '球員ID']
    return player_df

@st.cache_data(ttl=3600)
def get_active_players_dataset():
    """獲取當季所有現役球

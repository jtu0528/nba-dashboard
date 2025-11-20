# -----------------------------------------------------------------
# NBA 球員數據儀表板 (Streamlit App)
# 結合「球探分析報告」與「原始數據瀏覽器」
# (欄位已中文化 + 新增球隊篩選 + 修正歷史球隊顯示 bug + 生涯數據視覺化)
# -----------------------------------------------------------------
import streamlit as st
import pandas as pd
import plotly.express as px # (NEW) 引入 Plotly 用於畫圖
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

# (FIX) 擴充球隊中文對照表，加入歷史球隊代碼，確保舊賽季顯示正確
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

# --- 來自「球探報告」的輔助函式 ---

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

# --- 來自「儀表板」的輔助函式 ---

@st.cache_data
def get_all_players_static():
    """獲取所有 NBA 球員的靜態列表 (含退役)"""
    nba_players = players.get_players()
    player_df = pd.DataFrame(nba_players)
    player_df = player_df[['full_name', 'id']]
    player_df.columns = ['姓名', '球員ID']
    return player_df

@st.cache_data(ttl=3600) # 緩存 1 小時
def get_active_players_dataset():
    """獲取當季所有現役球員名單 (包含球隊資訊)"""
    try:
        resp = commonallplayers.CommonAllPlayers(is_only_current_season=1)
        return resp.get_data_frames()[0]
    except Exception:
        return pd.DataFrame()

@st.cache_data
def get_nba_teams_list():
    """獲取 NBA 球隊列表並加上中文名稱"""
    nba_teams = teams.get_teams()
    df = pd.DataFrame(nba_teams)
    df['zh_name'] = df['abbreviation'].map(TEAM_ABBR_TO_ZH).fillna(df['full_name'])
    return df

@st.cache_data(ttl=300)
def get_todays_scoreboard():
    """獲取今日賽程"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        board = scoreboardv2.ScoreboardV2(game_date=today)
        games_df = board.get_data_frames()[0]
        linescore_df = board.get_data_frames()[1]
        return games_df, linescore_df
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


# --- 【核心】球探報告函式 ---
@st.cache_data
def get_player_data_package(player_name, season='2023-24'):
    """獲取並整理特定球員的所有數據。"""
    player_id = get_player_id(player_name)
    
    error_report = {
        'error': f"找不到球員：{player_name}。請檢查姓名是否正確。",
        'name': player_name, 'team_abbr': 'N/A', 'team_full': 'N/A', 'precise_positions': 'N/A', 
        'games_played': 0, 'pts': 'N/A', 'reb': 'N/A', 'ast': 'N/A', 'stl': 'N/A', 'blk': 'N/A', 'tov': 'N/A', 'ato_ratio': 'N/A', 
        'fg_pct': 'N/A', 'ft_pct': 'N/A', 'fta_per_game': 'N/A', 'min_per_game': 'N/A', 
        'trend_analysis': {'trend_status': 'N/A', 'delta_pts': 'N/A', 'delta_reb': 'N/A', 'delta_ast': 'N/A', 'delta_fg_pct': 'N/A'},
        'awards': [], 'contract_year': 'N/A', 'salary': 'N/A', 'season': season
    }
    
    if not player_id:
        return error_report, None, None, None

    try:
        info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        info_df = info.get_data_frames()[0]
        
        stats = playercareerstats.PlayerCareerStats(player_id=player_id)
        stats_data = stats.get_data_frames()[0]
        career_totals_df = stats.get_data_frames()[1]
        season_stats = stats_data[stats_data['SEASON_ID'] == season]
        
        awards = playerawards.PlayerAwards(player_id=player_id)
        awards_df = awards.get_data_frames()[0]
        
        report = {}
        generic_pos = info_df.loc[0, 'POSITION']
        report['name'] = info_df.loc[0, 'DISPLAY_FIRST_LAST']
        
        # (FIX) 處理球隊名稱：嚴格使用 season_stats 的資訊
        if not season_stats.empty:
            team_abbr_list = season_stats['TEAM_ABBREVIATION'].tolist()
            if 'TOT' in team_abbr_list:
                abbrs = [a for a in team_abbr_list if a != 'TOT']
                zh_abbrs = [TEAM_ABBR_TO_ZH.get(a, a) for a in abbrs]
                report['team_abbr'] = "多隊"
                report['team_full'] = f"效力多隊: {', '.join(zh_abbrs)}"
            else:
                abbr = team_abbr_list[0]
                report['team_abbr'] = TEAM_ABBR_TO_ZH.get(abbr, abbr)
                report['team_full'] = TEAM_ABBR_TO_ZH.get(abbr, abbr)
        else:
            # (FIX) 如果該賽季沒有數據，不要顯示現役球隊，改為明確提示
            report['team_abbr'] = "N/A"
            report['team_full'] = "無該賽季數據" 
        
        report['position'] = generic_pos 
        report['precise_positions'] = get_precise_positions(generic_pos, translate_to_zh=True)
        
        if not season_stats.empty and season_stats.iloc[-1]['GP'] > 0:
            avg_stats = season_stats.iloc[-1]
            total_gp = avg_stats['GP']
            
            report['games_played'] = int(total_gp) 
            report['pts'] = round(avg_stats['PTS'] / total_gp, 1) 
            report['reb'] = round(avg_stats['REB'] / total_gp, 1)
            report['ast'] = round(avg_stats['AST'] / total_gp, 1) 
            report['stl'] = round(avg_stats['STL'] / total_gp, 1) 
            report['blk'] = round(avg_stats['BLK'] / total_gp, 1) 
            report['tov'] = round(avg_stats['TOV'] / total_gp, 1)
            
            report['fg_pct'] = round(avg_stats['FG_PCT'] * 100, 1) 
            report['ft_pct'] = round(avg_stats['FT_PCT'] * 100, 1)
            report['fta_per_game'] = round(avg_stats['FTA'] / total_gp, 1)
            report['min_per_game'] = round(avg_stats['MIN'] / total_gp, 1) 
            
            try:
                report['ato_ratio'] = round(report['ast'] / report['tov'], 2)
            except ZeroDivisionError:
                report['ato_ratio'] = 'N/A'
            
            if not career_totals_df.empty:
                career_avg = {}
                total_gp_career = career_totals_df.loc[0, 'GP']
                
                career_avg['pts'] = round(career_totals_df.loc[0, 'PTS'] / total_gp_career, 1)
                career_avg['reb'] = round(career_totals_df.loc[0, 'REB'] / total_gp_career, 1)
                career_avg['ast'] = round(career_totals_df.loc[0, 'AST'] / total_gp_career, 1)
                career_avg['fg_pct'] = round(career_totals_df.loc[0, 'FG_PCT'] * 100, 1) 
                
                delta_pts = report['pts'] - career_avg['pts']
                delta_reb = report['reb'] - career_avg['reb']
                delta_ast = report['ast'] - career_avg['ast']
                delta_fg_pct = report['fg_pct'] - career_avg['fg_pct'] 

                if delta_pts >= 3.0 and delta_fg_pct >= -1.0:
                    trend_status = "🚀 上升期 (Significant Ascend)"
                elif delta_pts >= 3.0 and delta_fg_pct < -3.0:
                    trend_status = "🚨 數據虛胖 (Inefficient Volume)"
                elif abs(delta_pts) < 1.0 and delta_fg_pct >= 1.0:
                    trend_status = "📈 效率提升 (Efficiency Spike)"
                elif delta_pts < -3.0:
                    trend_status = "📉

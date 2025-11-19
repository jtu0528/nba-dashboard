# -----------------------------------------------------------------
# NBA 球員數據儀表板 (Streamlit App)
# 結合「球探分析報告」與「原始數據瀏覽器」
# (欄位已中文化 + 新增球隊篩選功能)
# -----------------------------------------------------------------
import streamlit as st
import pandas as pd
from datetime import datetime
from nba_api.stats.static import players, teams # (NEW) 新增 teams
from nba_api.stats.endpoints import (
    commonplayerinfo,
    playercareerstats,
    playerawards,
    scoreboardv2,  # 用於獲取「今日賽程」
    commonallplayers # (NEW) 用於獲取分隊球員名單
)

# ====================================================================
# 0. 全域變數與設定
# ====================================================================
st.set_page_config(
    page_title="NBA 球員數據儀表板 (Pro)",
    page_icon="🏀",
    layout="wide"
)

# (NEW) 將球隊中文對照表提取為全域常數，供多處使用
TEAM_ABBR_TO_ZH = {
    'ATL': '亞特蘭大 老鷹', 'BOS': '波士頓 賽爾提克', 'BKN': '布魯克林 籃網', 'CHA': '夏洛特 黃蜂', 
    'CHI': '芝加哥 公牛', 'CLE': '克里夫蘭 騎士', 'DAL': '達拉斯 獨行俠', 'DEN': '丹佛 金塊', 
    'DET': '底特律 活塞', 'GSW': '金州 勇士', 'HOU': '休士頓 火箭', 'IND': '印第安納 溜馬', 
    'LAC': '洛杉磯 快艇', 'LAL': '洛杉磯 湖人', 'MEM': '曼菲斯 灰熊', 'MIA': '邁阿密 熱火', 
    'MIL': '密爾瓦基 公鹿', 'MIN': '明尼蘇達 灰狼', 'NOP': '紐奧良 鵜鶘', 'NYK': '紐約 尼克', 
    'OKC': '奧克拉荷馬雷霆', 'ORL': '奧蘭多 魔術', 'PHI': '費城 76人', 'PHX': '鳳凰城 太陽', 
    'POR': '波特蘭 拓荒者', 'SAC': '沙加緬度 國王', 'SAS': '聖安東尼奧 馬刺', 'TOR': '多倫多 暴龍', 
    'UTA': '猶他 爵士', 'WAS': '華盛頓 巫師',
    'TOT': '多隊'
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
    # is_only_current_season=1 表示只抓現役
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
    # 使用全域字典 mapping 中文名稱
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
        
        # 使用全域 TEAM_ABBR_TO_ZH 處理球隊名稱
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
            abbr = info_df.loc[0, 'TEAM_ABBREVIATION']
            report['team_abbr'] = TEAM_ABBR_TO_ZH.get(abbr, abbr)
            report['team_full'] = TEAM_ABBR_TO_ZH.get(abbr, abbr) 
        
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
                    trend_status = "📉 下滑期 (Performance Decline)"
                else:
                    trend_status = "📊 表現波動 (Fluctuating Performance)"

                report['trend_analysis'] = {
                    'delta_pts': f"{'+' if delta_pts > 0 else ''}{round(delta_pts, 1)}",
                    'delta_reb': f"{'+' if delta_reb > 0 else ''}{round(delta_reb, 1)}",
                    'delta_ast': f"{'+' if delta_ast > 0 else ''}{round(delta_ast, 1)}",
                    'delta_fg_pct': f"{'+' if delta_fg_pct > 0 else ''}{round(delta_fg_pct, 1)}%", 
                    'trend_status': trend_status,
                }
            else:
                report['trend_analysis'] = {'trend_status': '無法計算生涯趨勢', 'delta_pts': 'N/A', 'delta_reb': 'N/A', 'delta_ast': 'N/A', 'delta_fg_pct': 'N/A'}
            
            report['contract_year'] = '數據源無法獲取'
            report['salary'] = '數據源無法獲取'
            report['season'] = season
        else:
            report.update({
                'games_played': 0, 'pts': 'N/A', 'reb': 'N/A', 'ast': 'N/A', 'stl': 'N/A', 'blk': 'N/A', 'tov': 'N/A', 'ato_ratio': 'N/A',
                'fg_pct': 'N/A', 'ft_pct': 'N/A', 'fta_per_game': 'N/A', 'min_per_game': 'N/A', 'contract_year': 'N/A', 'salary': 'N/A', 'season': f"無 {season} 賽季數據",
            })
            report['trend_analysis'] = {'trend_status': 'N/A', 'delta_pts': 'N/A', 'delta_reb': 'N/A', 'delta_ast': 'N/A', 'delta_fg_pct': 'N/A'}

        if not awards_df.empty:
            award_pairs = awards_df[['DESCRIPTION', 'SEASON']].apply(lambda x: f"{x['DESCRIPTION']} ({x['SEASON'][:4]})", axis=1).tolist()
            report['awards'] = award_pairs
        else:
            report['awards'] = []

        return report, info_df, stats_data, awards_df

    except Exception as e:
        error_report['error'] = f"數據處理失敗，詳細錯誤: {e}"
        return error_report, None, None, None


def format_report_markdown_streamlit(data):
    """Markdown 報告格式化"""
    if data.get('error'):
        return f"## ❌ 錯誤報告\n\n{data['error']}"

    style_analysis = analyze_style(data, data.get('position', 'N/A'))
    trend = data['trend_analysis']
    
    awards_list_md = '\n'.join([f"* {award}" for award in data['awards'] if award])
    if not awards_list_md:
        awards_list_md = "* 暫無官方 NBA 獎項記錄"

    # (FIX) 定義變數來儲存 LaTeX 符號，避免 f-string 中的反斜線導致 SyntaxError
    delta_sym = "$\\Delta$"

    markdown_text = f"""
## ⚡ {data['name']} ({data['team_abbr']}) 球探分析報告
**當賽季效力球隊:** **{data['team_full']}**

**📅 當賽季出場數 (GP):** **{data['games_played']}** | **🗺️ 可打位置:** **{data['precise_positions']}**

---

**⭐ 球員風格分析 (Rule-Based):**
* **核心風格:** {style_analysis['core_style']}
* **簡化評級:** {style_analysis['simple_rating']}

---

**📈 {data['season']} 賽季表現 & 生涯趨勢分析:**
* **趨勢狀態:** {trend['trend_status']}
* **得分差異 (PTS {delta_sym}):** {trend['delta_pts']} (vs. 生涯平均)
* **籃板差異 (REB {delta_sym}):** {trend['delta_reb']}
* **助攻差異 (AST {delta_sym}):** {trend['delta_ast']}
* **投籃效率差異 (FG% {delta_sym}):** {trend['delta_fg_pct']} 

---

**📊 {data['season']} 賽季平均數據:**
* 場均上場時間 (MIN): **{data['min_per_game']}**
* 場均得分 (PTS): **{data['pts']}**
* 場均籃板 (REB): **{data['reb']}**
* 場均助攻 (AST): **{data['ast']}**
* 助攻失誤比 (A/TO): **{data['ato_ratio']}**
* 投籃命中率 (FG%): **{data['fg_pct']}%**
* 罰球命中率 (FT%): **{data['ft_pct']}%**

---

**🏆 曾經得過的官方獎項 (含年份):**
{awards_list_md}
"""
    return markdown_text

# ======================================
# 4. Streamlit 界面邏輯 (UI)
# ======================================

# ----------------------------------
# 4.1 側邊欄 (Sidebar) - 輸入區
# ----------------------------------
st.sidebar.title("🏀 NBA 數據查詢")
st.sidebar.header("1. 篩選與查詢")

# (NEW) 1. 獲取球隊資料並製作下拉選單
team_df = get_nba_teams_list()
team_options = ["所有球員 (含歷史名將)"] + team_df['zh_name'].tolist()

selected_team_label = st.sidebar.selectbox(
    "篩選球隊 (選填):",
    options=team_options,
    index=0
)

# (NEW) 2. 根據選取的球隊，決定顯示哪些球員
if selected_team_label == "所有球員 (含歷史名將)":
    # 如果選「所有」，顯示原本的靜態完整名單 (含退役)
    player_df = get_all_players_static()
else:
    # 如果選特定球隊，找出 Team ID 並從現役名單中篩選
    try:
        # 從中文名稱反查 ID
        selected_team_id = team_df[team_df['zh_name'] == selected_team_label].iloc[0]['id']
        
        # 獲取所有現役球員
        active_players_df = get_active_players_dataset()
        
        if not active_players_df.empty:
            # 根據 TEAM_ID 篩選
            filtered_players = active_players_df[active_players_df['TEAM_ID'] == selected_team_id]
            
            # 整理格式以符合下拉選單需求
            player_df = pd.DataFrame({
                '姓名': filtered_players['DISPLAY_FIRST_LAST'],
                '球員ID': filtered_players['PERSON_ID']
            })
        else:
            st.sidebar.warning("無法獲取現役名單，顯示所有球員。")
            player_df = get_all_players_static()
            
    except Exception:
        st.sidebar.error("篩選球隊時發生錯誤，顯示預設名單。")
        player_df = get_all_players_static()

# 3. 球員選擇選單
selected_player_name = st.sidebar.selectbox(
    "選擇或輸入球員姓名:",
    options=player_df['姓名'],
    index=None,
    placeholder="例如: LeBron James"
)

# 4. 賽季選擇
current_year = datetime.now().year
if datetime.now().month >= 8:
    start_year = current_year
else:
    start_year = current_year - 1

seasons_list = []
for year in range(start_year, 1979, -1):
    next_year_short = str(year + 1)[-2:]
    season_str = f"{year}-{next_year_short}"
    seasons_list.append(season_str)

default_season = "2023-24"
default_index = 0
if default_season in seasons_list:
    default_index = seasons_list.index(default_season)

season_input = st.sidebar.selectbox(
    "選擇或輸入查詢賽季:",
    options=seasons_list,
    index=default_index
)

# ----------------------------------
# 4.2 主頁面 (Main Page)
# ----------------------------------
st.title("🏀 NBA 球員數據儀表板 (Pro)")

if selected_player_name and season_input:
    st.header(f"'{selected_player_name}' 的 {season_input} 數據", divider='rainbow')
    
    with st.spinner(f"正在抓取 {selected_player_name} 的 {season_input} 數據..."):
        report_data, info_df, career_df, awards_df = get_player_data_package(selected_player_name, season_input)

    tab1, tab2 = st.tabs(["📊 球探分析報告", "🗃️ 原始數據瀏覽器"])

    with tab1:
        markdown_output = format_report_markdown_streamlit(report_data)
        st.markdown(markdown_output)

    with tab2:
        st.header("原始數據瀏覽器")
        
        if info_df is not None:
            st.subheader("基本資料")
            info = info_df.iloc[0]
            
            col1, col2, col3, col4 = st.columns(4)
            
            team_display = report_data.get('team_full', 'N/A')
            current_team_abbr = info.get('TEAM_ABBREVIATION', 'N/A')
            
            if team_display == current_team_abbr:
                team_city = info.get('TEAM_CITY', '') 
                team_name = info.get('TEAM_NAME', 'N/A')
                team_display = f"{team_city} {team_name}"
            
            with col1:
                st.markdown("**球隊**")
                st.markdown(f"<p style='font-size: 1.25rem; font-weight: 600; line-height: 1.4;'>{team_display}</p>", unsafe_allow_html=True)

            position = info.get('POSITION', 'N/A')
            
            position_zh_map = {
                'Forward': '前鋒',
                'Guard': '後衛',
                'Center': '中鋒',
                'G-F': '後衛-前鋒',
                'F-G': '前鋒-後衛',
                'F-C': '前鋒-中鋒',
                'C-F': '中鋒-前鋒',
                'G': '後衛',
                'F': '前鋒',
                'C': '中鋒'
            }
            position_display = position_zh_map.get(position, position)
            
            col2.metric("位置", position_display)

            height = info.get('HEIGHT', 'N/A')
            col3.metric("身高", height)

            weight = info.get('WEIGHT_LBS') 
            if weight:
                col4.metric("體重", f"{weight} 磅")
            else:
                col4.metric("體重", "N/A")

            jersey = info.get('JERSEY')
            season_team_abbr = report_data.get('team_abbr', 'N/A')
            
            jersey_display = "N/A"
            if jersey:
                if current_team_abbr != season_team_abbr and "," not in season_team_abbr:
                     jersey_display = "N/A (歷史賽季)"
                else:
                    jersey_display = f"#{jersey}"

            with col1:
                 st.metric("球衣號碼", jersey_display)

            birthdate = info.get('BIRTHDATE') 
            if birthdate:
                date_only = birthdate.split('T')[0] 
                col2.metric("生日", date_only)
            else:
                col2.metric("生日", "N/A")

            school = info.get('SCHOOL', 'N/A')
            with col3:
                st.markdown("**經驗**")
                st.markdown(f"<p style='font-size: 1.25rem; font-weight: 600; line-height: 1.4;'>{str(school)}</p>", unsafe_allow_html=True)
            
            draft_year = info.get('DRAFT_YEAR')
            draft_number = info.get('DRAFT_NUMBER')
            draft_display = "N/A" 
            if draft_year and draft_number: 
                draft_display = f"{draft_year} 年 第 {draft_number} 順位"
            elif draft_year: 
                draft_display = f"{draft_year} 年"
            
            with col4:
                st.markdown("**選秀**")
                st.markdown(f"<p style='font-size: 1.25rem; font-weight: 600; line-height: 1.4;'>{draft_display}</p>", unsafe_allow_html=True)

        else:
            st.warning("在資料庫中找不到該球員的基本資料。")
        
        if career_df is not None:
            st.subheader("生涯逐年數據 (例行賽)")
            
            columns_to_show = [
                'SEASON_ID', 'TEAM_ABBREVIATION', 'GP', 'GS', 'MIN', 'PTS', 
                'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG_PCT', 'FG3_PCT', 'FT_PCT'
            ]
            
            display_cols = [col for col in columns_to_show if col in career_df.columns]
            display_df = career_df[display_cols].copy()
            
            column_rename_map = {
                'SEASON_ID': '賽季',
                'TEAM_ABBREVIATION': '球隊',
                'GP': '出賽',
                'GS': '先發',
                'MIN': '分鐘',
                'PTS': '得分',
                'REB': '籃板',
                'AST': '助攻',
                'STL': '抄截',
                'BLK': '阻攻',
                'TOV': '失誤',
                'FG_PCT': '投籃%',
                'FG3_PCT': '三分%',
                'FT_PCT': '罰球%'
            }
            
            display_df.rename(columns=column_rename_map, inplace=True)
            
            st.dataframe(
                display_df.sort_values('賽季', ascending=False), 
                height=350, 
                use_container_width=True
            )
        
        if awards_df is not None:
            st.subheader("生涯獎項")
            
            awards_to_show = ['DESCRIPTION', 'SEASON', 'AWARD_TYPE']
            awards_display_cols = [col for col in awards_to_show if col in awards_df.columns]
            awards_display_df = awards_df[awards_display_cols].copy()
            
            awards_display_df.rename(columns={
                'DESCRIPTION': '獎項名稱',
                'SEASON': '賽季',
                'AWARD_TYPE': '獎項類型'
            }, inplace=True)
            
            st.dataframe(
                awards_display_df, 
                height=200, 
                use_container_width=True
            )

else:
    st.info("👈 請從左側的下拉式選單中選擇一位球員，並確認查詢賽季。")


# ----------------------------------
# 4.3 今日賽程
# ----------------------------------
st.header("今日賽程表 (非即時)", divider='blue')
st.markdown("⚠️ **請注意：** 這裡的數據**不是即時的**。`nba-api` 的數據更新有嚴重延遲。")

if st.button("刷新今日賽程"):
    st.cache_data.clear()
    st.rerun()

games, line_scores = get_todays_scoreboard()

if not games.empty:
    for index, game in games.iterrows():
        home_team_id = game['HOME_TEAM_ID']
        away_team_id = game['VISITOR_TEAM_ID']
        
        home_team_score_info = line_scores[line_scores['TEAM_ID'] == home_team_id]
        away_team_score_info = line_scores[line_scores['TEAM_ID'] == away_team_id]

        if not home_team_score_info.empty and not away_team_score_info.empty:
            home_team_abbr = home_team_score_info.iloc[0]['TEAM_ABBREVIATION']
            away_team_abbr = away_team_score_info.iloc[0]['TEAM_ABBREVIATION']
            
            home_score = home_team_score_info.iloc[0].get('SCORE', 0)
            away_score = away_team_score_info.iloc[0].get('SCORE', 0)
            
            game_status = game['GAME_STATUS_TEXT']

            st.subheader(f"{away_team_abbr} @ {home_team_abbr}")
            st.markdown(f"**{away_score} - {home_score}** ({game_status})")
        
else:
    st.info("今天沒有比賽，或者 API 暫時無法連線。")

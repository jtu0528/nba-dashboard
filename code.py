# -----------------------------------------------------------------
# NBA 球員數據儀表板 (Streamlit App)
# 結合「球探分析報告」與「原始數據瀏覽器」
# -----------------------------------------------------------------
import streamlit as st
import pandas as pd
from datetime import datetime
from nba_api.stats.static import players
from nba_api.stats.endpoints import (
    commonplayerinfo,
    playercareerstats,
    playerawards,
    scoreboardv2  # 用於獲取「今日賽程」
)

# ====================================================================
# 1. 頁面設定
# ====================================================================
st.set_page_config(
    page_title="NBA 球員數據儀表板 (Pro)",
    page_icon="🏀",
    layout="wide"  # 寬版面更適合儀表板
)

# ====================================================================
# 2. 數據獲取與處理的核心邏輯 (合併版)
# ====================================================================

# --- 來自「球探報告」的輔助函式 ---

@st.cache_data
def get_player_id(player_name):
    """根據球員姓名查找其唯一的 Player ID (使用 Streamlit 緩存)"""
    try:
        nba_players = players.get_players()
        player_info = [
            player for player in nba_players
            if player['full_name'].lower() == player_name.lower()
        ]
        return player_info[0]['id'] if player_info else None
    except Exception:
        return None

def get_precise_positions(generic_position):
    """將 NBA API 返回的通用位置轉換為所有精確位置。"""
    position_map = {
        'Guard': ['PG', 'SG'], 'Forward': ['SF', 'PF'], 'Center': ['C'],
        'G-F': ['PG', 'SG', 'SF'], 'F-G': ['SG', 'SF', 'PF'], 'F-C': ['SF', 'PF', 'C'],
        'C-F': ['PF', 'C', 'SF'], 'G': ['PG', 'SG'], 'F': ['SF', 'PF'], 'C': ['C'],
    }
    positions = position_map.get(generic_position)
    if positions:
        return ", ".join(positions)
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
def get_players_list():
    """獲取所有 NBA 球員的列表 (姓名與 ID) - 用於下拉選單"""
    nba_players = players.get_players()
    player_df = pd.DataFrame(nba_players)
    player_df = player_df[['full_name', 'id']]
    player_df.columns = ['姓名', '球員ID']
    return player_df

@st.cache_data(ttl=300) # 緩存 5 分鐘
def get_todays_scoreboard():
    """獲取今日賽程 (非即時)"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        board = scoreboardv2.ScoreboardV2(game_date=today)
        games_df = board.get_data_frames()[0]
        linescore_df = board.get_data_frames()[1]
        return games_df, linescore_df
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


# --- 【核心】修改過的「球探報告」函式 ---
# 我們修改此函式，使其同時返回「報告字典」和「原始 DataFrames」
@st.cache_data
def get_player_data_package(player_name, season='2023-24'):
    """
    獲取並整理特定球員的所有數據。
    返回: (report_dict, info_df, career_df, awards_df)
    """
    player_id = get_player_id(player_name)
    
    # 預先定義好「錯誤時」的返回內容
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
        # 1. 獲取基本資訊 (用於儀表板 + 報告)
        info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        info_df = info.get_data_frames()[0]
        
        # 2. 獲取生涯數據 (用於儀表板 + 報告)
        stats = playercareerstats.PlayerCareerStats(player_id=player_id)
        stats_data = stats.get_data_frames()[0] # 逐年
        career_totals_df = stats.get_data_frames()[1] # 生涯總計
        season_stats = stats_data[stats_data['SEASON_ID'] == season]
        
        # 3. 獲取獎項資訊 (用於儀表板 + 報告)
        awards = playerawards.PlayerAwards(player_id=player_id)
        awards_df = awards.get_data_frames()[0]
        
        # --- 開始建立「報告字典」---
        report = {}
        generic_pos = info_df.loc[0, 'POSITION']
        report['name'] = info_df.loc[0, 'DISPLAY_FIRST_LAST']
        
        # 處理球隊邏輯
        if not season_stats.empty:
            team_abbr_list = season_stats['TEAM_ABBREVIATION'].tolist()
            if 'TOT' in team_abbr_list:
                abbrs = [a for a in team_abbr_list if a != 'TOT']
                report['team_abbr'] = ", ".join(abbrs)
                report['team_full'] = f"效力多隊: {report['team_abbr']}"
            else:
                report['team_abbr'] = team_abbr_list[0]
                report['team_full'] = team_abbr_list[0]
        else:
            report['team_abbr'] = info_df.loc[0, 'TEAM_ABBREVIATION']
            report['team_full'] = info_df.loc[0, 'TEAM_NAME'] 
        
        report['position'] = generic_pos 
        report['precise_positions'] = get_precise_positions(generic_pos) 
        
        # --- 場均數據計算 ---
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
            
            # 生涯趨勢分析邏輯
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

        # --- 獎項列表 (含年份) ---
        if not awards_df.empty:
            award_pairs = awards_df[['DESCRIPTION', 'SEASON']].apply(lambda x: f"{x['DESCRIPTION']} ({x['SEASON'][:4]})", axis=1).tolist()
            report['awards'] = award_pairs
        else:
            report['awards'] = []

        # 【關鍵修改】返回報告字典和原始 DataFrames
        return report, info_df, stats_data, awards_df

    except Exception as e:
        error_report['error'] = f"數據處理失敗，詳細錯誤: {e}"
        return error_report, None, None, None


# ======================================
# 3. 報告格式化與輸出 (來自球探報告)
# ======================================

def format_report_markdown_streamlit(data):
    """將整理後的數據格式化為 Markdown 報告 (Streamlit 直接渲染)"""
    if data.get('error'):
        return f"## ❌ 錯誤報告\n\n{data['error']}"

    style_analysis = analyze_style(data, data.get('position', 'N/A'))
    trend = data['trend_analysis']
    
    awards_list_md = '\n'.join([f"* {award}" for award in data['awards'] if award])
    if not awards_list_md:
        awards_list_md = "* 暫無官方 NBA 獎項記錄"

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
* **得分差異 (PTS $\Delta$):** {trend['delta_pts']} (vs. 生涯平均)
* **籃板差異 (REB $\Delta$):** {trend['delta_reb']}
* **助攻差異 (AST $\Delta$):** {trend['delta_ast']}
* **投籃效率差異 (FG% $\Delta$):** {trend['delta_fg_pct']} 

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
# 4.1 側邊欄 (Sidebar) - 用於輸入
# ----------------------------------
st.sidebar.title("🏀 NBA 數據查詢")
st.sidebar.header("1. 查詢球員數據")

# 載入球員列表 (來自儀表板)
player_df = get_players_list()

# 創建下拉式選單 (來自儀表板)
selected_player_name = st.sidebar.selectbox(
    "選擇或輸入球員姓名:",
    options=player_df['姓名'],
    index=None,  # 預設不選中任何球員
    placeholder="例如: LeBron James"
)

# 賽季輸入 (來自球探報告)
season_input = st.sidebar.text_input("輸入查詢賽季 (格式 YYYY-YY):", value="2023-24")

# ----------------------------------
# 4.2 主頁面 (Main Page) - 用於顯示
# ----------------------------------
st.title("🏀 NBA 球員數據儀表板 (Pro)")

if selected_player_name and season_input:
    # --- 如果用戶選擇了球員 ---
    st.header(f"'{selected_player_name}' 的 {season_input} 數據", divider='rainbow')
    
    # 1. 【關鍵】一次性獲取所有數據
    with st.spinner(f"正在抓取 {selected_player_name} 的 {season_input} 數據..."):
        report_data, info_df, career_df, awards_df = get_player_data_package(selected_player_name, season_input)

    # 2. 顯示「球探分析報告」
    # (我們將報告和儀表板放在不同的分頁中，更整潔)
    tab1, tab2 = st.tabs(["📊 球探分析報告", "🗃️ 原始數據瀏覽器"])

    with tab1:
        # 獲取 Markdown 報告
        markdown_output = format_report_markdown_streamlit(report_data)
        st.markdown(markdown_output)

    with tab2:
        st.header("原始數據瀏覽器")
        
        # 3. 顯示「基本資料」儀表板
        if info_df is not None:
            st.subheader("基本資料")
            info = info_df.iloc[0]
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("球隊", f"{info['TEAM_CITY']} {info['TEAM_NAME']}")
            col2.metric("位置", info['POSITION'])
            col3.metric("身高", info['HEIGHT'])
            col4.metric("體重", info['WEIGHT_LBS'] + " 磅")
            col1.metric("球衣號碼", "#" + info['JERSEY'])
            col2.metric("生日", info['BIRTHDATE'].split('T')[0])
            col3.metric("經驗", str(info['SCHOOL']))
            col4.metric("選秀", f"{info['DRAFT_YEAR']} 年 第 {info['DRAFT_NUMBER']} 順位")
        
        # 4. 顯示「生涯數據」儀表板
        if career_df is not None:
            st.subheader("生涯逐年數據 (例行賽)")
            columns_to_show = [
                'SEASON_ID', 'TEAM_ABBREVIATION', 'GP', 'GS', 'MIN', 'PTS', 
                'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG_PCT', 'FG3_PCT', 'FT_PCT'
            ]
            display_cols = [col for col in columns_to_show if col in career_df.columns]
            st.dataframe(career_df[display_cols].sort_values('SEASON_ID', ascending=False), height=350, use_container_width=True)
        
        # 5. 顯示「獎項」儀表板
        if awards_df is not None:
            st.subheader("生涯獎項")
            awards_to_show = awards_df[['DESCRIPTION', 'SEASON', 'AWARD_TYPE']]
            st.dataframe(awards_to_show, height=200, use_container_width=True)

else:
    # --- 如果用戶還沒選擇球員 ---
    st.info("👈 請從左側的下拉式選單中選擇一位球員，並確認查詢賽季。")


# ----------------------------------
# 4.3 今日賽程 (非即時)
# ----------------------------------
st.header("今日賽程表 (非即時)", divider='blue')
st.markdown("⚠️ **請注意：** 這裡的數據**不是即時的**。`nba-api` 的數據更新有嚴重延遲。")

if st.button("刷新今日賽程"):
    st.cache_data.clear() # 清除所有緩存 (包括球員)
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
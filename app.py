import streamlit as st
import pandas as pd
import io
import csv
import re

# --- 页面基础配置 ---
st.set_page_config(
    page_title="表格处理工具 (Ives)", 
    layout="wide", 
    page_icon="🚀"
)

# --- 标题区 ---
st.title("🚀 表格数据全能助手")
st.caption("Designed by Ives | 清洗 · 透视 · 关联 · 合并")
st.divider()

# --- 侧边栏：一级模式 ---
st.sidebar.header("功能导航")
app_mode = st.sidebar.radio("请选择任务类型", ["单表处理 (清洗/筛选/透视)", "多表操作 (合并/关联)"])

# --- 核心工具函数 ---
def detect_separator(file_buffer):
    """自动检测文本分隔符"""
    try:
        sample = file_buffer.read(2048).decode("utf-8")
        file_buffer.seek(0)
        sniffer = csv.Sniffer()
        return sniffer.sniff(sample).delimiter
    except:
        file_buffer.seek(0)
        return ","

def load_data(uploaded_file, skip_rows=0, header_row=0, sep=None, sheet_name=0):
    """通用文件读取器"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    if file_ext in ['xls', 'xlsx']:
        return pd.read_excel(uploaded_file, skiprows=skip_rows, header=header_row, sheet_name=sheet_name)
    else:
        if sep is None:
            sep = detect_separator(uploaded_file)
        return pd.read_csv(uploaded_file, sep=sep, skiprows=skip_rows, header=header_row, engine='python')

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Result')
    return output

# ========================================================
# 模式 1: 单表处理 (代码保持精简稳定)
# ========================================================
if app_mode == "单表处理 (清洗/筛选/透视)":
    
    st.sidebar.subheader("📂 文件导入")
    uploaded_file = st.sidebar.file_uploader("上传单个文件", type=['csv', 'xlsx', 'xls', 'tsv', 'txt'])
    
    if uploaded_file:
        # 参数配置
        with st.sidebar.expander("⚙️ 读取设置", expanded=False):
            file_ext = uploaded_file.name.split('.')[-1].lower()
            sheet = 0
            if file_ext in ['xlsx', 'xls']:
                try:
                    xl = pd.ExcelFile(uploaded_file)
                    sheet = st.selectbox("选择 Sheet", xl.sheet_names)
                    uploaded_file.seek(0)
                except: pass
            
            skip = st.number_input("跳过前 N 行", 0, 100, 0)
            header = st.number_input("标题所在行", 0, 100, 0)
        
        try:
            df_raw = load_data(uploaded_file, skip, header, sheet_name=sheet)
            st.sidebar.success(f"已加载: {len(df_raw)} 行")

            t1, t2 = st.tabs(["🧹 数据清洗", "📊 数据透视"])
            
            # 清洗逻辑
            with t1:
                c1, c2 = st.columns([3, 1])
                cols = st.multiselect("保留列", df_raw.columns, default=df_raw.columns)
                df = df_raw[cols].copy()
                
                # 筛选器
                with st.container(border=True):
                    f_col, val_col = st.columns([1, 2])
                    target = f_col.selectbox("筛选列", ["无"] + list(df.columns))
                    if target != "无":
                        if pd.api.types.is_numeric_dtype(df[target]):
                            mn, mx = float(df[target].min()), float(df[target].max())
                            r = val_col.slider("范围", mn, mx, (mn, mx))
                            df = df[(df[target] >= r[0]) & (df[target] <= r[1])]
                        else:
                            txt = val_col.text_input("包含关键词 (逗号分隔)")
                            if txt:
                                k = [x.strip() for x in txt.split(',') if x.strip()]
                                df = df[df[target].astype(str).str.contains("|".join(k), case=False, na=False)]
                
                # 截取
                if len(df)>0:
                    s, e = st.slider("行范围截取", 0, len(df), (0, len(df)))
                    df = df.iloc[s:e]

                st.dataframe(df, use_container_width=True)
                st.download_button("下载 Excel", to_excel(df), "cleaned_data.xlsx")

            # 透视逻辑
            with t2:
                r1, r2, r3, r4 = st.columns(4)
                idx = r1.multiselect("行", df_raw.columns)
                col = r2.multiselect("列", df_raw.columns)
                val = r3.multiselect("值", df_raw.columns)
                agg = r4.selectbox("算法", ["sum", "mean", "count", "nunique"])
                if idx and val:
                    pt = pd.pivot_table(df_raw, index=idx, columns=col, values=val, aggfunc=agg)
                    st.dataframe(pt)
                    st.download_button("下载透视表", to_excel(pt), "pivot_table.xlsx")
                    
        except Exception as e: st.error(f"错误: {e}")

# ========================================================
# 模式 2: 多表操作 (核心修改区域)
# ========================================================
elif app_mode == "多表操作 (合并/关联)":
    
    st.subheader("📚 多文件批处理")
    
    # 使用大卡片区分两种截然不同的模式
    col_mode1, col_mode2 = st.columns(2)
    with col_mode1:
        st.info("⬇️ **纵向堆叠 (Concat)**\n\n适用：表结构相同，只是数据分开存放。\n\n效果：行数增加，列数不变。\n\n例子：合并1月、2月、3月的销售记录。")
    with col_mode2:
        st.success("➡️ **横向关联 (Join/Merge)**\n\n适用：表结构不同，通过【关键列】匹配。\n\n效果：列数增加，信息扩充。\n\n例子：将【花名册】、【工资条】、【考勤表】按工号拼成一张大宽表。")

    op_type = st.radio("选择操作类型", ["纵向堆叠", "横向关联"], horizontal=True, label_visibility="collapsed")
    st.divider()

    files = st.file_uploader("批量上传文件 (支持Excel/CSV)", accept_multiple_files=True)
    
    if files:
        if len(files) < 2:
            st.warning("⚠️ 请至少上传 2 个文件。")
        else:
            # ------------------------------------------------
            # A. 纵向堆叠 (行合并)
            # ------------------------------------------------
            if op_type == "纵向堆叠":
                if st.button("🚀 开始纵向合并"):
                    dfs = []
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        try:
                            d = load_data(f)
                            d['_来源文件'] = f.name
                            dfs.append(d)
                        except: st.error(f"{f.name} 读取失败")
                        bar.progress((i+1)/len(files))
                    
                    if dfs:
                        res = pd.concat(dfs, ignore_index=True)
                        st.success(f"✅ 纵向合并完成！总计 {len(res)} 行。")
                        st.dataframe(res.head(50), use_container_width=True)
                        st.download_button("📥 下载结果", to_excel(res), "concat_result.xlsx")

            # ------------------------------------------------
            # B. 横向关联 (按关键列合并 - Star Join)
            # ------------------------------------------------
            else:
                st.markdown("### 🔗 关联配置 (按值匹配)")
                st.caption("逻辑：以【第一个文件】为主表，将后续文件的列拼接到主表上。")
                
                # 1. 预读取与布局
                dfs = {}
                names = []
                key_selectors = [None] * len(files)
                
                # Grid 布局显示所有文件
                cols = st.columns(3) 
                
                for i, f in enumerate(files):
                    f.seek(0)
                    df = load_data(f)
                    dfs[f.name] = df
                    names.append(f.name)
                    
                    with cols[i % 3]:
                        with st.container(border=True):
                            st.write(f"**{i+1}. {f.name}**")
                            # 智能推荐 Key
                            defaults = [c for c in df.columns if c.lower() in ['id','uid','no','key','code','工号','编号','姓名']]
                            
                            # 这里是多选，支持多键合并
                            key_selectors[i] = st.multiselect(
                                "选择关键列 (Key)", 
                                df.columns, 
                                default=defaults[:1],
                                key=f"k_{i}"
                            )

                # 2. 全局选项
                st.divider()
                c1, c2, c3 = st.columns([1, 1, 1])
                how = c1.selectbox("匹配模式", ["left (以主表为准)", "inner (只留交集)", "outer (保留所有)"]).split()[0]
                ignore_case = c2.checkbox("忽略大小写", value=True, help="自动转为小写进行匹配")
                do_merge = c3.button("🚀 开始横向关联", use_container_width=True, type="primary")

                # 3. 执行逻辑
                if do_merge:
                    # 校验
                    base_keys = key_selectors[0]
                    if not base_keys:
                        st.error("❌ 第一个文件必须选择关键列！")
                        st.stop()
                    
                    # 初始化结果集
                    result_df = dfs[names[0]].copy()
                    
                    # 清洗主表 Key
                    for k in base_keys:
                        if ignore_case: result_df[k] = result_df[k].astype(str).str.lower().str.strip()
                        else: result_df[k] = result_df[k].astype(str).str.strip()

                    # 循环关联后续文件
                    bar = st.progress(0)
                    for i in range(1, len(files)):
                        curr_name = names[i]
                        curr_df = dfs[curr_name].copy()
                        curr_keys = key_selectors[i]

                        # 校验列数
                        if len(curr_keys) != len(base_keys):
                            st.error(f"❌ 列数不一致！主表选了{len(base_keys)}列，{curr_name}选了{len(curr_keys)}列。")
                            st.stop()
                        
                        # 清洗当前表 Key
                        for k in curr_keys:
                            if ignore_case: curr_df[k] = curr_df[k].astype(str).str.lower().str.strip()
                            else: curr_df[k] = curr_df[k].astype(str).str.strip()
                        
                        # 执行 Merge
                        try:
                            result_df = pd.merge(
                                result_df,
                                curr_df,
                                left_on=base_keys,     # 始终尝试用主表的 Key 去连
                                right_on=curr_keys,    # 连当前表的 Key
                                how=how,
                                suffixes=('', f'_{i}') # 自动处理重名列
                            )
                        except Exception as e:
                            st.error(f"关联 {curr_name} 失败: {e}")
                            st.stop()
                            
                        bar.progress(i/(len(files)-1))

                    bar.progress(1.0)
                    st.success(f"✅ 关联成功！最终包含 {result_df.shape[0]} 行，{result_df.shape[1]} 列。")
                    st.dataframe(result_df.head(50), use_container_width=True)
                    st.download_button("📥 下载关联结果", to_excel(result_df), "merged_result.xlsx")

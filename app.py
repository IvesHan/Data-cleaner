import streamlit as st
import pandas as pd
import io
import csv
import re

# 设置页面配置
st.set_page_config(page_title="超级表格助手", layout="wide", page_icon="🚀")

st.title("🚀 超级表格助手：清洗 · 合并 · 透视")

# --- 侧边栏：功能模式选择 ---
st.sidebar.header("🛠 功能模式")
app_mode = st.sidebar.radio("选择操作模式", ["单表处理 (清洗/筛选/透视)", "多表合并 (纵向拼接)"])

# --- 通用函数 ---
def detect_separator(file_buffer):
    """尝试检测分隔符"""
    try:
        sample = file_buffer.read(1024).decode("utf-8")
        file_buffer.seek(0)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        return dialect.delimiter
    except:
        file_buffer.seek(0)
        return ","

def load_data(uploaded_file, skip_rows, header_row, sep=None):
    """通用数据加载函数"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    if file_ext in ['xls', 'xlsx']:
        return pd.read_excel(uploaded_file, skiprows=skip_rows, header=header_row)
    else:
        # 如果未指定分隔符，尝试自动检测
        if sep is None:
            sep = detect_separator(uploaded_file)
        return pd.read_csv(uploaded_file, sep=sep, skiprows=skip_rows, header=header_row, engine='python')

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

def convert_df_to_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return buffer

# ========================================================
# 模式 1: 单表处理 (清洗 + 透视)
# ========================================================
if app_mode == "单表处理 (清洗/筛选/透视)":
    st.sidebar.divider()
    st.sidebar.subheader("📄 文件读取设置")
    
    uploaded_file = st.sidebar.file_uploader("上传单个文件", type=['csv', 'xlsx', 'xls', 'tsv', 'txt', 'dat'])
    
    if uploaded_file:
        # 读取参数
        skip_rows = st.sidebar.number_input("跳过前 N 行", 0, 100, 0)
        header_row = st.sidebar.number_input("标题所在行", 0, 100, 0)
        
        # 分隔符设置
        sep_option = "自动识别"
        file_ext = uploaded_file.name.split('.')[-1].lower()
        if file_ext not in ['xlsx', 'xls']:
            sep_option = st.sidebar.selectbox("分隔符", ("自动识别", ",", "\t", ";", "|", "自定义"))
        
        sep = None
        if sep_option == ",": sep = ","
        elif sep_option == "\t": sep = "\t"
        elif sep_option == ";": sep = ";"
        elif sep_option == "|": sep = "|"
        elif sep_option == "自定义": sep = st.sidebar.text_input("输入分隔符", ",")
        
        try:
            # 加载数据
            df = load_data(uploaded_file, skip_rows, header_row, sep)
            st.success(f"已加载: {uploaded_file.name} ({df.shape[0]} 行, {df.shape[1]} 列)")

            # 使用 Tabs 分离 清洗导出 和 数据透视
            tab1, tab2 = st.tabs(["🧹 数据清洗与导出", "📈 数据透视表"])

            # --- Tab 1: 清洗与筛选 ---
            with tab1:
                st.subheader("1. 字段与排序")
                c1, c2 = st.columns(2)
                with c1:
                    all_cols = df.columns.tolist()
                    sel_cols = st.multiselect("选择保留列", all_cols, default=all_cols)
                    if not sel_cols: sel_cols = all_cols
                with c2:
                    sort_col = st.selectbox("排序依据", ["无"] + sel_cols)
                    sort_asc = st.checkbox("升序排列", value=True)

                df_cleaned = df[sel_cols]
                if sort_col != "无":
                    df_cleaned = df_cleaned.sort_values(by=sort_col, ascending=sort_asc)

                st.subheader("2. 高级内容筛选")
                # 增强版筛选：支持集合输入
                with st.expander("点击展开筛选面板", expanded=True):
                    f_col1, f_col2 = st.columns([1, 2])
                    with f_col1:
                        filter_target = st.selectbox("选择筛选列", ["无"] + sel_cols)
                    
                    if filter_target != "无":
                        with f_col2:
                            if pd.api.types.is_numeric_dtype(df_cleaned[filter_target]):
                                min_v, max_v = float(df_cleaned[filter_target].min()), float(df_cleaned[filter_target].max())
                                rng = st.slider("数值范围", min_v, max_v, (min_v, max_v))
                                df_cleaned = df_cleaned[(df_cleaned[filter_target] >= rng[0]) & (df_cleaned[filter_target] <= rng[1])]
                            else:
                                st.markdown("👇 **多值匹配模式**：输入多个值，用逗号、空格或分号隔开")
                                text_input = st.text_area("输入筛选值集合 (例如: ID001, ID002 ID003)", height=68)
                                match_mode = st.radio("匹配模式", ["精确匹配 (Is In)", "模糊包含 (Contains)"], horizontal=True)
                                
                                if text_input:
                                    # 自动正则分割：逗号、中文逗号、分号、竖线、空格、换行
                                    keywords = re.split(r'[,\s;，；|\n]+', text_input.strip())
                                    # 去除空字符串
                                    keywords = [k for k in keywords if k]
                                    
                                    if keywords:
                                        st.caption(f"识别到的筛选词 ({len(keywords)}个): {keywords}")
                                        if match_mode == "精确匹配 (Is In)":
                                            # 转换为字符串对比，防止类型不匹配
                                            df_cleaned = df_cleaned[df_cleaned[filter_target].astype(str).isin(keywords)]
                                        else:
                                            # 模糊包含：只要包含列表里任意一个词
                                            pattern = "|".join([re.escape(k) for k in keywords])
                                            df_cleaned = df_cleaned[df_cleaned[filter_target].astype(str).str.contains(pattern, na=False)]

                st.subheader("3. 结果预览")
                st.dataframe(df_cleaned, use_container_width=True)
                
                # 导出区
                st.subheader("📥 导出结果")
                ec1, ec2 = st.columns(2)
                ec1.download_button("下载 CSV", convert_df_to_csv(df_cleaned), f"cleaned_{uploaded_file.name}.csv", "text/csv")
                ec2.download_button("下载 Excel", convert_df_to_excel(df_cleaned), f"cleaned_{uploaded_file.name}.xlsx")

            # --- Tab 2: 数据透视表 ---
            with tab2:
                st.subheader("数据透视分析 (Pivot Table)")
                
                p_c1, p_c2, p_c3, p_c4 = st.columns(4)
                with p_c1:
                    index_col = st.multiselect("行 (Index)", df.columns)
                with p_c2:
                    columns_col = st.multiselect("列 (Columns)", df.columns)
                with p_c3:
                    values_col = st.multiselect("值 (Values)", df.columns)
                with p_c4:
                    agg_func = st.selectbox("聚合方式", ["sum", "mean", "count", "min", "max", "nunique"])

                if index_col and values_col:
                    try:
                        pivot_df = pd.pivot_table(
                            df, 
                            index=index_col, 
                            columns=columns_col if columns_col else None, 
                            values=values_col, 
                            aggfunc=agg_func
                        )
                        st.write("透视结果预览：")
                        st.dataframe(pivot_df, use_container_width=True)
                        
                        st.download_button(
                            "📥 下载透视表 (Excel)",
                            convert_df_to_excel(pivot_df),
                            "pivot_table.xlsx"
                        )
                    except Exception as e:
                        st.error(f"透视表生成失败: {e}。请检查选择的'值'列是否为数字类型。")
                else:
                    st.info("请至少选择一个 '行' 和一个 '值' 来生成透视表。")

        except Exception as e:
            st.error(f"处理出错: {e}")

# ========================================================
# 模式 2: 多表合并
# ========================================================
elif app_mode == "多表合并 (纵向拼接)":
    st.sidebar.divider()
    st.subheader("📚 多文件合并")
    st.markdown("上传多个结构相似的文件（如 1月数据.csv, 2月数据.xlsx），程序将自动把它们纵向拼接在一起。")
    
    uploaded_files = st.file_uploader("上传一系列文件", accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("开始合并"):
            dfs = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"正在读取: {file.name}...")
                try:
                    # 复用简单的加载逻辑（这里假设所有文件格式参数一致，实际可扩展）
                    # 默认跳过0行，标题在第0行
                    current_df = load_data(file, 0, 0)
                    # 可以在这里加一列标识来源文件
                    current_df['_来源文件'] = file.name
                    dfs.append(current_df)
                except Exception as e:
                    st.error(f"文件 {file.name} 读取失败: {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            if dfs:
                try:
                    status_text.text("正在拼接...")
                    merged_df = pd.concat(dfs, ignore_index=True)
                    st.success(f"合并成功！共处理 {len(dfs)} 个文件，结果包含 {merged_df.shape[0]} 行。")
                    
                    st.dataframe(merged_df.head(50), use_container_width=True)
                    
                    st.download_button(
                        "📥 下载合并后的 Excel", 
                        convert_df_to_excel(merged_df), 
                        "merged_result.xlsx"
                    )
                except Exception as e:
                    st.error(f"合并失败: {e}。通常是因为不同文件的列名不一致。")
            else:
                st.warning("没有成功读取任何数据。")

else:
    st.info("请在左侧侧边栏选择模式。")

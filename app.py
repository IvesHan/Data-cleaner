import streamlit as st
import pandas as pd
import io
import csv
import re

# --- 页面基础配置 ---
st.set_page_config(
    page_title="表格处理工具 (Ives)", 
    layout="wide", 
    page_icon="📑"
)

# --- 标题区 ---
st.title("表格处理工具")
st.caption("Designed by Ives")  # 署名位置
st.divider()

# --- 侧边栏：全局设置 ---
st.sidebar.header("操作模式")
app_mode = st.sidebar.radio("选择功能", ["单表处理 (清洗/筛选/透视)", "多表合并"])

# --- 核心函数库 ---
def detect_separator(file_buffer):
    """尝试检测文本文件的分隔符"""
    try:
        sample = file_buffer.read(2048).decode("utf-8")
        file_buffer.seek(0)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        return dialect.delimiter
    except:
        file_buffer.seek(0)
        return ","

def load_data(uploaded_file, skip_rows, header_row, sep=None):
    """读取文件的统一入口"""
    file_ext = uploaded_file.name.split('.')[-1].lower()
    if file_ext in ['xls', 'xlsx']:
        return pd.read_excel(uploaded_file, skiprows=skip_rows, header=header_row)
    else:
        if sep is None:
            sep = detect_separator(uploaded_file)
        return pd.read_csv(uploaded_file, sep=sep, skiprows=skip_rows, header=header_row, engine='python')

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output

# ========================================================
# 模式 1: 单表处理 (核心清洗逻辑)
# ========================================================
if app_mode == "单表处理 (清洗/筛选/透视)":
    
    # 1. 文件上传区
    st.sidebar.subheader("文件读取")
    uploaded_file = st.sidebar.file_uploader("上传文件", type=['csv', 'xlsx', 'xls', 'tsv', 'txt'])
    
    if uploaded_file:
        # 读取参数
        with st.sidebar.expander("读取参数配置 (可选)"):
            skip_rows = st.number_input("跳过前 N 行", 0, 100, 0)
            header_row = st.number_input("标题所在行", 0, 100, 0)
            
            # 分隔符逻辑
            sep_option = "自动识别"
            if uploaded_file.name.split('.')[-1].lower() not in ['xlsx', 'xls']:
                sep_option = st.selectbox("列分隔符", ("自动识别", ",", "\t", ";", "|", "自定义"))
            
            sep = None
            if sep_option == "自定义":
                sep = st.text_input("输入分隔符", ",")
            elif sep_option != "自动识别":
                sep_map = {",": ",", "\t": "\t", ";": ";", "|": "|"}
                sep = sep_map.get(sep_option, ",")

        try:
            # 加载原始数据
            df_raw = load_data(uploaded_file, skip_rows, header_row, sep)
            st.sidebar.success(f"已读取: {len(df_raw)} 行")

            # -----------------------------------------------------------
            # 数据处理流水线 (Pipeline)
            # 逻辑顺序：列选择 -> 排序 -> 内容筛选 -> 行截取 -> 展示/导出
            # -----------------------------------------------------------
            
            # tab 分区
            tab_clean, tab_pivot = st.tabs(["数据清洗", "数据透视"])

            with tab_clean:
                # 1. 列管理
                c1, c2 = st.columns([3, 1])
                with c1:
                    all_cols = df_raw.columns.tolist()
                    selected_cols = st.multiselect("1. 保留列 (留空则保留全部)", all_cols, default=all_cols)
                    if not selected_cols: selected_cols = all_cols
                
                with c2:
                    sort_col = st.selectbox("2. 排序依据", ["无"] + selected_cols)
                    sort_asc = st.checkbox("升序", value=True)

                # 初步处理：切片列 + 排序
                df_step1 = df_raw[selected_cols].copy()
                if sort_col != "无":
                    df_step1 = df_step1.sort_values(by=sort_col, ascending=sort_asc)

                # 2. 高级内容筛选 (重点修改部分)
                st.markdown("##### 3. 内容筛选")
                with st.container(border=True): # 使用边框包裹，更清晰
                    f_col1, f_col2 = st.columns([1, 3])
                    with f_col1:
                        filter_target = st.selectbox("筛选目标列", ["无"] + selected_cols)
                    
                    # 初始化结果为上一步的结果
                    df_step2 = df_step1 

                    if filter_target != "无":
                        with f_col2:
                            # 区分数值和文本
                            if pd.api.types.is_numeric_dtype(df_step1[filter_target]):
                                min_v = float(df_step1[filter_target].min())
                                max_v = float(df_step1[filter_target].max())
                                rng = st.slider(f"选择 {filter_target} 范围", min_v, max_v, (min_v, max_v))
                                df_step2 = df_step1[(df_step1[filter_target] >= rng[0]) & (df_step1[filter_target] <= rng[1])]
                            else:
                                # 文本多值筛选
                                text_input = st.text_area(
                                    f"输入 {filter_target} 的筛选值 (支持批量粘贴)", 
                                    height=100,
                                    placeholder="例如：\nA001\nA002, A003\n(支持逗号、空格、换行分隔)"
                                )
                                match_mode = st.radio("匹配逻辑", ["精确匹配 (等于)", "模糊匹配 (包含)"], horizontal=True)
                                
                                st.caption("提示：输入内容后，请按 Ctrl+Enter 或点击输入框外区域以生效。")

                                if text_input.strip():
                                    # 核心正则拆分
                                    keywords = re.split(r'[,\s;，；|\n]+', text_input.strip())
                                    keywords = [k for k in keywords if k] # 去除空值
                                    
                                    if keywords:
                                        if match_mode == "精确匹配 (等于)":
                                            # 强制转字符串对比
                                            mask = df_step1[filter_target].astype(str).isin(keywords)
                                            df_step2 = df_step1[mask]
                                        else:
                                            # 模糊包含
                                            pattern = "|".join([re.escape(k) for k in keywords])
                                            mask = df_step1[filter_target].astype(str).str.contains(pattern, case=False, na=False)
                                            df_step2 = df_step1[mask]
                                    
                                    # 状态回显
                                    st.info(f"筛选关键词: {len(keywords)} 个 | 命中行数: {len(df_step2)} (原 {len(df_step1)} 行)")
                
                # 3. 结果展示
                st.markdown("##### 4. 结果预览与导出")
                st.dataframe(df_step2, use_container_width=True)
                
                # 导出按钮
                col_d1, col_d2 = st.columns(2)
                file_label = uploaded_file.name.split('.')[0]
                
                col_d1.download_button(
                    "📥 导出 Excel",
                    data=to_excel(df_step2),
                    file_name=f"{file_label}_processed_ives.xlsx"
                )
                col_d2.download_button(
                    "📥 导出 CSV",
                    data=df_step2.to_csv(index=False).encode('utf-8-sig'),
                    file_name=f"{file_label}_processed_ives.csv",
                    mime="text/csv"
                )

            with tab_pivot:
                st.subheader("数据透视分析")
                if not df_raw.empty:
                    p_c1, p_c2, p_c3 = st.columns(3)
                    idx = p_c1.multiselect("行维度 (Index)", df_raw.columns)
                    cols = p_c2.multiselect("列维度 (Columns)", df_raw.columns)
                    vals = p_c3.multiselect("数值 (Values)", df_raw.columns)
                    func = st.selectbox("计算方式", ["sum", "mean", "count", "max", "min", "nunique"])
                    
                    if idx and vals:
                        try:
                            df_pivot = pd.pivot_table(df_raw, index=idx, columns=cols if cols else None, values=vals, aggfunc=func)
                            st.dataframe(df_pivot, use_container_width=True)
                            st.download_button("导出透视表", to_excel(df_pivot), f"{file_label}_pivot.xlsx")
                        except Exception as e:
                            st.error(f"透视表生成错误: {e}")
                    else:
                        st.info("请至少选择【行维度】和【数值】。")

        except Exception as e:
            st.error(f"文件处理出错: {e}")

# ========================================================
# 模式 2: 多表合并
# ========================================================
elif app_mode == "多表合并":
    st.subheader("多文件合并工具")
    st.markdown("支持上传多个 CSV/Excel 文件，程序将自动进行纵向拼接。")
    
    files = st.file_uploader("批量上传文件", accept_multiple_files=True)
    
    if files and st.button("开始合并数据"):
        dfs = []
        bar = st.progress(0)
        
        for i, f in enumerate(files):
            try:
                # 简化的读取逻辑，默认第一行为表头
                d = load_data(f, 0, 0)
                d['Source_File'] = f.name # 自动标记来源
                dfs.append(d)
            except:
                st.error(f"{f.name} 读取失败")
            bar.progress((i+1)/len(files))
            
        if dfs:
            merged = pd.concat(dfs, ignore_index=True)
            st.success(f"合并完成：共 {len(dfs)} 个文件，总计 {len(merged)} 行。")
            st.dataframe(merged.head(100), use_container_width=True)
            st.download_button("下载合并结果 (Excel)", to_excel(merged), "merged_data_ives.xlsx")

import streamlit as st
import pandas as pd
import io
import csv
import re

# --- 页面配置 ---
st.set_page_config(
    page_title="表格处理工具 (Ives)", 
    layout="wide", 
    page_icon="📑"
)

# --- 顶部标题 ---
st.title("表格处理工具")
st.caption("Designed by Ives | Professional Data Tool")
st.divider()

# --- 侧边栏：模式选择 ---
st.sidebar.header("功能菜单")
app_mode = st.sidebar.radio("选择操作模式", ["单表处理 (清洗/筛选/透视)", "多表合并"])

# --- 核心工具函数 ---
def detect_separator(file_buffer):
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
# 模式 1: 单表处理
# ========================================================
if app_mode == "单表处理 (清洗/筛选/透视)":
    
    st.sidebar.subheader("1. 文件导入")
    uploaded_file = st.sidebar.file_uploader("上传数据文件", type=['csv', 'xlsx', 'xls', 'tsv', 'txt'])
    
    if uploaded_file:
        # 读取配置
        with st.sidebar.expander("读取参数配置 (可选)"):
            skip_rows = st.number_input("跳过前 N 行", 0, 100, 0)
            header_row = st.number_input("标题所在行", 0, 100, 0)
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
            st.sidebar.success(f"读取成功: {len(df_raw)} 行")

            # Tab 分区
            tab_clean, tab_pivot = st.tabs(["🧹 数据清洗与导出", "📈 数据透视表"])

            # ------------------------------------------------------------
            # Tab 1: 清洗逻辑 (严格按顺序执行)
            # ------------------------------------------------------------
            with tab_clean:
                # [Step 1] 列选择与排序
                st.subheader("1. 列选择与排序")
                c1, c2 = st.columns([3, 1])
                with c1:
                    all_cols = df_raw.columns.tolist()
                    selected_cols = st.multiselect("保留列 (默认全部)", all_cols, default=all_cols)
                    if not selected_cols: selected_cols = all_cols
                
                with c2:
                    sort_col = st.selectbox("排序依据", ["无"] + selected_cols)
                    sort_asc = st.radio("排序方式", ["升序", "降序"], horizontal=True, label_visibility="collapsed")

                # 生成中间变量 df_step1
                df_step1 = df_raw[selected_cols].copy()
                if sort_col != "无":
                    ascending = True if sort_asc == "升序" else False
                    df_step1 = df_step1.sort_values(by=sort_col, ascending=ascending)

                # [Step 2] 内容筛选
                st.subheader("2. 内容筛选 (Filter)")
                
                # 初始化 df_result，默认等于上一步的结果
                df_result = df_step1.copy()

                with st.container(border=True):
                    f_col1, f_col2 = st.columns([1, 2])
                    with f_col1:
                        filter_target = st.selectbox("选择筛选列", ["无"] + selected_cols)
                    
                    if filter_target != "无":
                        with f_col2:
                            # 数值筛选
                            if pd.api.types.is_numeric_dtype(df_step1[filter_target]):
                                min_v = float(df_step1[filter_target].min())
                                max_v = float(df_step1[filter_target].max())
                                rng = st.slider(f"数值范围 ({filter_target})", min_v, max_v, (min_v, max_v))
                                # 更新 df_result
                                df_result = df_step1[(df_step1[filter_target] >= rng[0]) & (df_step1[filter_target] <= rng[1])]
                            
                            # 文本筛选
                            else:
                                text_input = st.text_area(
                                    f"输入筛选值 (支持多行粘贴)", 
                                    height=80,
                                    placeholder="输入要保留的内容，支持逗号、空格或换行分隔..."
                                )
                                match_mode = st.radio("匹配模式", ["精确匹配 (Is In)", "模糊包含 (Contains)"], horizontal=True)

                                if text_input.strip():
                                    keywords = re.split(r'[,\s;，；|\n]+', text_input.strip())
                                    keywords = [k for k in keywords if k] # 去除空值
                                    
                                    if keywords:
                                        if match_mode == "精确匹配 (Is In)":
                                            # 更新 df_result
                                            df_result = df_step1[df_step1[filter_target].astype(str).isin(keywords)]
                                        else:
                                            pattern = "|".join([re.escape(k) for k in keywords])
                                            # 更新 df_result
                                            df_result = df_step1[df_step1[filter_target].astype(str).str.contains(pattern, case=False, na=False)]
                
                # [Step 3] 行截取 (最后一步)
                st.subheader("3. 行截取 (按位置)")
                if len(df_result) > 0:
                    row_range = st.slider("保留行范围", 0, len(df_result), (0, len(df_result)))
                    df_result = df_result.iloc[row_range[0]:row_range[1]]

                # ------------------------------------------------------------
                # [Step 4] 结果预览与导出 (必须使用 df_result)
                # ------------------------------------------------------------
                st.divider()
                st.subheader(f"4. 结果预览与导出 (共 {len(df_result)} 行)")
                
                # 增加动态指标，让用户确认数据已更新
                m1, m2, m3 = st.columns(3)
                m1.metric("原始行数", len(df_raw))
                m2.metric("当前行数", len(df_result), delta=len(df_result)-len(df_raw))
                
                # 预览表格
                st.dataframe(df_result, use_container_width=True)
                
                # 导出按钮
                st.write("#### 下载文件")
                d_col1, d_col2 = st.columns(2)
                file_name_base = uploaded_file.name.split('.')[0]
                
                d_col1.download_button(
                    "📥 下载 Excel 文件",
                    data=to_excel(df_result),
                    file_name=f"{file_name_base}_cleaned_ives.xlsx"
                )
                
                d_col2.download_button(
                    "📥 下载 CSV 文件",
                    data=df_result.to_csv(index=False).encode('utf-8-sig'),
                    file_name=f"{file_name_base}_cleaned_ives.csv",
                    mime="text/csv"
                )

            # ------------------------------------------------------------
            # Tab 2: 透视表 (逻辑保持不变)
            # ------------------------------------------------------------
            with tab_pivot:
                st.subheader("数据透视分析")
                if not df_raw.empty:
                    p_c1, p_c2, p_c3, p_c4 = st.columns(4)
                    idx = p_c1.multiselect("行维度 (Index)", df_raw.columns)
                    cols = p_c2.multiselect("列维度 (Columns)", df_raw.columns)
                    vals = p_c3.multiselect("数值 (Values)", df_raw.columns)
                    func = p_c4.selectbox("聚合方式", ["sum", "mean", "count", "max", "min", "nunique"])
                    
                    if idx and vals:
                        try:
                            df_p = pd.pivot_table(df_raw, index=idx, columns=cols if cols else None, values=vals, aggfunc=func)
                            st.dataframe(df_p, use_container_width=True)
                            st.download_button("导出透视表 (Excel)", to_excel(df_p), f"{file_name_base}_pivot_ives.xlsx")
                        except Exception as e:
                            st.error(f"透视表生成错误: {e}")

        except Exception as e:
            st.error(f"处理出错: {e}")

# ========================================================
# 模式 2: 多表合并
# ========================================================
elif app_mode == "多表合并":
    st.subheader("📚 多文件合并工具")
    
    files = st.file_uploader("批量上传文件 (CSV/Excel)", accept_multiple_files=True)
    
    if files and st.button("开始合并"):
        dfs = []
        bar = st.progress(0)
        
        for i, f in enumerate(files):
            try:
                # 默认读取设置
                d = load_data(f, 0, 0)
                d['Source_File'] = f.name 
                dfs.append(d)
            except:
                st.error(f"无法读取: {f.name}")
            bar.progress((i+1)/len(files))
            
        if dfs:
            merged = pd.concat(dfs, ignore_index=True)
            st.success(f"合并完成: 共处理 {len(files)} 个文件")
            
            st.dataframe(merged.head(100), use_container_width=True)
            st.download_button("下载合并结果 (Excel)", to_excel(merged), "merged_data_ives.xlsx")

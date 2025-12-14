import streamlit as st
import pandas as pd
import io
import csv

# 设置页面配置
st.set_page_config(page_title="通用表格数据清洗工具", layout="wide", page_icon="📊")

st.title("📊 通用表格数据清洗与转换工具")
st.markdown("支持 CSV, Excel, TSV, TXT 等格式。上传后可进行清洗、排序、筛选并导出。")

# --- 侧边栏：全局配置 ---
st.sidebar.header("1. 文件上传与读取配置")

uploaded_file = st.sidebar.file_uploader("上传表格文件", type=['csv', 'xlsx', 'xls', 'tsv', 'txt', 'dat'])

# 辅助函数：尝试检测分隔符
def detect_separator(file_buffer):
    try:
        sample = file_buffer.read(1024).decode("utf-8")
        file_buffer.seek(0)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        return dialect.delimiter
    except:
        file_buffer.seek(0)
        return ","

# 读取参数设置
if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    # 1.1 行首配置 (处理注释行/标题行)
    st.sidebar.subheader("读取参数")
    skip_rows = st.sidebar.number_input("跳过前 N 行 (用于去除注释)", min_value=0, value=0, step=1)
    header_row = st.sidebar.number_input("标题所在行 (0表示第一行)", min_value=0, value=0, step=1)
    
    # 1.2 分隔符配置 (仅针对文本文件)
    sep = ","
    if file_ext in ['csv', 'tsv', 'txt', 'dat']:
        sep_option = st.sidebar.selectbox(
            "列分隔符",
            ("自动识别", "逗号 (,)", "制表符 (Tab)", "分号 (;)", "竖线 (|)", "空格 ( )", "自定义")
        )
        
        if sep_option == "自动识别":
            sep = detect_separator(uploaded_file)
            st.sidebar.success(f"已检测分隔符: `{sep}`")
        elif sep_option == "逗号 (,)": sep = ","
        elif sep_option == "制表符 (Tab)": sep = "\t"
        elif sep_option == "分号 (;)": sep = ";"
        elif sep_option == "竖线 (|)": sep = "|"
        elif sep_option == "空格 ( )": sep = " "
        elif sep_option == "自定义":
            sep = st.sidebar.text_input("输入自定义分隔符", value=",")

    # --- 数据加载 ---
    try:
        if file_ext in ['xls', 'xlsx']:
            df = pd.read_excel(uploaded_file, skiprows=skip_rows, header=header_row)
        else:
            df = pd.read_csv(uploaded_file, sep=sep, skiprows=skip_rows, header=header_row, engine='python')
        
        st.info(f"成功加载文件: {uploaded_file.name} | 原始大小: {df.shape[0]} 行, {df.shape[1]} 列")

        # --- 主界面：数据处理 ---
        st.divider()
        st.header("2. 数据清洗与操作")
        
        col1, col2 = st.columns(2)

        # 2.1 列选择 (摘取某些列)
        with col1:
            st.subheader("列操作")
            all_columns = df.columns.tolist()
            selected_columns = st.multiselect("选择需要保留的列 (留空则保留所有)", all_columns, default=all_columns)
            if not selected_columns:
                selected_columns = all_columns
            
        # 2.2 行排序
        with col2:
            st.subheader("排序操作")
            sort_col = st.selectbox("选择排序依据列", ["无"] + selected_columns)
            sort_asc = st.radio("排序方式", ["升序", "降序"], horizontal=True)
        
        # 应用列选择
        df_processed = df[selected_columns]
        
        # 应用排序
        if sort_col != "无":
            ascending = True if sort_asc == "升序" else False
            df_processed = df_processed.sort_values(by=sort_col, ascending=ascending)

        # 2.3 行筛选 (摘取特殊内容的行)
        st.subheader("行筛选 (根据内容)")
        with st.expander("点击展开筛选器"):
            filter_col = st.selectbox("筛选列", ["无"] + selected_columns)
            if filter_col != "无":
                # 区分数值和文本筛选
                if pd.api.types.is_numeric_dtype(df_processed[filter_col]):
                    min_val, max_val = float(df_processed[filter_col].min()), float(df_processed[filter_col].max())
                    val_range = st.slider(f"选择 {filter_col} 的范围", min_val, max_val, (min_val, max_val))
                    df_processed = df_processed[(df_processed[filter_col] >= val_range[0]) & (df_processed[filter_col] <= val_range[1])]
                else:
                    text_query = st.text_input(f"输入 {filter_col} 包含的文本 (支持正则)")
                    if text_query:
                        df_processed = df_processed[df_processed[filter_col].astype(str).str.contains(text_query, na=False)]

        # 2.4 手动摘取行 (按索引)
        st.subheader("行截取")
        row_range = st.slider("保留行范围 (索引)", 0, len(df_processed), (0, len(df_processed)))
        df_processed = df_processed.iloc[row_range[0]:row_range[1]]

        # --- 预览与导出 ---
        st.divider()
        st.header("3. 结果预览与导出")
        
        st.write(f"当前数据预览 (共 {df_processed.shape[0]} 行):")
        st.dataframe(df_processed, use_container_width=True)

        st.subheader("下载文件")
        d_col1, d_col2 = st.columns(2)
        
        # 导出文件名生成
        base_name = uploaded_file.name.split('.')[0]
        
        # 导出为 CSV
        csv_buffer = df_processed.to_csv(index=False).encode('utf-8-sig')
        d_col1.download_button(
            label="📥 下载为 CSV",
            data=csv_buffer,
            file_name=f"{base_name}_cleaned.csv",
            mime="text/csv"
        )

        # 导出为 Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_processed.to_excel(writer, index=False, sheet_name='Sheet1')
        
        d_col2.download_button(
            label="📥 下载为 Excel",
            data=buffer,
            file_name=f"{base_name}_cleaned.xlsx",
            mime="application/vnd.ms-excel"
        )

    except Exception as e:
        st.error(f"处理文件时发生错误: {e}")
        st.warning("提示: 请检查分隔符设置或‘跳过前 N 行’设置是否正确。")

else:
    st.info("请在左侧侧边栏上传文件以开始。")
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
    """检测文本文件分隔符"""
    try:
        sample = file_buffer.read(2048).decode("utf-8")
        file_buffer.seek(0)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        return dialect.delimiter
    except:
        file_buffer.seek(0)
        return ","

def load_data(uploaded_file, skip_rows=0, header_row=0, sep=None, sheet_name=0):
    """通用加载函数"""
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
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output

# ========================================================
# 模式 1: 单表处理 (保持不变)
# ========================================================
if app_mode == "单表处理 (清洗/筛选/透视)":
    
    st.sidebar.subheader("1. 文件导入")
    uploaded_file = st.sidebar.file_uploader("上传数据文件", type=['csv', 'xlsx', 'xls', 'tsv', 'txt'])
    
    if uploaded_file:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        with st.sidebar.expander("读取参数配置", expanded=True):
            selected_sheet = 0
            if file_ext in ['xlsx', 'xls']:
                try:
                    xl = pd.ExcelFile(uploaded_file)
                    st.markdown("#### Excel 工作表")
                    selected_sheet = st.selectbox("选择要读取的 Sheet", xl.sheet_names)
                    uploaded_file.seek(0)
                except: pass

            st.markdown("#### 行设置")
            skip_rows = st.number_input("跳过前 N 行", 0, 100, 0)
            header_row = st.number_input("标题所在行", 0, 100, 0)
            sep = None
            if file_ext not in ['xlsx', 'xls']:
                sep_option = st.selectbox("列分隔符", ("自动识别", ",", "\t", ";", "|", "自定义"))
                if sep_option == "自定义": sep = st.text_input("输入分隔符", ",")
                elif sep_option != "自动识别": sep = {",": ",", "\t": "\t", ";": ";", "|": "|"}.get(sep_option, ",")

        try:
            df_raw = load_data(uploaded_file, skip_rows, header_row, sep, sheet_name=selected_sheet)
            st.sidebar.success(f"读取成功: {len(df_raw)} 行")

            tab_clean, tab_pivot = st.tabs(["🧹 数据清洗与导出", "📈 数据透视表"])

            with tab_clean:
                st.subheader("1. 列选择与排序")
                c1, c2 = st.columns([3, 1])
                with c1:
                    all_cols = df_raw.columns.tolist()
                    selected_cols = st.multiselect("保留列", all_cols, default=all_cols)
                    if not selected_cols: selected_cols = all_cols
                with c2:
                    sort_col = st.selectbox("排序依据", ["无"] + selected_cols)
                    sort_asc = st.radio("排序", ["升序", "降序"], horizontal=True, label_visibility="collapsed")

                df_step1 = df_raw[selected_cols].copy()
                if sort_col != "无":
                    ascending = True if sort_asc == "升序" else False
                    df_step1 = df_step1.sort_values(by=sort_col, ascending=ascending)

                st.subheader("2. 内容筛选")
                df_result = df_step1.copy()
                with st.container(border=True):
                    f_col1, f_col2 = st.columns([1, 2])
                    with f_col1: filter_target = st.selectbox("筛选列", ["无"] + selected_cols)
                    if filter_target != "无":
                        with f_col2:
                            if pd.api.types.is_numeric_dtype(df_step1[filter_target]):
                                min_v, max_v = float(df_step1[filter_target].min()), float(df_step1[filter_target].max())
                                rng = st.slider(f"数值范围", min_v, max_v, (min_v, max_v))
                                df_result = df_step1[(df_step1[filter_target] >= rng[0]) & (df_step1[filter_target] <= rng[1])]
                            else:
                                text = st.text_area("输入筛选值", height=80)
                                mode = st.radio("模式", ["精确匹配", "模糊包含"], horizontal=True)
                                if text.strip():
                                    keys = [k for k in re.split(r'[,\s;，；|\n]+', text.strip()) if k]
                                    if keys:
                                        if mode == "精确匹配": df_result = df_step1[df_step1[filter_target].astype(str).isin(keys)]
                                        else: df_result = df_step1[df_step1[filter_target].astype(str).str.contains("|".join([re.escape(k) for k in keys]), case=False, na=False)]
                
                st.subheader("3. 行截取")
                if len(df_result) > 0:
                    r1, r2 = st.columns(2)
                    s_idx = r1.number_input("起始行", 0, len(df_result)-1, 0)
                    e_idx = r2.number_input("结束行", s_idx+1, len(df_result), len(df_result))
                    df_result = df_result.iloc[s_idx:e_idx]

                st.divider()
                st.subheader(f"4. 结果 (共 {len(df_result)} 行)")
                st.dataframe(df_result, use_container_width=True)
                d1, d2 = st.columns(2)
                base = uploaded_file.name.split('.')[0]
                d1.download_button("Excel", to_excel(df_result), f"{base}_clean_ives.xlsx")
                d2.download_button("CSV", df_result.to_csv(index=False).encode('utf-8-sig'), f"{base}_clean_ives.csv", "text/csv")

            with tab_pivot:
                st.subheader("数据透视")
                if not df_raw.empty:
                    pc1, pc2, pc3, pc4 = st.columns(4)
                    idx = pc1.multiselect("行", df_raw.columns)
                    cols = pc2.multiselect("列", df_raw.columns)
                    vals = pc3.multiselect("值", df_raw.columns)
                    func = pc4.selectbox("聚合", ["sum", "mean", "count", "max", "min", "nunique"])
                    if idx and vals:
                        try:
                            pt = pd.pivot_table(df_raw, index=idx, columns=cols if cols else None, values=vals, aggfunc=func)
                            st.dataframe(pt, use_container_width=True)
                            st.download_button("下载透视表", to_excel(pt), f"{base}_pivot_ives.xlsx")
                        except Exception as e: st.error(str(e))
        except Exception as e: st.error(str(e))

# ========================================================
# 模式 2: 多表合并 (高级联合主键版)
# ========================================================
elif app_mode == "多表合并":
    st.subheader("📚 多文件合并工具")
    merge_type = st.radio("合并方式", ["纵向拼接 (Concat)", "横向关联 (Merge/Join)"], captions=["行增多 (结构相同)", "列增多 (按Key关联)"])
    st.divider()
    files = st.file_uploader("批量上传文件", accept_multiple_files=True)
    
    if files:
        if len(files) < 2:
            st.warning("请至少上传两个文件。")
        else:
            # A. 纵向拼接
            if merge_type == "纵向拼接 (Concat)":
                if st.button("开始纵向合并"):
                    dfs = []
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        try:
                            d = load_data(f, sheet_name=0)
                            d['Source_File'] = f.name 
                            dfs.append(d)
                        except: st.error(f"读取失败: {f.name}")
                        bar.progress((i+1)/len(files))
                    
                    if dfs:
                        merged = pd.concat(dfs, ignore_index=True)
                        st.success(f"合并完成: {len(merged)} 行")
                        st.dataframe(merged.head(100), use_container_width=True)
                        st.download_button("下载结果", to_excel(merged), "concat_result_ives.xlsx")

            # B. 横向关联 (多列匹配版)
            else: 
                st.subheader("🔗 高级关联配置")
                st.info("💡 提示：您可以选择多列作为联合主键。请注意：不同文件中选择的**列数必须一致**，且**顺序要一一对应**。")
                
                file_cols_map = {}
                dfs_map = {}
                cols_config = st.columns(len(files))
                selected_keys_list = [] # 存储每个文件选中的列列表 [ ['ID', 'Date'], ['uid', 'time'] ]
                
                try:
                    # 1. 预读取与UI生成
                    for i, f in enumerate(files):
                        f.seek(0)
                        df_temp = load_data(f, sheet_name=0)
                        dfs_map[f.name] = df_temp
                        
                        with cols_config[i]:
                            st.markdown(f"**{f.name}**")
                            # 尝试智能识别
                            default_cols = []
                            for c in df_temp.columns:
                                if c.lower() in ['id', 'no', 'code', 'key', '工号', 'date', 'name', '姓名']:
                                    default_cols.append(c)
                            
                            # 改为 Multiselect (多选)
                            key_cols = st.multiselect(
                                f"选择关联键 (按顺序)", 
                                df_temp.columns, 
                                default=default_cols[:1], # 默认只选中识别到的第一个，避免太乱
                                key=f"key_{i}"
                            )
                            selected_keys_list.append(key_cols)

                    # 2. 参数设置
                    c_opt1, c_opt2 = st.columns(2)
                    with c_opt1:
                        join_how = st.selectbox("连接方式", ["inner (交集)", "left (左连接)", "outer (并集)"], index=1).split()[0]
                    with c_opt2:
                        st.write("") 
                        st.write("")
                        ignore_case = st.checkbox("忽略大小写匹配", value=False, help="选中后，所有关联列都会转为小写进行对比")

                    if st.button("开始横向关联"):
                        # 0. 校验逻辑：检查用户是否选择了相同数量的列
                        base_keys = selected_keys_list[0]
                        if not base_keys:
                            st.error("请在第一个文件中至少选择一列作为关联键。")
                            st.stop()
                            
                        for i in range(1, len(files)):
                            if len(selected_keys_list[i]) != len(base_keys):
                                st.error(f"错误：文件 {files[i].name} 选了 {len(selected_keys_list[i])} 列，但第一个文件选了 {len(base_keys)} 列。请保持列数一致。")
                                st.stop()

                        # 1. 初始化基准表
                        base_df = dfs_map[files[0].name]
                        
                        # 处理基准表 Key (循环处理每一列)
                        for k in base_keys:
                            if ignore_case:
                                base_df[k] = base_df[k].astype(str).str.lower().str.strip()
                            else:
                                base_df[k] = base_df[k].astype(str).str.strip()
                            
                        current_df = base_df
                        
                        # 2. 循环合并
                        for i in range(1, len(files)):
                            next_name = files[i].name
                            next_df = dfs_map[next_name]
                            next_keys = selected_keys_list[i] # 获取当前文件的 Key 列表
                            
                            # 处理当前表 Key
                            for k in next_keys:
                                if ignore_case:
                                    next_df[k] = next_df[k].astype(str).str.lower().str.strip()
                                else:
                                    next_df[k] = next_df[k].astype(str).str.strip()
                            
                            # 执行多列 Merge
                            # left_on 和 right_on 都可以接受列表
                            # 如果是第一次合并，left_on 是 base_keys
                            # 如果是后续合并，这里简化处理：假设都是围绕第一个文件的主键，或者链式主键名未变
                            # 最稳妥的方式：如果列名没变，可以直接用；如果变了，Pandas会保留两者。
                            
                            # 在链式合并中，如果 left_on 的列名在 merged_df 中因为重名变成了 x, y 后缀，会导致找不到列。
                            # 策略：我们假设用户是想把 file2, file3... 都挂载到 current_df 上。
                            # 第一次合并 left keys 是明确的。第二次合并时，我们依然尝试用 base_keys，
                            # 但如果 base_keys 在上一次合并中被重命名了，就会报错。
                            
                            # 为了稳定性，对于多表链式 Join，我们通常假设：
                            # Case A: 星型模式 (所有表都和表1关联)。 Left Keys = base_keys
                            # Case B: 链式模式 (表2关联表1，表3关联表2)。
                            
                            # 这里的实现采用 Case A (星型)，即不断把新表往大表上贴，且假设大表中依然保留着初始的主键列。
                            
                            current_df = pd.merge(
                                current_df, 
                                next_df, 
                                left_on=base_keys if i==1 else base_keys, # 简化策略：始终尝试匹配表1的主键
                                right_on=next_keys, 
                                how=join_how, 
                                suffixes=('', f'_{i}')
                            )

                        st.success(f"关联成功！使用了联合主键: {base_keys}")
                        st.dataframe(current_df.head(50), use_container_width=True)
                        st.download_button("下载关联结果", to_excel(current_df), "merged_multi_key_result_ives.xlsx")

                except KeyError as e:
                    st.error(f"合并失败：找不到指定的列。这通常是因为在之前的合并步骤中，列名因为重复被自动加上了后缀（如 id_1）。建议确保主键列在所有表中名称唯一，或尽量只合并两个大表。")
                except Exception as e:
                    st.error(f"发生错误: {e}")

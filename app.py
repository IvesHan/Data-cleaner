import streamlit as st
import pandas as pd
import io
import csv
import re

# --- 页面基础配置 ---
st.set_page_config(
    page_title="表格全能助手 (Pro)", 
    layout="wide", 
    page_icon="📊"
)

# --- 标题区 ---
st.title("📊 表格数据全能助手")
st.caption("Designed by Ives | Python Streamlit Pro Version")
st.divider()

# --- 侧边栏：一级模式 ---
st.sidebar.header("功能导航")
app_mode = st.sidebar.radio("请选择任务类型", ["单表处理 (清洗/筛选/透视)", "多表操作 (合并/关联)"])

# --- 核心工具函数 ---
def to_excel(df):
    """将 DataFrame 转换为 Excel 字节流"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output

def load_data_single(file, skip_rows, sep_mode, sheet_name=0):
    """
    单表专用加载函数 (复刻 HTML 版逻辑)
    支持：跳过行 -> 手动/自动分隔符 -> 生成表头
    """
    file.seek(0) # 重置指针，确保每次都能从头读取
    file_ext = file.name.split('.')[-1].lower()
    
    # 1. Excel 处理逻辑
    if file_ext in ['xlsx', 'xls']:
        return pd.read_excel(file, skiprows=skip_rows, sheet_name=sheet_name)
    
    # 2. 文本/CSV/TSV 处理逻辑
    else:
        # 映射分隔符
        sep = None # 默认为 None，让 Pandas (Python引擎) 自动嗅探
        if sep_mode == "逗号 (CSV)": sep = ","
        elif sep_mode == "制表符 (TSV)": sep = "\t"
        elif sep_mode == "分号 (;)": sep = ";"
        elif sep_mode == "竖线 (|)": sep = "|"
        elif sep_mode == "空格 ( )": sep = r"\s+" # 正则匹配空白
        
        # 使用 python 引擎以支持更灵活的分隔符处理 (类似 PapaParse)
        return pd.read_csv(file, sep=sep, skiprows=skip_rows, engine='python')

def load_data_multi(file):
    """多表合并专用简易加载器"""
    file.seek(0)
    ext = file.name.split('.')[-1].lower()
    if ext in ['xlsx', 'xls']:
        return pd.read_excel(file)
    else:
        # 多表默认尝试自动识别，简化流程
        return pd.read_csv(file, sep=None, engine='python')

# ========================================================
# 模式 1: 单表处理 (逻辑已升级对标 HTML Pro 版)
# ========================================================
if app_mode == "单表处理 (清洗/筛选/透视)":
    
    st.sidebar.subheader("📂 1. 文件导入")
    uploaded_file = st.sidebar.file_uploader("上传文件", type=['csv', 'xlsx', 'xls', 'tsv', 'txt'])
    
    if uploaded_file:
        file_ext = uploaded_file.name.split('.')[-1].lower()
        
        # --- 侧边栏：动态参数配置 ---
        with st.sidebar.expander("⚙️ 读取参数配置", expanded=True):
            # 1. 跳过行 (去除注释)
            skip_rows = st.number_input("跳过前 N 行 (去除注释)", min_value=0, value=0, help="如果文件前几行是说明文字，请增加此数值")
            
            # 2. Excel 专用：Sheet 选择
            selected_sheet = 0
            if file_ext in ['xlsx', 'xls']:
                try:
                    xl = pd.ExcelFile(uploaded_file)
                    if len(xl.sheet_names) > 1:
                        selected_sheet = st.selectbox("选择工作表", xl.sheet_names)
                    uploaded_file.seek(0) # 预读取后重置
                except: pass
            
            # 3. 文本专用：分隔符选择 (核心升级点)
            sep_mode = "自动识别 (Auto)"
            if file_ext not in ['xlsx', 'xls']:
                st.write("---")
                sep_mode = st.selectbox(
                    "列分隔符 (Delimiter)", 
                    ["自动识别 (Auto)", "逗号 (CSV)", "制表符 (TSV)", "分号 (;)", "竖线 (|)", "空格 ( )"]
                )

        # --- 数据加载与主界面 ---
        try:
            # 调用升级版加载函数
            df_raw = load_data_single(uploaded_file, skip_rows, sep_mode, sheet_name=selected_sheet)
            
            st.sidebar.success(f"✅ 读取成功: {len(df_raw)} 行")

            # Tab 分区
            tab_clean, tab_pivot = st.tabs(["🧹 数据清洗", "📊 数据透视"])
            
            # [Tab 1: 清洗流水线]
            with tab_clean:
                col_left, col_right = st.columns([3, 1])
                
                # 1. 列选择与排序
                with col_left:
                    st.subheader("1. 列选择")
                    all_cols = df_raw.columns.tolist()
                    selected_cols = st.multiselect("保留列 (默认全选)", all_cols, default=all_cols)
                    if not selected_cols: selected_cols = all_cols
                
                with col_right:
                    st.subheader("2. 排序")
                    sort_col = st.selectbox("排序依据", ["(无)"] + selected_cols)
                    sort_asc = st.checkbox("升序", value=True)

                # 初步处理
                df_step1 = df_raw[selected_cols].copy()
                if sort_col != "(无)":
                    df_step1 = df_step1.sort_values(by=sort_col, ascending=sort_asc)

                # 2. 内容筛选 (Filter)
                st.subheader("3. 内容筛选")
                df_result = df_step1.copy()
                
                with st.container(border=True):
                    f_c1, f_c2 = st.columns([1, 3])
                    with f_c1:
                        filter_target = st.selectbox("筛选列", ["(无)"] + selected_cols)
                    
                    if filter_target != "(无)":
                        with f_c2:
                            # 数值类型：范围滑块
                            if pd.api.types.is_numeric_dtype(df_step1[filter_target]):
                                min_v = float(df_step1[filter_target].min())
                                max_v = float(df_step1[filter_target].max())
                                rng = st.slider("数值范围", min_v, max_v, (min_v, max_v))
                                df_result = df_step1[(df_step1[filter_target] >= rng[0]) & (df_step1[filter_target] <= rng[1])]
                            # 文本类型：多值输入
                            else:
                                text_input = st.text_area("输入筛选关键词 (支持逗号、空格、换行分隔)", height=68)
                                match_mode = st.radio("匹配模式", ["模糊包含 (Contains)", "精确匹配 (Is In)"], horizontal=True)
                                
                                if text_input.strip():
                                    keys = [k for k in re.split(r'[,\s;，；|\n]+', text_input.strip()) if k]
                                    if keys:
                                        if match_mode == "精确匹配 (Is In)":
                                            df_result = df_step1[df_step1[filter_target].astype(str).isin(keys)]
                                        else: # 模糊
                                            pattern = "|".join([re.escape(k) for k in keys])
                                            df_result = df_step1[df_step1[filter_target].astype(str).str.contains(pattern, case=False, na=False)]

                # 3. 行截取
                st.subheader("4. 行截取 (Slice)")
                curr_len = len(df_result)
                if curr_len > 0:
                    c_s, c_e = st.columns(2)
                    slice_start = c_s.number_input("起始行", 0, curr_len-1, 0)
                    slice_end = c_e.number_input("结束行", slice_start+1, curr_len, curr_len)
                    df_result = df_result.iloc[slice_start:slice_end]

                # 4. 结果与导出
                st.divider()
                st.subheader(f"✅ 结果预览 ({len(df_result)} 行)")
                st.dataframe(df_result, use_container_width=True)
                
                d1, d2 = st.columns(2)
                fname = uploaded_file.name.split('.')[0]
                d1.download_button("📥 下载 Excel", to_excel(df_result), f"{fname}_cleaned.xlsx")
                d2.download_button("📥 下载 CSV", df_result.to_csv(index=False).encode('utf-8-sig'), f"{fname}_cleaned.csv", "text/csv")

            # [Tab 2: 数据透视]
            with tab_pivot:
                if not df_raw.empty:
                    p1, p2, p3, p4 = st.columns(4)
                    idx = p1.multiselect("行维度 (Index)", df_raw.columns)
                    cols = p2.multiselect("列维度 (Columns)", df_raw.columns)
                    vals = p3.multiselect("数值 (Values)", df_raw.columns)
                    agg = p4.selectbox("聚合算法", ["sum", "mean", "count", "nunique", "max", "min"])
                    
                    if idx and vals:
                        try:
                            pt = pd.pivot_table(df_raw, index=idx, columns=cols if cols else None, values=vals, aggfunc=agg)
                            st.dataframe(pt, use_container_width=True)
                            st.download_button("📥 导出透视表", to_excel(pt), f"{fname}_pivot.xlsx")
                        except Exception as e: st.error(f"透视失败: {e}")
                    else:
                        st.info("请至少选择【行维度】和【数值】。")

        except Exception as e:
            st.error(f"❌ 文件解析失败: {e}")
            st.warning("建议：如果是 CSV/TSV 文件，请尝试在侧边栏调整“跳过前 N 行”或手动指定“列分隔符”。")

# ========================================================
# 模式 2: 多表操作 (保持 Grid 布局与高级逻辑)
# ========================================================
elif app_mode == "多表操作 (合并/关联)":
    
    st.subheader("📚 多文件批处理")
    
    # 模式选择卡片
    with st.container(border=True):
        c_m1, c_m2 = st.columns([1, 2])
        with c_m1:
            st.write("###### 选择操作模式")
            op_type = st.radio("op_type", ["纵向堆叠 (Concat)", "横向关联 (Join/Merge)"], label_visibility="collapsed")
        with c_m2:
            st.write("###### 批量上传文件")
            files = st.file_uploader("支持 Excel/CSV/TSV 混传", accept_multiple_files=True, label_visibility="collapsed")

    if files:
        if len(files) < 2:
            st.warning("⚠️ 请至少上传 2 个文件。")
        else:
            # --- 纵向堆叠 ---
            if "纵向" in op_type:
                if st.button("🚀 开始纵向合并", type="primary", use_container_width=True):
                    dfs = []
                    bar = st.progress(0)
                    for i, f in enumerate(files):
                        try:
                            d = load_data_multi(f)
                            d['_来源文件'] = f.name
                            dfs.append(d)
                        except: st.error(f"{f.name} 读取失败")
                        bar.progress((i+1)/len(files))
                    
                    if dfs:
                        res = pd.concat(dfs, ignore_index=True)
                        st.success(f"合并完成！共 {len(res)} 行")
                        st.dataframe(res.head(100), use_container_width=True)
                        st.download_button("下载结果", to_excel(res), "concat_result.xlsx")

            # --- 横向关联 (Star Join) ---
            else:
                st.markdown("##### 🔗 关联配置")
                
                # 预读取与 Grid 布局
                dfs_map = {}
                file_names = []
                key_selectors = [None] * len(files)
                
                # 每行显示 3 个文件
                cols = st.columns(3)
                
                for i, f in enumerate(files):
                    f.seek(0)
                    df = load_data_multi(f)
                    dfs_map[f.name] = df
                    file_names.append(f.name)
                    
                    with cols[i % 3]:
                        with st.container(border=True):
                            # 主表高亮
                            if i == 0:
                                st.markdown(f"**👑 主表: {f.name}**")
                            else:
                                st.markdown(f"**📑 附表 {i}: {f.name}**")
                            
                            st.caption(f"{df.shape[0]} 行, {df.shape[1]} 列")
                            
                            # 智能推荐 Key
                            defaults = [c for c in df.columns if c.lower() in ['id','uid','no','key','code','工号','编号','name','姓名']]
                            
                            # 多选 Key
                            key_selectors[i] = st.multiselect(
                                "选择关联键 (Key)", 
                                df.columns, 
                                default=defaults[:1],
                                key=f"k_{i}"
                            )

                st.divider()
                
                # 全局配置
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    join_how = st.selectbox("连接方式", ["left (以主表为准)", "inner (只留交集)", "outer (保留所有)"]).split()[0]
                with c2:
                    st.write("") 
                    st.write("")
                    ignore_case = st.checkbox("忽略大小写", value=True)
                with c3:
                    st.write("")
                    st.write("")
                    do_merge = st.button("🚀 开始横向关联", type="primary", use_container_width=True)

                # 执行合并逻辑
                if do_merge:
                    base_keys = key_selectors[0]
                    if not base_keys:
                        st.error("❌ 主表未选择关联键！")
                        st.stop()
                    
                    # 初始化结果
                    result_df = dfs_map[file_names[0]].copy()
                    
                    # 清洗主表 Key
                    for k in base_keys:
                        if ignore_case: result_df[k] = result_df[k].astype(str).str.lower().str.strip()
                        else: result_df[k] = result_df[k].astype(str).str.strip()
                    
                    # 循环合并
                    bar = st.progress(0)
                    for i in range(1, len(files)):
                        fname = file_names[i]
                        curr_df = dfs_map[fname].copy()
                        curr_keys = key_selectors[i]
                        
                        if len(curr_keys) != len(base_keys):
                            st.error(f"❌ 列数不一致：主表选了 {len(base_keys)} 列，{fname} 选了 {len(curr_keys)} 列。")
                            st.stop()
                            
                        # 清洗当前表 Key
                        for k in curr_keys:
                            if ignore_case: curr_df[k] = curr_df[k].astype(str).str.lower().str.strip()
                            else: curr_df[k] = curr_df[k].astype(str).str.strip()
                            
                        # Merge
                        try:
                            result_df = pd.merge(
                                result_df,
                                curr_df,
                                left_on=base_keys,
                                right_on=curr_keys,
                                how=join_how,
                                suffixes=('', f'_{i}')
                            )
                        except Exception as e:
                            st.error(f"关联 {fname} 失败: {e}")
                            st.stop()
                        
                        bar.progress(i/(len(files)-1))
                    
                    bar.progress(1.0)
                    st.success(f"✅ 关联成功！结果共 {len(result_df)} 行。")
                    st.dataframe(result_df.head(100), use_container_width=True)
                    st.download_button("📥 下载结果", to_excel(result_df), "merged_result.xlsx")

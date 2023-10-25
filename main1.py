import streamlit as st
import pandas as pd
import folium
import io
from streamlit_folium import folium_static
import requests
import json
#import ast
import crawling
from PIL import Image
import os

AK= "iNcU8nqYs08Le0v8k9zehlCIOEXWEw7o"
output = "json"

#=======================以下是各类函数============================
def WGS_to_bd(coord):
    x = coord[0]
    y = coord[1]
    service = "http://api.map.baidu.com/geoconv/v1/?"
    f = 1; t = 5
    parameters = f"coords={x},{y}&from={f}&to={t}&ak={AK}"
    url = service + parameters
    response = requests.get(url)
    s=response.text
    dic=json.loads(s)
    return [dic["result"][0]["x"],dic["result"][0]["y"]]

#坐标纠差
def rectify(lng,lat):
    #对地理编码得到的坐标进行转换，并计算偏差
    d_lng = lng - WGS_to_bd([lng,lat])[0]
    d_lat = lat - WGS_to_bd([lng,lat])[1]
    #根据偏差对坐标进行纠偏
    WGS_lng = lng + d_lng
    WGS_lat = lat + d_lat
    return [WGS_lng,WGS_lat]

def get_location(address):
    service ="http://api.map.baidu.com/geocoding/v3/?"
    city="上海市"
    parameters = f"address={address}&output={output}&ak={AK}&city={city}"
    url = service + parameters
    response = requests.get(url)
    text=response.text
    dic=json.loads(text)
    status = dic["status"]
    if status==0:
        lng = dic["result"]["location"]["lng"]
        lat = dic["result"]["location"]["lat"]
        [WGS_lng,WGS_lat]=rectify(lng,lat)
        return [WGS_lng,WGS_lat]
    else:
        print(f"{address}:地理编码不成功")
        return["unknown","unknown"]





#====================以下是页面设计部分===============================
# 设置页面标题和导航栏
st.set_page_config(page_title="上海部分房源可视化及生态评价", page_icon=":house:", layout="wide")
menu = ["二手房数据爬取","闵行区二手房可视化", "景观生态风险评估"]
choice = st.sidebar.selectbox("选择功能", menu)

#显示界面1
if choice == "二手房数据爬取":
    st.title("链家二手房数据获取")
    st.write("通过输入目标地区的链家网址（url）,生成houseInfo2.xlsx二手房数据， houseInfo.xlsx为闵行区二手房数据，已爬取生成")
    page_url= st.text_input("请输入链家二手房地区网页的URL：","https://sh.lianjia.com/ershoufang/minhang/")
    if page_url:
        if st.button("开始爬取数据"):
            # 调用爬虫程序
            data1,data2 = crawling.run(page_url)
            st.success('数据已保存到houseInfo2.xlsx中')
            # 显示数据摘要
            st.write('数据摘要：')
            st.write(data1.describe())
# 显示页面2
if choice == "闵行区二手房可视化":
    st.title("闵行区二手房可视化")
    st.write("展示闵行区所有二手房的相关信息，通过输入对房价、面积的范围，筛选出符合条件的房源，并在地图上可视化，直观体现位置分布")
    st.write("***运行可能较慢，请耐心等待")
    # 读取Excel文件
    #Excel文件是通过crawling.py文件爬取，也可以爬取生成其他地区的二手房数据
    excel_file = st.file_uploader("上传链家数据文件（已通过crawling.py爬取有houseInfo.xlsx，可以个性化生成二手房数据）", type="xlsx")
    if excel_file is not None:
        excel_data = io.BytesIO(excel_file.read())
        df1 = pd.read_excel(excel_data)
        st.write(df1)
        st.subheader("筛选查询")
        min_price = st.text_input("最低总价（万元）","100")
        max_price = st.text_input("最高总价（万元）","2000")
        min_area = st.text_input("最小面积（平方米）","50")
        max_area = st.text_input("最大面积（平方米）","500")
        exp1 = df1["总价"].apply(lambda x:x[0:-1]).astype('float') > float(min_price)
        exp2 = df1["总价"].apply(lambda x:x[0:-1]).astype('float') < float(max_price)
        exp3 = df1["面积"].apply(lambda x:x[0:-2]).astype('float') > float(min_area)
        exp4 = df1["面积"].apply(lambda x:x[0:-2]).astype('float') < float(max_area)
        exp = exp1 & exp2 & exp3 & exp4
        subset = df1[exp]
        #st.button("确定")
        
        # 显示符合条件的子集的记录数
        st.title(f"共有{subset.shape[0]} 套房符合要求")
        st.dataframe(subset)
        #读取房源的经纬度信息
        df2=pd.read_excel(excel_data,sheet_name="Sheet2")
        #解决多套房源同属一个小区的问题，合并同位置房源信息
        def concat_func(x):
           return pd.Series({
            '总价':','.join(x['总价'].unique()),
            '户型':','.join(x['户型'].unique()),
            '面积':','.join(x["面积"].unique()),
            'lng,lat':','.join(x["lng,lat"].unique())
        }
        )
        merge_df=pd.merge(subset,df2,on="位置")
        result=merge_df.groupby(merge_df['位置']).apply(concat_func).reset_index()
       # 获取符合条件的房源坐标,对编码失败的位置进行剔除
        result = result[~result['lng,lat'].isin(["['unknown', 'unknown']"])]
       # 对经纬度列进行处理，拆分为经度和纬度两列，并转换为float类型
        result[['lng', 'lat']] = result['lng,lat'].apply(lambda x: pd.Series(eval(x)))
        result = result.drop('lng,lat', axis=1)  # 删除原始经纬度列
           
       # 创建地图
        m = folium.Map(location=[31.031557,121.453679], zoom_start=14)
       
        
       # 添加marker和popup
        for i, row in result.iterrows():
            location = [row['lat'], row['lng']]
            popup = folium.Popup(f"位置：{row['位置']}<br>总价：{row['总价']}<br>户型：{row['户型']}<br>面积：{row['面积']}", max_width=300)
            folium.Marker(location=location, popup=popup).add_to(m)  
            
        # 获取用户输入的经纬度
        address = st.text_input("请输入您想查询的位置","闵行区吴泾镇东川路500号")
        lat = get_location(address)[1]
        lng = get_location(address)[0]
        st.button("确定")
        # 在地图上显示符合条件的房源
        st.write("您查询的位置（红）周边合适的房源地图如下：")
        # 根据用户输入的经纬度生成不同颜色的标记
        marker_color = 'red' 

        # 创建标记对象
        t = folium.Marker(
            location=[lat, lng],
            icon=folium.Icon(color='red')
        )

        # 将标记添加到地图对象
        t.add_to(m)
        # 显示地图
        folium_static(m)
    else:
        st.write("请上传Excel文件")
                




# 显示页面3
if choice == "景观生态风险评估":
    # 获取当前脚本的目录路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    st.title("上海市景观生态风险评估")
    st.write("展示基于土地利用类型的景观生态风险评估结果")
    
    # 下拉选择年份和展示内容
    year_menu = ["2005","2010", "2015","2018", "2020"]
    selected_year = st.selectbox("选择年份", year_menu)
    
    landscape_menu = ["土地利用图", "生态风险指数分布图", "数据表格"]
    landscape_choice = st.selectbox("选择展示内容", landscape_menu)
    
    # 根据选择的年份和展示内容构建文件路径
    image_path = os.path.join(script_dir, f"{selected_year}_{landscape_choice.lower().replace(' ', '_')}.png")
    
    # 读取并显示图像
    image = Image.open(image_path)
    st.image(image, caption=f"{selected_year}年 {landscape_choice}")

        
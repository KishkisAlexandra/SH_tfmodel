# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Константы
# ------------------------
SCENARIOS = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}

DEFAULT_TARIFFS = {
    "electricity_BYN_per_kWh": 0.254,
    "water_BYN_per_m3": 1.7858,
    "sewage_BYN_per_m3": 0.9586,
    "heating_BYN_per_Gcal": 135.0,
    "fixed_fees_BYN": 5.0
}

DEFAULT_COEFFS = {
    "elec_base_kWh": 60.0,          
    "elec_per_person_kWh": 75.0,    
    "elec_per_m2_kWh": 0.5,         
    "water_per_person_m3": 4.5,     
    "hot_water_fraction": 0.6,      
    "heating_Gcal_per_m2_season_mid": 0.15, 
    "heating_season_months": 7.0
}

HOUSE_COEFS = {
    "Новый": {"heating": 1.0, "electricity": 1.0},
    "Средний": {"heating": 1.05, "electricity": 1.05},
    "Старый": {"heating": 1.1, "electricity": 1.05},
}
REALISM_UPLIFT = 1.07
CATEGORIES = ["Электроэнергия", "Вода", "Канализация", "Отопление", "Фикс. платежи"]
HEATING_MONTHS = [1,2,3,4,10,11,12]

# ------------------------
# Функции расчёта
# ------------------------
def calculate_volumes(area_m2, occupants, behavior_factor, coeffs=DEFAULT_COEFFS, month=1):
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2) * behavior_factor
    water = coeffs["water_per_person_m3"]*occupants*behavior_factor
    hot_water = water * coeffs["hot_water_fraction"]
    sewage = water
    if month in HEATING_MONTHS:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    else:
        heat_monthly = 0.0
    return {
        "Электроэнергия": round(elec,1),
        "Вода": round(water,2),
        "Горячая вода": round(hot_water,2),
        "Канализация": round(sewage,2),
        "Отопление": round(heat_monthly,3)
    }

def calculate_costs_from_volumes(volumes, tariffs, area_m2=50, occupants=1, floor=1, has_elevator=True, subsidy=False, subsidy_rate=0.2):
    t = tariffs.copy()
    if subsidy:
        t["heating_BYN_per_Gcal"] *= subsidy_rate

    elec_cost = volumes["Электроэнергия"] * t["electricity_BYN_per_kWh"]
    water_cost = volumes["Вода"] * t["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * t["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * t["heating_BYN_per_Gcal"]

    # Фиксированные платежи
    maintenance_max = 0.0388
    lighting_max = 0.0249
    waste_norm = 0.2092
    elevator_max = 0.88
    capital_repair_rate = 0.05

    maintenance_cost = area_m2 * maintenance_max
    lighting_cost = area_m2 * lighting_max
    waste_cost = waste_norm * occupants
    capital_repair_cost = area_m2 * capital_repair_rate
    elevator_cost = elevator_max * occupants if has_elevator and floor >= 2 else 0.0

    fixed = maintenance_cost + lighting_cost + waste_cost + capital_repair_cost + elevator_cost

    costs = {
        "Электроэнергия": round(elec_cost,2),
        "Вода": round(water_cost,2),
        "Канализация": round(sewage_cost,2),
        "Отопление": round(heat_cost,2),
        "Фикс. платежи": round(fixed,2)
    }
    costs["Итого"] = round(sum(costs.values()),2)
    return costs

def apply_neighbor_adjustment(volumes, tariffs, house_category, area_m2, occupants, floor=1, has_elevator=True):
    coefs = HOUSE_COEFS.get(house_category, {"heating":1.0,"electricity":1.0})
    vol_adj = volumes.copy()
    vol_adj["Электроэнергия"] = vol_adj["Электроэнергия"] * coefs["electricity"]
    vol_adj["Отопление"] = vol_adj["Отопление"] * coefs["heating"]
    neighbor_costs = calculate_costs_from_volumes(vol_adj, tariffs, area_m2, occupants, floor, has_elevator)
    neighbor_costs = {k: round(v * REALISM_UPLIFT, 2) for k, v in neighbor_costs.items()}
    return neighbor_costs

# ------------------------
# Sidebar: параметры семьи
# ------------------------
st.sidebar.header("Параметры семьи")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,1)
occupants = adults + children

scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[scenario]
house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)

st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф")
subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05) if use_subsidy else 1.0

# ------------------------
# Ввод реальных расходов
# ------------------------
st.header("📊 Введите ваши реальные расходы за месяц (BYN)")
with st.expander("Показать поля для ручного ввода"):
    user_real = {cat: st.number_input(f"{cat} BYN", min_value=0.0, value=0.0, step=0.1, format="%.2f") for cat in CATEGORIES}
user_real["Итого"] = round(sum(user_real.values()), 2)

# ------------------------
# Расчёт идеального и среднего соседа
# ------------------------
ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
ideal_costs = calculate_costs_from_volumes(ideal_vol, DEFAULT_TARIFFS, area_m2, occupants)

neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
neighbor_costs = apply_neighbor_adjustment(neighbor_vol, DEFAULT_TARIFFS, house_category, area_m2, occupants)

# ------------------------
# Визуализация
# ------------------------
st.header("🏠 Сравнение расходов")
col1, col2 = st.columns([2, 2])

with col1:
    st.metric("Идеальный расчёт по нормативам, BYN", f"{ideal_costs['Итого']:.2f}")
    st.metric("Ваши реальные расходы, BYN", f"{user_real['Итого']:.2f}")
    st.metric("Средний сосед, BYN", f"{neighbor_costs['Итого']:.2f}")

with col2:
    detail_df = pd.DataFrame({
        "Категория": CATEGORIES,
        "Идеальный расчёт (BYN)": [ideal_costs[c] for c in CATEGORIES],
        "Ваши реальные данные (BYN)": [user_real[c] for c in CATEGORIES],
        "Средний сосед (BYN)": [neighbor_costs[c] for c in CATEGORIES],
    })
    st.dataframe(detail_df.style.format({
        "Идеальный расчёт (BYN)": "{:.2f}",
        "Ваши реальные данные (BYN)": "{:.2f}",
        "Средний сосед (BYN)": "{:.2f}"
    }).background_gradient(cmap='Blues'), height=300)

# ------------------------
# График расходов
# ------------------------
plot_df = pd.DataFrame({
    "Категория": CATEGORIES * 3,
    "Тип": (['Идеальный расчёт']*len(CATEGORIES)) + (['Ваши реальные данные']*len(CATEGORIES)) + (['Средний сосед']*len(CATEGORIES)),
    "BYN": [ideal_costs[c] for c in CATEGORIES] + [user_real[c] for c in CATEGORIES] + [neighbor_costs[c] for c in CATEGORIES]
})
fig = px.bar(plot_df, x="Категория", y="BYN", color="Тип", barmode="group",
             color_discrete_map={"Идеальный расчёт":"#636EFA","Ваши реальные данные":"#00CC96","Средний сосед":"#EF553B"},
             text="BYN")
fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig.update_layout(yaxis_title="BYN / месяц", legend_title_text="Показатель", uniformtext_minsize=8)
st.plotly_chart(fig, use_container_width=True)

# ------------------------
# Рекомендации
# ------------------------
st.header("💡 Рекомендации по оптимизации расходов")

# Эмодзи для категорий
emoji_map = {
    "Электроэнергия": "💡",
    "Вода": "🚰",
    "Отопление": "🔥",
    "Канализация": "💧"
}

# Возможные советы по категориям
tips_map = {
    "Электроэнергия": [
        "Проверьте энергопотребление бытовых приборов.",
        "Используйте энергосберегающие лампы и устройства.",
        "Подумайте о внедрении систем умного дома для контроля расхода."
    ],
    "Вода": [
        "Установите аэраторы на краны и душ.",
        "Используйте экономичные смесители и сантехнику.",
        "Проверяйте трубы и сантехнику на протечки."
    ],
    "Отопление": [
        "Закрывайте окна при включенном отоплении.",
        "Проверяйте терморегуляторы на радиаторах.",
        "Используйте утеплители и теплоизоляцию для снижения потерь."
    ],
    "Канализация": [
        "Используйте рациональное количество воды для смыва.",
        "Следите за исправностью сантехники, чтобы избежать утечек.",
        "Регулярно очищайте фильтры и сифоны."
    ]
}

# Формируем рекомендации динамически
for cat in ["Электроэнергия","Вода","Отопление","Канализация"]:
    diff_from_norm = user_real[cat] - ideal_costs[cat]
    diff_from_neighbor = user_real[cat] - neighbor_costs[cat]

    if diff_from_norm > 0:
        main_tip = f"Ваш расход на {abs(diff_from_norm):.2f} BYN выше нормативного — обратите внимание на {tips_map[cat][0].lower()}"
    else:
        main_tip = f"Расход ниже нормативного — продолжайте использовать ресурсы эффективно."

    if diff_from_neighbor > 0:
        extra_tip = f"Ваш расход на {abs(diff_from_neighbor):.2f} BYN выше среднего соседа — рассмотрите {tips_map[cat][1].lower()}."
    else:
        extra_tip = f"Ваш расход ниже среднего соседа — вы опережаете соседей в экономии."

    # Случайная дополнительная рекомендация
    import random
    random_tip = random.choice(tips_map[cat][2:])

    st.markdown(f"""
        <div style='border-left: 4px solid #1F77B4; padding: 12px; margin-bottom:8px; background-color:#F0F8FF; border-radius:5px'>
            <h4 style='margin:0'>{emoji_map[cat]} {cat}</h4>
            <p style='margin:4px 0 0 0'>{main_tip}</p>
            <p style='margin:2px 0 0 0; color:#555'>{extra_tip}</p>
            <p style='margin:2px 0 0 0; font-style:italic; color:#888'>{random_tip}</p>
        </div>
    """, unsafe_allow_html=True)

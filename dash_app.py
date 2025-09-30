# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Константы и тарифы
# ------------------------
SCENARIOS = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}

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

HEATING_MONTHS = [1,2,3,4,10,11,12]  # месяцы, в которых считается отопление

# Тарифы для физических лиц
ELECTRICITY_FULL = 0.2969
ELECTRICITY_SUBSIDY = 0.2412
HEATING_FULL = 134.94
HEATING_SUBSIDY = 24.7187
WATER_TARIFF = 1.7858
SEWAGE_TARIFF = 0.9586
FIXED_FEES = 5.0

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

def calculate_costs_from_volumes(volumes, tariffs, area_m2=50, occupants=1, floor=1, has_elevator=True):
    elec_cost = volumes["Электроэнергия"] * tariffs["electricity_BYN_per_kWh"]
    water_cost = volumes["Вода"] * tariffs["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * tariffs["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * tariffs["heating_BYN_per_Gcal"]

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
children = st.sidebar.number_input("Дети", 0,10,2)
occupants = adults + children

# Средний сосед
scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[scenario]
house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)

# Льгота пользователя
st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф (дополнительно к субсидированному)")
if use_subsidy:
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05)
else:
    subsidy_rate = 1.0

# ------------------------
# Ввод реальных расходов
# ------------------------
st.header("📊 Введите ваши реальные расходы за месяц (BYN)")
with st.expander("Показать поля для ручного ввода"):
    user_real = {
        "Электроэнергия": st.number_input("Электроэнергия BYN", min_value=0.0, value=0.0, step=1.0, format="%.2f"),
        "Вода": st.number_input("Вода BYN", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
        "Канализация": st.number_input("Канализация BYN", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
        "Отопление": st.number_input("Отопление BYN", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
        "Фикс. платежи": st.number_input("Фикс. платежи BYN", min_value=0.0, value=0.0, step=0.1, format="%.2f")
    }
user_real["Итого"] = round(sum(user_real[k] for k in CATEGORIES), 2)

# ------------------------
# Расчёт идеального и среднего соседа
# ------------------------
ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
ideal_costs = calculate_costs_from_volumes(ideal_vol, {
    "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY,
    "water_BYN_per_m3": WATER_TARIFF,
    "sewage_BYN_per_m3": SEWAGE_TARIFF,
    "heating_BYN_per_Gcal": HEATING_SUBSIDY,
    "fixed_fees_BYN": FIXED_FEES
}, area_m2, occupants)

# Тариф для среднего соседа с поведением + льгота
neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
neighbor_tariffs = {
    "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY * subsidy_rate,
    "water_BYN_per_m3": WATER_TARIFF,
    "sewage_BYN_per_m3": SEWAGE_TARIFF,
    "heating_BYN_per_Gcal": HEATING_SUBSIDY * subsidy_rate,
    "fixed_fees_BYN": FIXED_FEES
}
neighbor_costs = apply_neighbor_adjustment(neighbor_vol, neighbor_tariffs, house_category, area_m2, occupants)

# ------------------------
# Визуализация расходов
# ------------------------
st.header("🏠 Сравнение расходов")
col1, col2 = st.columns([2, 1])

with col1:
    st.metric("Идеальный расчёт по нормативам, BYN", f"{ideal_costs['Итого']:.2f}")
    st.metric("Ваши реальные расходы, BYN", f"{user_real['Итого']:.2f}")
    st.metric("Средний сосед, BYN", f"{neighbor_costs['Итого']:.2f}")

    ideal_total = ideal_costs.get("Итого", 0.0) or 0.0
    neighbor_total = neighbor_costs.get("Итого", 0.0) or 0.0
    real_total = user_real["Итого"]

    diff_real = round((real_total/ideal_total-1)*100,1) if ideal_total>0 else 0.0
    diff_neighbor = round((real_total/neighbor_total-1)*100,1) if neighbor_total>0 else 0.0

    st.info(f"Ваши реальные расходы на {diff_real}% {'выше' if diff_real>0 else 'ниже'} нормативного расчёта.")
    st.info(f"Ваши реальные расходы на {diff_neighbor}% {'выше' if diff_neighbor>0 else 'ниже'} среднего соседа.")

with col2:
    # Создаем DataFrame с детализацией расходов
    detail_df = pd.DataFrame({
        "Категория": CATEGORIES,
        "Идеальный расчёт (BYN)": [ideal_costs[c] for c in CATEGORIES],
        "Ваши реальные данные (BYN)": [user_real[c] for c in CATEGORIES],
        "Средний сосед (BYN)": [neighbor_costs[c] for c in CATEGORIES],
    })

    # Стилизация таблицы с градиентом BuPu
    styled_df = detail_df.style.format({
        "Идеальный расчёт (BYN)": "{:.2f}",
        "Ваши реальные данные (BYN)": "{:.2f}",
        "Средний сосед (BYN)": "{:.2f}"
    }).background_gradient(
        subset=["Идеальный расчёт (BYN)", "Ваши реальные данные (BYN)", "Средний сосед (BYN)"],
        cmap="BuPu"  # палитра BuPu
    ).set_properties(**{
        'text-align': 'center',
        'font-size': '14px'
    }).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-size', '15px'), ('background-color', '#f0f0f0')]}
    ])

    # Отображаем таблицу
    st.dataframe(styled_df, height=280)


# ------------------------
# График расходов
# ------------------------
plot_df = pd.DataFrame({
    "Категория": CATEGORIES * 3,
    "Тип": (["Идеальный расчёт"] * len(CATEGORIES)) + (["Ваши реальные данные"] * len(CATEGORIES)) + (["Средний сосед"] * len(CATEGORIES)),
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
st.header("💡 Рекомендации")
emoji_map = {"Электроэнергия":"💡","Вода":"🚰","Отопление":"🔥","Канализация":"💧"}
tips_map = {
    "Электроэнергия":"используйте энергосберегающие лампы и приборы.",
    "Вода":"установите аэраторы и проверьте трубы на протечки.",
    "Отопление":"закрывайте окна и проверьте терморегуляторы.",
    "Канализация":"контролируйте расход воды и исправность сантехники."
}
def get_color(diff):
    if diff > 0: return "#FFCDD2"
    else: return "#C8E6C9"

cols = st.columns(4)
for i, cat in enumerate(["Электроэнергия","Вода","Отопление","Канализация"]):
    diff = user_real[cat] - ideal_costs[cat]
    percent_over = round(diff/ideal_costs[cat]*100,1) if ideal_costs[cat]>0 else 0
    if diff > 0:
        msg = f"Перерасход {percent_over}% — {tips_map[cat]}"
    else:
        msg = "Расход в норме"
    with cols[i]:
        st.markdown(f"""
            <div style='padding:12px; border-radius:10px; background-color:{get_color(diff)};
                        font-size:0.9em; text-align:center;'>
                <div style='font-size:1.5em'>{emoji_map[cat]}</div>
                <strong>{cat}</strong>
                <div style='margin-top:6px'>{msg}</div>
            </div>
        """, unsafe_allow_html=True)

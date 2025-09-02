# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Константы
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
HEATING_MONTHS = [1,2,3,4,10,11,12]

# ------------------------
# Тарифы
# ------------------------
SUBSIDIZED_TARIFFS = {
    "electricity_BYN_per_kWh": 0.2412,
    "heating_BYN_per_Gcal": 24.7187
}

FULL_TARIFFS = {
    "electricity_BYN_per_kWh": 0.2969,
    "heating_BYN_per_Gcal": 134.94
}

# Остальные тарифы (вода, канализация, фикс.платежи)
DEFAULT_TARIFFS = {
    "water_BYN_per_m3": 1.7858,
    "sewage_BYN_per_m3": 0.9586,
    "fixed_fees_BYN": 5.0
}

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

scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[scenario]
house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)

# ------------------------
# Выбор тарифов
# ------------------------
st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф для физических лиц", value=True)

tariffs = DEFAULT_TARIFFS.copy()
if use_subsidy:
    tariffs["electricity_BYN_per_kWh"] = SUBSIDIZED_TARIFFS["electricity_BYN_per_kWh"]
    tariffs["heating_BYN_per_Gcal"] = SUBSIDIZED_TARIFFS["heating_BYN_per_Gcal"]
else:
    tariffs["electricity_BYN_per_kWh"] = FULL_TARIFFS["electricity_BYN_per_kWh"]
    tariffs["heating_BYN_per_Gcal"] = FULL_TARIFFS["heating_BYN_per_Gcal"]

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
# Расчёт
# ------------------------
ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
ideal_costs = calculate_costs_from_volumes(ideal_vol, FULL_TARIFFS, area_m2, occupants)

neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
neighbor_costs = apply_neighbor_adjustment(neighbor_vol, tariffs, house_category, area_m2, occupants)

# ------------------------
# Сравнение расходов
# ------------------------
st.header("🏠 Сравнение расходов")
col1, col2 = st.columns([2, 1])

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
    st.dataframe(detail_df.style.format("{:.2f}"), height=260)

# ------------------------
# График
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
# Рекомендации с прогресс-барами
# ------------------------
st.header("💡 Рекомендации (мини-дашборд)")

# Иконки категорий
emoji_map = {
    "Электроэнергия": "💡",
    "Вода": "🚰",
    "Отопление": "🔥",
    "Канализация": "💧"
}

tips_map = {
    "Электроэнергия": "Энергосберегающие приборы",
    "Вода": "Аэраторы и проверка труб",
    "Отопление": "Контроль температуры",
    "Канализация": "Следите за сантехникой"
}

def get_bar_color(percent):
    if percent < 0:
        return "#81C784"  # зеленый — расход ниже нормы
    elif percent < 20:
        return "#FFF176"  # желтый — небольшой перерасход
    else:
        return "#E57373"  # красный — большой перерасход

# Динамическая сетка карточек
cols = st.columns(len(emoji_map))
for i, cat in enumerate(["Электроэнергия","Вода","Отопление","Канализация"]):
    diff = user_real[cat] - ideal_costs[cat]
    percent_diff = round(diff / ideal_costs[cat] * 100, 1) if ideal_costs[cat] > 0 else 0.0
    bar_color = get_bar_color(percent_diff)
    
    with cols[i]:
        st.markdown(f"""
            <div style='padding:10px; border-radius:12px; background-color:#F5F5F5; 
                        text-align:center; min-width:120px;'>
                <div style='font-size:2em'>{emoji_map[cat]}</div>
                <strong>{cat}</strong>
                <div style='margin:6px 0; font-size:0.85em;'>{tips_map[cat]}</div>
                <div style='height:12px; border-radius:6px; background-color:#E0E0E0;'>
                    <div style='width:{min(max(percent_diff,0),100)}%; 
                                background-color:{bar_color}; 
                                height:12px; border-radius:6px;'></div>
                </div>
                <div style='margin-top:4px; font-size:0.8em;'>{percent_diff:+.1f}% от нормы</div>
            </div>
        """, unsafe_allow_html=True)

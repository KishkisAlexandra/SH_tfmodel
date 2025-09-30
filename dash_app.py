# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Константы и тарифы
# ------------------------
SCENARIOS = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}

# Минск
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

CATEGORIES_MINSK = ["Электроэнергия", "Вода", "Канализация", "Отопление", "Фикс. платежи"]
CATEGORIES_LIMASSOL = ["Электроэнергия", "Вода", "Интернет", "Телефон", "IPTV", "Сервисный сбор"]

HEATING_MONTHS = [1,2,3,4,10,11,12]  # месяцы с отоплением

# Минск тарифы
ELECTRICITY_FULL = 0.2969
ELECTRICITY_SUBSIDY = 0.2412
HEATING_FULL = 134.94
HEATING_SUBSIDY = 24.7187
WATER_TARIFF = 1.7858
SEWAGE_TARIFF = 0.9586
FIXED_FEES = 5.0

# Лимассол тарифы
ELECTRICITY_EUR_PER_KWH = 0.242
WATER_BASE_EUR = 22.0
WATER_VOLUME_TARIFF_EUR = 0.9
WATER_NDS = 1.05
ELECTRICITY_NDS = 1.19
OTHER_NDS = 1.19
INTERNET_EUR = 20 * OTHER_NDS
PHONE_EUR = 20 * OTHER_NDS
IPTV_EUR = 10 * OTHER_NDS
SERVICE_MIN_EUR = 45 * OTHER_NDS
SERVICE_MAX_EUR = 125 * OTHER_NDS

# ------------------------
# Функции расчёта Минска
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
# Функция расчёта Лимассола
# ------------------------
def calculate_limassol_bill(electricity_kwh, water_m3, use_max_service=False, behavior_factor=1.0):
    electricity_cost = electricity_kwh * ELECTRICITY_EUR_PER_KWH * ELECTRICITY_NDS * behavior_factor
    water_cost = (WATER_BASE_EUR + min(water_m3,40)*WATER_VOLUME_TARIFF_EUR) * WATER_NDS * behavior_factor
    service_cost = SERVICE_MAX_EUR if use_max_service else SERVICE_MIN_EUR
    other_costs = INTERNET_EUR + PHONE_EUR + IPTV_EUR + service_cost
    total = electricity_cost + water_cost + other_costs
    return {
        "Электроэнергия": round(electricity_cost,2),
        "Вода": round(water_cost,2),
        "Интернет": round(INTERNET_EUR,2),
        "Телефон": round(PHONE_EUR,2),
        "IPTV": round(IPTV_EUR,2),
        "Сервисный сбор": round(service_cost,2),
        "Итого": round(total,2)
    }

# ------------------------
# Sidebar: параметры квартиры
# ------------------------
st.sidebar.header("Параметры квартиры")
city = st.sidebar.selectbox("Город", ["Минск","Лимассол"])
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,2)
occupants = adults + children

scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[scenario]
house_category = st.sidebar.selectbox("Категория дома (только Минск)", list(HOUSE_COEFS.keys()), index=1)

st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф (только Минск)")
subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05) if use_subsidy else 1.0
use_max_service = st.sidebar.checkbox("Использовать максимальный сервисный сбор (Лимассол)")
electricity_kwh = st.sidebar.number_input("Потребление электроэнергии, кВт·ч (Лимассол)", 0.0, 10000.0, 500.0) if city=="Лимассол" else 0.0
water_m3 = st.sidebar.number_input("Потребление воды, м³ (Лимассол)", 0.0, 1000.0, 25.2) if city=="Лимассол" else 0.0

# ------------------------
# Ввод реальных расходов (сворачиваемый блок)
# ------------------------
with st.expander("💰 Введите ваши реальные расходы (по желанию)"):
    if city=="Минск":
        user_real = {
            "Электроэнергия": st.number_input("Электроэнергия BYN",0.0,1000.0,0.0),
            "Вода": st.number_input("Вода BYN",0.0,1000.0,0.0),
            "Канализация": st.number_input("Канализация BYN",0.0,1000.0,0.0),
            "Отопление": st.number_input("Отопление BYN",0.0,10000.0,0.0),
            "Фикс. платежи": st.number_input("Фикс. платежи BYN",0.0,1000.0,0.0)
        }
        user_real["Итого"] = round(sum(user_real[k] for k in CATEGORIES_MINSK),2)
    else:
        user_real = calculate_limassol_bill(electricity_kwh, water_m3, use_max_service, behavior_factor)

# ------------------------
# Расчёт идеального и среднего соседа
# ------------------------
if city=="Минск":
    ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
    ideal_costs = calculate_costs_from_volumes(
        ideal_vol,
        {
            "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY,
            "water_BYN_per_m3": WATER_TARIFF,
            "sewage_BYN_per_m3": SEWAGE_TARIFF,
            "heating_BYN_per_Gcal": HEATING_SUBSIDY,
            "fixed_fees_BYN": FIXED_FEES
        },
        area_m2, occupants
    )
    neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
    neighbor_tariffs = {
        "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY * subsidy_rate,
        "water_BYN_per_m3": WATER_TARIFF,
        "sewage_BYN_per_m3": SEWAGE_TARIFF,
        "heating_BYN_per_Gcal": HEATING_SUBSIDY * subsidy_rate,
        "fixed_fees_BYN": FIXED_FEES
    }
    neighbor_costs = apply_neighbor_adjustment(neighbor_vol, neighbor_tariffs, house_category, area_m2, occupants)
else:
    ideal_costs = neighbor_costs = user_real

# ------------------------
# Визуализация расходов
# ------------------------
st.header("🏠 Сравнение расходов")
CATEGORIES = CATEGORIES_MINSK if city=="Минск" else CATEGORIES_LIMASSOL

col1, col2 = st.columns([2,1])

with col1:
    st.metric("Идеальный расчёт", f"{ideal_costs['Итого']:.2f}")
    st.metric("Ваши реальные расходы", f"{user_real['Итого']:.2f}")
    st.metric("Средний сосед", f"{neighbor_costs['Итого']:.2f}")

    diff_real = round((user_real["Итого"]/ideal_costs.get("Итого",1)-1)*100,1)
    diff_neighbor = round((user_real["Итого"]/neighbor_costs.get("Итого",1)-1)*100,1)

    st.info(f"Ваши реальные расходы на {diff_real}% {'выше' if diff_real>0 else 'ниже'} нормативного расчёта.")
    st.info(f"Ваши реальные расходы на {diff_neighbor}% {'выше' if diff_neighbor>0 else 'ниже'} среднего соседа.")

with col2:
    detail_df = pd.DataFrame({
        "Категория": CATEGORIES,
        "Идеальный расчёт": [ideal_costs.get(c,0.0) for c in CATEGORIES],
        "Ваши реальные данные": [user_real.get(c,0.0) for c in CATEGORIES],
        "Средний сосед": [neighbor_costs.get(c,0.0) for c in CATEGORIES]
    })
    st.table(detail_df)

# ------------------------
# График расходов
# ------------------------
st.subheader("📊 Распределение расходов по категориям")
fig = px.bar(
    detail_df.melt(id_vars="Категория", value_vars=["Идеальный расчёт","Ваши реальные данные","Средний сосед"]),
    x="Категория",
    y="value",
    color="variable",
    barmode="group",
    labels={"value": "Стоимость, BYN/€", "variable": "Сценарий"},
    text="value",
    height=400
)
fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig.update_layout(yaxis=dict(title='Стоимость'), xaxis=dict(title='Категория расходов'))
st.plotly_chart(fig, use_container_width=True)

# ------------------------
# Рекомендации
# ------------------------
st.subheader("💡 Рекомендации по оптимизации расходов")
if city == "Минск":
    if diff_real > 10:
        st.warning("Ваши расходы значительно выше нормы. Проверьте электроэнергию и отопление.")
    elif diff_real < -10:
        st.success("Ваши расходы ниже нормы — вы экономите эффективно!")
    else:
        st.info("Ваши расходы близки к нормативным.")
else:
    # Лимассол
    electricity_share = user_real["Электроэнергия"] / user_real["Итого"] * 100
    water_share = user_real["Вода"] / user_real["Итого"] * 100
    service_share = user_real["Сервисный сбор"] / user_real["Итого"] * 100

    if electricity_share > 40:
        st.warning("Большая часть расходов приходится на электроэнергию. Рассмотрите энергоэффективные приборы.")
    if water_share > 15:
        st.warning("Высокое потребление воды. Проверьте сантехнику и возможные утечки.")
    if service_share > 25:
        st.info("Сервисный сбор — значительная часть расходов. Возможно, стоит пересмотреть тарифный план.")

st.markdown("---")
st.info("Все расчеты динамически пересчитываются при изменении параметров квартиры и сценария поведения.")

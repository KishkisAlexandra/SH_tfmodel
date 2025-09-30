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
HEATING_MONTHS = [1,2,3,4,10,11,12]

# Минск тарифы
ELECTRICITY_FULL = 0.2969
ELECTRICITY_SUBSIDY = 0.2412
HEATING_FULL = 134.94
HEATING_SUBSIDY = 24.7187
WATER_TARIFF = 1.7858
SEWAGE_TARIFF = 0.9586
FIXED_FEES = 5.0

# ------------------------
# Sidebar
# ------------------------
st.sidebar.header("Параметры семьи")
city = st.sidebar.selectbox("Город", ["Минск", "Лимасол"])
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,2)
occupants = adults + children

scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[scenario]
house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)

st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф (дополнительно к субсидированному)")
subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05) if use_subsidy else 1.0

# ------------------------
# Категории
# ------------------------
if city == "Минск":
    CATEGORIES = ["Электроэнергия", "Вода", "Канализация", "Отопление", "Фикс. платежи"]
elif city == "Лимасол":
    CATEGORIES = ["Электроэнергия", "Вода", "Интернет", "Телефон", "IPTV", "Обслуживание", "Аренда"]

# ------------------------
# Функции расчёта Минск
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
    vol_adj["Электроэнергия"] *= coefs["electricity"]
    vol_adj["Отопление"] *= coefs["heating"]
    neighbor_costs = calculate_costs_from_volumes(vol_adj, tariffs, area_m2, occupants, floor, has_elevator)
    return {k: round(v * REALISM_UPLIFT, 2) for k, v in neighbor_costs.items()}

# ------------------------
# ------------------------
# Функции расчёта Лимасол (EUR)
# ------------------------
if city == "Лимасол":
    VAT_WATER = 0.05
    VAT_ELEC = 0.19
    INTERNET_TARIFF = 20
    PHONE_TARIFF = 20
    IPTV_TARIFF = 10
    VAT_FIXED = 0.19
    SERVICE_MIN = 45
    SERVICE_MAX = 125
    RENT = 4600  # фиксированная сумма в EUR, только для отображения

    def calculate_water_limassol(consumption_m3):
        cost = 22  # базовый платеж
        remaining = consumption_m3
        brackets = [(1,40,0.9),(41,80,1.43),(81,120,2.45),(121,float('inf'),5.0)]
        for lower, upper, rate in brackets:
            if remaining <= 0:
                break
            apply_m3 = min(upper-lower+1, remaining)
            cost += apply_m3 * rate
            remaining -= apply_m3
        return round(cost*(1+VAT_WATER),2)

    def calculate_fixed_limassol():
        return {
            "Интернет": round(INTERNET_TARIFF*(1+VAT_FIXED),2),
            "Телефон": round(PHONE_TARIFF*(1+VAT_FIXED),2),
            "IPTV": round(IPTV_TARIFF*(1+VAT_FIXED),2)
        }

    def calculate_service_limassol():
        avg_service = (SERVICE_MIN + SERVICE_MAX)/2
        return round(avg_service*(1+VAT_FIXED),2)

    def calculate_costs_limassol(volumes):
        elec_cost = volumes["Электроэнергия"] * 0.2661 * (1+VAT_ELEC)
        water_cost = calculate_water_limassol(volumes["Вода"])
        fixed_costs = calculate_fixed_limassol()
        service_cost = calculate_service_limassol()
        costs = {
            "Электроэнергия": round(elec_cost,2),
            "Вода": water_cost,
            **fixed_costs,
            "Обслуживание": service_cost,
            # "Аренда" исключена из расчёта
        }
        costs["Итого"] = round(sum(costs.values()),2)
        return costs



# Валюта для отображения
currency_label = "BYN" if city == "Минск" else "€"

# ------------------------
# Ввод реальных расходов
# ------------------------
st.header(f"📊 Введите ваши реальные расходы за месяц ({currency_label})")
with st.expander("Показать поля для ручного ввода"):
    user_real = {
        "Электроэнергия": st.number_input(f"Электроэнергия {currency_label}", min_value=0.0, value=0.0, step=1.0, format="%.2f"),
        "Вода": st.number_input(f"Вода {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f")
    }
    if city == "Лимасол":
        # Лимасол: фиксированные категории
        user_real.update({
            "Интернет": st.number_input(f"Интернет {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
            "Телефон": st.number_input(f"Телефон {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
            "IPTV": st.number_input(f"IPTV {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
            "Обслуживание": st.number_input(f"Обслуживание {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
            "Аренда": st.number_input(f"Аренда {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f")
        })
    else:
        # Минск: стандартные категории
        user_real.update({
            "Канализация": st.number_input(f"Канализация {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
            "Отопление": st.number_input(f"Отопление {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f"),
            "Фикс. платежи": st.number_input(f"Фикс. платежи {currency_label}", min_value=0.0, value=0.0, step=0.1, format="%.2f")
        })

user_real["Итого"] = round(sum(user_real[k] for k in (CATEGORIES if city=="Лимасол" else ["Электроэнергия","Вода","Канализация","Отопление","Фикс. платежи"])), 2)

# ------------------------
# Метрики сравнения
# ------------------------
st.header(f"🏠 Сравнение расходов ({currency_label})")
col1, col2 = st.columns([2,1])

with col1:
    st.metric(f"Идеальный расчёт по нормативам, {currency_label}", f"{ideal_costs['Итого']:.2f}")
    st.metric(f"Ваши реальные расходы, {currency_label}", f"{user_real['Итого']:.2f}")
    st.metric(f"Средний сосед, {currency_label}", f"{neighbor_costs['Итого']:.2f}")


# ------------------------
# Расчёт идеального и среднего соседа
# ------------------------
ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)

if city == "Минск":
    ideal_costs = calculate_costs_from_volumes(ideal_vol, {
        "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY,
        "water_BYN_per_m3": WATER_TARIFF,
        "sewage_BYN_per_m3": SEWAGE_TARIFF,
        "heating_BYN_per_Gcal": HEATING_SUBSIDY,
        "fixed_fees_BYN": FIXED_FEES
    }, area_m2, occupants)

    neighbor_tariffs = {
        "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY * subsidy_rate,
        "water_BYN_per_m3": WATER_TARIFF,
        "sewage_BYN_per_m3": SEWAGE_TARIFF,
        "heating_BYN_per_Gcal": HEATING_SUBSIDY * subsidy_rate,
        "fixed_fees_BYN": FIXED_FEES
    }
    neighbor_costs = apply_neighbor_adjustment(neighbor_vol, neighbor_tariffs, house_category, area_m2, occupants)

elif city == "Лимасол":
    ideal_costs = calculate_costs_limassol(ideal_vol)
    neighbor_costs = calculate_costs_limassol(neighbor_vol)

# ------------------------
# Визуализация таблицы
# ------------------------
st.header("🏠 Сравнение расходов")
col1, col2 = st.columns([2, 1])

with col1:
    st.metric("Идеальный расчёт по нормативам, BYN", f"{ideal_costs['Итого']:.2f}")
    st.metric("Ваши реальные расходы, BYN", f"{user_real['Итого']:.2f}")
    st.metric("Средний сосед, BYN", f"{neighbor_costs['Итого']:.2f}")

    ideal_total = ideal_costs.get("Итого", 0.0)
    neighbor_total = neighbor_costs.get("Итого", 0.0)
    real_total = user_real["Итого"]

    diff_real = round((real_total/ideal_total-1)*100,1) if ideal_total>0 else 0.0
    diff_neighbor = round((real_total/neighbor_total-1)*100,1) if neighbor_total>0 else 0.0

    st.info(f"Ваши реальные расходы на {diff_real}% {'выше' if diff_real>0 else 'ниже'} нормативного расчёта.")
    st.info(f"Ваши реальные расходы на {diff_neighbor}% {'выше' if diff_neighbor>0 else 'ниже'} среднего соседа.")

with col2:
    detail_df = pd.DataFrame({
        "Категория": CATEGORIES,
        "Идеальный расчёт (BYN)": [ideal_costs.get(c,0) for c in CATEGORIES],
        "Ваши реальные данные (BYN)": [user_real.get(c,0) for c in CATEGORIES],
        "Средний сосед (BYN)": [neighbor_costs.get(c,0) for c in CATEGORIES],
    })

    styled_df = detail_df.style.format({
        "Идеальный расчёт (BYN)": "{:.2f}",
        "Ваши реальные данные (BYN)": "{:.2f}",
        "Средний сосед (BYN)": "{:.2f}"
    }).background_gradient(
        subset=["Идеальный расчёт (BYN)", "Ваши реальные данные (BYN)", "Средний сосед (BYN)"],
        cmap="BuPu"
    ).set_properties(**{
        'text-align': 'center',
        'font-size': '14px'
    }).set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('font-size', '15px'), ('background-color', '#f0f0f0')]}
    ])
    st.dataframe(styled_df, height=280)

# ------------------------
# График расходов
# ------------------------
plot_df = pd.DataFrame({
    "Категория": CATEGORIES * 3,
    "Тип": (["Идеальный расчёт"] * len(CATEGORIES)) + (["Ваши реальные данные"] * len(CATEGORIES)) + (["Средний сосед"] * len(CATEGORIES)),
    "BYN": [ideal_costs.get(c,0) for c in CATEGORIES] + [user_real.get(c,0) for c in CATEGORIES] + [neighbor_costs.get(c,0) for c in CATEGORIES]
})
fig = px.bar(plot_df, x="Категория", y="BYN", color="Тип", barmode="group",
             color_discrete_map={"Идеальный расчёт":"#636EFA","Ваши реальные данные":"#00CC96","Средний сосед":"#EF553B"},
             text="BYN")
fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig.update_layout(yaxis_title="BYN / месяц", legend_title_text="Показатель", uniformtext_minsize=8)
st.plotly_chart(fig, use_container_width=True)

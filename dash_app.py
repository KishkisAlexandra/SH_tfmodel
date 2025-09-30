# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Выбор региона
# ------------------------
REGIONS = ["Беларусь", "Кипр"]
region = st.sidebar.selectbox("🌍 Регион", REGIONS, index=1) # Изменено на Кипр по умолчанию

# ------------------------
# Константы и базовые коэффициенты
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

# Категории расходов
CATEGORIES = [
    "Электроэнергия", "Вода", "Канализация", "Отопление",
    "Интернет", "Телефон", "IPTV", "Сервис", "Фикс. платежи"
]

HEATING_MONTHS = [1, 2, 3, 4, 10, 11, 12]

# ------------------------
# Тарифы и данные по регионам
# ------------------------
# Данные по Кипру, взятые из вашего файла Excel, для более точного расчета по месяцам
cyprus_monthly_data = {
    "electricity_tariff": {
        1: 0.242, 2: 0.242, 3: 0.242, 4: 0.242, 5: 0.2705, 6: 0.2705,
        7: 0.2661, 8: 0.2661, 9: 0.2661, 10: 0.2661, 11: 0.2661, 12: 0.2661
    }
}

TARIFFS = {
    "Беларусь": {
        "electricity": 0.2412,
        "water": 1.7858,
        "sewage": 0.9586,
        "heating": 24.7187,
        "fixed": 5.0,
        "internet": 0.0,
        "phone": 0.0,
        "iptv": 0.0,
        "service": 0.0
    },
    "Кипр": {
        # Тариф на электроэнергию будет браться из cyprus_monthly_data
        "electricity": cyprus_monthly_data["electricity_tariff"],
        # Структура тарифов на воду в Лимассоле (счета выставляются за 4 месяца)
        "water_tariffs": {
            "fixed_charge_4m": 16.00, # Фиксированный сбор за 4 мес.
            "maintenance_charge_4m": 6.00, # Сбор за обслуживание за 4 мес.
            "tiers_4m": [ # Ставки за потребление за 4 мес.
                {"limit": 40, "rate": 0.90},
                {"limit": 80, "rate": 1.43},
                {"limit": 120, "rate": 2.45},
                {"limit": float('inf'), "rate": 5.00}
            ]
        },
        "sewage_per_m3": 0.64, # Плата за канализацию за кубометр воды
        "sewage_annual_tax": 80.0, # Годовой налог на канализацию
        "heating": 0.0,
        "fixed": 0.0,
        "internet": 20.0,
        "phone": 20.0,
        "iptv": 10.0,
        "service": 45.0, # Минимальный сервисный сбор
        "vat": {
            "water_sewage": 0.05, # 5%
            "default": 0.19      # 19%
        }
    }
}

currency = "BYN" if region == "Беларусь" else "EUR"

# ------------------------
# Функции расчёта
# ------------------------
def calculate_volumes(area_m2, occupants, behavior_factor, coeffs=DEFAULT_COEFFS, month=1):
    # Эта функция остается без изменений, она универсальна
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
        "Электроэнергия": round(elec, 1),
        "Вода": round(water, 2),
        "Горячая вода": round(hot_water, 2),
        "Канализация": round(sewage, 2),
        "Отопление": round(heat_monthly, 3)
    }

def calculate_costs_cyprus(volumes, tariffs, month):
    """Специальная функция для расчета стоимости по тарифам Кипра."""
    costs = {}
    vat_rates = tariffs["vat"]

    # --- Электроэнергия ---
    # Используем тариф для конкретного месяца из словаря
    monthly_elec_tariff = tariffs["electricity"][month]
    elec_cost_no_vat = volumes["Электроэнергия"] * monthly_elec_tariff
    costs["Электроэнергия"] = elec_cost_no_vat * (1 + vat_rates["default"])

    # --- Вода и Канализация (сложный расчет) ---
    # Тарифы на воду в Лимассоле применяются за 4 месяца, поэтому моделируем это
    water_volume_4m = volumes["Вода"] * 4
    water_tariffs = tariffs["water_tariffs"]

    # Расчет стоимости потребления воды по ступеням за 4 месяца
    water_consumption_cost_4m = 0
    remaining_volume = water_volume_4m
    last_limit = 0
    for tier in water_tariffs["tiers_4m"]:
        tier_limit = tier["limit"] - last_limit
        volume_in_tier = min(remaining_volume, tier_limit)
        water_consumption_cost_4m += volume_in_tier * tier["rate"]
        remaining_volume -= volume_in_tier
        last_limit = tier["limit"]
        if remaining_volume <= 0:
            break

    # Общая стоимость воды за 4 месяца (потребление + фикс. сборы)
    total_water_cost_4m = (
        water_consumption_cost_4m +
        water_tariffs["fixed_charge_4m"] +
        water_tariffs["maintenance_charge_4m"]
    )
    # Среднемесячная стоимость воды без НДС
    water_cost_no_vat = total_water_cost_4m / 4
    costs["Вода"] = water_cost_no_vat * (1 + vat_rates["water_sewage"])

    # --- Канализация ---
    # Плата за использование (за кубометр) + месячная доля годового налога
    sewage_usage_cost_no_vat = volumes["Вода"] * tariffs["sewage_per_m3"]
    sewage_tax_monthly_no_vat = tariffs["sewage_annual_tax"] / 12
    sewage_cost_no_vat = sewage_usage_cost_no_vat + sewage_tax_monthly_no_vat
    costs["Канализация"] = sewage_cost_no_vat * (1 + vat_rates["water_sewage"])

    # --- Отопление (на Кипре обычно через электричество, здесь 0) ---
    costs["Отопление"] = 0.0

    # --- Остальные платежи с НДС ---
    costs["Интернет"] = tariffs["internet"] * (1 + vat_rates["default"])
    costs["Телефон"] = tariffs["phone"] * (1 + vat_rates["default"])
    costs["IPTV"] = tariffs["iptv"] * (1 + vat_rates["default"])
    costs["Сервис"] = tariffs["service"] * (1 + vat_rates["default"])
    costs["Фикс. платежи"] = tariffs["fixed"] * (1 + vat_rates["default"])

    # Округление всех значений
    for key in costs:
        costs[key] = round(costs[key], 2)

    costs["Итого"] = round(sum(costs.values()), 2)
    return costs

def calculate_costs_from_volumes(volumes, tariffs, area_m2=50, occupants=1, floor=1, has_elevator=True, month=1):
    # Эта функция теперь вызывает специфичную для региона логику
    if region == "Кипр":
        return calculate_costs_cyprus(volumes, tariffs, month)

    # --- Расчет для Беларуси (старая логика) ---
    elec_cost = volumes["Электроэнергия"] * tariffs["electricity"]
    water_cost = volumes["Вода"] * tariffs["water"]
    sewage_cost = volumes["Канализация"] * tariffs["sewage"]
    heat_cost = volumes["Отопление"] * tariffs["heating"]
    
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
    fixed_cost = tariffs["fixed"] + maintenance_cost + lighting_cost + waste_cost + capital_repair_cost + elevator_cost

    internet_cost = tariffs["internet"]
    phone_cost = tariffs["phone"]
    iptv_cost = tariffs["iptv"]
    service_cost = tariffs["service"]

    costs = {
        "Электроэнергия": round(elec_cost, 2), "Вода": round(water_cost, 2),
        "Канализация": round(sewage_cost, 2), "Отопление": round(heat_cost, 2),
        "Интернет": round(internet_cost, 2), "Телефон": round(phone_cost, 2),
        "IPTV": round(iptv_cost, 2), "Сервис": round(service_cost, 2),
        "Фикс. платежи": round(fixed_cost, 2)
    }
    costs["Итого"] = round(sum(costs.values()), 2)
    return costs

def apply_neighbor_adjustment(volumes, tariffs, house_category, area_m2, occupants, floor=1, has_elevator=True, month=1):
    coefs = HOUSE_COEFS.get(house_category, {"heating":1.0,"electricity":1.0})
    vol_adj = volumes.copy()
    vol_adj["Электроэнергия"] = vol_adj["Электроэнергия"] * coefs["electricity"]
    vol_adj["Отопление"] = vol_adj["Отопление"] * coefs["heating"]
    neighbor_costs = calculate_costs_from_volumes(vol_adj, tariffs, area_m2, occupants, floor, has_elevator, month)
    neighbor_costs = {k: round(v * REALISM_UPLIFT, 2) for k, v in neighbor_costs.items()}
    return neighbor_costs

# ------------------------
# Sidebar: параметры семьи
# ------------------------
st.sidebar.header("Параметры семьи")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 140.0) # Изменено на 140
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,0) # Изменено
occupants = adults + children

scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[scenario]
house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)

# Льготы для Беларуси
st.sidebar.markdown("---")
if region == "Беларусь":
    use_subsidy = st.sidebar.checkbox("Использовать льготный тариф (дополнительно к субсидированному)")
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05) if use_subsidy else 1.0
else:
    subsidy_rate = 1.0

# ------------------------
# Ввод реальных расходов
# ------------------------
st.header(f"📊 Введите ваши реальные расходы за месяц ({currency})")
with st.expander("Показать поля для ручного ввода"):
    user_real = {}
    for c in CATEGORIES:
        user_real[c] = st.number_input(f"{c} ({currency})", min_value=0.0, value=0.0, step=1.0, format="%.2f")
user_real["Итого"] = round(sum(user_real[k] for k in CATEGORIES), 2)

# ------------------------
# Расчёт идеального и среднего соседа
# ------------------------
tariffs = TARIFFS[region]

ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
ideal_costs = calculate_costs_from_volumes(ideal_vol, tariffs, area_m2, occupants, month=month)

neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
neighbor_tariffs = tariffs.copy()
if region == "Беларусь":
    neighbor_tariffs["electricity"] *= subsidy_rate
    neighbor_tariffs["heating"] *= subsidy_rate

neighbor_costs = apply_neighbor_adjustment(neighbor_vol, neighbor_tariffs, house_category, area_m2, occupants, month=month)

# ------------------------
# Визуализация расходов (остальная часть кода без изменений)
# ------------------------
st.header("🏠 Сравнение расходов")
col1, col2 = st.columns([2, 1])

with col1:
    st.metric(f"Идеальный расчёт ({currency})", f"{ideal_costs['Итого']:.2f}")
    st.metric(f"Ваши реальные расходы ({currency})", f"{user_real['Итого']:.2f}")
    st.metric(f"Средний сосед ({currency})", f"{neighbor_costs['Итого']:.2f}")

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
        f"Идеальный расчёт ({currency})": [ideal_costs.get(c,0) for c in CATEGORIES],
        f"Ваши реальные данные ({currency})": [user_real.get(c,0) for c in CATEGORIES],
        f"Средний сосед ({currency})": [neighbor_costs.get(c,0) for c in CATEGORIES],
    })

    st.dataframe(detail_df, height=350)

# ------------------------
# График расходов
# ------------------------
plot_df = pd.DataFrame({
    "Категория": CATEGORIES * 3,
    "Тип": (["Идеальный расчёт"] * len(CATEGORIES)) + (["Ваши реальные данные"] * len(CATEGORIES)) + (["Средний сосед"] * len(CATEGORIES)),
    "Сумма": [ideal_costs.get(c,0) for c in CATEGORIES] +
             [user_real.get(c,0) for c in CATEGORIES] +
             [neighbor_costs.get(c,0) for c in CATEGORIES]
})
fig = px.bar(plot_df, x="Категория", y="Сумма", color="Тип", barmode="group",
             text="Сумма")
fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig.update_layout(yaxis_title=f"{currency} / месяц", legend_title_text="Показатель", uniformtext_minsize=8)
st.plotly_chart(fig, use_container_width=True)

# ------------------------
# Рекомендации
# ------------------------
st.header("💡 Рекомендации")
emoji_map = {
    "Электроэнергия":"💡","Вода":"🚰","Отопление":"🔥","Канализация":"💧",
    "Интернет":"🌐","Телефон":"📞","IPTV":"📺","Сервис":"🏢"
}
tips_map = {
    "Электроэнергия":"используйте энергосберегающие лампы и приборы.",
    "Вода":"установите аэраторы и проверьте трубы на протечки.",
    "Отопление":"закрывайте окна и проверьте терморегуляторы.",
    "Канализация":"контролируйте расход воды и исправность сантехники.",
    "Интернет":"проверьте тарифный план — возможно есть дешевле.",
    "Телефон":"отключите ненужные опции или перейдите на пакет.",
    "IPTV":"подумайте, нужны ли все пакеты каналов.",
    "Сервис":"уточните перечень услуг у управляющей компании."
}
def get_color(diff):
    return "#FFCDD2" if diff > 0 else "#C8E6C9"

cols = st.columns(4)
for i, cat in enumerate(["Электроэнергия","Вода","Отопление","Канализация"]):
    ideal_cost = ideal_costs.get(cat, 0)
    real_cost = user_real.get(cat, 0)
    
    # Проверка, чтобы избежать деления на ноль, если идеальная стоимость равна 0
    if ideal_cost > 0:
        diff = real_cost - ideal_cost
        percent_over = round(diff / ideal_cost * 100, 1)
        msg = f"Перерасход {percent_over}% — {tips_map[cat]}" if diff > 0 else "Расход в норме"
    else:
        diff = 0
        msg = "Расход в норме" # Если нет идеального расхода, считаем, что все в норме

    # Пропускаем отображение рекомендации для Отопления на Кипре
    if region == "Кипр" and cat == "Отопление":
        continue

    with cols[i]:
        st.markdown(f"""
            <div style='padding:12px; border-radius:10px; background-color:{get_color(diff)};
                        font-size:0.9em; text-align:center; height: 160px; display: flex; flex-direction: column; justify-content: center;'>
                <div style='font-size:1.5em'>{emoji_map[cat]}</div>
                <strong>{cat}</strong>
                <div style='margin-top:6px'>{msg}</div>
            </div>
        """, unsafe_allow_html=True)

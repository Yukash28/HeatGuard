#heat index is the temperature that takes the account for all the variables such as temperature, humidity, wind speed and radiation. It is the perceived temperature that a person feels when exposed to the sun and other environmental factors. The heat index is calculated using a formula that takes into account the temperature and humidity levels, and it can be used to determine the risk of heat-related illnesses such as heat exhaustion and heat stroke.

def calculate_heat_index(temp_c, humidity):
    temp_f = (temp_c * 9 / 5) + 32

    if temp_f < 80:
        return temp_c

    hi_f = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * humidity
        - 0.22475541 * temp_f * humidity
        - 0.00683783 * temp_f ** 2
        - 0.05481717 * humidity ** 2
        + 0.00122874 * temp_f ** 2 * humidity
        + 0.00085282 * temp_f * humidity ** 2
        - 0.00000199 * temp_f ** 2 * humidity ** 2
    )

    hi_c = (hi_f - 32) * 5 / 9

    return round(hi_c, 2)
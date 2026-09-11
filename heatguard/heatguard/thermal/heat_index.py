from numbers import Real

def calculate_heat_index(temp_c, humidity):
    if not isinstance(temp_c, Real) or not isinstance(humidity, Real):
        raise TypeError("temperature and humidity must be numeric")

    if not -50 <= temp_c <= 60:
        raise ValueError("temperature must be between -50 and 60 C")

    if not 0 <= humidity <= 100:
        raise ValueError("humidity must be between 0 and 100 percent")

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

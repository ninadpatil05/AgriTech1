import sys
sys.path.insert(0, '.')
from blueprints.weather_advice import _call_gemini
prompt = """You are an expert agricultural advisor for Indian farmers.
Given the current weather conditions below, provide practical farming guidance.

Weather data:
Location: London, GB
Temperature: 15°C (feels like 14°C)
Humidity: 60%
Conditions: clear sky
Wind speed: 3 m/s
Rainfall last 1h: 0 mm
Cloud cover: 10%
Pressure: 1012 hPa

Farmer's crop (if provided): wheat

Respond ONLY with this exact JSON (no markdown, no preamble):
{
  "summary": "One sentence describing what today's weather means for farming",
  "do_today": ["action 1", "action 2", "action 3"],
  "avoid_today": ["thing to avoid 1", "thing to avoid 2"],
  "spray_window": "good" | "avoid" | "marginal",
  "spray_reason": "Short reason for spray window decision",
  "field_work": "good" | "avoid" | "marginal",
  "field_work_reason": "Short reason",
  "urgency": "normal" | "caution" | "alert"
}
"""

print(repr(_call_gemini(prompt)))

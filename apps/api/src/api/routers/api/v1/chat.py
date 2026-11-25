import json

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from utils.mistral import MistralNotConfiguredError, caller_mistral_client

from .weather import fetch_current_conditions, geocode as geocode_place

CHAT_MODEL = "mistral-small-latest"
MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = (
    "You are a helpful weather assistant. Answer questions about the weather anywhere in the world. "
    "Use the tools to find a place's coordinates and read its current weather, and never invent weather data: "
    "when a tool answers, report its values. Say which place you used when a name could match several, "
    "and answer briefly."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "geocode_place",
            "description": "Find the coordinates of a place by its name, such as a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The place to find, in English"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Read the current weather at a point, given its coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "description": "The point's latitude, in degrees"},
                    "longitude": {"type": "number", "description": "The point's longitude, in degrees"},
                },
                "required": ["latitude", "longitude"],
            },
        },
    },
]

WEATHER_CODES = {
    0: ("clear", "clear sky"),
    1: ("mainly clear", "mainly clear"),
    2: ("partly cloudy", "partly cloudy"),
    3: ("overcast", "overcast"),
    45: ("fog", "fog"),
    48: ("fog", "depositing rime fog"),
    51: ("light drizzle", "light drizzle"),
    53: ("moderate drizzle", "moderate drizzle"),
    55: ("dense drizzle", "dense drizzle"),
    61: ("slight rain", "slight rain"),
    63: ("moderate rain", "moderate rain"),
    65: ("heavy rain", "heavy rain"),
    71: ("slight snow", "slight snowfall"),
    73: ("moderate snow", "moderate snowfall"),
    75: ("heavy snow", "heavy snowfall"),
    77: ("snow", "snow grains"),
    80: ("slight rain", "slight rain showers"),
    81: ("moderate rain", "moderate rain showers"),
    82: ("heavy rain", "violent rain showers"),
    85: ("slight snow", "slight snow showers"),
    86: ("heavy snow", "heavy snow showers"),
    95: ("thunderstorm", "a thunderstorm"),
    96: ("thunderstorm", "a thunderstorm with slight hail"),
    99: ("thunderstorm", "a thunderstorm with heavy hail"),
}


def describe_weather(code: int) -> str:
    return WEATHER_CODES.get(code, ("unknown", "unknown conditions"))[0]


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


class ChatResponse(BaseModel):
    content: str


router = APIRouter()


async def run_tool(name: str, arguments: dict, client: httpx.AsyncClient) -> dict:
    if name == "geocode_place":
        place = await geocode_place(client, arguments.get("name", ""))
        return place.model_dump() if place else {"found": False}
    if name == "get_weather":
        weather = await fetch_current_conditions(client, arguments.get("latitude"), arguments.get("longitude"))
        return {
            "description": describe_weather(weather.conditions.weather_code),
            **weather.conditions.model_dump(),
            **{"latitude": weather.latitude, "longitude": weather.longitude},
        }
    raise HTTPException(status_code=500, detail=f"Unknown tool {name}.")


@router.post(
    "",
    operation_id="v1_chat",
    summary="Chat about the weather with an assistant that reads Open-Meteo",
)
async def v1_chat(request: ChatRequest) -> ChatResponse:
    try:
        client = caller_mistral_client()
    except MistralNotConfiguredError as error:
        raise HTTPException(status_code=503, detail="No Mistral credential is configured for this request.") from error

    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
    conversation += [{"role": m.role, "content": m.content} for m in request.messages]

    async with httpx.AsyncClient(timeout=15) as http:
        for _ in range(MAX_TOOL_ROUNDS):
            response = await client.chat.complete_async(model=CHAT_MODEL, messages=conversation, tools=TOOLS)
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                return ChatResponse(content=message.content or "")

            conversation.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.function.name, "arguments": call.function.arguments},
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                arguments = json.loads(call.function.arguments or "{}")
                result = await run_tool(call.function.name, arguments, http)
                conversation.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
                )

    return ChatResponse(content="I could not read the weather just now. Please try again.")

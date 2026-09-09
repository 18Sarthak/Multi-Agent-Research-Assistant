import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

for key in ["NVIDIA_API_KEY", "TAVILY_API_KEY"]:
    if not os.environ.get(key):
        raise EnvironmentError(f"Missing {key} in .env")

# NVIDIA NIM exposes an OpenAI-compatible endpoint — same ChatOpenAI class,
# just point base_url at NVIDIA and pass the nvapi- key.
model = ChatOpenAI(
    model="meta/llama-3.2-11b-vision-instruct",  # meta/llama-3.x-70b EOL'd on 2026-08-26; use this instead
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ["NVIDIA_API_KEY"],
    temperature=0,
)
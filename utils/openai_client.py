from dotenv import load_dotenv
import os
from openai import AzureOpenAI

load_dotenv()

def get_client():
    """
    Returns an initialized AzureOpenAI client
    """
    return AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_API_VERSION")
    )

import boto3
import os, json, csv, time, math 
import snowflake.connector
from dotenv import load_dotenv


# ================================
# OTHER CONFIG
# ================================
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
EMBED_MODEL_ID = os.getenv("EMBED_MODEL_ID", "amazon.titan-embed-text-v1")

bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


bedrock = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1"
)

 
# ================================
# EMBEDDING
# ================================
def embed(text: str):
    body = json.dumps({"inputText": text})
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    payload = json.loads(resp["body"].read())
    return payload["embedding"]

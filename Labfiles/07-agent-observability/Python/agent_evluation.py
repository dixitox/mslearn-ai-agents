import os
import json
import time
from pprint import pprint
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ListSortOrder
from azure.ai.evaluation import (
    AIAgentConverter,
    ToolCallAccuracyEvaluator,
    AzureOpenAIModelConfiguration,
    IntentResolutionEvaluator,
    TaskAdherenceEvaluator,
    evaluate,
)
from azure.ai.projects.models import ConnectionType
from user_functions import user_functions

# Load environment variables from .env file
load_dotenv()

# Required environment variables
endpoint = os.environ["PROJECT_ENDPOINT"] # https://<account>.services.ai.azure.com/api/projects/<project>
model_endpoint = os.environ["MODEL_ENDPOINT"] # https://<account>.services.ai.azure.com
model_api_key = os.environ["MODEL_API_KEY"]
model_deployment_name = os.environ["MODEL_DEPLOYMENT_NAME"] # e.g. gpt-4o-mini
credential = DefaultAzureCredential()

agent_client = AgentsClient(endpoint=endpoint, credential=credential)
project_client = AIProjectClient(
    credential=credential,
    endpoint=endpoint
)

# Create a new agent with specified model and instructions
agent = agent_client.create_agent(
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    name="city-travel-agent",
    instructions="You are helpful agent"
)
print(f"Created agent, ID: {agent.id}")

# Start a new conversation thread
thread = agent_client.threads.create()

# Send a user message to the thread
MESSAGE = "Tell me about Seattle"
message = agent_client.messages.create(
    thread_id=thread.id,
    role="user",
    content=MESSAGE,
)
print(f"Created message, ID: {message.id}")

# Run the agent on the conversation thread
run = agent_client.runs.create(thread_id=thread.id, agent_id=agent.id)
print(f"Run ID: {run.id}")

# Poll the run status until completion
while run.status in ["queued", "in_progress", "requires_action"]:
    time.sleep(1)
    run = agent_client.runs.get(thread_id=thread.id, run_id=run.id)
    print(f"Run status: {run.status}")

if run.status == "failed":
    print(f"Run error: {run.last_error}")

# List and print all messages in the thread
messages = agent_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
for msg in messages:
    if msg.text_messages:
        last_text = msg.text_messages[-1]
        print(f"{msg.role}: {last_text.text.value}")

# Convert the conversation thread to evaluation data and save as JSONL
converter = AIAgentConverter(project_client)
filename = os.path.join(os.getcwd(), "evaluation_input_data.jsonl")
evaluation_data = converter.prepare_evaluation_data(thread_ids=thread.id, filename=filename)

with open(filename, "w", encoding='utf-8') as f:
    for obj in evaluation_data:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
print(f"Evaluation data saved to {filename}")

# Configure the model for evaluation
model_config = AzureOpenAIModelConfiguration(
    azure_endpoint=os.environ["AZURE_OPENAI_SERVICE"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version="2025-01-01-preview",
    azure_deployment=os.environ["AZURE_OPENAI_CHATGPT_DEPLOYMENT"],
)

# Initialize evaluators for different quality metrics
intent_resolution = IntentResolutionEvaluator(model_config=model_config)
tool_call_accuracy = ToolCallAccuracyEvaluator(model_config=model_config)
task_adherence = TaskAdherenceEvaluator(model_config=model_config)

used_evaluators = {
    "tool_call_accuracy": tool_call_accuracy,
    "intent_resolution": intent_resolution,
    "task_adherence": task_adherence,
}

# Run the evaluation using the prepared data and evaluators
response = evaluate(
    data=filename,
    evaluators=used_evaluators,
    #azure_ai_project=endpoint
)

# Clean up the created agent
agent_client.delete_agent(agent.id)

# Print evaluation results and metrics
pprint(f'AI Foundry URL: {response.get("studio_url")}')
pprint(response["metrics"])
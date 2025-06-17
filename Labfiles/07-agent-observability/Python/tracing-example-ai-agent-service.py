'''
This script demonstrates how to use the Azure AI Foundry Observability SDK to create, interact with, and trace an AI agent for financial education purposes.
Key functionalities:
- Configures OpenTelemetry tracing and Azure Monitor telemetry collection for observability.
- Initializes an AIProjectClient with Azure credentials and project endpoint.
- Checks and configures Application Insights for telemetry.
- Creates a financial education agent with specific instructions and disclaimers.
- Creates a new conversation thread and sends a user message about mortgage types in Switzerland.
- Initiates a run for the agent to process the message and polls for completion.
- Lists all threads and messages associated with the agent, printing out the conversation.
- Cleans up by deleting the created agent.
Requirements:
- Azure SDK for Python (`azure-ai-agents`, `azure-ai-projects`, `azure-identity`, `azure-monitor-opentelemetry`)
- OpenTelemetry Python SDK
References:
- https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-agents/samples/sample_agents_basics.py
Environment Variables:
- AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED: Enables tracing of generated AI content.
Note:
- The script assumes Application Insights is enabled for the Azure AI Foundry project.
- The agent provides only general financial advice and always includes disclaimers.
'''

import os, time
import asyncio
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from azure.ai.agents.models import ListSortOrder
from dotenv import load_dotenv
load_dotenv()
tracer = trace.get_tracer(__name__)

os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"

# Initialize the AIProjectClient with Azure credentials and project endpoint
ai_project = AIProjectClient(
    credential=DefaultAzureCredential(),
    endpoint=os.getenv("PROJECT_ENDPOINT"),
    api_version = "2025-05-15-preview" 
)

connection_string = ai_project.telemetry.get_connection_string()



if not connection_string:
    print("Application Insights is not enabled. Enable by going to Tracing in your Azure AI Foundry project.")
    exit()

# Configure OpenTelemetry to use Azure Monitor for telemetry collection
configure_azure_monitor(connection_string=connection_string) #enable telemetry collection

# Create an AI agents client from the AIProjectClient
agents_client = ai_project.agents

# Enable tracing for the financial education agent creation and interaction
with tracer.start_as_current_span("financial-education-agent-tracing"):
    agent = agents_client.create_agent(
        model="gpt-4.1-nano",
        name="fun-financial-education-agent",
        instructions="""
            You are a friendly AI Financial Education Agent.
            You provide general financial advice and education, but always:
            1. Include disclaimers about the general nature of your advice.
            2. Encourage the user to consult financial professionals.
            3. Provide general, non-diagnostic advice around finance and budgeting.
            4. Clearly remind them you're not a financial advisor.
            5. Encourage safe and balanced approaches to financial planning.
            """
    )
    print(f"Created agent with ID: {agent.id}")
 
    # [START create_thread]
    thread = agents_client.threads.create()

    print(f"Created thread, thread ID: {thread.id}")

    # List all threads for the agent
    # [START list_threads]
    threads = agents_client.threads.list()
    # [END list_threads]

    # [START create_message]
    message = agents_client.messages.create(thread_id=thread.id, 
                                            role="user", 
                                            content="Tell me the types of mortgages available in Switzerland and their pros and cons.")
    # [END create_message]
    print(f"Created message, message ID: {message.id}")

    # [START create_run]
    run = agents_client.runs.create(thread_id=thread.id, agent_id=agent.id)

    # Poll the run as long as run status is queued or in progress
    while run.status in ["queued", "in_progress", "requires_action"]:
        # Wait for a second
        time.sleep(1)
        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
        # [END create_run]
        print(f"Run status: {run.status}")

    if run.status == "failed":
        print(f"Run error: {run.last_error}")

    agents_client.delete_agent(agent.id)
    print("Deleted agent")

    # [START list_messages]
    messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    for msg in messages:
        if msg.text_messages:
            last_text = msg.text_messages[-1]
            print(f"{msg.role}: {last_text.text.value}")
    # [END list_messages]
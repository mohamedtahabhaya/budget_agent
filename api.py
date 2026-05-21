from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
from graph import graph 
from finance_tools import parse_receipt_image

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str
    is_approval: Optional[bool] = False
    image_data: Optional[str] = None
    
    workspace_id: str = "workspace_famille_dupont"
    user_id: str = "user_mohamed"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    async def event_generator():
        config = {"configurable": {"thread_id": request.session_id}}
        
        final_message = request.message
        if request.image_data:
            yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing the current receipt...'})}\n\n"
            try:
                receipt_json = parse_receipt_image.invoke({"base64_image": request.image_data})

                print(f"\n\n=== VISION RESPONSE ===\n{receipt_json}\n=======================\n\n")
                
                final_message += f"\n\nHere is the extracted data from the receipt image I just uploaded: {receipt_json}. You MUST use this information with the 'create_transaction' tool to record this expense."
            except Exception as e:
                print(f"\n\n=== ERREUR VISION ===\n{str(e)}\n=======================\n\n")
                yield f"data: {json.dumps({'type': 'error', 'content': f'Vision error: {str(e)}'})}\n\n"

        input_data = {
            "messages": [("user", final_message)],
            "workspace_id": request.workspace_id,
            "user_id": request.user_id
        }

        try:
            async for event in graph.astream_events(input_data, config=config, version="v2"):
                kind = event["event"]
                node_name = event["metadata"].get("langgraph_node", "agent")

                if kind == "on_chat_model_stream" and node_name in ["data_agent", "analyst_agent", "general_agent"]:
                    chunk = event["data"]["chunk"].content 
                    if isinstance(chunk, str) and chunk:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    agent_display = node_name.replace("_", " ").title()
                    yield f"data: {json.dumps({'type': 'status', 'content': f'⚙️ {agent_display} utilise {tool_name}...'})}\n\n"

                elif kind == "on_tool_end":
                    yield f"data: {json.dumps({'type': 'status', 'content': 'done'})}\n\n"

                elif kind == "on_chain_end" and node_name == "supervisor":
                    pass
                            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
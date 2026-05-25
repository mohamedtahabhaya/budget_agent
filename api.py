from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import json
from graph import graph 
from finance_tools import parse_receipt_image, transcribe_audio

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

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
    audio_data: Optional[str] = None
    
    workspace_id: str = "workspace_famille_dupont"
    user_id: str = "user_mohamed"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    async def event_generator():
        config = {"configurable": {"thread_id": request.session_id}}
        
        final_message = request.message
        
        # Audio transcription pre-processing
        if request.audio_data:
            yield f"data: {json.dumps({'type': 'status', 'content': '⚙️ Transcribing audio note...'})}\n\n"
            try:
                import os
                import base64
                
                temp_audio_path = "scratch/temp_voice.webm"
                os.makedirs("scratch", exist_ok=True)
                with open(temp_audio_path, "wb") as f:
                    f.write(base64.b64decode(request.audio_data))
                
                transcription_res = transcribe_audio.invoke({"audio_file_path": temp_audio_path})
                
                if os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
                    
                if transcription_res.startswith("Transcription successful:"):
                    transcript_text = transcription_res.replace("Transcription successful:", "").strip()
                    final_message = f"{transcript_text}\n\n{final_message}".strip()
                    status_msg = f'🎤 Transcription: "{transcript_text}"'
                    yield f"data: {json.dumps({'type': 'status', 'content': status_msg})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'content': f'Audio transcription failed: {transcription_res}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Audio transcription error: {str(e)}'})}\n\n"

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
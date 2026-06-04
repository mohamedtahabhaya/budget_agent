from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import json
from graph import graph 
from finance_tools import parse_receipt_image, transcribe_audio, process_recurring_transactions

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("[STARTUP] Processing recurring transactions...")
    try:
        res = process_recurring_transactions.invoke({"workspace_id": "workspace_coloc_taha_mohamed"})
        print(f"[STARTUP] Result:\n{res}")
    except Exception as e:
        print(f"[STARTUP ERROR] Failed to process recurring transactions: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/invite/accept", response_class=HTMLResponse)
async def accept_invite(token: str):
    from database import SessionLocal, InvitationModel, UserModel, WorkspaceModel
    db = SessionLocal()
    try:
        invite = db.query(InvitationModel).filter(InvitationModel.token == token).first()
        if not invite:
            return HTMLResponse(content="""
            <html>
                <head>
                    <title>Invalid Invitation</title>
                    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
                    <style>
                        body { font-family: 'Outfit', sans-serif; background: #0b0f19; color: #f3f4f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                        .card { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 40px; text-align: center; max-width: 400px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
                        h1 { color: #f87171; margin-top: 0; font-weight: 600; }
                        p { color: #9ca3af; font-size: 1.1em; line-height: 1.6; }
                        .btn { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 12px; font-weight: bold; transition: background 0.2s; }
                        .btn:hover { background: #2563eb; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>⚠️ Invitation Not Found</h1>
                        <p>The provided invitation token is invalid or has expired.</p>
                        <a href="/" class="btn">Back to Home</a>
                    </div>
                </body>
            </html>
            """, status_code=404)
            
        if invite.is_accepted:
            user_exists = db.query(UserModel).filter(UserModel.email == invite.email, UserModel.workspace_id == invite.workspace_id).first()
            user_msg = f" (User: {user_exists.name})" if user_exists else ""
            return HTMLResponse(content=f"""
            <html>
                <head>
                    <title>Invitation Already Accepted</title>
                    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
                    <style>
                        body {{ font-family: 'Outfit', sans-serif; background: #0b0f19; color: #f3f4f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                        .card {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 40px; text-align: center; max-width: 400px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }}
                        h1 {{ color: #fbbf24; margin-top: 0; font-weight: 600; }}
                        p {{ color: #9ca3af; font-size: 1.1em; line-height: 1.6; }}
                        .btn {{ display: inline-block; margin-top: 20px; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 12px; font-weight: bold; transition: background 0.2s; }}
                        .btn:hover {{ background: #2563eb; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>💡 Already a Member</h1>
                        <p>This invitation has already been accepted{user_msg}. You are already a member of this workspace.</p>
                        <a href="/" class="btn">Back to Home</a>
                    </div>
                </body>
            </html>
            """)
            
        base_id = f"user_{invite.name.lower().replace(' ', '_')}"
        user_id = base_id
        counter = 1
        while db.query(UserModel).filter(UserModel.id == user_id).first():
            user_id = f"{base_id}_{counter}"
            counter += 1
            
        from database import NotificationPreferenceModel
        new_user = UserModel(
            id=user_id,
            workspace_id=invite.workspace_id,
            name=invite.name,
            role=invite.role,
            email=invite.email,
            income_mad=invite.income_mad
        )
        db.add(new_user)
        
        new_pref = NotificationPreferenceModel(user_id=user_id)
        db.add(new_pref)
        
        invite.is_accepted = True
        db.commit()
        
        ws = db.query(WorkspaceModel).filter(WorkspaceModel.id == invite.workspace_id).first()
        ws_name = ws.name if ws else "Workspace"
        
        return HTMLResponse(content=f"""
        <html>
            <head>
                <title>Invitation Accepted!</title>
                <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
                <style>
                    body {{
                        font-family: 'Outfit', sans-serif;
                        background: radial-gradient(circle at center, #1e1b4b, #090514);
                        color: #f3f4f6;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        overflow: hidden;
                    }}
                    .card {{
                        background: rgba(255, 255, 255, 0.03);
                        backdrop-filter: blur(20px);
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        border-radius: 32px;
                        padding: 50px 40px;
                        text-align: center;
                        max-width: 450px;
                        box-shadow: 0 30px 60px rgba(0,0,0,0.8), inset 0 1px 0 rgba(255,255,255,0.1);
                        animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1);
                    }}
                    @keyframes fadeInUp {{
                        from {{ opacity: 0; transform: translateY(20px); }}
                        to {{ opacity: 1; transform: translateY(0); }}
                    }}
                    .icon-container {{
                        width: 80px;
                        height: 80px;
                        background: linear-gradient(135deg, #10b981, #059669);
                        border-radius: 50%;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        margin: 0 auto 24px;
                        box-shadow: 0 10px 20px rgba(16, 185, 129, 0.3);
                        animation: scaleIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 0.3s both;
                    }}
                    @keyframes scaleIn {{
                        from {{ transform: scale(0); }}
                        to {{ transform: scale(1); }}
                    }}
                    .icon-container svg {{
                        width: 40px;
                        height: 40px;
                        fill: none;
                        stroke: white;
                        stroke-width: 3;
                        stroke-linecap: round;
                        stroke-linejoin: round;
                    }}
                    h1 {{
                        font-size: 2.2em;
                        margin: 0 0 10px;
                        font-weight: 600;
                        background: linear-gradient(to right, #ffffff, #9ca3af);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                    }}
                    h2 {{
                        font-size: 1.2em;
                        color: #10b981;
                        margin: 0 0 20px;
                        font-weight: 400;
                    }}
                    p {{
                        color: #9ca3af;
                        font-size: 1.05em;
                        line-height: 1.6;
                        margin: 0 0 30px;
                    }}
                    .details {{
                        background: rgba(0, 0, 0, 0.2);
                        border-radius: 16px;
                        padding: 16px;
                        margin-bottom: 30px;
                        font-size: 0.95em;
                        text-align: left;
                        border: 1px solid rgba(255,255,255,0.03);
                    }}
                    .details-row {{
                        display: flex;
                        justify-content: space-between;
                        margin-bottom: 8px;
                    }}
                    .details-row:last-child {{
                        margin-bottom: 0;
                    }}
                    .details-label {{ color: #6b7280; }}
                    .details-value {{ color: #e5e7eb; font-weight: 600; }}
                    .btn {{
                        display: inline-block;
                        width: 100%;
                        box-sizing: border-box;
                        padding: 14px 28px;
                        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                        color: white;
                        text-decoration: none;
                        border-radius: 16px;
                        font-weight: 600;
                        letter-spacing: 0.5px;
                        transition: all 0.3s;
                        box-shadow: 0 8px 16px rgba(59, 130, 246, 0.2);
                    }}
                    .btn:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 12px 20px rgba(59, 130, 246, 0.3);
                        background: linear-gradient(135deg, #60a5fa, #2563eb);
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon-container">
                        <svg viewBox="0 0 24 24">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    </div>
                    <h1>Congratulations!</h1>
                    <h2>Welcome Aboard</h2>
                    <p>You have successfully joined the shared budget workspace <strong>{ws_name}</strong>.</p>
                    
                    <div class="details">
                        <div class="details-row">
                            <span class="details-label">Name:</span>
                            <span class="details-value">{invite.name}</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">Email:</span>
                            <span class="details-value">{invite.email}</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">Role:</span>
                            <span class="details-value">{invite.role}</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">Reported Income:</span>
                            <span class="details-value">{invite.income_mad} MAD</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">User ID:</span>
                            <span class="details-value">{user_id}</span>
                        </div>
                    </div>
                    
                    <a href="/" class="btn">Access Dashboard</a>
                </div>
            </body>
        </html>
        """)
    except Exception as e:
        db.rollback()
        return HTMLResponse(content=f"<h3>An error occurred during invitation validation: {str(e)}</h3>", status_code=500)
    finally:
        db.close()

class UpdatePreferencesRequest(BaseModel):
    budget_alerts_enabled: Optional[bool] = None
    recurring_tx_enabled: Optional[bool] = None
    csv_import_enabled: Optional[bool] = None
    browser_push_enabled: Optional[bool] = None

@app.get("/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    from database import SessionLocal, NotificationPreferenceModel, UserModel
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return {"error": f"User '{user_id}' not found."}
            
        pref = db.query(NotificationPreferenceModel).filter(NotificationPreferenceModel.user_id == user_id).first()
        if not pref:
            pref = NotificationPreferenceModel(user_id=user_id)
            db.add(pref)
            db.commit()
            
        return {
            "user_id": user_id,
            "budget_alerts_enabled": pref.budget_alerts_enabled,
            "recurring_tx_enabled": pref.recurring_tx_enabled,
            "csv_import_enabled": pref.csv_import_enabled,
            "browser_push_enabled": pref.browser_push_enabled
        }
    finally:
        db.close()

@app.post("/preferences/{user_id}")
async def update_user_preferences(user_id: str, request: UpdatePreferencesRequest):
    from database import SessionLocal, NotificationPreferenceModel, UserModel
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return {"error": f"User '{user_id}' not found."}
            
        pref = db.query(NotificationPreferenceModel).filter(NotificationPreferenceModel.user_id == user_id).first()
        if not pref:
            pref = NotificationPreferenceModel(user_id=user_id)
            db.add(pref)
            
        if request.budget_alerts_enabled is not None:
            pref.budget_alerts_enabled = request.budget_alerts_enabled
        if request.recurring_tx_enabled is not None:
            pref.recurring_tx_enabled = request.recurring_tx_enabled
        if request.csv_import_enabled is not None:
            pref.csv_import_enabled = request.csv_import_enabled
        if request.browser_push_enabled is not None:
            pref.browser_push_enabled = request.browser_push_enabled
            
        db.commit()
        return {
            "success": True,
            "preferences": {
                "budget_alerts_enabled": pref.budget_alerts_enabled,
                "recurring_tx_enabled": pref.recurring_tx_enabled,
                "csv_import_enabled": pref.csv_import_enabled,
                "browser_push_enabled": pref.browser_push_enabled
            }
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/accounts")
async def get_accounts(workspace_id: str = "workspace_coloc_taha_mohamed"):
    from database import SessionLocal, AccountModel
    db = SessionLocal()
    try:
        accounts = db.query(AccountModel).filter(AccountModel.workspace_id == workspace_id).all()
        return [{"name": acc.name, "slug": acc.slug, "balance": acc.balance, "currency": acc.currency, "type": acc.type} for acc in accounts]
    finally:
        db.close()

@app.get("/savings-goals")
async def get_savings_goals(workspace_id: str = "workspace_coloc_taha_mohamed"):
    from database import SessionLocal, SavingsGoalModel
    db = SessionLocal()
    try:
        goals = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == workspace_id).all()
        return [{"id": g.id, "name": g.name, "target": g.target, "current": g.current, "target_date": g.target_date} for g in goals]
    finally:
        db.close()

@app.get("/notifications")
async def get_notifications_list(workspace_id: str = "workspace_coloc_taha_mohamed", limit: int = 5):
    from database import SessionLocal, NotificationModel
    db = SessionLocal()
    try:
        notifs = db.query(NotificationModel).filter(NotificationModel.workspace_id == workspace_id).order_by(NotificationModel.timestamp.desc()).limit(limit).all()
        return [{"id": n.id, "message": n.message, "timestamp": n.timestamp, "is_read": n.is_read} for n in notifs]
    finally:
        db.close()


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
    
    workspace_id: str = "workspace_coloc_taha_mohamed"
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
                    tool_name = event["name"]
                    output = event["data"].get("output")
                    yield f"data: {json.dumps({'type': 'status', 'content': 'done'})}\n\n"
                    if tool_name == "create_transaction" and isinstance(output, str) and "CRITICAL" in output:
                        yield f"data: {json.dumps({'type': 'notification', 'content': output})}\n\n"

                elif kind == "on_chain_end" and node_name == "supervisor":
                    pass
                            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
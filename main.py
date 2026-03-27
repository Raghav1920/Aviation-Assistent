import os
import re
import json
import asyncpg
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

print(f"HOST={os.getenv('DB_HOST')}")
print(f"USER={os.getenv('DB_USER')}")  
print(f"PASS={'SET' if os.getenv('DB_PASSWORD') else 'MISSING'}")

db_pool = None
FORBIDDEN_KEYWORDS = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    try:
        print(f"🔌 Connecting as user: '{os.getenv('DB_USER')}'")
        print(f"🔌 To host: '{os.getenv('DB_HOST')}'")

        db_pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 6543)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "postgres"),
            min_size=1,
            max_size=5,
            statement_cache_size=0,
            ssl="require"  # Required for Supabase pooler
        )
        print("✅ Successfully connected to Supabase!")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
    yield
    if db_pool:
        await db_pool.close()

app = FastAPI(title="Aviation AI - Dynamic Unified Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    user_query: str
    history: list[ChatMessage] = []

class ChatResponse(BaseModel):
    explanation: str
    sql_executed: str
    intent_detected: str

# --- Security Validation ---
def validate_sql(sql: str) -> bool:
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        return False
    for word in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{word}\b", sql_upper):
            return False
    return True

# --- AGENT 1: The Router ---
def route_intent(user_query: str) -> str:
    prompt = f"""
    You are the Intent Router for an Aviation AI Assistant.
    Analyze the user's question and classify it into exactly ONE of these three categories:

    1. "GENERAL": Asking for definitions (e.g., "What is load factor?"), general greetings, or off-topic questions.
    2. "FLIGHT_SEARCH": The user acts like a traveler. They want to find flights, flight schedules, check ticket prices, find the best states to visit, or ask about delays.
    3. "FINANCIAL_ANALYSIS": The user acts like a business manager. They ask about total revenue, profit, fuel costs, aircraft performance, load factors, or canceled flights statistics.

    User Question: "{user_query}"
    Output ONLY one word: "GENERAL", "FLIGHT_SEARCH", or "FINANCIAL_ANALYSIS".
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite-preview',
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0)
    )
    return response.text.strip().upper()

# --- AGENT 2: General Knowledge Base ---
def handle_general_query(user_query: str) -> str:
    prompt = f"""
    You are an elite, strict Aviation Assistant.
    User Question: "{user_query}"
    
    CRITICAL RULES:
    1. You ONLY answer questions related to Aviation, Airlines, Flight Travel, or Revenue Management (Load Factor, Yield, CASK, etc.).
    2. If the user asks about ANYTHING else (e.g., sports, cricket, politics, weather, history, coding, celebrities), you MUST reply EXACTLY with:
       "I apologize, but that is outside my area of expertise. How can I help you with flight planning or analytics today?"
    3. Do NOT attempt to answer the off-topic question under any circumstances.
    4. If they say hello, politely greet them and explain your aviation capabilities.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt, 
        config=types.GenerateContentConfig(temperature=0.0) # Lowered temp so it never breaks the rules
    )
    return response.text.strip()

# --- AGENT 3: SQL Expert ---
def generate_sql(user_query: str, intent: str, history: list) -> dict:
    history_text = "\n".join([f"{msg.role}: {msg.content}" for msg in history[-4:]])

    prompt = f"""
    You are a PostgreSQL Expert for an Aviation Company. 
    
    Previous Chat History:
    {history_text}
    
    Current Question: {user_query}
    Detected Intent: {intent}

    CRITICAL SCHEMA DICTIONARY:
    Table Name: "Avaiation Data" (You MUST use double quotes!)
    
    Columns available:
    "FlightDate", "Flight_Number", "Aircraft_Type", "Origin", "Origin_State", 
    "Destination", "Destination_State", "Total_Seats", "Passengers", 
    "Avg_Ticket_Price_INR", "Ancillary_Revenue_Per_Pax_INR", "Fuel_Cost_INR", 
    "Delay_Minutes", "Canceled_Flag", "Competitor_Avg_Price_INR", "Booking_Lead_Days"

    RULES:
    1. You MUST wrap the table name AND all column names in double quotes!
    2. "Delay_Minutes" is stored as text. To do math: CAST("Delay_Minutes" AS INT).
    3. FOR RECOMMENDATIONS ("best place", "where to visit"): Fetch multiple rows (LIMIT 10). Group by "Destination". You MUST include SUM("Passengers") as "Total_Passengers" and AVG("Avg_Ticket_Price_INR") as "Average_Price". 
    4. AVOID CRASHES: If grouping by month, DO NOT use subqueries, window functions, or nested selects. Use a simple: EXTRACT(MONTH FROM CAST("FlightDate" AS DATE)). Group by both Month and Destination.
    5. Formulas for FINANCIAL_ANALYSIS:
       - Total Revenue = ("Passengers" * "Avg_Ticket_Price_INR") + ("Passengers" * "Ancillary_Revenue_Per_Pax_INR")
       - Profit = Total Revenue - "Fuel_Cost_INR"
       - Load Factor = ("Passengers" * 100.0) / "Total_Seats"

    Output strictly in valid JSON format with a single key: "sql_query".
    """
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json")
    )
    
    try:
        raw_text = response.text.strip()
        if raw_text.startswith("```json"): 
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)
    except Exception as e:
        raise ValueError("AI failed to format JSON correctly.")

# --- AGENT 4: The Synthesizer ---
def synthesize_data(user_query: str, sql_data: list, intent: str) -> str:
    prompt = f"""
    You are an AI reporting on Aviation Data.
    Detected Intent: {intent}
    User Question: "{user_query}"
    Raw Database Data: {sql_data}

    TONE & STYLE:
    - If Intent is "FLIGHT_SEARCH": Act like a friendly, expert travel advisor. 
    - If Intent is "FINANCIAL_ANALYSIS": Act like a sharp corporate data analyst providing actionable business insights.

    FORMATTING RULES FOR RECOMMENDATIONS (Crucial):
    If the user asks for destination recommendations (e.g., "best place to visit", "best destination each month"), use the raw data to provide a rich answer. Use these exact bullet points for your recommendations:
    * 🏆 **Most Popular:** State the destination with the highest passenger volume from the data.
    * 💰 **Best Value:** State the destination with the cheapest average ticket price from the data.
    * 🌤️ **Travel & Weather Context:** Add 1 sentence of your own general knowledge explaining why it is a good time to visit that state/destination (e.g., weather, festivals, tourist season).

    FORMATTING RULES FOR GENERAL QUERIES:
    1. Format money amounts with the ₹ symbol (INR).
    2. Use Markdown tables if there is a long list of data (but not for the recommendations above).
    3. Do not mention SQL, databases, or how you got the data. Just present the insights naturally.
    """
    
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt, 
        config=types.GenerateContentConfig(temperature=0.3) # 0.3 allows it to be creative with the weather context
    )
    return response.text.strip()

# --- Orchestrator API Endpoint ---
@app.post("/chat", response_model=ChatResponse)
async def chat_with_aviation_bot(request: ChatRequest):
    try:
        # 1. Route the Intent
        intent = route_intent(request.user_query)
        print(f"🚦 Detected Intent: {intent}")

        # 2. Handle General Chat
        if intent == "GENERAL":
            reply = handle_general_query(request.user_query)
            return ChatResponse(explanation=reply, sql_executed="", intent_detected=intent)

        # 3. Handle Data Request
        ai_response = generate_sql(request.user_query, intent, request.history)
        sql_query = ai_response.get("sql_query", "")

        if not sql_query:
            return ChatResponse(
                explanation="I couldn't generate a safe query for that request.",
                sql_executed="",
                intent_detected=intent
            )

        # 4. Security Validation
        if not validate_sql(sql_query):
            raise HTTPException(status_code=400, detail="AI generated an unsafe query. Blocked.")

        # 5. Execute Async SQL Query (WITH SAFETY NET)
        try:
            async with db_pool.acquire() as connection:
                await connection.execute("SET statement_timeout = '5000ms'")
                records = await connection.fetch(sql_query)
                data = [dict(record) for record in records]
                
        except asyncpg.exceptions.PostgresError as db_error:
            # Catch database errors (like bad AI SQL) so the server doesn't crash!
            print(f"⚠️ SQL Execution Failed: {db_error}")
            return ChatResponse(
                explanation="I tried to analyze that, but the specific breakdown you asked for is a bit too complex. Could you try asking for a simpler summary (like one month at a time)?",
                sql_executed=sql_query,
                intent_detected=intent
            )

        # 6. Synthesize Data into Markdown
        final_reply = synthesize_data(request.user_query, data, intent)

        return ChatResponse(explanation=final_reply, sql_executed=sql_query, intent_detected=intent)

    except Exception as e:
        print("\n" + "🔴" * 20)
        traceback.print_exc()
        print("🔴" * 20 + "\n")
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")
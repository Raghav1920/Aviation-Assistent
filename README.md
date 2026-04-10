# ✈️ Aviation Assistent: AI-Powered Revenue & Route Analytics

An enterprise-grade, Multi-Agent AI Analytics Platform built to transform how stakeholders interact with aviation data. This project bridges the gap between traditional Business Intelligence and cutting-edge Generative AI by allowing non-technical users to query complex PostgreSQL databases using conversational natural language (**Text-to-SQL**).

### 🌐 Live Demo
**Try the live application here:** [Aviation Assistent on Vercel](https://aviation-assistent.vercel.app/)

---

## 🚀 Key Features

* **Conversational Analytics (Text-to-SQL):** Replaces complex SQL queries with natural language. Users can simply ask, *"Which aircraft generated the highest profit on the Mumbai route?"* and receive a formatted, actionable insight.
* **Multi-Agent Intent Routing:** Utilizes Google Gemini to autonomously detect user intent:
  * **Flight Search Agent:** Acts as a travel advisor, providing the best value and most popular destinations.
  * **Financial Analyst Agent:** Calculates complex KPIs (Load Factor, Yield, Profit Margins, Total Revenue).
  * **General Knowledge Agent:** Explains aviation metrics or strictly refuses off-topic (non-aviation) queries.
* **Algorithmic Security & Validation:** Built-in Python validation layer that scans generated SQL to block destructive keywords (`DROP`, `UPDATE`) and prevents nested subquery crashes.
* **Dynamic Data Synthesis:** Generates safe, optimized SQL aggregations, executes them asynchronously, and translates the raw JSON results into highly readable Markdown tables with added business context.

## 🛠️ Tech Stack

* **Artificial Intelligence:** Google Generative AI (`gemini-2.5-flash`), Structured JSON Outputs.
* **Backend:** Python, FastAPI.
* **Database:** PostgreSQL (Hosted on Supabase), Asynchronous pooling via `asyncpg`.
* **Frontend:** HTML5, Tailwind CSS, Marked.js (for dynamic Markdown table rendering).

## 🧠 How the AI Architecture Works

1. **The Router:** The user's query is intercepted by Agent 1, which classifies the intent (`FLIGHT_SEARCH`, `FINANCIAL_ANALYSIS`, or `GENERAL`).
2. **Security Check:** The query passes through a validation layer ensuring the requested intent matches the allowed database columns and safe SQL protocols.
3. **The SQL Generator:** Agent 3 constructs a PostgreSQL query tailored strictly to the Aviation schema.
4. **Execution:** The backend uses an asynchronous connection pool (`asyncpg`) to execute the query against Supabase safely.
5. **The Synthesizer:** Agent 4 receives the raw data from the database and synthesizes it into a conversational response, adding formatting and insights before returning it to the UI.

## 💡 Use Cases Demonstrated

### 1. Business Intelligence & Financials
> **User:** *"What was the average ticket price and load factor for Boeing 737s in March?"*  
> **Ava (AI):** Safely pulls `Passengers`, `Total_Seats`, and `Avg_Ticket_Price`, performs the calculations dynamically, and returns a formatted Markdown table for the management team.

### 2. Trip Planning & Recommendations
> **User:** *"What is the best destination to visit in December?"*  
> **Ava (AI):** Analyzes passenger volume to find the "Most Popular" and ticket prices to find the "Best Value", then appends real-world context about winter tourism before responding to the user.

### 3. Strict Guardrails
> **User:** *"Who won the cricket world cup?"*  
> **Ava (AI):** *"I apologize, but that is outside my area of expertise. I am strictly an Aviation Data AI. How can I help you with flight planning or analytics today?"*

---

## ⚙️ Local Setup & Installation

If you wish to run the backend locally:

**1. Clone the repository:**
```bash
git clone https://github.com/yourusername/aviation-assistent.git
cd aviation-assistent

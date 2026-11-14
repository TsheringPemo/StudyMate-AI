# StudyMate AI – An Intelligent Study Planning Agent

**DAT404 – Intelligent and Generative Agents**  
**Assignment D: Build, Evaluate and Defend a Custom AI Agent**

## About the Project

StudyMate AI is a tool-using intelligent agent designed to help students organise their academic tasks and manage their available study time.

It analyses students' tasks, priorities, deadlines and estimated study hours to generate realistic and personalised study plans. Students can also provide feedback, allowing the agent to adapt its future planning decisions.

Unlike a traditional chatbot, StudyMate AI combines an optional Large Language Model (LLM) with Python-based tools, memory, decision-making rules and self-reflection to produce reliable and explainable study plans.

**Main Goal:** Help students decide what to study based on their priorities, deadlines and the time they actually have.

## Key Features

- **Task Management:** Add and manage academic tasks, priorities and deadlines.
- **Intelligent Study Planning:** Generate study plans based on available hours and task urgency.
- **LLM Integration:** Interpret natural-language requests using Ollama and Qwen3.
- **Tool Selection:** Select and execute relevant Python tools based on student requests.
- **Memory:** Store tasks, previous planning sessions and feedback using SQLite.
- **Feedback and Adaptation:** Adjust future study plans based on student feedback.
- **Self-Reflection:** Check generated plans before presenting them.
- **Evaluation:** Run automated tests to assess agent functionality, reliability and safety.

## How the Agent Works

StudyMate AI follows an agent-based workflow:

1. Receives and validates the student's request.
2. Interprets the request using the LLM or rule-based fallback.
3. Selects appropriate tools based on the request.
4. Retrieves relevant information from memory.
5. Executes Python tools for task ranking, time management and deadline checking.
6. Generates and validates a study plan.
7. Presents the result and uses student feedback to improve future plans.

The application also provides an **Agent Trace**, allowing users to observe the agent's decision-making and tool execution steps.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Agent logic and planning tools |
| Streamlit | Interactive user interface |
| Ollama + Qwen3 | Local LLM integration |
| SQLite | Database and memory management |
| Pandas | Data handling |
| Matplotlib | Evaluation visualisations |
| Requests | Communication with the Ollama API |

## Project Structure

| File | Description |
|---|---|
| `app.py` | Main Streamlit application and user interface |
| `agent.py` | Agent workflow, interpretation and reflection |
| `tools.py` | Python tools and tool-selection policy |
| `scheduler.py` | Task ranking, time allocation and adaptation |
| `memory.py` | SQLite database and memory management |
| `guardrails.py` | Input validation and safety checks |
| `evaluation.py` | Automated testing and evaluation |
| `generate_assets.py` | Generates evaluation figures |
| `docs/` | Project documentation, diagrams and guides |

## Installation and Setup

### Requirements

- Python 3.14
- Git
- Ollama (optional, for LLM functionality)

### 1. Clone the Repository

```powershell
git clone <https://github.com/TsheringPemo/StudyMate-AI.git>
cd StudyMate-AI
```

### 2. Create and Activate a Virtual Environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Set Up the Optional LLM

Install Ollama and download the Qwen3 model:

```powershell
ollama pull qwen3:8b
```

For computers with limited resources, `qwen3:4b` can also be used.

### 5. Run the Application

```powershell
streamlit run app.py
```

**Note:** StudyMate AI can also operate without Ollama. If the LLM is unavailable, the application automatically uses its rule-based fallback.

## Testing and Evaluation

StudyMate AI includes **70 automated test cases across eight testing groups**, covering:

- Planner
- Time Parsing
- Interpretation
- Tool Selection
- Safety
- Robustness
- LLM Integration
- Performance

Run the evaluation using:

```powershell
python evaluation.py
```

The application also includes an Evaluation page where testing results and performance metrics can be viewed.

## AI Assistance

Claude and ChatGPT were used as supporting tools during development for debugging, troubleshooting errors, understanding programming concepts and exploring possible solutions. The implementation involved individual planning, development decisions, integration and testing. AI-generated suggestions were reviewed, adapted and tested during development.

---

**Developed as part of DAT404 – Intelligent and Generative Agents**  
**Sherubtse College | Royal University of Bhutan**
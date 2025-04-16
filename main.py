from dotenv import load_dotenv
import os
from openai import OpenAI
import json
import datetime

import requests


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAPI_KEY"),
)


def exec_command(command: str) -> str:
    try:
        print("🔨 Tool Called: exec_command", command)
        os.system(command)
        return f"Command '{command}' executed successfully."
    except Exception as e:
        return f"Error executing command '{command}': {str(e)}"


def make_directory(folder_path: str) -> str:
    try:
        os.makedirs(folder_path, exist_ok=True)
        return f"Folder '{folder_path}' created successfully."
    except Exception as e:
        return f"Error creating folder '{folder_path}': {str(e)}"


def edit_file(params) -> str:
    try:
        file_name = params["file_name"]
        content = params["content"]
        folder_path = params["folder_path"] if "folder_path" in params else None
        if folder_path:
            file_name = os.path.join(folder_path, file_name)
        print("🔨 Tool Called: edit_file", file_name)
        with open(file_name, "w") as f:
            f.write(content)
        return f"File '{file_name}' edited successfully."

    except Exception as e:
        return f"Error editing file '{file_name}': {str(e)}"

def log_message(message):
    try:
        if hasattr(message, "dict"):  # handle OpenAI object
            message = message.dict()
        with open("session_memory.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(message) + "\n")
    except Exception as e:
        print("⚠️ Failed to log message:", e)


system_prompt = """

You are a helpful AI code assistant specialized in building Python-based applications, including web apps (Flask, Streamlit, Dash), dashboards, and data analysis tools.

You follow the strict reasoning loop:
1. **Plan** – Break down the user request into clear execution steps. Use internal Tree-of-Thought (ToT) reasoning to explore multiple architectural options, libraries, or approaches. Choose the best strategy.
2. **Action** – Execute exactly one terminal or file operation using an available tool.
3. **Observe** – Wait for the result of the executed action (confirmation message, file output, errors, etc.).
4. **Output** – Summarize progress. If work is not finished, loop back to Plan.

---

## ✅ You Can Build Applications Using:
- **Flask** (web server and API backends)
- **Streamlit** (data-driven UIs)
- **Dash** (Plotly-based dashboards)
- **Python Scripts** (with pandas, matplotlib, scikit-learn, etc.)
- **Jupyter / Analysis Reports** (Markdown/HTML exports)

---

## 📦 Project Output Expectations

- Create a root project folder (named from user intent).
- Setup relevant subfolders (`/scripts`, `/assets`, `/data`, `/models`).
- Install required packages in a local `venv`.
- Add a `README.md` with run instructions.
- Automatically generate `.gitignore` and `requirements.txt`.
- Launch the app with the appropriate terminal command (`flask run`, `streamlit run`, etc.)

---

## 🛠️ Tools You Can Use

- `exec_command`: Run a terminal command
- `make_directory`: Create folders
- `edit_file`: Create or write to files

---




## 🧠 Tree-of-Thought Prompting: Sample Reasoning

User Query: "Build a dashboard using Dash to show COVID-19 trends from a CSV file with line charts and filters."

```json
{ "step": "plan", "content": "The user wants a dashboard using Dash. I will create the folder, install Dash, and build an app with filters and a line chart. First, create the project folder." }
{ "step": "action", "function": "make_directory", "input": "./covid_dashboard" }
{ "step": "observe", "output": "Folder created" }
{ "step": "plan", "content": "Now I will set up a virtual environment and install Dash-related packages." }
{ "step": "action", "function": "exec_command", "input": "cd covid_dashboard && python -m venv venv && venv\Scripts\\activate && pip install dash pandas" }
{ "step": "observe", "output": "Packages installed." }
{ "step": "plan", "content": "Now I will create 'app.py' with a basic Dash layout and CSV data loading logic." }
{ "step": "action", "function": "edit_file", "input": {
    "file_name": "app.py",
    "folder_path": "./covid_dashboard",
    "content": "import dash\\nimport dash_core_components as dcc\\nimport dash_html_components as html\\nimport pandas as pd\\n..."
} }
{ "step": "observe", "output": "File created." }
{ "step": "plan", "content": "Now I will create a README.md with run instructions." }
{ "step": "action", "function": "edit_file", "input": {
    "file_name": "README.md",
    "folder_path": "./covid_dashboard",
    "content": "# COVID Dashboard\\n\\nRun with:\\n```\\ncd covid_dashboard\\nvenv\Scripts\\activate\\npython app.py\\n```"
} }
{ "step": "output", "content": "App created. Run it using the README instructions." }
```

---

You must always follow the strict loop: **Plan → Action → Observe → Output**  
Use thoughtful reasoning before choosing a package or structure. For analysis apps, consider where to place input data, model files, and helper modules.

You are working on a Windows machine.
"""

avialable_tools = {
    "exec_command": {
        "description": "Takes a command as input and executes it in the terminal of the folder path",
        "fn": exec_command,
    },
    "edit_file": {
        "description": "Takes a file name, content and folder path as an input and edits the file inside the folder directory",
        "fn": edit_file,
    },
    "make_directory": {
        "description": "Takes a folder name as input and creates the folder inside the project directory",
        "fn": make_directory,
    },
}

messages = [{"role": "system", "content": system_prompt}]

# Load past session
if os.path.exists("session_memory.jsonl"):
    with open("session_memory.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue

while True:
    # messages = [
    #     {"role": "system", "content": system_prompt},
    # ]

    user_query = input("➡️➡️ Enter your query (or type 'reset'): ")
    messages.append({"role": "user", "content": user_query})
    log_message({"role": "user", "content": user_query})

    if user_query.lower() == "reset":
        open("session_memory.jsonl", "w").close()
        messages = [{"role": "system", "content": system_prompt}]
        print("🧽 Session reset.")
        continue


    if user_query.lower() == "thanks":
        print("Exiting...")
        break
    while True:
        response = client.chat.completions.create(
            model="gpt-4o", response_format={"type": "json_object"}, messages=messages,

        )

        parsed_response = json.loads(response.choices[0].message.content)
        messages.append(response.choices[0].message)
        log_message(response.choices[0].message.dict())


        if parsed_response["step"] == "output":
            print(parsed_response["content"])
            break

        elif parsed_response["step"] == "action":
            if avialable_tools.get(parsed_response["function"]):
                function = avialable_tools[parsed_response["function"]]["fn"]
                input_param = parsed_response["input"]
                output = function(input_param)
                messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "step": "observe",
                                "output": output,
                            }
                        ),
                    }
                )
                log_message(
                    {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "step": "observe",
                                "output": output,
                            }
                        ),
                    }
                )

            else:
                print("🔴🔴 Function not found.", parsed_response["function"])
                break
        elif parsed_response["step"] == "plan":
            print(f"✅ {parsed_response['content']}")
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "step": "plan",
                            "content": parsed_response["content"],
                        }
                    ),
                }
            )
        else:
            print("🔴🔴 Invalid step.", parsed_response)
            break
            
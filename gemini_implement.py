import json
import re
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import os

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

# Tool functions (same as before)
def query_db(sql):
    pass

def run_command(command):
    print(command)
    result = os.system(command=command)
    return result

def get_weather(city: str):
    print("🔨 Tool Called: get_weather", city)
    url = f"https://wttr.in/{city}?format=%C+%t"
    response = requests.get(url)
    if response.status_code == 200:
        return f"The weather in {city} is {response.text}."
    return "Something went wrong"

avaiable_tools = {
    "get_weather": {
        "fn": get_weather,
        "description": "Takes a city name as an input and returns the current weather for the city"
    },
    "run_command": {
        "fn": run_command,
        "description": "Takes a command as input to execute on system and returns output"
    }
}

# System prompt (same as before)
system_prompt1 = """ You are an helpfull AI Assistant who is specialized in resolving user query.
    You work on start, plan, action, observe mode.
    For the given user query and available tools, plan the step by step execution, based on the planning,
    select the relevant tool from the available tool. and based on the tool selection you perform an action to call the tool.
    Wait for the observation and based on the observation from the tool call resolve the user query.

    Rules:
    - Follow the Output JSON Format.
    - Always perform one step at a time and wait for next input
    - Carefully analyse the user query
    - This is a windows machine. So keep any OS operations windows specific.

    Output JSON Format:
    {
        "step": "string",
        "content": "string",
        "function": "The name of function if the step is action",
        "input": "The input parameter for the function"
    }

    Available Tools:
    - get_weather: Takes a city name as an input and returns the current weather for the city
    - run_command: Takes a command as input to execute on system and returns ouput

    Example:
    User Query: What is the weather of new york?
    Output: { "step": "plan", "content": "The user is interseted in weather data of new york" }
    Output: { "step": "plan", "content": "From the available tools I should call get_weather" }
    Output: { "step": "action", "function": "get_weather", "input": "new york" }
    Output: { "step": "observe", "output": "12 Degree Cel" }
    Output: { "step": "output", "content": "The weather for new york seems to be 12 degrees." }

    Tree-of-Thought Prompting: For more complex multi-part queries, allowing the model to explore multiple reasoning paths for each part and then evaluate them can increase the likelihood of a consistent and correct overall response.

Here are a few multi-part weather query scenarios and how a ToT approach might look internally (you would guide the model to consider these options):

**Case 1: Weather in Two Locations with Ambiguity**

User Query: "What's the weather like in London and is it warmer than here?"

Thought 1 (Initial Plan): Get the weather for London and compare it to the current weather. *Potential Issue: "here" is ambiguous.*

Branch 1.1 (Clarification): Ask the user for their current location to make the comparison.
   * Action: `{"step": "output", "content": "To compare the weather, could you please tell me your current location?"}`

Branch 1.2 (Assume Default Location): Assume the user's current location is the system's default location (Indore).
   * Action 1: `{"step": "action", "function": "get_weather", "input": "London"}`
   * Action 2: `{"step": "action", "function": "get_weather", "input": "Indore"}`
   * Observe 1: `{"step": "observe", "output": "Partly cloudy 15°C"}` (London)
   * Observe 2: `{"step": "observe", "output": "Sunny 32°C"}` (Indore)
   * Output: `{"step": "output", "content": "The weather in London is partly cloudy with a temperature of 15°C. That is cooler than the current weather in Indore, which is sunny at 32°C."}`

Evaluation: Branch 1.1 is more robust as it resolves ambiguity. Branch 1.2 makes an assumption that might be incorrect.

**Case 2: Weather Forecast and Specific Conditions**

User Query: "Will it rain in Mumbai tomorrow, and what will the temperature be like in the evening?"

Thought 1 (Linear Plan): Get the forecast for Mumbai and then try to extract evening temperature and rain information. *Potential Issue: Might require parsing a longer forecast string.*

Branch 2.1 (Separate Queries - More Structured):
   * Action 1: `{"step": "action", "function": "get_weather", "input": "Mumbai tomorrow rain"}` (Assuming the tool can handle specific forecast queries)
   * Action 2: `{"step": "action", "function": "get_weather", "input": "Mumbai tomorrow evening temperature"}` (Assuming the tool can handle time-specific temperature)
   * Observe 1: `{"step": "observe", "output": "Yes, there is a 60% chance of rain tomorrow in Mumbai."}`
   * Observe 2: `{"step": "observe", "output": "The temperature in Mumbai tomorrow evening is expected to be around 28°C."}`
   * Output: `{"step": "output", "content": "Yes, there is a 60% chance of rain in Mumbai tomorrow. The temperature in the evening is expected to be around 28°C."}`

Branch 2.2 (Single Forecast Query - More Parsing):
   * Action: `{"step": "action", "function": "get_weather", "input": "Mumbai tomorrow forecast"}`
   * Observe: `{"step": "observe", "output": "Tomorrow in Mumbai: Morning - Sunny 30°C, Afternoon - Cloudy with showers 32°C, Evening - Light rain 28°C, Night - Partly cloudy 26°C"}`
   * Thought 2.2.1 (Parsing): Extract rain information (Yes, light rain) and evening temperature (28°C) from the forecast string.
   * Output: `{"step": "output", "content": "Yes, there will be light rain in Mumbai tomorrow evening. The temperature is expected to be around 28°C."}`

Evaluation: Branch 2.1 relies on more specific tool capabilities but is cleaner. Branch 2.2 requires more complex parsing of the tool's output.

**Case 3: Weather Comparison with Units**

User Query: "Is it hotter in Delhi than in Bangalore right now? Tell me the temperatures in Fahrenheit."

Thought 1 (Direct Comparison): Get temperatures and then compare. *Potential Issue: Default units might be Celsius.*

Branch 3.1 (Unit Conversion in Tool - Ideal): Assume the \`get_weather\` tool can handle unit conversion.
   * Action 1: \`{"step": "action", "function": "get_weather", "input": "Delhi Fahrenheit"}\`
   * Action 2: \`{"step": "action", "function": "get_weather", "input": "Bangalore Fahrenheit"}\`
   * Observe 1: \`{"step": "observe", "output": "Delhi: 95°F"}\`
   * Observe 2: \`{"step": "observe", "output": "Bangalore: 82°F"}\`
   * Output: \`{"step": "output", "content": "Yes, it is hotter in Delhi (95°F) than in Bangalore (82°F) right now."}\`

Branch 3.2 (Unit Conversion After Observation - More Complex):
   * Action 1: \`{"step": "action", "function": "get_weather", "input": "Delhi"}\` (Default Celsius)
   * Action 2: \`{"step": "action", "function": "get_weather", "input": "Bangalore"}\` (Default Celsius)
   * Observe 1: \`{"step": "observe", "output": "Delhi: 35°C"}\`
   * Observe 2: \`{"step": "observe", "output": "Bangalore: 28°C"}\`
   * Thought 3.2.1 (Conversion): Convert 35°C to Fahrenheit: (35 * 9/5) + 32 = 95°F. Convert 28°C to Fahrenheit: (28 * 9/5) + 32 = 82.4°F (round to 82°F).
   * Output: \`{"step": "output", "content": "Yes, it is hotter in Delhi (95°F) than in Bangalore (82°F) right now."}\`

Evaluation: Branch 3.1 is cleaner if the tool supports unit conversion. Branch 3.2 requires additional calculation logic.
"""


fullstack_agent_prompt = """
You are a terminal-based AI Agent specialized in building full-stack web development projects.

Your core loop follows a strict 4-phase reasoning pipeline:
1. **Plan**
2. **Action**
3. **Observe**
4. **Output**

You always perform exactly one step at a time and never skip or merge steps.

---

## 🧠 Thought Process (Tree-of-Thought Planning)

For each user request, you must **simulate multiple reasoning branches** to evaluate alternative approaches. This allows better tool use and decision-making before executing actions.

Examples of Thought Branching:
- Should I create a new file or modify an existing one?
- Should I install packages before generating code, or vice versa?
- Should I split logic into separate modules?

Only after exploring and evaluating the branches, choose the best path and continue to the next step in the loop.

---

## 🛠️ Terminal-Based Constraints

You operate **only through the terminal (CLI)**. No GUI interaction is allowed.

Supported actions include:
- Writing files (`echo "content" > file`)
- Installing packages (`pip install flask`, `npm install`)
- Reading files (`type filename.txt`)
- Running build tools (`npm run build`, etc.)

All such commands are executed using the `run_command` tool.

---

## 📦 Responsibilities

You are expected to:
- Initialize full-stack project folders
- Generate file structures
- Create backend routes (Flask, Express, etc.)
- Setup frontend scaffolds (React, HTML, etc.)
- Add features (e.g., login/signup) via follow-up prompts
- Manage package installation
- Parse existing code and modify files appropriately
- Always explain your reasoning and next step clearly in the `plan` phase
- You are working on a "windows" based machine. (strict)
---

## 🔁 Reasoning Loop Format

For every query, always follow this loop:

1. **Plan** – Decide the sequence of actions and explore options via internal branching.
2. **Action** – Execute **only one command** using `run_command`. Use `echo`, `type`, `mkdir`, etc.
3. **Observe** – Wait for and process the result/output or exit code.
4. **Output** – Give a user-facing update and explain the result. If more steps are required, loop back to Plan.

You never perform multiple steps together. Each step should result in a new JSON block.

---

## 🧰 Available Tool

- `run_command`: Executes a terminal command on a Windows system and returns the output or error code.

---

## 🧪 Example: Flask Hello World App

**User Query:** "Create a basic Flask backend with a route that says 'Hello, World!' in a file named 'app.py'."

**Thoughts (Tree-of-Thought Planning):**
Branch A: First write the Flask code, then install Flask.
Branch B: Install Flask first, then write the code.
Evaluation: Installing Flask first ensures smoother execution if the user runs it right away.
→ Choose Branch B.

Final Response (Step-by-Step):

```json
{
  "step": "plan",
  "content": "The user wants a Flask app with a 'Hello, World!' route. I will first install Flask, then create 'app.py' with the route code."
}
"""


# Message history
history = [{"role": "user", "parts": [fullstack_agent_prompt]}]

# Loop
while True:
    user_query = input("> ")
    if user_query.lower() == "bye":
        break

    history.append({"role": "user", "parts": [user_query]})

    processed_output = False  # Initialize the flag for each user query

    while True:
        response = model.generate_content(history,
                                          generation_config=genai.types.GenerationConfig(
                                              temperature=0.7,
                                              max_output_tokens=1024)
                                          )

        if not response.candidates or not response.candidates[0].content.parts:
            print("⚠️ Gemini did not return a valid response.")
            print(response.candidates)
            break

        output = response.candidates[0].content.parts[0].text.strip()

        # 🧽 Clean up markdown wrappers
        if output.startswith("```json"):
            output = output.replace("```json", "").replace("```", "").strip()
        elif output.startswith("```"):
            output = output.replace("```", "").strip()

        try:
            json_objects = re.findall(r'\{.*?\}', output, re.DOTALL)
            processed_output = False


            for obj_str in json_objects:
                parsed_output = json.loads(obj_str)
                history.append({"role": "model", "parts": [json.dumps(parsed_output)]})
                step = parsed_output.get("step")
                content = parsed_output.get("content")
                print(f"Step: {step}")
                print(f"Content: {content}")

                if step == "plan":
                    continue  # Go to the next parsed object or next iteration

                elif step == "action":
                    tool_name = parsed_output.get("function")
                    tool_input = parsed_output.get("input")
                    if avaiable_tools.get(tool_name):
                        observation = avaiable_tools[tool_name]["fn"](tool_input)
                        history.append({"role": "user", "parts": [json.dumps({"step": "observe", "output": observation})]})
                        continue # Go to the next parsed object or next iteration

                elif step == "observe":
                    print(f"Observation: {parsed_output.get('output')}")
                    history.append({"role": "user", "parts": ["Based on the observation, what is the final output?"]})
                    continue # Go to the next parsed object or next iteration

                elif step == "output":
                    print(f"🤖: {content}")
                    processed_output = True

                    break # Exit the inner loop after the final output


            if processed_output:
                break # Exit the outer loop after getting the final output
            elif not json_objects:
                print("⚠️ No JSON object found in Gemini response.")
                print(history)
                break


        except json.JSONDecodeError as e:
            print(f"⚠️ Couldn't parse JSON output from Gemini: {e}")
            print(output)
            break
from langchain_ollama import ChatOllama


llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0
)


def create_plan(state):

    task = state["task"]

    prompt = f"""
You are a senior software engineer and debugging expert.

Your job is to analyze a coding task and create a clear debugging plan.

Coding task:
{task}

Create a step-by-step plan for solving this problem.

The plan should cover:

1. Understand the problem
2. Locate the relevant code
3. Analyze the root cause
4. Design the fix
5. Test the fix

Keep the plan concise and practical.

Return only the numbered debugging plan.
"""

    response = llm.invoke(prompt)

    plan = response.content.split("\n")

    return {
        "plan": plan,
        "status": "planning_complete"
    }
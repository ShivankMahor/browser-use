import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import threading
import asyncio
from langchain_openai import ChatOpenAI
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use import Agent
import os

api_key = os.getenv("OPENAI_API_KEY")
task = os.getenv("TASK")
if not api_key:
    raise ValueError("OPENAI_API_KEY is not set!")
if not task:
    raise ValueError("Task is not given!")

# Initialize the model
llm = ChatOpenAI(
	model='gpt-4o',
	temperature=0.0,
)
extend_system_message = (
	'REMEMBER the most important RULES: '
    '1. if you need login credentials, payment details , OTP, or any other user specific information then always call wait 16 seconds so user can input login details dont not input details by yourself!!!'
    '2. if the agent is repeating same steps again and again and failing then always wait for user to intervene'
)
agent = Agent(task=task, llm=llm, extend_system_message=extend_system_message)

# Thread-safe control flags
is_paused = threading.Event()
is_stopped = threading.Event()

task_status = None
async def agent_runner():
    """ Continuously runs the agent while respecting pause and stop commands """
    try:
        while not is_stopped.is_set():
            if is_paused.is_set():
                await asyncio.sleep(1)  # Wait while paused
                continue
            task_status = await agent.run()  # Run agent step
            print("task_status:",task_status)
            if task_status:
                print('if task_status:')
                print("task_status.is_done():", task_status.is_done())
                if task_status.is_done():
                    print("inside isDone()")
                    is_stopped.set()
                    print("Final Result: ",task_status.final_result())
                    print("Exiting the process now...")
                    sys.stdout.flush()  # Ensure all output is sent before exiting
                    os._exit(0)
                else : 
                    print("outside, task_status.finalResult()",task_status.final_result() )
                    is_stopped.set()
            else: print("outside the if task_status : ",task_status)

        print("Agent has stopped. task_status =", task_status)
    except Exception as e:
        print(f"Error during automation: {str(e)}")
        sys.exit(1)

def start_agent():
    """ Runs the agent in a separate event loop """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(agent_runner())

# Start the agent in a separate thread
thread = threading.Thread(target=start_agent, daemon=True)
thread.start()

# Electron IPC handlers (via stdin input from Electron)
def handle_commands():
    while True:
        command = sys.stdin.readline().strip()
        print("\ntask_status = ",task_status,"\n")
        if command == "pause":
            is_paused.set()
            print("🔄 Agent Paused")
            if hasattr(agent, "pause"):
                agent.pause()
        elif command == "resume":
            is_paused.clear()
            print("▶️ Agent Resumed")
            if hasattr(agent, "resume"):
                agent.resume()
        elif command == "stop":
            is_stopped.set()
            print("⏹️ Agent Stopping")
            if hasattr(agent, "stop"):
                agent.stop()
            break  # Exit loop when stopped

# Run the command handler in the main thread
handle_commands()
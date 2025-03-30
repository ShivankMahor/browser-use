import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from plyer import notification
import asyncio
import threading
import time
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller, ActionResult
from browser_use.browser.browser import Browser, BrowserConfig

# Get environment variables from the Electron app
api_key = os.getenv("OPENAI_API_KEY")
task = os.getenv("TASK")
profile = os.getenv("PROFILE_DIR")  # This is passed from the Electron app

print(task, profile)

if not api_key:
    print("Error: OPENAI_API_KEY is not set!")
    sys.exit(1)

if not task:
    print("Error: TASK is not set!")
    sys.exit(1)

if not profile:
    print("Warning: PROFILE is not set, using Default profile")
    profile = "Default"
else:
    print(f"Using profile: {profile}")

extend_system_message = (
	'REMEMBER the most important RULES:'
    '1. Notify the user when task is completed'
    '2. if you need login credentials, payment details , OTP, or any other user specific information then always calls notify and wait 16 seconds so user can input login details dont not input details by yourself!!!'
    '3. if the agent is repeating same steps again and again and failing then always wait for user to intervene'
)
# Get Chrome user data directory based on OS
def get_chrome_user_data_dir():
    if os.name == 'nt':  # Windows
        return os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data')
    elif sys.platform == 'darwin':  # macOS
        return os.path.expanduser('~/Library/Application Support/Google/Chrome')
    else:  # Linux
        return os.path.expanduser('~/.config/google-chrome')

# Initialize the model
llm = ChatOpenAI(
    model='gpt-4o',
    temperature=0.0,
)
controller = Controller()
@controller.registry.action('Notify the user with a message')
def notify(msg: str):
    if notification.notify is None:
        print("Error: notification.notify is None!")
        return
    
    notification.notify(
        title="Alert",
        message=msg,
        timeout=20
    )
    return ActionResult(extracted_content="Notified the user with msg :"+msg, include_in_memory=True)
# Get the user data directory
user_data_dir = get_chrome_user_data_dir()

# Initialize browser with profile configuration
browser = Browser(
    config=BrowserConfig(
        chrome_instance_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' if os.name == 'nt' else '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        extra_chromium_args=[
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile}"
        ]
    )
)

agent = Agent(task=task, llm=llm, browser=browser,controller=controller, extend_system_message=extend_system_message, planner_llm=llm)

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
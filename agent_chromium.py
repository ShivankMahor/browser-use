# import sys
# import os
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# import threading
# import asyncio
# from langchain_openai import ChatOpenAI
# from browser_use.browser.browser import Browser, BrowserConfig
# from browser_use import Agent
# import os

# api_key = os.getenv("OPENAI_API_KEY")
# task = os.getenv("TASK")
# if not api_key:
#     raise ValueError("OPENAI_API_KEY is not set!")
# if not task:
#     raise ValueError("Task is not given!")

# # Initialize the model
# llm = ChatOpenAI(
# 	model='gpt-4o',
# 	temperature=0.0,
# )
# extend_system_message = (
# 	'REMEMBER the most important RULES: '
#     '1. if you need login credentials, payment details , OTP, or any other user specific information then always call wait 16 seconds so user can input login details dont not input details by yourself!!!'
#     '2. if the agent is repeating same steps again and again and failing then always wait for user to intervene'
# )
# agent = Agent(task=task, llm=llm, extend_system_message=extend_system_message)

# # Thread-safe control flags
# is_paused = threading.Event()
# is_stopped = threading.Event()

# task_status = None
# async def agent_runner():
#     """ Continuously runs the agent while respecting pause and stop commands """
#     try:
#         while not is_stopped.is_set():
#             if is_paused.is_set():
#                 await asyncio.sleep(1)  # Wait while paused
#                 continue
#             task_status = await agent.run()  # Run agent step
#             print("task_status:",task_status)
#             if task_status:
#                 print('if task_status:')
#                 print("task_status.is_done():", task_status.is_done())
#                 if task_status.is_done():
#                     print("inside isDone()")
#                     is_stopped.set()
#                     print("Final Result: ",task_status.final_result())
#                     print("Exiting the process now...")
#                     sys.stdout.flush()  # Ensure all output is sent before exiting
#                     os._exit(0)
#                 else : 
#                     print("outside, task_status.finalResult()",task_status.final_result() )
#                     is_stopped.set()
#             else: print("outside the if task_status : ",task_status)

#         print("Agent has stopped. task_status =", task_status)
#     except Exception as e:
#         print(f"Error during automation: {str(e)}")
#         sys.exit(1)

# def start_agent():
#     """ Runs the agent in a separate event loop """
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     loop.run_until_complete(agent_runner())

# # Start the agent in a separate thread
# thread = threading.Thread(target=start_agent, daemon=True)
# thread.start()

# # Electron IPC handlers (via stdin input from Electron)
# def handle_commands():
#     while True:
#         command = sys.stdin.readline().strip()
#         print("\ntask_status = ",task_status,"\n")
#         if command == "pause":
#             is_paused.set()
#             print("🔄 Agent Paused")
#             if hasattr(agent, "pause"):
#                 agent.pause()
#         elif command == "resume":
#             is_paused.clear()
#             print("▶️ Agent Resumed")
#             if hasattr(agent, "resume"):
#                 agent.resume()
#         elif command == "stop":
#             is_stopped.set()
#             print("⏹️ Agent Stopping")
#             if hasattr(agent, "stop"):
#                 agent.stop()
#             break  # Exit loop when stopped

# # Run the command handler in the main thread
# handle_commands()




import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import asyncio
from plyer import notification
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserConfig, Controller, ActionResult,BrowserContextConfig
import psutil 

load_dotenv()

# Initialize the model
llm = ChatOpenAI(
    model='gpt-4o',
    temperature=0.0,
)
env_task = os.getenv("TASK")

# Setup Browser with Chrome path
browser = Browser(
    config=BrowserConfig(
        new_context_config=BrowserContextConfig(keep_alive=True),
    ),
)

extend_system_message = (
    'REMEMBER the most important RULES:\n'
    '1. Always Notify the user when task is completed\n'
    '2. If you need login credentials, payment details, OTP, or any other user-specific information, always notify and wait\n'
    '3. If the agent is failing repeatedly, wait for user intervention'
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
class AgentController:
    def __init__(self, first_task):
        """Initialize the agent with the first task."""
        self.agent = Agent(
            task=first_task,
            llm=llm,
            controller=controller,
            browser=browser,
            extend_system_message=extend_system_message
        )
        self.task = first_task
        self.running = True
        self.paused = False
        self.waiting_for_followup = False
        # asking_follow_up_prompt = False
    
    async def run_agent(self):
        """Run the agent loop. If not paused, wait for a new task if no command is set.
        When the agent finishes a task, it will check for follow-up commands."""
        # Run the initial task if provided
        if self.task:
            print(f"Running initial task: {self.task}")
            await self.agent.run()
            self.task = None
            # self.agent.add_new_task("Open 2 tabs")
            # await self.agent.run()

        while self.running:
            if not self.paused:
                # Agent is ready to accept a new task or follow-up command
                has_printed_prompt = False  # <- Add this flag
                while self.task is None and self.running and not self.paused:
                    self.asking_follow_up_prompt = True
                    if not has_printed_prompt:
                        print("Agent waiting for a follow-up task")
                        has_printed_prompt = True  # <- Only print once
                    await asyncio.sleep(2)

                self.asking_follow_up_prompt = False
                if not self.running:
                    break
                if self.task:
                    print(f"New task received: {self.task}")
                    self.agent.add_new_task(self.task)
                    self.task = None
                    print("Running agent with the new task...")
                    result = await self.agent.run()
                    print("Agent Result:", result)
                    if result.has_errors():
                        print("Result has errors:", result.errors())
                        self.running = False
                        break
            else:
                # Agent is paused; let the global command listener handle resume/stop
                print("Agent is paused. Awaiting resume command...")
                await asyncio.sleep(3)
        print("Agent has stopped.")

    def pause(self):
        if not self.paused:
            self.paused = True
            self.agent.pause()
            print("Agent paused.")

    def resume(self):
        if self.paused:
            self.paused = False
            self.agent.resume()
            # Optionally, call any resume method on the agent if available
            print("Agent resumed.")

    def stop(self):
        self.running = False
        self.agent.stop()
        print("Agent stopped.")

    def set_new_task(self, task):
        if not self.paused:
            self.task = task
            print("New task set: " + task)
    
    # def restart(self, new_task=None):
    #     print("🔁 Restarting the agent...")

    #     # Re-initialize the Agent with the same config
    #     self.agent = Agent(
    #         task=new_task or "No task set yet",
    #         llm=llm,
    #         controller=controller,
    #         browser=browser,
    #         extend_system_message=extend_system_message
    #     )
        
    #     self.task = new_task
    #     self.paused = False
    #     self.waiting_for_followup = False

    #     print("✅ Agent restarted.")


async def global_command_listener(controller: AgentController):
    """
    Listen for global commands. Commands include:
      - new_task: <task>  to set a new task.
      - pause            to pause the agent.
      - resume           to resume if paused.
      - stop or exit     to stop the agent.
    """
    while controller.running:
        command = await asyncio.to_thread(input, "\nWaiting for user input...")
        cmd = command.strip()
        print("Command Recieved: " + cmd)
        if cmd.lower().startswith("new_task:"):
            task_text = cmd[len("new_task:"):].strip()
            if task_text:
                controller.set_new_task(task_text)
            else:
                print("No task provided after 'new_task:'")
        elif cmd.lower().startswith("interrupt:"):
            task_text = cmd[len("interrupt:"):].strip()
            print("Controller.asking_follow_up_prompt: ",controller.asking_follow_up_prompt)
            if task_text and not controller.asking_follow_up_prompt:
                print("⚡ Interrupting agent with new task: " + task_text)
                controller.agent.add_new_task(task_text)
            elif task_text: 
                print("Agent was asking for follow up task")
                controller.set_new_task(task_text)
            else:    
                print("⚠️ No task provided after 'interrupt:'")
        elif cmd.lower() == "pause":
            controller.pause()
        elif cmd.lower() == "resume":
            controller.resume()
        elif cmd.lower() in ["stop", "exit"]:
            controller.stop()
            break
        else:
            print("Unknown command. Please try again.")

# def kill_chrome_if_not_using_profile(target_profile):
#     chrome_found = False
#     print(f"\n[INFO] Target Chrome profile: {target_profile}\n")

#     for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
#         try:
#             if proc.info['name'] and 'chrome.exe' in proc.info['name'].lower():
#                 pid = proc.info['pid']
#                 cmdline_args = proc.info['cmdline']
                
#                 used_profile = None
#                 for arg in cmdline_args:
#                     if arg.startswith("--profile-directory="):
#                         used_profile = arg.split("=")[-1]
#                         break

#                 if used_profile:
#                     print(f"[FOUND] Chrome PID {pid} using profile: {used_profile}")
#                     if used_profile.lower() != target_profile.lower():
#                         print(f"  ⛔ Killing PID {pid} — Mismatched profile")
#                         proc.kill()
#                     else:
#                         print(f"  ✅ PID {pid} is using the correct profile")
#                         chrome_found = True
#                 else:
#                     print(f"[FOUND] Chrome PID {pid} has NO profile — Killing it")
#                     proc.kill()

#         except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
#             continue

#     if not chrome_found:
#         print("\n[INFO] No Chrome with the correct profile is currently running.\n")


async def kill_all_chrome():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                # print(f"Killing Chrome process: PID {proc.info['pid']} — {proc.info['name']}")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # print("\n✅ All Chrome processes terminated.")

async def main_async():
    await kill_all_chrome()
    # first_task = await asyncio.to_thread(input, "Enter initial task for the agent new: ")
    agent_controller = AgentController(first_task=env_task)
    # Create both tasks concurrently
    agent_task = asyncio.create_task(agent_controller.run_agent())
    command_task = asyncio.create_task(global_command_listener(agent_controller))
    await asyncio.gather(agent_task, command_task)


if __name__ == '__main__':
    asyncio.run(main_async())

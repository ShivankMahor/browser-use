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
# llm = ChatOpenAI(
#     model='gpt-4o',
#     temperature=0.0,
# )


from langchain_together import ChatTogether
env_profile = os.getenv("PROFILE_DIR")
env_task = os.getenv("TASK")
env_api_key = os.getenv("TOGETHER_API_KEY")

llm = ChatTogether(
    together_api_key=env_api_key,
    model="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
    temperature=0.0,
    # model_kwargs={"response_format": "json"}
)
env_max_step = os.getenv("MAX_STEP")
if not env_max_step:
    print("Error Max Steps not defined",env_max_step)
    sys.exit(1)

def _setup_browser_config(profile):
    """Set up the browser configuration based on OS and profile"""
    if os.name == 'nt':  # Windows
        user_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data')
        chrome_path = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    elif sys.platform == 'darwin':  # macOS
        user_data_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome')
        chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    else:  # Linux
        user_data_dir = os.path.expanduser('~/.config/google-chrome')
        chrome_path = '/usr/bin/google-chrome'
    
    print("user_data_dir and Profile:", user_data_dir, profile)
    return BrowserConfig(
        browser_binary_path=chrome_path,
        new_context_config=BrowserContextConfig(
			keep_alive=True,
		),   
        extra_browser_args=[
            f"--user-data-dir={user_data_dir}",
            f"--profile-directory={profile}"
        ]
    )
# Setup Browser with Chrome path
# browser = Browser(
#     config=BrowserConfig(
#         browser_binary_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
#         new_context_config=BrowserContextConfig(keep_alive=True),
#     ),
# )

browser = Browser(config=_setup_browser_config(env_profile))

extend_system_message = (
    'REMEMBER the most important RULES:\n'
    '1. Always Notify the user when task is completed\n'
    '2. If you need login credentials, payment details, OTP, or any other user-specific information, always notify the user and wait for them to enter details\n'
    '3. Always ask the user for login details and notify the user and wait for them to fill up the essential details'
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
            # print(f"Running initial task: {self.task}")
            if not env_max_step:
                print("Error: Max Steps not defined", env_max_step)
                sys.exit(1)
            max_steps = int(env_max_step)
            await self.agent.run(max_steps=max_steps)
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
                    currentStep = self.agent.state.n_steps
                    print("Current Step: ",currentStep)
                    result = await self.agent.run(max_steps=max_steps+currentStep)
                    print("Agent Result:", result)
                    if result.has_errors():
                        print("Result has errors:", result.errors())
                        # self.running = False
                        # break
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

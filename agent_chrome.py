import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import asyncio
import threading
import time
from plyer import notification
from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller, ActionResult
from browser_use.browser.browser import Browser, BrowserConfig


class AgentController:
    def __init__(self, initial_task=None, profile_dir=None):
        # Get environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        env_task = os.getenv("TASK")
        env_profile = os.getenv("PROFILE_DIR")
        
        # Check for API key
        if not api_key:
            print("Error: OPENAI_API_KEY is not set!")
            sys.exit(1)
        
        # Determine task priority: parameter > environment variable > default
        if initial_task:
            task = initial_task
        elif env_task:
            task = env_task
            print(f"Using task from environment: {task}")
        else:
            print("Error: No task provided and TASK environment variable is not set!")
            sys.exit(1)
        
        # Determine profile priority: parameter > environment variable > default
        if profile_dir:
            profile = profile_dir
        elif env_profile:
            profile = env_profile
            print(f"Using profile from environment: {profile}")
        else:
            profile = "Default"
            print("Warning: PROFILE_DIR is not set, using Default profile")
        
        # Initialize LLM
        llm = ChatOpenAI(model='gpt-4o')
        
        # System message for guidance
        extend_system_message = (
            'REMEMBER the most important RULES:\n'
            '1. Always Notify the user when task is completed\n'
            '2. If you need login credentials, payment details, OTP, or any other user-specific information, always notify and wait\n'
            '3. If the agent is failing repeatedly, wait for user intervention'
        )
        
        # Browser configuration
        browser_config = self._setup_browser_config(profile)
        browser = Browser(config=browser_config)
        
        # Controller setup
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
        # Initialize agent
        self.agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            controller=controller,
            extend_system_message=extend_system_message,
            planner_llm=llm
        )
        
        # Control flags
        self.running = False
        self.is_paused = threading.Event()
        self.is_stopped = threading.Event()
        self.task_status = None
        self.agent_thread = None

    def _setup_browser_config(self, profile):
        """Set up the browser configuration based on OS and profile"""
        # Get Chrome user data directory
        if os.name == 'nt':  # Windows
            user_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data')
            chrome_path = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
        elif sys.platform == 'darwin':  # macOS
            user_data_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome')
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        else:  # Linux
            user_data_dir = os.path.expanduser('~/.config/google-chrome')
            chrome_path = '/usr/bin/google-chrome'
        
        # Configure browser
        return BrowserConfig(
            chrome_instance_path=chrome_path,
            extra_chromium_args=[
                f"--user-data-dir={user_data_dir}",
                f"--profile-directory={profile}"
            ]
        )

    async def run_agent(self):
        """Run the agent with pause/stop capabilities"""
        self.running = True
        self.is_stopped.clear()
        self.is_paused.clear()
        
        try:
            while not self.is_stopped.is_set():
                if self.is_paused.is_set():
                    await asyncio.sleep(0.5)  # Reduced sleep time for responsiveness
                    continue
                
                self.task_status = await self.agent.run()
                print(f"Task status: {self.task_status}")
                
                if self.task_status and hasattr(self.task_status, 'is_done') and self.task_status.is_done():
                    print("✅ Task completed", self.task_status)
                    sys.stdout.flush()  # Ensure all output is sent before exiting
                    os._exit(0)
        except Exception as e:
            print(f"Error during automation: {str(e)}")
            self.running = False
            self.is_stopped.set()

    def start(self):
        """Start the agent in a separate thread"""
        if self.agent_thread and self.agent_thread.is_alive():
            print("Agent is already running")
            return
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.run_agent())

    def pause(self):
        """Pause the agent"""
        self.is_paused.set()
        if hasattr(self.agent, 'pause'):
            self.agent.pause()

    def resume(self):
        """Resume the agent"""
        self.is_paused.clear()
        if hasattr(self.agent, 'resume'):
            self.agent.resume()

    def stop(self):
        """Stop the agent"""
        self.is_stopped.set()
        if hasattr(self.agent, 'stop'):
            self.agent.stop()
        self.running = False

    def add_task(self, new_task):
        """Add a new task to the agent"""
        print("New Task:", new_task)
        self.agent.add_new_task(new_task)
        return True


def handle_commands(controller):
    """Handle commands from stdin instead of using a menu"""
    while True:
        command = sys.stdin.readline().strip()
        
        if command == "pause":
            print('Pausing agent...')
            controller.pause()
            
        elif command == "resume":
            print('Resuming agent...')
            controller.resume()
            
        elif command == "stop":
            print('Stopping agent...')
            controller.stop()
            
        elif command.startswith("new_task"):
            new_task = command[len("new_task"):].strip()
            success = controller.add_task(new_task)
            if success and controller.is_paused.is_set():
                print('Resuming agent with new task...')
                controller.resume()
                
        elif command == "exit":
            print('Exiting...')
            if controller.running:
                controller.stop()
            break
            
        else:
            print('Unknown command. Available commands: pause, resume, stop, new_task, exit')


def main():
    # Create controller with environment variables
    controller = AgentController()
    
    # Start agent automatically in a separate thread
    agent_thread = threading.Thread(target=controller.start)
    agent_thread.daemon = True  # Make thread exit when main program exits
    agent_thread.start()
    
    # Handle commands from stdin
    handle_commands(controller)
    
    # Wait for the agent thread to complete if still running
    if agent_thread.is_alive():
        agent_thread.join(timeout=5)


if __name__ == '__main__':
    main()
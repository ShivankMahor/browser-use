import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sys
import os
import asyncio
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig

# Get environment variables from the Electron app
api_key = os.getenv("OPENAI_API_KEY")
task = os.getenv("TASK")
profile = os.getenv("PROFILE_DIR")  # This is passed from the Electron app
print(task,profile)
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

agent = Agent(task=task, llm=llm, browser=browser)

async def main():
    try:
        print(f"Starting browser automation with task: {task}")
        print(f"Using Chrome profile: {profile}")
        await agent.run()
        print("Task completed successfully")
    except Exception as e:
        print(f"Error during automation: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())